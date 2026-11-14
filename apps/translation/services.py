"""
Chaîne de traitement commune (plan 1.3.0, lot 4) : toute traduction est une TÂCHE, même un seul champ.

  préparation (rien n'est envoyé)  →  confirmation explicite  →  exécution par paquets (Celery, file
  « traduction »)  →  enregistrement (versions de segments, ou contenus éditoriaux pour les notices)

Règles appliquées :
- rien n'est envoyé à un service avant confirmation ; seconde confirmation au-delà du seuil (B3) et,
  pour les IA, selon la préférence IA « confirmation supplémentaire pour les lots » ;
- projet confidentiel : moteurs en ligne refusés côté serveur (D1) ;
- plafond mensuel du moteur ; pour les IA, plafond IA en plus (le plus strict des deux, C4) ;
- consentement IA (C5) vérifié par le moteur IA ;
- une tâche IA (apps.ai.AITask) par appel IA, réussi ou non (E1) ;
- aucune bascule automatique : en cas d'échec, le deuxième moteur est seulement PROPOSÉ ;
- un paquet en échec n'arrête pas la tâche (sauf clé refusée, configuration ou quota épuisé) ; une réponse
  illisible pour un paquet est reprise segment par segment ;
- reprise sans renvoi : seuls les éléments « en attente » sont traités ;
- jamais de texte dans le journal (voir journal.py).
"""
import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.ai.models import PROVIDERS as AI_PROVIDERS
from apps.incidents.services import record_incident, short_traceback

from . import memory as tm
from .checks import check_translation
from .glossary import bundle_for as glossary_bundle_for
from .engines.base import Segment, TranslationEngineError
from .engines.registry import get_engine
from .journal import record_translation_error
from .models import (EngineSetting, TranslationJob, TranslationJobItem, TranslationPreference, TranslationSegment,
                     TranslationVersion)
from .pricing import estimate

#: champs de notice traduisibles (décision C1) → libellé
RECORD_FIELDS = {"original_title": "Titre", "description_original": "Description",
                 "subjects_original": "Sujets", "place_original": "Lieu"}
#: états d'une tâche pendant lesquels des caractères ont pu être envoyés (consommation du mois)
SPENDING_STATUSES = ("confirmed", "running", "interrupted", "done", "failed", "cancelled")
#: erreurs qui arrêtent toute la tâche (inutile d'insister) : configuration, clé, quota
STOP_KINDS = ("config",)
STOP_CODES = ("cle_refusee", "quota_depasse")


class TranslationUnavailable(Exception):
    """Préparation ou confirmation impossible : explication présentable, rien n'a été envoyé."""

    def __init__(self, message, *, reason=""):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class EngineChoice:
    code: str
    ai_provider: str = ""
    ai_model: str = ""

    def engine(self, user):
        return get_engine(self.code, user, ai_provider=self.ai_provider, ai_model=self.ai_model)

    @classmethod
    def of(cls, obj, prefix):
        code = getattr(obj, f"{prefix}_engine", "")
        if not code:
            return None
        return cls(code, getattr(obj, f"{prefix}_ai_provider", ""), getattr(obj, f"{prefix}_ai_model", ""))

    @classmethod
    def of_job(cls, job):
        return cls(job.engine, job.ai_provider, job.ai_model)


def ensure_preference(user):
    """Préférences de traduction de l'utilisateur, créées au besoin.

    Reprise UNIQUE (lot 5) : si la 1.2.0 traduisait par IA pour cet utilisateur (case « Traduction » cochée et
    fournisseur + modèle définis, propres à la traduction ou par défaut) et qu'aucun moteur n'est encore choisi,
    cette IA devient le moteur par défaut. Les préférences IA ne sont pas modifiées.
    """
    from apps.ai.models import AIPreferenceProfile

    pref, _ = TranslationPreference.objects.get_or_create(user=user)
    if not pref.migrated_from_ai:
        profile = AIPreferenceProfile.objects.filter(user=user, is_active=True).first()
        if profile is not None and not pref.default_engine and profile.mode != "disabled" and profile.translation_enabled:
            provider, model = profile.provider_for("translation")
            if provider and model:
                pref.default_engine, pref.default_ai_provider, pref.default_ai_model = "ai", provider, model
        pref.migrated_from_ai = True
        pref.save()
    return pref


