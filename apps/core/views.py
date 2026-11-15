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
from django.views.decorators.http import require_POST

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
    """Page mise en cache par le navigateur, affichée quand le serveur J-ed ne répond pas.

    2.0.0 : page autonome, sans menu ni numéro de version, pour ne pas laisser croire qu'une ancienne version
    est en service (constat du 14 novembre 2026).
    """
    return render(request, "core/offline.html")


@cache_control(no_store=True)
def health(request):
    """Contrôle de santé de Docker : le serveur répond et la base est joignable. Aucune donnée affichée."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 — le type d'erreur suffit au diagnostic
        return HttpResponse(f"base injoignable : {type(exc).__name__}\n", status=503,
                            content_type="text/plain; charset=utf-8")
    return HttpResponse("ok\n", content_type="text/plain; charset=utf-8")


# Composants livrés avec l'interface (dossier static/vendor) et principaux composants du serveur.
ABOUT_COMPONENTS = [
    ("Django", "cadre de l'application"), ("PostgreSQL", "base de données"),
    ("Celery et Redis", "tâches en arrière-plan"), ("HTMX", "interface, licence BSD zéro clause"),
    ("Bootstrap et Bootstrap Icons", "présentation, licence MIT"),
    ("ReportLab et python-docx", "exports PDF et Word"), ("Argos Translate", "traduction hors ligne (facultative)"),
]


@login_required
def about(request):
    return render(request, "core/about.html", {
        "instance_name": AppSettings.get().instance_name,
        "schema_version": settings.DATA_SCHEMA_VERSION,
        "components": ABOUT_COMPONENTS,
    })


_SHELL_FILES = ("css/app.css", "js/app.js", "vendor/bootstrap/bootstrap.min.css",
                "vendor/bootstrap/bootstrap.bundle.min.js", "vendor/htmx/htmx.min.js",
                "vendor/bootstrap-icons/bootstrap-icons.min.css")
_shell_fingerprint = None


def shell_fingerprint():
    """Empreinte des fichiers de l'interface mis en cache par le navigateur.

    2.0.0 (lot 5) : le cache du service worker portait seulement le numéro de version ; entre deux livraisons
    de la même version (lots de la 2.0.0), le navigateur gardait l'ancien app.js et l'ancien app.css. Le nom du
    cache change désormais dès que l'un de ces fichiers change.
    """
    global _shell_fingerprint
    if _shell_fingerprint is None or settings.DEBUG:
        import hashlib

        from django.contrib.staticfiles import finders

        digest = hashlib.sha256(settings.APP_VERSION.encode())
        for name in _SHELL_FILES:
            path = finders.find(name)
            if path:
                with open(path, "rb") as fh:
                    digest.update(fh.read())
        _shell_fingerprint = digest.hexdigest()[:12]
    return _shell_fingerprint


@cache_control(no_cache=True)
def service_worker(request):
    content = render_to_string("core/sw.js", {"version": f"{settings.APP_VERSION}-{shell_fingerprint()}",
                                              "static_prefix": settings.STATIC_URL})
    response = HttpResponse(content, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


def manifest(request):
    data = {
        "name": settings.APP_NAME,
        "short_name": settings.APP_NAME,
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
def installation_state(request):
    """2.0.0 : état de l'installation (version, base, workers, planificateur, Redis, Argos, sauvegardes…)."""
    from . import health

    results = health.collect()
    return render(request, "core/state.html", {
        "results": results, "overall": health.overall(results), "level_labels": health.LEVEL_LABELS,
        "diagnostic": health.diagnostic_text(results),
    })


@admin_required
@require_POST
def argos_selftest(request):
    from apps.translation.tasks import run_argos_selftest

    run_argos_selftest.delay()
    log_action(request, "argos.selftest", None, "Traduction d'essai Argos demandée")
    messages.info(request, "Traduction d'essai d'Argos lancée : le résultat s'affiche ici dans quelques secondes "
                           "(rechargez la page).")
    return redirect("core:state")


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
