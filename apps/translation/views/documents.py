"""
Documents et segments : ajout (collage ou fichier), écran de travail à deux colonnes, page d'un segment
(versions, comparaison, correction, validation, fusion, division, chapitre), traduction, publication.
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from .. import glossary as G
from .. import projects as P
from .. import services
from ..forms import DocumentForm
from ..importers import ImportRefused, import_file
from ..models import SEGMENT_STATES, TranslationDocument, TranslationSegment, TranslationVersion
from ..permissions import can_edit_glossary, can_edit_project, can_validate_project, can_view_project, require
from ..segmentation import is_translatable
from .projects import get_project_for


def _document(request, pk, *, edit=False):
    document = get_object_or_404(TranslationDocument.objects.select_related("project__owner", "record"), pk=pk)
    project = document.project
    if not (can_edit_project(request.user, project) if edit else can_view_project(request.user, project)):
        raise Http404
    return document


def _segment(request, pk, *, edit=False):
    segment = get_object_or_404(TranslationSegment.objects.select_related("document__project__owner", "chapter"), pk=pk)
    project = segment.document.project
    if not (can_edit_project(request.user, project) if edit else can_view_project(request.user, project)):
        raise Http404
    return segment


def _workbench_url(segment):
    return reverse("translation:document_workbench", args=[segment.document_id]) + f"#seg-{segment.pk}"


@researcher_required
def document_add(request, project_pk):
    project = get_project_for(request, project_pk, edit=True)
    form = DocumentForm(request.POST or None, request.FILES or None)
    preview = None
    if request.method == "POST" and request.POST.get("confirmed_text") is not None:
        # Deuxième étape après un encodage incertain : texte décodé revu par l'utilisateur.
        if not request.POST.get("confirm_encoding"):
            messages.error(request, "Cochez la confirmation après avoir vérifié l'aperçu.")
        else:
            document = P.create_document(
                project, title=request.POST.get("title", ""), text=request.POST["confirmed_text"],
                source_kind=request.POST.get("source_kind", "txt"), filename=request.POST.get("filename", ""),
                encoding=request.POST.get("encoding", ""), confidence="uncertain",
                variety=request.POST.get("variety", "modern"))
            return _created(request, document)
    elif request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if data.get("file"):
                imported = import_file(data["file"])
                if imported.confidence == "uncertain":
                    preview = imported
                else:
                    for note in imported.notes:
                        messages.info(request, note)
                    document = P.create_document(project, title=data["title"], text=imported.text,
                                                 source_kind=imported.kind, filename=imported.filename,
                                                 encoding=imported.encoding, confidence=imported.confidence,
                                                 variety=data["variety"])
                    return _created(request, document)
            else:
                document = P.create_document(project, title=data["title"], text=data["text"], source_kind="paste",
                                             variety=data["variety"])
                return _created(request, document)
        except (ImportRefused, P.ProjectError) as exc:
            messages.error(request, str(exc))
    return render(request, "translation/document_form.html", {"project": project, "form": form, "preview": preview,
                                                              "form_data": request.POST})


def _created(request, document):
    n = document.segments.count()
    log_action(request, "translation.document_created", document, f"{n} segment(s)")
    messages.success(request, f"Document importé et découpé en {n} segment(s). Le texte importé est conservé à "
                              "l'identique.")
    return redirect("translation:document_workbench", pk=document.pk)


@researcher_required
def document_workbench(request, pk):
    document = _document(request, pk)
    project = document.project
    segments = document.segments.select_related("chapter").prefetch_related("versions").order_by("position")
    state = request.GET.get("etat", "")
    if state in dict(SEGMENT_STATES):
        segments = segments.filter(state=state)
    chapter = request.GET.get("chapitre", "")
    if chapter.isdigit():
        segments = segments.filter(chapter_id=int(chapter))
    page = Paginator(segments, 100).get_page(request.GET.get("page"))
    rows = []
    for seg in page:
        versions = sorted(seg.versions.all(), key=lambda v: v.created_at, reverse=True)
        shown = next((v for v in versions if v.status == "validated"), None) or next(
            (v for v in versions if v.status == "proposed"), None)
        rows.append({"segment": seg, "shown": shown, "n_versions": len(versions),
                     "translatable": is_translatable(seg.source_text)})
    counts = {code: document.segments.filter(state=code).count() for code, _ in SEGMENT_STATES}
    return render(request, "translation/workbench.html", {
        "document": document, "project": project, "rows": rows, "page": page, "states": SEGMENT_STATES,
        "state": state, "chapter": chapter, "chapters": document.chapters.order_by("order"), "counts": counts,
        "total": sum(counts.values()), "can_edit": can_edit_project(request.user, project),
        "can_validate": can_validate_project(request.user, project), "notice_field": P.notice_field(document),
        "integrity": P.integrity_ok(document),
    })


@researcher_required
@require_POST
def document_bulk(request, pk):
    document = _document(request, pk, edit=True)
    project = document.project
    ids = [int(i) for i in request.POST.getlist("segments") if i.isdigit()]
    scope = request.POST.get("scope", "selected")
    segments = document.segments.order_by("position")
    if scope == "untranslated":
        segments = segments.filter(state="untranslated")
    elif scope.startswith("chapter:") and scope[8:].isdigit():
        segments = segments.filter(chapter_id=int(scope[8:]))
    else:
        segments = segments.filter(pk__in=ids)
    segments = [s for s in segments if is_translatable(s.source_text)]
    if not segments:
        messages.error(request, "Aucun segment à traiter (sélectionnez des segments).")
        return redirect("translation:document_workbench", pk=document.pk)
    action = request.POST.get("action")
    if action == "validate":
        require(can_validate_project(request.user, project))
        n = P.validate_latest_proposals(segments, request.user)
        messages.success(request, f"{n} traduction(s) validée(s).")
        return redirect("translation:document_workbench", pk=document.pk)
    which = "second" if request.POST.get("engine") == "second" else "default"
    try:
        job = services.prepare_segments_job(request.user, segments, project=project,
                                            choice=services.resolve_choice(request.user, project=project, which=which))
    except services.TranslationUnavailable as exc:
        messages.error(request, str(exc))
        return redirect("translation:document_workbench", pk=document.pk)
    return redirect("translation:job_detail", pk=job.pk)


@researcher_required
def segment_detail(request, pk):
    segment = _segment(request, pk)
    project = segment.document.project
    versions = segment.versions.select_related("author", "decided_by", "parent").order_by("-created_at")
    neighbours = TranslationSegment.objects.filter(document=segment.document,
                                                   position__in=(segment.position - 1, segment.position + 1))
    return render(request, "translation/segment_detail.html", {
        "segment": segment, "document": segment.document, "project": project, "versions": versions,
        "previous": next((s for s in neighbours if s.position < segment.position), None),
        "next": next((s for s in neighbours if s.position > segment.position), None),
        "can_edit": can_edit_project(request.user, project), "can_validate": can_validate_project(request.user, project),
        "edit_from": versions.filter(pk=request.GET.get("corriger")).first() if request.GET.get("corriger") else None,
        "terms_found": G.terms_in(segment.source_text, G.project_terms(project), project.source_lang),
        "term_glossaries": [g for g in G.project_glossaries(project) if can_edit_glossary(request.user, g)],
        "term_categories": G.GLOSSARY_CATEGORIES,
    })


@researcher_required
@require_POST
def segment_action(request, pk):
    segment = _segment(request, pk, edit=True)
    project = segment.document.project
    action = request.POST.get("action")
    try:
        if action == "translate":
            which = "second" if request.POST.get("engine") == "second" else "default"
            job = services.prepare_segments_job(request.user, [segment], project=project,
                                                choice=services.resolve_choice(request.user, project=project,
                                                                               which=which))
            return redirect("translation:job_detail", pk=job.pk)
        if action == "human":
            parent = segment.versions.filter(pk=request.POST.get("parent")).first() if request.POST.get("parent") else None
            P.add_human_version(segment, request.user, request.POST.get("text", ""), parent=parent)
            messages.success(request, "Traduction enregistrée comme nouvelle version (proposée).")
        elif action == "merge":
            P.merge_with_next(segment)
            messages.success(request, "Segments fusionnés ; le texte importé est inchangé.")
        elif action == "split":
            P.split_segment(segment, request.POST.get("first_part", ""))
            messages.success(request, "Segment divisé ; le texte importé est inchangé.")
        elif action == "chapter":
            P.start_chapter(segment, request.POST.get("title", ""))
            messages.success(request, "Chapitre créé.")
    except (P.ProjectError, services.TranslationUnavailable) as exc:
        messages.error(request, str(exc))
        return redirect("translation:segment_detail", pk=segment.pk)
    return redirect(_workbench_url(segment) if action in ("merge", "split", "chapter") else
                    reverse("translation:segment_detail", args=[segment.pk]))


@researcher_required
@require_POST
def version_action(request, pk):
    version = get_object_or_404(TranslationVersion.objects.select_related("segment__document__project"), pk=pk)
    project = version.segment.document.project
    if not can_view_project(request.user, project):
        raise Http404
    require(can_validate_project(request.user, project))  # seul le propriétaire valide (C2)
    action = request.POST.get("action")
    if action == "validate":
        P.validate_version(version, request.user)
        messages.success(request, "Version validée ; la précédente redevient proposée.")
    elif action == "reject":
        P.reject_version(version, request.user)
        messages.info(request, "Version rejetée (conservée dans l'historique).")
    return redirect("translation:segment_detail", pk=version.segment_id)


@researcher_required
@require_POST
def document_publish(request, pk):
    document = _document(request, pk, edit=True)
    require(can_validate_project(request.user, document.project))
    if not request.POST.get("confirm_publish"):
        messages.error(request, "Cochez la confirmation : la traduction publiée sera visible par tous les comptes.")
        return redirect("translation:document_workbench", pk=document.pk)
    try:
        ed = P.publish_to_record(document, request.user)
    except P.ProjectError as exc:
        messages.error(request, str(exc))
        return redirect("translation:document_workbench", pk=document.pk)
    log_action(request, "translation.published", ed,
               f"Document {document.pk} publié dans la notice (projet {'confidentiel' if document.project.confidential else 'ordinaire'})")
    messages.success(request, "Traduction publiée dans la notice comme proposition ; un administrateur peut la "
                              "valider (et l'adopter) depuis la notice.")
    return redirect("translation:record_translations", record_id=document.record.record_id)
