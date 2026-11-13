from celery import shared_task


@shared_task
def generate_export(job_id):
    from .models import ExportJob
    from .services import generate

    job = ExportJob.objects.filter(pk=job_id).first()
    if job and job.status in ("pending", "failed"):
        generate(job)
