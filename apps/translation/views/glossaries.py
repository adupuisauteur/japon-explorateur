"""Glossaires : liste, création, entrées, import et export CSV, envoi à DeepL, liens avec les projets."""
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import researcher_required

from .. import glossary as G
from ..engines.base import TranslationEngineError
from ..forms import GlossaryEntryForm, GlossaryForm, GlossaryImportForm
from ..models import Glossary, GlossaryEntry, ProjectGlossary, TranslationSegment
from ..permissions import (can_edit_glossary, can_edit_project, can_view_glossary, glossaries_metadata_only_for,
                           glossaries_visible_for, require)
from .projects import get_project_for


def get_glossary_for(request, pk, *, edit=False):
    glossary = get_object_or_404(Glossary.objects.select_related("owner"), pk=pk)
    allowed = can_edit_glossary(request.user, glossary) if edit else can_view_glossary(request.user, glossary)
    if not allowed:
        raise Http404
    return glossary


def _annotated(qs):
    return qs.select_related("owner").annotate(n_entries=Count("entries", distinct=True),
                                               n_projects=Count("project_links", distinct=True))


@researcher_required
def glossary_list(request):
    visible = glossaries_visible_for(request.user)
    return render(request, "translation/glossary_list.html", {
        "mine": _annotated(visible.filter(owner=request.user)),
        "others": _annotated(visible.exclude(owner=request.user)),
        "hidden": _annotated(glossaries_metadata_only_for(request.user)),
    })


@researcher_required
def glossary_create(request):
    form = GlossaryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        glossary = form.save(commit=False)
        glossary.owner = request.user
        glossary.save()
        log_action(request, "translation.glossary_created", glossary, f"Glossaire « {glossary.name} »")
        messages.success(request, "Glossaire créé. Ajoutez des entrées ou importez un fichier CSV.")
        return redirect("translation:glossary_detail", pk=glossary.pk)
    return render(request, "translation/glossary_form.html", {"form": form, "glossary": None})


@researcher_required
def glossary_edit(request, pk):
    glossary = get_glossary_for(request, pk, edit=True)
    langs = (glossary.source_lang, glossary.target_lang)
    form = GlossaryForm(request.POST or None, instance=glossary)
    if request.method == "POST" and form.is_valid():
        form.save()
        if (glossary.source_lang, glossary.target_lang) != langs:
            G.bump(glossary)
        log_action(request, "translation.glossary_updated", glossary, f"Glossaire « {glossary.name} »")
        messages.success(request, "Glossaire enregistré.")
        return redirect("translation:glossary_detail", pk=glossary.pk)
    return render(request, "translation/glossary_form.html", {"form": form, "glossary": glossary})


@researcher_required
def glossary_detail(request, pk):
    glossary = get_glossary_for(request, pk)
    entries = glossary.entries.all()
    q = request.GET.get("q", "").strip()
    if q:
        entries = entries.filter(Q(source_term__icontains=q) | Q(target_term__icontains=q) | Q(reading__icontains=q)
                                 | Q(note__icontains=q))
    category = request.GET.get("categorie", "")
    if category:
        entries = entries.filter(category=category)
    editing = glossary.entries.filter(pk=request.GET.get("modifier")).first() if request.GET.get("modifier") else None
    copy = G.remote_copy(glossary, request.user)
    return render(request, "translation/glossary_detail.html", {
        "glossary": glossary, "entries": entries, "q": q, "category": category,
        "categories": GlossaryEntry._meta.get_field("category").choices,
        "entry_form": GlossaryEntryForm(initial=GlossaryEntryForm.initial_for(editing) if editing else None),
        "editing": editing, "import_form": GlossaryImportForm(),
        "can_edit": can_edit_glossary(request.user, glossary),
        "projects": glossary.projects.filter(Q(owner=request.user) | Q(confidential=False)).select_related("owner"),
        "remote": copy, "remote_current": G.remote_copy_is_current(glossary, request.user),
        "send_problem": G.send_problem(glossary, request.user), "n_deepl_entries": len(G.deepl_entries(glossary)),
        "contradictions": _internal_overlaps(glossary),
    })


