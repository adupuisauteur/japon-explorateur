"""Test de démarrage d'Argos (2.0.0, lot 0) : traduction d'une phrase FICTIVE par le service local.

Lancé après chaque installation de paquet réussie et depuis la page « État de l'installation ». Le résultat
est enregistré (ServiceCheck « argos_essai ») : « Argos prêt » ou le message d'erreur précis, jamais masqué.
Aucun texte de l'utilisateur n'est utilisé ; rien ne quitte l'ordinateur.

2.0.0 (lot 3) : essai automatique 2 minutes après le démarrage de J-ed (donc après une mise à jour ou une
installation), seulement si Argos est prêt et n'a pas encore été essayé avec la version installée.
"""
from django.conf import settings

from apps.core.models import ServiceCheck

from .engines.argos import ArgosEngine
from .engines.base import TranslationEngineError

CHECK_NAME = "argos_essai"
#: phrase fictive (« Ceci est une courte phrase d'essai. »)
TEST_SENTENCE = "これは試験用の短い文です。"


def run_selftest(source="ja", target="fr", *, auto=False):
    engine = ArgosEngine(None)
    if not engine.service_url:
        return ServiceCheck.record(CHECK_NAME, False, "Service Argos non configuré (TRANSLATION_ARGOS_URL).")
    path, info, _reachable = engine._real_path(source, target)
    if path is None:
        return ServiceCheck.record(CHECK_NAME, False, f"Argos ne peut pas traduire : {info}.")
    try:
        data = engine._http().request("POST", f"{engine.service_url}/translate",
                                      json={"texts": [TEST_SENTENCE], "source": source, "target": target},
                                      n_texts=1, n_chars=len(TEST_SENTENCE))
    except TranslationEngineError as exc:
        return ServiceCheck.record(CHECK_NAME, False, f"Traduction d'essai en échec : {exc}", kind=exc.kind,
                                   code=exc.code)
    items = data.get("translations") if isinstance(data, dict) else None
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], str) or not items[0].strip():
        return ServiceCheck.record(CHECK_NAME, False, "Traduction d'essai : réponse vide ou mal formée du service.")
    return ServiceCheck.record(CHECK_NAME, True, f"Argos prêt — {info}.", sentence=TEST_SENTENCE,
                               translation=items[0][:300], pair=f"{source}→{target}",
                               version=settings.APP_VERSION, auto=auto)


#: nombre maximal d'essais automatiques quand le service ne répond pas encore (il démarre, ou se construit)
AUTO_ATTEMPTS = 5


def auto_selftest(attempt=1):
    """Essai automatique après démarrage. Retourne « fait », « inutile », « attente » ou « abandon »."""
    engine = ArgosEngine(None)
    if not engine.service_url:
        return "inutile"
    path, _info, reachable = engine._real_path("ja", "fr")
    if not reachable:
        return "attente" if attempt < AUTO_ATTEMPTS else "abandon"
    if path is None:
        return "inutile"  # paquets absents : l'invitation à les installer s'affiche dans l'application
    last = ServiceCheck.objects.filter(name=CHECK_NAME).first()
    if last and last.ok and last.data.get("version") == settings.APP_VERSION:
        return "inutile"  # déjà essayé avec cette version
    run_selftest(auto=True)
    return "fait"
