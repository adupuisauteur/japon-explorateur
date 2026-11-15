import os

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.forms import BootstrapMixin
from apps.core.models import AppSettings

from .document import build_document
from .generators.common import fiche_rows, metadata_lines
from .models import FORMATS, PRESETS, SCOPES, ExportFile, ExportJob, ExportProfile
from .services import PRESET_DEFAULTS, clone_for_regeneration, data_changed_since


class ExportForm(BootstrapMixin, forms.Form):
    preset = forms.ChoiceField(label="Modèle", choices=PRESETS)
    format = forms.ChoiceField(label="Format", choices=FORMATS)
    title = forms.CharField(label="Titre du document", max_length=300)
    subtitle = forms.CharField(label="Sous-titre", max_length=300, required=False)
    subject = forms.CharField(label="Sujet / objet de l'export", max_length=500, required=False)
    author = forms.CharField(label="Auteur / préparateur", max_length=200, required=False)
    header_text = forms.CharField(label="En-tête", max_length=300, required=False)
    footer_text = forms.CharField(label="Pied de page", max_length=300, required=False)
    hide_user = forms.BooleanField(
        label="Ne pas indiquer mon identifiant en bas de page (export destiné à être diffusé)", required=False)
    column_profile = forms.ChoiceField(label="Profil de colonnes (CSV)", choices=[
        ("bibliography", "Bibliographie"), ("inventory", "Inventaire complet"), ("historical", "Recherche historique"),
        ("generic", "Import générique (réimportable)")], required=False)
    csv_separator = forms.ChoiceField(label="Séparateur CSV", required=False, choices=[
        ("semicolon", "Point-virgule ;"), ("comma", "Virgule ,"), ("tab", "Tabulation")])
    csv_bom = forms.BooleanField(label="UTF-8 avec BOM (ouverture directe dans Excel)", required=False)
    csv_neutralize = forms.BooleanField(
        label="Neutraliser les formules (CSV) : préfixe ' devant les cellules commençant par = + - @",
        required=False, initial=True)
    include_ai = forms.BooleanField(label="Inclure traductions automatiques et contenus IA (signalés comme tels)",
                                    required=False,
                                    initial=True)
    include_notes = forms.BooleanField(label="Inclure les notes et annotations", required=False, initial=True)
    include_images = forms.BooleanField(label="Inclure les liens vers images (uniquement si droits connus)",
                                        required=False)
    pagination = forms.BooleanField(label="Pagination (DOCX/PDF)", required=False, initial=True)
    toc = forms.BooleanField(label="Sommaire", required=False, initial=True)
    only_selected = forms.BooleanField(label="Session : uniquement les résultats sélectionnés", required=False,
                                       initial=True)
    save_profile_as = forms.CharField(label="Enregistrer ces réglages comme profil (nom)", required=False)

    OPTION_FIELDS = ["column_profile", "csv_separator", "csv_bom", "csv_neutralize", "include_ai", "include_notes", "include_images",
                     "pagination", "toc", "hide_user"]


def _scope_from_request(request):
    p = request.GET if request.method == "GET" else request.POST
    scope = p.get("scope", "selection")
    if scope not in dict(SCOPES):
        scope = "selection"
    params = {}
    defaults = {"title": "Sélection de notices", "subject": ""}
    if scope == "collection":
        from apps.library.models import Collection

        collection = get_object_or_404(Collection, pk=p.get("collection"))
        if not collection.can_view(request.user):
            raise PermissionDenied
        params["collection_id"] = collection.pk
        defaults = {"title": collection.title, "subject": collection.keywords or collection.description[:200]}
    elif scope == "session":
        from apps.searching.models import SearchSession

        session = get_object_or_404(SearchSession, uid=p.get("session"))
        if session.owner_id != request.user.pk and not request.user.is_admin_role:
            raise PermissionDenied
        params["session_uid"] = str(session.uid)
        defaults = {"title": f"Recherche : {session.query or 'avancée'}", "subject": session.query}
    elif scope == "library":
        params = {k: p.get(k) for k in ("tag", "favorites") if p.get(k)}
        defaults = {"title": "Bibliothèque personnelle", "subject": ""}
    else:
        ids = [i for i in p.get("records", "").split(",") if i]
        params["record_ids"] = ids
    return scope, params, defaults


def _job_from_form(request, form, scope, params):
    d = form.cleaned_data
    options = {k: d.get(k) for k in ExportForm.OPTION_FIELDS}
    if scope == "session":
        params = {**params, "only_selected": d.get("only_selected", True)}
    return ExportJob(owner=request.user, preset=d["preset"], format=d["format"], scope=scope, scope_params=params,
                     title=d["title"], subtitle=d["subtitle"], subject=d["subject"], author=d["author"],
                     header_text=d["header_text"], footer_text=d["footer_text"], options=options)


