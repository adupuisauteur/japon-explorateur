from django.urls import path

from . import views

app_name = "ai"

urlpatterns = [
    path("preferences/", views.preferences, name="preferences"),
    path("preferences/<int:pk>/", views.profile_action, name="profile_action"),
    path("fournisseurs/", views.providers, name="providers"),
    path("fournisseurs/<slug:provider>/", views.provider_save, name="provider_save"),
    path("lancer/", views.launch, name="launch"),
    path("lancer/bibliotheque/", views.launch_from_session, name="launch_from_session"),
    path("taches/", views.tasks, name="tasks"),
    path("taches/<int:pk>/", views.task_detail, name="task"),
    path("tarifs/", views.prices, name="prices"),
]
