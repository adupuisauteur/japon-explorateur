from django.urls import path

from . import views
from .views import engines

app_name = "translation"

urlpatterns = [
    path("", views.home, name="home"),
    path("moteurs/", engines.engines, name="engines"),
    path("moteurs/choix/", engines.preferences_save, name="preferences_save"),
    path("moteurs/<slug:code>/", engines.engine_save, name="engine_save"),
]
