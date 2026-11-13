from django.urls import path

from . import views

app_name = "connectors"

urlpatterns = [
    path("", views.source_list, name="list"),
    path("japansearch/bases/", views.jps_databases, name="jps_databases"),
    path("japansearch/bases/creer/", views.jps_create_source, name="jps_create_source"),
    path("<slug:code>/", views.source_detail, name="detail"),
    path("<slug:code>/tester/", views.source_test, name="test"),
    path("<slug:code>/appliquer-detection/", views.apply_detection, name="apply_detection"),
]
