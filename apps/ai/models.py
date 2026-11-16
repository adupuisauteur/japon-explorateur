"""Module IA facultatif : fournisseurs, clés chiffrées, préférences, tâches tracées (§11)."""
from decimal import Decimal

from django.conf import settings
from django.db import models

PROVIDERS = [
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic (Claude)"),
    ("gemini", "Google (Gemini)"),
    ("openai_compatible", "Compatible OpenAI (modèle local ou autre service)"),
    # 2.0.0 (lot 4) : service Ollama facultatif de J-ed, sur l'ordinateur (gratuit, rien ne sort)
    ("ollama", "IA locale (Ollama, sur cet ordinateur)"),
]

MODES = [
    ("disabled", "Désactivée"),
    ("demand", "À la demande"),
    ("confirm", "Confirmation systématique"),
]

FUNCTIONS = [
    ("translation", "Traduction japonais → français"),
    ("summary", "Résumé documentaire"),
    ("classification", "Classification historique"),
    ("duplicates", "Détection des doublons assistée"),
    ("query_extension", "Extension de recherche"),
    ("extraction", "Extraction d'entités"),
    ("rag", "Question-réponse sur le fonds local"),
    ("comparison", "Comparaison de notices"),
]


class AIProviderCredential(models.Model):
    """Clé API d'un utilisateur. Chiffrée au repos ; jamais renvoyée au navigateur."""

    STATUS = [("untested", "Non testée"), ("ok", "Connexion réussie"), ("error", "Erreur"), ("revoked", "Révoquée")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ai_credentials", on_delete=models.CASCADE)
    provider = models.CharField(max_length=30, choices=PROVIDERS)
    encrypted_key = models.TextField(blank=True)
    base_url = models.URLField("Adresse de l'API (services compatibles uniquement)", blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="untested")
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    available_models = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "provider")]

    def __str__(self):
        return f"{self.get_provider_display()} ({self.get_status_display()})"

    @property
    def is_configured(self):
        return bool(self.encrypted_key) and self.status != "revoked"


class AIPreferenceProfile(models.Model):
    """Profil de préférences IA. Enregistrer un profil ne vaut jamais consentement à un traitement."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ai_profiles", on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default="Profil par défaut")
    is_active = models.BooleanField(default=False)
    mode = models.CharField("Mode général", max_length=20, choices=MODES, default="demand")
    translation_enabled = models.BooleanField("Traduction japonais-français", default=True)
    summary_enabled = models.BooleanField("Résumé des notices", default=True)
    classification_enabled = models.BooleanField("Classification historique", default=False)
    duplicates_enabled = models.BooleanField("Détection des doublons assistée", default=True)
    query_extension_enabled = models.BooleanField("Extension de recherche", default=False)
    extraction_enabled = models.BooleanField("Extraction d'entités", default=False)
    rag_enabled = models.BooleanField("Question-réponse sur le fonds local", default=False)
    comparison_enabled = models.BooleanField("Comparaison de notices", default=False)
    default_provider = models.CharField("Fournisseur par défaut", max_length=30, choices=PROVIDERS, blank=True)
    default_model = models.CharField("Modèle par défaut", max_length=120, blank=True)
    function_overrides = models.JSONField("Fournisseur par fonction", default=dict, blank=True)
    batch_extra_confirmation = models.BooleanField("Confirmation supplémentaire pour les lots", default=True)
    store_inputs = models.BooleanField("Conserver le contenu envoyé dans l'historique", default=False)
    monthly_budget = models.DecimalField("Plafond mensuel estimé (USD)", max_digits=10, decimal_places=2,
                                         null=True, blank=True)
    alert_threshold_pct = models.PositiveIntegerField("Alerte à (% du plafond)", default=80)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name

    def function_enabled(self, function):
        if self.mode == "disabled":
            return False
        return bool(getattr(self, f"{function}_enabled", False))

    def provider_for(self, function):
        override = (self.function_overrides or {}).get(function) or {}
        if override.get("provider"):
            return override["provider"], override.get("model") or ""
        return self.default_provider, self.default_model


class AIModelPrice(models.Model):
    """Tarifs saisis par l'administrateur, utilisés uniquement pour des estimations affichées comme telles."""

    provider = models.CharField(max_length=30, choices=PROVIDERS)
    model_prefix = models.CharField("Modèle (ou début du nom)", max_length=120)
    input_per_million = models.DecimalField("Entrée (USD / million de jetons)", max_digits=10, decimal_places=4)
    output_per_million = models.DecimalField("Sortie (USD / million de jetons)", max_digits=10, decimal_places=4)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "model_prefix"]

    @classmethod
    def estimate(cls, provider, model, tokens_in, tokens_out):
        candidates = [p for p in cls.objects.filter(provider=provider) if model and model.startswith(p.model_prefix)]
        price = max(candidates, key=lambda p: len(p.model_prefix)) if candidates else None
        if price is None:
            return None
        return (Decimal(tokens_in) * price.input_per_million + Decimal(tokens_out) * price.output_per_million) / Decimal(1_000_000)


