"""2.0.0 (lot 4) : résumés IA — demande (maintenant ou file de nuit), consultation, historique ; textes anciens."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.ai.models import SUMMARY_KINDS, SUMMARY_LANGUAGES, Summary
from apps.catalog.models import Record
from apps.core.audit import log_action
from apps.core.permissions import researcher_required
from apps.core.redirects import safe_next

from .. import services
from .. import summaries as S
from .. import variety as V
from ..models import VARIETIES, TranslationDocument
from ..permissions import can_edit_project, can_view_project


def _ids(raw):
    return [x.strip() for x in (raw or "").replace("\n", ",").split(",") if x.strip()]


def start(request, *, records=(), documents=(), mode="now", back):
    """Prépare la (les) tâche(s) ; « maintenant » sans confirmation si l'IA est locale ou sous le seuil choisi."""
    try:
        jobs = S.prepare(request.user, records=records, documents=documents, kind=request.POST.get("kind"),
                         language=request.POST.get("language"), source=request.POST.get("source", "original"),
                         launch="now" if mode == "now" else "immediate")
    except S.SummaryUnavailable as exc:
        messages.error(request, str(exc))
        return redirect(back)
    job = jobs[0]
    log_action(request, "summary.prepared", job, job.scope_label)
    if mode == "now" and S.now_allowed(job):
        services.confirm(job, request.user, launch="now")
        log_action(request, "translation.job_confirmed", job, f"{S.engine_label(job)} : maintenant")
        messages.success(request, "Résumé lancé : il s'affiche ici dès qu'il est prêt ; une fenêtre vous prévient si "
                                  "vous avez changé de page.")
        return redirect(back)
    return redirect(reverse("translation:job_detail", args=[job.pk]) + ("?lancement=nuit" if mode == "night" else ""))


@researcher_required
@require_POST
def summarize(request):
    mode = "night" if request.POST.get("mode") == "night" else "now"
    back = safe_next(request, reverse("library:index"))
    records = list(Record.objects.filter(record_id__in=_ids(request.POST.get("records"))))
    documents = []
    for pk in _ids(request.POST.get("documents")):
        document = TranslationDocument.objects.select_related("project").filter(pk=pk).first()
        if document is None or not can_edit_project(request.user, document.project):
            raise PermissionDenied
        documents.append(document)
    return start(request, records=records, documents=documents, mode=mode, back=back)


@researcher_required
def summary_detail(request, pk):
    summary = get_object_or_404(Summary.objects.select_related("record", "document__project", "job"), pk=pk)
    if summary.document_id and not can_view_project(request.user, summary.document.project):
        raise PermissionDenied
    return render(request, "translation/summary_detail.html", {"summary": summary, "history": summary.history()})


@researcher_required
def summary_list(request):
    kind, language = request.GET.get("type", ""), request.GET.get("langue", "")
    qs = Summary.objects.select_related("record", "document__project").order_by("-created_at")
    if kind in dict(SUMMARY_KINDS):
        qs = qs.filter(kind=kind)
    if language in dict(SUMMARY_LANGUAGES):
        qs = qs.filter(language=language)
    rows = [s for s in qs[:2000] if not s.document_id or can_view_project(request.user, s.document.project)]
    return render(request, "translation/summary_list.html", {
        "page": Paginator(rows, 50).get_page(request.GET.get("page")), "kinds": SUMMARY_KINDS,
        "languages": SUMMARY_LANGUAGES, "kind": kind, "language": language})


@researcher_required
@require_POST
def record_variety(request, record_id):
    """U10 : confirmer ou corriger la variété de langue d'une notice (la suggestion n'est jamais sûre)."""
    record = get_object_or_404(Record, record_id=record_id)
    variety = request.POST.get("variety", "")
    if variety not in dict(VARIETIES):
        messages.error(request, "Variété inconnue.")
    else:
        V.confirm_record(record, variety, request.user)
        log_action(request, "translation.variety_confirmed", record, dict(VARIETIES)[variety])
        messages.success(request, f"Notice marquée « {dict(VARIETIES)[variety]} ».")
    return redirect(safe_next(request, record.get_absolute_url()))


@researcher_required
@require_POST
def document_variety(request, pk):
    document = get_object_or_404(TranslationDocument.objects.select_related("project"), pk=pk)
    if not can_edit_project(request.user, document.project):
        raise PermissionDenied
    variety = request.POST.get("variety", "")
    if variety in dict(VARIETIES):
        document.variety = variety
        document.save(update_fields=["variety", "updated_at"])
        log_action(request, "translation.variety_confirmed", document, dict(VARIETIES)[variety])
        messages.success(request, f"Document marqué « {dict(VARIETIES)[variety]} ».")
    return redirect("translation:document_workbench", pk=document.pk)
