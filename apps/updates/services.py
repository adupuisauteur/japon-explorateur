"""
Imports contrôlés et synchronisations : analyse, comparaison, rapport, validation,
intégration historisée. Aucune notice locale n'est supprimée parce qu'elle manque
dans un export ou une moisson (§9.5).
"""
import logging
import os
from contextlib import contextmanager

from django.conf import settings
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.catalog.models import Catalogue, Record
from apps.catalog.services import (_title_key, clean_source_data, compare_with_existing, set_record_status,
                                   upsert_record)
from apps.connectors.base import NOT_AN_INCIDENT, ConnectorError
from apps.connectors.http import last_exchange
from apps.incidents import services as incidents
from apps.connectors.registry import get_connector

from . import importers
from .models import ImportJob, IncomingRecord, SyncJob

logger = logging.getLogger(__name__)

SAMPLE_SIZE = 8


# --------------------------------------------------------------------------- imports


def analyze_import(job):
    """Détecte le format, lit l'en-tête, propose un mapping et un échantillon (§9.6)."""
    path = job.file.file.path
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if not job.format:
        job.format = importers.detect_format(job.file_name, head)
    columns, rows, info = importers.read_rows(path, job.format, delimiter=job.delimiter, sheet_name=job.sheet_name)
    sample, total = [], 0
    for row in rows:
        total += 1
        if len(sample) < SAMPLE_SIZE:
            sample.append(row)
    job.columns = columns
    job.sample = sample
    job.total_rows = total
    job.encoding = info.get("encoding", job.encoding)
    job.delimiter = info.get("delimiter", job.delimiter)
    job.sheet_name = info.get("sheet_name", job.sheet_name)
    job.report = {**(job.report or {}), "info": {k: v for k, v in info.items() if k != "sheets"},
                  "sheets": info.get("sheets", [])}
    if not job.mapping:
        job.mapping = importers.auto_mapping(columns)
    job.unknown_columns = importers.unknown_columns(columns, job.mapping)
    job.file_sha256 = job.file_sha256 or importers.file_sha256(path)
    job.save()
    return job


def stage_import(job, *, generate_ids=False):
    """Compare chaque ligne avec la base et crée la zone de validation (aucune écriture de notice)."""
    job.incoming.all().delete()
    columns, rows, _ = importers.read_rows(job.file.file.path, job.format, delimiter=job.delimiter,
                                           sheet_name=job.sheet_name)
    title_index = {}
    for pk, title, cat in Record.objects.values_list("pk", "original_title", "catalogue__name"):
        title_index.setdefault(_title_key(title), (pk, title, cat))
    catalogues = {c.code: c for c in Catalogue.objects.all()}
    seen_ids = set()
    counts = {"new": 0, "modified": 0, "unchanged": 0, "error": 0, "possible_duplicate": 0, "duplicate_in_file": 0,
              "warnings": 0}
    errors = []
    batch = []
    for n, row in enumerate(rows, start=1):
        data = importers.build_data(row, job.mapping, generate_ids=generate_ids)
        catalogue = job.catalogue
        matched = None
        if job.format == "json_export":
            catalogue = catalogues.get(row.get("catalogue.code") or "", job.catalogue)
            if row.get("record_id"):
                matched = Record.objects.filter(record_id=row["record_id"]).select_related("catalogue").first()
                if matched:
                    catalogue = matched.catalogue
                    data.setdefault("source_id", matched.source_id)
        item = IncomingRecord(import_job=job, row_number=n, source_id=data.get("source_id", ""), data=data,
                              raw=row, raw_format=job.format)
        item.data["_catalogue"] = catalogue.code
        clean_source_data(data, item.warnings)
        if item.warnings:
            counts["warnings"] += 1
        if not data.get("source_id"):
            item.comparison, item.error = "error", "Identifiant source absent (colonne non mappée ou vide)."
        elif not data.get("original_title"):
            item.comparison, item.error = "error", "Titre absent."
        elif (catalogue.code, data["source_id"]) in seen_ids:
            item.comparison, item.error = "error", "Identifiant présent plusieurs fois dans le fichier."
            counts["duplicate_in_file"] += 1
        else:
            seen_ids.add((catalogue.code, data["source_id"]))
            existing, status, changed = compare_with_existing(catalogue, data, row, job.format)
            item.matched_record = existing or matched
            item.comparison = status
            item.changed_fields = changed
            if status == "new":
                hint = title_index.get(_title_key(data.get("original_title", "")))
                if hint:
                    item.duplicate_hint = f"Titre identique à une notice existante ({hint[2]} : {hint[1]})"
                    counts["possible_duplicate"] += 1
        if item.comparison == "error":
            errors.append({"row": n, "error": item.error})
        counts[item.comparison] = counts.get(item.comparison, 0) + 1
        # Décision proposée par défaut selon la stratégie
        if item.comparison == "new":
            item.decision = "pending" if job.duplicate_strategy == "review" or item.duplicate_hint else "accept"
        elif item.comparison == "modified":
            item.decision = {"version": "accept", "skip": "reject", "review": "pending"}[job.duplicate_strategy]
        else:
            item.decision = "reject"
        batch.append(item)
        if len(batch) >= 500:
            IncomingRecord.objects.bulk_create(batch)
            batch = []
    IncomingRecord.objects.bulk_create(batch)
    job.counts = counts
    job.errors = errors[:500]
    job.status = "review"
    job.report = {**(job.report or {}), "staged_at": timezone.now().isoformat(), "generate_ids": generate_ids}
    job.save()
    return job


