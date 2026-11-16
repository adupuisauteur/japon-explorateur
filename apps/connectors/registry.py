"""Registre des connecteurs. Ajouter une source = ajouter une classe et l'enregistrer ici."""
from .base import ConnectorNotConfigured

_REGISTRY = {}
_LOADED = False


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
    """2.0.0 (lot 10) : le test « registre vide » laissait le registre incomplet quand un module de connecteur avait
    déjà été importé ailleurs (il s'enregistre alors seul) : les autres sources n'étaient jamais chargées. Cause des
    tests de recherche instables depuis la 1.x, selon l'ordre des tests."""
    global _LOADED
    if _LOADED:
        return
    from . import aozora, cinii, japansearch, kokusho, local, ndl
    from .base import BaseConnector

    for module in (aozora, cinii, japansearch, kokusho, local, ndl):  # sans dépendre de l'ordre des imports
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, BaseConnector) and value is not BaseConnector \
                    and value.__module__ == module.__name__:
                _REGISTRY.setdefault(value.key, value)
    _LOADED = True