def _internal_overlaps(glossary):
    """Entrées dont un terme à éviter est le terme cible imposé par une autre entrée (incohérence probable)."""
    targets = {G.fold(e.target_term): e for e in glossary.entries.all()}
    out = []
    for e in glossary.entries.all():
        for bad in e.avoid:
            other = targets.get(G.fold(bad))
            if other is not None and other.pk != e.pk:
                out.append((e, bad, other))
    return out


@researcher_required
@require_POST
def entry_save(request, pk):
    glossary = get_glossary_for(request, pk, edit=True)
    entry = glossary.entries.filter(pk=request.POST.get("entry")).first() if request.POST.get("entry") else None
    form = GlossaryEntryForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Entrée incomplète : " + " ".join(e for errs in form.errors.values() for e in errs))
    else:
        try:
            saved = G.save_entry(glossary, form.cleaned_data, entry=entry)
            messages.success(request, f"Entrée « {saved.source_term} » enregistrée (glossaire version {glossary.version}).")
        except G.GlossaryError as exc:
            messages.error(request, str(exc))
    target = request.POST.get("next", "")
    if target.startswith("/traduction/"):
        return redirect(target)
    return redirect("translation:glossary_detail", pk=glossary.pk)


@researcher_required
@require_POST
def entry_delete(request, pk, entry_pk):
    glossary = get_glossary_for(request, pk, edit=True)
    entry = get_object_or_404(GlossaryEntry, pk=entry_pk, glossary=glossary)
    term = entry.source_term
    G.delete_entry(entry)
    messages.info(request, f"Entrée « {term} » supprimée.")
    return redirect("translation:glossary_detail", pk=glossary.pk)


@researcher_required
def glossary_import(request, pk):
    glossary = get_glossary_for(request, pk, edit=True)
    if request.method != "POST":
        return redirect("translation:glossary_detail", pk=glossary.pk)
    form = GlossaryImportForm(request.POST, request.FILES)
    report = None
    if form.is_valid():
        raw = form.cleaned_data["file"].read()
        dry_run = request.POST.get("action") != "import"
        try:
            report = G.import_csv(glossary, raw, update_existing=form.cleaned_data["update_existing"], dry_run=True)
            if not dry_run:
                if report.encoding_confidence == "uncertain" and not form.cleaned_data["confirm_encoding"]:
                    messages.error(request, "Encodage incertain : vérifiez l'aperçu puis cochez la case de confirmation.")
                else:
                    report = G.import_csv(glossary, raw, update_existing=form.cleaned_data["update_existing"])
                    log_action(request, "translation.glossary_imported", glossary,
                               f"Import CSV : {len(report.added)} ajoutée(s), {len(report.updated)} mise(s) à jour")
                    messages.success(request, f"Import terminé : {len(report.added)} entrée(s) ajoutée(s), "
                                              f"{len(report.updated)} mise(s) à jour, {len(report.skipped)} ignorée(s), "
                                              f"{len(report.errors)} en erreur.")
        except G.GlossaryError as exc:
            messages.error(request, str(exc))
    return render(request, "translation/glossary_import.html", {"glossary": glossary, "form": form, "report": report})


@researcher_required
def glossary_export(request, pk):
    glossary = get_glossary_for(request, pk)
    response = HttpResponse(G.export_csv(glossary), content_type="text/csv; charset=utf-8")
    name = slugify(glossary.name) or "glossaire"
    response["Content-Disposition"] = f'attachment; filename="glossaire-{name}-v{glossary.version}.csv"'
    return response


@researcher_required
@require_POST
def glossary_deepl(request, pk):
    """Envoi à DeepL ou suppression de la copie distante : action explicite et confirmée du propriétaire."""
    glossary = get_glossary_for(request, pk, edit=True)
    action = request.POST.get("action")
    try:
        if action == "send":
            if not request.POST.get("confirm"):
                raise G.GlossaryError("Cochez la case de confirmation : les termes du glossaire seront envoyés à DeepL.")
            message = G.send_to_deepl(glossary, request.user)
            log_action(request, "translation.glossary_sent_deepl", glossary, message)
            messages.success(request, message)
        elif action == "delete":
            message = G.delete_remote(glossary, request.user)
            log_action(request, "translation.glossary_remote_deleted", glossary, message)
            messages.success(request, message)
    except G.GlossaryError as exc:
        messages.error(request, str(exc))
    except TranslationEngineError as exc:
        messages.error(request, f"DeepL : {exc}")
    return redirect("translation:glossary_detail", pk=glossary.pk)


