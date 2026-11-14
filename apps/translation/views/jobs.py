"""Tâches de traduction : confirmation, suivi (HTMX), annulation, reprise, relance des échecs, deuxième moteur."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from .. import services
from ..models import TranslationJob


def _own_job(request, pk):
    # Une tâche n'est visible que par son auteur (elle peut citer un projet confidentiel).
    # Les installations de paquets Argos ont leur propre page (Traduction → Moteurs locaux).
    return get_object_or_404(TranslationJob.objects.select_related("project").exclude(kind="package"), pk=pk,
                             user=request.user)


@researcher_required
def job_list(request):
    jobs = TranslationJob.objects.filter(user=request.user).exclude(kind="package").select_related("project")[:200]
    return render(request, "translation/job_list.html", {
        "jobs": [(job, services.is_stale(job), services.engine_label(job)) for job in jobs]})


@researcher_required
def job_detail(request, pk):
    job = _own_job(request, pk)
    items = job.items.select_related("segment", "record", "version", "editorial").order_by("position")[:500]
    context = {"job": job, "items": items, "stale": services.is_stale(job), "engine_label": services.engine_label(job),
               "polling": job.status in ("confirmed", "running") and not services.is_stale(job)}
    if job.status == "draft":
        context["summary"] = services.summary(job)
    if request.headers.get("HX-Request"):
        return render(request, "translation/_job_status.html", context)
    return render(request, "translation/job_detail.html", context)


@researcher_required
@require_POST
def job_action(request, pk):
    job = _own_job(request, pk)
    action = request.POST.get("action", "")
    try:
        if action == "confirm":
            services.confirm(job, request.user, second_confirmation=bool(request.POST.get("second_confirmation")),
                             terms_acknowledged=bool(request.POST.get("terms_acknowledged")))
            log_action(request, "translation.job_confirmed", job,
                       f"{services.engine_label(job)} : {job.chars_estimated} caractère(s) prévus")
            messages.success(request, "Traduction lancée.")
        elif action == "cancel":
            services.cancel(job, request.user)
            messages.info(request, "Tâche annulée." + (" Rien n'a été envoyé." if not job.chars_sent else ""))
        elif action == "resume":
            services.resume(job, request.user)
            messages.success(request, "Reprise lancée : seuls les éléments non traduits seront envoyés.")
        elif action == "retry":
            services.retry_failed(job, request.user)
            messages.success(request, "Relance des éléments en échec.")
        elif action == "second":
            new = services.propose_second_engine(job, request.user)
            messages.info(request, "Nouvelle tâche préparée avec le deuxième moteur : vérifiez-la, puis confirmez.")
            return redirect("translation:job_detail", pk=new.pk)
    except services.TranslationUnavailable as exc:
        messages.error(request, str(exc))
    return redirect("translation:job_detail", pk=job.pk)
