from django import forms

from apps.ai.models import PROVIDERS as AI_PROVIDERS
from apps.core.forms import BootstrapMixin

from .models import GLOSSARY_CATEGORIES, EngineSetting, Glossary, TranslationPreference, TranslationProject


class EngineSettingForm(BootstrapMixin, forms.Form):
    """Clé et réglages d'un moteur. La clé n'est jamais réaffichée : champ vide = clé inchangée."""

    api_key = forms.CharField(label="Clé", required=False, strip=True,
                              widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
                              help_text="Laissez vide pour conserver la clé enregistrée.")
    plan = forms.ChoiceField(label="Offre", choices=[("", "— choisir —")] + EngineSetting.PLANS, required=False)
    monthly_char_cap = forms.IntegerField(label="Plafond mensuel (caractères)", required=False, min_value=0,
                                          help_text="Facultatif : au-delà, la traduction est bloquée (lot 4).")
    enabled = forms.BooleanField(label="Actif", required=False, initial=True)

    def __init__(self, *args, engine="", **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = engine
        if engine != "deepl":
            del self.fields["plan"]
        if engine == "argos":
            del self.fields["api_key"]
            self.fields["enabled"].label = "Activer Argos (mode simulé tant que le service n'est pas installé)"


class PreferenceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = TranslationPreference
        fields = ["default_engine", "default_ai_provider", "default_ai_model", "second_engine", "second_ai_provider",
                  "second_ai_model", "confirmation_threshold", "send_neighbour_context", "translate_subjects",
                  "translate_place"]

    def clean_confirmation_threshold(self):
        value = self.cleaned_data["confirmation_threshold"]
        if value < 1000:
            raise forms.ValidationError("Choisissez au moins 1 000 caractères.")
        return value

    def clean(self):
        data = super().clean()
        for prefix, label in (("default", "moteur par défaut"), ("second", "deuxième moteur")):
            engine = data.get(f"{prefix}_engine")
            if engine == "ai":
                if not data.get(f"{prefix}_ai_provider") or not data.get(f"{prefix}_ai_model"):
                    self.add_error(f"{prefix}_ai_provider",
                                   f"Pour une IA comme {label}, choisissez le fournisseur et le modèle.")
            else:
                data[f"{prefix}_ai_provider"], data[f"{prefix}_ai_model"] = "", ""
        first = (data.get("default_engine"), data.get("default_ai_provider"), data.get("default_ai_model"))
        second = (data.get("second_engine"), data.get("second_ai_provider"), data.get("second_ai_model"))
        if first[0] and first == second:
            self.add_error("second_engine", "Le deuxième moteur doit différer du moteur par défaut.")
        if second[0] and not first[0]:
            self.add_error("default_engine", "Choisissez d'abord un moteur par défaut.")
        return data


AI_PROVIDER_LABELS = dict(AI_PROVIDERS)


class ProjectForm(BootstrapMixin, forms.ModelForm):
    """Projet de traduction. Moteurs vides = ceux de Traduction → Moteurs."""

    class Meta:
        model = TranslationProject
        fields = ["title", "description", "source_lang", "target_lang", "confidential", "collection",
                  "default_engine", "default_ai_provider", "default_ai_model", "second_engine", "second_ai_provider",
                  "second_ai_model", "is_reference_corpus"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.library.models import Collection

        # Paires de la 1.3.0 (décision B2) : japonais → français, anglais → français.
        self.fields["source_lang"].choices = [("ja", "Japonais"), ("en", "Anglais")]
        self.fields["target_lang"].choices = [("fr", "Français")]
        self.fields["collection"].queryset = Collection.objects.filter(owner=user) if user else Collection.objects.none()
        self.fields["collection"].required = False
        for name in ("default_engine", "second_engine"):
            self.fields[name].help_text = "Vide : moteur choisi dans Traduction → Moteurs."

    def clean(self):
        data = super().clean()
        for prefix in ("default", "second"):
            if data.get(f"{prefix}_engine") == "ai":
                if not data.get(f"{prefix}_ai_provider") or not data.get(f"{prefix}_ai_model"):
                    self.add_error(f"{prefix}_ai_provider", "Pour une IA, choisissez le fournisseur et le modèle.")
            else:
                data[f"{prefix}_ai_provider"], data[f"{prefix}_ai_model"] = "", ""
        if data.get("confidential"):
            from .engines.registry import ENGINE_CLASSES

            for prefix in ("default", "second"):
                code = data.get(f"{prefix}_engine")
                if code and ENGINE_CLASSES[code].online:
                    self.add_error(f"{prefix}_engine", "Projet confidentiel : choisissez un moteur local (Argos) "
                                                       "ou laissez vide.")
        return data


class DocumentForm(BootstrapMixin, forms.Form):
    title = forms.CharField(label="Titre du document", max_length=300)
    variety = forms.ChoiceField(label="Variété de langue", choices=[("modern", "Japonais moderne"),
                                                                   ("classical", "Japonais classique (bungo)"),
                                                                   ("kanbun", "Kanbun")], initial="modern")
    text = forms.CharField(label="Texte à traduire (coller)", required=False, widget=forms.Textarea(attrs={"rows": 8}),
                           strip=False)
    file = forms.FileField(label="… ou fichier .txt, .docx, .pdf (avec texte)", required=False)

    def clean(self):
        data = super().clean()
        if not data.get("file") and not (data.get("text") or "").strip():
            raise forms.ValidationError("Collez un texte ou choisissez un fichier.")
        if data.get("file") and (data.get("text") or "").strip():
            raise forms.ValidationError("Collez un texte OU choisissez un fichier, pas les deux.")
        return data


class GlossaryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Glossary
        fields = ["name", "description", "source_lang", "target_lang"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_lang"].choices = [("ja", "Japonais"), ("en", "Anglais")]
        self.fields["target_lang"].choices = [("fr", "Français")]

    def clean(self):
        data = super().clean()
        g = self.instance
        if g.pk and (data.get("source_lang"), data.get("target_lang")) != (g.source_lang, g.target_lang):
            if g.project_links.exists():
                raise forms.ValidationError("Ce glossaire est utilisé par des projets : sa paire de langues ne peut "
                                            "plus changer (retirez-le d'abord des projets).")
        return data


class GlossaryEntryForm(BootstrapMixin, forms.Form):
    """Entrée de glossaire. Listes (à éviter, variantes) : valeurs séparées par « | »."""

    source_term = forms.CharField(label="Terme source", max_length=300)
    reading = forms.CharField(label="Lecture", max_length=300, required=False)
    target_term = forms.CharField(label="Terme cible", max_length=300)
    category = forms.ChoiceField(label="Catégorie", choices=GLOSSARY_CATEGORIES, initial="other")
    variants = forms.CharField(label="Variantes de graphie de l'original", required=False,
                               help_text="Séparées par « | » (exemple : 徳川家康 | 德川家康).")
    avoid = forms.CharField(label="Traductions à éviter", required=False, help_text="Séparées par « | ».")
    note = forms.CharField(label="Remarque", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    decision_source = forms.CharField(label="Source de la décision", max_length=300, required=False)

    @classmethod
    def initial_for(cls, entry):
        return {"source_term": entry.source_term, "reading": entry.reading, "target_term": entry.target_term,
                "category": entry.category, "variants": " | ".join(entry.variants), "avoid": " | ".join(entry.avoid),
                "note": entry.note, "decision_source": entry.decision_source}


class GlossaryImportForm(BootstrapMixin, forms.Form):
    file = forms.FileField(label="Fichier CSV", help_text="Colonnes : source_term, target_term (obligatoires), reading, "
                                                          "category, avoid, variants, note, decision_source.")
    update_existing = forms.BooleanField(label="Mettre à jour les termes déjà présents (sinon ils sont ignorés)",
                                         required=False)
    confirm_encoding = forms.BooleanField(label="J'ai vérifié l'aperçu : l'encodage détecté est correct", required=False)
