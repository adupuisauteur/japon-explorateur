"""
Argos Translate : moteur local, hors ligne, sans clé (décision A1 : service Docker séparé et facultatif).

Ce module est le CLIENT du service `argos` (docker/argos/server.py, lot 9). Contrat du service, sur le
réseau interne Docker uniquement :
  GET  /health       → {"argos_version": "…", "packages": [{"from": "ja", "to": "en", "version": "1.1"}, …]}
  POST /translate    → corps {"texts": […], "source": "ja", "target": "fr"}
                       réponse {"translations": […], "path": ["ja", "en", "fr"]}
  POST /index        → paquets proposés par l'index Argos (le service consulte Internet)
  POST /install      → {"from", "to"} : téléchargement depuis l'index et installation (Internet)
  POST /install-file → {"filename"} : installation d'un fichier .argosmodel du dossier de dépôt
  POST /remove       → {"from", "to"}
  POST /install-sbd  → {"from", "to"} : modèle de découpage en phrases d'un paquet qui n'en contient pas (Internet)
Les quatre derniers ne sont appelés que sur action explicite (Traduction → Moteurs locaux) : le choix de
télécharger des paquets appartient à l'utilisateur.

Mode démonstration (2.0.0, décision D4 ; « mode simulé » de la 1.3.0) : la simulation n'est plus un repli
automatique. Elle n'a lieu que si l'administrateur active « Argos : mode démonstration » (Administration →
Paramètres). Argos ne traduit alors rien : il renvoie le texte original précédé de la mention
« [Simulation Argos — aucune traduction réelle] » ; ces versions portent l'indicateur `simulated` et la
mention « Simulation » partout.

Sans ce mode, une traduction impossible est une ERREUR, jamais une simulation :
- service injoignable (arrêté, en redémarrage, mémoire insuffisante…) : erreur « indisponibilite » ; la
  tâche est interrompue et reprenable, les éléments non traités restent en attente ;
- paquets ou modèle de découpage absents : erreur de configuration « paquet_absent » ; la tâche s'arrête.
En 1.3.0, un service devenu injoignable au milieu d'une tâche produisait des simulations pour la suite
de la tâche, sans erreur (constat de l'audit 2.0.0).
"""
from django.conf import settings

from ..http import TranslationHTTP
from .base import EngineResult, EngineStatus, TranslationEngine, TranslationEngineError, engine_error

SIMULATION_PREFIX = "[Simulation Argos — aucune traduction réelle] "
PIVOT = "en"
#: paquets nécessaires à chaque paire de la 1.3.0 (pas de paquet direct japonais → français dans l'index)
NEEDED = {("ja", "fr"): [("ja", "en"), ("en", "fr")], ("en", "fr"): [("en", "fr")]}

#: codes d'erreur du service → catégorie du journal et nature
SERVICE_CODES = {
    "paquet_absent": ("unsupported", "paquet_absent"),
    "sbd_absent": ("config", "paquet_absent"),
    "paquet_corrompu": ("technical", "paquet_absent"),
    "argos_absent": ("config", "paquet_absent"),
    "fichier_absent": ("query", ""),
    "fichier_refuse": ("query", ""),
    "langue_non_prise": ("unsupported", "langue_non_prise"),
    "occupe": ("unavailable", ""),
    "index_injoignable": ("unavailable", ""),
    "telechargement_echoue": ("unavailable", ""),
    # erreur interne du service : son type est affiché (jamais masqué derrière « momentanément indisponible »)
    "erreur_interne": ("technical", ""),
}


class ArgosHTTP(TranslationHTTP):
    def classify(self, status, service_code, service_message, diagnostic):
        if service_code in SERVICE_CODES:
            kind, code = SERVICE_CODES[service_code]
            return engine_error(f"Service Argos : {service_message or service_code}", kind=kind, code=code,
                                http_status=status, diagnostic=diagnostic)
        return super().classify(status, service_code, service_message, diagnostic)


