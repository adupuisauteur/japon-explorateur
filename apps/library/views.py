from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.catalog.models import DOCUMENT_TYPES, PERIODS, Catalogue, Record
from apps.catalog.services import record_editorial_change
from apps.core import japanese as jp
from apps.core.audit import log_action
from apps.core.redirects import safe_next
from apps.core.forms import BootstrapMixin
from apps.core.permissions import admin_required, researcher_required

from .models import (Annotation, Collection, CollectionRecord, CollectionSection, CollectionShare,
                     CorrectionProposal, LibraryEntry, Tag)


class CollectionForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Collection
        fields = ["title", "description", "keywords", "visibility", "methodology"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4}), "methodology": forms.Textarea(attrs={"rows": 3})}


def _record_ids(request):
    ids = []
    for value in request.POST.getlist("record_ids"):
        ids.extend(v for v in value.split(",") if v)
    return ids


def _next(request, default):
    return safe_next(request, default)


# --------------------------------------------------------------------------- bibliothèque


@login_required
def index(request):
    qs = LibraryEntry.objects.filter(user=request.user).select_related("record__catalogue").prefetch_related("tags")
    p = request.GET
    if p.get("q"):
        norm = jp.search_normalize(p["q"])
        qs = qs.filter(record__search_text__contains=norm)
    if p.get("tag"):
        qs = qs.filter(tags__name=p["tag"])
    if p.get("favorite"):
        qs = qs.filter(favorite=True)
    if p.get("verification"):
        qs = qs.filter(verification=p["verification"])
    if p.get("period"):
        qs = qs.filter(record__period=p["period"])
    if p.get("doc_type"):
        qs = qs.filter(record__document_type=p["doc_type"])
    if p.get("source"):
        qs = qs.filter(record__catalogue__code=p["source"])
    if p.get("duplicates"):
        qs = qs.filter(Q(record__links_out__status="proposed") | Q(record__links_in__status="proposed")).distinct()
    sort = {"title": "record__original_title", "date": "record__composition_year_start",
            "source": "record__catalogue__name", "collected": "-record__collected_at"}.get(p.get("sort"), "-added_at")
    qs = qs.order_by(sort)
    page = Paginator(qs, 30).get_page(p.get("page"))
    return render(request, "library/index.html", {
        "page": page, "tags": Tag.objects.filter(owner=request.user), "periods": [x for x in PERIODS if x[0]],
        "doc_types": [x for x in DOCUMENT_TYPES if x[0]], "verifications": LibraryEntry.VERIFICATION,
        "catalogues": Catalogue.objects.filter(records__library_entries__user=request.user).distinct(),
        "collections": Collection.objects.filter(owner=request.user), "total": qs.count(),
    })


@researcher_required
@require_POST
def add(request):
    records = Record.objects.filter(record_id__in=_record_ids(request))
    n = 0
    for record in records:
        n += int(LibraryEntry.objects.get_or_create(user=request.user, record=record)[1])
    messages.success(request, f"{n} notice(s) ajoutée(s) à votre bibliothèque.")
    return redirect(_next(request, records[0].get_absolute_url() if records else "library:index"))


@researcher_required
@require_POST
def remove(request):
    """Retire de la bibliothèque personnelle : la notice reste dans la base (§8.4)."""
    n, _ = LibraryEntry.objects.filter(user=request.user, record__record_id__in=_record_ids(request)).delete()
    messages.info(request, f"{n} notice(s) retirée(s) de votre bibliothèque (elles restent dans la base).")
    return redirect(_next(request, "library:index"))


@researcher_required
@require_POST
def entry_update(request, pk):
    entry = get_object_or_404(LibraryEntry, pk=pk, user=request.user)
    if "favorite" in request.POST:
        entry.favorite = request.POST["favorite"] == "1"
    if request.POST.get("verification") in dict(LibraryEntry.VERIFICATION):
        entry.verification = request.POST["verification"]
    entry.save()
    if "tags" in request.POST:
        names = {t.strip() for t in request.POST["tags"].split(",") if t.strip()}
        entry.tags.set([Tag.objects.get_or_create(owner=request.user, name=n[:80])[0] for n in names])
    if request.headers.get("HX-Request"):
        return render(request, "library/_entry_actions.html", {"entry": entry})
    return redirect(_next(request, entry.record.get_absolute_url()))