def resolve_choice(user, *, project=None, which="default"):
    """Moteur du projet s'il en a un, sinon celui des préférences (Traduction → Moteurs)."""
    if project is not None:
        choice = EngineChoice.of(project, which)
        if choice:
            return choice
    return EngineChoice.of(ensure_preference(user), which)


def month_start():
    return timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def monthly_chars(user, engine_code):
    total = (TranslationJob.objects.filter(user=user, engine=engine_code, status__in=SPENDING_STATUSES,
                                           created_at__gte=month_start()).aggregate(s=Sum("chars_sent"))["s"])
    return total or 0


def _variety_of_segment(segment):
    return segment.variety or segment.document.variety


def _variety_of_record(record):
    return "kanbun" if getattr(record, "language", "") == "lzh" else "modern"


# --------------------------------------------------------------------------- préparation


def prepare_segments_job(user, segments, *, project, choice=None):
    specs = [{"segment": s, "text": s.source_text} for s in segments]
    return _prepare(user, "segments", specs, project=project, choice=choice,
                    scope_label=f"{len(specs)} segment(s) — {project.title}")


def prepare_records_job(user, records, fields=("original_title", "description_original"), *, choice=None):
    specs = []
    for record in records:
        for field in fields:
            if field not in RECORD_FIELDS:
                continue
            text = (getattr(record, field, "") or "").strip()
            if text:
                specs.append({"record": record, "field": field, "text": text})
    return _prepare(user, "records", specs, project=None, choice=choice,
                    scope_label=f"{len(records)} notice(s), {len(specs)} champ(s)")


def _prepare(user, kind, specs, *, project, choice, scope_label):
    choice = choice or resolve_choice(user, project=project)
    if choice is None:
        raise TranslationUnavailable("Aucun moteur par défaut : choisissez-en un dans Traduction → Moteurs.",
                                     reason="no_engine")
    engine = choice.engine(user)
    if project is not None and project.confidential and engine.online:
        raise TranslationUnavailable("Projet confidentiel : les moteurs en ligne sont refusés. Utilisez un moteur "
                                     "local (Argos).", reason="confidential")
    status = engine.status()
    if not status.usable:
        raise TranslationUnavailable(f"{engine.display_name} : {status.label}. {status.detail}".strip(),
                                     reason="engine_unavailable")
    source, target = (project.source_lang, project.target_lang) if project is not None else ("ja", "fr")
    if not engine.supports(source, target):
        raise TranslationUnavailable(f"{engine.display_name} ne traduit pas de « {source} » vers « {target} ».",
                                     reason="unsupported_pair")
    if not specs:
        raise TranslationUnavailable("Rien à traduire : aucun texte non vide.", reason="empty")

    pending_chars, pending = 0, 0
    with transaction.atomic():
        job = TranslationJob.objects.create(user=user, project=project, kind=kind, scope_label=scope_label[:300],
                                            engine=choice.code, ai_provider=choice.ai_provider,
                                            ai_model=choice.ai_model, total_items=len(specs))
        items = []
        for position, spec in enumerate(specs, start=1):
            item = TranslationJobItem(job=job, position=position, segment=spec.get("segment"),
                                      record=spec.get("record"), record_field=spec.get("field", ""),
                                      chars=len(spec["text"]))
            segment = spec.get("segment")
            if segment is not None:
                if segment.versions.filter(status="validated").exists():
                    item.status, item.skip_reason = "skipped", "validated"
                elif tm.lookup(project.owner, segment.memory_key, exclude_segment=segment) is not None:
                    item.status, item.skip_reason = "skipped", "memory"
            if item.status == "pending":
                pending += 1
                pending_chars += item.chars
            items.append(item)
        TranslationJobItem.objects.bulk_create(items)
        cost = estimate(choice.code, pending_chars, ai_provider=choice.ai_provider, ai_model=choice.ai_model,
                        batches=max(1, math.ceil(pending / max(engine.max_items, 1))))
        job.chars_estimated = pending_chars
        job.cost_estimate, job.currency = cost["amount"], cost["currency"]
        threshold = ensure_preference(user).confirmation_threshold
        extra_ai = False
        if choice.code == "ai":
            from apps.ai.preferences import active_profile

            extra_ai = active_profile(user).batch_extra_confirmation and pending > 1
        job.requires_second_confirmation = pending_chars > threshold or extra_ai
        job.save()
    return job


