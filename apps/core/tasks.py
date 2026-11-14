"""Tâches Celery du socle (2.0.0)."""
from celery import shared_task
from django.utils import timezone


@shared_task
def heartbeat(sent_at=None):
    """Signe de vie : envoyé par le planificateur (Celery beat), exécuté par un worker.

    La page « État de l'installation » en déduit que le planificateur ET un worker fonctionnent.
    """
    from .models import ServiceCheck

    ServiceCheck.record("planificateur", True, "Signe de vie reçu.", sent_at=sent_at or "",
                        received_at=timezone.now().isoformat())
