"""
Google Cloud Translation — édition Basic (v2), avec une clé d'API simple (décision A2).

Vérifié sur la documentation officielle (13 novembre 2026) :
- POST https://translation.googleapis.com/language/translate/v2, clé d'API en paramètre « key » ;
- corps JSON : q (liste de textes), source, target, format (« text » pour du texte brut) ;
- réponse : data.translations[].translatedText, dans l'ordre des textes envoyés ;
- au plus 128 textes par requête ; Google recommande au plus 5 000 caractères par requête ;
- pas de glossaire dans l'édition Basic : seul le contrôle terminologique local s'applique.
À confirmer en test réel (non vérifiable ici) : la forme exacte des messages d'erreur. Le classement
ci-dessous se fonde sur le code HTTP et sur le champ « status » de l'erreur Google.
"""
from apps.ai.crypto import decrypt_secret

from ..http import TranslationHTTP
from .base import TEST_PHRASE, EngineResult, EngineStatus, TranslationEngine, engine_error

URL = "https://translation.googleapis.com/language/translate/v2"


class GoogleHTTP(TranslationHTTP):
    def classify(self, status, service_code, service_message, diagnostic):
        message = service_message.lower()
        if status == 400 and ("api key" in message or service_code == "INVALID_ARGUMENT" and "key" in message):
            return engine_error("Clé Google refusée (clé non valide).", kind="config", code="cle_refusee",
                                http_status=status, diagnostic=diagnostic)
        if status == 403:
            return engine_error("Accès refusé par Google : clé non autorisée, API Cloud Translation non activée "
                                "ou facturation absente pour le projet.", kind="config", code="cle_refusee",
                                http_status=status, diagnostic=diagnostic)
        if status == 429 or service_code == "RESOURCE_EXHAUSTED":
            return engine_error("Quota Google atteint : réessayez plus tard ou relevez le quota du projet.",
                                kind="unavailable", code="quota_depasse", http_status=status, diagnostic=diagnostic)
        return super().classify(status, service_code, service_message, diagnostic)


class GoogleBasicEngine(TranslationEngine):
    code = "google_basic"
    label = "Google Traduction (Basic)"
    online = True
    needs_key = True
    glossary_support = "none"
    max_items = 128
    max_chars = 5000

    def _key(self):
        if self.setting is None or not self.setting.has_key:
            raise engine_error("Aucune clé Google n'est enregistrée.", kind="config", code="cle_refusee")
        return decrypt_secret(self.setting.encrypted_key)

    def _http(self):
        from django.conf import settings

        return GoogleHTTP("Google Traduction", timeout=settings.TRANSLATION_TIMEOUTS.get("google_basic"),
                          transport=self.transport)

    def status(self):
        s = self.setting
        if s is None or not s.has_key:
            return EngineStatus(False, "Non configuré", "Clé Google Cloud à saisir.")
        if not s.enabled:
            return EngineStatus(False, "Désactivé", level="secondary")
        if s.status == "error":
            return EngineStatus(True, "Dernier test en échec", s.last_error, level="warning")
        if s.status == "ok":
            return EngineStatus(True, "Testé avec succès", level="success")
        return EngineStatus(True, "Configuré, non testé", level="secondary")

    def _call(self, texts, source, target):
        body = {"q": texts, "source": source, "target": target, "format": "text"}
        data = self._http().request("POST", URL, params={"key": self._key()}, json=body, n_texts=len(texts),
                                    n_chars=sum(len(t) for t in texts))
        items = (data.get("data") or {}).get("translations") if isinstance(data, dict) else None
        if not isinstance(items, list) or len(items) != len(texts):
            raise engine_error("Réponse Google incomplète : le nombre de traductions ne correspond pas.",
                               kind="unparsable", code="reponse_vide")
        out = []
        for item in items:
            text = item.get("translatedText") if isinstance(item, dict) else None
            if not isinstance(text, str):
                raise engine_error("Réponse Google mal formée.", kind="unparsable", code="reponse_vide")
            out.append(text)
        return out

    def test(self):
        """Traduit une phrase fictive fixe (une vingtaine de caractères décomptés)."""
        result = self._call([TEST_PHRASE], "ja", "fr")[0]
        return f"Connexion réussie. Phrase d'essai traduite : « {result} »"

    def translate(self, segments, source, target, *, glossary=None, variety="modern", context=None):
        self.check_pair(source, target)
        translations, chars = {}, 0
        for batch in self.batches(segments):
            for seg, text in zip(batch, self._call([s.text for s in batch], source, target)):
                translations[seg.id] = text
            chars += sum(len(s.text) for s in batch)
        return EngineResult(translations, chars_sent=chars, model="Google NMT (Basic v2)")
