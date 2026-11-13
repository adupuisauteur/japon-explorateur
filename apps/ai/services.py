"""
Cycle de vie d'une tâche IA : préparation → présentation des données envoyées →
confirmation explicite → exécution → résultats étiquetés « IA » et soumis à validation.

Aucune fonction de ce module n'est appelée par un import, une synchronisation, une
mise à jour, une ouverture de dossier ou une connexion (§11.4).
"""
import json
import re
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.catalog.models import EditorialContent, Record, RecordLink

from .models import AIProviderCredential, AITask
from .preferences import active_profile
from .providers import ProviderError, get_provider

PROMPT_VERSION = "1.0"

SYSTEM = (
    "Tu es un assistant documentaire spécialisé dans les sources japonaises anciennes, médiévales et "
    "féodales. Tu travailles pour un chercheur francophone. Règles impératives : ne jamais inventer de "
    "donnée bibliographique, de date, d'URL ou de lecture ; distinguer ce qui figure dans la notice de ce "
    "qui est une hypothèse ; signaler explicitement toute incertitude ; conserver les graphies originales. "
    "Réponds uniquement par un objet JSON valide conforme au format demandé, sans texte autour."
)

FUNCTION_SPECS = {
    "translation": {
        "categories": ["titre original", "lecture", "auteur", "description originale (解題)"],
        "instruction": (
            "Traduis en français les titres et descriptions japonais des notices ci-dessous. Conserve les noms "
            "propres en rōmaji Hepburn avec macrons. Format : {\"records\": [{\"record_id\": \"…\", "
            "\"translated_title\": \"…\", \"description_translation\": \"…\" ou null, \"uncertainty\": \"…\"}]}"
        ),
    },
    "summary": {
        "categories": ["titre", "auteur", "dates", "type", "institution", "description originale"],
        "instruction": (
            "Rédige pour chaque notice un résumé documentaire en français (3 à 5 phrases) fondé uniquement sur "
            "les champs fournis. Indique les champs effectivement utilisés et les limites. Format : {\"records\": "
            "[{\"record_id\": \"…\", \"summary\": \"…\", \"fields_used\": [\"…\"], \"limits\": \"…\"}]}"
        ),
    },
    "classification": {
        "categories": ["titre", "auteur", "dates", "type", "sujets", "description originale"],
        "instruction": (
            "Propose pour chaque notice une classification historique (propositions, pas des faits) : période, "
            "catégories, genres, personnes, lieux, clans, thèmes, avec un niveau de confiance. Format : "
            "{\"records\": [{\"record_id\": \"…\", \"period\": \"heian|kamakura|nanbokucho|muromachi|sengoku|"
            "azuchi_momoyama|edo|meiji|\", \"genres\": [], \"persons\": [], \"places\": [], \"clans\": [], "
            "\"themes\": [], \"confidence\": \"faible|moyenne|élevée\", \"rationale\": \"…\"}]}"
        ),
    },
    "duplicates": {
        "categories": ["titre", "lecture", "auteur", "dates", "institution", "cote", "catalogue"],
        "instruction": (
            "Repère parmi ces notices celles qui décrivent probablement le même ouvrage, la même œuvre ou le même "
            "exemplaire. Ne propose que des rapprochements argumentés. Format : {\"pairs\": [{\"a\": \"record_id\", "
            "\"b\": \"record_id\", \"relation\": \"possible_duplicate|same_work|same_copy\", \"score\": 0.0-1.0, "
            "\"rationale\": \"…\"}]}"
        ),
    },
    "query_extension": {
        "categories": ["texte de la requête"],
        "instruction": (
            "Propose des variantes de recherche pour cette requête : graphies (kyūjitai/shinjitai), lectures, "
            "rōmaji, noms alternatifs attestés, termes liés. Indique pour chacune si elle est attestée ou "
            "hypothétique. Format : {\"variants\": [{\"value\": \"…\", \"kind\": \"…\", \"status\": "
            "\"attestée|hypothétique\", \"rationale\": \"…\"}]}"
        ),
    },
    "extraction": {
        "categories": ["titre", "auteur", "description originale", "sujets"],
        "instruction": (
            "Extrais des notices les personnes, lieux, dates, institutions et titres mentionnés, en citant le champ "
            "d'origine. Format : {\"records\": [{\"record_id\": \"…\", \"entities\": [{\"type\": \"personne|lieu|"
            "date|institution|titre\", \"value\": \"…\", \"field\": \"…\"}]}]}"
        ),
    },
    "rag": {
        "categories": ["question", "notices locales sélectionnées (titre, auteur, dates, description)"],
        "instruction": (
            "Réponds à la question uniquement à partir des notices fournies. Cite les record_id utilisés. Si les "
            "notices ne permettent pas de répondre, dis-le. Format : {\"answer\": \"…\", \"sources\": "
            "[\"record_id\"], \"limits\": \"…\"}"
        ),
    },
    "comparison": {
        "categories": ["titre", "auteur", "dates", "description originale", "institution"],
        "instruction": (
            "Compare ces notices : points communs, différences, hypothèses de relation, en citant précisément les "
            "champs. Format : {\"comparison\": \"…\", \"points\": [{\"record_ids\": [], \"field\": \"…\", "
            "\"observation\": \"…\"}]}"
        ),
    },
}

