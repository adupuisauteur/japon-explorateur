"""
Module de traduction (version 1.3.0).

Douze tables, validées dans le plan de développement du 13 novembre 2026 :
réglages (EngineSetting, TranslationPreference), glossaires (Glossary, GlossaryEntry),
projets (TranslationProject, ProjectGlossary, TranslationDocument, TranslationChapter,
TranslationSegment, TranslationVersion) et tâches (TranslationJob, TranslationJobItem).

Règles structurantes :
- le texte original n'est jamais modifié par une traduction : il est conservé tel quel
  (TranslationDocument.original_text, TranslationSegment.source_text, et un instantané dans
  chaque TranslationVersion) ;
- une seule version validée par segment, garantie par une contrainte en base ;
- les traductions de NOTICES ne sont pas ici : elles restent dans catalog.EditorialContent ;
- un compte anonymisé ou supprimé ne fait pas disparaître ses projets ni ses glossaires : ils
  sont confiés à un administrateur (apps/translation/ownership.py). C'est pourquoi le lien
  « propriétaire » n'a pas de suppression en cascade (DO_NOTHING + contrainte différée en base).
"""
from django.conf import settings
from django.db import models
from django.db.models import Deferrable, Q

from apps.ai.models import PROVIDERS as AI_PROVIDERS

# --------------------------------------------------------------------------- listes de choix

#: Moteurs configurables dans Traduction → Moteurs. « ai » désigne les fournisseurs du module IA.
ENGINES = [
    ("deepl", "DeepL"),
    ("google_basic", "Google Traduction (Basic)"),
    ("argos", "Argos Translate (local)"),
    ("ai", "Intelligence artificielle en ligne"),
]
#: Moteurs dont la clé ou le réglage est géré dans le module (les clés IA restent dans IA → Fournisseurs).
SETTING_ENGINES = [e for e in ENGINES if e[0] != "ai"]

LANGUAGES = [("ja", "Japonais"), ("en", "Anglais"), ("fr", "Français")]

VARIETIES = [
    ("modern", "Japonais moderne"),
    ("classical", "Japonais classique (bungo)"),
    ("kanbun", "Kanbun"),
]

SEGMENT_STATES = [
    ("untranslated", "Non traduit"),
    ("proposed", "Proposé"),
    ("validated", "Validé"),
    ("alert", "En alerte"),
]

VERSION_STATUS = [("proposed", "Proposée"), ("validated", "Validée"), ("rejected", "Rejetée")]

VERSION_ORIGINS = [
    ("machine", "Traduction automatique"),
    ("ai", "Intelligence artificielle"),
    ("human", "Saisie humaine"),
    ("human_edit", "Modification humaine"),
]

RATINGS = [
    ("correct", "Correcte"),
    ("acceptable", "Acceptable"),
    ("faulty", "Fautive"),
    ("misreading", "Contresens"),
]

GLOSSARY_CATEGORIES = [
    ("person", "Nom de personne"),
    ("era", "Ère et date"),
    ("title", "Titre ou fonction"),
    ("institution", "Institution"),
    ("place", "Lieu"),
    ("work", "Titre d'œuvre"),
    ("historical", "Terme historique"),
    ("administrative", "Terme administratif"),
    ("other", "Autre"),
]

JOB_STATUS = [
    ("draft", "Préparée"),
    ("confirmed", "Confirmée"),
    ("running", "En cours"),
    ("interrupted", "Interrompue"),
    ("done", "Terminée"),
    ("failed", "Échec"),
    ("cancelled", "Annulée"),
    ("blocked", "Bloquée"),
    # 2.0.0 (lot 3)
    ("scheduled", "Planifiée"),
    ("paused", "En pause"),
    ("late", "En retard — à confirmer"),
]
#: 2.0.0 (lot 3) : façon dont la tâche a été lancée
JOB_LAUNCHES = [
    ("immediate", "Immédiat"),
    ("now", "Maintenant (depuis une fiche)"),
    ("scheduled", "Programmé"),
    ("night", "File de nuit"),
    ("after", "Après la traduction"),  # 2.0.0 (lot 4) : résumé enchaîné
]
PAUSE_REASONS = [
    ("user", "Demande de l'utilisateur"),
    ("cap", "Plafond atteint"),
    ("night_end", "Fin de la plage de nuit"),
]
JOB_KINDS = [
    ("segments", "Segments d'un projet"),
    ("records", "Champs de notices"),
    ("evaluation", "Comparaison sur le corpus de référence"),
    ("package", "Installation de paquets Argos"),
    ("summary", "Résumés IA"),  # 2.0.0 (lot 4)
]
ITEM_STATUS = [("pending", "En attente"), ("done", "Traduit"), ("failed", "Échec"), ("skipped", "Non envoyé")]

