from django.conf import settings
from django.db import models


class BackupJob(models.Model):
    KINDS = [("full", "Complète (base + fichiers)"), ("db", "Base de données"), ("files", "Fichiers")]
    STATUS = [("running", "En cours"), ("done", "Terminée"), ("failed", "Échec")]

    kind = models.CharField(max_length=10, choices=KINDS, default="full")
    status = models.CharField(max_length=10, choices=STATUS, default="running")
    path = models.CharField(max_length=500, blank=True)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    method = models.CharField(max_length=40, blank=True)
    external_copy = models.CharField("Copie externe", max_length=500, blank=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    scheduled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    verified_at = models.DateTimeField("Dernière vérification d'intégrité", null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sauvegarde {self.created_at:%Y-%m-%d %H:%M}"