@researcher_required
@require_POST
def bulk(request):
    ids = request.POST.getlist("entry_ids")
    entries = LibraryEntry.objects.filter(user=request.user, pk__in=ids).select_related("record")
    action = request.POST.get("action")
    if action == "remove":
        n = entries.count()
        entries.delete()
        messages.info(request, f"{n} notice(s) retirée(s) de votre bibliothèque (conservées dans la base).")
    elif action == "verification":
        entries.update(verification=request.POST.get("verification", "unverified"))
        messages.success(request, "État de vérification mis à jour.")
    elif action == "tag" and request.POST.get("tag"):
        tag, _ = Tag.objects.get_or_create(owner=request.user, name=request.POST["tag"].strip()[:80])
        for e in entries:
            e.tags.add(tag)
        messages.success(request, f"Tag « {tag.name} » ajouté.")
    elif action == "collection":
        collection = get_object_or_404(Collection, pk=request.POST.get("collection"))
        if not collection.can_edit(request.user):
            raise PermissionDenied
        n = sum(int(CollectionRecord.objects.get_or_create(collection=collection, record=e.record,
                                                           defaults={"added_by": request.user})[1]) for e in entries)
        collection.save()
        messages.success(request, f"{n} notice(s) ajoutée(s) au dossier « {collection.title} ».")
    elif action == "export":
        ids = ",".join(e.record.record_id for e in entries)
        return redirect(f"/exports/preparer/?scope=selection&records={ids}")
    elif action == "translate":  # 1.3.0 : module de traduction
        ids = ",".join(e.record.record_id for e in entries)
        return redirect(f"{reverse('translation:records_prepare')}?records={ids}")
    elif action and action.startswith("ai_"):
        request.session["ai_records"] = [e.record.record_id for e in entries]
        request.session["ai_function"] = action[3:]
        return redirect("ai:launch_from_session")
    return redirect(_next(request, "library:index"))


# --------------------------------------------------------------------------- dossiers


@login_required
def collections(request):
    qs = Collection.visible_to(request.user).select_related("owner")
    return render(request, "library/collections.html", {
        "mine": qs.filter(owner=request.user), "others": qs.exclude(owner=request.user)})


@researcher_required
def collection_create(request):
    initial = {}
    session = None
    if request.GET.get("session"):
        from apps.searching.models import SearchSession

        session = SearchSession.objects.filter(uid=request.GET["session"], owner=request.user).first()
        if session:
            initial = {"title": session.query, "description": f"Dossier créé depuis la recherche « {session.query} »."}
    form = CollectionForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        collection = form.save(commit=False)
        collection.owner = request.user
        collection.created_from_session = session
        collection.save()
        if session:
            for r in session.results.filter(decision="selected", integrated_record__isnull=False):
                CollectionRecord.objects.get_or_create(collection=collection, record=r.integrated_record,
                                                       defaults={"added_by": request.user})
        ids = request.POST.get("record_ids", "")
        for record in Record.objects.filter(record_id__in=[i for i in ids.split(",") if i]):
            CollectionRecord.objects.get_or_create(collection=collection, record=record, defaults={"added_by": request.user})
        messages.success(request, "Dossier créé.")
        return redirect(collection.get_absolute_url())
    return render(request, "library/collection_form.html", {"form": form, "title": "Nouveau dossier",
                                                            "record_ids": request.GET.get("records", "")})


def _get_collection(request, pk, edit=False):
    collection = get_object_or_404(Collection, pk=pk)
    if not collection.can_view(request.user) or (edit and not collection.can_edit(request.user)):
        raise PermissionDenied
    return collection


