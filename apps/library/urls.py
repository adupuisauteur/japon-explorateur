from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.index, name="index"),
    path("ajouter/", views.add, name="add"),
    path("retirer/", views.remove, name="remove"),
    path("lot/", views.bulk, name="bulk"),
    path("entree/<int:pk>/", views.entry_update, name="entry_update"),
    path("dossiers/", views.collections, name="collections"),
    path("dossiers/nouveau/", views.collection_create, name="collection_create"),
    path("dossiers/ajouter/", views.add_to_collection, name="add_to_collection"),
    path("dossiers/<int:pk>/", views.collection_detail, name="collection_detail"),
    path("dossiers/<int:pk>/modifier/", views.collection_edit, name="collection_edit"),
    path("dossiers/<int:pk>/supprimer/", views.collection_delete, name="collection_delete"),
    path("dossiers/<int:pk>/sections/", views.section_save, name="section_save"),
    path("dossiers/<int:pk>/elements/<int:item_pk>/", views.item_update, name="item_update"),
    path("dossiers/<int:pk>/partage/", views.share, name="share"),
    path("notes/ajouter/", views.annotation_add, name="annotation_add"),
    path("notes/<int:pk>/supprimer/", views.annotation_delete, name="annotation_delete"),
    path("corrections/", views.corrections, name="corrections"),
    path("corrections/<str:record_id>/proposer/", views.correction_add, name="correction_add"),
    path("corrections/<int:pk>/decision/", views.correction_decide, name="correction_decide"),
]
