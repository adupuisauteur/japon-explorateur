"""Profils d'export, exports générés et fichiers associés (§12)."""
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse

FORMATS = [
    ("docx", "Word (DOCX)"),
    ("pdf", "PDF"),
    ("txt", "Texte (TXT)"),
    ("json", "JSON"),
    ("csv", "CSV"),
    ("html", "Site HTML autonome (ZIP)"),
    ("zip", "Archive complète (ZIP)"),
]

PRESETS = [
    ("bibliography", "Bibliographie"),
    ("inventory", "Inventaire complet"),
    ("dossier", "Dossier historique"),
    ("synthesis", "Synthèse"),
    ("import", "Import bibliographique"),
    ("html_doc", "Documentation HTML"),
]

SCOPES = [
    ("selection", "Sélection de notices"),
    ("session", "Résultats d'une session"),
    ("library", "Bibliothèque"),
    ("collection", "Dossier documentaire complet"),
]


class ExportProfile(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="export_profiles", on_delete=models.CASCADE)
    name = models.CharField("Nom", max_length=200)
    preset = models.CharField("Modèle", max_length=20, choices=PRESETS, default="bibliography")
    format = models.CharField(max_length=10, choices=FORMATS, default="docx")
    options = models.JSONField("Options (champs, présentation, en-têtes…)", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExportJob(models.Model):
    STATUS = [("draft", "Préparation"), ("pending", "En file d'attente"), ("running", "Génération"),
              ("done", "Généré"), ("failed", "Échec")]

    export_uid = models.CharField("Identifiant de l'export", max_length=40, unique=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="exports", on_delete=models.CASCADE)
    profile = models.ForeignKey(ExportProfile, null=True, blank=True, on_delete=models.SET_NULL)
    preset = models.CharField(max_length=20, choices=PRESETS, default="bibliography")
    format = models.CharField(max_length=10, choices=FORMATS, default="docx")
    scope = models.CharField(max_length=20, choices=SCOPES)
    scope_params = models.JSONField(default=dict, blank=True)
    title = models.CharField("Titre du document", max_length=300)
    subtitle = models.CharField("Sous-titre", max_length=300, blank=True)
    subject = models.CharField("Sujet / objet de l'export", max_length=500, blank=True)
    author = models.CharField("Auteur / préparateur", max_length=200, blank=True)
    header_text = models.CharField("En-tête", max_length=300, blank=True)
    footer_text = models.CharField("Pied de page", max_length=300, blank=True)
    options = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    generated_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField("Métadonnées de traçabilité", default=dict, blank=True)
    data_fingerprint = models.CharField(max_length=64, blank=True)
    error = models.TextField(blank=True)
    regenerated_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.export_uid:
            self.export_uid = f"EXP-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_format_display()})"

    def get_absolute_url(self):
        return reverse("exports:detail", args=[self.pk])

    @property
    def main_file(self):
        return self.files.filter(role="main").first()


class ExportFile(models.Model):
    ROLES = [("main", "Fichier principal"), ("manifest", "Manifeste"), ("schema", "Schéma / documentation")]

    job = models.ForeignKey(ExportJob, related_name="files", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES, default="main")
    path = models.CharField(max_length=500)
    name = models.CharField(max_length=300)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
