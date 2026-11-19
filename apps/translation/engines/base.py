"""
Contrat commun des moteurs de traduction (plan 1.3.0, lot 3).

Un moteur traduit une liste de segments d'une langue vers une autre. Il ne connaît rien des projets,
des tâches ni de la base de données : la chaîne de traitement (lot 4) ne dépend que de cette interface.
Ajouter un moteur (Ollama plus tard) = écrire une classe qui hérite de TranslationEngine et l'inscrire
dans registry.py.

Les erreurs sont des ConnectorError (contrat de la 1.2.0) : `kind` décide du traitement (indisponible,
configuration, requête…) et `code` porte la catégorie du journal des dysfonctionnements propre à la
traduction (cle_refusee, quota_depasse, langue_non_prise…).
"""
from dataclasses import dataclass, field

from apps.connectors.base import ConnectorError

#: Paires validées pour la 1.3.0 (décision B2) : japonais → français et anglais → français.
DEFAULT_PAIRS = frozenset({("ja", "fr"), ("en", "fr")})

#: Phrase fictive, non confidentielle, utilisée par le bouton « Tester » quand un moteur exige un texte.
TEST_PHRASE = "これは動作確認のための架空の文です。"


class TranslationEngineError(ConnectorError):
    """Erreur d'un moteur de traduction. `code` = catégorie du journal (voir apps.incidents.models.CATEGORIES)."""


def engine_error(message, *, kind, code="", http_status=None, diagnostic=None):
    return TranslationEngineError(message, kind=kind, code=code, http_status=http_status, diagnostic=diagnostic)


@dataclass
class Segment:
    """Un texte à traduire. `id` est propre à l'appel (numéro de segment, champ de notice…)."""

    id: str
    text: str


@dataclass
class EngineResult:
    """Résultat d'un appel. `translations` : identifiant de segment → texte traduit."""

    translations: dict
    chars_sent: int = 0
    model: str = ""
    engine_version: str = ""
    simulated: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    alerts: dict = field(default_factory=dict)  # identifiant → [alertes propres au moteur]


@dataclass
class EngineStatus:
    """État présenté dans Traduction → Moteurs. `usable` : peut être choisi pour traduire maintenant."""

    usable: bool
    label: str
    detail: str = ""
    simulated: bool = False
    level: str = "secondary"  # couleur Bootstrap : success, warning, danger, secondary


class TranslationEngine:
    code = ""
    label = ""
    online = True
    needs_key = False
    #: « native » (glossaire envoyé au service), « prompt » (entrées dans la consigne), « none » (contrôle local seul)
    glossary_support = "none"
    max_items = 50
    max_chars = 5000
    #: paramètre réseau injectable par les tests (httpx.MockTransport)
    transport = None

    def __init__(self, user, *, setting=None, ai_provider="", ai_model=""):
        self.user = user
        self.setting = setting
        self.ai_provider = ai_provider
        self.ai_model = ai_model

    # --- description ------------------------------------------------------------------------------
    def pairs(self):
        return DEFAULT_PAIRS

    def supports(self, source, target):
        return (source, target) in self.pairs()

    def status(self):
        raise NotImplementedError

    @property
    def display_name(self):
        return self.label

    # --- traduction -------------------------------------------------------------------------------
    def batches(self, segments):
        """Découpe en paquets respectant les limites du service (nombre de textes, caractères)."""
        batch, size = [], 0
        for seg in segments:
            n = len(seg.text)
            if batch and (len(batch) >= self.max_items or size + n > self.max_chars):
                yield batch
                batch, size = [], 0
            batch.append(seg)
            size += n
        if batch:
            yield batch

    def check_pair(self, source, target):
        if not self.supports(source, target):
            raise engine_error(f"{self.label} ne traduit pas de « {source} » vers « {target} » dans cette version.",
                               kind="unsupported", code="langue_non_prise")

    def translate(self, segments, source, target, *, glossary=None, variety="modern", context=None):
        """Traduit `segments` (liste de Segment). `glossary` : liste de (terme source, terme cible)."""
        raise NotImplementedError

    def test(self):
        """Vérifie le réglage sans texte réel. Retourne un message à afficher ; lève TranslationEngineError."""
        raise NotImplementedError
