"""Sessions de recherche, résultats, décisions et recherches enregistrées (§8)."""
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

MODES = [("auto", "Automatique"), ("selective", "Sélectif"), ("manual", "Manuel / temporaire")]

EXCLUSION_REASONS = [
    ("off_topic", "Hors sujet"),
    ("duplicate", "Doublon"),
    ("wrong_period", "Mauvaise période"),
    ("late_source", "Source tardive"),
    ("insufficient", "Référence insuffisante"),
    ("other", "Autre"),
]


class SavedSearch(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="saved_searches", on_delete=models.CASCADE)
    name = models.CharField("Nom", max_length=200)
    params = models.JSONField("Paramètres de relance", default=dict)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_run_at", "-created_at"]
        verbose_name = "recherche enregistrée"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("searching:saved_detail", args=[self.pk])


class SearchSession(models.Model):
    STATUS = [("running", "En cours"), ("done", "Terminée"), ("partial", "Terminée avec erreurs")]

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="search_sessions", on_delete=models.CASCADE)
    title = models.CharField(max_length=300, blank=True)
    query = models.CharField("Requête initiale", max_length=500, blank=True)
    variants = models.JSONField("Variantes retenues", default=list, blank=True)
    variant_details = models.JSONField(default=list, blank=True)
    fields = models.JSONField("Champs de recherche avancée", default=dict, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    sources = models.JSONField("Sources interrogées", default=list)
    mode = models.CharField("Mode d'enregistrement", max_length=20, choices=MODES, default="selective")
    status = models.CharField(max_length=20, choices=STATUS, default="running")
    source_stats = models.JSONField("Statistiques par source", default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    is_saved = models.BooleanField("Session conservée", default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    saved_search = models.ForeignKey(SavedSearch, null=True, blank=True, related_name="sessions",
                                     on_delete=models.SET_NULL)
    previous_session = models.ForeignKey("self", null=True, blank=True, related_name="replays",
                                         on_delete=models.SET_NULL)
    target_collection = models.ForeignKey("library.Collection", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "session de recherche"

    def __str__(self):
        return self.title or self.query or f"Session {self.started_at:%d/%m/%Y %H:%M}"

    def get_absolute_url(self):
        return reverse("searching:session", args=[self.uid])

    def counts(self):
        qs = self.results.all()
        return {
            "found": qs.exclude(comparison="unavailable").count(),
            "selected": qs.filter(decision="selected").count(),
            "excluded": qs.filter(decision="excluded").count(),
            "pending": qs.filter(decision="pending").exclude(comparison="unavailable").count(),
            "integrated": qs.filter(integrated_record__isnull=False).count(),
            "in_library": qs.filter(in_library=True).count(),
        }

    def search_params(self):
        return {"query": self.query, "variants": self.variants, "fields": self.fields, "filters": self.filters,
                "sources": self.sources, "mode": self.mode}


class SearchResult(models.Model):
    DECISIONS = [("pending", "En attente"), ("selected", "Sélectionné"), ("excluded", "Exclu")]
    COMPARISON = [
        ("", "—"),
        ("new", "Nouveau"),
        ("known", "Déjà connu"),
        ("modified", "Modifié"),
        ("unavailable", "Indisponible"),
        ("not_comparable", "Non comparable"),
    ]

    session = models.ForeignKey(SearchSession, related_name="results", on_delete=models.CASCADE)
    catalogue = models.ForeignKey("catalog.Catalogue", on_delete=models.PROTECT)
    source_id = models.CharField(max_length=300)
    rank = models.PositiveIntegerField(default=0)
    data = models.JSONField("Résultat normalisé", default=dict)
    raw = models.JSONField("Réponse brute", default=dict, blank=True)
    raw_format = models.CharField(max_length=30, blank=True)
    result_hash = models.CharField(max_length=64, blank=True)
    local_record = models.ForeignKey("catalog.Record", null=True, blank=True, related_name="+",
                                     on_delete=models.SET_NULL, help_text="Notice locale correspondante")
    in_library = models.BooleanField("Déjà dans la bibliothèque", default=False)
    possible_duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    decision = models.CharField(max_length=20, choices=DECISIONS, default="pending")
    exclusion_reason = models.CharField(max_length=20, choices=EXCLUSION_REASONS, blank=True)
    exclusion_note = models.CharField(max_length=300, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    integrated_record = models.ForeignKey("catalog.Record", null=True, blank=True, related_name="+",
                                          on_delete=models.SET_NULL)
    integrated_at = models.DateTimeField(null=True, blank=True)
    comparison = models.CharField(max_length=20, choices=COMPARISON, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    collected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["rank", "pk"]
        indexes = [models.Index(fields=["session", "decision"])]

    @property
    def title(self):
        return self.data.get("original_title") or "(sans titre)"


class ResultDecision(models.Model):
    """Historique append-only des décisions (sélection, exclusion, réintégration, intégration)."""

    result = models.ForeignKey(SearchResult, related_name="decision_log", on_delete=models.CASCADE)
    action = models.CharField(max_length=20)
    reason = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=300, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