@login_required
def prepare(request):
    scope, params, defaults = _scope_from_request(request)
    app = AppSettings.get()
    initial = {"title": defaults["title"], "subject": defaults["subject"], "preset": "dossier" if scope == "collection"
               else "bibliography", "format": "docx", "author": app.export_default_author or str(request.user),
               "header_text": app.export_default_header or defaults["title"], "footer_text": app.export_default_footer,
               "column_profile": "bibliography", "csv_separator": "semicolon", "include_ai": True, "include_notes": True,
               "pagination": True, "toc": True, "only_selected": True}
    profile = None
    if request.GET.get("profile"):
        profile = ExportProfile.objects.filter(pk=request.GET["profile"], owner=request.user).first()
        if profile:
            initial.update({"preset": profile.preset, "format": profile.format, **profile.options})
    elif request.GET.get("preset") in PRESET_DEFAULTS:
        initial.update({"preset": request.GET["preset"], **PRESET_DEFAULTS[request.GET["preset"]]})
    form = ExportForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        job = _job_from_form(request, form, scope, params)
        job.profile = profile
        job.status = "pending"
        job.save()
        if form.cleaned_data.get("save_profile_as"):
            ExportProfile.objects.create(owner=request.user, name=form.cleaned_data["save_profile_as"][:200],
                                         preset=job.preset, format=job.format, options=job.options)
            messages.info(request, "Profil d'export enregistré.")
        from .tasks import generate_export

        generate_export.delay(job.pk)
        log_action(request, "export.generate", job, f"{job.get_format_display()} — {job.title}")
        return redirect(job.get_absolute_url())
    return render(request, "exports/prepare.html", {
        "form": form, "scope": scope, "scope_label": dict(SCOPES)[scope], "params": params,
        "hidden": {k: v for k, v in (request.GET.items() if request.method == "GET" else request.POST.items())
                   if k in ("scope", "collection", "session", "records", "tag", "favorites")},
        "profiles": ExportProfile.objects.filter(owner=request.user), "preset_defaults": PRESET_DEFAULTS,
    })


@login_required
@require_POST
def preview(request):
    scope, params, _ = _scope_from_request(request)
    form = ExportForm(request.POST)
    if not form.is_valid():
        return render(request, "exports/_preview.html", {"errors": form.errors})
    job = _job_from_form(request, form, scope, params)
    job.export_uid = "EXP-APERÇU"
    doc = build_document(job)
    first = doc.records[0] if doc.records else None
    return render(request, "exports/_preview.html", {
        "doc": doc, "meta": doc.metadata, "lines": metadata_lines(doc), "first": first,
        "rows": fiche_rows(first) if first else [], "fmt": job.format,
    })


@login_required
def export_list(request):
    return render(request, "exports/list.html", {"jobs": ExportJob.objects.filter(owner=request.user)[:100],
                                                 "profiles": ExportProfile.objects.filter(owner=request.user)})


def _get_job(request, pk):
    job = get_object_or_404(ExportJob, pk=pk)
    if job.owner_id != request.user.pk and not request.user.is_admin_role:
        raise PermissionDenied
    return job


@login_required
def detail(request, pk):
    job = _get_job(request, pk)
    return render(request, "exports/detail.html", {"job": job, "files": job.files.all(),
                                                   "changed": data_changed_since(job) if job.status == "done" else None})


@login_required
def download(request, pk, file_pk):
    job = _get_job(request, pk)
    f = get_object_or_404(ExportFile, pk=file_pk, job=job)
    path = os.path.join(settings.MEDIA_ROOT, f.path)
    if not os.path.realpath(path).startswith(os.path.realpath(settings.MEDIA_ROOT)) or not os.path.exists(path):
        raise Http404
    return FileResponse(open(path, "rb"), as_attachment=True, filename=f.name, content_type=f.mime_type)


@login_required
@require_POST
def regenerate(request, pk):
    job = _get_job(request, pk)
    new = clone_for_regeneration(job)
    from .tasks import generate_export

    generate_export.delay(new.pk)
    messages.info(request, "Export régénéré avec les mêmes paramètres.")
    return redirect(new.get_absolute_url())


@login_required
@require_POST
def profile_delete(request, pk):
    get_object_or_404(ExportProfile, pk=pk, owner=request.user).delete()
    messages.info(request, "Profil supprimé.")
    return redirect("exports:list")
