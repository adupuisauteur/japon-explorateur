from django.urls import path

from . import views

app_name = "help"

urlpatterns = [
    path("", views.index, name="index"),
    path("recherche/", views.search, name="search"),
    path("historique-des-versions/", views.history, name="history"),
    path("<slug:slug>/", views.page, name="page"),
]
