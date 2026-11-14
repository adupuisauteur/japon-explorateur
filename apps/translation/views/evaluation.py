"""Traduction → Évaluation : corpus de référence, comparaison des moteurs, notation humaine (lot 10)."""
from urllib.parse import quote, unquote

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.ai.models import PROVIDERS as AI_PROVIDERS
from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from .. import evaluation as E
from .. import services
from ..models import ENGINES, RATINGS, TranslationProject, TranslationVersion


def _corpus(request, pk):
    project = get_object_or_404(TranslationProject, pk=pk, owner=request.user)  # propriétaire seulement
    if not project.is_reference_corpus:
        raise Http404
    return project


@researcher_required
def evaluation_home(request):
    corpora = E.corpus_projects(request.user)
    return render(request, "translation/evaluation.html", {
        "corpora": [(p, E.comparisons(request.user, p)[:5], len(E.corpus_segments(p))) for p in corpora],
        "engines": [(code, label) for code, label in ENGINES if code != "ai"], "ai_providers": AI_PROVIDERS,
        "pref": services.ensure_preference(request.user),
    })


def _choices(request):
    choices = [services.EngineChoice(code) for code in request.POST.getlist("engines") if code in dict(ENGINES)
               and code != "ai"]
    for i in (1, 2):
        provider, model = request.POST.get(f"ai_provider_{i}", ""), request.POST.get(f"ai_model_{i}", "").strip()
        if provider and model and provider in dict(AI_PROVIDERS):
            choices.append(services.EngineChoice("ai", provider, model))
    return choices


@researcher_required
@require_POST
def comparison_prepare(request, pk):
    project = _corpus(request, pk)
    try:
        label, jobs, errors = E.prepare_comparison(request.user, project, _choices(request))
    except E.EvaluationError as exc:
        messages.error(request, str(exc))
        return redirect("translation:evaluation")
    for choice, error in errors:
        messages.warning(request, f"{choice.engine(request.user).display_name} écarté : {error}")
    if not jobs:
        messages.error(request, "Aucun moteur utilisable : rien n'a été préparé.")
        return redirect("translation:evaluation")
    return redirect(_comparison_url(project, label))


def _comparison_url(project, label):
    return reverse("translation:comparison", args=[project.pk]) + "?c=" + quote(label)


@researcher_required
def comparison(request, pk):
    project = _corpus(request, pk)
    label = unquote(request.GET.get("c", ""))
    jobs = E.comparison_jobs(request.user, project, label)
    if not jobs:
        raise Http404
    drafts = [j for j in jobs if j.status == "draft"]
    return render(request, "translation/comparison.html", {
        "project": project, "label": label, "jobs": jobs, "rows": E.rows(jobs), "summary": E.rating_summary(jobs),
        "drafts": [(j, services.summary(j), services.engine_label(j)) for j in drafts],
        "needs_second": any(j.requires_second_confirmation for j in drafts),
        "ratings": RATINGS, "columns": [(j, services.engine_label(j)) for j in jobs],
        "running": any(j.status in ("confirmed", "running") and not services.is_stale(j) for j in jobs),
        "url": _comparison_url(project, label),
    })


@researcher_required
@require_POST
def comparison_action(request, pk):
    project = _corpus(request, pk)
    label = request.POST.get("c", "")
    jobs = E.comparison_jobs(request.user, project, label)
    if not jobs:
        raise Http404
    action = request.POST.get("action")
    if action == "confirm":
        started, errors = E.confirm_all(jobs, request.user,
                                        second_confirmation=bool(request.POST.get("second_confirmation")))
        for job in started:
            log_action(request, "translation.job_confirmed", job,
                       f"Comparaison sur le corpus — {services.engine_label(job)} : {job.chars_estimated} caractère(s)")
        for job, error in errors:
            messages.error(request, f"{services.engine_label(job)} : {error}")
        if started:
            messages.success(request, f"{len(started)} traduction(s) du corpus lancée(s).")
    elif action == "cancel":
        for job in jobs:
            if job.status == "draft":
                services.cancel(job, request.user)
        messages.info(request, "Moteurs non lancés annulés : rien ne leur a été envoyé.")
    return redirect(_comparison_url(project, label))


@researcher_required
@require_POST
def version_rate(request, pk):
    version = get_object_or_404(TranslationVersion.objects.select_related("segment__document__project"), pk=pk)
    project = version.segment.document.project
    if project.owner_id != request.user.pk:
        raise Http404
    try:
        E.rate(version, request.user, request.POST.get("rating", ""), request.POST.get("comment", ""))
    except E.EvaluationError as exc:
        messages.error(request, str(exc))
    back = request.POST.get("next", "")
    return redirect(back if back.startswith("/traduction/") else "translation:evaluation")