DOCUMENT_SOURCES = [
    ("paste", "Texte collé"),
    ("txt", "Fichier texte"),
    ("docx", "Fichier Word"),
    ("pdf", "Fichier PDF"),
    ("record", "Notice"),
]
ENCODING_CONFIDENCE = [("sure", "Certaine"), ("probable", "Probable"), ("uncertain", "Incertaine")]


class TransferMixin(models.Model):
    """Trace d'un transfert de propriété (compte anonymisé ou supprimé)."""

    transferred_from = models.CharField("Ancien propriétaire", max_length=150, blank=True)
    transferred_at = models.DateTimeField("Date du transfert", null=True, blank=True)

    class Meta:
        abstract = True


class EngineChoiceMixin(models.Model):
    """Moteur par défaut et deuxième moteur. Vide = pas de choix (ou héritage pour un projet)."""

    default_engine = models.CharField("Moteur par défaut", max_length=20, choices=ENGINES, blank=True)
    default_ai_provider = models.CharField("Fournisseur IA (moteur par défaut)", max_length=30,
                                           choices=AI_PROVIDERS, blank=True)
    default_ai_model = models.CharField("Modèle IA (moteur par défaut)", max_length=120, blank=True)
    second_engine = models.CharField("Deuxième moteur", max_length=20, choices=ENGINES, blank=True)
    second_ai_provider = models.CharField("Fournisseur IA (deuxième moteur)", max_length=30,
                                          choices=AI_PROVIDERS, blank=True)
    second_ai_model = models.CharField("Modèle IA (deuxième moteur)", max_length=120, blank=True)

    class Meta:
        abstract = True


# --------------------------------------------------------------------------- réglages


class EngineSetting(models.Model):
    """Réglage d'un moteur (DeepL, Google, Argos) pour un utilisateur. Clé chiffrée, jamais renvoyée au navigateur."""

    STATUS = [("untested", "Non testé"), ("ok", "Test réussi"), ("error", "Erreur"), ("revoked", "Clé effacée")]
    PLANS = [("free", "Offre gratuite"), ("pro", "Offre payante")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="translation_engines", on_delete=models.CASCADE)
    engine = models.CharField(max_length=20, choices=SETTING_ENGINES)
    encrypted_key = models.TextField(blank=True)
    plan = models.CharField("Offre", max_length=10, choices=PLANS, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="untested")
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    quota_info = models.JSONField("Quota lu auprès du service", default=dict, blank=True)
    monthly_char_cap = models.PositiveIntegerField("Plafond mensuel (caractères)", null=True, blank=True)
    enabled = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "engine"], name="translation_one_setting_per_engine")]
        verbose_name = "réglage de moteur"

    def __str__(self):
        return f"{self.get_engine_display()} ({self.get_status_display()})"

    @property
    def has_key(self):
        return bool(self.encrypted_key) and self.status != "revoked"


