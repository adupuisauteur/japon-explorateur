"""Projets de traduction : liste, création, modification, page du projet, suppression, copie d'une notice."""
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Record
from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from .. import projects as P
from ..forms import ProjectForm
from ..models import TranslationProject
from ..permissions import (can_edit_project, can_view_project, can_view_project_metadata, projects_metadata_only_for,
                           projects_with_content_for, require)


def _annotated(qs):
    return qs.select_related("owner").annotate(
        n_docs=Count("documents", distinct=True), n_segments=Count("documents__segments", distinct=True),
        n_validated=Count("documents__segments", filter=Q(documents__segments__state="validated"), distinct=True))


def get_project_for(request, pk, *, edit=False):
    """Projet dont l'utilisateur peut voir (ou modifier) le contenu ; 404 sinon (l'existence n'est pas révélée)."""
    project = get_object_or_404(TranslationProject.objects.select_related("owner"), pk=pk)
    allowed = can_edit_project(request.user, project) if edit else can_view_project(request.user, project)
    if not allowed:
        raise Http404
    return project


@researcher_required
def project_list(request):
    visible = projects_with_content_for(request.user)
    return render(request, "translation/project_list.html", {
        "mine": _annotated(visible.filter(owner=request.user)),
        "others": _annotated(visible.exclude(owner=request.user)),
        "hidden": _annotated(projects_metadata_only_for(request.user)),
    })


@researcher_required
def project_create(request):
    form = ProjectForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        log_action(request, "translation.project_created", project,
                   f"Projet « {project.title} »{' (confidentiel)' if project.confidential else ''}")
        messages.success(request, "Projet créé. Ajoutez maintenant un document.")
        return redirect("translation:project_detail", pk=project.pk)
    return render(request, "translation/project_form.html", {"form": form, "project": None})


@researcher_required
def project_edit(request, pk):
    project = get_project_for(request, pk, edit=True)
    form = ProjectForm(request.POST or None, instance=project, user=project.owner)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "translation.project_updated", project, f"Projet « {project.title} »")
        messages.success(request, "Projet enregistré.")
        return redirect("translation:project_detail", pk=project.pk)
    return render(request, "translation/project_form.html", {"form": form, "project": project})


@researcher_required
def project_detail(request, pk):
    project = get_object_or_404(TranslationProject.objects.select_related("owner", "collection"), pk=pk)
    if not can_view_project(request.user, project):
        if can_view_project_metadata(request.user, project):
            # Décision D3 : projet confidentiel d'un autre compte → titre, propriétaire, taille seulement.
            meta = _annotated(TranslationProject.objects.filter(pk=project.pk)).get()
            return render(request, "translation/project_metadata.html", {"project": meta})
        raise Http404
    documents = project.documents.annotate(
        n_segments=Count("segments", distinct=True),
        n_validated=Count("segments", filter=Q(segments__state="validated"), distinct=True),
        n_alert=Count("segments", filter=Q(segments__state="alert"), distinct=True))
    from .. import glossary as G
    from .glossaries import linkable_glossaries

    can_edit = can_edit_project(request.user, project)
    return render(request, "translation/project_detail.html", {
        "project": project, "documents": documents, "jobs": project.jobs.filter(user=request.user)[:10],
        "can_edit": can_edit,
        "glossary_links": project.glossary_links.select_related("glossary").annotate(n_entries=Count("glossary__entries")),
        "linkable": linkable_glossaries(request, project) if can_edit else [],
        "contradictions": G.project_contradictions(project),
    })


@researcher_required
@require_POST
def project_delete(request, pk):
    project = get_object_or_404(TranslationProject, pk=pk, owner=request.user)  # propriétaire seulement
    if request.POST.get("confirm_title", "").strip() != project.title.strip():
        messages.error(request, "Pour supprimer le projet, recopiez exactement son titre.")
        return redirect("translation:project_detail", pk=project.pk)
    title = project.title
    log_action(request, "translation.project_deleted", project, f"Projet « {title} » supprimé")
    project.delete()
    messages.info(request, f"Projet « {title} » supprimé avec ses documents et traductions.")
    return redirect("translation:project_list")


@researcher_required
@require_POST
def copy_record(request, record_id):
    """Décision D2 : copie le texte d'une notice dans un projet (documents), sans contenu éditorial automatique."""
    record = get_object_or_404(Record, record_id=record_id)
    project = get_project_for(request, request.POST.get("project"), edit=True)
    fields = [f for f in request.POST.getlist("fields") if f] or ["original_title", "description_original"]
    try:
        documents = P.copy_record_to_project(record, project, fields)
    except P.ProjectError as exc:
        messages.error(request, str(exc))
        return redirect("translation:record_translations", record_id=record.record_id)
    messages.success(request, f"{len(documents)} document(s) créé(s) dans « {project.title} ».")
    return redirect("translation:document_workbench", pk=documents[0].pk)


def require_edit(request, project):
    require(can_edit_project(request.user, project))
