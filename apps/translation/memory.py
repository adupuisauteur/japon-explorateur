"""
Mémoire de traduction : correspondance EXACTE seulement (décision A5).

Deux segments correspondent si leurs textes sont identiques après normalisation NFKC (formes pleine
chasse / demi-chasse unifiées) et réduction des espaces. Seules les versions VALIDÉES, non exclues de
la mémoire, des projets du même propriétaire sont reprises : la mémoire ne fait jamais circuler un texte
d'un compte à un autre (confidentialité). Une reprise crée une version « proposée », jamais validée.
"""
import hashlib
import re
import unicodedata

_SPACES = re.compile(r"\s+")


def normalize(text):
    return _SPACES.sub(" ", unicodedata.normalize("NFKC", text or "")).strip()


def memory_key(text):
    norm = normalize(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest() if norm else ""


def lookup(owner, key, *, exclude_segment=None):
    """Dernière version validée et non exclue, dans les projets de `owner`, pour la clé donnée."""
    from .models import TranslationVersion

    if not key:
        return None
    qs = (TranslationVersion.objects.filter(status="validated", excluded_from_memory=False,
                                            segment__memory_key=key, segment__document__project__owner=owner)
          .select_related("segment").order_by("-decided_at", "-created_at"))
    if exclude_segment is not None:
        qs = qs.exclude(segment=exclude_segment)
    return qs.first()
