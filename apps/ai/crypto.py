"""Chiffrement au repos des clés API (Fernet / AES-128-CBC + HMAC).

La clé maîtresse vient de la variable d'environnement AI_KEYS_ENCRYPTION_KEY, jamais
de la base ni du dépôt. Sans elle, l'enregistrement de clés API est refusé.
"""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    key = settings.AI_KEYS_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured(
            "AI_KEYS_ENCRYPTION_KEY n'est pas défini : impossible de stocker une clé API de façon sécurisée. "
            "Générez-la avec « python manage.py generate_secrets »."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encryption_available():
    try:
        _fernet()
        return True
    except (ImproperlyConfigured, ValueError):
        return False


def encrypt_secret(secret):
    return _fernet().encrypt(secret.strip().encode("utf-8")).decode("ascii")


def decrypt_secret(token):
    """Réservé au composant serveur chargé des appels IA (providers.py)."""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ImproperlyConfigured("Clé API illisible : la clé de chiffrement a changé. Ressaisissez la clé.") from exc
