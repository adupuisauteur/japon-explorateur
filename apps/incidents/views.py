"""Pages du journal des dysfonctionnements : liste filtrée, détail, signalement, analyse, export."""
import datetime
import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.logging import redact

from . import report
from .forms import ExportForm, FilterForm, ManualReportForm, StatusForm
from .models import OPEN_STATUSES, ORIGIN_HELP, Incident
from .services import before_after_fix, change_status, record_incident


def _filtered(request):
    sources = (Incident.objects.exclude(source_code="").values_list("source_code", flat=True)
               .distinct().order_by("source_code"))
    form = FilterForm(request.GET or None, sources=list(sources))
    qs = Incident.objects.all()
    applied = {}
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            q = d["q"].strip()
            qs = qs.filter(Q(uid__icontains=q) | Q(title__icontains=q) | Q(message__icontains=q)
                           | Q(last_request_id__iexact=q) | Q(occurrences__request_id__iexact=q)).distinct()
        if d["date_from"]:
            qs = qs.filter(last_seen_at__date__gte=d["date_from"])
        if d["date_to"]:
            qs = qs.filter(first_seen_at__date__lte=d["date_to"])
        for key, field in (("module", "module"), ("source", "source_code"), ("severity", "severity")):
            if d[key]:
                qs = qs.filter(**{field: d[key]})
        if d["status"] == "ouverts":
            qs = qs.filter(status__in=OPEN_STATUSES)
        elif d["status"]:
            qs = qs.filter(status=d["status"])
        if d["manual"]:
            qs = qs.filter(is_manual=d["manual"] == "manual")
        applied = {k: str(v) for k, v in d.items() if v}
    return form, qs, applied


@login_required
def incident_list(request):
    form, qs, applied = _filtered(request)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    counts = Incident.objects.filter(status__in=OPEN_STATUSES).values("severity").annotate(n=Count("pk"))
    open_counts = {c["severity"]: c["n"] for c in counts}
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "incidents/list.html", {
        "form": form, "page": page, "open_counts": open_counts, "applied": applied,
        "querystring": query.urlencode(), "total": qs.count(),
    })


@login_required
def incident_detail(request, uid):
    incident = get_object_or_404(Incident, uid=uid)
    status_form = StatusForm(initial={"status": incident.status}) if request.user.is_admin_role else None
    return render(request, "incidents/detail.html", {
        "incident": incident, "occurrences": incident.occurrences.all()[:50], "events": incident.events.all(),
        "status_form": status_form, "comparison": before_after_fix(incident),
        "similar": Incident.objects.filter(source_code=incident.source_code, category=incident.category)
                   .exclude(pk=incident.pk)[:5] if incident.source_code else [],
    })


@login_required
@require_POST
def incident_status(request, uid):
    if not request.user.is_admin_role:
        raise PermissionDenied("Seul l'administrateur peut changer le statut d'un incident.")
    incident = get_object_or_404(Incident, uid=uid)
    form = StatusForm(request.POST)
    if form.is_valid():
        change_status(incident, form.cleaned_data["status"], request.user, form.cleaned_data["comment"])
        log_action(request, "incident.status", incident, f"{incident.uid} → {incident.get_status_display()}")
        messages.success(request, f"Statut de {incident.uid} : {incident.get_status_display()}.")
    return redirect(incident.get_absolute_url())


@login_required
def incident_report(request):
    form = ManualReportForm(request.POST or None, request.FILES or None,
                            initial={"module": request.GET.get("module", ""), "source_code": request.GET.get("source", "")})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        description = d["description"].strip()
        incident = record_incident(
            module=d["module"], category="signalement", severity=d["severity"], origin="utilisateur",
            source_code=d["source_code"].strip(), title=description.splitlines()[0][:200], message=description,
            operation="Signalement manuel", technical_code="manuel", group=False,
            context={"page_precedente": request.POST.get("from_path", "")[:200]},
        )
        if incident is None:
            messages.error(request, "Le signalement n'a pas pu être enregistré.")
            return redirect("incidents:list")
        incident.is_manual = True
        incident.steps = redact(d["steps"])
        incident.expected = redact(d["expected"])
        incident.obtained = redact(d["obtained"])
        incident.reported_by = request.user
        if d["screenshot"]:
            incident.screenshot = d["screenshot"]
        incident.save()
        messages.success(request, f"Signalement enregistré sous l'identifiant {incident.uid}.")
        return redirect(incident.get_absolute_url())
    return render(request, "incidents/report_form.html", {"form": form, "from_path": request.GET.get("from", "")})


