"""
DeepL API (offre gratuite ou payante), traduction de texte.

Vérifié sur la documentation officielle (13 novembre 2026) :
- adresse https://api.deepl.com (offre payante) ou https://api-free.deepl.com (offre gratuite) ;
- en-tête « Authorization: DeepL-Auth-Key <clé> » ;
- POST /v2/translate : jusqu'à 50 textes par requête, corps limité à 128 Kio ; réponses dans l'ordre ;
- GET /v2/usage : character_count et character_limit (1000000000000 = aucune limite configurée) ;
- HTTP 456 : quota épuisé (ne pas réessayer) ; 429 : trop de requêtes (réessayer) ; 403 : authentification.
L'offre (gratuite ou payante) est choisie par l'utilisateur ; elle n'est pas devinée à partir de la clé.
Glossaires DeepL : lot 7.
"""
from apps.ai.crypto import decrypt_secret

from ..http import TranslationHTTP
from .base import EngineResult, EngineStatus, TranslationEngine, engine_error

BASE_URLS = {"free": "https://api-free.deepl.com", "pro": "https://api.deepl.com"}
#: codes de langue DeepL (source / cible)
SOURCE_CODES = {"ja": "JA", "en": "EN"}
TARGET_CODES = {"fr": "FR"}
NO_LIMIT = 1_000_000_000_000


class DeepLHTTP(TranslationHTTP):
    def classify(self, status, service_code, service_message, diagnostic):
        if status == 456:
            return engine_error("Quota DeepL épuisé pour la période en cours (ou plafond de la clé atteint).",
                                kind="unavailable", code="quota_depasse", http_status=status, diagnostic=diagnostic)
        if status == 403:
            return engine_error("Clé DeepL refusée. Vérifiez la clé et l'offre choisie (gratuite ou payante).",
                                kind="config", code="cle_refusee", http_status=status, diagnostic=diagnostic)
        if status == 413:
            return engine_error("Texte trop long pour une requête DeepL.", kind="technical", http_status=status,
                                diagnostic=diagnostic)
        return super().classify(status, service_code, service_message, diagnostic)


class DeepLEngine(TranslationEngine):
    code = "deepl"
    label = "DeepL"
    online = True
    needs_key = True
    glossary_support = "native"
    max_items = 50
    max_chars = 30000  # bien en deçà de 128 Kio une fois encodé en UTF-8 et en JSON

    def _key(self):
        if self.setting is None or not self.setting.has_key:
            raise engine_error("Aucune clé DeepL n'est enregistrée.", kind="config", code="cle_refusee")
        if self.setting.plan not in BASE_URLS:
            raise engine_error("Choisissez l'offre DeepL (gratuite ou payante) : l'adresse du service en dépend.",
                               kind="config")
        return decrypt_secret(self.setting.encrypted_key)

    def _http(self):
        from django.conf import settings

        return DeepLHTTP("DeepL", timeout=settings.TRANSLATION_TIMEOUTS.get("deepl"), transport=self.transport)

    def _headers(self):
        return {"Authorization": f"DeepL-Auth-Key {self._key()}"}

    @property
    def base_url(self):
        if self.setting is None or self.setting.plan not in BASE_URLS:
            raise engine_error("Choisissez l'offre DeepL (gratuite ou payante) : l'adresse du service en dépend.",
                               kind="config")
        return BASE_URLS[self.setting.plan]

    def status(self):
        s = self.setting
        if s is None or not s.has_key:
            return EngineStatus(False, "Non configuré", "Clé DeepL à saisir.")
        if not s.enabled:
            return EngineStatus(False, "Désactivé", level="secondary")
        if s.status == "error":
            return EngineStatus(True, "Dernier test en échec", s.last_error, level="warning")
        if s.status == "ok":
            return EngineStatus(True, "Testé avec succès", level="success")
        return EngineStatus(True, "Configuré, non testé", level="secondary")

    def test(self):
        """Lit la consommation (/v2/usage) : aucun texte envoyé, aucun caractère décompté."""
        headers = self._headers()
        data = self._http().request("GET", f"{self.base_url}/v2/usage", headers=headers)
        if not isinstance(data, dict) or "character_count" not in data:
            raise engine_error("Réponse inattendue de DeepL (/v2/usage).", kind="unparsable", code="reponse_vide")
        count, limit = int(data.get("character_count") or 0), int(data.get("character_limit") or 0)
        self.setting.quota_info = {"character_count": count, "character_limit": limit}
        if limit and limit < NO_LIMIT:
            return f"Connexion réussie : {count:,} caractères utilisés sur {limit:,} pour la période.".replace(",", " ")
        return f"Connexion réussie : {count:,} caractères utilisés ; aucune limite configurée.".replace(",", " ")

    def translate(self, segments, source, target, *, glossary=None, variety="modern", context=None):
        self.check_pair(source, target)
        headers = self._headers()  # vérifie d'abord la clé et l'offre
        url = f"{self.base_url}/v2/translate"
        translations, chars = {}, 0
        for batch in self.batches(segments):
            body = {"text": [s.text for s in batch], "source_lang": SOURCE_CODES[source],
                    "target_lang": TARGET_CODES[target]}
            if glossary and isinstance(glossary, dict) and glossary.get("deepl_glossary_id"):
                body["glossary_id"] = glossary["deepl_glossary_id"]
            n = sum(len(s.text) for s in batch)
            data = self._http().request("POST", url, headers=headers, json=body, n_texts=len(batch), n_chars=n)
            items = data.get("translations") if isinstance(data, dict) else None
            if not isinstance(items, list) or len(items) != len(batch):
                raise engine_error("Réponse DeepL incomplète : le nombre de traductions ne correspond pas.",
                                   kind="unparsable", code="reponse_vide")
            for seg, item in zip(batch, items):
                text = item.get("text") if isinstance(item, dict) else None
                if not isinstance(text, str):
                    raise engine_error("Réponse DeepL mal formée.", kind="unparsable", code="reponse_vide")
                translations[seg.id] = text
            chars += n
        return EngineResult(translations, chars_sent=chars, model="DeepL API")
