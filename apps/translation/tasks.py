"""
Tâches Celery du module de traduction, routées vers la file « traduction » (décision E5).

Une exécution traite UN paquet puis se relance : une longue traduction ne bloque donc pas le worker
partagé avec les synchronisations, les imports et les exports. La progression est enregistrée en base
(aucun stockage de résultats Celery). En mode « eager » (tests, ou absence de Redis), les paquets sont
traités en boucle dans le même appel.
"""
from celery import shared_task
from django.conf import settings


@shared_task
def run_translation_job(job_id):
    from .services import run_job_safely

    if settings.CELERY_TASK_ALWAYS_EAGER:
        while run_job_safely(job_id):
            pass
        return
    if run_job_safely(job_id):
        run_translation_job.delay(job_id)
