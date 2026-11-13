import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Catalogue
from apps.core.audit import log_action
from apps.core.forms import BootstrapMixin
from apps.core.permissions import admin_required

from .registry import available_connectors, connector_class


class CatalogueForm(BootstrapMixin, forms.ModelForm):
    config_json = forms.CharField(label="Paramètres du connecteur (JSON)", required=False,
                                  widget=forms.Textarea(attrs={"rows": 4, "class": "form-control font-monospace"}))

    class Meta:
        model = Catalogue
        fields = ["name", "name_original", "connector", "status", "enabled_for_search", "frequency",
                  "custom_interval_hours", "min_interval_seconds", "timeout_seconds", "base_url", "terms_url",
                  "role", "access_method", "license_notes", "unsupported_fields", "is_snapshot", "snapshot_date", "notes"]
        widgets = {"role": forms.Textarea(attrs={"rows": 2}), "access_method": forms.Textarea(attrs={"rows": 3}),
                   "license_notes": forms.Textarea(attrs={"rows": 3}), "unsupported_fields": forms.Textarea(attrs={"rows": 2}),
                   "notes": forms.Textarea(attrs={"rows": 2}), "snapshot_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["connector"] = forms.ChoiceField(
            label="Connecteur", required=False,
            choices=[("", "— Aucun (import de fichiers uniquement)")] + [(k, c.label) for k, c in available_connectors().items()],
            widget=forms.Select(attrs={"class": "form-select"}))
        self.fields["config_json"].initial = json.dumps(self.instance.config or {}, ensure_ascii=False, indent=2)

    def clean_config_json(self):
        raw = self.cleaned_data.get("config_json") or "{}"
        try:
            value = json.loads(raw)
        except ValueError:
            raise forms.ValidationError("JSON invalide.")
        if not isinstance(value, dict):
            raise forms.ValidationError("Un objet JSON est attendu.")
        return value

    def save(self, commit=True):
        self.instance.config = self.cleaned_data.get("config_json") or {}
        return super().save(commit)


@login_required
def source_list(request):
    catalogues = Catalogue.objects.annotate(
        n_records=Count("records", filter=~Q(records__record_status="deleted"))).select_related("institution")
    return render(request, "connectors/list.html", {"catalogues": catalogues})


@login_required
def source_detail(request, code):
    catalogue = get_object_or_404(Catalogue, code=code)
    cls = connector_class(catalogue.connector)
    form = None
    if request.user.is_admin_role:
        form = CatalogueForm(request.POST or None, instance=catalogue)
        if request.method == "POST" and form.is_valid():
            form.save()
            log_action(request, "source.updated", catalogue, f"Source {catalogue.code} modifiée")
            messages.success(request, "Source mise à jour.")
            return redirect(catalogue.get_absolute_url())
    return render(request, "connectors/detail.html", {
        "catalogue": catalogue, "connector_cls": cls, "form": form,
        "jobs": catalogue.sync_jobs.all()[:10], "imports": catalogue.import_jobs.all()[:10],
        "n_records": catalogue.records.exclude(record_status="deleted").count(),
    })


@admin_required
@require_POST
def source_test(request, code):
    from apps.updates.models import SyncJob
    from apps.updates.services import run_sync

    catalogue = get_object_or_404(Catalogue, code=code)
    job = run_sync(SyncJob.objects.create(catalogue=catalogue, kind="test", triggered_by=request.user))
    level = messages.SUCCESS if job.status == "done" else messages.ERROR
    messages.add_message(request, level, job.message or job.get_status_display())
    detected = (job.report or {}).get("details", {}).get("detected_japansearch_db")
    if detected and detected != catalogue.config.get("japansearch_db"):
        request.session["detected_db"] = {"code": code, "value": detected}
    return redirect(catalogue.get_absolute_url())


@admin_required
@require_POST
def apply_detection(request, code):
    catalogue = get_object_or_404(Catalogue, code=code)
    detected = request.session.pop("detected_db", None)
    if detected and detected["code"] == code:
        catalogue.config = {**(catalogue.config or {}), "japansearch_db": detected["value"]}
        catalogue.save(update_fields=["config"])
        log_action(request, "source.config", catalogue, f"Base Japan Search : {detected['value']}")
        messages.success(request, f"Identifiant de base enregistré : {detected['value']}.")
    return redirect(catalogue.get_absolute_url())
