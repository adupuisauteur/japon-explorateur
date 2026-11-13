from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

admin.site.site_header = "Japon — Explorateur documentaire (gestion interne)"
admin.site.site_title = "Gestion interne"

urlpatterns = [
    path("", include("apps.core.urls")),
    path("comptes/", include("apps.accounts.urls")),
    path("notices/", include("apps.catalog.urls")),
    path("sources/", include("apps.connectors.urls")),
    path("recherche/", include("apps.searching.urls")),
    path("mises-a-jour/", include("apps.updates.urls")),
    path("bibliotheque/", include("apps.library.urls")),
    path("exports/", include("apps.exports.urls")),
    path("ia/", include("apps.ai.urls")),
    path("administration/sauvegardes/", include("apps.backups.urls")),
    path("journal/", include("apps.incidents.urls")),
    path("gestion-interne/", admin.site.urls),
    # PWA : le service worker doit être servi à la racine pour couvrir tout le site.
    path("sw.js", core_views.service_worker, name="service_worker"),
    path("manifest.webmanifest", core_views.manifest, name="manifest"),
]
