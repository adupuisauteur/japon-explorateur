from django.apps import AppConfig


class HelpConfig(AppConfig):
    """2.0.0 (lot 6) : aide intégrée, tirée des fichiers Markdown de docs/aide/ (une seule source)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.help"
    verbose_name = "Aide"
