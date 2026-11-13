"""Filtre de journalisation empêchant l'écriture de clés API ou secrets."""
import logging
import re

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),          # OpenAI / Anthropic (sk-ant-...)
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),          # Google
    re.compile(r"(?i)(x-api-key|authorization|api[_-]?key|key)=?[:\s\"']+[A-Za-z0-9_\-\.]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{16,}"),
]


def redact(text):
    if not isinstance(text, str):
        return text
    for pattern in _PATTERNS:
        text = pattern.sub("[secret masqué]", text)
    return text


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
