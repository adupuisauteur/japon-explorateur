from celery import shared_task


@shared_task
def purge_expired_sessions():
    from .services import purge_expired

    return purge_expired()
