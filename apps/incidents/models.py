"""Journal des dysfonctionnements (cahier des charges 1.2.0, §3).

Un *incident* regroupe toutes les occurrences d'un même problème (même
empreinte : module, source, catégorie, code technique, message normalisé).
Chaque *occurrence* garde sa date, sa version et son identifiant de requête ;
l'*historique* conserve chaque changement de statut, y compris après correction.
Le journal est local : aucune donnée n'est envoyée à l'extérieur.
"""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

MODULES = [
    ("recherche", "Recherche documentaire"),
    ("connecteur", "Connecteurs externes"),
    ("metadonnees", "Récupération des métadonnées"),
    ("telechargement", "Téléchargement de documents"),
    ("importation", "Importation"),
    ("base_de_donnees", "Base de données"),
    ("reseau", "Réseau"),
    ("application", "Application (autre)"),
    ("interface", "Interface"),
    ("traduction", "Traduction"),  # 1.3.0
]

CATEGORIES = [
    ("indisponibilite", "Indisponibilité de la source"),
    ("erreur_technique", "Erreur technique"),
    ("reponse_illisible", "Réponse impossible à interpréter"),
    ("erreur_traitement", "Erreur de traitement des données"),
    ("configuration", "Configuration incomplète"),
    ("erreur_critique", "Erreur critique (risque pour les données)"),
    ("erreur_application", "Erreur inattendue de l'application"),
    ("avertissement_source", "Avertissement d'une source"),
    ("signalement", "Signalement manuel"),
    # 1.3.0 — module de traduction. Jamais de texte original ni traduit dans un incident.
    ("cle_refusee", "Clé de traduction refusée ou expirée"),
    ("quota_depasse", "Quota épuisé ou plafond atteint"),
    ("langue_non_prise", "Paire de langues non prise en charge"),
    ("glossaire_refuse", "Glossaire refusé par le service"),
    ("paquet_absent", "Paquet de langue Argos absent ou corrompu"),
    ("reponse_vide", "Réponse vide, identique à l'original ou mal formée"),
    ("delai_depasse", "Délai de réponse dépassé"),
    ("lot_interrompu", "Lot de traduction interrompu"),
]

SEVERITIES = [
    ("info", "Information"),
    ("warning", "Avertissement"),
    ("error", "Erreur"),
    ("critical", "Critique"),
]
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2, "critical": 3}

STATUSES = [
    ("nouveau", "Nouveau"),
    ("a_analyser", "À analyser"),
    ("en_cours", "En cours de correction"),
    ("corrige", "Corrigé"),
    ("a_verifier", "À vérifier"),
    ("cloture", "Clôturé"),
]
OPEN_STATUSES = ("nouveau", "a_analyser", "en_cours")
FIXED_STATUSES = ("corrige", "a_verifier", "cloture")

ORIGINS = [
    ("application", "Application"),
    ("connecteur", "Connecteur"),
    ("source_distante", "Source distante"),
    ("reseau", "Réseau (connexion de ce poste ou accès Internet)"),
    ("traitement", "Traitement des données"),
    ("utilisateur", "Constaté par l'utilisateur"),
]

#: Explication en langage courant, affichée dans le journal (§3.6 : compréhensible sans connaître la programmation).
ORIGIN_HELP = {
    "application": "Le problème vient probablement de l'application elle-même. Exportez le diagnostic pour le développeur.",
    "connecteur": "Le connecteur n'a pas compris la réponse de la source : la source a peut-être changé son format "
                  "ou ses paramètres. Une correction du connecteur sera sans doute nécessaire.",
    "source_distante": "Le site de l'institution n'a pas répondu correctement (serveur en panne, surchargé ou en "
                       "maintenance). En général, il suffit de réessayer plus tard.",
    "reseau": "Ce poste n'a pas pu joindre la source : vérifiez la connexion Internet, le Wi-Fi ou le VPN. "
              "Si toutes les sources échouent en même temps, la cause est presque toujours locale.",
    "traitement": "Les données ont bien été reçues, mais leur conversion a échoué. Une correction de l'application "
                  "sera nécessaire ; vos données existantes ne sont pas modifiées.",
    "utilisateur": "Problème signalé manuellement.",
}


