"""Client HTTP commun : identification, délais, limite de débit, cache, reprise sur erreur temporaire.

Depuis la 1.2.0, chaque échange reçoit un identifiant de requête local et
alimente un « contexte de diagnostic » (adresse expurgée, code HTTP, durée,
nombre de tentatives) que le journal des dysfonctionnements récupère en cas
d'échec. Aucun identifiant n'est transmis à la source distante.
"""
import contextvars
import hashlib
import json
import logging
import threading
import time
import uuid

import httpx
from django.conf import settings
from django.core.cache import cache

from apps.core.logging import redact, redact_url

from .base import ConnectorError, ResponseFormatError

logger = logging.getLogger(__name__)

_last_request = {}
_lock = threading.Lock()

#: Dernier échange HTTP de l'opération en cours (lu par le journal des dysfonctionnements).
last_exchange = contextvars.ContextVar("last_exchange", default=None)

_DNS_MARKERS = ("name or service not known", "getaddrinfo failed", "temporary failure in name resolution",
                "nodename nor servname", "no address associated", "name resolution")


def new_request_id():
    return uuid.uuid4().hex[:12]


def response_excerpt(text, limit=300):
    """Court extrait expurgé d'une réponse illisible : utile pour détecter un changement de format."""
    text = (text or "").strip().replace("\r", " ").replace("\n", " ")
    return redact(text[:limit]) + ("…" if len(text) > limit else "")


class ConnectorHTTP:
    #: transport injectable pour les tests (httpx.MockTransport)
    transport = None

    def __init__(self, catalogue):
        self.catalogue = catalogue
        self.timeout = catalogue.timeout_seconds or settings.CONNECTOR_DEFAULT_TIMEOUT
        self.min_interval = max(catalogue.min_interval_seconds or 0, 0)

    def _throttle(self):
        with _lock:
            last = _last_request.get(self.catalogue.code, 0)
            wait = self.min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(min(wait, 10))
            _last_request[self.catalogue.code] = time.monotonic()

    def _client(self):
        kwargs = {
            "timeout": self.timeout,
            "headers": {"User-Agent": settings.CONNECTOR_USER_AGENT, "Accept-Language": "ja,fr;q=0.8,en;q=0.6"},
            "follow_redirects": True,
        }
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.Client(**kwargs)

    def _diag(self, request_id, url, params, started, attempts, **extra):
        shown = str(httpx.URL(url, params=params)) if params else url
        diag = {"request_id": request_id, "url": redact_url(shown), "source": self.catalogue.code,
                "elapsed_ms": int((time.monotonic() - started) * 1000), "attempts": attempts,
                "timeout_s": self.timeout}
        diag.update(extra)
        last_exchange.set(diag)
        return diag

    def get(self, url, params=None, *, accept="application/json", use_cache=True, retries=2):
        key = "conn:" + hashlib.sha256(json.dumps([url, params], sort_keys=True, default=str).encode()).hexdigest()
        request_id = new_request_id()
        started = time.monotonic()
        if use_cache:
            hit = cache.get(key)
            if hit is not None:
                self._diag(request_id, url, params, started, 0, cached=True, http_status=hit.get("status"))
                return dict(hit, request_id=request_id)
        last_exc = None
        for attempt in range(retries + 1):
            self._throttle()
            try:
                with self._client() as client:
                    response = client.get(url, params=params, headers={"Accept": accept})
            except httpx.TimeoutException as exc:
                diag = self._diag(request_id, url, params, started, attempt + 1, exception=exc.__class__.__name__)
                last_exc = ConnectorError(f"Délai d'attente dépassé ({self.timeout:.0f} s).", kind="unavailable",
                                          code="timeout", diagnostic=diag)
                logger.warning("Délai dépassé pour %s : %s", self.catalogue.code, exc)
            except httpx.HTTPError as exc:
                text = str(exc).lower()
                dns = any(m in text for m in _DNS_MARKERS)
                diag = self._diag(request_id, url, params, started, attempt + 1, exception=exc.__class__.__name__,
                                  network_hint="dns" if dns else "connect")
                message = ("Adresse de la source introuvable (résolution DNS) : vérifiez la connexion Internet de ce poste."
                           if dns else f"Source injoignable : {exc.__class__.__name__}.")
                last_exc = ConnectorError(message, kind="unavailable", code="dns" if dns else "connect",
                                          diagnostic=diag)
                logger.warning("Erreur réseau pour %s : %s", self.catalogue.code, redact(str(exc)))
            else:
                status = response.status_code
                if status in (429, 502, 503, 504):
                    retry_after = response.headers.get("Retry-After", "")
                    delay = min(float(retry_after), 30) if retry_after.isdigit() else 2 ** (attempt + 1)
                    diag = self._diag(request_id, url, params, started, attempt + 1, http_status=status)
                    last_exc = ConnectorError(
                        f"La source limite ou refuse temporairement les requêtes (HTTP {status}).",
                        kind="unavailable", http_status=status, code=f"http_{status}", diagnostic=diag,
                    )
                    time.sleep(delay if attempt < retries else 0)
                    continue
                if status >= 500:
                    diag = self._diag(request_id, url, params, started, attempt + 1, http_status=status)
                    raise ConnectorError(f"Le serveur de la source est en erreur (HTTP {status}).", kind="unavailable",
                                         http_status=status, code=f"http_{status}", diagnostic=diag)
                if status == 404:
                    diag = self._diag(request_id, url, params, started, attempt + 1, http_status=status)
                    raise ConnectorError("Ressource introuvable sur la source (HTTP 404).", kind="technical",
                                         http_status=404, code="http_404", diagnostic=diag)
                if status >= 400:
                    diag = self._diag(request_id, url, params, started, attempt + 1, http_status=status,
                                      response_excerpt=response_excerpt(response.text, 200))
                    hint = (" Vérifiez l'identifiant d'accès du connecteur." if status in (401, 403) else
                            " La source a peut-être modifié son interface (paramètres refusés)." if status == 400 else "")
                    raise ConnectorError(f"La source a répondu par une erreur (HTTP {status}).{hint}", kind="technical",
                                         http_status=status, code=f"http_{status}", diagnostic=diag)
                diag = self._diag(request_id, url, params, started, attempt + 1, http_status=status,
                                  content_type=response.headers.get("content-type", ""))
                result = {"text": response.text, "status": status, "url": str(response.url),
                          "content_type": response.headers.get("content-type", "")}
                if use_cache:
                    cache.set(key, result, settings.CONNECTOR_CACHE_SECONDS)
                return dict(result, request_id=request_id)
            if attempt < retries:
                time.sleep(2 ** attempt)
        raise last_exc or ConnectorError("Erreur inconnue lors de l'appel à la source.", kind="technical")

    def get_json(self, url, params=None, **kwargs):
        result = self.get(url, params, **kwargs)
        try:
            return json.loads(result["text"])
        except ValueError as exc:
            raise format_error("La source n'a pas renvoyé de JSON valide.", result["text"], code="invalid_json") from exc


def format_error(message, text="", *, code="invalid_format"):
    """Construit une erreur « réponse impossible à interpréter » avec le contexte du dernier échange."""
    diag = dict(last_exchange.get() or {})
    if text:
        diag["response_excerpt"] = response_excerpt(text)
    return ResponseFormatError(message, code=code, http_status=diag.get("http_status"), diagnostic=diag)
