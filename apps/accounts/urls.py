from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.LoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("premier-demarrage/", views.first_run, name="first_run"),
    path("mon-compte/", views.profile, name="profile"),
    path("utilisateurs/", views.users, name="users"),
    path("utilisateurs/nouveau/", views.user_create, name="user_create"),
    path("utilisateurs/<int:pk>/", views.user_edit, name="user_edit"),
    path("utilisateurs/<int:pk>/anonymiser/", views.user_anonymize, name="user_anonymize"),
]