RECORD_FIELDS_SENT = ["record_id", "original_title", "reading", "creator_original", "composition_date_text",
                      "copy_date_text", "document_type_original", "holding_institution_text", "shelfmark",
                      "subjects_original", "description_original"]


class AIUnavailable(Exception):
    """Préparation impossible : explication présentée à l'utilisateur, aucun basculement silencieux."""

    def __init__(self, message, *, reason="", alternatives=None):
        super().__init__(message)
        self.reason = reason
        self.alternatives = alternatives or []


def _record_payload(record):
    data = {f: getattr(record, f) for f in RECORD_FIELDS_SENT}
    data["catalogue"] = record.catalogue.name
    return {k: v for k, v in data.items() if v not in (None, "")}


def configured_providers(user):
    return [c for c in AIProviderCredential.objects.filter(user=user) if c.is_configured]


def monthly_spend(user):
    start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = AITask.objects.filter(user=user, created_at__gte=start).aggregate(s=Sum("cost_estimate"))["s"]
    return total or Decimal("0")


def prepare_task(user, function, *, records=(), parameters=None, provider=None, model=None, scope_label=""):
    """Crée une tâche en brouillon. Ne transmet RIEN au fournisseur."""
    profile = active_profile(user)
    if profile.mode == "disabled":
        raise AIUnavailable("L'IA est désactivée dans vos préférences.", reason="disabled")
    if function not in FUNCTION_SPECS:
        raise AIUnavailable("Fonction IA inconnue.")
    if not profile.function_enabled(function):
        raise AIUnavailable("Cette fonction IA n'est pas activée dans votre profil actif.", reason="function_disabled")

    chosen_provider, chosen_model = (provider, model) if provider else profile.provider_for(function)
    alternatives = [c.provider for c in configured_providers(user)]
    if not chosen_provider:
        raise AIUnavailable("Aucun fournisseur d'IA n'est choisi par défaut.", reason="no_provider",
                            alternatives=alternatives)
    credential = AIProviderCredential.objects.filter(user=user, provider=chosen_provider).first()
    if credential is None or not credential.is_configured:
        raise AIUnavailable("Le fournisseur choisi n'est pas configuré (clé API absente ou révoquée).",
                            reason="not_configured", alternatives=[a for a in alternatives if a != chosen_provider])
    if credential.status == "error":
        raise AIUnavailable(f"Le dernier test de connexion a échoué : {credential.last_error}",
                            reason="unavailable", alternatives=[a for a in alternatives if a != chosen_provider])
    if not chosen_model:
        raise AIUnavailable("Aucun modèle n'est défini pour ce fournisseur.", reason="no_model",
                            alternatives=alternatives)
    if credential.available_models and chosen_model not in credential.available_models:
        raise AIUnavailable(f"Le modèle « {chosen_model} » n'apparaît pas dans la liste du fournisseur.",
                            reason="incompatible", alternatives=alternatives)

    spec = FUNCTION_SPECS[function]
    parameters = parameters or {}
    payload = {"parameters": parameters}
    records = list(records)
    if records:
        payload["records"] = [_record_payload(r) for r in records]
    task = AITask.objects.create(user=user, function=function, provider=chosen_provider, model=chosen_model,
                                 parameters=parameters, data_categories=spec["categories"],
                                 prompt_version=PROMPT_VERSION, instruction=spec["instruction"],
                                 input_payload=payload, scope_label=scope_label or f"{len(records)} notice(s)")
    if records:
        task.records.set(records)
    return task


PURGED_PAYLOAD = {"note": "contenu non conservé selon les préférences de confidentialité"}


def purge_payload_if_needed(task, *, force=False, save=True):
    """Efface le contenu transmis (ou prévu) quand l'utilisateur ne souhaite pas le conserver."""
    if force or not active_profile(task.user).store_inputs:
        task.input_payload = PURGED_PAYLOAD
        if save:
            task.save(update_fields=["input_payload"])