def summary(job):
    """Ce que l'écran de confirmation affiche (rien n'a encore été envoyé)."""
    items = job.items.all()
    counts = {"pending": 0, "validated": 0, "memory": 0}
    for item in items:
        if item.status == "pending":
            counts["pending"] += 1
        elif item.skip_reason in counts:
            counts[item.skip_reason] += 1
    engine = EngineChoice.of_job(job).engine(job.user)
    cost = estimate(job.engine, job.chars_estimated, ai_provider=job.ai_provider, ai_model=job.ai_model,
                    batches=max(1, math.ceil(counts["pending"] / max(engine.max_items, 1))))
    setting = EngineSetting.objects.filter(user=job.user, engine=job.engine).first()
    return {"engine": engine, "status": engine.status(), "counts": counts, "cost": cost,
            "quota": (setting.quota_info if setting else {}) or {}, "problems": blocking_problems(job),
            "glossary": _bundle(job)}


def blocking_problems(job, *, resuming=False):
    """Raisons qui empêchent l'envoi, vérifiées à la préparation ET à la confirmation (côté serveur).

    En reprise, une tâche sans élément restant n'est pas bloquée : la reprise la clôt simplement.
    """
    problems = []
    user = job.user
    engine = EngineChoice.of_job(job).engine(user)
    status = engine.status()
    if not status.usable:
        problems.append(f"{engine.display_name} : {status.label}. {status.detail}".strip())
    if job.project_id and job.project.confidential and engine.online:
        problems.append("Projet confidentiel : moteurs en ligne refusés.")
    setting = EngineSetting.objects.filter(user=user, engine=job.engine).first()
    if setting and setting.monthly_char_cap is not None:
        used = monthly_chars(user, job.engine)
        if used + job.chars_estimated > setting.monthly_char_cap:
            problems.append(f"Plafond mensuel de {setting.get_engine_display()} atteint : {used} caractères "
                            f"utilisés, {job.chars_estimated} prévus, plafond {setting.monthly_char_cap}.")
    if job.engine == "ai":
        from apps.ai.preferences import active_profile
        from apps.ai.services import monthly_spend

        profile = active_profile(user)
        if profile.monthly_budget is not None:
            spent = monthly_spend(user)
            planned = job.cost_estimate or Decimal("0")
            if spent + planned > profile.monthly_budget:
                problems.append(f"Plafond mensuel IA atteint ou dépassé : {spent:.4f} USD consommés, {planned:.4f} "
                                f"USD prévus, plafond {profile.monthly_budget} USD (préférences IA).")
    if (not resuming and not job.items.filter(status="pending").exists()
            and not job.items.filter(skip_reason="memory").exists()):
        problems.append("Rien à envoyer : tous les éléments sont déjà validés.")
    return problems


# --------------------------------------------------------------------------- confirmation et suivi


def confirm(job, user, *, second_confirmation=False):
    if job.user_id != user.pk or job.status != "draft":
        raise TranslationUnavailable("Cette tâche ne peut plus être lancée.")
    problems = blocking_problems(job)
    if problems:
        job.status, job.error_summary = "blocked", " ".join(problems)[:2000]
        job.save(update_fields=["status", "error_summary"])
        raise TranslationUnavailable(" ".join(problems), reason="blocked")
    if job.requires_second_confirmation and not second_confirmation:
        raise TranslationUnavailable("Volume important : cochez la seconde confirmation pour lancer l'envoi.",
                                     reason="second_confirmation")
    job.status, job.confirmed_at = "confirmed", timezone.now()
    job.save(update_fields=["status", "confirmed_at"])
    dispatch(job)
    return job


