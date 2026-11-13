"""Gestionnaire de mises à jour : synchronisations, imports et zone de validation (§9)."""
from django.conf import settings
from django.db import models
from django.urls import reverse

JOB_STATUS = [
    ("pending", "En attente"),
    ("running", "En cours"),
    ("review", "À valider"),
    ("applied", "Intégré"),
    ("partially_applied", "Partiellement intégré"),
    ("cancelled", "Annulé"),
    ("failed", "Échec"),
    ("done", "Terminé"),
]


class SyncJob(models.Model):
    KINDS = [("incremental", "Synchronisation incrémentale"), ("full", "Synchronisation complète"),
             ("refresh", "Actualisation des notices connues"), ("test", "Test du connecteur")]

    catalogue = models.ForeignKey("catalog.Catalogue", related_name="sync_jobs", on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=KINDS)
    status = models.CharField(max_length=30, choices=JOB_STATUS, default="pending")
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    scheduled = models.BooleanField("Lancement planifié", default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    cursor = models.CharField("Curseur / jeton de reprise", max_length=500, blank=True)
    counts = models.JSONField(default=dict, blank=True)
    report = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-pk"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.catalogue}"

    def get_absolute_url(self):
        return reverse("updates:sync_detail", args=[self.pk])


class ImportJob(models.Model):
    FORMATS = [("csv", "CSV"), ("tsv", "TSV"), ("xlsx", "Excel (XLSX)"), ("json", "JSON"),
               ("json_export", "JSON exporté par l'application"), ("xml", "XML générique"),
               ("marcxml", "MARCXML"), ("dc", "Dublin Core (OAI-DC)")]
    DUPLICATE_STRATEGIES = [
        ("version", "Mettre à jour avec historisation (recommandé)"),
        ("skip", "Ignorer les notices déjà présentes"),
        ("review", "Tout présenter pour validation sélective"),
    ]

    catalogue = models.ForeignKey("catalog.Catalogue", related_name="import_jobs", on_delete=models.PROTECT)
    file = models.ForeignKey("catalog.StoredFile", null=True, on_delete=models.SET_NULL)
    file_name = models.CharField(max_length=300)
    file_sha256 = models.CharField(max_length=64, blank=True)
    format = models.CharField(max_length=20, choices=FORMATS, blank=True)
    encoding = models.CharField(max_length=30, blank=True)
    delimiter = models.CharField(max_length=5, blank=True)
    sheet_name = models.CharField(max_length=100, blank=True)
    columns = models.JSONField(default=list, blank=True)
    sample = models.JSONField(default=list, blank=True)
    mapping = models.JSONField("Correspondance colonnes → champs", default=dict, blank=True)
    preset = models.CharField(max_length=40, blank=True)
    duplicate_strategy = models.CharField(max_length=20, choices=DUPLICATE_STRATEGIES, default="version")
    dataset_label = models.CharField("Libellé du jeu de données", max_length=200, blank=True)
    archive_source = models.BooleanField("Archiver le fichier source", default=True)
    status = models.CharField(max_length=30, choices=JOB_STATUS, default="pending")
    total_rows = models.PositiveIntegerField(default=0)
    counts = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    unknown_columns = models.JSONField(default=list, blank=True)
    report = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-pk"]

    def __str__(self):
        return f"Import {self.file_name}"

    def get_absolute_url(self):
        return reverse("updates:import_detail", args=[self.pk])


class IncomingRecord(models.Model):
    """Notice entrante en attente de validation (rapport avant intégration, §9.5)."""

    COMPARISON = [("new", "Nouvelle"), ("modified", "Modifiée"), ("unchanged", "Inchangée"),
                  ("missing", "Non retrouvée à la source"), ("error", "Erreur"), ("possible_duplicate", "Doublon potentiel")]
    DECISIONS = [("pending", "En attente"), ("accept", "À intégrer"), ("reject", "Rejetée"), ("hold", "Mise en attente"),
                 ("applied", "Intégrée")]

    import_job = models.ForeignKey(ImportJob, null=True, blank=True, related_name="incoming", on_delete=models.CASCADE)
    sync_job = models.ForeignKey(SyncJob, null=True, blank=True, related_name="incoming", on_delete=models.CASCADE)
    row_number = models.PositiveIntegerField(null=True, blank=True)
    source_id = models.CharField(max_length=300, blank=True)
    data = models.JSONField(default=dict)
    raw = models.JSONField(default=dict, blank=True)
    raw_format = models.CharField(max_length=30, blank=True)
    comparison = models.CharField(max_length=20, choices=COMPARISON)
    changed_fields = models.JSONField(default=list, blank=True)
    matched_record = models.ForeignKey("catalog.Record", null=True, blank=True, on_delete=models.SET_NULL)
    duplicate_hint = models.CharField(max_length=500, blank=True)
    error = models.CharField(max_length=500, blank=True)
    warnings = models.JSONField("Avertissements (troncatures, valeurs ignorées)", default=list, blank=True)
    decision = models.CharField(max_length=20, choices=DECISIONS, default="pending")

    class Meta:
        ordering = ["row_number", "pk"]

    @property
    def title(self):
        return self.data.get("original_title") or "(sans titre)"
