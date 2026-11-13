from django.apps import AppConfig


class IncidentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.incidents"
    verbose_name = "Journal des dysfonctionnements"

    def ready(self):
        from django.core.signals import got_request_exception

        got_request_exception.connect(_on_request_exception, dispatch_uid="incidents.request_exception")


def _on_request_exception(sender, request=None, **kwargs):
    """Erreur non prévue lors de l'affichage d'une page (erreur 500) : journalisée avec le chemin, sans paramètres."""
    import sys

    from django.db import DatabaseError

    from .services import record_database_error, record_exception

    exc = sys.exc_info()[1]
    if exc is None:
        return
    path = getattr(request, "path", "") if request is not None else ""
    operation = f"Affichage de la page {path}" if path else "Traitement d'une requête"
    extra = {"path": path, "method": getattr(request, "method", ""),
             "request_id": getattr(request, "request_id", "")}
    if isinstance(exc, DatabaseError):
        record_database_error(exc, operation=operation)
    else:
        record_exception(exc, module="application", operation=operation, extra=extra)
