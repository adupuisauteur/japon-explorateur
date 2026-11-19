"""Masquage des secrets et données personnelles inutiles dans les journaux (techniques et dysfonctionnements)."""
import logging
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit

MASK = "[secret masqué]"

#: Noms de paramètres ou de champs dont la valeur n'est jamais conservée.
SENSITIVE_NAMES = {
    "appid", "app_id", "api_key", "apikey", "key", "token", "access_token", "refresh_token", "id_token",
    "password", "passwd", "pwd", "secret", "client_secret", "signature", "sig", "auth", "authorization",
    "session", "sessionid", "csrftoken", "csrfmiddlewaretoken", "cookie", "x-api-key", "setup_token",
    "postgres_password", "django_secret_key", "ai_keys_encryption_key", "cinii_appid",
}

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),          # OpenAI / Anthropic (sk-ant-...)
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),          # Google
    re.compile(r"(?i)(x-api-key|authorization|api[_-]?key|key)=?[:\s\"']+[A-Za-z0-9_\-\.]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{16,}"),
    # paramètres sensibles dans une adresse ou un texte : appid=…, token=…, password=…
    re.compile(r"(?i)\b(appid|app_id|api_?key|access_token|token|password|passwd|secret|signature|sessionid|csrftoken)"
               r"=(?!\[secret)([^&\s\"'<>]+)"),
    # chaînes de connexion : postgres://utilisateur:motdepasse@hôte
    re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^:/\s@]+):([^@\s/]+)@"),
]
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Dossiers personnels (Windows, macOS, Linux) : le nom de l'utilisateur du poste n'est pas utile au diagnostic.
_HOME = re.compile(r"(?i)([A-Z]:\\Users\\|/Users/|/home/)([^\\/\s]+)")


def redact(text):
    if not isinstance(text, str):
        return text
    for i, pattern in enumerate(_PATTERNS):
        if i == 4:
            text = pattern.sub(lambda m: f"{m.group(1)}={MASK}", text)
        elif i == 5:
            text = pattern.sub(lambda m: f"{m.group(1)}:{MASK}@", text)
        else:
            text = pattern.sub(MASK, text)
    text = _EMAIL.sub("[adresse e-mail masquée]", text)
    text = _HOME.sub(lambda m: f"{m.group(1)}[utilisateur]", text)
    return text


def redact_url(url):
    """Retire les valeurs des paramètres sensibles d'une adresse (ex. appid de CiNii)."""
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return redact(url)
    query = [(k, MASK if k.lower() in SENSITIVE_NAMES else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    netloc = parts.netloc
    if "@" in netloc:  # identifiants dans l'adresse
        netloc = f"{MASK}@" + netloc.split("@", 1)[1]
    # Paramètres laissés lisibles (caractères japonais compris) : l'adresse sert au diagnostic, pas à la navigation.
    readable = "&".join(f"{k}={v}" for k, v in query)
    return redact(urlunsplit((parts.scheme, netloc, parts.path, readable, parts.fragment)))


def redact_mapping(value, depth=0):
    """Expurge récursivement un dictionnaire / une liste (clés sensibles, motifs de secrets)."""
    if depth > 6:
        return "…"
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if str(k).lower() in SENSITIVE_NAMES:
                out[k] = MASK
            elif str(k).lower() in ("url", "link", "endpoint") and isinstance(v, str):
                out[k] = redact_url(v)
            else:
                out[k] = redact_mapping(v, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_mapping(v, depth + 1) for v in value]
    if isinstance(value, str):
        return redact(value)
    return value


class RedactSecretsFilter(logging.Filter):
    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - message mal formé
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg = cleaned
            record.args = ()
        return True