class Incident(models.Model):
    uid = models.CharField("Identifiant", max_length=32, unique=True, editable=False)
    fingerprint = models.CharField(max_length=64, db_index=True, editable=False)
    module = models.CharField("Module", max_length=30, choices=MODULES)
    source_code = models.CharField("Source documentaire", max_length=50, blank=True, db_index=True)
    category = models.CharField("Catégorie", max_length=30, choices=CATEGORIES)
    severity = models.CharField("Gravité", max_length=10, choices=SEVERITIES, default="error")
    origin = models.CharField("Origine probable", max_length=20, choices=ORIGINS, default="application")
    operation = models.CharField("Opération en cours", max_length=300, blank=True)
    title = models.CharField("Résumé", max_length=300)
    message = models.TextField("Message d'erreur", blank=True)
    technical_code = models.CharField("Code technique", max_length=80, blank=True)
    http_status = models.PositiveSmallIntegerField("Code HTTP", null=True, blank=True)
    last_request_id = models.CharField("Dernier identifiant de requête", max_length=40, blank=True)
    context = models.JSONField("Contexte technique (expurgé)", default=dict, blank=True)
    status = models.CharField("Statut", max_length=20, choices=STATUSES, default="nouveau", db_index=True)
    first_seen_at = models.DateTimeField("Première occurrence", default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField("Dernière occurrence", default=timezone.now, db_index=True)
    occurrence_count = models.PositiveIntegerField("Nombre d'occurrences", default=1)
    first_seen_version = models.CharField("Version à la première occurrence", max_length=20)
    last_seen_version = models.CharField("Version à la dernière occurrence", max_length=20)
    fixed_at = models.DateTimeField("Corrigé le", null=True, blank=True)
    fixed_in_version = models.CharField("Corrigé dans la version", max_length=20, blank=True)
    reappeared_count = models.PositiveIntegerField("Réapparitions après correction", default=0)
    # Signalement manuel (§3.7)
    is_manual = models.BooleanField("Signalement manuel", default=False)
    steps = models.TextField("Opérations réalisées", blank=True)
    expected = models.TextField("Résultat attendu", blank=True)
    obtained = models.TextField("Résultat obtenu", blank=True)
    screenshot = models.FileField("Capture d'écran", upload_to="incidents/%Y/%m/", blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")

    class Meta:
        ordering = ["-last_seen_at"]
        verbose_name = "incident"
        indexes = [models.Index(fields=["module", "severity"]), models.Index(fields=["source_code", "category"])]

    def __str__(self):
        return f"{self.uid} — {self.title}"

    def get_absolute_url(self):
        return reverse("incidents:detail", args=[self.uid])

    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    @property
    def origin_help(self):
        return ORIGIN_HELP.get(self.origin, "")

    @property
    def severity_rank(self):
        return SEVERITY_RANK.get(self.severity, 0)


class IncidentOccurrence(models.Model):
    """Une survenue du problème (le contexte de chaque survenue reste consultable)."""

    incident = models.ForeignKey(Incident, related_name="occurrences", on_delete=models.CASCADE)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    app_version = models.CharField(max_length=20)
    request_id = models.CharField(max_length=40, blank=True)
    operation = models.CharField(max_length=300, blank=True)
    message = models.TextField(blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]


class IncidentEvent(models.Model):
    """Historique append-only : création, changements de statut, commentaires, réapparitions."""

    KINDS = [("created", "Création"), ("status", "Changement de statut"), ("comment", "Commentaire"),
             ("reappeared", "Réapparition après correction"), ("recovered", "Source de nouveau disponible")]

    incident = models.ForeignKey(Incident, related_name="events", on_delete=models.CASCADE)
    at = models.DateTimeField(default=timezone.now)
    kind = models.CharField(max_length=20, choices=KINDS)
    from_status = models.CharField(max_length=20, choices=STATUSES, blank=True)
    to_status = models.CharField(max_length=20, choices=STATUSES, blank=True)
    comment = models.TextField(blank=True)
    app_version = models.CharField(max_length=20, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")

    class Meta:
        ordering = ["at", "pk"]
