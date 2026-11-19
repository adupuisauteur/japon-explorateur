"""Exports du module (décision E4) : rangés par projet, réservés à son propriétaire, produits à la demande."""
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.text import slugify

from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from .. import exports as X
from ..models import Glossary, TranslationProject
from ..permissions import can_validate_project


def _own_project(request, pk):
    project = get_object_or_404(TranslationProject.objects.select_related("owner"), pk=pk)
    if not can_validate_project(request.user, project):  # propriétaire seulement (E4)
        raise Http404
    return project


@researcher_required
def exports_home(request):
    projects = (TranslationProject.objects.filter(owner=request.user)
                .annotate(n_docs=Count("documents", distinct=True),
                          n_segments=Count("documents__segments", distinct=True),
                          n_validated=Count("documents__segments", filter=Q(documents__segments__state="validated"),
                                            distinct=True)))
    glossaries = Glossary.objects.filter(owner=request.user).annotate(n_entries=Count("entries"))
    return render(request, "translation/exports_home.html", {"projects": projects, "glossaries": glossaries})


@researcher_required
def project_export(request, pk):
    project = _own_project(request, pk)
    documents = list(project.documents.order_by("order", "pk"))
    fmt = request.GET.get("format", "")
    mode = request.GET.get("mode", "validated")
    document = None
    if request.GET.get("document"):
        document = next((d for d in documents if str(d.pk) == request.GET["document"]), None)
        if document is None:
            raise Http404
    if fmt:
        try:
            produced_by = "" if request.GET.get("sans_identifiant") else request.user.get_username()
            content, mime, ext, data = X.render(project, fmt, document=document, mode=mode, produced_by=produced_by)
        except X.ExportError as exc:
            return render(request, "translation/project_export.html", {
                "project": project, "documents": documents, "formats": X.FORMATS, "modes": X.MODES,
                "error": str(exc)}, status=400)
        base = slugify(data.title, allow_unicode=True)[:80] or f"projet-{project.pk}"
        name = f"traduction-{base}-{'validees' if mode == 'validated' else 'avec-propositions'}-" \
               f"{timezone.localdate():%Y%m%d}.{ext}"
        log_action(request, "translation.exported", project,
                   f"Export {X.FORMATS[fmt][0]} — {X.MODES[mode]}"
                   + (f" — document n° {document.pk}" if document else " — projet entier"))
        response = HttpResponse(content, content_type=mime)
        response["Content-Disposition"] = content_disposition_header(True, name)
        return response
    preview = {"fallback": X.collect(project, mode="fallback")}
    return render(request, "translation/project_export.html", {
        "project": project, "documents": documents, "formats": X.FORMATS, "modes": X.MODES, "preview": preview,
    })