@researcher_required
@require_POST
def glossary_delete(request, pk):
    glossary = get_glossary_for(request, pk, edit=True)
    if glossary.remote_copies:
        messages.error(request, "Ce glossaire a encore une copie chez DeepL : supprimez-la d'abord (la copie d'un autre "
                                "compte ne peut être supprimée que par lui).")
        return redirect("translation:glossary_detail", pk=glossary.pk)
    if request.POST.get("confirm_name", "").strip() != glossary.name.strip():
        messages.error(request, "Pour supprimer le glossaire, recopiez exactement son nom.")
        return redirect("translation:glossary_detail", pk=glossary.pk)
    name, n_projects = glossary.name, glossary.project_links.count()
    log_action(request, "translation.glossary_deleted", glossary, f"Glossaire « {name} » supprimé")
    glossary.delete()
    messages.info(request, f"Glossaire « {name} » supprimé" + (f" et retiré de {n_projects} projet(s)." if n_projects else "."))
    return redirect("translation:glossary_list")


# --------------------------------------------------------------------------- projets


def linkable_glossaries(request, project):
    owners = {project.owner_id, request.user.pk}
    return (Glossary.objects.filter(owner_id__in=owners, source_lang=project.source_lang,
                                    target_lang=project.target_lang)
            .exclude(project_links__project=project).order_by("name"))


@researcher_required
@require_POST
def project_glossaries(request, pk):
    project = get_project_for(request, pk, edit=True)
    require(can_edit_project(request.user, project))
    action = request.POST.get("action")
    if action == "add":
        glossary = linkable_glossaries(request, project).filter(pk=request.POST.get("glossary")).first()
        if glossary is None:
            messages.error(request, "Glossaire introuvable ou de paire de langues différente.")
        else:
            last = project.glossary_links.order_by("-priority").first()
            ProjectGlossary.objects.create(project=project, glossary=glossary, priority=(last.priority + 1) if last else 0)
            messages.success(request, f"Glossaire « {glossary.name} » ajouté au projet.")
    else:
        link = get_object_or_404(ProjectGlossary, project=project, pk=request.POST.get("link"))
        if action == "remove":
            link.delete()
            messages.info(request, f"Glossaire « {link.glossary.name} » retiré du projet (il n'est pas supprimé).")
        elif action in ("up", "down"):
            links = list(project.glossary_links.order_by("priority", "pk"))
            i = links.index(link)
            j = i - 1 if action == "up" else i + 1
            if 0 <= j < len(links):
                links[i], links[j] = links[j], links[i]
            for n, item in enumerate(links):
                if item.priority != n:
                    ProjectGlossary.objects.filter(pk=item.pk).update(priority=n)
    return redirect(reverse("translation:project_detail", args=[project.pk]) + "#glossaires")


@researcher_required
@require_POST
def segment_term(request, pk):
    """« Ajouter au glossaire » depuis la page d'un segment."""
    segment = get_object_or_404(TranslationSegment.objects.select_related("document__project"), pk=pk)
    project = segment.document.project
    if not can_edit_project(request.user, project):
        raise Http404
    glossary = project.glossaries.filter(pk=request.POST.get("glossary")).first()
    if glossary is None or not can_edit_glossary(request.user, glossary):
        messages.error(request, "Choisissez un glossaire du projet que vous pouvez modifier.")
        return redirect("translation:segment_detail", pk=segment.pk)
    form = GlossaryEntryForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Terme source et terme cible obligatoires.")
    else:
        try:
            entry = G.save_entry(glossary, form.cleaned_data)
            messages.success(request, f"« {entry.source_term} → {entry.target_term} » ajouté au glossaire « {glossary.name} ».")
        except G.GlossaryError as exc:
            messages.error(request, str(exc))
    return redirect("translation:segment_detail", pk=segment.pk)