def _path(source, target, packages):
    # Un paquet sans son modèle de découpage en phrases ne peut pas traduire hors ligne : ignoré.
    have = {(p.get("from"), p.get("to")) for p in packages if p.get("sbd_ready", True)}
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
        return ArgosHTTP("Argos Translate", timeout=timeout or settings.TRANSLATION_TIMEOUTS.get("argos"),
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

    @staticmethod
    def demo_mode():
        from apps.core.models import AppSettings

        return AppSettings.get().argos_demo_mode

    def _real_path(self, source, target):
        """(chemin, détail, joignable) : chemin si une traduction réelle est possible, sinon None et la raison.

        `joignable` vaut False si le service ne répond pas (ou n'est pas configuré) : situation passagère,
        à distinguer des paquets manquants, qui demandent une action de l'administrateur.
        """
        try:
            health = self.health()
        except Exception as exc:  # service arrêté, profil non démarré, réseau Docker…
            return None, f"service Argos injoignable — est-il démarré ? ({str(exc).rstrip('.')})", False
        if health is None:
            return None, "service Argos non configuré (TRANSLATION_ARGOS_URL)", False
        packages = health.get("packages") or []
        path = _path(source, target, packages)
        if path is None:
            if _path(source, target, [dict(p, sbd_ready=True) for p in packages]):
                return None, "modèle de découpage en phrases manquant (Traduction → Moteurs locaux)", True
            return None, "paquets de langues nécessaires non installés (Traduction → Moteurs locaux)", True
        versions = {f"{p['from']}→{p['to']}": p.get("version", "?") for p in packages}
        used = " ; ".join(f"{a}→{b} {versions.get(f'{a}→{b}', '?')}" for a, b in zip(path, path[1:]))
        return path, f"Argos {health.get('argos_version', '?')} — {used}", True

    def status(self):
        s = self.setting
        if s is None or not s.enabled:
            return EngineStatus(False, "Non activé", "Activez Argos pour l'utiliser.")
        path, info, _reachable = self._real_path("ja", "fr")
        if path:
            return EngineStatus(True, "Disponible hors ligne", info, level="success")
        if self.demo_mode():
            return EngineStatus(True, "Mode démonstration", f"Aucune traduction réelle : {info}.", simulated=True,
                                level="warning")
        return EngineStatus(False, "Indisponible", f"Argos ne peut pas traduire : {info}.", level="danger")

    def test(self):
        path, info, _reachable = self._real_path("ja", "fr")
        if path:
            return f"Service Argos disponible : {info}."
        if self.demo_mode():
            return f"Mode démonstration : {info}. Les traductions porteront la mention « Simulation »."
        return f"Argos ne peut pas traduire : {info}."

    def translate(self, segments, source, target, *, glossary=None, variety="modern", context=None):
        self.check_pair(source, target)
        if self.setting is None or not self.setting.enabled:
            raise engine_error("Argos n'est pas activé dans Traduction → Moteurs.", kind="config")
        path, info, reachable = self._real_path(source, target)
        chars = sum(len(s.text) for s in segments)
        if path is None:
            if self.demo_mode():
                return EngineResult({s.id: SIMULATION_PREFIX + s.text for s in segments}, chars_sent=0,
                                    model="Argos (simulation)", engine_version=info, simulated=True)
            if not reachable:
                raise engine_error(f"Argos ne peut pas traduire : {info}.", kind="unavailable",
                                   code="indisponibilite")
            raise engine_error(f"Argos ne peut pas traduire : {info}.", kind="config", code="paquet_absent")
        translations = {}
        for batch in self.batches(segments):
            try:
                data = self._http().request("POST", f"{self.service_url}/translate",
                                            json={"texts": [s.text for s in batch], "source": source,
                                                  "target": target},
                                            n_texts=len(batch), n_chars=sum(len(s.text) for s in batch))
            except TranslationEngineError as exc:
                if exc.kind == "unavailable" and not exc.code:  # connexion perdue pendant l'envoi
                    raise engine_error(f"{exc} La tâche pourra reprendre quand le service répondra.",
                                       kind="unavailable", code="indisponibilite",
                                       diagnostic=exc.diagnostic) from None
                raise
            items = data.get("translations") if isinstance(data, dict) else None
            if not isinstance(items, list) or len(items) != len(batch) or not all(isinstance(t, str) for t in items):
                raise engine_error("Réponse du service Argos incomplète ou mal formée.", kind="unparsable",
                                   code="reponse_vide")
            translations.update({s.id: t for s, t in zip(batch, items)})
        return EngineResult(translations, chars_sent=chars, model="Argos Translate", engine_version=info)

    # --- gestion des paquets (Traduction → Moteurs locaux ; action explicite de l'utilisateur) -----------
    def _require_service(self):
        if not self.service_url:
            raise engine_error("Service Argos non configuré (TRANSLATION_ARGOS_URL).", kind="config")

    def index(self):
        """Paquets proposés par l'index Argos. Le service consulte Internet : appel sur action explicite."""
        self._require_service()
        data = self._http(timeout=60).request("POST", f"{self.service_url}/index", json={})
        items = data.get("packages") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise engine_error("Réponse inattendue du service Argos (index).", kind="unparsable", code="reponse_vide")
        return items

    def install(self, source, target):
        """Téléchargement depuis l'index et installation (long : délai TRANSLATION_ARGOS_INSTALL_TIMEOUT)."""
        self._require_service()
        return self._http(timeout=settings.TRANSLATION_ARGOS_INSTALL_TIMEOUT).request(
            "POST", f"{self.service_url}/install", json={"from": source, "to": target})

    def install_file(self, filename):
        self._require_service()
        return self._http(timeout=settings.TRANSLATION_ARGOS_INSTALL_TIMEOUT).request(
            "POST", f"{self.service_url}/install-file", json={"filename": filename})

    def install_sbd(self, source, target):
        self._require_service()
        return self._http(timeout=settings.TRANSLATION_ARGOS_INSTALL_TIMEOUT).request(
            "POST", f"{self.service_url}/install-sbd", json={"from": source, "to": target})

    def remove(self, source, target):
        self._require_service()
        return self._http(timeout=60).request("POST", f"{self.service_url}/remove", json={"from": source, "to": target})
