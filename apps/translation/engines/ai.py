"""
Intelligences artificielles en ligne déjà configurées dans le module IA (ChatGPT, Claude, Gemini,
service compatible OpenAI), utilisées comme moteurs de traduction.

Réutilisation sans duplication : clés, fournisseurs et appels viennent de apps/ai (AIProviderCredential,
providers.get_provider). Les clés restent gérées dans IA → Fournisseurs.
Consentement (décision C5) : moteur indisponible si le profil IA actif est en mode « Désactivée » ou si
la case « Traduction » du profil est décochée.
Consignes : reference/consignes-ia.json (versionnées). Réponse JSON exigée et vérifiée : identifiants
manquants ou en trop → réponse rejetée ; texte autour du JSON → alerte « commentaire hors traduction ».
La création d'une tâche IA par appel (décision E1) et le plafond IA sont appliqués par la chaîne de
traitement (lot 4), pas ici.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from apps.ai.models import PROVIDERS, AIProviderCredential
from apps.ai.preferences import active_profile
from apps.ai.providers import ProviderError, get_provider

from .base import EngineResult, EngineStatus, TranslationEngine, engine_error

PROMPTS_FILE = Path(__file__).resolve().parent.parent / "reference" / "consignes-ia.json"

#: nature d'une ProviderError → (nature ConnectorError, catégorie du journal)
PROVIDER_KIND_MAP = {
    "auth": ("config", "cle_refusee"),
    "quota": ("unavailable", "quota_depasse"),
    "unavailable": ("unavailable", ""),
    "not_found": ("config", ""),
    "refused": ("config", ""),
    "redirect": ("technical", ""),
    "unparsable": ("unparsable", "reponse_vide"),
    "technical": ("technical", ""),
}

#: débuts de réponse qui signalent un commentaire au lieu d'une traduction seule
COMMENT_MARKERS = re.compile(r"(?i)^\s*(traduction\s*:|voici|note\s*:|remarque\s*:|translation\s*:)")


@lru_cache(maxsize=1)
def prompts():
    return json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))


def build_prompt(batch, source, target, *, glossary=None, variety="modern", context=None):
    p = prompts()
    labels = p["language_labels"]
    joined_sources = "\n".join(s.text for s in batch)
    terms = [(a, b) for a, b in (glossary or []) if a and a in joined_sources]
    instruction = p["instruction"].format(
        source_label=labels.get(source, source), target_label=labels.get(target, target),
        variety_note=p["variety_notes"].get(variety, ""),
        glossary_note=p["glossary_note"].format(terms=" ; ".join(f"{a} → {b}" for a, b in terms)) if terms else "",
        context_note=p["context_note"].format(context=" / ".join(context)) if context else "",
    )
    data = {"segments": [{"id": s.id, "text": s.text} for s in batch]}
    return p["system"], instruction + "\n\nSEGMENTS :\n" + json.dumps(data, ensure_ascii=False, indent=1), terms


def parse_response(text, expected_ids):
    """Retourne ({id: traduction}, alertes globales). Lève une erreur si la réponse ne convient pas."""
    stripped = (text or "").strip()
    match = re.search(r"\{.*\}", stripped, re.S)
    if not match:
        raise engine_error("La réponse de l'IA n'est pas au format JSON attendu.", kind="unparsable",
                           code="reponse_vide")
    alerts = []
    if stripped[:match.start()].strip() or stripped[match.end():].strip():
        alerts.append("commentaire hors traduction dans la réponse de l'IA (ignoré)")
    try:
        data = json.loads(match.group(0))
    except ValueError:
        raise engine_error("JSON invalide dans la réponse de l'IA.", kind="unparsable", code="reponse_vide") from None
    items = data.get("translations") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise engine_error("Réponse de l'IA sans liste « translations ».", kind="unparsable", code="reponse_vide")
    found = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise engine_error("Élément de traduction mal formé dans la réponse de l'IA.", kind="unparsable",
                               code="reponse_vide")
        found[str(item.get("id"))] = item["text"]
    expected = set(expected_ids)
    missing, extra = expected - set(found), set(found) - expected
    if missing or extra or len(items) != len(expected):
        detail = []
        if missing:
            detail.append(f"{len(missing)} segment(s) manquant(s)")
        if extra:
            detail.append(f"{len(extra)} identifiant(s) inconnu(s)")
        if len(items) != len(found):
            detail.append("identifiants en double")
        raise engine_error("Réponse de l'IA rejetée : " + ", ".join(detail or ["nombre d'éléments incorrect"]) + ".",
                           kind="unparsable", code="reponse_vide")
    return found, alerts


class AIEngine(TranslationEngine):
    code = "ai"
    label = "Intelligence artificielle en ligne"
    online = True
    needs_key = True
    glossary_support = "prompt"
    max_items = 20
    max_chars = 6000

    @property
    def display_name(self):
        provider = dict(PROVIDERS).get(self.ai_provider, self.ai_provider or "fournisseur à choisir")
        return f"{provider} — {self.ai_model or 'modèle à choisir'}"

    def credential(self):
        return AIProviderCredential.objects.filter(user=self.user, provider=self.ai_provider).first()

    def consent_problem(self):
        profile = active_profile(self.user)
        if profile.mode == "disabled":
            return "L'IA est désactivée dans vos préférences IA."
        if not profile.translation_enabled:
            return "La traduction par IA n'est pas autorisée dans vos préférences IA (case « Traduction »)."
        return ""

    def status(self):
        if not self.ai_provider:
            return EngineStatus(False, "Fournisseur à choisir")
        problem = self.consent_problem()
        if problem:
            return EngineStatus(False, "Non autorisé", problem, level="warning")
        cred = self.credential()
        if cred is None or not cred.is_configured:
            return EngineStatus(False, "Clé absente", "Clé à saisir dans IA → Fournisseurs.", level="warning")
        if not self.ai_model:
            return EngineStatus(False, "Modèle à choisir")
        if cred.status == "error":
            return EngineStatus(True, "Dernier test en échec", cred.last_error, level="warning")
        if cred.status == "ok":
            return EngineStatus(True, "Clé testée avec succès", level="success")
        return EngineStatus(True, "Clé non testée", "Testez-la dans IA → Fournisseurs.")

    def test(self):
        st = self.status()
        return f"{self.display_name} : {st.label}. {st.detail}".strip()

    def _provider(self):
        problem = self.consent_problem()
        if problem:
            raise engine_error(problem, kind="config")
        cred = self.credential()
        if cred is None or not cred.is_configured:
            raise engine_error("Aucune clé n'est enregistrée pour ce fournisseur (IA → Fournisseurs).",
                               kind="config", code="cle_refusee")
        if not self.ai_model:
            raise engine_error("Aucun modèle n'est choisi pour ce moteur IA.", kind="config")
        try:
            return get_provider(cred)
        except ProviderError as exc:
            raise self._convert(exc) from None

    def _convert(self, exc):
        kind, code = PROVIDER_KIND_MAP.get(getattr(exc, "kind", "") or "technical", ("technical", ""))
        return engine_error(str(exc), kind=kind, code=code, http_status=getattr(exc, "http_status", None),
                            diagnostic={"engine": "ai", "provider": self.ai_provider, "model": self.ai_model,
                                        "http_status": getattr(exc, "http_status", None)})

    def translate(self, segments, source, target, *, glossary=None, variety="modern", context=None):
        self.check_pair(source, target)
        provider = self._provider()
        translations, alerts = {}, {}
        tokens_in = tokens_out = chars = 0
        model = self.ai_model
        for batch in self.batches(segments):
            system, prompt, _terms = build_prompt(batch, source, target, glossary=glossary, variety=variety,
                                                  context=context)
            size = sum(len(s.text) for s in batch)
            try:
                completion = provider.complete(system, prompt, self.ai_model, max_tokens=min(8000, 500 + size * 4))
            except ProviderError as exc:
                raise self._convert(exc) from None
            found, global_alerts = parse_response(completion.text, [s.id for s in batch])
            for seg in batch:
                text = found[seg.id]
                seg_alerts = list(global_alerts)
                if COMMENT_MARKERS.match(text) and not COMMENT_MARKERS.match(seg.text):
                    seg_alerts.append("la traduction semble commencer par un commentaire")
                translations[seg.id] = text
                if seg_alerts:
                    alerts[seg.id] = seg_alerts
            tokens_in += completion.tokens_in
            tokens_out += completion.tokens_out
            chars += size
            model = completion.model or model
        return EngineResult(translations, chars_sent=chars, model=model,
                            engine_version=f"consignes {prompts()['version']}", tokens_in=tokens_in,
                            tokens_out=tokens_out, alerts=alerts)