def dispatch(job):
    from .tasks import run_translation_job

    run_translation_job.delay(job.pk)


def cancel(job, user):
    if job.user_id != user.pk or job.status not in ("draft", "confirmed", "running", "interrupted", "blocked"):
        raise TranslationUnavailable("Cette tâche ne peut pas être annulée.")
    job.status, job.finished_at = "cancelled", timezone.now()
    job.save(update_fields=["status", "finished_at"])


def is_stale(job):
    """Tâche lancée mais sans signe d'activité depuis TRANSLATION_STALE_MINUTES (worker arrêté, Docker éteint…)."""
    limit = timezone.now() - timedelta(minutes=settings.TRANSLATION_STALE_MINUTES)
    if job.status == "running":
        return (job.heartbeat_at or job.started_at or job.confirmed_at or job.created_at) < limit
    if job.status == "confirmed":
        return (job.confirmed_at or job.created_at) < limit
    return False


def resume(job, user):
    """Reprend une tâche interrompue ou en échec : seuls les éléments en attente sont envoyés."""
    if job.user_id != user.pk:
        raise TranslationUnavailable("Cette tâche ne vous appartient pas.")
    stale = is_stale(job)
    if not (stale or job.status in ("interrupted", "failed")):
        raise TranslationUnavailable("Cette tâche n'est pas interrompue.")
    if stale:
        record_incident(module="traduction", category="lot_interrompu", severity="warning", origin="application",
                        source_code=job.engine, title=f"Lot de traduction interrompu — {job.engine}",
                        message=f"Tâche n° {job.pk} sans signe d'activité ; reprise demandée.",
                        operation="Reprise d'une tâche de traduction", technical_code="stale_job",
                        context={"job": job.pk, "done": job.done_items, "total": job.total_items})
    problems = blocking_problems(job, resuming=True)
    if problems:
        raise TranslationUnavailable(" ".join(problems), reason="blocked")
    job.status, job.error_summary = "confirmed", ""
    job.save(update_fields=["status", "error_summary"])
    dispatch(job)
    return job


def retry_failed(job, user):
    if job.user_id != user.pk or job.status not in ("done", "failed", "interrupted"):
        raise TranslationUnavailable("Impossible de relancer les échecs de cette tâche.")
    n = job.items.filter(status="failed").update(status="pending", error_kind="", error_message="")
    if not n:
        raise TranslationUnavailable("Aucun élément en échec.")
    job.failed_items = 0
    job.status = "interrupted"
    job.save(update_fields=["failed_items", "status"])
    return resume(job, user)


def propose_second_engine(job, user):
    """Prépare (sans l'envoyer) une nouvelle tâche avec le DEUXIÈME moteur pour les éléments non traduits."""
    if job.user_id != user.pk:
        raise TranslationUnavailable("Cette tâche ne vous appartient pas.")
    second = resolve_choice(user, project=job.project, which="second")
    if second is None:
        raise TranslationUnavailable("Aucun deuxième moteur n'est choisi (Traduction → Moteurs).")
    if second == EngineChoice.of_job(job):
        raise TranslationUnavailable("Le deuxième moteur est celui de cette tâche.")
    items = job.items.filter(status__in=("failed", "pending")).select_related("segment", "record")
    if job.kind == "segments":
        return prepare_segments_job(user, [i.segment for i in items if i.segment_id], project=job.project,
                                    choice=second)
    records = {}
    for i in items:
        if i.record_id:
            records.setdefault(i.record, []).append(i.record_field)
    fields = sorted({f for fs in records.values() for f in fs})
    return prepare_records_job(user, list(records), fields, choice=second)


# --------------------------------------------------------------------------- exécution


def _touch(job, **fields):
    fields["heartbeat_at"] = timezone.now()
    for k, v in fields.items():
        setattr(job, k, v)
    job.save(update_fields=list(fields))


