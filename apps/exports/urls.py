from django.urls import path

from . import views

app_name = "exports"

urlpatterns = [
    path("", views.export_list, name="list"),
    path("preparer/", views.prepare, name="prepare"),
    path("apercu/", views.preview, name="preview"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/regenerer/", views.regenerate, name="regenerate"),
    path("<int:pk>/fichiers/<int:file_pk>/", views.download, name="download"),
    path("profils/<int:pk>/supprimer/", views.profile_delete, name="profile_delete"),
]
