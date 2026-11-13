"""
Modèle documentaire (§6 et annexe A).

Distinction fondamentale : œuvre (Work) → édition (Edition) → exemplaire (Copy),
et notice publiée par un catalogue (Record). Le fichier local éventuel est un
StoredFile. Chaque notice conserve trois couches :
  - originale : `raw_data` et champs « *_original » tels que fournis par la source ;
  - normalisée : champs calculés (années, translittération, types harmonisés, texte de recherche) ;
  - éditoriale : traductions, résumés, analyses (EditorialContent), toujours avec leur origine.
"""
import hashlib
import json
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

# --------------------------------------------------------------------------- choix

DATE_PRECISION = [
    ("exact", "Date exacte"),
    ("year", "Année"),
    ("interval", "Intervalle"),
    ("century", "Siècle"),
    ("period", "Période"),
    ("estimated", "Estimation"),
    ("unknown", "Inconnue"),
]

ORIGIN = [
    ("source", "Source (catalogue)"),
    ("rule", "Règle automatique"),
    ("user", "Utilisateur"),
    ("ai", "Intelligence artificielle"),
]

PERIODS = [
    ("", "—"),
    ("nara", "Nara (710–794)"),
    ("heian", "Heian (794–1185)"),
    ("kamakura", "Kamakura (1185–1333)"),
    ("nanbokucho", "Nanboku-chō (1336–1392)"),
    ("muromachi", "Muromachi (1336–1573)"),
    ("sengoku", "Sengoku (1467–1590)"),
    ("azuchi_momoyama", "Azuchi-Momoyama (1573–1603)"),
    ("edo", "Edo (1603–1868)"),
    ("meiji", "Meiji et après (1868– )"),
]
PERIOD_RANGES = {
    "nara": (710, 794), "heian": (794, 1185), "kamakura": (1185, 1333),
    "nanbokucho": (1336, 1392), "muromachi": (1336, 1573), "sengoku": (1467, 1590),
    "azuchi_momoyama": (1573, 1603), "edo": (1603, 1868), "meiji": (1868, 2100),
}

DOCUMENT_TYPES = [
    ("", "—"),
    ("chronique", "Chronique"),
    ("journal", "Journal"),
    ("genealogie", "Généalogie"),
    ("registre", "Registre"),
    ("traite_militaire", "Traité militaire"),
    ("traite", "Traité"),
    ("recit", "Récit"),
    ("recueil", "Recueil"),
    ("carte", "Carte"),
    ("lettre", "Lettre / correspondance"),
    ("poesie", "Poésie"),
    ("religieux", "Texte religieux"),
    ("dictionnaire", "Dictionnaire"),
    ("autre", "Autre"),
]

MATERIAL_TYPES = [
    ("", "—"),
    ("manuscrit", "Manuscrit"),
    ("imprime", "Imprimé"),
    ("copie", "Copie"),
    ("edition_moderne", "Édition moderne"),
    ("transcription", "Transcription"),
    ("numerique", "Document numérique"),
    ("autre", "Autre"),
]

DIGITAL_ACCESS = [
    ("", "Inconnu"),
    ("fulltext", "Texte intégral"),
    ("image", "Image disponible"),
    ("record_only", "Notice seule"),
    ("restricted", "Accès restreint"),
]

LANGUAGES = [
    ("", "—"),
    ("ja", "Japonais"),
    ("lzh", "Chinois classique (kanbun)"),
    ("fr", "Français"),
    ("en", "Anglais"),
    ("other", "Autre"),
]

RECORD_STATUS = [
    ("active", "Active"),
    ("unavailable", "Indisponible"),
    ("withdrawn", "Retirée"),
    ("to_check", "À vérifier"),
    ("deleted", "Supprimée (corbeille)"),
]

CONNECTOR_STATUS = [
    ("not_configured", "Non configuré"),
    ("to_study", "À étudier"),
    ("available", "Disponible"),
    ("partial", "Partiel"),
    ("degraded", "Dégradé"),
    ("disabled", "Désactivé"),
]

FREQUENCIES = [
    ("manual", "Manuelle"),
    ("daily", "Quotidienne"),
    ("weekly", "Hebdomadaire"),
    ("monthly", "Mensuelle"),
    ("custom", "Personnalisée (en heures)"),
]


def new_uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


