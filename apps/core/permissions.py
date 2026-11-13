"""Contrôles d'accès côté serveur selon les rôles (§13.2)."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restreint une vue aux rôles indiqués ('admin', 'researcher', 'reader')."""

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles and not request.user.is_superuser:
                raise PermissionDenied("Votre rôle ne permet pas cette action.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


admin_required = role_required("admin")
researcher_required = role_required("admin", "researcher")
