"""
Traduction des notices (lot 5).

- Préparer la traduction d'une ou plusieurs notices (fiche, sélection de la Bibliothèque) : champs (titre et
  description ; sujets et lieu en option, décision C1), moteur par défaut ou deuxième moteur → tâche à confirmer.
- Consulter, pour une notice, l'original, la traduction adoptée et toutes les propositions (versions), puis
  valider (= adopter dans la notice, décision du 13 novembre 2026), rejeter ou supprimer. Comme sur la fiche,
  valider et rejeter sont réservés à l'administrateur (C2) ; le chercheur propose.
Les traductions restent dans la couche éditoriale existante (EditorialContent) ; la notice source n'est jamais
modifiée (seuls les champs « traduits » de la couche éditoriale reçoivent la traduction adoptée).
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.catalog.models import EditorialContent, Record
from apps.catalog.services import (ADOPTABLE_TRANSLATION_FIELDS, bulk_validation_message, plan_bulk_validation,
                                   validate_translation, validate_translations)
from apps.core.audit import log_action
from apps.core.permissions import admin_required, researcher_required
from apps.core.redirects import safe_next

from .. import services

DEFAULT_FIELDS = ("original_title", "description_original")


def _ids(request):
    raw = request.POST.get("records") if request.method == "POST" else request.GET.get("records", "")
    return [i for i in (raw or "").split(",") if i][:500]


def _engine_options(user):
    options = []
    for which, label in (("default", "Moteur par défaut"), ("second", "Deuxième moteur")):
        choice = services.resolve_choice(user, which=which)
        if choice:
            engine = choice.engine(user)
            options.append({"value": which, "label": label, "name": engine.display_name, "status": engine.status(),
                            "online": engine.online})
    return options


@researcher_required
def records_prepare(request):
    ids = _ids(request)
    records = list(Record.objects.filter(record_id__in=ids).select_related("catalogue"))
    pref = services.ensure_preference(request.user)
    defaults = list(DEFAULT_FIELDS) + (["subjects_original"] if pref.translate_subjects else []) + (
        ["place_original"] if pref.translate_place else [])
    if request.method == "POST":
        fields = [f for f in request.POST.getlist("fields") if f in services.RECORD_FIELDS]
        which = request.POST.get("engine", "default")
        choice = services.resolve_choice(request.user, which="second" if which == "second" else "default")
        if not records:
            messages.error(request, "Aucune notice sélectionnée.")
        elif not fields:
            messages.error(request, "Choisissez au moins un champ à traduire.")
        else:
            try:
                job = services.prepare_records_job(request.user, records, fields, choice=choice)
                log_action(request, "translation.records_prepared", job, f"{len(records)} notice(s), {fields}")
                return redirect("translation:job_detail", pk=job.pk)
            except services.TranslationUnavailable as exc:
                messages.error(request, str(exc))
        defaults = fields or defaults
    return render(request, "translation/records_prepare.html", {
        "records": records, "ids": ",".join(r.record_id for r in records), "fields": services.RECORD_FIELDS,
        "selected": defaults, "engines": _engine_options(request.user),
        "kanbun": [r for r in records if r.language == "lzh"],
    })


@researcher_required
def record_translations(request, record_id):
    record = get_object_or_404(Record.objects.select_related("catalogue"), record_id=record_id)
    proposals = (EditorialContent.objects.filter(record=record, kind="translation")
                 .select_related("ai_task", "author").order_by("-created_at"))
    rows = []
    for field, label in services.RECORD_FIELDS.items():
        original = (getattr(record, field, "") or "").strip()
        adopted_field = ADOPTABLE_TRANSLATION_FIELDS.get(field)
        rows.append({
            "field": field, "label": label, "original": original,
            "adopted": getattr(record, adopted_field, "") if adopted_field else "",
            "adopted_origin": getattr(record, f"{adopted_field}_origin", "") if adopted_field else "",
            "adoptable": bool(adopted_field),
            "proposals": [p for p in proposals if p.target_field == field],
        })
    from ..models import TranslationProject

    bulk, bulk_skipped = plan_bulk_validation(list(proposals.select_related("record")))
    return render(request, "translation/record_translations.html", {
        "record": record, "rows": rows, "engines": _engine_options(request.user),
        "bulk": bulk, "bulk_skipped": bulk_skipped,
        "kanbun": record.language == "lzh",
        "my_projects": TranslationProject.objects.filter(owner=request.user).order_by("title"),
    })


@researcher_required
@require_POST
def record_decide(request, pk):
    ed = get_object_or_404(EditorialContent.objects.select_related("record"), pk=pk, kind="translation")
    action = request.POST.get("action")
    back = reverse("translation:record_translations", args=[ed.record.record_id])
    if action in ("validate", "reject") and not request.user.is_admin_role:
        raise PermissionDenied("Validation réservée à l'administrateur.")
    if action == "validate":
        field = validate_translation(ed, request.user)
        log_action(request, "editorial.validate", ed, "Traduction validée et adoptée" if field else "Traduction validée")
        messages.success(request, "Traduction validée" + (" et recopiée dans la fiche." if field else "."))
    elif action == "reject":
        ed.status = "rejected"
        ed.save(update_fields=["status", "updated_at"])
        log_action(request, "editorial.reject", ed, ed.get_kind_display())
        messages.info(request, "Traduction rejetée (conservée dans l'historique).")
    elif action == "delete":
        if not (ed.author_id == request.user.pk or request.user.is_admin_role):
            raise PermissionDenied("Seuls l'auteur et l'administrateur peuvent supprimer cette proposition.")
        if ed.status == "validated" and not request.POST.get("confirm_validated"):
            messages.error(request, "Cette traduction est validée : confirmez sa suppression.")
            return redirect(back)
        ed.delete()
        messages.info(request, "Proposition supprimée.")
    return redirect(back)


@admin_required
@require_POST
def record_validate_all(request, record_id):
    """2.0.0 (demande du 15 novembre 2026) : valider et adopter en une fois les traductions proposées d'une notice."""
    record = get_object_or_404(Record, record_id=record_id)
    proposals = EditorialContent.objects.filter(record=record, kind="translation", status="proposed").select_related(
        "record")
    chosen, skipped = validate_translations(list(proposals), request.user)
    for ed in chosen:
        log_action(request, "editorial.validate", ed, "Traduction validée et adoptée (validation groupée)")
    (messages.success if chosen else messages.info)(request, bulk_validation_message(chosen, skipped))
    return redirect(safe_next(request, reverse("translation:record_translations", args=[record.record_id])))
