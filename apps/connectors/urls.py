from django.urls import path

from . import views

app_name = "connectors"

urlpatterns = [
    path("", views.source_list, name="list"),
    path("<slug:code>/", views.source_detail, name="detail"),
    path("<slug:code>/tester/", views.source_test, name="test"),
    path("<slug:code>/appliquer-detection/", views.apply_detection, name="apply_detection"),
]
