"""Bibliothèque personnelle, dossiers documentaires, annotations, partage et corrections (§10, §13)."""
from django.conf import settings
from django.db import models
from django.urls import reverse

VISIBILITY = [
    ("private", "Privé"),
    ("shared", "Partagé avec des utilisateurs"),
    ("common", "Commun à l'espace"),
]


class Tag(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="tags", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)

    class Meta:
        unique_together = [("owner", "name")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class LibraryEntry(models.Model):
    VERIFICATION = [("unverified", "Non vérifiée"), ("in_progress", "En cours"), ("verified", "Vérifiée"),
                    ("doubtful", "Douteuse")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="library", on_delete=models.CASCADE)
    record = models.ForeignKey("catalog.Record", related_name="library_entries", on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    favorite = models.BooleanField("Favori", default=False)
    verification = models.CharField("État de vérification", max_length=20, choices=VERIFICATION,
                                    default="unverified")
    tags = models.ManyToManyField(Tag, blank=True)
    source_session = models.ForeignKey("searching.SearchSession", null=True, blank=True, on_delete=models.SET_NULL)
    offline = models.BooleanField("Disponible hors ligne", default=False)

    class Meta:
        unique_together = [("user", "record")]
        ordering = ["-added_at"]
        verbose_name = "entrée de bibliothèque"


class Collection(models.Model):
    """Dossier documentaire (ex. « Musashi — sources anciennes »)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="collections", on_delete=models.CASCADE)
    title = models.CharField("Titre", max_length=300)
    description = models.TextField("Description", blank=True)
    keywords = models.CharField("Mots-clés", max_length=500, blank=True)
    visibility = models.CharField("Confidentialité", max_length=20, choices=VISIBILITY, default="private")
    shared_with = models.ManyToManyField(settings.AUTH_USER_MODEL, through="CollectionShare",
                                         related_name="shared_collections", blank=True)
    methodology = models.TextField("Méthodologie", blank=True)
    created_from_session = models.ForeignKey("searching.SearchSession", null=True, blank=True, related_name="+",
                                             on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "dossier"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("library:collection_detail", args=[self.pk])

    def can_view(self, user):
        if user.is_admin_role or self.owner_id == user.pk:
            return True
        if self.visibility == "common":
            return True
        return self.visibility == "shared" and self.shares.filter(user=user).exists()

    def can_edit(self, user):
        if not user.can_edit:
            return False
        if user.is_admin_role or self.owner_id == user.pk:
            return True
        return self.visibility == "shared" and self.shares.filter(user=user, can_edit=True).exists()

    @classmethod
    def visible_to(cls, user):
        if user.is_admin_role:
            return cls.objects.all()
        return cls.objects.filter(models.Q(owner=user) | models.Q(visibility="common")
                                  | models.Q(visibility="shared", shares__user=user)).distinct()


class CollectionShare(models.Model):
    collection = models.ForeignKey(Collection, related_name="shares", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    can_edit = models.BooleanField("Peut modifier", default=False)

    class Meta:
        unique_together = [("collection", "user")]


class CollectionSection(models.Model):
    collection = models.ForeignKey(Collection, related_name="sections", on_delete=models.CASCADE)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.CASCADE)
    title = models.CharField("Titre", max_length=300)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return self.title


class CollectionRecord(models.Model):
    collection = models.ForeignKey(Collection, related_name="items", on_delete=models.CASCADE)
    section = models.ForeignKey(CollectionSection, null=True, blank=True, related_name="items",
                                on_delete=models.SET_NULL)
    record = models.ForeignKey("catalog.Record", related_name="collection_items", on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    note = models.TextField("Note de dossier", blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("collection", "record")]
        ordering = ["section__order", "order", "pk"]


class Annotation(models.Model):
    VISIBILITY = [("private", "Note privée"), ("shared", "Note partagée"), ("editorial", "Commentaire éditorial")]
    LOCATOR = [("", "—"), ("page", "Page"), ("folio", "Folio"), ("image", "Image"), ("passage", "Passage")]

    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="annotations", on_delete=models.CASCADE)
    record = models.ForeignKey("catalog.Record", null=True, blank=True, related_name="annotations",
                               on_delete=models.CASCADE)
    work = models.ForeignKey("catalog.Work", null=True, blank=True, related_name="annotations", on_delete=models.CASCADE)
    copy = models.ForeignKey("catalog.Copy", null=True, blank=True, related_name="annotations", on_delete=models.CASCADE)
    collection = models.ForeignKey(Collection, null=True, blank=True, related_name="annotations",
                                   on_delete=models.CASCADE)
    visibility = models.CharField(max_length=20, choices=VISIBILITY, default="private")
    locator_type = models.CharField("Repère", max_length=20, choices=LOCATOR, blank=True)
    locator = models.CharField("Référence (page, folio, image…)", max_length=200, blank=True)
    body = models.TextField("Note")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="+",
                                   on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-updated_at"]

    @classmethod
    def visible_to(cls, user):
        if user.is_admin_role:
            return cls.objects.all()
        return cls.objects.filter(models.Q(author=user) | models.Q(visibility__in=["shared", "editorial"]))


class CorrectionProposal(models.Model):
    """Proposition de correction sur la couche normalisée ou éditoriale (jamais sur la donnée source)."""

    FIELDS = [
        ("translated_title", "Titre traduit"),
        ("description_translation", "Traduction de la description"),
        ("period", "Période"),
        ("document_type", "Type documentaire (normalisé)"),
        ("material_type", "Support (normalisé)"),
        ("composition_year_start", "Composition : année de début"),
        ("composition_year_end", "Composition : année de fin"),
        ("copy_year_start", "Exemplaire : année de début"),
        ("copy_year_end", "Exemplaire : année de fin"),
        ("language", "Langue"),
    ]
    STATUS = [("proposed", "Proposée"), ("accepted", "Acceptée"), ("rejected", "Rejetée")]

    record = models.ForeignKey("catalog.Record", related_name="corrections", on_delete=models.CASCADE)
    field = models.CharField("Champ", max_length=40, choices=FIELDS)
    current_value = models.TextField(blank=True)
    proposed_value = models.TextField("Valeur proposée")
    justification = models.TextField("Justification")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="corrections", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS, default="proposed")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="+",
                                    on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
