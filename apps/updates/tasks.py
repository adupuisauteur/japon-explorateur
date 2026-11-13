from celery import shared_task


@shared_task
def run_sync_job(job_id):
    from .models import SyncJob
    from .services import run_sync

    job = SyncJob.objects.filter(pk=job_id, status="pending").first()
    if job:
        run_sync(job)


@shared_task
def run_due_syncs():
    """Lancé chaque heure par Celery beat : crée les synchronisations arrivées à échéance.

    Ne déclenche jamais de traitement IA (§11.4).
    """
    from .models import SyncJob
    from .services import due_catalogues, run_sync

    for catalogue in due_catalogues():
        if SyncJob.objects.filter(catalogue=catalogue, status__in=["pending", "running"]).exists():
            continue
        job = SyncJob.objects.create(catalogue=catalogue, kind="incremental", scheduled=True)
        run_sync(job)


@shared_task
def stage_import_job(job_id, generate_ids=False):
    from .models import ImportJob
    from .services import stage_import

    job = ImportJob.objects.get(pk=job_id)
    stage_import(job, generate_ids=generate_ids)
