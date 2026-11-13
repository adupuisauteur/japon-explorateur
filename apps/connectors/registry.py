"""Registre des connecteurs. Ajouter une source = ajouter une classe et l'enregistrer ici."""
from .base import ConnectorNotConfigured

_REGISTRY = {}


def register(cls):
    _REGISTRY[cls.key] = cls
    return cls


def available_connectors():
    _load()
    return dict(sorted(_REGISTRY.items()))


def get_connector(catalogue):
    _load()
    cls = _REGISTRY.get(catalogue.connector or "")
    if cls is None:
        raise ConnectorNotConfigured(
            f"Aucun connecteur opérationnel n'est associé à « {catalogue.name} » (import de fichiers uniquement)."
        )
    return cls(catalogue)


def connector_class(key):
    _load()
    return _REGISTRY.get(key or "")


def _load():
    if _REGISTRY:
        return
    from . import cinii, japansearch, kokusho, local, ndl  # noqa: F401
