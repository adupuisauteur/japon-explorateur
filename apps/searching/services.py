"""Logique des sessions de recherche : exécution par source, décisions, intégration, relance et comparaison."""
import hashlib
import json
import logging
import time
from datetime import timedelta

from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.catalog.models import Catalogue, Record
from apps.catalog.services import _title_key, upsert_record
from apps.connectors.base import ConnectorError, SearchQuery
from apps.connectors.registry import get_connector
from apps.core.models import AppSettings

from .models import ResultDecision, SearchResult, SearchSession

logger = logging.getLogger(__name__)


def data_hash(data):
    payload = json.dumps({k: v for k, v in data.items() if k not in ("collected_at", "norm")}, sort_keys=True,
                         ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def build_query(session, page=1, page_size=20):
    f = session.fields or {}
    return SearchQuery(
        text=session.query, variants=list(session.variants or []), title=f.get("title", ""),
        creator=f.get("creator", ""), subject=f.get("subject", ""), place=f.get("place", ""),
        date_from=_int(f.get("date_from")), date_to=_int(f.get("date_to")), filters=session.filters or {},
        page=page, page_size=page_size,
    )


def create_session(user, *, query="", variants=None, variant_details=None, fields=None, filters=None,
                   sources=None, mode=None, saved_search=None, previous_session=None, title="",
                   target_collection=None):
    retention = AppSettings.get().temporary_session_days
    session = SearchSession.objects.create(
        owner=user, query=query.strip(), variants=variants or [], variant_details=variant_details or [],
        fields=fields or {}, filters=filters or {}, sources=sources or ["local"],
        mode=mode or user.effective_search_mode(), saved_search=saved_search, previous_session=previous_session,
        title=title, expires_at=timezone.now() + timedelta(days=retention), target_collection=target_collection,
        source_stats={code: {"status": "pending"} for code in (sources or ["local"])},
    )
    return session


#: États d'une source dans une session (§2.7). Seuls les trois derniers sont des échecs.
SUCCESS_STATUSES = ("ok", "empty", "warning")
FAILURE_STATUSES = ("unavailable", "error", "unparsable")


def _operation_label(session, catalogue_name):
    terms = " | ".join(t for t in [session.query] + list(session.variants or []) if t)[:150]
    return f"Recherche « {terms} » sur {catalogue_name}" if terms else f"Recherche avancée sur {catalogue_name}"


def run_source(session, code, page_size=50):
    """Interroge une source pour la session. Une erreur n'affecte jamais les autres sources (§5.4).

    Distingue (§2.7 du cahier 1.2.0) : résultats (ok), aucun résultat (empty), source
    indisponible (unavailable), erreur technique (error), réponse illisible (unparsable).
    Les échecs sont transmis au journal des dysfonctionnements ; l'absence de résultat, jamais.
    """
    from apps.connectors.http import last_exchange
    from apps.incidents import services as incidents

    stats = {"status": "running"}
    started = time.monotonic()
    last_exchange.set(None)
    catalogue = Catalogue.objects.filter(code=code).first()
    operation = _operation_label(session, catalogue.name if catalogue else code)
    query_context = {"query_terms": " | ".join(t for t in [session.query] + list(session.variants or []) if t)[:300],
                     "fields": {k: v for k, v in (session.fields or {}).items() if v}, "search_session": str(session.uid)}
    try:
        if catalogue is None:
            raise Catalogue.DoesNotExist
        connector = get_connector(catalogue)
        response = connector.search(build_query(session, page_size=page_size))
        stored, skipped = _store_results(session, catalogue, response.results, operation=operation)
        warnings = list(response.warnings)
        if skipped:
            warnings.append(f"{skipped} résultat(s) n'ont pas pu être convertis et ont été ignorés "
                            "(voir le journal des dysfonctionnements).")
        status = "warning" if warnings else ("ok" if stored else "empty")
        stats = {"status": status, "count": stored, "total": response.total, "warnings": warnings,
                 "ms": response.elapsed_ms or int((time.monotonic() - started) * 1000)}
        for w in response.warnings:
            incidents.record_incident(module="recherche", category="avertissement_source", severity="info",
                                      origin="source_distante", source_code=code, title=f"Avertissement — {code}",
                                      message=w, operation=operation, technical_code="warning",
                                      context=dict(last_exchange.get() or {}, **query_context))
        if code != "local":
            Catalogue.objects.filter(pk=catalogue.pk).update(last_success_at=timezone.now(), last_error="")
            incidents.note_source_recovered(code)
    except Catalogue.DoesNotExist:
        stats = {"status": "error", "error": "Source inconnue.", "count": 0}
    except ConnectorError as exc:
        status = {"unavailable": "unavailable", "unparsable": "unparsable"}.get(exc.kind, "error")
        incident = None
        if exc.kind != "query":  # une requête refusée pour critères vides n'est pas un dysfonctionnement
            incident = incidents.record_connector_error(exc, module="recherche", source_code=code,
                                                        operation=operation, extra=query_context)
        stats = {"status": status, "error": str(exc), "kind": exc.kind, "kind_label": exc.kind_label, "count": 0,
                 "ms": int((time.monotonic() - started) * 1000), "incident": incident.uid if incident else ""}
        Catalogue.objects.filter(code=code).update(last_error=str(exc)[:1000], last_attempt_at=timezone.now())
        if exc.temporary:
            Catalogue.objects.filter(code=code, status="available").update(status="degraded")
    except Exception as exc:  # garde-fou : une source défaillante ne bloque pas la session
        logger.exception("Erreur inattendue du connecteur %s", code)
        incident = incidents.record_exception(exc, module="recherche", operation=operation, source_code=code,
                                              extra=dict(last_exchange.get() or {}, **query_context))
        stats = {"status": "error", "error": f"Erreur inattendue : {exc.__class__.__name__}", "kind": "technical",
                 "kind_label": "Erreur technique", "count": 0, "incident": incident.uid if incident else ""}
    _update_stats(session, code, stats)
    if session.mode == "auto" and stats["status"] in ("ok", "warning"):
        integrate(session, session.results.filter(catalogue__code=code, decision="pending"), session.owner,
                  origin="enregistrement automatique")
    return stats


@transaction.atomic
def _update_stats(session, code, stats):
    s = SearchSession.objects.select_for_update().get(pk=session.pk)
    s.source_stats[code] = stats
    if stats.get("status") in FAILURE_STATUSES:
        s.errors = (s.errors or []) + [{"source": code, "error": stats.get("error"), "kind": stats.get("kind", ""),
                                        "incident": stats.get("incident", ""), "at": timezone.now().isoformat()}]
    if all(v.get("status") not in ("pending", "running") for v in s.source_stats.values()):
        s.finished_at = timezone.now()
        s.duration_ms = int((s.finished_at - s.started_at).total_seconds() * 1000)
        s.status = "partial" if any(v.get("status") in FAILURE_STATUSES for v in s.source_stats.values()) else "done"
        if s.previous_session_id:
            compare_with_previous(s)
    s.save()
    session.source_stats, session.status = s.source_stats, s.status


def _store_results(session, catalogue, results, operation=""):
    """Enregistre les résultats d'une source. Retourne (enregistrés, ignorés pour erreur de conversion)."""
    from apps.library.models import LibraryEntry

    library_ids = set(LibraryEntry.objects.filter(user=session.owner).values_list("record_id", flat=True))
    existing_keys = {}
    for r in session.results.exclude(catalogue=catalogue).only("pk", "data"):
        existing_keys.setdefault(_title_key(r.data.get("original_title", "")), r.pk)
    rank = session.results.count()
    created = skipped = 0
    for res in results:
        try:
            with transaction.atomic():
                created += _store_one(session, catalogue, res, library_ids, existing_keys, rank + created + 1)
        except DatabaseError as exc:
            from apps.incidents.services import record_database_error

            logger.exception("Erreur de base de données (résultat %s)", res.source_id)
            record_database_error(exc, module="base_de_donnees", operation=operation, source_code=catalogue.code)
            skipped += 1
        except Exception as exc:  # métadonnées mal formées : le résultat est ignoré, les autres sont conservés
            from apps.incidents.services import record_exception

            logger.warning("Résultat %s non converti : %s", res.source_id, exc)
            record_exception(exc, module="metadonnees", operation=operation, source_code=catalogue.code,
                             category="erreur_traitement", severity="error", origin="traitement",
                             extra={"source_id": str(res.source_id)[:120], "raw_format": res.raw_format,
                                    "fields": sorted(res.data)[:40] if isinstance(res.data, dict) else []})
            skipped += 1
    return created, skipped


def _store_one(session, catalogue, res, library_ids, existing_keys, rank):
    """Enregistre un résultat de source dans la session (même logique que la 1.1, isolée par résultat)."""
    if catalogue.code == "local":
        local = Record.objects.filter(record_id=res.source_id).select_related("catalogue").first()
    else:
        local = Record.objects.filter(catalogue=catalogue, source_id=res.source_id).first()
    data = dict(res.data)
    h = data_hash(data)
    data["norm"] = _normalized_view(catalogue, data, local)
    comparison = ""
    changed = []
    if local and catalogue.code != "local":
        from apps.catalog.services import compare_with_existing

        _, status, changed = compare_with_existing(catalogue, data, res.raw, res.raw_format)
        comparison = {"unchanged": "known", "modified": "modified"}.get(status, "")
    key = _title_key(data.get("original_title", ""))
    SearchResult.objects.update_or_create(
        session=session, catalogue=catalogue, source_id=res.source_id,
        defaults=dict(rank=rank, data=data, raw=res.raw, raw_format=res.raw_format, result_hash=h,
                      local_record=local, in_library=bool(local and local.pk in library_ids),
                      possible_duplicate_of_id=existing_keys.get(key) if len(key) >= 2 else None,
                      comparison=comparison, changed_fields=changed),
    )
    return 1


def _normalized_view(catalogue, data, local):
    """Vue normalisée d'un résultat (filtres, tri, affichage) ; la donnée source reste intacte."""
    if catalogue.code == "local" and local is not None:
        rec = local
    else:
        from apps.catalog.normalization import normalize_record
        from apps.catalog.services import build_unsaved_record

        rec = normalize_record(build_unsaved_record(catalogue, data))
    return {"period": rec.period, "document_type": rec.document_type, "material_type": rec.material_type,
            "digital_access": rec.digital_access, "title_romaji": rec.title_romaji,
            "composition_year_start": rec.composition_year_start, "composition_year_end": rec.composition_year_end,
            "copy_year_start": rec.copy_year_start, "copy_year_end": rec.copy_year_end,
            "period_label": rec.get_period_display() if rec.period else "",
            "document_type_label": rec.get_document_type_display() if rec.document_type else ""}


def run_all_sources(session):
    for code in list(session.sources):
        run_source(session, code)
    session.refresh_from_db()
    return session


# --------------------------------------------------------------------------- décisions


def set_decision(results, action, user, reason="", note=""):
    """action ∈ select, deselect, exclude, reinstate. Aucune n'efface une notice existante (§8.4)."""
    now = timezone.now()
    mapping = {"select": "selected", "deselect": "pending", "exclude": "excluded", "reinstate": "pending"}
    if action not in mapping:
        raise ValueError(action)
    count = 0
    for result in results:
        result.decision = mapping[action]
        result.decided_at = now
        if action == "exclude":
            result.exclusion_reason = reason
            result.exclusion_note = note[:300]
        elif action == "reinstate":
            result.exclusion_reason = ""
            result.exclusion_note = ""
        result.save(update_fields=["decision", "decided_at", "exclusion_reason", "exclusion_note"])
        ResultDecision.objects.create(result=result, action=action, reason=reason, note=note[:300], user=user)
        count += 1
    return count


@transaction.atomic
def integrate(session, results, user, *, collection=None, section=None, origin="recherche"):
    """Intègre des résultats en bibliothèque (et éventuellement dans un dossier).

    Les résultats exclus sont ignorés. Une notice existante est mise à jour avec
    historisation (aucun écrasement silencieux) ; jamais supprimée.
    """
    from apps.library.models import CollectionRecord, LibraryEntry

    stats = {"created": 0, "updated": 0, "unchanged": 0, "added_to_library": 0, "skipped_excluded": 0,
             "added_to_collection": 0, "errors": []}
    for result in results:
        if result.decision == "excluded":
            stats["skipped_excluded"] += 1
            continue
        if result.comparison == "unavailable":
            continue
        try:
            if result.catalogue.code == "local":
                record = result.local_record or Record.objects.get(record_id=result.source_id)
                status = "unchanged"
            else:
                record, status = upsert_record(result.catalogue, result.data, raw=result.raw,
                                               raw_format=result.raw_format, origin=origin, user=user,
                                               collected_at=result.collected_at,
                                               note=f"Session de recherche {session.uid}")
            stats[status if status != "created" else "created"] = stats.get(status, 0) + 1
        except (ValueError, Record.DoesNotExist) as exc:
            stats["errors"].append(f"{result.title} : {exc}")
            continue
        entry, created = LibraryEntry.objects.get_or_create(user=user, record=record,
                                                            defaults={"source_session": session})
        stats["added_to_library"] += int(created)
        if collection is not None:
            _, c_created = CollectionRecord.objects.get_or_create(collection=collection, record=record,
                                                                  defaults={"section": section, "added_by": user})
            stats["added_to_collection"] += int(c_created)
        result.integrated_record = record
        result.integrated_at = timezone.now()
        result.local_record = record
        result.in_library = True
        if result.decision == "pending":
            result.decision = "selected"
        result.save(update_fields=["integrated_record", "integrated_at", "local_record", "in_library", "decision"])
        ResultDecision.objects.create(result=result, action="integrate", user=user,
                                      note=(f"dossier {collection.pk}" if collection else "bibliothèque"))
    if not session.is_saved and session.mode != "manual":
        session.is_saved = True
        session.expires_at = None
        session.save(update_fields=["is_saved", "expires_at"])
    return stats


# --------------------------------------------------------------------------- relance et comparaison


def replay(saved_search, user):
    params = saved_search.params
    last = saved_search.sessions.order_by("-started_at").first()
    session = create_session(user, query=params.get("query", ""), variants=params.get("variants"),
                             fields=params.get("fields"), filters=params.get("filters"),
                             sources=params.get("sources"), mode=params.get("mode", "selective"),
                             saved_search=saved_search, previous_session=last,
                             title=f"{saved_search.name} — relance du {timezone.localtime():%d/%m/%Y}")
    saved_search.last_run_at = timezone.now()
    saved_search.save(update_fields=["last_run_at"])
    return session


def compare_with_previous(session):
    """Classe les résultats : nouveaux, déjà connus, modifiés, indisponibles, non comparables (§8.6)."""
    previous = session.previous_session
    if previous is None:
        return
    prev = {(r.catalogue_id, r.source_id): r for r in previous.results.exclude(comparison="unavailable")}
    ok_now = {c for c, s in session.source_stats.items() if s.get("status") in SUCCESS_STATUSES}
    ok_before = {c for c, s in previous.source_stats.items() if s.get("status") in SUCCESS_STATUSES}
    seen = set()
    for result in session.results.select_related("catalogue"):
        key = (result.catalogue_id, result.source_id)
        seen.add(key)
        if not result.source_id or result.catalogue.code not in ok_before:
            result.comparison = "not_comparable"
        elif key not in prev:
            result.comparison = "new" if not result.local_record_id else (result.comparison or "known")
        elif prev[key].result_hash == result.result_hash:
            result.comparison = "known"
        else:
            result.comparison = "modified"
            result.changed_fields = sorted(k for k in set(result.data) | set(prev[key].data)
                                           if result.data.get(k) != prev[key].data.get(k))
        result.save(update_fields=["comparison", "changed_fields"])
    rank = session.results.count()
    for key, old in prev.items():
        if key in seen or old.catalogue.code not in ok_now:
            continue
        rank += 1
        SearchResult.objects.create(session=session, catalogue=old.catalogue, source_id=old.source_id, rank=rank,
                                    data=old.data, raw={}, result_hash=old.result_hash, comparison="unavailable",
                                    local_record=old.local_record, in_library=old.in_library)


def purge_expired():
    """Supprime les sessions temporaires expirées (jamais les notices intégrées)."""
    qs = SearchSession.objects.filter(is_saved=False, expires_at__lt=timezone.now(), saved_search__isnull=True)
    count = qs.count()
    qs.delete()
    return count