class AITask(models.Model):
    STATUS = [("draft", "Préparée"), ("confirmed", "Confirmée"), ("running", "En cours"), ("done", "Terminée"),
              ("failed", "Échec"), ("cancelled", "Annulée"), ("blocked", "Bloquée")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ai_tasks", on_delete=models.CASCADE)
    function = models.CharField(max_length=30, choices=FUNCTIONS)
    provider = models.CharField(max_length=30, choices=PROVIDERS, blank=True)
    model = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    records = models.ManyToManyField("catalog.Record", blank=True, related_name="ai_tasks")
    scope_label = models.CharField(max_length=300, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    data_categories = models.JSONField("Catégories de données transmises", default=list, blank=True)
    prompt_version = models.CharField(max_length=20, blank=True)
    instruction = models.TextField("Instruction utilisée", blank=True)
    input_payload = models.JSONField("Contenu transmis", default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    output_text = models.TextField(blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    cost_estimate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_function_display()} ({self.get_status_display()})"


# --------------------------------------------------------------------------- 2.0.0 (lot 4) : résumés

SUMMARY_KINDS = [
    ("court", "Résumé court"),
    ("detaille", "Résumé détaillé"),
    ("analyse", "Fiche d'analyse (thèmes, personnes, lieux, dates)"),
]
SUMMARY_LANGUAGES = [("fr", "Français"), ("en", "Anglais"), ("ja", "Japonais")]
SUMMARY_SOURCES = [
    ("record_original", "Notice (texte original)"),
    ("document_original", "Document (texte original)"),
    ("document_validated", "Document (traduction validée)"),
    ("document_unvalidated", "Document (traduction non validée)"),
]


class Summary(models.Model):
    """Résumé ou fiche d'analyse produit par une IA, toujours marqué « généré par IA ».

    Rattaché à une notice, ou à un document d'un projet (au moins l'un des deux). Une nouvelle version garde
    un lien vers la précédente (historique). N'entre ni dans la mémoire de traduction ni dans les exports de
    traduction validée ; il n'apparaît dans un export de notices que si l'utilisateur le demande.
    """

    record = models.ForeignKey("catalog.Record", null=True, blank=True, related_name="ai_summaries",
                               on_delete=models.CASCADE)
    project = models.ForeignKey("translation.TranslationProject", null=True, blank=True, related_name="summaries",
                                on_delete=models.CASCADE)
    document = models.ForeignKey("translation.TranslationDocument", null=True, blank=True,
                                 related_name="summaries", on_delete=models.CASCADE)
    kind = models.CharField("Type", max_length=10, choices=SUMMARY_KINDS)
    language = models.CharField("Langue", max_length=5, choices=SUMMARY_LANGUAGES, default="fr")
    source_kind = models.CharField("Texte résumé", max_length=24, choices=SUMMARY_SOURCES)
    source_sha256 = models.CharField(max_length=64, blank=True)
    variety = models.CharField("Variété de langue du texte", max_length=12, blank=True)
    content = models.TextField("Résumé")
    data = models.JSONField("Analyse (thèmes, personnes, lieux, dates, limites)", default=dict, blank=True)
    provider = models.CharField(max_length=30, choices=PROVIDERS)
    model = models.CharField(max_length=120, blank=True)
    calls = models.PositiveSmallIntegerField("Appels à l'IA", default=1)
    job = models.ForeignKey("translation.TranslationJob", null=True, blank=True, related_name="summaries",
                            on_delete=models.SET_NULL)
    ai_task = models.ForeignKey(AITask, null=True, blank=True, related_name="summaries", on_delete=models.SET_NULL)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="ai_summaries",
                               on_delete=models.SET_NULL)
    previous = models.OneToOneField("self", null=True, blank=True, related_name="next_version",
                                    on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "résumé IA"
        constraints = [models.CheckConstraint(condition=models.Q(record__isnull=False) | models.Q(document__isnull=False),
                                              name="ai_summary_has_target")]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.get_language_display()})"

    @property
    def is_latest(self):
        return not hasattr(self, "next_version") or self.next_version is None

    @property
    def unvalidated_source(self):
        return self.source_kind == "document_unvalidated"

    def history(self):
        out, current = [], self.previous
        while current is not None and len(out) < 50:
            out.append(current)
            current = current.previous
        return out