def apply_incoming(items, user, *, origin, dataset_label=""):
    """Intègre les éléments acceptés. Retourne les compteurs."""
    stats = {"created": 0, "updated": 0, "unchanged": 0, "marked_unavailable": 0, "errors": 0}
    catalogues = {c.code: c for c in Catalogue.objects.all()}
    for item in items:
        if item.decision != "accept":
            continue
        try:
            with transaction.atomic():
                if item.comparison == "missing" and item.matched_record:
                    set_record_status(item.matched_record, "unavailable", origin=origin, user=user,
                                      note="Absente de la source lors de la synchronisation (validé)")
                    stats["marked_unavailable"] += 1
                else:
                    data = {k: v for k, v in item.data.items() if not k.startswith("_")}
                    catalogue = catalogues.get(item.data.get("_catalogue")) or (
                        item.import_job.catalogue if item.import_job_id else item.sync_job.catalogue)
                    _, status = upsert_record(catalogue, data, raw=item.raw, raw_format=item.raw_format,
                                              origin=origin, user=user, dataset_label=dataset_label)
                    stats[status] += 1
                item.decision = "applied"
                item.save(update_fields=["decision"])
        except Exception as exc:  # une ligne en erreur n'interrompt pas l'intégration
            logger.warning("Ligne non intégrée : %s", exc)
            item.error = str(exc)[:500]
            item.save(update_fields=["error"])
            stats["errors"] += 1
            operation = f"Intégration ({origin}) de la notice {item.source_id or '?'}"
            if isinstance(exc, DatabaseError):
                incidents.record_database_error(exc, module="importation", operation=operation)
            else:
                incidents.record_exception(exc, module="importation", operation=operation,
                                           category="erreur_traitement", origin="traitement",
                                           extra={"import_job": item.import_job_id, "sync_job": item.sync_job_id})
    return stats


def apply_import(job, user):
    with apply_lock(job.catalogue_id):
        return _apply_import(job, user)


def _apply_import(job, user):
    items = job.incoming.filter(decision="accept").select_related("import_job", "import_job__catalogue")
    stats = apply_incoming(items, user, origin="import", dataset_label=job.dataset_label or job.file_name)
    pending = job.incoming.filter(decision__in=["pending", "hold"]).count()
    job.status = "partially_applied" if pending else "applied"
    job.applied_at = timezone.now()
    job.report = {**(job.report or {}), "applied": stats, "pending_after_apply": pending}
    job.save()
    Catalogue.objects.filter(pk=job.catalogue_id).update(last_success_at=timezone.now(), last_attempt_at=timezone.now())
    if not job.archive_source and job.file and job.status == "applied":
        try:
            os.remove(job.file.file.path)
            job.file.delete()
        except OSError:
            pass
    return stats


