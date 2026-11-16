"""
Résumés et fiches d'analyse par IA (2.0.0, lot 4 ; cahier § 7, décisions U8 à U10 du 15 novembre 2026).

- Trois types : court, détaillé, fiche d'analyse. Toujours rédigés dans la langue choisie (français par défaut).
- Texte lu : l'original japonais (notice ou document) ; une traduction n'est utilisée que pour un document dont
  l'utilisateur la choisit, avec la mention « traduction non validée » s'il y a lieu.
- Un résumé est une tâche de la file (lot 3) : `TranslationJob` de type « summary », un élément par notice ou
  par document. Un texte long est découpé en parties ; chaque partie est résumée (un appel), puis une synthèse
  produit le résumé final. Les résumés partiels sont gardés dans l'élément : une reprise ne renvoie rien.
- Avant chaque appel : fin de plage de nuit et plafonds (pause, jamais d'autre moteur).
- Chaque appel est tracé par une tâche IA (`AITask`) : coût, jetons, contenu transmis selon les préférences de
  confidentialité ; le budget mensuel IA en tient compte.
"""
import hashlib
import json
import math
import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai.models import (PROVIDERS, SUMMARY_KINDS, SUMMARY_LANGUAGES, AIModelPrice, AIProviderCredential, AITask,
                            Summary)
from apps.ai.preferences import active_profile
from apps.ai.providers import ProviderError, get_provider

from .models import TranslationJob, TranslationJobItem

PROMPT_VERSION = "résumés 1.0"
#: taille d'une partie (caractères). Un texte plus long est résumé par parties, puis synthétisé.
PART_CHARS = 6000
LOCAL_PART_CHARS = 3000  # IA locale : contexte plus court, calcul plus lent
#: jetons de sortie prévus par appel (estimation du coût)
OUT_TOKENS = {"court": 400, "detaille": 1200, "analyse": 1200, "part": 500}
LANG_NAMES = {"fr": "français", "en": "anglais", "ja": "japonais"}
KIND_INSTRUCTIONS = {
    "court": "un résumé court : 3 à 5 phrases",
    "detaille": "un résumé détaillé : 2 à 4 paragraphes structurés (contenu, contexte, intérêt pour la recherche)",
    "analyse": ("une fiche d'analyse : un résumé de 3 phrases, puis les thèmes, les personnes, les lieux et les dates "
                "cités dans le texte, chacun avec une courte précision"),
}
VARIETY_NOTES = {
    "classical": "Le texte est en japonais classique (bungo) : lis-le comme tel, sans le moderniser à tort.",
    "kanbun": "Le texte est en kanbun (chinois classique lu à la japonaise).",
}
SYSTEM = (
    "Tu es un assistant documentaire spécialisé dans les sources japonaises. Tu travailles pour un chercheur. "
    "Règles impératives : ne résume que ce que dit le texte fourni ; n'invente aucune donnée (nom, date, titre, lieu) ; "
    "signale ce qui est incertain ou illisible ; conserve les noms propres dans leur graphie originale suivie du rōmaji "
    "Hepburn avec macrons. Réponds uniquement par un objet JSON valide, sans texte autour."
)


class SummaryUnavailable(Exception):
    pass


# --------------------------------------------------------------------------- texte source


def record_text(record):
    """Texte original d'une notice : titre, auteur, dates, description (japonais), sujets."""
    parts = [("Titre", record.original_title), ("Lecture", record.reading), ("Auteur", record.creator_original),
             ("Date de composition", record.composition_date_text), ("Date de copie", record.copy_date_text),
             ("Type", record.document_type_original), ("Sujets", record.subjects_original),
             ("Description", record.description_original)]
    return "\n".join(f"{label} : {value}" for label, value in parts if value)


def document_text(document, source="original"):
    """(texte, source_kind) d'un document : original exact, ou traduction (validée de préférence)."""
    if source == "translation":
        from .models import TranslationVersion

        lines, validated_only = [], True
        for segment in document.segments.order_by("position"):
            version = (TranslationVersion.objects.filter(segment=segment, status="validated").order_by("-created_at")
                       .first())
            if version is None:
                version = segment.versions.order_by("-created_at").first()
                validated_only = validated_only and version is None
            if version is not None:
                lines.append(version.text)
        if lines:
            return "\n".join(lines), "document_validated" if validated_only else "document_unvalidated"
    return document.original_text, "document_original"


