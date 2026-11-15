"""Notifications (2.0.0, lot 5 ; cahier § 8 ; audit § 5.4).

Un mécanisme unique pour les fins de tâches et les alertes de dysfonctionnement. Canal « dans l'application »
seulement en 2.0.0 ; le champ `channel` prépare le courriel et les notifications du navigateur (versions
suivantes, jamais activés par défaut).
"""
from django.conf import settings
from django.db import models

EVENT_TYPES = [
    ("task_done", "Tâche terminée"),
    ("task_errors", "Tâche terminée avec des erreurs, ou en échec"),
    ("task_paused", "Tâche interrompue ou en pause"),
    ("incident", "Dysfonctionnement (administrateur)"),
    ("test", "Notification d'essai"),
]
#: Types que chaque utilisateur peut activer ou désactiver (l'essai est toujours remis : il est demandé).
CONFIGURABLE = ("task_done", "task_errors", "task_paused", "incident")
ADMIN_ONLY = ("incident",)

SEVERITIES = [
    ("info", "Information"),
    ("success", "Réussite"),
    ("warning", "Avertissement"),
    ("error", "Erreur"),
    ("critical", "Critique"),
]
CHANNELS = [("app", "Dans l'application")]

#: Seuil par défaut des fenêtres de dysfonctionnement (gravité des incidents, apps.incidents).
DEFAULT_INCIDENT_THRESHOLD = "error"
INCIDENT_THRESHOLDS = [("info", "Information et plus"), ("warning", "Avertissement et plus"),
                       ("error", "Erreur et plus"), ("critical", "Critique seulement")]


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE)
    event_type = models.CharField("Type", max_length=20, choices=EVENT_TYPES)
    severity = models.CharField("Gravité", max_length=10, choices=SEVERITIES, default="info")
    title = models.CharField("Titre", max_length=200)
    body = models.CharField("Texte", max_length=1000, blank=True)
    link = models.CharField("Lien", max_length=500, blank=True)
    # Regroupement : une seule notification non lue par groupe (un incident, une tâche).
    group_key = models.CharField(max_length=120, blank=True, db_index=True)
    channel = models.CharField("Canal", max_length=10, choices=CHANNELS, default="app")
    created_at = models.DateTimeField("Créée le", auto_now_add=True)
    read_at = models.DateTimeField("Lue le", null=True, blank=True)
    popup_shown_at = models.DateTimeField("Fenêtre affichée le", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["recipient", "read_at"]),
                   models.Index(fields=["recipient", "popup_shown_at"])]

    def __str__(self):
        return f"{self.recipient} — {self.title}"

    @property
    def is_read(self):
        return self.read_at is not None


class NotificationPreference(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notification_preferences",
                             on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    channel = models.CharField(max_length=10, choices=CHANNELS, default="app")
    enabled = models.BooleanField(default=True)
    # Seuil de gravité des fenêtres de dysfonctionnement (type « incident » seulement).
    min_severity = models.CharField(max_length=10, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "event_type", "channel"],
                                               name="unique_notification_preference")]

    def __str__(self):
        return f"{self.user} — {self.event_type} ({'oui' if self.enabled else 'non'})"