class TranslationPreference(EngineChoiceMixin):
    """Choix des moteurs : lieu unique (Traduction → Moteurs), propre à chaque utilisateur."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="translation_preference",
                                on_delete=models.CASCADE)
    confirmation_threshold = models.PositiveIntegerField("Seconde confirmation au-delà de (caractères)", default=20000)
    send_neighbour_context = models.BooleanField("Envoyer les segments voisins aux IA comme contexte", default=False)
    translate_subjects = models.BooleanField("Notices : traduire aussi les sujets", default=False)
    translate_place = models.BooleanField("Notices : traduire aussi le lieu", default=False)
    migrated_from_ai = models.BooleanField("Ancien réglage IA de traduction déjà repris", default=False)
    # 2.0.0 (lot 3) : plage de la file de nuit, choisie par l'utilisateur (aucune valeur par défaut)
    night_start = models.TimeField("File de nuit : début", null=True, blank=True)
    night_end = models.TimeField("File de nuit : fin", null=True, blank=True)
    night_window_seen = models.DateTimeField("Début de la dernière plage observée", null=True, blank=True)
    night_window_open = models.BooleanField("Plage de nuit commencée à l'heure", default=False)
    # 2.0.0 (lot 4) : résumés (fournisseur et modèle, type et langue par défaut)
    summary_provider = models.CharField("Résumés : fournisseur IA", max_length=30, choices=AI_PROVIDERS, blank=True)
    summary_model = models.CharField("Résumés : modèle", max_length=120, blank=True)
    summary_kind = models.CharField("Résumés : type par défaut", max_length=10, default="court",
                                    choices=[("court", "Résumé court"), ("detaille", "Résumé détaillé"),
                                             ("analyse", "Fiche d'analyse")])
    summary_language = models.CharField("Résumés : langue par défaut", max_length=5, default="fr",
                                        choices=[("fr", "Français"), ("en", "Anglais"), ("ja", "Japonais")])
    # 2.0.0 (lot 4, U10) : moteur choisi d'avance pour le japonais ancien (bungo, kanbun, sōrōbun)
    ancient_engine = models.CharField("Japonais ancien : moteur de traduction", max_length=20, choices=ENGINES,
                                      blank=True)
    ancient_ai_provider = models.CharField("Japonais ancien : fournisseur IA", max_length=30, choices=AI_PROVIDERS,
                                           blank=True)
    ancient_ai_model = models.CharField("Japonais ancien : modèle IA", max_length=120, blank=True)
    summary_ancient_provider = models.CharField("Japonais ancien : fournisseur IA des résumés", max_length=30,
                                                choices=AI_PROVIDERS, blank=True)
    summary_ancient_model = models.CharField("Japonais ancien : modèle des résumés", max_length=120, blank=True)
    confirm_below = models.DecimalField("« Traduire maintenant » sans confirmation en dessous de (USD)", max_digits=8,
                                        decimal_places=4, null=True, blank=True,
                                        help_text="Vide : toujours confirmer. Les plafonds et le consentement IA "
                                                  "restent vérifiés dans tous les cas.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "préférences de traduction"

    def __str__(self):
        return f"Préférences de traduction de {self.user}"


# --------------------------------------------------------------------------- glossaires


class Glossary(TransferMixin):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="translation_glossaries",
                              on_delete=models.DO_NOTHING)
    name = models.CharField("Nom", max_length=200)
    description = models.TextField(blank=True)
    source_lang = models.CharField("Langue source", max_length=5, choices=LANGUAGES, default="ja")
    target_lang = models.CharField("Langue cible", max_length=5, choices=LANGUAGES, default="fr")
    version = models.PositiveIntegerField("Version", default=1, help_text="Incrémentée à chaque modification.")
    remote_copies = models.JSONField("Copies distantes (DeepL)", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "glossaire"

    def __str__(self):
        return self.name


class GlossaryEntry(models.Model):
    glossary = models.ForeignKey(Glossary, related_name="entries", on_delete=models.CASCADE)
    source_term = models.CharField("Terme source", max_length=300)
    reading = models.CharField("Lecture", max_length=300, blank=True)
    target_term = models.CharField("Terme cible", max_length=300)
    category = models.CharField("Catégorie", max_length=20, choices=GLOSSARY_CATEGORIES, default="other")
    avoid = models.JSONField("Traductions à éviter", default=list, blank=True)
    variants = models.JSONField("Variantes de graphie de l'original", default=list, blank=True)
    note = models.TextField(blank=True)
    decision_source = models.CharField("Source de la décision", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_term"]
        constraints = [models.UniqueConstraint(fields=["glossary", "source_term"],
                                               name="translation_one_entry_per_term")]
        verbose_name = "entrée de glossaire"

    def __str__(self):
        return f"{self.source_term} → {self.target_term}"


# --------------------------------------------------------------------------- projets


class TranslationProject(TransferMixin, EngineChoiceMixin):
    """Projet de traduction. Les moteurs vides héritent des préférences du propriétaire."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="translation_projects",
                              on_delete=models.DO_NOTHING)
    title = models.CharField("Titre", max_length=300)
    description = models.TextField(blank=True)
    source_lang = models.CharField("Langue source", max_length=5, choices=LANGUAGES, default="ja")
    target_lang = models.CharField("Langue cible", max_length=5, choices=LANGUAGES, default="fr")
    collection = models.ForeignKey("library.Collection", null=True, blank=True, related_name="translation_projects",
                                   on_delete=models.SET_NULL, verbose_name="Dossier lié")
    records = models.ManyToManyField("catalog.Record", blank=True, related_name="translation_projects",
                                     verbose_name="Notices liées")
    confidential = models.BooleanField(
        "Confidentiel", default=False,
        help_text="Moteurs en ligne refusés ; contenu invisible pour les autres comptes, administrateur compris.")
    is_reference_corpus = models.BooleanField("Corpus de référence", default=False)
    glossaries = models.ManyToManyField(Glossary, through="ProjectGlossary", blank=True, related_name="projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "projet de traduction"

    def __str__(self):
        return self.title


class ProjectGlossary(models.Model):
    project = models.ForeignKey(TranslationProject, related_name="glossary_links", on_delete=models.CASCADE)
    glossary = models.ForeignKey(Glossary, related_name="project_links", on_delete=models.CASCADE)
    priority = models.PositiveSmallIntegerField("Priorité", default=0, help_text="0 = la plus haute.")

    class Meta:
        ordering = ["priority", "pk"]
        constraints = [models.UniqueConstraint(fields=["project", "glossary"], name="translation_glossary_once")]


class TranslationDocument(models.Model):
    project = models.ForeignKey(TranslationProject, related_name="documents", on_delete=models.CASCADE)
    title = models.CharField("Titre", max_length=300)
    order = models.PositiveIntegerField("Ordre", default=0)
    source_kind = models.CharField("Provenance", max_length=10, choices=DOCUMENT_SOURCES, default="paste")
    record = models.ForeignKey("catalog.Record", null=True, blank=True, related_name="translation_documents",
                               on_delete=models.SET_NULL, verbose_name="Notice d'origine")
    source_filename = models.CharField("Fichier importé", max_length=255, blank=True)
    original_text = models.TextField("Texte importé (exact)")
    original_sha256 = models.CharField(max_length=64, blank=True)
    encoding = models.CharField("Encodage détecté", max_length=30, blank=True)
    encoding_confidence = models.CharField(max_length=10, choices=ENCODING_CONFIDENCE, blank=True)
    variety = models.CharField("Variété de langue", max_length=12, choices=VARIETIES, default="modern")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project", "order", "pk"]
        verbose_name = "document à traduire"

    def __str__(self):
        return self.title


class TranslationChapter(models.Model):
    document = models.ForeignKey(TranslationDocument, related_name="chapters", on_delete=models.CASCADE)
    title = models.CharField("Titre", max_length=300)
    order = models.PositiveIntegerField("Ordre", default=0)

    class Meta:
        ordering = ["document", "order", "pk"]
        verbose_name = "chapitre"

    def __str__(self):
        return self.title


class TranslationSegment(models.Model):
    """Unité de traduction. La concaténation des segments d'un document redonne exactement son texte importé."""

    document = models.ForeignKey(TranslationDocument, related_name="segments", on_delete=models.CASCADE)
    chapter = models.ForeignKey(TranslationChapter, null=True, blank=True, related_name="segments",
                                on_delete=models.SET_NULL)
    position = models.PositiveIntegerField("Position")
    source_text = models.TextField("Texte original (exact)")
    memory_key = models.CharField("Clé de mémoire (texte normalisé)", max_length=64, db_index=True, blank=True)
    variety = models.CharField("Variété (si différente du document)", max_length=12, choices=VARIETIES, blank=True)
    state = models.CharField("État", max_length=12, choices=SEGMENT_STATES, default="untranslated")
    source_changed = models.BooleanField("Original modifié depuis la traduction", default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document", "position"]
        constraints = [
            # Différée : permet de renuméroter les segments (fusion, division) dans une même transaction.
            models.UniqueConstraint(fields=["document", "position"], name="translation_segment_position",
                                    deferrable=Deferrable.DEFERRED),
        ]
        verbose_name = "segment"

    def __str__(self):
        return f"{self.document} — segment {self.position}"


class TranslationVersion(models.Model):
    """Une traduction d'un segment. Jamais écrasée : une correction crée une nouvelle version liée."""

    segment = models.ForeignKey(TranslationSegment, related_name="versions", on_delete=models.CASCADE)
    text = models.TextField("Traduction")
    source_text = models.TextField("Original au moment de la traduction")
    engine = models.CharField("Moteur", max_length=20, choices=ENGINES, blank=True)
    ai_provider = models.CharField(max_length=30, choices=AI_PROVIDERS, blank=True)
    model = models.CharField("Modèle", max_length=120, blank=True)
    engine_version = models.CharField("Version du moteur ou des paquets", max_length=120, blank=True)
    simulated = models.BooleanField("Simulation", default=False,
                                    help_text="Produite par un moteur simulé : mention « Simulation » partout.")
    glossaries = models.JSONField("Glossaires appliqués (identifiant et version)", default=list, blank=True)
    variety = models.CharField(max_length=12, choices=VARIETIES, blank=True)
    origin = models.CharField("Origine", max_length=12, choices=VERSION_ORIGINS)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="revisions", on_delete=models.SET_NULL,
                               verbose_name="Version modifiée")
    status = models.CharField("Statut", max_length=12, choices=VERSION_STATUS, default="proposed")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="+",
                               on_delete=models.SET_NULL)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="+",
                                   on_delete=models.SET_NULL)
    decided_at = models.DateTimeField(null=True, blank=True)
    chars_sent = models.PositiveIntegerField("Caractères envoyés", default=0)
    cost_estimate = models.DecimalField("Coût estimé", max_digits=12, decimal_places=6, null=True, blank=True)
    currency = models.CharField("Devise", max_length=3, blank=True)
    alerts = models.JSONField("Alertes de contrôle", default=list, blank=True)
    rating = models.CharField("Appréciation (corpus)", max_length=12, choices=RATINGS, blank=True)
    rating_comment = models.TextField(blank=True)
    excluded_from_memory = models.BooleanField("Exclue de la mémoire de traduction", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["segment", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["segment"], condition=Q(status="validated"),
                                    name="translation_one_validated_version_per_segment"),
        ]
        indexes = [models.Index(fields=["segment", "status"])]
        verbose_name = "version de traduction"

    def __str__(self):
        return f"{self.segment} — {self.get_origin_display()} ({self.get_status_display()})"


