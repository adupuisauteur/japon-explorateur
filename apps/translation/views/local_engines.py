"""Traduction → Moteurs locaux : état du service Argos et gestion de ses paquets de langues (lot 9)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import admin_required, researcher_required

from .. import argos_packages as A
from ..engines.base import TranslationEngineError
from ..models import TranslationJob


@researcher_required
def local_engines(request):
    health, problem = A.service_state(request.user)
    jobs = TranslationJob.objects.filter(kind="package").select_related("user").order_by("-created_at")[:10]
    return render(request, "translation/local_engines.html", {
        "health": health, "problem": problem, "needed": A.needed_status(health),
        "jobs": [(j, A.is_stale(j)) for j in jobs], "can_manage": request.user.is_admin_role,
        "running": any(j.status in ("confirmed", "running") and not A.is_stale(j) for j in jobs),
    })


@admin_required
@require_POST
def argos_index(request):
    """Consulter l'index Argos : le service interroge Internet (aucun paquet n'est téléchargé à ce stade)."""
    health, problem = A.service_state(request.user)
    if health is None:
        messages.error(request, problem)
        return redirect("translation:local_engines")
    try:
        available = A.index_packages()
    except TranslationEngineError as exc:
        messages.error(request, f"Index Argos : {exc}")
        return redirect("translation:local_engines")
    installed = {f"{p.get('from')}→{p.get('to')}": p for p in health.get("packages") or []}
    needed = {p["code"] for row in A.needed_status(health) for p in row["packages"]}
    rows = [{**p, "code": f"{p.get('from')}→{p.get('to')}", "installed": installed.get(f"{p.get('from')}→{p.get('to')}"),
             "needed": f"{p.get('from')}→{p.get('to')}" in needed} for p in available]
    rows.sort(key=lambda r: (not r["needed"], r["code"]))
    return render(request, "translation/argos_index.html", {"rows": rows})


@admin_required
@require_POST
def argos_install(request):
    if not request.POST.get("confirm"):
        messages.error(request, "Cochez la case de confirmation : les paquets seront téléchargés depuis Internet.")
        return redirect("translation:local_engines")
    try:
        job = A.prepare_index_install(request.user, request.POST.getlist("packages"))
    except A.PackageError as exc:
        messages.error(request, str(exc))
        return redirect("translation:local_engines")
    log_action(request, "translation.argos_download", job, job.scope_label)
    A.dispatch(job)
    messages.success(request, "Téléchargement lancé : suivez la progression ci-dessous.")
    return redirect("translation:local_engines")


@admin_required
@require_POST
def argos_install_file(request):
    uploaded = request.FILES.get("file")
    if uploaded is None:
        messages.error(request, "Choisissez un fichier .argosmodel.")
        return redirect("translation:local_engines")
    try:
        job = A.prepare_file_install(request.user, uploaded)
    except A.PackageError as exc:
        messages.error(request, str(exc))
        return redirect("translation:local_engines")
    log_action(request, "translation.argos_install_file", job, job.scope_label)
    A.dispatch(job)
    messages.success(request, "Installation lancée : suivez la progression ci-dessous.")
    return redirect("translation:local_engines")


@admin_required
@require_POST
def argos_install_sbd(request):
    if not request.POST.get("confirm"):
        messages.error(request, "Cochez la case de confirmation : le modèle sera téléchargé depuis Internet.")
        return redirect("translation:local_engines")
    try:
        job = A.prepare_sbd_install(request.user, request.POST.get("package", ""))
    except A.PackageError as exc:
        messages.error(request, str(exc))
        return redirect("translation:local_engines")
    log_action(request, "translation.argos_download", job, job.scope_label)
    A.dispatch(job)
    messages.success(request, "Téléchargement lancé : suivez la progression ci-dessous.")
    return redirect("translation:local_engines")


@admin_required
@require_POST
def argos_remove(request):
    code = request.POST.get("package", "")
    try:
        A.remove(code)
        log_action(request, "translation.argos_removed", None, f"Paquet Argos {code} désinstallé")
        messages.success(request, f"Paquet {code} désinstallé.")
    except (A.PackageError, TranslationEngineError) as exc:
        messages.error(request, str(exc))
    return redirect("translation:local_engines")


@admin_required
@require_POST
def argos_job_action(request, pk):
    job = get_object_or_404(TranslationJob, pk=pk, kind="package")
    action = request.POST.get("action")
    try:
        if action == "relaunch":
            A.relaunch(job)
            messages.success(request, "Reprise lancée : les paquets déjà installés ne sont pas téléchargés à nouveau.")
        elif action == "cancel" and job.status in ("confirmed", "running", "failed"):
            job.status = "cancelled"
            job.save(update_fields=["status"])
            messages.info(request, "Tâche annulée (un téléchargement déjà commencé par le service se termine).")
    except A.PackageError as exc:
        messages.error(request, str(exc))
    return redirect("translation:local_engines")