def _next_chunk(job, engine):
    """Prochain paquet d'éléments en attente, de même variété de langue, dans les limites du moteur."""
    pending = list(job.items.filter(status="pending").select_related("segment__document", "record")
                   .order_by("position")[:max(engine.max_items, 1)])
    if not pending:
        return [], "modern"
    variety = _variety(pending[0])
    chunk, size = [], 0
    for item in pending:
        if _variety(item) != variety:
            break
        if chunk and size + item.chars > engine.max_chars:
            break
        chunk.append(item)
        size += item.chars
    return chunk, variety


def _variety(item):
    if item.segment_id:
        return _variety_of_segment(item.segment)
    if item.record_id:
        return _variety_of_record(item.record)
    return "modern"


def _source_text(item):
    if item.segment_id:
        return item.segment.source_text
    if item.record_id:
        return (getattr(item.record, item.record_field, "") or "").strip()
    return ""


def _context(job, chunk):
    """Segments voisins (avant et après le paquet) pour les IA, si la préférence l'autorise."""
    if job.engine != "ai" or job.kind != "segments":
        return None
    pref = TranslationPreference.objects.filter(user=job.user).first()
    if not (pref and pref.send_neighbour_context):
        return None
    first, last = chunk[0].segment, chunk[-1].segment
    around = TranslationSegment.objects.filter(document=first.document,
                                               position__in=(first.position - 1, last.position + 1))
    return [s.source_text for s in around.order_by("position")] or None


def update_segment_state(segment):
    versions = list(segment.versions.all())
    if any(v.status == "validated" for v in versions):
        state = "validated"
    elif not versions:
        state = "untranslated"
    else:
        latest = max(versions, key=lambda v: v.created_at)
        state = "alert" if latest.alerts else "proposed"
    if segment.state != state:
        segment.state = state
        segment.save(update_fields=["state", "updated_at"])


def _apply_memory(job):
    """Éléments repris de la mémoire : une version PROPOSÉE est créée, sans appel au moteur."""
    for item in job.items.filter(status="skipped", skip_reason="memory", version__isnull=True).select_related("segment"):
        source = tm.lookup(job.project.owner, item.segment.memory_key, exclude_segment=item.segment)
        if source is None:
            item.status, item.skip_reason = "pending", ""
            item.save(update_fields=["status", "skip_reason", "updated_at"])
            continue
        version = TranslationVersion.objects.create(
            segment=item.segment, text=source.text, source_text=item.segment.source_text, engine=source.engine,
            ai_provider=source.ai_provider, model=source.model, engine_version=source.engine_version,
            simulated=source.simulated, variety=source.variety, origin=source.origin, author=job.user,
            alerts=[f"repris de la mémoire de traduction (version validée n° {source.pk})"])
        item.version = version
        item.save(update_fields=["version", "updated_at"])
        update_segment_state(item.segment)


def _record_ai_task(job, chunk, result=None, error=None):
    """Une tâche IA par appel IA (décision E1) : historique, consommation et plafond IA du module IA."""
    from apps.ai.models import AIModelPrice, AITask
    from apps.ai.preferences import active_profile
    from apps.ai.services import PURGED_PAYLOAD

    from .engines.ai import prompts

    profile = active_profile(job.user)
    payload = ({"segments": [{"id": str(i.pk), "text": _source_text(i)} for i in chunk]} if profile.store_inputs
               else PURGED_PAYLOAD)
    now = timezone.now()
    task = AITask.objects.create(
        user=job.user, function="translation", provider=job.ai_provider, model=job.ai_model,
        status="failed" if error is not None else "done", scope_label=f"Module de traduction — tâche n° {job.pk}",
        parameters={"translation_job": job.pk, "items": len(chunk)},
        data_categories=["segments de texte à traduire"], prompt_version=str(prompts().get("version", "")),
        instruction="Consignes du module de traduction (reference/consignes-ia.json)", input_payload=payload,
        tokens_in=result.tokens_in if result else 0, tokens_out=result.tokens_out if result else 0,
        cost_estimate=(AIModelPrice.estimate(job.ai_provider, result.model or job.ai_model, result.tokens_in,
                                             result.tokens_out) if result else None),
        error=str(error)[:2000] if error is not None else "", confirmed_at=job.confirmed_at, finished_at=now)
    records = [i.record for i in chunk if i.record_id]
    if records:
        task.records.set(records)
    return task