def validate_upload(uploaded):
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in settings.IMPORT_ALLOWED_EXTENSIONS:
        raise ValueError(f"Type de fichier non accepté ({ext}). Formats : "
                         + ", ".join(settings.IMPORT_ALLOWED_EXTENSIONS))
    if uploaded.size > settings.IMPORT_MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Fichier trop volumineux (maximum {settings.IMPORT_MAX_FILE_SIZE_MB} Mo).")


# --------------------------------------------------------------------------- synchronisations


def run_sync(job):
    """Exécute une synchronisation et prépare un rapport à valider (aucune intégration silencieuse)."""
    catalogue = job.catalogue
    job.status = "running"
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])
    Catalogue.objects.filter(pk=catalogue.pk).update(last_attempt_at=job.started_at)
    counts = {"new": 0, "modified": 0, "unchanged": 0, "missing": 0, "error": 0}
    try:
        connector = get_connector(catalogue)
        if job.kind == "test":
            ok, message, details = connector.live_test()
            job.status = "done" if ok else "failed"
            job.message = message
            job.report = {"details": details}
            if ok:
                Catalogue.objects.filter(pk=catalogue.pk).update(last_success_at=timezone.now(), last_error="",
                                                                  real_test_ok_at=timezone.now())
                incidents.note_source_recovered(catalogue.code)
            else:
                Catalogue.objects.filter(pk=catalogue.pk).update(last_error=message[:1000])
                diag = dict(last_exchange.get() or {})
                failure = ConnectorError(message, kind=(details or {}).get("error_kind", "technical"),
                                         code=(details or {}).get("error_code") or "test_failed",
                                         http_status=diag.get("http_status"), diagnostic=diag)
                incidents.record_connector_error(failure, module="connecteur", source_code=catalogue.code,
                                                 operation=f"Test du connecteur {catalogue.name}")
        elif job.kind in ("full", "incremental") and connector.supports_harvest:
            since = catalogue.last_success_at if job.kind == "incremental" else None
            seen = set()
            for batch in connector.harvest(since=since, cursor=job.cursor or None):
                for res in batch.results:
                    seen.add(res.source_id)
                    _stage_sync_result(job, catalogue, res, counts)
                job.cursor = batch.cursor or ""
                job.save(update_fields=["cursor"])
            if job.kind == "full":
                for record in Record.objects.filter(catalogue=catalogue, record_status="active").exclude(
                        source_id__in=seen):
                    IncomingRecord.objects.create(sync_job=job, source_id=record.source_id,
                                                  data={"original_title": record.original_title},
                                                  comparison="missing", matched_record=record, decision="pending")
                    counts["missing"] += 1
            job.status = "review" if counts["new"] + counts["modified"] + counts["missing"] else "done"
        else:
            # Source sans moisson : actualisation ciblée des notices déjà connues (ex. Kokusho via IIIF).
            if not connector.supports_fetch:
                raise ConnectorError("Ce connecteur sert aux recherches : il ne propose ni moisson ni actualisation "
                                     "par identifiant. Les notices déjà intégrées sont comparées à chaque nouvelle "
                                     "recherche (« Déjà connu » / « Modifié »).", kind="unsupported",
                                     code="unsupported_operation")
            limit = int(catalogue.config.get("refresh_limit", 200))
            records = Record.objects.filter(catalogue=catalogue).exclude(record_status="deleted").order_by("collected_at")[:limit]
            for record in records:
                try:
                    res = connector.fetch_record(record.source_id)
                except ConnectorError as exc:
                    incidents.record_connector_error(exc, module="metadonnees", source_code=catalogue.code,
                                                     operation=f"Actualisation de la notice {record.source_id} "
                                                               f"({catalogue.name})")
                    if "404" in str(exc):
                        IncomingRecord.objects.create(sync_job=job, source_id=record.source_id,
                                                      data={"original_title": record.original_title},
                                                      comparison="missing", matched_record=record, decision="pending",
                                                      error=str(exc))
                        counts["missing"] += 1
                    else:
                        counts["error"] += 1
                        job.errors = (job.errors or []) + [{"source_id": record.source_id, "error": str(exc)}]
                    continue
                if res is not None:
                    _stage_sync_result(job, catalogue, res, counts)
            job.status = "review" if counts["new"] + counts["modified"] + counts["missing"] else "done"
        if job.kind != "test":
            Catalogue.objects.filter(pk=catalogue.pk).update(last_success_at=timezone.now(), last_error="")
    except ConnectorError as exc:
        job.status = "failed"
        job.message = str(exc)
        if exc.kind not in NOT_AN_INCIDENT:  # une opération non proposée n'est pas un dysfonctionnement
            Catalogue.objects.filter(pk=catalogue.pk).update(last_error=str(exc)[:1000])
            incidents.record_connector_error(exc, module="connecteur", source_code=catalogue.code,
                                             operation=f"{job.get_kind_display()} — {catalogue.name}")
    except DatabaseError as exc:
        logger.exception("Synchronisation %s : erreur de base de données", catalogue.code)
        job.status = "failed"
        job.message = f"Erreur de base de données : {exc.__class__.__name__}"
        incidents.record_database_error(exc, operation=f"{job.get_kind_display()} — {catalogue.name}",
                                        source_code=catalogue.code)
    except Exception as exc:
        logger.exception("Synchronisation %s en échec", catalogue.code)
        job.status = "failed"
        job.message = f"Erreur inattendue : {exc.__class__.__name__}"
        incidents.record_exception(exc, module="connecteur", source_code=catalogue.code,
                                   operation=f"{job.get_kind_display()} — {catalogue.name}",
                                   extra=dict(last_exchange.get() or {}))
    job.counts = counts
    job.finished_at = timezone.now()
    job.save()
    from apps.notifications.services import sync_ended  # 2.0.0 (lot 5)

    sync_ended(job)
    return job


