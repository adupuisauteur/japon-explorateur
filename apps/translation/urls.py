from django.urls import path

from . import views
from .views import engines, jobs

app_name = "translation"

urlpatterns = [
    path("", views.home, name="home"),
    path("moteurs/", engines.engines, name="engines"),
    path("moteurs/choix/", engines.preferences_save, name="preferences_save"),
    path("moteurs/<slug:code>/", engines.engine_save, name="engine_save"),
    path("taches/", jobs.job_list, name="job_list"),
    path("taches/<int:pk>/", jobs.job_detail, name="job_detail"),
    path("taches/<int:pk>/action/", jobs.job_action, name="job_action"),
]
