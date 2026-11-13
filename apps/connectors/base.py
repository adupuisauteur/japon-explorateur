"""
Contrat commun des connecteurs (§5.2).

Un connecteur interroge une source et renvoie des résultats structurés et
traçables. Il ne connaît rien du reste de l'application : le moteur de recherche
et le gestionnaire de mises à jour ne dépendent que de cette interface.
"""
import time
from dataclasses import dataclass, field
from typing import Iterator, Optional


class ConnectorError(Exception):
    """Erreur explicite et présentable à l'utilisateur."""

    def __init__(self, message, *, temporary=False):
        super().__init__(message)
        self.temporary = temporary


class ConnectorNotConfigured(ConnectorError):
    pass


@dataclass
class SearchQuery:
    text: str = ""
    variants: list = field(default_factory=list)
    title: str = ""
    creator: str = ""
    subject: str = ""
    place: str = ""
    date_from: Optional[int] = None
    date_to: Optional[int] = None
    filters: dict = field(default_factory=dict)
    page: int = 1
    page_size: int = 20

    def all_terms(self):
        """Requête principale + variantes retenues par l'utilisateur."""
        terms = [self.text] if self.text else []
        for v in self.variants:
            if v and v not in terms:
                terms.append(v)
        return terms


@dataclass
class ConnectorResult:
    """Résultat normalisé selon les champs de notice (RECORD_SOURCE_FIELDS)."""

    source_id: str
    data: dict
    raw: dict = field(default_factory=dict)
    raw_format: str = "json"

    @property
    def title(self):
        return self.data.get("original_title") or "(sans titre)"


@dataclass
class SearchResponse:
    results: list
    total: Optional[int] = None
    page: int = 1
    has_more: bool = False
    warnings: list = field(default_factory=list)
    elapsed_ms: int = 0


@dataclass
class HarvestBatch:
    results: list
    cursor: Optional[str] = None
    done: bool = True


class BaseConnector:
    do_not_call_in_templates = True  # la classe est passée telle quelle aux gabarits
    key = "base"
    label = "Connecteur"
    description = ""
    #: capacités déclarées, affichées dans l'écran Sources
    supports_search = True
    supports_fielded_search = False
    supports_date_filter = False
    supports_fetch = False
    supports_harvest = False
    supports_incremental = False
    #: champs que la source ne fournit pas ou que le connecteur ne traite pas
    unsupported_fields: list = []
    #: paramètres attendus dans Catalogue.config : {clé: description}
    config_help: dict = {}

    def __init__(self, catalogue):
        self.catalogue = catalogue
        self.config = dict(catalogue.config or {})

    # -- opérations ------------------------------------------------------------
    def search(self, query: SearchQuery) -> SearchResponse:
        raise ConnectorError("Ce connecteur ne permet pas la recherche directe.")

    def fetch_record(self, source_id: str) -> Optional[ConnectorResult]:
        raise ConnectorError("Ce connecteur ne permet pas de récupérer une notice par identifiant.")

    def harvest(self, since=None, cursor=None) -> Iterator[HarvestBatch]:
        raise ConnectorError("Ce connecteur ne permet pas de moisson complète ou incrémentale.")

    def test(self):
        """Vérifie la disponibilité. Retourne (ok: bool, message: str, details: dict)."""
        try:
            started = time.monotonic()
            response = self.search(SearchQuery(text="源氏物語", page_size=1))
            ms = int((time.monotonic() - started) * 1000)
            return True, f"La source répond ({ms} ms, {response.total if response.total is not None else '?'} résultats).", {}
        except ConnectorError as exc:
            return False, str(exc), {}

    # -- description -----------------------------------------------------------
    @classmethod
    def capabilities(cls):
        return [
            ("Recherche", cls.supports_search),
            ("Recherche par champs", cls.supports_fielded_search),
            ("Filtre de dates", cls.supports_date_filter),
            ("Notice par identifiant", cls.supports_fetch),
            ("Moisson complète", cls.supports_harvest),
            ("Synchronisation incrémentale", cls.supports_incremental),
        ]
