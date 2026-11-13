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
    from apps.incidents.models import OPEN_STATUSES, Incident

    incidents = Incident.objects.filter(source_code=catalogue.code)
    return render(request, "connectors/detail.html", {
        "catalogue": catalogue, "connector_cls": cls, "form": form,
        "jobs": catalogue.sync_jobs.all()[:10], "imports": catalogue.import_jobs.all()[:10],
        "n_records": catalogue.records.exclude(record_status="deleted").count(),
        "incidents": incidents[:5], "incidents_open": incidents.filter(status__in=OPEN_STATUSES).count(),
        "incidents_total": incidents.count(),
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


# --------------------------------------------------------------------------- Japan Search : bases institutionnelles (1.2.0)


@admin_required
def jps_databases(request):
    """Recherche, à la demande de l'utilisateur, des bases connectées à Japan Search (archives, universités…)."""
    from apps.incidents.services import record_connector_error

    from .base import ConnectorError
    from .http import ConnectorHTTP
    from .japansearch import search_databases

    keyword = (request.GET.get("q") or "").strip()[:100]
    found, error = [], ""
    existing = {c.config.get("database"): c for c in Catalogue.objects.filter(connector="japansearch")
                if c.config.get("database")}
    if keyword:
        jps = Catalogue.objects.filter(code="japansearch").first() or Catalogue(code="japansearch", name="Japan Search")
        try:
            found = search_databases(ConnectorHTTP(jps), keyword)
        except ConnectorError as exc:
            error = str(exc)
            record_connector_error(exc, module="connecteur", source_code="japansearch",
                                   operation=f"Recherche des bases Japan Search « {keyword} »")
    return render(request, "connectors/jps_databases.html", {"q": keyword, "found": found, "error": error,
                                                              "existing": existing})


@admin_required
@require_POST
def jps_create_source(request):
    """Crée une source restreinte à une base Japan Search (désactivée tant qu'elle n'a pas été testée)."""
    from django.utils.text import slugify

    db_id = (request.POST.get("db_id") or "").strip()[:60]
    name = (request.POST.get("name") or db_id).strip()[:200]
    if not db_id:
        messages.error(request, "Identifiant de base manquant.")
        return redirect("connectors:jps_databases")
    existing = next((c for c in Catalogue.objects.filter(connector="japansearch") if c.config.get("database") == db_id), None)
    if existing:
        messages.info(request, f"Une source existe déjà pour la base {db_id} : « {existing.name} ».")
        return redirect(existing.get_absolute_url())
    code = slugify(f"jps-{db_id}")[:50] or "jps-base"
    if Catalogue.objects.filter(code=code).exists():
        code = f"{code[:44]}-{Catalogue.objects.count()}"
    catalogue = Catalogue.objects.create(
        code=code, name=name, connector="japansearch", status="partial", enabled_for_search=False, sort_order=60,
        config={"database": db_id}, base_url=(request.POST.get("url") or "")[:200] if (request.POST.get("url") or "").startswith("http") else "",
        terms_url="https://jpsearch.go.jp/static/developer/webapi/",
        role=f"Base « {name} » interrogée via Japan Search ({(request.POST.get('provider') or '').strip()[:150]}).",
        access_method=f"API officielle de Japan Search, filtrée sur la base « {db_id} » (paramètre f-db). Seules les "
                      "métadonnées que l'institution autorise à diffuser par API sont disponibles.",
        notes="Source créée depuis « Trouver une base Japan Search ». Testez-la, puis cochez « Interrogé dans les "
              "recherches ».", min_interval_seconds=1.0)
    log_action(request, "source.created", catalogue, f"Base Japan Search {db_id}")
    messages.success(request, f"Source « {name} » créée. Cliquez sur « Tester le connecteur », puis activez-la "
                              "pour les recherches.")
    return redirect(catalogue.get_absolute_url())
