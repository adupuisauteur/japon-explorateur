from django.urls import path

from . import views

app_name = "searching"

urlpatterns = [
    path("", views.search_form, name="form"),
    path("rapide/", views.quick, name="quick"),
    path("variantes/", views.variants, name="variants"),
    path("lancer/", views.launch, name="launch"),
    path("historique/", views.history, name="history"),
    path("enregistrees/", views.saved_list, name="saved_list"),
    path("enregistrees/<int:pk>/", views.saved_detail, name="saved_detail"),
    path("enregistrees/<int:pk>/relancer/", views.saved_replay, name="saved_replay"),
    path("enregistrees/<int:pk>/supprimer/", views.saved_delete, name="saved_delete"),
    path("session/<uuid:uid>/", views.session_detail, name="session"),
    path("session/<uuid:uid>/source/<slug:code>/", views.run_source, name="run_source"),
    path("session/<uuid:uid>/resultats/", views.results, name="results"),
    path("session/<uuid:uid>/compteurs/", views.counts, name="counts"),
    path("session/<uuid:uid>/resultat/<int:pk>/", views.result_panel, name="result_panel"),
    path("session/<uuid:uid>/decision/", views.decide, name="decide"),
    path("session/<uuid:uid>/integrer/", views.integrate, name="integrate"),
    path("session/<uuid:uid>/enregistrer/", views.save_search, name="save"),
    path("session/<uuid:uid>/conserver/", views.keep_session, name="keep"),
    path("session/<uuid:uid>/supprimer/", views.delete_session, name="delete"),
]
