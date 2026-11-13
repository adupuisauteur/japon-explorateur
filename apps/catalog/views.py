from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.redirects import safe_next
from apps.core.permissions import admin_required, researcher_required

from .models import EditorialContent, Record, RecordLink, RecordVersion, Work
from .services import propose_duplicate_links, record_editorial_change, set_record_status


def _record_context(request, record):
    from apps.ai.preferences import active_profile
    from apps.library.models import Annotation, Collection, CorrectionProposal, LibraryEntry

    profile = active_profile(request.user)
    return {
        "record": record,
        "versions": record.versions.select_related("created_by")[:20],
        "editorial": record.editorial.select_related("ai_task", "author"),
        "links": RecordLink.objects.filter(Q(record_a=record) | Q(record_b=record))
                 .select_related("record_a__catalogue", "record_b__catalogue").exclude(status="rejected"),
        "annotations": Annotation.visible_to(request.user).filter(record=record).select_related("author"),
        "entry": LibraryEntry.objects.filter(user=request.user, record=record).first(),
        "collections_in": record.collection_items.select_related("collection")
                          .filter(collection__in=Collection.visible_to(request.user)),
        "my_collections": Collection.objects.filter(owner=request.user) if request.user.can_edit else [],
        "corrections": CorrectionProposal.objects.filter(record=record).select_related("author")[:10],
        "ai_profile": profile,
        "correction_fields": CorrectionProposal.FIELDS,
    }


@login_required
def record_detail(request, record_id):
    record = get_object_or_404(Record.objects.select_related("catalogue", "work", "holding_institution"),
                               record_id=record_id)
    if record.record_status == "deleted" and not request.user.is_admin_role:
        messages.warning(request, "Cette notice est dans la corbeille.")
        return redirect("library:index")
    return render(request, "catalog/record_detail.html", _record_context(request, record))


@login_required
def record_panel(request, record_id):
    record = get_object_or_404(Record.objects.select_related("catalogue"), record_id=record_id)
    return render(request, "catalog/_record_panel.html", {"record": record})


@login_required
def version_detail(request, record_id, version):
    record = get_object_or_404(Record, record_id=record_id)
    v = get_object_or_404(RecordVersion, record=record, version=version)
    return render(request, "catalog/version_detail.html", {"record": record, "v": v})


@researcher_required
@require_POST
def translation_edit(request, record_id):
    """Traduction de la couche éditoriale, jamais la donnée source.

    Administrateur : modification directe et historisée. Chercheur : proposition de
    correction soumise à validation (§13.2 — le Chercheur ne modifie pas le fonds commun).
    """
    from apps.library.models import CorrectionProposal

    record = get_object_or_404(Record, record_id=record_id)
    changed = 0
    for field in ("translated_title", "description_translation"):
        if field in request.POST:
            new = request.POST.get(field, "").strip()
            old = getattr(record, field)
            if new == old:
                continue
            changed += 1
            if request.user.is_admin_role:
                setattr(record, field, new)
                setattr(record, f"{field}_origin", "user" if new else "")
                record_editorial_change(record, field, old, new, request.user, note="Traduction utilisateur")
            else:
                CorrectionProposal.objects.create(record=record, field=field, current_value=old, proposed_value=new,
                                                  justification=request.POST.get("justification", "").strip()
                                                  or "Traduction proposée depuis la fiche.", author=request.user)
    if not changed:
        messages.info(request, "Aucun changement.")
    elif request.user.is_admin_role:
        messages.success(request, "Traduction enregistrée (origine : utilisateur).")
    else:
        messages.success(request, "Traduction proposée : elle sera appliquée après validation par un administrateur.")
    return redirect(record.get_absolute_url())