def _call_cost(job, result):
    if job.engine == "ai":
        from apps.ai.models import AIModelPrice

        return AIModelPrice.estimate(job.ai_provider, result.model or job.ai_model, result.tokens_in,
                                     result.tokens_out), "USD"
    if result.simulated:
        return None, ""
    cost = estimate(job.engine, result.chars_sent)
    return cost["amount"], cost["currency"]


def _glossary_alerts(bundle, source, text, simulated):
    """Contrôle terminologique local (tous moteurs) : signale, ne corrige jamais."""
    if not bundle or not bundle.found_in(source):
        return []
    alerts = list(bundle.notes)
    if not simulated:
        alerts += bundle.check(source, text)
    return alerts


def _store(job, chunk, result, ai_task, bundle=None):
    from apps.catalog.models import EditorialContent

    call_cost, currency = _call_cost(job, result)
    total_chars = sum(i.chars for i in chunk) or 1
    for item in chunk:
        text = result.translations[str(item.pk)]
        source = _source_text(item)
        alerts = (list(result.alerts.get(str(item.pk), [])) + check_translation(source, text, simulated=result.simulated)
                  + _glossary_alerts(bundle, source, text, result.simulated))
        share = (call_cost * Decimal(item.chars) / Decimal(total_chars)) if call_cost is not None else None
        variety = _variety(item)
        if item.segment_id:
            version = TranslationVersion.objects.create(
                segment=item.segment, text=text, source_text=source, engine=job.engine, ai_provider=job.ai_provider,
                model=result.model, engine_version=result.engine_version, simulated=result.simulated,
                variety=variety, origin="ai" if job.engine == "ai" else "machine", author=job.user,
                chars_sent=0 if result.simulated else item.chars, cost_estimate=share, currency=currency,
                alerts=alerts, glossaries=bundle.refs if bundle else [])
            item.version = version
            update_segment_state(item.segment)
        else:
            editorial = EditorialContent.objects.create(
                record=item.record, kind="translation", target_field=item.record_field, source_text=source,
                content=text, origin="ai" if job.engine == "ai" else "mt", ai_task=ai_task, author=job.user,
                data={"engine": job.engine, "ai_provider": job.ai_provider, "model": result.model,
                      "engine_version": result.engine_version, "simulated": result.simulated, "variety": variety,
                      "alerts": alerts, "chars": item.chars, "translation_job": job.pk,
                      "cost_estimate": str(share) if share is not None else None, "currency": currency})
            item.editorial = editorial
        item.status, item.ai_task, item.attempts = "done", ai_task, item.attempts + 1
        item.save(update_fields=["status", "version", "editorial", "ai_task", "attempts", "updated_at"])


def _fail(chunk, exc):
    for item in chunk:
        item.status = "failed"
        item.error_kind = getattr(exc, "code", "") or getattr(exc, "kind", "technical")
        item.error_message = str(exc)[:500]
        item.attempts += 1
        item.save(update_fields=["status", "error_kind", "error_message", "attempts", "updated_at"])


def _bundle(job):
    """Glossaires du projet pour cette tâche (lot 7) ; aucun pour les traductions de notices."""
    if job.kind != "segments" or not job.project_id:
        return None
    return glossary_bundle_for(job.project, job.user, job.engine)


def _translate(job, engine, chunk, variety, bundle=None):
    segments = [Segment(str(i.pk), _source_text(i)) for i in chunk]
    source, target = (job.project.source_lang, job.project.target_lang) if job.project_id else ("ja", "fr")
    return engine.translate(segments, source, target, glossary=bundle, variety=variety, context=_context(job, chunk))