@login_required
def collection_detail(request, pk):
    collection = _get_collection(request, pk)
    items = collection.items.select_related("record__catalogue", "section")
    sections = list(collection.sections.all())
    grouped = [(None, [i for i in items if i.section_id is None])] + [(s, [i for i in items if i.section_id == s.pk])
                                                                     for s in sections]
    return render(request, "library/collection_detail.html", {
        "collection": collection, "grouped": grouped, "sections": sections, "count": items.count(),
        "can_edit": collection.can_edit(request.user),
        "annotations": Annotation.visible_to(request.user).filter(collection=collection),
        "shares": collection.shares.select_related("user"),
        "users": get_user_model().objects.filter(is_active=True).exclude(pk=collection.owner_id),
        "exports": collection_exports(collection),
    })


def collection_exports(collection):
    from apps.exports.models import ExportJob

    return ExportJob.objects.filter(scope="collection", scope_params__collection_id=collection.pk)[:5]


@login_required
def collection_edit(request, pk):
    collection = _get_collection(request, pk, edit=True)
    form = CollectionForm(request.POST or None, instance=collection)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dossier mis à jour.")
        return redirect(collection.get_absolute_url())
    return render(request, "library/collection_form.html", {"form": form, "title": "Modifier le dossier",
                                                            "collection": collection})


