from django.apps import AppConfig


class TranslationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.translation"
    verbose_name = "Traduction"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import pre_delete

        from .ownership import on_user_pre_delete

        pre_delete.connect(on_user_pre_delete, sender=get_user_model(), dispatch_uid="translation.user_pre_delete")
