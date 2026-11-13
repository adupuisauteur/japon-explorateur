import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.views.decorators.cache import cache_control

from .audit import log_action
from .forms import AppSettingsForm
from .models import AppSettings, AuditLog
from .permissions import admin_required


@login_required
def home(request):
    from apps.catalog.models import Catalogue, Record
    from apps.library.models import Collection, LibraryEntry
    from apps.searching.models import SavedSearch, SearchSession
    from apps.updates.models import ImportJob, SyncJob

    context = {
        "recent_collections": Collection.visible_to(request.user)[:5],
        "saved_searches": SavedSearch.objects.filter(owner=request.user)[:5],
        "recent_sessions": SearchSession.objects.filter(owner=request.user)[:5],
        "catalogues": Catalogue.objects.exclude(status="disabled").exclude(code="local"),
        "recent_syncs": SyncJob.objects.select_related("catalogue")[:5],
        "recent_imports": ImportJob.objects.select_related("catalogue")[:3],
        "pending_reviews": SyncJob.objects.filter(status="review").count()
                           + ImportJob.objects.filter(status="review").count(),
        "stats": {
            "records": Record.objects.exclude(record_status="deleted").count(),
            "library": LibraryEntry.objects.filter(user=request.user).count(),
            "collections": Collection.objects.filter(owner=request.user).count(),
        },
    }
    return render(request, "core/home.html", context)


def offline(request):
    return render(request, "core/offline.html")


@cache_control(no_cache=True)
def service_worker(request):
    content = render_to_string("core/sw.js", {"version": settings.APP_VERSION, "static_prefix": settings.STATIC_URL})
    response = HttpResponse(content, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


def manifest(request):
    data = {
        "name": "Japon — Explorateur documentaire",
        "short_name": "Explorateur Japon",
        "description": "Recherche, gestion et exploitation de ressources documentaires japonaises.",
        "lang": "fr",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#fbf9f6",
        "theme_color": "#8a2b23",
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/icon-maskable-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": static("icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return HttpResponse(json.dumps(data, ensure_ascii=False), content_type="application/manifest+json")


@admin_required
def admin_hub(request):
    from apps.backups.models import BackupJob
    from apps.catalog.models import Record
    from apps.library.models import CorrectionProposal

    return render(request, "core/admin_hub.html", {
        "last_backup": BackupJob.objects.filter(status="done").first(),
        "pending_corrections": CorrectionProposal.objects.filter(status="proposed").count(),
        "trash_count": Record.objects.filter(record_status="deleted").count(),
        "recent_logs": AuditLog.objects.select_related("user")[:8],
    })


@admin_required
def app_settings(request):
    obj = AppSettings.get()
    form = AppSettingsForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "settings.update", obj, "Paramètres de l'instance modifiés")
        messages.success(request, "Paramètres enregistrés.")
        return redirect("core:admin_hub")
    return render(request, "core/settings.html", {"form": form})


@admin_required
def audit_log(request):
    qs = AuditLog.objects.select_related("user")
    if request.GET.get("action"):
        qs = qs.filter(action__startswith=request.GET["action"])
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "core/audit_log.html", {"page": page})
