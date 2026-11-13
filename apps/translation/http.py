"""
Client HTTP des moteurs de traduction.

Différences voulues avec apps/connectors/http.py (ConnectorHTTP) :
- requêtes POST comme GET, jamais de cache ;
- le diagnostic joint aux erreurs ne contient AUCUN extrait de texte, ni envoyé ni reçu : seulement
  l'adresse expurgée, le code HTTP, la durée, le nombre de textes et de caractères, le code d'erreur
  du service (règle de confidentialité du cahier des charges, § 13 et § 17) ;
- nouvelle tentative seulement pour 429 et 5xx (jamais pour un quota épuisé ni une requête invalide) ;
- en tests, tout appel réseau réel est refusé (TRANSLATION_BLOCK_NETWORK).
"""
import time
import uuid

import httpx
from django.conf import settings

from apps.core.logging import redact, redact_url

from .engines.base import engine_error


class NetworkBlocked(RuntimeError):
    """Appel réseau réel tenté pendant les tests : refusé."""


def _service_message(response):
    """Code et message d'erreur structurés du service (jamais le corps brut), tronqués et expurgés."""
    try:
        data = response.json()
    except ValueError:
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    err = data.get("error")
    if isinstance(err, dict):  # Google : {"error": {"code", "message", "status"}}
        return str(err.get("status") or err.get("code") or ""), redact(str(err.get("message") or ""))[:200]
    return str(data.get("code") or ""), redact(str(data.get("message") or ""))[:200]


class TranslationHTTP:
    def __init__(self, engine_label, *, timeout=None, transport=None, retries=2):
        self.engine_label = engine_label
        self.timeout = timeout or settings.TRANSLATION_DEFAULT_TIMEOUT
        self.transport = transport
        self.retries = retries

    def _client(self):
        if self.transport is None and settings.TRANSLATION_BLOCK_NETWORK:
            raise NetworkBlocked(f"Appel réseau réel refusé pendant les tests ({self.engine_label}).")
        kwargs = {"timeout": self.timeout, "follow_redirects": False,
                  "headers": {"User-Agent": settings.CONNECTOR_USER_AGENT}}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.Client(**kwargs)

    def request(self, method, url, *, headers=None, params=None, json=None, n_texts=0, n_chars=0):
        request_id = uuid.uuid4().hex[:12]
        started = time.monotonic()
        shown = redact_url(str(httpx.URL(url, params=params)) if params else url)

        def diag(**extra):
            d = {"request_id": request_id, "url": shown, "method": method, "engine": self.engine_label,
                 "elapsed_ms": int((time.monotonic() - started) * 1000), "timeout_s": self.timeout,
                 "texts": n_texts, "chars": n_chars}
            d.update(extra)
            return d

        attempt = 0
        while True:
            attempt += 1
            try:
                with self._client() as client:
                    response = client.request(method, url, headers=headers, params=params, json=json)
            except httpx.TimeoutException as exc:
                raise engine_error(f"{self.engine_label} n'a pas répondu dans le délai ({self.timeout:g} s).",
                                   kind="unavailable", code="delai_depasse",
                                   diagnostic=diag(attempts=attempt, exception=exc.__class__.__name__)) from None
            except httpx.HTTPError as exc:
                raise engine_error(f"{self.engine_label} est injoignable ({exc.__class__.__name__}).",
                                   kind="unavailable", diagnostic=diag(attempts=attempt,
                                                                       exception=exc.__class__.__name__)) from None
            status = response.status_code
            if (status == 429 or status >= 500) and attempt <= self.retries:
                time.sleep(min(0.5 * attempt, 2) if self.transport is None else 0)
                continue
            if status >= 300:
                service_code, service_message = _service_message(response)
                raise self.classify(status, service_code, service_message,
                                    diag(attempts=attempt, http_status=status, service_code=service_code,
                                         service_message=service_message))
            try:
                return response.json()
            except ValueError:
                raise engine_error(f"Réponse illisible de {self.engine_label}.", kind="unparsable", code="reponse_vide",
                                   http_status=status, diagnostic=diag(attempts=attempt, http_status=status)) from None

    def classify(self, status, service_code, service_message, diagnostic):
        """Classement générique ; chaque moteur peut le préciser (voir deepl.py, google_basic.py)."""
        label = self.engine_label
        if 300 <= status < 400:
            return engine_error(f"Redirection refusée par sécurité ({label}).", kind="technical", http_status=status,
                                diagnostic=diagnostic)
        if status in (401, 403):
            return engine_error(f"Clé refusée par {label} (authentification).", kind="config", code="cle_refusee",
                                http_status=status, diagnostic=diagnostic)
        if status == 429:
            return engine_error(f"{label} limite le nombre de requêtes : réessayez plus tard.", kind="unavailable",
                                code="quota_depasse", http_status=status, diagnostic=diagnostic)
        if status >= 500:
            return engine_error(f"{label} est momentanément indisponible (HTTP {status}).", kind="unavailable",
                                http_status=status, diagnostic=diagnostic)
        detail = f" : {service_message}" if service_message else ""
        return engine_error(f"Requête refusée par {label} (HTTP {status}){detail}.", kind="technical",
                            http_status=status, diagnostic=diagnostic)
