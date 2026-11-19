"""Tâches de fond du catalogue (2.0.0, lot 2) : vérification des manifestes IIIF demandés."""
from celery import shared_task


@shared_task
def verify_iiif_pending():
    """Traite les vérifications IIIF en attente (demandées par l'utilisateur ; reprise après un arrêt)."""
    from .iiif import run_pending

    return run_pending()
