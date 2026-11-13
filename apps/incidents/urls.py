from django.urls import path

from . import views

app_name = "incidents"

urlpatterns = [
    path("", views.incident_list, name="list"),
    path("signaler/", views.incident_report, name="report"),
    path("analyse/", views.incident_analysis, name="analysis"),
    path("export/", views.incident_export, name="export_list"),
    path("<str:uid>/", views.incident_detail, name="detail"),
    path("<str:uid>/statut/", views.incident_status, name="status"),
    path("<str:uid>/export/", views.incident_export, name="export"),
    path("<str:uid>/capture/", views.incident_screenshot, name="screenshot"),
]