@login_required
@require_POST
def collection_delete(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    if collection.owner_id != request.user.pk and not request.user.is_admin_role:
        raise PermissionDenied
    title = collection.title
    collection.delete()
    log_action(request, "collection.deleted", None, f"Dossier « {title} » supprimé (notices conservées)")
    messages.info(request, "Dossier supprimé ; les notices restent dans la base et dans votre bibliothèque.")
    return redirect("library:collections")


@researcher_required
@require_POST
def add_to_collection(request):
    collection = get_object_or_404(Collection, pk=request.POST.get("collection"))
    if not collection.can_edit(request.user):
        raise PermissionDenied
    section = collection.sections.filter(pk=request.POST.get("section") or 0).first()
    n = 0
    for record in Record.objects.filter(record_id__in=_record_ids(request)):
        n += int(CollectionRecord.objects.get_or_create(collection=collection, record=record,
                                                        defaults={"added_by": request.user, "section": section})[1])
        LibraryEntry.objects.get_or_create(user=request.user, record=record)
    collection.save()
    messages.success(request, f"{n} notice(s) ajoutée(s) au dossier « {collection.title} ».")
    return redirect(_next(request, collection.get_absolute_url()))


@login_required
@require_POST
def section_save(request, pk):
    collection = _get_collection(request, pk, edit=True)
    sid = request.POST.get("section_id")
    if request.POST.get("delete") and sid:
        collection.sections.filter(pk=sid).delete()
        messages.info(request, "Sous-section supprimée ; ses références restent dans le dossier.")
    else:
        section = collection.sections.filter(pk=sid).first() if sid else CollectionSection(collection=collection)
        section.title = request.POST.get("title", "").strip()[:300] or "Sans titre"
        section.description = request.POST.get("description", "")
        section.order = int(request.POST.get("order") or collection.sections.count() + 1)
        parent = collection.sections.filter(pk=request.POST.get("parent") or 0).first()
        section.parent = parent if parent and parent != section else None
        section.save()
    collection.save()
    return redirect(collection.get_absolute_url())


@login_required
@require_POST
def item_update(request, pk, item_pk):
    collection = _get_collection(request, pk, edit=True)
    item = get_object_or_404(CollectionRecord, pk=item_pk, collection=collection)
    if request.POST.get("remove"):
        item.delete()
        messages.info(request, "Notice retirée du dossier (elle reste dans la bibliothèque).")
    else:
        item.section = collection.sections.filter(pk=request.POST.get("section") or 0).first()
        item.note = request.POST.get("note", item.note)
        if request.POST.get("order"):
            item.order = int(request.POST["order"])
        item.save()
    collection.save()
    return redirect(collection.get_absolute_url() + f"#item-{item_pk}")


@login_required
@require_POST
def share(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    if collection.owner_id != request.user.pk and not request.user.is_admin_role:
        raise PermissionDenied
    if request.POST.get("remove"):
        collection.shares.filter(pk=request.POST["remove"]).delete()
    elif request.POST.get("user"):
        target = get_object_or_404(get_user_model(), pk=request.POST["user"])
        CollectionShare.objects.update_or_create(collection=collection, user=target,
                                                 defaults={"can_edit": bool(request.POST.get("can_edit"))})
        if collection.visibility == "private":
            collection.visibility = "shared"
            collection.save(update_fields=["visibility"])
        log_action(request, "collection.shared", collection, f"Partagé avec {target}")
    messages.success(request, "Partage mis à jour.")
    return redirect(collection.get_absolute_url() + "#partage")


# --------------------------------------------------------------------------- annotations


@researcher_required
@require_POST
def annotation_add(request):
    body = request.POST.get("body", "").strip()
    if not body:
        messages.error(request, "La note est vide.")
        return redirect(_next(request, "library:index"))
    target = {}
    if request.POST.get("record"):
        target["record"] = get_object_or_404(Record, pk=request.POST["record"])
    if request.POST.get("collection"):
        collection = _get_collection(request, request.POST["collection"])
        target["collection"] = collection
    visibility = request.POST.get("visibility", "private")
    if visibility == "editorial" and not request.user.can_edit:
        visibility = "private"
    Annotation.objects.create(author=request.user, body=body, updated_by=request.user,
                              visibility=visibility if visibility in dict(Annotation.VISIBILITY) else "private",
                              locator_type=request.POST.get("locator_type", "")[:20],
                              locator=request.POST.get("locator", "")[:200], **target)
    messages.success(request, "Note ajoutée.")
    return redirect(_next(request, "library:index"))


@login_required
@require_POST
def annotation_delete(request, pk):
    note = get_object_or_404(Annotation, pk=pk)
    if note.author_id != request.user.pk and not request.user.is_admin_role:
        raise PermissionDenied
    back = note.record.get_absolute_url() + "#notes" if note.record else (
        note.collection.get_absolute_url() if note.collection else "/")
    note.delete()
    return redirect(back)


# --------------------------------------------------------------------------- corrections


@researcher_required
@require_POST
def correction_add(request, record_id):
    record = get_object_or_404(Record, record_id=record_id)
    field = request.POST.get("field")
    if field not in dict(CorrectionProposal.FIELDS):
        messages.error(request, "Champ non corrigeable : les données originales de la source ne sont jamais modifiées.")
        return redirect(record.get_absolute_url())
    CorrectionProposal.objects.create(record=record, field=field, current_value=str(getattr(record, field) or ""),
                                      proposed_value=request.POST.get("proposed_value", "").strip(),
                                      justification=request.POST.get("justification", "").strip(),
                                      author=request.user)
    messages.success(request, "Proposition de correction enregistrée ; elle sera examinée par un administrateur.")
    return redirect(record.get_absolute_url())


@admin_required
def corrections(request):
    qs = CorrectionProposal.objects.select_related("record", "author")
    status = request.GET.get("status", "proposed")
    if status:
        qs = qs.filter(status=status)
    return render(request, "library/corrections.html", {"items": qs[:200], "status": status})


@admin_required
@require_POST
def correction_decide(request, pk):
    proposal = get_object_or_404(CorrectionProposal, pk=pk, status="proposed")
    decision = request.POST.get("decision")
    proposal.reviewed_by = request.user
    proposal.reviewed_at = timezone.now()
    proposal.review_note = request.POST.get("note", "")
    if decision == "accept":
        record = proposal.record
        field = proposal.field
        old = getattr(record, field)
        value = proposal.proposed_value
        if field.endswith(("_start", "_end")):
            try:
                value = int(value) if value else None
            except ValueError:
                messages.error(request, "Valeur numérique attendue.")
                return redirect("library:corrections")
            prefix = field.rsplit("_year", 1)[0]
            setattr(record, f"{prefix}_date_origin", "user")
        setattr(record, field, value)
        if field in ("translated_title", "description_translation"):
            setattr(record, f"{field}_origin", "user")
        record_editorial_change(record, field, old, value, request.user,
                                note=f"Correction acceptée (proposée par {proposal.author}) : {proposal.justification[:200]}")
        proposal.status = "accepted"
    else:
        proposal.status = "rejected"
    proposal.save()
    log_action(request, f"correction.{proposal.status}", proposal.record, proposal.get_field_display())
    messages.success(request, f"Proposition {proposal.get_status_display().lower()}.")
    return redirect("library:corrections")