def item_source(item, job):
    if item.record_id:
        return record_text(item.record), "record_original"
    return document_text(item.document, job.options.get("source", "original"))


def split_parts(text, size):
    """Parties d'au plus `size` caractères, coupées de préférence en fin de ligne ou de phrase."""
    text = (text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    parts, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("\n", start, end), text.rfind("。", start, end))
            if cut > start + size // 2:
                end = cut + 1
        parts.append(text[start:end].strip())
        start = end
    return [p for p in parts if p]


def sha256(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- moteur


def is_local(provider):
    return provider == "ollama"


def part_size(provider):
    return LOCAL_PART_CHARS if is_local(provider) else PART_CHARS


def choice_for(user, *, ancient=False):
    """(fournisseur, modèle) des résumés : réglage « japonais ancien » s'il y a lieu, sinon résumés, sinon profil IA."""
    from .services import ensure_preference

    pref = ensure_preference(user)
    if ancient and pref.summary_ancient_provider and pref.summary_ancient_model:
        return pref.summary_ancient_provider, pref.summary_ancient_model
    if pref.summary_provider and pref.summary_model:
        return pref.summary_provider, pref.summary_model
    return active_profile(user).provider_for("summary")


def plan(text, provider):
    parts = len(split_parts(text, part_size(provider))) or 1
    return parts, parts + (1 if parts > 1 else 0)


def estimate(provider, model, texts, kind):
    """{"calls", "tokens_in", "tokens_out", "amount", "currency", "basis"} pour une liste de textes."""
    calls = tokens_in = tokens_out = 0
    for text in texts:
        parts, n = plan(text, provider)
        calls += n
        tokens_in += int(len(text) * 1.2) + 400 * n + (OUT_TOKENS["part"] * parts if parts > 1 else 0)
        tokens_out += OUT_TOKENS[kind] + (OUT_TOKENS["part"] * parts if parts > 1 else 0)
    if is_local(provider):
        return {"calls": calls, "tokens_in": tokens_in, "tokens_out": tokens_out, "amount": Decimal("0"),
                "currency": "USD", "basis": "IA locale : gratuite, rien ne quitte l'ordinateur"}
    amount = AIModelPrice.estimate(provider, model, tokens_in, tokens_out)
    basis = ("tarif saisi dans IA → Tarifs ; la facture du fournisseur fait foi" if amount is not None
             else "tarif de ce modèle non saisi (IA → Tarifs) : coût inconnu")
    return {"calls": calls, "tokens_in": tokens_in, "tokens_out": tokens_out, "amount": amount, "currency": "USD",
            "basis": basis}


# --------------------------------------------------------------------------- préparation


def _variety_for(item_or_target):
    from .variety import variety_of_document, variety_of_record

    if getattr(item_or_target, "record_id", None) or item_or_target.__class__.__name__ == "Record":
        record = item_or_target if item_or_target.__class__.__name__ == "Record" else item_or_target.record
        return variety_of_record(record)
    document = item_or_target if item_or_target.__class__.__name__ == "TranslationDocument" else item_or_target.document
    return variety_of_document(document)


def prepare(user, *, records=(), documents=(), kind=None, language=None, source="original", launch="immediate",
            project=None):
    """Tâche(s) de résumé en brouillon. Rien n'est envoyé. Retourne la liste des tâches (2 si textes anciens).

    U10 : si un fournisseur est choisi pour le japonais ancien, les textes anciens forment une tâche sœur avec ce
    fournisseur ; les deux sont présentées et confirmées ensemble.
    """
    from .services import ensure_preference
    from .variety import is_ancient

    pref = ensure_preference(user)
    kind = kind if kind in dict(SUMMARY_KINDS) else pref.summary_kind
    language = language if language in dict(SUMMARY_LANGUAGES) else pref.summary_language
    targets = [("record", r) for r in records] + [("document", d) for d in documents]
    if not targets:
        raise SummaryUnavailable("Rien à résumer : aucune notice ni aucun document sélectionné.")
    if len(targets) > 500:
        raise SummaryUnavailable("Au plus 500 notices ou documents par tâche de résumé.")
    split = bool(pref.summary_ancient_provider and pref.summary_ancient_model)
    groups = {"modern": [], "ancient": []}
    for target in targets:
        ancient = split and is_ancient(_variety_for(target[1]))
        groups["ancient" if ancient else "modern"].append(target)
    jobs = []
    for group, items in groups.items():
        if not items:
            continue
        provider, model = choice_for(user, ancient=(group == "ancient"))
        jobs.append(_create(user, items, provider=provider, model=model, kind=kind, language=language, source=source,
                            launch=launch, project=project, ancient=(group == "ancient")))
    if len(jobs) == 2:
        for a, b in ((jobs[0], jobs[1]), (jobs[1], jobs[0])):
            a.options = dict(a.options, sibling=b.pk)
            a.save(update_fields=["options"])
    return jobs


def _create(user, targets, *, provider, model, kind, language, source, launch, project, ancient):
    texts = []
    for what, obj in targets:
        if what == "record":
            texts.append(record_text(obj))
        else:
            texts.append(document_text(obj, source)[0])
    est = estimate(provider or "", model or "", texts, kind)
    first_project = project or next((obj.project for what, obj in targets if what == "document"), None)
    label = (f"{len(targets)} résumé(s) — {dict(SUMMARY_KINDS)[kind].lower()}, {dict(SUMMARY_LANGUAGES)[language].lower()}"
             + (" — japonais ancien" if ancient else ""))
    job = TranslationJob.objects.create(
        user=user, kind="summary", engine="ai", ai_provider=provider or "", ai_model=model or "", project=first_project,
        status="draft", launch=launch, total_items=len(targets), chars_estimated=sum(len(t) for t in texts),
        cost_estimate=est["amount"], scope_label=label[:300],
        options={"kind": kind, "language": language, "source": source, "calls": est["calls"], "ancient": ancient,
                 "basis": est["basis"][:300]})
    TranslationJobItem.objects.bulk_create([
        TranslationJobItem(job=job, position=i, record=obj if what == "record" else None,
                           document=obj if what == "document" else None, chars=len(texts[i]))
        for i, (what, obj) in enumerate(targets)])
    return job


def problems(job):
    """Ce qui empêche l'envoi d'une tâche de résumé (préparation, confirmation, reprise)."""
    out = []
    user = job.user
    profile = active_profile(user)
    local = is_local(job.ai_provider)
    if profile.mode == "disabled" and not local:
        out.append("L'IA est désactivée dans vos préférences (IA → Préférences).")
    elif not local and not profile.function_enabled("summary"):
        out.append("La fonction « Résumé documentaire » n'est pas activée dans votre profil IA (IA → Préférences).")
    if not job.ai_provider:
        out.append("Aucune IA n'est choisie pour les résumés (Traduction → Moteurs, section « Résumés »).")
        return out
    if local:
        from apps.ai.local import service_problem

        problem = service_problem()
        if problem:
            out.append(problem)
    else:
        cred = AIProviderCredential.objects.filter(user=user, provider=job.ai_provider).first()
        if cred is None or not cred.is_configured:
            out.append(f"Aucune clé enregistrée pour {dict(PROVIDERS).get(job.ai_provider, job.ai_provider)} "
                       "(IA → Fournisseurs).")
    if not job.ai_model:
        out.append("Aucun modèle n'est choisi pour les résumés.")
    if not local and profile.monthly_budget is not None:
        from apps.ai.services import monthly_spend

        spent = monthly_spend(user)
        planned = job.cost_estimate or Decimal("0")
        if spent + planned > profile.monthly_budget:
            out.append(f"Budget mensuel IA dépassé : {spent:.4f} USD consommés, {planned:.4f} USD prévus, plafond "
                       f"{profile.monthly_budget} USD.")
    return out


def siblings(job):
    pk = (job.options or {}).get("sibling")
    other = TranslationJob.objects.filter(pk=pk).first() if pk else None
    return [other] if other is not None else []


# --------------------------------------------------------------------------- exécution


def _build_prompt(job, text, *, step, index=0, count=1, partials=None, variety="modern"):
    kind, language = job.options.get("kind", "court"), job.options.get("language", "fr")
    lang = LANG_NAMES.get(language, "français")
    note = VARIETY_NOTES.get(variety, "")
    if job.options.get("source") == "translation" and step != "part":
        note += " Le texte fourni est une traduction automatique non vérifiée : signale-le dans les limites."
    if step == "part":
        instruction = (f"Voici la partie {index + 1} sur {count} d'un texte. Résume-la en {lang}, en 5 à 8 phrases, "
                       "en gardant les noms, les dates et les faits importants. Format : {\"summary\": \"…\"}")
        body = text
    else:
        fields = ('"summary": "…", "limits": "…"' if kind != "analyse" else
                  '"summary": "…", "themes": ["…"], "persons": [{"name": "…", "note": "…"}], "places": '
                  '[{"name": "…", "note": "…"}], "dates": [{"date": "…", "note": "…"}], "limits": "…"')
        instruction = (f"Rédige en {lang} {KIND_INSTRUCTIONS[kind]}. Dans « limits », indique ce qui est incertain, "
                       f"illisible ou absent du texte. Format : {{{fields}}}")
        if partials:
            body = "Résumés des parties successives du texte :\n" + "\n".join(
                f"[Partie {i + 1}] {p}" for i, p in enumerate(partials))
            instruction = "À partir des résumés des parties ci-dessous, " + instruction[0].lower() + instruction[1:]
        else:
            body = text
    prompt = f"{instruction}\n{note}\n\nTEXTE :\n{body}".strip()
    if job.ai_model.lower().startswith("qwen3"):
        prompt += "\n/no_think"  # Qwen3 : pas de raisonnement affiché, réponse directe
    return prompt


THINK = re.compile(r"<think>.*?</think>", re.S)


def parse(text):
    text = THINK.sub("", text or "").strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ProviderError("La réponse de l'IA n'est pas au format JSON attendu.", kind="unparsable")
    try:
        data = json.loads(match.group(0))
    except ValueError:
        raise ProviderError("JSON invalide dans la réponse de l'IA.", kind="unparsable") from None
    if not isinstance(data, dict) or not str(data.get("summary") or "").strip():
        raise ProviderError("La réponse de l'IA ne contient pas de résumé.", kind="unparsable")
    return data


def _call(job, prompt, label):
    """Un appel à l'IA, tracé par une tâche IA (coût, jetons). Retourne (données, completion)."""
    credential = _credential(job)
    provider = get_provider(credential)
    max_tokens = OUT_TOKENS.get(job.options.get("kind", "court"), 1200) * 2
    completion = provider.complete(SYSTEM, prompt, job.ai_model, max_tokens=max_tokens)
    cost = (Decimal("0") if is_local(job.ai_provider)
            else AIModelPrice.estimate(job.ai_provider, job.ai_model, completion.tokens_in, completion.tokens_out))
    task = AITask.objects.create(
        user=job.user, function="summary", provider=job.ai_provider, model=completion.model or job.ai_model,
        status="done", scope_label=label[:300], parameters={"job": job.pk, **{k: job.options.get(k) for k in
                                                                             ("kind", "language", "source")}},
        data_categories=["texte original de la notice ou du document"], prompt_version=PROMPT_VERSION,
        instruction=prompt[:2000], input_payload={"note": "texte transmis non conservé (résumés)"},
        output_text=completion.text[:20000], tokens_in=completion.tokens_in, tokens_out=completion.tokens_out,
        cost_estimate=cost, confirmed_at=job.confirmed_at, finished_at=timezone.now())
    return parse(completion.text), task


def _credential(job):
    if is_local(job.ai_provider):
        from apps.ai.local import credential_for

        return credential_for(job.user)
    return AIProviderCredential.objects.get(user=job.user, provider=job.ai_provider)


def process_next(job):
    """Un appel (une partie, ou la synthèse). Retourne True s'il reste du travail (la tâche se relance)."""
    from .queue import pause_reason_before_chunk
    from .services import _refresh_counters, _touch

    item = job.items.filter(status="pending").select_related("record", "document").order_by("position").first()
    if item is None:
        _refresh_counters(job)
        _touch(job, status="done", finished_at=timezone.now(), done_items=job.done_items,
               failed_items=job.failed_items, skipped_items=job.skipped_items, chars_sent=job.chars_sent)
        _after_done(job)
        return False
    text, source_kind = item_source(item, job)
    if not (text or "").strip():
        item.status, item.skip_reason = "skipped", "texte vide"
        item.save(update_fields=["status", "skip_reason"])
        return True
    parts = split_parts(text, part_size(job.ai_provider))
    partials = list((item.data or {}).get("partials") or [])
    step = "part" if len(parts) > 1 and len(partials) < len(parts) else "final"
    sent = parts[len(partials)] if step == "part" else ("" if len(parts) > 1 else text)
    planned = estimate(job.ai_provider, job.ai_model, [sent or "\n".join(partials)], job.options.get("kind", "court"))
    reason, message = pause_reason_before_chunk(job, 0 if job.engine == "ai" else len(sent), planned["amount"])
    if reason:
        _refresh_counters(job)
        _touch(job, status="paused", pause_reason=reason, error_summary=message[:2000])
        return False
    variety = _variety_for(item)
    prompt = _build_prompt(job, sent, step=step, index=len(partials), count=len(parts),
                           partials=partials if step == "final" and len(parts) > 1 else None, variety=variety)
    label = f"Résumé — {item.record.original_title if item.record_id else item.document.title}"
    item.attempts += 1
    try:
        data, task = _call(job, prompt, label)
    except ProviderError as exc:
        return _failure(job, item, exc)
    except Exception as exc:  # noqa: BLE001 — erreur affichée telle quelle, jamais masquée
        return _failure(job, item, ProviderError(f"{exc.__class__.__name__} : {exc}", kind="technical"))
    job.chars_sent += len(sent) if step == "part" or len(parts) == 1 else 0
    if step == "part":
        partials.append(str(data["summary"]).strip())
        item.data = dict(item.data or {}, partials=partials)
        item.ai_task = task
        item.save(update_fields=["data", "ai_task", "attempts", "updated_at"])
        _touch(job, chars_sent=job.chars_sent)
        return True
    summary = _store(job, item, data, task, source_kind=source_kind, text=text, calls=len(partials) + 1,
                     variety=variety)
    item.status, item.ai_task, item.data = "done", task, {"summary": summary.pk, "parts": len(parts)}
    item.save(update_fields=["status", "ai_task", "data", "attempts", "updated_at"])
    _refresh_counters(job)
    _touch(job, chars_sent=job.chars_sent, done_items=job.done_items, failed_items=job.failed_items)
    return True


def _failure(job, item, exc):
    from .services import _refresh_counters, _touch

    kind = getattr(exc, "kind", "")
    if kind in ("unavailable", "quota"):  # service injoignable ou limite : la tâche s'interrompt, reprenable
        item.save(update_fields=["attempts", "updated_at"])
        _refresh_counters(job)
        _touch(job, status="interrupted", error_summary=f"Interrompue : {exc}"[:2000])
        return False
    item.status, item.error_kind, item.error_message = "failed", kind or "technical", str(exc)[:500]
    item.save(update_fields=["status", "error_kind", "error_message", "attempts", "updated_at"])
    _refresh_counters(job)
    _touch(job, failed_items=job.failed_items)
    return True


@transaction.atomic
def _store(job, item, data, task, *, source_kind, text, calls, variety):
    """Nouveau résumé (nouvelle version s'il en existait un de même type, langue et cible)."""
    kind, language = job.options.get("kind", "court"), job.options.get("language", "fr")
    if item.record_id:
        target = {"record": item.record, "document": None}
        project = job.project
    else:
        target = {"record": item.document.record, "document": item.document}
        project = item.document.project
    previous = (Summary.objects.filter(document=target["document"], kind=kind, language=language,
                                       **({"record": target["record"]} if target["document"] is None else {}))
                .order_by("-created_at").first())
    extra = {k: data.get(k) for k in ("themes", "persons", "places", "dates", "limits") if data.get(k)}
    return Summary.objects.create(
        **target, project=project, kind=kind, language=language, source_kind=source_kind,
        source_sha256=sha256(text), variety=variety, content=str(data["summary"]).strip(), data=extra,
        provider=job.ai_provider, model=task.model or job.ai_model, calls=calls, job=job, ai_task=task,
        author=job.user, previous=previous)


def _after_done(job):
    """Lot 4b : rien ici ; les résumés enchaînés sont lancés par la tâche de traduction (services.chain)."""


def latest_for(*, record=None, document=None):
    """Derniers résumés (un par type et par langue) d'une notice ou d'un document."""
    qs = Summary.objects.filter(record=record) if record is not None else Summary.objects.filter(document=document)
    seen, out = set(), []
    for summary in qs.select_related("job", "document").order_by("-created_at"):
        key = (summary.kind, summary.language, summary.document_id)
        if key in seen:
            continue
        seen.add(key)
        summary.versions = 1 + len(summary.history())
        out.append(summary)
    return out


def engine_label(job):
    label = dict(PROVIDERS).get(job.ai_provider, job.ai_provider or "IA à choisir")
    return f"Résumé IA — {label}{' — ' + job.ai_model if job.ai_model else ''}"


def report_links(job):
    from django.urls import reverse

    links = []
    for item in job.items.filter(status="done").select_related("record", "document")[:20]:
        if item.record_id:
            links.append((item.record.original_title or item.record.record_id, item.record.get_absolute_url()))
        elif item.document_id:
            links.append((item.document.title, reverse("translation:document_workbench", args=[item.document_id])))
    return links


def now_allowed(job):
    """« Résumer maintenant » sans écran de confirmation : IA locale, ou coût connu sous le seuil choisi."""
    from .services import ensure_preference

    if job.status != "draft" or problems(job) or siblings(job):
        return False
    if is_local(job.ai_provider):
        return True
    if active_profile(job.user).mode == "confirm":
        return False
    threshold = ensure_preference(job.user).confirm_below
    return threshold is not None and job.cost_estimate is not None and job.cost_estimate <= threshold


def settings_ok():
    return bool(getattr(settings, "OLLAMA_URL", ""))


def page_context(user, *, record=None, document=None):
    """Contexte des écrans (fiche, atelier) : résumés, demande en cours, réglages, variété de langue."""
    from datetime import timedelta

    from .models import VARIETIES
    from .services import ensure_preference
    from .variety import detect, suggest_for_document

    pref = ensure_preference(user) if user.is_authenticated else None
    ctx = {"summaries": latest_for(record=record) if record is not None else latest_for(document=document),
           "can_summarize": bool(user.is_authenticated and user.can_edit), "summary_kinds": SUMMARY_KINDS,
           "summary_languages": SUMMARY_LANGUAGES, "summary_pref": pref, "varieties": VARIETIES}
    if ctx["can_summarize"]:
        provider, model = choice_for(user)
        ctx["summary_engine"] = (f"{dict(PROVIDERS).get(provider, provider)}{' — ' + model if model else ''}"
                                 if provider else "aucune IA choisie pour les résumés")
        jobs = TranslationJob.objects.filter(user=user, kind="summary", launch="now",
                                             created_at__gte=timezone.now() - timedelta(hours=1))
        jobs = jobs.filter(items__record=record) if record is not None else jobs.filter(items__document=document)
        ctx["summary_job"] = jobs.exclude(status__in=("draft", "cancelled")).order_by("-created_at").distinct().first()
    labels = dict(VARIETIES)
    if record is not None:
        annotation = getattr(record, "language_variety", None) if _has_variety(record) else None
        if getattr(record, "language", "") == "lzh":
            ctx["variety_info"] = {"variety": "kanbun", "label": labels["kanbun"], "origin": "user",
                                   "reasons": ["langue déclarée par la source : chinois classique"]}
        elif annotation is not None:
            ctx["variety_info"] = {"variety": annotation.variety, "label": labels.get(annotation.variety, ""),
                                   "origin": annotation.origin, "reasons": annotation.reasons}
        else:
            variety, reasons = detect("\n".join(v for v in (record.original_title, record.description_original) if v))
            ctx["variety_info"] = {"variety": variety, "label": labels.get(variety, ""), "origin": "detected",
                                   "reasons": reasons}
    if document is not None:
        suggestion = suggest_for_document(document)
        ctx["variety_suggestion"] = ({"variety": suggestion[0], "label": labels[suggestion[0]],
                                      "reasons": suggestion[1]} if suggestion else None)
    return ctx


def _has_variety(record):
    from .models import RecordVariety

    try:
        return record.language_variety is not None
    except RecordVariety.DoesNotExist:
        return False
