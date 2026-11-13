import os

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.models import AppSettings
from apps.core.permissions import admin_required

from .models import BackupJob
from .services import create_backup, restore_backup, verify_backup


@admin_required
def backup_list(request):
    return render(request, "backups/list.html", {
        "jobs": BackupJob.objects.all()[:50], "settings_obj": AppSettings.get(),
        "backup_dir": settings.BACKUP_DIR, "external": settings.BACKUP_EXTERNAL_DIR,
    })


@admin_required
@require_POST
def backup_create(request):
    kind = request.POST.get("kind", "full")
    job = create_backup(kind if kind in ("full", "db", "files") else "full", user=request.user)
    log_action(request, "backup.create", job, job.message)
    (messages.success if job.status == "done" else messages.error)(request, job.message)
    return redirect("backups:list")


@admin_required
@require_POST
def backup_verify(request, pk):
    job = get_object_or_404(BackupJob, pk=pk)
    ok, msg = verify_backup(job)
    (messages.success if ok else messages.error)(request, msg)
    return redirect("backups:list")


@admin_required
def backup_download(request, pk):
    job = get_object_or_404(BackupJob, pk=pk, status="done")
    if not job.path or not os.path.exists(job.path):
        raise Http404
    log_action(request, "backup.download", job)
    return FileResponse(open(job.path, "rb"), as_attachment=True, filename=os.path.basename(job.path))


@admin_required
@require_POST
def backup_restore(request, pk):
    job = get_object_or_404(BackupJob, pk=pk, status="done")
    if request.POST.get("confirmation", "").strip() != "RESTAURER":
        messages.error(request, "Tapez RESTAURER pour confirmer la restauration.")
        return redirect("backups:list")
    safety = create_backup("full", user=request.user)
    try:
        log = restore_backup(job.path)
    except Exception as exc:
        messages.error(request, f"Restauration impossible : {exc}. Sauvegarde de sécurité : {safety.path}")
        return redirect("backups:list")
    messages.success(request, " ".join(log) + f" Une sauvegarde de sécurité a été créée avant restauration : {safety.path}. "
                                              "Reconnectez-vous si nécessaire.")
    return redirect("backups:list")
