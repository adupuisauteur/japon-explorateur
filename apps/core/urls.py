from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("hors-ligne/", views.offline, name="offline"),
    path("sante/", views.health, name="health"),
    path("a-propos/", views.about, name="about"),
    path("administration/", views.admin_hub, name="admin_hub"),
    path("administration/etat/", views.installation_state, name="state"),
    path("administration/etat/test-argos/", views.argos_selftest, name="argos_selftest"),
    path("administration/parametres/", views.app_settings, name="settings"),
    path("administration/journal/", views.audit_log, name="audit_log"),
]