class HistoricalDateMixin:
    """Aide à l'affichage d'une date historique stockée en plusieurs champs."""

    @staticmethod
    def format_date(text, start, end, precision):
        if text:
            return text
        if start and end and start != end:
            return f"{start}–{end}"
        if start:
            return str(start)
        return "Date inconnue" if precision == "unknown" else ""


# --------------------------------------------------------------------------- référentiels


class Institution(models.Model):
    name = models.CharField("Nom", max_length=300)
    name_original = models.CharField("Nom original", max_length=300, blank=True)
    kind = models.CharField("Type", max_length=50, blank=True,
                            help_text="Bibliothèque, archive, université, temple, collection privée…")
    country = models.CharField("Pays", max_length=80, blank=True, default="Japon")
    url = models.URLField("Site officiel", blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name_original and f"{self.name} — {self.name_original}" or self.name


class Catalogue(models.Model):
    """Source documentaire et paramètres de son connecteur (§5, §9)."""

    code = models.SlugField("Identifiant technique", unique=True, max_length=50)
    name = models.CharField("Nom", max_length=200)
    name_original = models.CharField("Nom original", max_length=200, blank=True)
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.SET_NULL)
    connector = models.CharField("Connecteur", max_length=50, blank=True,
                                 help_text="Clé du connecteur dans le registre (vide = import de fichiers uniquement).")
    role = models.TextField("Rôle envisagé", blank=True)
    access_method = models.TextField("Méthode d'accès", blank=True)
    status = models.CharField("Statut", max_length=20, choices=CONNECTOR_STATUS, default="to_study")
    enabled_for_search = models.BooleanField("Interrogé dans les recherches", default=False)
    base_url = models.URLField("Adresse du catalogue", blank=True)
    terms_url = models.URLField("Conditions d'utilisation", blank=True)
    license_notes = models.TextField("Licences, restrictions et droits connus", blank=True)
    unsupported_fields = models.TextField("Champs indisponibles ou non pris en charge", blank=True)
    config = models.JSONField("Paramètres du connecteur", default=dict, blank=True)
    frequency = models.CharField("Fréquence d'actualisation", max_length=20, choices=FREQUENCIES, default="manual")
    custom_interval_hours = models.PositiveIntegerField("Intervalle personnalisé (heures)", null=True, blank=True)
    sync_paused = models.BooleanField("Actualisation suspendue", default=False)
    min_interval_seconds = models.FloatField("Délai minimal entre deux requêtes (s)", default=1.0)
    timeout_seconds = models.FloatField("Délai d'attente (s)", default=20.0)
    is_snapshot = models.BooleanField("Jeu de données historique (instantané)", default=False)
    snapshot_date = models.DateField("Date de l'instantané", null=True, blank=True)
    last_attempt_at = models.DateTimeField("Dernière tentative", null=True, blank=True)
    last_success_at = models.DateTimeField("Dernière réussite", null=True, blank=True)
    last_error = models.TextField("Dernière erreur", blank=True)
    real_test_ok_at = models.DateTimeField("Dernier test réel réussi", null=True, blank=True,
                                           help_text="Renseigné uniquement par « Tester le connecteur » sur le service réel.")
    notes = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("connectors:detail", args=[self.code])

    @property
    def needs_real_verification(self):
        """Connecteur externe jamais vérifié avec succès sur le service réel (audit, point particulier 4)."""
        return bool(self.connector) and self.connector != "local" and self.real_test_ok_at is None

    @property
    def can_refresh(self):
        """Le connecteur sait-il actualiser des notices (moisson ou relecture par identifiant) ? (1.2.0)

        NDL Search, Japan Search et CiNii servent aux recherches : ils ne proposent pas d'actualisation.
        """
        if not self.connector or self.connector == "local":
            return False
        from apps.connectors.registry import connector_class

        cls = connector_class(self.connector)
        return bool(cls and (cls.supports_harvest or cls.supports_fetch))

    @property
    def is_searchable(self):
        return self.enabled_for_search and self.status in ("available", "partial", "degraded")

    def next_sync_due(self):
        from datetime import timedelta

        if self.frequency == "manual" or self.sync_paused or self.status == "disabled":
            return None
        hours = {"daily": 24, "weekly": 24 * 7, "monthly": 24 * 30}.get(self.frequency)
        if self.frequency == "custom":
            hours = self.custom_interval_hours or 24
        base = self.last_attempt_at or (timezone.now() - timedelta(hours=hours + 1))
        return base + timedelta(hours=hours)