def _run_chunk(job, engine, chunk, variety, bundle=None):
    """Traduit un paquet ; retourne False si la tâche doit s'arrêter (clé, configuration, quota)."""
    try:
        result = _translate(job, engine, chunk, variety, bundle)
    except TranslationEngineError as exc:
        if job.engine == "ai":
            _record_ai_task(job, chunk, error=exc)
        record_translation_error(exc, engine=job.engine, operation=f"Tâche de traduction n° {job.pk}")
        if exc.kind in STOP_KINDS or exc.code in STOP_CODES:
            job.error_summary = f"Arrêt : {exc}"[:2000]
            return False
        if len(chunk) > 1 and exc.kind in ("unparsable", "technical"):
            for item in chunk:  # isole l'élément fautif : les autres sont traduits
                if not _run_chunk(job, engine, [item], variety, bundle):
                    return False
            return True
        _fail(chunk, exc)
        return True
    ai_task = _record_ai_task(job, chunk, result=result) if job.engine == "ai" else None
    _store(job, chunk, result, ai_task, bundle)
    job.chars_sent += result.chars_sent
    return True


def _refresh_counters(job):
    statuses = list(job.items.values_list("status", flat=True))
    job.done_items = statuses.count("done")
    job.failed_items = statuses.count("failed")
    job.skipped_items = statuses.count("skipped")


def process_next_chunk(job_id):
    """Traite un paquet. Retourne True s'il reste des éléments à traiter (la tâche se relance)."""
    job = TranslationJob.objects.select_related("project", "user").filter(pk=job_id).first()
    if job is None or job.status not in ("confirmed", "running"):
        return False
    if job.status == "confirmed":
        _touch(job, status="running", started_at=job.started_at or timezone.now())
    if job.kind == "segments":
        _apply_memory(job)
    engine = EngineChoice.of_job(job).engine(job.user)
    chunk, variety = _next_chunk(job, engine)
    if not chunk:
        _refresh_counters(job)
        _touch(job, status="done", finished_at=timezone.now(), done_items=job.done_items,
               failed_items=job.failed_items, skipped_items=job.skipped_items, chars_sent=job.chars_sent)
        return False
    keep_going = _run_chunk(job, engine, chunk, variety, _bundle(job))
    _refresh_counters(job)
    job.refresh_from_db(fields=["status"])  # annulation demandée pendant le paquet ?
    if job.status == "cancelled":
        _touch(job, done_items=job.done_items, failed_items=job.failed_items, skipped_items=job.skipped_items,
               chars_sent=job.chars_sent)
        return False
    if not keep_going:
        _touch(job, status="failed", finished_at=timezone.now(), error_summary=job.error_summary,
               done_items=job.done_items, failed_items=job.failed_items, skipped_items=job.skipped_items,
               chars_sent=job.chars_sent)
        return False
    _touch(job, done_items=job.done_items, failed_items=job.failed_items, skipped_items=job.skipped_items,
           chars_sent=job.chars_sent)
    return True  # le paquet suivant (ou la clôture) est traité par un nouvel appel


def run_job_safely(job_id):
    """Exécute un paquet ; une erreur imprévue est journalisée et la tâche marquée en échec (jamais masquée)."""
    try:
        return process_next_chunk(job_id)
    except Exception as exc:  # noqa: BLE001
        # Message de l'exception NON journalisé (il pourrait contenir du texte) : type et pile d'appels seulement.
        record_incident(module="traduction", category="erreur_application", severity="error", origin="application",
                        title=f"{exc.__class__.__name__} pendant : tâche de traduction n° {job_id}",
                        message="Erreur inattendue pendant une tâche de traduction (voir la pile d'appels).",
                        operation=f"Tâche de traduction n° {job_id}", technical_code=exc.__class__.__name__,
                        context={"exception": exc.__class__.__name__, "traceback": short_traceback(exc)})
        TranslationJob.objects.filter(pk=job_id).update(status="failed", finished_at=timezone.now(),
                                                        error_summary=f"Erreur inattendue : {exc.__class__.__name__}")
        return False


def engine_label(job):
    if job.engine == "ai":
        return f"{dict(AI_PROVIDERS).get(job.ai_provider, job.ai_provider)} — {job.ai_model}"
    return job.get_engine_display()
