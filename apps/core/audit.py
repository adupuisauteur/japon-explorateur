"""Journalisation des actions sensibles (sans secrets ni données inutiles)."""
from .logging import redact


def log_action(request_or_user, action, target=None, summary="", **details):
    from .models import AuditLog

    user = None
    ip = None
    if request_or_user is not None:
        if hasattr(request_or_user, "user"):
            user = request_or_user.user if request_or_user.user.is_authenticated else None
            ip = request_or_user.META.get("REMOTE_ADDR")
        else:
            user = request_or_user
    target_type = target_id = ""
    if target is not None:
        target_type = target.__class__.__name__
        target_id = str(getattr(target, "pk", ""))
    clean = {k: redact(v) if isinstance(v, str) else v for k, v in details.items()}
    return AuditLog.objects.create(
        user=user,
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=redact(summary)[:500],
        details=clean,
        ip_address=ip,
    )