@login_required
def incident_screenshot(request, uid):
    incident = get_object_or_404(Incident, uid=uid)
    if not incident.screenshot:
        raise Http404
    content_type = mimetypes.guess_type(incident.screenshot.name)[0] or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise Http404
    response = FileResponse(incident.screenshot.open("rb"), content_type=content_type)
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def incident_analysis(request):
    """Regroupements simples (§3.9) : récurrences, sources instables, connecteurs en échec, versions, réapparitions."""
    since = timezone.now() - datetime.timedelta(days=int(request.GET.get("jours", 30) or 30))
    auto = Incident.objects.filter(is_manual=False)
    recurrent = auto.filter(occurrence_count__gt=1).order_by("-occurrence_count")[:10]
    unstable = (auto.filter(category="indisponibilite", last_seen_at__gte=since).exclude(source_code="")
                .values("source_code").annotate(n=Sum("occurrence_count"), k=Count("pk")).order_by("-n")[:10])
    failing = (auto.filter(category__in=("erreur_technique", "reponse_illisible", "erreur_traitement", "configuration"),
                           last_seen_at__gte=since).exclude(source_code="")
               .values("source_code").annotate(n=Sum("occurrence_count"), k=Count("pk")).order_by("-n")[:10])
    by_version = (Incident.objects.values("first_seen_version").annotate(n=Count("pk"))
                  .order_by("-first_seen_version"))
    from django.conf import settings

    new_in_version = Incident.objects.filter(first_seen_version=settings.APP_VERSION).order_by("-last_seen_at")[:10]
    reappeared = Incident.objects.filter(reappeared_count__gt=0).order_by("-last_seen_at")[:10]
    network_bursts = _network_bursts(since)
    return render(request, "incidents/analysis.html", {
        "recurrent": recurrent, "unstable": unstable, "failing": failing, "by_version": by_version,
        "new_in_version": new_in_version, "reappeared": reappeared, "days": (timezone.now() - since).days,
        "network_bursts": network_bursts, "origin_help": ORIGIN_HELP,
    })


def _network_bursts(since):
    """Moments où plusieurs sources différentes ont échoué dans la même minute : cause locale probable."""
    from .models import IncidentOccurrence

    rows = (IncidentOccurrence.objects.filter(occurred_at__gte=since, incident__category="indisponibilite")
            .values_list("occurred_at", "incident__source_code"))
    buckets = {}
    for at, source in rows:
        key = timezone.localtime(at).replace(second=0, microsecond=0)
        buckets.setdefault(key, set()).add(source)
    return sorted(((k, sorted(v)) for k, v in buckets.items() if len(v) >= 2), reverse=True)[:10]


@login_required
def incident_export(request, uid=None):
    """Aperçu contrôlé puis téléchargement du rapport de diagnostic (un incident ou la sélection filtrée)."""
    if uid:
        incidents = [get_object_or_404(Incident, uid=uid)]
        filters = {"identifiant": uid}
    else:
        _, qs, filters = _filtered(request)
        incidents = list(qs[:100])
    form = ExportForm(request.GET or None)
    fmt = form.cleaned_data["format"] if form.is_valid() else "md"
    hide = form.cleaned_data.get("hide_terms", False) if form.is_valid() else False
    content = (report.build_json(incidents, hide_terms=hide, filters=filters) if fmt == "json"
               else report.build_markdown(incidents, hide_terms=hide, filters=filters))
    if request.GET.get("download"):
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
        name = f"diagnostic-{uid or 'journal'}-{stamp}.{'json' if fmt == 'json' else 'md'}"
        response = HttpResponse(content, content_type=("application/json" if fmt == "json" else "text/markdown")
                                + "; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        log_action(request, "incident.export", incidents[0] if uid else None, name)
        return response
    query = request.GET.copy()
    query["download"] = "1"
    return render(request, "incidents/export_preview.html", {
        "content": content, "form": form, "uid": uid, "count": len(incidents), "download_query": query.urlencode(),
        "fmt": fmt, "hide": hide,
    })
