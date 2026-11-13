"""Logique des sessions de recherche : exécution par source, décisions, intégration, relance et comparaison."""
import hashlib
import json
import logging
import time
from datetime import timedelta

from django.db import transaction
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


def run_source(session, code, page_size=50):
    """Interroge une source pour la session. Une erreur n'affecte jamais les autres sources (§5.4)."""
    stats = {"status": "running"}
    started = time.monotonic()
    try:
        catalogue = Catalogue.objects.get(code=code)
        connector = get_connector(catalogue)
        response = connector.search(build_query(session, page_size=page_size))
        stored = _store_results(session, catalogue, response.results)
        stats = {"status": "warning" if response.warnings else "ok", "count": stored, "total": response.total,
                 "warnings": response.warnings, "ms": response.elapsed_ms or int((time.monotonic() - started) * 1000)}
        if code != "local":
            Catalogue.objects.filter(pk=catalogue.pk).update(last_success_at=timezone.now(), last_error="")
    except Catalogue.DoesNotExist:
        stats = {"status": "error", "error": "Source inconnue.", "count": 0}
    except ConnectorError as exc:
        stats = {"status": "error", "error": str(exc), "count": 0, "ms": int((time.monotonic() - started) * 1000)}
        Catalogue.objects.filter(code=code).update(last_error=str(exc)[:1000], last_attempt_at=timezone.now())
        if exc.temporary:
            Catalogue.objects.filter(code=code, status="available").update(status="degraded")
    except Exception as exc:  # garde-fou : une source défaillante ne bloque pas la session
        logger.exception("Erreur inattendue du connecteur %s", code)
        stats = {"status": "error", "error": f"Erreur inattendue : {exc.__class__.__name__}", "count": 0}
    _update_stats(session, code, stats)
    if session.mode == "auto" and stats["status"] in ("ok", "warning"):
        integrate(session, session.results.filter(catalogue__code=code, decision="pending"), session.owner,
                  origin="enregistrement automatique")
    return stats


@transaction.atomic
def _update_stats(session, code, stats):
    s = SearchSession.objects.select_for_update().get(pk=session.pk)
    s.source_stats[code] = stats
    if stats.get("status") == "error":
        s.errors = (s.errors or []) + [{"source": code, "error": stats.get("error"), "at": timezone.now().isoformat()}]
    if all(v.get("status") not in ("pending", "running") for v in s.source_stats.values()):
        s.finished_at = timezone.now()
        s.duration_ms = int((s.finished_at - s.started_at).total_seconds() * 1000)
        s.status = "partial" if any(v.get("status") == "error" for v in s.source_stats.values()) else "done"
        if s.previous_session_id:
            compare_with_previous(s)
    s.save()
    session.source_stats, session.status = s.source_stats, s.status


def _store_results(session, catalogue, results):
    from apps.library.models import LibraryEntry

    library_ids = set(LibraryEntry.objects.filter(user=session.owner).values_list("record_id", flat=True))
    existing_keys = {}
    for r in session.results.exclude(catalogue=catalogue).only("pk", "data"):
        existing_keys.setdefault(_title_key(r.data.get("original_title", "")), r.pk)
    rank = session.results.count()
    created = 0
    for res in results:
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
        rank += 1
        SearchResult.objects.update_or_create(
            session=session, catalogue=catalogue, source_id=res.source_id,
            defaults=dict(rank=rank, data=data, raw=res.raw, raw_format=res.raw_format, result_hash=h,
                          local_record=local, in_library=bool(local and local.pk in library_ids),
                          possible_duplicate_of_id=existing_keys.get(key) if len(key) >= 2 else None,
                          comparison=comparison, changed_fields=changed),
        )
        created += 1
    return created


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
    ok_now = {c for c, s in session.source_stats.items() if s.get("status") in ("ok", "warning")}
    ok_before = {c for c, s in previous.source_stats.items() if s.get("status") in ("ok", "warning")}
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
