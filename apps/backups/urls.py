from django.urls import path

from . import views

app_name = "backups"

urlpatterns = [
    path("", views.backup_list, name="list"),
    path("creer/", views.backup_create, name="create"),
    path("<int:pk>/verifier/", views.backup_verify, name="verify"),
    path("<int:pk>/telecharger/", views.backup_download, name="download"),
    path("<int:pk>/restaurer/", views.backup_restore, name="restore"),
]