@researcher_required
@require_POST
def editorial_decide(request, pk):
    ed = get_object_or_404(EditorialContent.objects.select_related("record"), pk=pk)
    action = request.POST.get("action")
    if action in ("validate", "reject", "adopt") and not request.user.is_admin_role:
        raise PermissionDenied("Validation et adoption réservées à l'administrateur.")
    if action in ("validate", "reject"):
        ed.status = "validated" if action == "validate" else "rejected"
        ed.save(update_fields=["status", "updated_at"])
        log_action(request, f"editorial.{action}", ed, ed.get_kind_display())
    elif action == "adopt" and ed.kind == "translation":
        record = ed.record
        field = {"original_title": "translated_title", "description_original": "description_translation"}.get(ed.target_field)
        if field:
            old = getattr(record, field)
            setattr(record, field, ed.content)
            setattr(record, f"{field}_origin", ed.origin)
            record_editorial_change(record, field, old, ed.content, request.user,
                                    note=f"Traduction adoptée ({ed.get_origin_display()})")
            ed.status = "validated"
            ed.save(update_fields=["status", "updated_at"])
    elif action == "delete" and (ed.author_id == request.user.pk or request.user.is_admin_role):
        ed.delete()
        messages.info(request, "Contenu éditorial supprimé.")
    return redirect(ed.record.get_absolute_url() + "#editoriale")


@researcher_required
@require_POST
def compute_duplicates(request, record_id):
    record = get_object_or_404(Record, record_id=record_id)
    n = propose_duplicate_links(record, request.user)
    messages.info(request, f"{n} rapprochement(s) proposé(s) par règles (identifiants, titres, auteurs, dates). "
                           "Aucune fusion n'est effectuée.")
    return redirect(record.get_absolute_url() + "#doublons")


@admin_required
@require_POST
def link_decide(request, pk):
    link = get_object_or_404(RecordLink, pk=pk)
    action = request.POST.get("action")
    if action in ("validated", "rejected"):
        link.status = action
        link.reviewed_by = request.user
        link.save(update_fields=["status", "reviewed_by"])
        if action == "validated" and request.POST.get("link_type") in dict(RecordLink.LINK_TYPES):
            link.link_type = request.POST["link_type"]
            link.save(update_fields=["link_type"])
        log_action(request, f"link.{action}", link, link.rationale[:200])
    back = safe_next(request, link.record_a.get_absolute_url())
    return redirect(back)


@admin_required
@require_POST
def record_status(request, record_id):
    record = get_object_or_404(Record, record_id=record_id)
    status = request.POST.get("status")
    if status in ("active", "unavailable", "withdrawn", "to_check", "deleted"):
        set_record_status(record, status, user=request.user, note=request.POST.get("note", ""))
        log_action(request, "record.status", record, f"{record.record_id} → {status}")
        messages.success(request, "Statut mis à jour (historisé, réversible).")
    return redirect(record.get_absolute_url())


@admin_required
def trash(request):
    page = Paginator(Record.objects.filter(record_status="deleted").select_related("catalogue"), 50) \
        .get_page(request.GET.get("page"))
    return render(request, "catalog/trash.html", {"page": page})


@admin_required
@require_POST
def attach_work(request, record_id):
    record = get_object_or_404(Record, record_id=record_id)
    uid = request.POST.get("work_uid", "").strip()
    if uid:
        work = Work.objects.filter(uid=uid).first()
        if not work:
            messages.error(request, "Œuvre introuvable.")
            return redirect(record.get_absolute_url())
    else:
        work = Work.objects.create(title_original=record.original_title, title_reading=record.reading,
                                   title_romaji=record.title_romaji, created_by=request.user,
                                   composition_date_text=record.composition_date_text,
                                   composition_year_start=record.composition_year_start,
                                   composition_year_end=record.composition_year_end,
                                   composition_date_precision=record.composition_date_precision,
                                   document_type=record.document_type, period=record.period)
    record.work = work
    record.save(update_fields=["work"])
    messages.success(request, f"Notice rattachée à l'œuvre « {work} » (rattachement validé par l'utilisateur).")
    return redirect(record.get_absolute_url())


@login_required
def work_detail(request, pk):
    work = get_object_or_404(Work, pk=pk)
    return render(request, "catalog/work_detail.html",
                  {"work": work, "records": work.records.select_related("catalogue")})
