"""
Clients des fournisseurs d'IA (appels REST directs, sans SDK propriétaire).

Ajouter un fournisseur = ajouter une classe Provider et l'enregistrer dans PROVIDER_CLASSES.
Les clés ne sont déchiffrées qu'ici, au moment de l'appel, et ne sont jamais journalisées.
"""
from dataclasses import dataclass

import httpx

from apps.core.logging import redact

from .crypto import decrypt_secret
from .urlsafety import UnsafeProviderURL, check_provider_url  # noqa: F401


class ProviderError(Exception):
    """Erreur présentable à l'utilisateur. Message inchangé depuis la 1.2.0.

    1.3.0 (ajout compatible) : `http_status` et `kind` permettent au module de traduction de classer
    l'erreur sans analyser le texte du message. `kind` : unavailable, auth, quota, not_found, redirect,
    technical, unparsable, refused ; vide si non précisé.
    """

    def __init__(self, message="", *, http_status=None, kind=""):
        super().__init__(message)
        self.http_status = http_status
        self.kind = kind


@dataclass
class Completion:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""


#: 2.0.0 : nombre maximal de pages lues pour la liste des modèles (garde-fou contre une boucle sans fin).
MAX_MODEL_PAGES = 20
#: 2.0.0 : nombre maximal de modèles conservés avec la clé (300 en 1.3.0).
MAX_STORED_MODELS = 2000


class BaseProvider:
    key = ""
    label = ""
    default_base_url = ""
    #: transport injectable pour les tests
    transport = None

    #: seuls les services « compatibles » acceptent une adresse personnalisée
    custom_base_url = False

    def __init__(self, credential):
        self.credential = credential
        if self.custom_base_url:
            if not credential.base_url:
                raise ProviderError("Aucune adresse n'est définie pour ce service.")
            self.base_url = credential.base_url.rstrip("/")
        else:
            self.base_url = self.default_base_url.rstrip("/")

    def _api_key(self):
        if not self.credential.is_configured:
            raise ProviderError("Aucune clé API valide n'est enregistrée pour ce fournisseur.")
        return decrypt_secret(self.credential.encrypted_key)

    def _client(self, timeout=60):
        kwargs = {"timeout": timeout}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.Client(**kwargs)

    def _request(self, method, url, **kwargs):
        if self.custom_base_url:
            try:  # contrôle répété à chaque appel (la résolution DNS peut changer)
                check_provider_url(self.base_url)
            except UnsafeProviderURL as exc:
                raise ProviderError(f"Adresse du service refusée : {exc}", kind="refused") from None
        kwargs.setdefault("follow_redirects", False)
        try:
            with self._client(kwargs.pop("timeout", 90)) as client:
                response = client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Fournisseur injoignable ({exc.__class__.__name__}).", kind="unavailable") from None
        status = response.status_code
        if status in (401, 403):
            raise ProviderError("Clé API refusée par le fournisseur (authentification).", http_status=status, kind="auth")
        if status == 429:
            raise ProviderError("Quota ou limite de débit atteint chez le fournisseur.", http_status=status, kind="quota")
        if status == 404:
            raise ProviderError("Modèle ou service introuvable chez le fournisseur (vérifiez le nom du modèle).",
                                http_status=status, kind="not_found")
        if 300 <= status < 400:
            raise ProviderError("Redirection refusée par sécurité.", http_status=status, kind="redirect")
        if status >= 400:
            # Le corps de la réponse n'est jamais renvoyé à l'utilisateur (fuite d'information possible).
            detail = _provider_error_message(response) if not self.custom_base_url else ""
            raise ProviderError(f"Erreur du fournisseur (HTTP {status}){detail}.", http_status=status,
                                kind="unavailable" if status >= 500 else "technical")
        try:
            return response.json()
        except ValueError:
            raise ProviderError("Réponse illisible du fournisseur.", http_status=status, kind="unparsable") from None

    def list_models(self):
        raise NotImplementedError

    def complete(self, system, prompt, model, max_tokens=2000):
        raise NotImplementedError


