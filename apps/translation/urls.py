from django.urls import path

from . import views
from .views import documents, engines, jobs, projects, records

app_name = "translation"

urlpatterns = [
    path("", views.home, name="home"),
    path("moteurs/", engines.engines, name="engines"),
    path("moteurs/choix/", engines.preferences_save, name="preferences_save"),
    path("moteurs/<slug:code>/", engines.engine_save, name="engine_save"),
    path("taches/", jobs.job_list, name="job_list"),
    path("taches/<int:pk>/", jobs.job_detail, name="job_detail"),
    path("taches/<int:pk>/action/", jobs.job_action, name="job_action"),
    path("notices/preparer/", records.records_prepare, name="records_prepare"),
    path("notices/decision/<int:pk>/", records.record_decide, name="record_decide"),
    path("notices/<str:record_id>/", records.record_translations, name="record_translations"),
    path("notices/<str:record_id>/copier/", projects.copy_record, name="copy_record"),
    path("projets/", projects.project_list, name="project_list"),
    path("projets/nouveau/", projects.project_create, name="project_create"),
    path("projets/<int:pk>/", projects.project_detail, name="project_detail"),
    path("projets/<int:pk>/modifier/", projects.project_edit, name="project_edit"),
    path("projets/<int:pk>/supprimer/", projects.project_delete, name="project_delete"),
    path("projets/<int:project_pk>/documents/nouveau/", documents.document_add, name="document_add"),
    path("documents/<int:pk>/", documents.document_workbench, name="document_workbench"),
    path("documents/<int:pk>/lot/", documents.document_bulk, name="document_bulk"),
    path("documents/<int:pk>/publier/", documents.document_publish, name="document_publish"),
    path("segments/<int:pk>/", documents.segment_detail, name="segment_detail"),
    path("segments/<int:pk>/action/", documents.segment_action, name="segment_action"),
    path("versions/<int:pk>/action/", documents.version_action, name="version_action"),
]
