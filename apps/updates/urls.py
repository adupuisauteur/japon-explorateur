from django.urls import path

from . import views

app_name = "updates"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tout-lancer/", views.sync_all, name="sync_all"),
    path("source/<slug:code>/lancer/", views.sync_launch, name="sync_launch"),
    path("source/<slug:code>/suspendre/", views.toggle_pause, name="toggle_pause"),
    path("synchro/<int:pk>/", views.sync_detail, name="sync_detail"),
    path("synchro/<int:pk>/integrer/", views.sync_apply, name="sync_apply"),
    path("decisions/", views.incoming_decide, name="incoming_decide"),
    path("import/nouveau/", views.import_new, name="import_new"),
    path("import/<int:pk>/", views.import_detail, name="import_detail"),
]