def _provider_error_message(response):
    """Message d'erreur structuré des API officielles uniquement (champ « message »), tronqué et masqué."""
    try:
        data = response.json()
    except ValueError:
        return ""
    err = data.get("error") if isinstance(data, dict) else None
    message = err.get("message") if isinstance(err, dict) else (data.get("message") if isinstance(data, dict) else None)
    return f" : {redact(str(message))[:160]}" if message else ""


class OpenAIProvider(BaseProvider):
    key = "openai"
    label = "OpenAI"
    default_base_url = "https://api.openai.com/v1"

    def _headers(self):
        return {"Authorization": f"Bearer {self._api_key()}"}

    def list_models(self):
        data = self._request("GET", f"{self.base_url}/models", headers=self._headers(), timeout=20)
        return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))

    def complete(self, system, prompt, model, max_tokens=2000):
        body = {"model": model, "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": prompt}]}
        data = self._request("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            raise ProviderError("Réponse OpenAI sans contenu.", kind="unparsable") from None
        usage = data.get("usage") or {}
        return Completion(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), data.get("model", model))


class OpenAICompatibleProvider(OpenAIProvider):
    key = "openai_compatible"
    label = "Compatible OpenAI"
    default_base_url = ""
    custom_base_url = True


class AnthropicProvider(BaseProvider):
    key = "anthropic"
    label = "Anthropic (Claude)"
    default_base_url = "https://api.anthropic.com/v1"

    def _headers(self):
        return {"x-api-key": self._api_key(), "anthropic-version": "2023-06-01"}

    def list_models(self):
        """Liste complète : l'API renvoie 20 modèles par page par défaut (2.0.0 : toutes les pages sont lues)."""
        ids, params = [], {"limit": 1000}
        for _ in range(MAX_MODEL_PAGES):
            data = self._request("GET", f"{self.base_url}/models", headers=self._headers(), params=params, timeout=20)
            ids += [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            if not data.get("has_more") or not data.get("last_id"):
                break
            params = {"limit": 1000, "after_id": data["last_id"]}
        return sorted(set(ids))

    def complete(self, system, prompt, model, max_tokens=2000):
        body = {"model": model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": prompt}]}
        data = self._request("POST", f"{self.base_url}/messages", headers=self._headers(), json=body)
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        usage = data.get("usage") or {}
        return Completion(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0), data.get("model", model))


class GeminiProvider(BaseProvider):
    key = "gemini"
    label = "Google (Gemini)"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _headers(self):
        return {"x-goog-api-key": self._api_key()}

    def list_models(self):
        """Modèles de texte (generateContent) ; 50 par page par défaut (2.0.0 : toutes les pages sont lues)."""
        names, params = [], {"pageSize": 1000}
        for _ in range(MAX_MODEL_PAGES):
            data = self._request("GET", f"{self.base_url}/models", headers=self._headers(), params=params, timeout=20)
            names += [m.get("name", "").removeprefix("models/") for m in data.get("models", [])
                      if "generateContent" in (m.get("supportedGenerationMethods") or [])]
            if not data.get("nextPageToken"):
                break
            params = {"pageSize": 1000, "pageToken": data["nextPageToken"]}
        return sorted(set(n for n in names if n))

    def complete(self, system, prompt, model, max_tokens=2000):
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens}}
        data = self._request("POST", f"{self.base_url}/models/{model}:generateContent", headers=self._headers(),
                             json=body)
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            raise ProviderError("Réponse Gemini sans contenu (filtrage ou erreur).", kind="unparsable") from None
        usage = data.get("usageMetadata") or {}
        return Completion("".join(p.get("text", "") for p in parts), usage.get("promptTokenCount", 0),
                          usage.get("candidatesTokenCount", 0), model)


PROVIDER_CLASSES = {cls.key: cls for cls in (OpenAIProvider, AnthropicProvider, GeminiProvider,
                                             OpenAICompatibleProvider)}


def get_provider(credential):
    cls = PROVIDER_CLASSES.get(credential.provider)
    if cls is None:
        raise ProviderError("Fournisseur non pris en charge.")
    return cls(credential)
