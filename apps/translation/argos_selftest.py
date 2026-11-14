"""Test de démarrage d'Argos (2.0.0, lot 0) : traduction d'une phrase FICTIVE par le service local.

Lancé après chaque installation de paquet réussie et depuis la page « État de l'installation ». Le résultat
est enregistré (ServiceCheck « argos_essai ») : « Argos prêt » ou le message d'erreur précis, jamais masqué.
Aucun texte de l'utilisateur n'est utilisé ; rien ne quitte l'ordinateur.
"""
from apps.core.models import ServiceCheck

from .engines.argos import ArgosEngine
from .engines.base import TranslationEngineError

CHECK_NAME = "argos_essai"
#: phrase fictive (« Ceci est une courte phrase d'essai. »)
TEST_SENTENCE = "これは試験用の短い文です。"


def run_selftest(source="ja", target="fr"):
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
                               translation=items[0][:300], pair=f"{source}→{target}")
