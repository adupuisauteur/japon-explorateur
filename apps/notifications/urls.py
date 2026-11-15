from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("fenetres/", views.popups, name="popups"),
    path("preferences/", views.preferences, name="preferences"),
    path("essai/", views.send_test, name="test"),
    path("<int:pk>/lue/", views.mark_read, name="mark_read"),
    path("<int:pk>/ouvrir/", views.open_notification, name="open"),
]
