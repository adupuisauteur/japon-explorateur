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
        # 2.0.0 (lot 3) : le paquet suivant reste dans la file de la tâche (« maintenant » ou « traduction »)
        from .models import TranslationJob
        from .queue import queue_for

        job = TranslationJob.objects.filter(pk=job_id).first()
        if job is not None:
            run_translation_job.apply_async(args=[job_id], queue=queue_for(job))


@shared_task
def clock():
    """2.0.0 (lot 3) : horloge des tâches, chaque minute (tâches programmées, file de nuit, compte rendu)."""
    from .queue import clock as run_clock

    return run_clock()


@shared_task
def run_package_job(job_id):
    """Installation de paquets Argos (téléchargement compris) : une seule exécution, suivie en base."""
    from .argos_packages import run_safely

    run_safely(job_id)


@shared_task
def auto_argos_selftest(attempt=1):
    """2.0.0 (lot 3) : essai automatique d'Argos, programmé au démarrage du planificateur (config/celery.py)."""
    from django.conf import settings

    from .argos_selftest import auto_selftest

    result = auto_selftest(attempt)
    if result == "attente":
        auto_argos_selftest.apply_async(args=[attempt + 1], countdown=settings.ARGOS_AUTO_SELFTEST_DELAY)
    return result


@shared_task
def auto_local_ai_selftest(attempt=1):
    """2.0.0 (lot 6) : essai automatique de l'IA locale au démarrage, comme pour Argos."""
    from django.conf import settings

    from apps.ai.local import auto_selftest

    result = auto_selftest(attempt)
    if result == "attente":
        auto_local_ai_selftest.apply_async(args=[attempt + 1], countdown=settings.ARGOS_AUTO_SELFTEST_DELAY)
    return result


@shared_task
def run_argos_selftest():
    """Test de démarrage d'Argos demandé depuis la page « État de l'installation » (2.0.0)."""
    from .argos_selftest import run_selftest

    run_selftest()
