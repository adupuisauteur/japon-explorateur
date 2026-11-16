"""Traduction → Moteurs locaux : état du service Argos et gestion de ses paquets de langues (lot 9)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import admin_required, researcher_required

from apps.core.models import ServiceCheck

from .. import argos_packages as A
from ..argos_selftest import CHECK_NAME
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
        "invite": A.invite(request.user, health, problem), "memory_warning": A.memory_warning(health),
        "selftest": ServiceCheck.objects.filter(name=CHECK_NAME).first(),
        **_local_ai_context(),
    })


def _local_ai_context():
    """2.0.0 (lot 4, U8) : IA locale facultative (Ollama) pour les résumés et la traduction par IA."""
    from apps.ai import local

    configured = bool(local.base_url())
    state, problem = local.health() if configured else (None, "")
    names = local.installed(state) if state else []
    sizes = {m["name"]: m["size"] for m in (state or {}).get("models", [])}
    catalogue = [{**m, "installed": m["model"] in names} for m in local.CATALOGUE]
    others = [{"model": n, "bytes": sizes.get(n, 0)} for n in names if n not in [m["model"] for m in local.CATALOGUE]]
    return {"ollama": {"configured": configured, "state": state, "problem": problem, "catalogue": catalogue,
                       "others": others, "installed": names, "selftest": local.last_selftest()}}


def _model_from(request):
    from apps.ai import local

    model = request.POST.get("model", "")
    if local.entry(model) is None and model not in local.installed():
        messages.error(request, "Modèle inconnu.")
        return None
    return model


@admin_required
@require_POST
def ollama_install(request):
    """Téléchargement d'un modèle choisi dans la courte liste, après affichage de sa taille et confirmation."""
    from apps.ai import local

    model = _model_from(request)
    back = reverse("translation:local_engines") + "#ia-locale"
    if model is None:
        return redirect(back)
    item = local.entry(model)
    if not request.POST.get("confirm"):
        messages.error(request, f"Cochez la case de confirmation : le modèle {model} ({item['size'] if item else '?'})"
                                " sera téléchargé depuis Internet.")
        return redirect(back)
    try:
        job = local.prepare_install(request.user, model)
    except local.LocalAIError as exc:
        messages.error(request, str(exc))
        return redirect(back)
    log_action(request, "ai.local_model_download", job, job.scope_label)
    A.dispatch(job)
    messages.success(request, "Téléchargement lancé : suivez la progression dans « Installations récentes ». Un "
                              "résumé d'essai sera fait à la fin ; vous pouvez continuer à travailler en attendant.")
    return redirect(reverse("translation:local_engines") + "#argos-jobs")


@admin_required
@require_POST
def ollama_test(request):
    from apps.ai import local

    model = _model_from(request)
    if model is not None:
        check = local.run_selftest(request.user, model)
        (messages.success if check.ok else messages.error)(request, check.message)
    return redirect(reverse("translation:local_engines") + "#ia-locale")


@admin_required
@require_POST
def ollama_remove(request):
    """Suppression d'un modèle installé (sur confirmation) : libère la place sur le disque, rien d'autre."""
    from apps.ai import local

    model = _model_from(request)
    if model is not None:
        if not request.POST.get("confirm"):
            messages.error(request, "Cochez la case de confirmation pour supprimer ce modèle.")
        else:
            try:
                local.remove(model)
                log_action(request, "ai.local_model_removed", None, model)
                messages.success(request, f"Modèle {model} supprimé de l'IA locale.")
            except (RuntimeError, Exception) as exc:  # noqa: BLE001 — erreur du service affichée telle quelle
                messages.error(request, f"Suppression impossible : {exc}")
    return redirect(reverse("translation:local_engines") + "#ia-locale")


@admin_required
@require_POST
def argos_install_ja_fr(request):
    """Bouton unique (2.0.0, lot 7) : paquets ja→en et en→fr, après affichage de la taille et confirmation."""
    if not request.POST.get("confirm"):
        messages.error(request, f"Cochez la case de confirmation : les paquets ({A.JA_FR_SIZE}) seront "
                                "téléchargés depuis Internet.")
        return redirect("translation:local_engines")
    try:
        job = A.prepare_ja_fr(request.user)
    except A.PackageError as exc:
        messages.error(request, str(exc))
        return redirect("translation:local_engines")
    if job is None:
        from ..argos_selftest import run_selftest

        check = run_selftest()
        (messages.success if check.ok else messages.error)(
            request, f"La traduction japonais → français est déjà installée. Essai : {check.message}")
        return redirect("translation:local_engines")
    log_action(request, "translation.argos_download", job, job.scope_label)
    A.dispatch(job)
    messages.success(request, "Installation lancée : suivez la progression ci-dessous. Une traduction d'essai "
                              "sera faite à la fin ; vous pouvez continuer à travailler en attendant.")
    return redirect(reverse("translation:local_engines") + "#argos-jobs")


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
