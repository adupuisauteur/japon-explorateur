"""
Registre des moteurs. Ajouter un moteur (Ollama, plus tard) : une classe dans ce dossier, une ligne ici.
Le reste du module ne connaît que `get_engine` et `ENGINE_CLASSES`.
"""
from .ai import AIEngine
from .argos import ArgosEngine
from .deepl import DeepLEngine
from .google_basic import GoogleBasicEngine

ENGINE_CLASSES = {cls.code: cls for cls in (DeepLEngine, GoogleBasicEngine, ArgosEngine, AIEngine)}


def get_engine(code, user, *, ai_provider="", ai_model=""):
    """Instancie le moteur `code` pour `user`, avec son réglage (clé, offre…) s'il en a un."""
    from ..models import EngineSetting

    cls = ENGINE_CLASSES.get(code)
    if cls is None:
        from .base import engine_error

        raise engine_error(f"Moteur de traduction inconnu : « {code} ».", kind="config")
    setting = None
    if code != "ai":
        setting = EngineSetting.objects.filter(user=user, engine=code).first()
    return cls(user, setting=setting, ai_provider=ai_provider, ai_model=ai_model)
