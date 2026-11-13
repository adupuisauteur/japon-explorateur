from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("corbeille/", views.trash, name="trash"),
    path("oeuvres/<int:pk>/", views.work_detail, name="work_detail"),
    path("editorial/<int:pk>/decision/", views.editorial_decide, name="editorial_decide"),
    path("liens/<int:pk>/decision/", views.link_decide, name="link_decide"),
    path("<str:record_id>/", views.record_detail, name="record_detail"),
    path("<str:record_id>/apercu/", views.record_panel, name="record_panel"),
    path("<str:record_id>/versions/<int:version>/", views.version_detail, name="version_detail"),
    path("<str:record_id>/traduction/", views.translation_edit, name="translation_edit"),
    path("<str:record_id>/doublons/", views.compute_duplicates, name="compute_duplicates"),
    path("<str:record_id>/statut/", views.record_status, name="record_status"),
    path("<str:record_id>/oeuvre/", views.attach_work, name="attach_work"),
]