class Creator(models.Model):
    """Personne ou collectivité (auteur, compilateur, éditeur…)."""

    uid = models.CharField(max_length=40, unique=True, editable=False)
    name_original = models.CharField("Nom original", max_length=300)
    name_reading = models.CharField("Lecture (kana)", max_length=300, blank=True)
    name_romaji = models.CharField("Transcription (rōmaji)", max_length=300, blank=True)
    kind = models.CharField(max_length=20, choices=[("person", "Personne"), ("collective", "Collectivité")],
                            default="person")
    dates = models.CharField("Dates", max_length=100, blank=True)
    identifiers = models.JSONField("Identifiants externes", default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name_original"]

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = new_uid("CRE")
        super().save(*args, **kwargs)

    def __str__(self):
        extra = self.name_romaji or self.name_reading
        return f"{self.name_original} ({extra})" if extra else self.name_original


class CreatorVariant(models.Model):
    """Variante de nom reliée par une relation documentée, jamais fusionnée automatiquement."""

    creator = models.ForeignKey(Creator, related_name="variants", on_delete=models.CASCADE)
    form = models.CharField("Forme", max_length=300)
    script = models.CharField(max_length=20, choices=[("kanji", "Kanji"), ("kana", "Kana"), ("romaji", "Rōmaji"),
                                                      ("other", "Autre")], default="kanji")
    origin = models.CharField(max_length=10, choices=ORIGIN, default="user")
    verified = models.BooleanField("Attestée / vérifiée", default=False)
    note = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return self.form


class Work(models.Model, HistoricalDateMixin):
    """Œuvre intellectuelle, indépendamment de ses éditions et exemplaires."""

    uid = models.CharField(max_length=40, unique=True, editable=False)
    title_original = models.CharField("Titre original", max_length=500)
    title_reading = models.CharField("Lecture", max_length=500, blank=True)
    title_romaji = models.CharField("Rōmaji", max_length=500, blank=True)
    title_translation = models.CharField("Titre traduit", max_length=500, blank=True)
    title_translation_origin = models.CharField(max_length=10, choices=ORIGIN, blank=True)
    creators = models.ManyToManyField(Creator, through="WorkCreator", blank=True)
    composition_date_text = models.CharField("Date de composition (texte)", max_length=120, blank=True)
    composition_year_start = models.IntegerField(null=True, blank=True)
    composition_year_end = models.IntegerField(null=True, blank=True)
    composition_date_precision = models.CharField(max_length=12, choices=DATE_PRECISION, default="unknown")
    composition_date_origin = models.CharField(max_length=10, choices=ORIGIN, default="source")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, blank=True)
    period = models.CharField(max_length=20, choices=PERIODS, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["title_original"]

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = new_uid("WRK")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title_original

    def get_absolute_url(self):
        return reverse("catalog:work_detail", args=[self.pk])

    @property
    def composition_display(self):
        return self.format_date(self.composition_date_text, self.composition_year_start,
                                self.composition_year_end, self.composition_date_precision)


class WorkCreator(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE)
    creator = models.ForeignKey(Creator, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, default="auteur")
    origin = models.CharField(max_length=10, choices=ORIGIN, default="user")


class Edition(models.Model, HistoricalDateMixin):
    """Édition, version, publication ou témoin textuel d'une œuvre."""

    work = models.ForeignKey(Work, related_name="editions", on_delete=models.CASCADE)
    title = models.CharField(max_length=500, blank=True)
    edition_statement = models.CharField("Mention d'édition", max_length=300, blank=True)
    publisher_original = models.CharField("Éditeur / atelier", max_length=300, blank=True)
    publication_date_text = models.CharField(max_length=120, blank=True)
    publication_year_start = models.IntegerField(null=True, blank=True)
    publication_year_end = models.IntegerField(null=True, blank=True)
    publication_date_precision = models.CharField(max_length=12, choices=DATE_PRECISION, default="unknown")
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.title or self.edition_statement or f"Édition de {self.work}"


class Copy(models.Model, HistoricalDateMixin):
    """Exemplaire matériel ou numérique, avec sa datation propre."""

    work = models.ForeignKey(Work, null=True, blank=True, related_name="copies", on_delete=models.SET_NULL)
    edition = models.ForeignKey(Edition, null=True, blank=True, related_name="copies", on_delete=models.SET_NULL)
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.SET_NULL)
    shelfmark = models.CharField("Cote", max_length=200, blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES, blank=True)
    copy_date_text = models.CharField("Date de copie / impression (texte)", max_length=120, blank=True)
    copy_year_start = models.IntegerField(null=True, blank=True)
    copy_year_end = models.IntegerField(null=True, blank=True)
    copy_date_precision = models.CharField(max_length=12, choices=DATE_PRECISION, default="unknown")
    digital_access_url = models.URLField(max_length=600, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "exemplaire"

    def __str__(self):
        inst = self.institution.name if self.institution else "institution inconnue"
        return f"{self.work or self.edition} — {inst} {self.shelfmark}".strip()


# --------------------------------------------------------------------------- notices

# Champs de la couche « originale » mappables depuis un import ou un connecteur.
RECORD_SOURCE_FIELDS = [
    "source_id", "source_url", "original_title", "reading", "translated_title",
    "creator_original", "creator_reading", "description_original", "description_translation",
    "composition_date_text", "composition_year_start", "composition_year_end", "composition_date_precision",
    "copy_date_text", "copy_year_start", "copy_year_end", "copy_date_precision",
    "document_type_original", "material_type_original", "holding_institution_text",
    "shelfmark", "digital_access_url", "digital_access", "rights_and_access", "language",
    "subjects_original", "place_original", "source_updated_at", "image_url",
]

# Champs dont la modification constitue un changement significatif (versionnement).
TRACKED_FIELDS = [f for f in RECORD_SOURCE_FIELDS if f not in ("source_id",)]


class Record(models.Model, HistoricalDateMixin):
    """Notice bibliographique publiée par un catalogue (ou saisie localement)."""

    record_id = models.CharField("Identifiant interne", max_length=40, unique=True, editable=False)
    catalogue = models.ForeignKey(Catalogue, related_name="records", on_delete=models.PROTECT)
    source_id = models.CharField("Identifiant source", max_length=300, db_index=True)
    source_url = models.URLField("URL officielle de la notice", max_length=600, blank=True)
    source_url_verified = models.BooleanField("URL fournie par la source", default=True)

    # Rattachements FRBR (facultatifs, validés par l'utilisateur)
    work = models.ForeignKey(Work, null=True, blank=True, related_name="records", on_delete=models.SET_NULL)
    edition = models.ForeignKey(Edition, null=True, blank=True, related_name="records", on_delete=models.SET_NULL)
    copy = models.ForeignKey(Copy, null=True, blank=True, related_name="records", on_delete=models.SET_NULL)

    # Couche originale
    raw_data = models.JSONField("Données brutes de la source", default=dict, blank=True)
    raw_format = models.CharField(max_length=30, blank=True)
    original_title = models.CharField("Titre original", max_length=1000)
    reading = models.CharField("Lecture", max_length=1000, blank=True)
    translated_title = models.CharField("Titre traduit", max_length=1000, blank=True)
    translated_title_origin = models.CharField(max_length=10, choices=ORIGIN, blank=True)
    creator_original = models.CharField("Auteur (forme originale)", max_length=1000, blank=True)
    creator_reading = models.CharField("Auteur (lecture)", max_length=1000, blank=True)
    description_original = models.TextField("Description originale (解題)", blank=True)
    description_translation = models.TextField("Traduction de la description", blank=True)
    description_translation_origin = models.CharField(max_length=10, choices=ORIGIN, blank=True)
    composition_date_text = models.CharField("Date de composition", max_length=200, blank=True)
    composition_year_start = models.IntegerField(null=True, blank=True)
    composition_year_end = models.IntegerField(null=True, blank=True)
    composition_date_precision = models.CharField(max_length=12, choices=DATE_PRECISION, default="unknown")
    composition_date_origin = models.CharField(max_length=10, choices=ORIGIN, default="source")
    copy_date_text = models.CharField("Date de copie / impression / édition", max_length=200, blank=True)
    copy_year_start = models.IntegerField(null=True, blank=True)
    copy_year_end = models.IntegerField(null=True, blank=True)
    copy_date_precision = models.CharField(max_length=12, choices=DATE_PRECISION, default="unknown")
    copy_date_origin = models.CharField(max_length=10, choices=ORIGIN, default="source")
    document_type_original = models.CharField("Type documentaire (source)", max_length=300, blank=True)
    material_type_original = models.CharField("Support (source)", max_length=300, blank=True)
    holding_institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.SET_NULL)
    holding_institution_text = models.CharField("Institution détentrice", max_length=500, blank=True)
    shelfmark = models.CharField("Cote", max_length=300, blank=True)
    digital_access_url = models.URLField("Lien vers la numérisation", max_length=600, blank=True)
    image_url = models.URLField("Manifeste ou image (IIIF)", max_length=600, blank=True)
    digital_access = models.CharField("Accès numérique", max_length=20, choices=DIGITAL_ACCESS, blank=True)
    rights_and_access = models.TextField("Conditions de consultation et de réutilisation", blank=True)
    language = models.CharField(max_length=10, choices=LANGUAGES, blank=True)
    subjects_original = models.TextField("Sujets (source)", blank=True)
    place_original = models.CharField("Lieu (source)", max_length=500, blank=True)
    collected_at = models.DateTimeField("Date de collecte", default=timezone.now)
    source_updated_at = models.CharField("Mise à jour indiquée par la source", max_length=60, blank=True)

    # Couche normalisée (traçable, recalculable)
    document_type = models.CharField("Type documentaire (normalisé)", max_length=30, choices=DOCUMENT_TYPES,
                                     blank=True)
    material_type = models.CharField("Support (normalisé)", max_length=20, choices=MATERIAL_TYPES, blank=True)
    period = models.CharField("Période", max_length=20, choices=PERIODS, blank=True)
    title_romaji = models.CharField("Titre en rōmaji (automatique)", max_length=1000, blank=True)
    search_text = models.TextField("Texte de recherche normalisé", blank=True)
    normalization_log = models.JSONField("Journal de normalisation", default=list, blank=True)
    manual_fields = models.JSONField("Champs normalisés fixés par l'utilisateur", default=list, blank=True,
                                     help_text="Jamais recalculés automatiquement (corrections validées).")

    # Gestion
    record_hash = models.CharField(max_length=64, blank=True)
    record_status = models.CharField(max_length=20, choices=RECORD_STATUS, default="active")
    version = models.PositiveIntegerField(default=1)
    dataset_label = models.CharField("Jeu de données d'origine", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["original_title"]
        constraints = [models.UniqueConstraint(fields=["catalogue", "source_id"], name="unique_source_record")]
        indexes = [
            models.Index(fields=["period"]),
            models.Index(fields=["document_type"]),
            models.Index(fields=["composition_year_start"]),
            models.Index(fields=["copy_year_start"]),
            models.Index(fields=["record_status"]),
        ]

    def __str__(self):
        return self.original_title

    def save(self, *args, **kwargs):
        if not self.record_id:
            self.record_id = new_uid("REC")
        from .normalization import normalize_record

        normalize_record(self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:record_detail", args=[self.record_id])

    # ---- affichage
    @property
    def composition_display(self):
        return self.format_date(self.composition_date_text, self.composition_year_start,
                                self.composition_year_end, self.composition_date_precision)

    @property
    def copy_display(self):
        return self.format_date(self.copy_date_text, self.copy_year_start,
                                self.copy_year_end, self.copy_date_precision)

    @property
    def institution_display(self):
        return self.holding_institution_text or (self.holding_institution and self.holding_institution.name) or ""

    def source_snapshot(self):
        """Représentation des champs suivis (sert à l'empreinte et aux versions)."""
        snap = {}
        for f in TRACKED_FIELDS:
            v = getattr(self, f)
            snap[f] = v if v is None or isinstance(v, (int, str)) else str(v)
        snap["raw_data"] = self.raw_data
        return snap

    def compute_hash(self):
        payload = json.dumps(self.source_snapshot(), sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RecordVersion(models.Model):
    """Version historisée d'une notice (aucun écrasement silencieux)."""

    CHANGE_TYPES = [
        ("created", "Création"),
        ("modified", "Modification"),
        ("unavailable", "Indisponible à la source"),
        ("withdrawn", "Retrait"),
        ("restored", "Restauration"),
        ("editorial", "Modification éditoriale"),
        ("deleted", "Mise en corbeille"),
    ]
    record = models.ForeignKey(Record, related_name="versions", on_delete=models.CASCADE)
    version = models.PositiveIntegerField()
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    origin = models.CharField(max_length=30, blank=True, help_text="import, synchronisation, recherche, utilisateur…")
    snapshot = models.JSONField(default=dict)
    record_hash = models.CharField(max_length=64, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    previous_values = models.JSONField(default=dict, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-version"]
        unique_together = [("record", "version")]


class EditorialContent(models.Model):
    """Couche éditoriale : traduction, résumé, classification, hypothèse… jamais confondue avec la source."""

    KINDS = [
        ("translation", "Traduction"),
        ("summary", "Résumé"),
        ("classification", "Classification proposée"),
        ("extraction", "Entités extraites"),
        ("hypothesis", "Hypothèse"),
        ("comment", "Commentaire éditorial"),
    ]
    record = models.ForeignKey(Record, related_name="editorial", on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, choices=KINDS)
    target_field = models.CharField(max_length=60, blank=True, help_text="Champ concerné (ex. original_title)")
    source_text = models.TextField("Texte source utilisé", blank=True)
    content = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    origin = models.CharField(max_length=10, choices=ORIGIN)
    ai_task = models.ForeignKey("ai.AITask", null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, default="proposed",
                              choices=[("proposed", "Proposé"), ("validated", "Validé"), ("rejected", "Rejeté")])
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Subject(models.Model):
    KINDS = [
        ("period", "Période"), ("place", "Lieu / province"), ("doc_type", "Type documentaire"),
        ("keyword", "Mot-clé"), ("person", "Personne"), ("clan", "Clan"), ("theme", "Thème"),
    ]
    kind = models.CharField(max_length=20, choices=KINDS, default="keyword")
    label = models.CharField(max_length=300)
    label_original = models.CharField(max_length=300, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = [("kind", "label")]
        ordering = ["kind", "label"]

    def __str__(self):
        return self.label


class RecordSubject(models.Model):
    record = models.ForeignKey(Record, related_name="record_subjects", on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    origin = models.CharField(max_length=10, choices=ORIGIN, default="user")
    verified = models.BooleanField(default=False)

    class Meta:
        unique_together = [("record", "subject")]


class RecordLink(models.Model):
    """Relation entre notices : doublon potentiel, même œuvre, même exemplaire… Jamais de fusion automatique."""

    LINK_TYPES = [
        ("possible_duplicate", "Doublon potentiel"),
        ("same_work", "Même œuvre"),
        ("same_copy", "Même exemplaire"),
        ("related", "Notice liée"),
    ]
    STATUS = [("proposed", "Proposé"), ("validated", "Validé"), ("rejected", "Rejeté")]
    record_a = models.ForeignKey(Record, related_name="links_out", on_delete=models.CASCADE)
    record_b = models.ForeignKey(Record, related_name="links_in", on_delete=models.CASCADE)
    link_type = models.CharField(max_length=30, choices=LINK_TYPES, default="possible_duplicate")
    status = models.CharField(max_length=20, choices=STATUS, default="proposed")
    origin = models.CharField(max_length=10, choices=ORIGIN, default="rule")
    score = models.FloatField(null=True, blank=True)
    rationale = models.TextField(blank=True)
    ai_task = models.ForeignKey("ai.AITask", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="+",
                                    on_delete=models.SET_NULL)

    class Meta:
        unique_together = [("record_a", "record_b", "link_type")]


def stored_file_path(instance, filename):
    return f"{instance.kind}/{timezone.now():%Y/%m}/{uuid.uuid4().hex[:8]}_{filename}"


class StoredFile(models.Model):
    """Fichier local (import, archive source autorisée, image autorisée, export, personnel)."""

    KINDS = [("import", "Fichier d'import"), ("archive", "Archive source"), ("image", "Image"),
             ("export", "Export"), ("personal", "Fichier personnel")]
    kind = models.CharField(max_length=20, choices=KINDS)
    file = models.FileField(upload_to=stored_file_path, max_length=500)
    original_name = models.CharField(max_length=300)
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    rights = models.TextField("Droits et conditions", blank=True)
    record = models.ForeignKey(Record, null=True, blank=True, related_name="files", on_delete=models.SET_NULL)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name
