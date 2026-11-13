from celery import shared_task


@shared_task
def scheduled_backup():
    from apps.core.models import AppSettings

    from .services import create_backup

    if AppSettings.get().backup_enabled:
        create_backup("full", scheduled=True)


@shared_task
def run_backup(kind, user_id=None):
    from django.contrib.auth import get_user_model

    from .services import create_backup

    user = get_user_model().objects.filter(pk=user_id).first()
    create_backup(kind, user=user)
