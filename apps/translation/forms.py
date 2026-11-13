from django import forms

from apps.ai.models import PROVIDERS as AI_PROVIDERS
from apps.core.forms import BootstrapMixin

from .models import EngineSetting, TranslationPreference


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
