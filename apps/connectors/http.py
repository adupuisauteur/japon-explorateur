"""Client HTTP commun : identification, délais, limite de débit, cache, reprise sur erreur temporaire."""
import hashlib
import json
import logging
import threading
import time

import httpx
from django.conf import settings
from django.core.cache import cache

from .base import ConnectorError

logger = logging.getLogger(__name__)

_last_request = {}
_lock = threading.Lock()


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

    def get(self, url, params=None, *, accept="application/json", use_cache=True, retries=2):
        key = "conn:" + hashlib.sha256(json.dumps([url, params], sort_keys=True, default=str).encode()).hexdigest()
        if use_cache:
            hit = cache.get(key)
            if hit is not None:
                return hit
        last_exc = None
        for attempt in range(retries + 1):
            self._throttle()
            try:
                with self._client() as client:
                    response = client.get(url, params=params, headers={"Accept": accept})
            except httpx.TimeoutException as exc:
                last_exc = ConnectorError(f"Délai d'attente dépassé ({self.timeout:.0f} s).", temporary=True)
                logger.warning("Délai dépassé pour %s : %s", self.catalogue.code, exc)
            except httpx.HTTPError as exc:
                last_exc = ConnectorError(f"Source injoignable : {exc.__class__.__name__}.", temporary=True)
                logger.warning("Erreur réseau pour %s : %s", self.catalogue.code, exc)
            else:
                if response.status_code in (429, 502, 503, 504):
                    retry_after = response.headers.get("Retry-After", "")
                    delay = min(float(retry_after), 30) if retry_after.isdigit() else 2 ** (attempt + 1)
                    last_exc = ConnectorError(
                        f"La source limite ou refuse temporairement les requêtes (HTTP {response.status_code}).",
                        temporary=True,
                    )
                    time.sleep(delay if attempt < retries else 0)
                    continue
                if response.status_code == 404:
                    raise ConnectorError("Ressource introuvable sur la source (HTTP 404).")
                if response.status_code >= 400:
                    raise ConnectorError(f"La source a répondu par une erreur (HTTP {response.status_code}).")
                result = {"text": response.text, "status": response.status_code, "url": str(response.url),
                          "content_type": response.headers.get("content-type", "")}
                if use_cache:
                    cache.set(key, result, settings.CONNECTOR_CACHE_SECONDS)
                return result
            if attempt < retries:
                time.sleep(2 ** attempt)
        raise last_exc or ConnectorError("Erreur inconnue lors de l'appel à la source.")

    def get_json(self, url, params=None, **kwargs):
        result = self.get(url, params, **kwargs)
        try:
            return json.loads(result["text"])
        except ValueError as exc:
            raise ConnectorError("La source n'a pas renvoyé de JSON valide.") from exc