def confirm_and_dispatch(task, user):
    """Confirmation explicite de l'utilisateur, puis exécution (asynchrone si Celery est actif)."""
    if task.user_id != user.pk or task.status != "draft":
        raise AIUnavailable("Cette tâche ne peut plus être lancée.")
    profile = active_profile(user)
    if profile.mode == "disabled" or not profile.function_enabled(task.function):
        task.status = "blocked"
        task.error = "IA ou fonction désactivée entre la préparation et la confirmation."
        task.save(update_fields=["status", "error"])
        purge_payload_if_needed(task)
        raise AIUnavailable(task.error)
    if profile.monthly_budget is not None and monthly_spend(user) >= profile.monthly_budget:
        task.status = "blocked"
        task.error = "Plafond mensuel estimé atteint : traitement non lancé."
        task.save(update_fields=["status", "error"])
        purge_payload_if_needed(task)
        raise AIUnavailable(task.error, reason="budget")
    task.status = "confirmed"
    task.confirmed_at = timezone.now()
    task.save(update_fields=["status", "confirmed_at"])
    from .tasks import run_ai_task

    run_ai_task.delay(task.pk)
    return task


def _parse_json(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ProviderError("La réponse de l'IA n'est pas au format JSON attendu.")
    try:
        return json.loads(m.group(0))
    except ValueError as exc:
        raise ProviderError("JSON invalide dans la réponse de l'IA.") from exc


def execute(task):
    """Appelle le fournisseur et enregistre les productions, toujours étiquetées IA et non validées."""
    if task.status != "confirmed":
        return task
    task.status = "running"
    task.save(update_fields=["status"])
    try:
        credential = AIProviderCredential.objects.get(user=task.user, provider=task.provider)
        provider = get_provider(credential)
        prompt = task.instruction + "\n\nDONNÉES :\n" + json.dumps(task.input_payload, ensure_ascii=False, indent=1)
        completion = provider.complete(SYSTEM, prompt, task.model, max_tokens=4000)
        task.output_text = completion.text
        task.tokens_in, task.tokens_out = completion.tokens_in, completion.tokens_out
        from .models import AIModelPrice

        task.cost_estimate = AIModelPrice.estimate(task.provider, task.model, completion.tokens_in, completion.tokens_out)
        task.output = _parse_json(completion.text)
        _store_outputs(task)
        task.status = "done"
    except (ProviderError, AIProviderCredential.DoesNotExist, Exception) as exc:  # noqa: B014
        task.status = "failed"
        task.error = str(exc)[:2000]
    task.finished_at = timezone.now()
    purge_payload_if_needed(task, save=False)
    task.save()
    return task


def purge_stale_drafts(hours=24):
    """Brouillons jamais confirmés : annulés et vidés de leur contenu (rien n'a été envoyé)."""
    from datetime import timedelta

    n = 0
    for task in AITask.objects.filter(status="draft", created_at__lt=timezone.now() - timedelta(hours=hours)):
        task.status = "cancelled"
        task.input_payload = PURGED_PAYLOAD
        task.save(update_fields=["status", "input_payload"])
        n += 1
    return n


def _store_outputs(task):
    records = {r.record_id: r for r in task.records.all()}
    out = task.output or {}
    if task.function in ("translation", "summary", "classification", "extraction"):
        for item in out.get("records") or []:
            record = records.get(str(item.get("record_id")))
            if record is None:
                continue
            if task.function == "translation":
                for field, src in (("translated_title", "original_title"),
                                   ("description_translation", "description_original")):
                    if item.get(field):
                        EditorialContent.objects.create(
                            record=record, kind="translation", target_field=src, source_text=getattr(record, src),
                            content=item[field], data={"uncertainty": item.get("uncertainty", "")}, origin="ai",
                            ai_task=task, author=task.user)
            elif task.function == "summary" and item.get("summary"):
                EditorialContent.objects.create(record=record, kind="summary", content=item["summary"],
                                                data={k: item.get(k) for k in ("fields_used", "limits")},
                                                origin="ai", ai_task=task, author=task.user)
            elif task.function == "classification":
                EditorialContent.objects.create(record=record, kind="classification",
                                                content=item.get("rationale", ""), data=item, origin="ai",
                                                ai_task=task, author=task.user)
            elif task.function == "extraction":
                EditorialContent.objects.create(record=record, kind="extraction",
                                                content=f"{len(item.get('entities') or [])} entité(s) proposée(s)",
                                                data=item, origin="ai", ai_task=task, author=task.user)
    elif task.function == "duplicates":
        for pair in out.get("pairs") or []:
            a, b = records.get(str(pair.get("a"))), records.get(str(pair.get("b")))
            if not a or not b or a == b:
                continue
            a, b = sorted([a, b], key=lambda r: r.pk)
            relation = pair.get("relation") if pair.get("relation") in ("possible_duplicate", "same_work",
                                                                         "same_copy") else "possible_duplicate"
            RecordLink.objects.get_or_create(
                record_a=a, record_b=b, link_type=relation,
                defaults={"origin": "ai", "status": "proposed", "score": pair.get("score"),
                          "rationale": pair.get("rationale", ""), "ai_task": task, "created_by": task.user})


def rag_context(question, limit=12):
    from apps.catalog.search import local_search
    from apps.connectors.base import SearchQuery

    return list(local_search(SearchQuery(text=question))[:limit]) or list(Record.objects.none())