# --------------------------------------------------------------------------- tâches


class TranslationJob(models.Model):
    """Toute traduction passe par une tâche, même un seul champ : confirmation, consommation, reprise."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="translation_jobs",
                             on_delete=models.SET_NULL)
    project = models.ForeignKey(TranslationProject, null=True, blank=True, related_name="jobs",
                                on_delete=models.SET_NULL)
    kind = models.CharField(max_length=12, choices=JOB_KINDS, default="segments")
    scope_label = models.CharField("Portée", max_length=300, blank=True)
    engine = models.CharField("Moteur", max_length=20, choices=ENGINES)
    ai_provider = models.CharField(max_length=30, choices=AI_PROVIDERS, blank=True)
    ai_model = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=JOB_STATUS, default="draft")
    total_items = models.PositiveIntegerField(default=0)
    done_items = models.PositiveIntegerField(default=0)
    failed_items = models.PositiveIntegerField(default=0)
    skipped_items = models.PositiveIntegerField(default=0)
    chars_estimated = models.PositiveIntegerField("Caractères estimés", default=0)
    chars_sent = models.PositiveIntegerField("Caractères envoyés", default=0)
    cost_estimate = models.DecimalField("Coût estimé", max_digits=12, decimal_places=6, null=True, blank=True)
    currency = models.CharField("Devise", max_length=3, blank=True)
    requires_second_confirmation = models.BooleanField(default=False)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField("Dernier signe d'activité", null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # 2.0.0 (lot 3) : lancement, heure prévue, ordre dans la file, raison d'une pause
    launch = models.CharField("Lancement", max_length=10, choices=JOB_LAUNCHES, default="immediate")
    scheduled_for = models.DateTimeField("Heure prévue", null=True, blank=True)
    queue_position = models.PositiveIntegerField("Ordre dans la file", null=True, blank=True)
    pause_reason = models.CharField("Raison de la pause", max_length=10, choices=PAUSE_REASONS, blank=True)
    # 2.0.0 (lot 4) : réglages d'une tâche de résumé (type, langue, texte), enchaînement, tâche sœur (textes anciens)
    options = models.JSONField("Options", default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "tâche de traduction"

    def __str__(self):
        return f"{self.get_kind_display()} — {self.get_engine_display()} ({self.get_status_display()})"

    @property
    def title_label(self):
        """Titre de la page d'une tâche (2.0.0, lot 6 : un résumé n'est pas une traduction)."""
        if self.kind == "summary":
            return "Demande de résumés"
        if self.kind == "package":
            return "Installation"
        return "Tâche de traduction"

    @property
    def done_word(self):
        """« traduit(s) », « résumé(s) » ou « installé(s) » selon la nature de la tâche."""
        return {"summary": "résumé(s)", "package": "installé(s)"}.get(self.kind, "traduit(s)")

    @property
    def sent_word(self):
        if self.kind == "summary":
            return "caractère(s) lu(s) par l'IA"
        return "caractère(s) envoyé(s)"

    @property
    def status_label(self):
        """État affiché : « Terminée avec erreurs » quand des éléments ont échoué (2.0.0, lot 3)."""
        if self.status == "done" and self.failed_items:
            return "Terminée avec erreurs"
        if self.status == "paused" and self.pause_reason:
            return f"En pause — {self.get_pause_reason_display().lower()}"
        return self.get_status_display()


class TranslationJobItem(models.Model):
    """Élément d'une tâche : un segment, ou un champ de notice. Son état permet la reprise sans renvoi."""

    job = models.ForeignKey(TranslationJob, related_name="items", on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    segment = models.ForeignKey(TranslationSegment, null=True, blank=True, related_name="job_items",
                                on_delete=models.SET_NULL)
    record = models.ForeignKey("catalog.Record", null=True, blank=True, related_name="translation_job_items",
                               on_delete=models.SET_NULL)
    record_field = models.CharField(max_length=60, blank=True)
    # 2.0.0 (lot 4) : document résumé ; résumés partiels déjà obtenus (reprise sans renvoi)
    document = models.ForeignKey("TranslationDocument", null=True, blank=True, related_name="job_items",
                                 on_delete=models.SET_NULL)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=ITEM_STATUS, default="pending")
    skip_reason = models.CharField(max_length=30, blank=True)
    error_kind = models.CharField(max_length=30, blank=True)
    error_message = models.CharField(max_length=500, blank=True, help_text="Jamais de texte traduit ni original.")
    attempts = models.PositiveSmallIntegerField(default=0)
    chars = models.PositiveIntegerField(default=0)
    version = models.ForeignKey(TranslationVersion, null=True, blank=True, related_name="job_items",
                                on_delete=models.SET_NULL)
    editorial = models.ForeignKey("catalog.EditorialContent", null=True, blank=True,
                                  related_name="translation_job_items", on_delete=models.SET_NULL)
    ai_task = models.ForeignKey("ai.AITask", null=True, blank=True, related_name="translation_job_items",
                                on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["job", "position"]
        constraints = [models.UniqueConstraint(fields=["job", "position"], name="translation_job_item_position")]
        verbose_name = "élément de tâche"


class RecordVariety(models.Model):
    """2.0.0 (lot 4, U10) : variété de langue d'une notice — repérée automatiquement (« probable ») ou confirmée.

    Le repérage n'est jamais présenté comme sûr ; seule la confirmation de l'utilisateur fait foi.
    """

    ORIGINS = [("detected", "Repérée automatiquement (probable)"), ("user", "Confirmée par l'utilisateur")]

    record = models.OneToOneField("catalog.Record", related_name="language_variety", on_delete=models.CASCADE)
    variety = models.CharField("Variété de langue", max_length=12, choices=VARIETIES)
    origin = models.CharField(max_length=10, choices=ORIGINS, default="detected")
    reasons = models.JSONField("Indices", default=list, blank=True)
    source_sha256 = models.CharField(max_length=64, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "variété de langue d'une notice"
