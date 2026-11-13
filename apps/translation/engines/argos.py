"""
Argos Translate : moteur local, hors ligne, sans clé (décision A1 : service Docker séparé et facultatif).

Ce module est le CLIENT du service `argos` (construit au lot 9). Contrat du service, sur le réseau
interne Docker uniquement :
  GET  /health    → {"argos_version": "…", "packages": [{"from": "ja", "to": "en", "version": "1.1"}, …]}
  POST /translate → corps {"texts": […], "source": "ja", "target": "fr"}
                    réponse {"translations": […], "path": ["ja", "en", "fr"]}

Mode simulé (décision du 13 novembre 2026) : tant que le service n'est pas activé ou que les paquets
nécessaires ne sont pas installés (leur téléchargement attend votre autorisation), Argos peut être
activé en MODE SIMULÉ. Il ne traduit alors rien : il renvoie le texte original précédé de la mention
« [Simulation Argos — aucune traduction réelle] ». Ces versions portent l'indicateur `simulated` et la
mention « Simulation » partout ; elles restent validables.
"""
from django.conf import settings

from ..http import TranslationHTTP
from .base import EngineResult, EngineStatus, TranslationEngine, engine_error

SIMULATION_PREFIX = "[Simulation Argos — aucune traduction réelle] "
PIVOT = "en"


def _path(source, target, packages):
    have = {(p.get("from"), p.get("to")) for p in packages}
    if (source, target) in have:
        return [source, target]
    if (source, PIVOT) in have and (PIVOT, target) in have:
        return [source, PIVOT, target]
    return None


class ArgosEngine(TranslationEngine):
    code = "argos"
    label = "Argos Translate (local)"
    online = False
    needs_key = False
    glossary_support = "none"
    max_items = 50
    max_chars = 20000

    def _http(self, timeout=None):
        return TranslationHTTP("Argos Translate", timeout=timeout or settings.TRANSLATION_TIMEOUTS.get("argos"),
                               transport=self.transport, retries=0)

    @property
    def service_url(self):
        return (settings.TRANSLATION_ARGOS_URL or "").rstrip("/")

    def health(self):
        """État du service, ou None s'il n'est pas activé dans la configuration."""
        if not self.service_url:
            return None
        data = self._http(timeout=3).request("GET", f"{self.service_url}/health")
        if not isinstance(data, dict) or not isinstance(data.get("packages"), list):
            raise engine_error("Réponse inattendue du service Argos.", kind="unparsable", code="paquet_absent")
        return data

    def _real_path(self, source, target):
        """(chemin, versions) si une traduction réelle est possible ; sinon (None, raison)."""
        try:
            health = self.health()
        except Exception as exc:  # service arrêté, réseau Docker…
            return None, f"service Argos injoignable ({exc})"
        if health is None:
            return None, "service Argos non activé (profil Docker « hors-ligne »)"
        packages = health.get("packages") or []
        path = _path(source, target, packages)
        if path is None:
            return None, "paquets de langues nécessaires non installés"
        versions = {f"{p['from']}→{p['to']}": p.get("version", "?") for p in packages}
        used = " ; ".join(f"{a}→{b} {versions.get(f'{a}→{b}', '?')}" for a, b in zip(path, path[1:]))
        return path, f"Argos {health.get('argos_version', '?')} — {used}"

    def status(self):
        s = self.setting
        if s is None or not s.enabled:
            return EngineStatus(False, "Non activé", "Activez Argos pour l'utiliser (en mode simulé tant que le "
                                "service et ses paquets ne sont pas installés).")
        path, info = self._real_path("ja", "fr")
        if path:
            return EngineStatus(True, "Disponible hors ligne", info, level="success")
        return EngineStatus(True, "Mode simulé", f"Aucune traduction réelle : {info}.", simulated=True,
                            level="warning")

    def test(self):
        path, info = self._real_path("ja", "fr")
        if path:
            return f"Service Argos disponible : {info}."
        return f"Mode simulé : {info}. Les traductions porteront la mention « Simulation »."

    def translate(self, segments, source, target, *, glossary=None, variety="modern", context=None):
        self.check_pair(source, target)
        if self.setting is None or not self.setting.enabled:
            raise engine_error("Argos n'est pas activé dans Traduction → Moteurs.", kind="config")
        path, info = self._real_path(source, target)
        chars = sum(len(s.text) for s in segments)
        if path is None:
            return EngineResult({s.id: SIMULATION_PREFIX + s.text for s in segments}, chars_sent=0,
                                model="Argos (simulation)", engine_version=info, simulated=True)
        translations = {}
        for batch in self.batches(segments):
            data = self._http().request("POST", f"{self.service_url}/translate",
                                        json={"texts": [s.text for s in batch], "source": source, "target": target},
                                        n_texts=len(batch), n_chars=sum(len(s.text) for s in batch))
            items = data.get("translations") if isinstance(data, dict) else None
            if not isinstance(items, list) or len(items) != len(batch) or not all(isinstance(t, str) for t in items):
                raise engine_error("Réponse du service Argos incomplète ou mal formée.", kind="unparsable",
                                   code="reponse_vide")
            translations.update({s.id: t for s, t in zip(batch, items)})
        return EngineResult(translations, chars_sent=chars, model="Argos Translate", engine_version=info)
