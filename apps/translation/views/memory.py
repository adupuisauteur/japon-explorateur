"""Mémoire de traduction (décision E7) : consultation, recherche et exclusion des paires validées.

Chaque compte ne voit QUE sa propre mémoire (versions validées de ses projets), administrateur compris :
la mémoire ne fait jamais circuler un texte d'un compte à un autre.
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from ..models import TranslationVersion


def memory_queryset(user):
    return (TranslationVersion.objects.filter(status="validated", segment__document__project__owner=user)
            .select_related("segment__document__project", "decided_by"))


@researcher_required
def memory_list(request):
    qs = memory_queryset(request.user)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(segment__source_text__icontains=q) | Q(text__icontains=q))
    state = request.GET.get("etat", "")
    if state == "exclues":
        qs = qs.filter(excluded_from_memory=True)
    elif state == "actives":
        qs = qs.filter(excluded_from_memory=False)
    project = request.GET.get("projet", "")
    if project.isdigit():
        qs = qs.filter(segment__document__project_id=int(project))
    page = Paginator(qs.order_by("-decided_at", "-pk"), 50).get_page(request.GET.get("page"))
    mine = memory_queryset(request.user)
    projects = (request.user.translation_projects.filter(documents__segments__versions__status="validated")
                .distinct().order_by("title"))
    return render(request, "translation/memory.html", {
        "page": page, "q": q, "state": state, "project": project, "projects": projects,
        "n_total": mine.count(), "n_excluded": mine.filter(excluded_from_memory=True).count(),
    })


@researcher_required
@require_POST
def memory_toggle(request, pk):
    version = get_object_or_404(memory_queryset(request.user), pk=pk)
    version.excluded_from_memory = request.POST.get("action") == "exclude"
    version.save(update_fields=["excluded_from_memory"])
    log_action(request, "translation.memory_" + ("excluded" if version.excluded_from_memory else "included"), version,
               f"Version validée n° {version.pk}")
    messages.success(request, "Paire exclue de la mémoire : elle ne sera plus proposée." if version.excluded_from_memory
                     else "Paire réintégrée dans la mémoire.")
    back = request.POST.get("next", "")
    return redirect(back if back.startswith("/traduction/memoire/") else "translation:memory")
