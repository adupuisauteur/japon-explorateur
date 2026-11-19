from celery import shared_task


@shared_task
def purge_old_notifications():
    """2.0.0 (lot 3) : nettoyage quotidien des notifications lues anciennes (jamais des non lues)."""
    from .services import purge_old

    return purge_old()
