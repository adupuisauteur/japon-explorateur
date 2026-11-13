from celery import shared_task


@shared_task
def run_ai_task(task_id):
    from .models import AITask
    from .services import execute

    task = AITask.objects.filter(pk=task_id, status="confirmed").first()
    if task is not None:
        execute(task)


@shared_task
def purge_stale_drafts():
    from .services import purge_stale_drafts as purge

    return purge()
