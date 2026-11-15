from django.conf import settings
from django.db import models


class AppSettings(models.Model):
    """Paramètres généraux de l'instance (singleton, non secrets)."""

    SEARCH_MODES = [
        ("auto", "Automatique"),
        ("selective", "Sélectif"),
        ("manual", "Manuel / temporaire"),
    ]

    instance_name = models.CharField("Nom de l'instance", max_length=200, default="J-ed")
    default_search_mode = models.CharField(
        "Mode d'enregistrement par défaut", max_length=20, choices=SEARCH_MODES, default="selective"
    )
    temporary_session_days = models.PositiveIntegerField(
        "Durée de conservation des sessions temporaires (jours)", default=30
    )
    backup_enabled = models.BooleanField("Sauvegarde quotidienne automatique", default=True)
    backup_retention = models.PositiveIntegerField("Nombre de sauvegardes conservées", default=14)
    export_default_author = models.CharField("Préparateur par défaut des exports", max_length=200, blank=True)
    export_default_header = models.CharField("En-tête par défaut des exports", max_length=300, blank=True)
    export_default_footer = models.CharField(
        "Pied de page par défaut des exports", max_length=300, blank=True,
        default="Document de travail — vérifier les notices auprès des catalogues d'origine",
    )
    setup_completed = models.BooleanField(default=False)
    # 2.0.0 (décision D4) : la simulation d'Argos n'est plus un repli automatique. Elle n'existe que si
    # l'administrateur l'active explicitement, pour une démonstration sans le service ni ses paquets.
    argos_demo_mode = models.BooleanField(
        "Argos : mode démonstration (traductions simulées)", default=False,
        help_text="Sans le service Argos ou ses paquets, renvoie le texte original précédé de la mention "
                  "« Simulation ». Désactivé : une traduction Argos impossible est arrêtée, jamais simulée.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres de l'instance"
        verbose_name_plural = "Paramètres de l'instance"

    def __str__(self):
        return self.instance_name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AuditLog(models.Model):
    """Journal des actions sensibles. Ne jamais y écrire de secret."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=80, blank=True)
    summary = models.CharField(max_length=500, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Entrée du journal"
        verbose_name_plural = "Journal des actions"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"


class ServiceCheck(models.Model):
    """2.0.0 : dernier résultat d'un contrôle de fonctionnement (page « État de l'installation »).

    Exemples : « planificateur » (signe de vie envoyé par Celery beat et exécuté par un worker),
    « argos_essai » (traduction d'une phrase fictive après l'installation d'un paquet). Aucun texte réel.
    """

    name = models.CharField("Contrôle", max_length=40, unique=True)
    ok = models.BooleanField(default=False)
    message = models.CharField(max_length=500, blank=True)
    data = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField("Date du contrôle")

    class Meta:
        verbose_name = "contrôle de fonctionnement"

    def __str__(self):
        return f"{self.name} : {'réussi' if self.ok else 'en échec'}"

    @classmethod
    def record(cls, name, ok, message="", **data):
        from django.utils import timezone

        obj, _ = cls.objects.update_or_create(name=name, defaults={
            "ok": ok, "message": message[:500], "data": data, "checked_at": timezone.now()})
        return obj