def _stage_sync_result(job, catalogue, res, counts):
    existing, status, changed = compare_with_existing(catalogue, res.data, res.raw, res.raw_format)
    counts[status] = counts.get(status, 0) + 1
    if status == "unchanged":
        Record.objects.filter(pk=existing.pk).update(collected_at=timezone.now())
        return
    IncomingRecord.objects.create(sync_job=job, source_id=res.source_id, data=dict(res.data, _catalogue=catalogue.code),
                                  raw=res.raw, raw_format=res.raw_format, comparison=status, changed_fields=changed,
                                  matched_record=existing, decision="accept" if status == "new" else "pending")


APPLY_INLINE_MAX = 1000  # au-delà, l'intégration d'une synchronisation passe en tâche de fond
_APPLY_LOCK = 20261116  # espace des verrous consultatifs PostgreSQL « intégration d'une source »


class ApplyBusy(Exception):
    """Une intégration est déjà en cours pour cette source (autre onglet, double clic, tâche de fond)."""


@contextmanager
def apply_lock(catalogue_id):
    """2.0.0 (lot 10, incident du 16/11/2026 : deux intégrations simultanées de la liste Aozora, 8 561 conflits).
    Une seule intégration à la fois par source, entre tous les processus (verrou consultatif PostgreSQL, libéré
    à la fin ou si le processus s'arrête). Lève ApplyBusy si le verrou est déjà pris."""
    if connection.vendor != "postgresql":
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [_APPLY_LOCK, catalogue_id])
        if not cursor.fetchone()[0]:
            raise ApplyBusy("Une intégration est déjà en cours pour cette source.")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [_APPLY_LOCK, catalogue_id])


def apply_running(catalogue_id):
    try:
        with apply_lock(catalogue_id):
            return False
    except ApplyBusy:
        return True


def apply_sync(job, user):
    with apply_lock(job.catalogue_id):
        return _apply_sync(job, user)


def _apply_sync(job, user):
    if job.status == "running":
        job.message = ""
    stats = apply_incoming(job.incoming.filter(decision="accept").select_related("sync_job__catalogue"), user,
                           origin="synchronisation")
    pending = job.incoming.filter(decision__in=["pending", "hold"]).count()
    job.status = "partially_applied" if pending else "applied"
    job.report = {**(job.report or {}), "applied": stats}
    job.save()
    return stats


def due_catalogues(now=None):
    now = now or timezone.now()
    for catalogue in Catalogue.objects.exclude(frequency="manual").exclude(status="disabled").filter(sync_paused=False):
        due = catalogue.next_sync_due()
        if due and due <= now and catalogue.can_refresh:
            yield catalogue
