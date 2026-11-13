from django import forms

from apps.catalog.models import DIGITAL_ACCESS, DOCUMENT_TYPES, LANGUAGES, MATERIAL_TYPES, PERIODS, Catalogue
from apps.core.forms import BootstrapMixin

from .models import MODES


def _choices(items):
    return [(k, v) for k, v in items if k]


class SearchForm(BootstrapMixin, forms.Form):
    q = forms.CharField(label="Requête", required=False, max_length=500)
    variants = forms.MultipleChoiceField(label="Variantes retenues", required=False)
    title = forms.CharField(label="Titre", required=False)
    creator = forms.CharField(label="Auteur / personne", required=False)
    subject = forms.CharField(label="Sujet", required=False)
    place = forms.CharField(label="Lieu / institution", required=False)
    date_from = forms.IntegerField(label="De (année)", required=False, min_value=500, max_value=2100)
    date_to = forms.IntegerField(label="À (année)", required=False, min_value=500, max_value=2100)
    date_kind = forms.ChoiceField(label="Date concernée", required=False, choices=[
        ("any", "Composition ou exemplaire"), ("composition", "Composition de l'œuvre"),
        ("copy", "Copie / impression / édition de l'exemplaire")])
    period = forms.MultipleChoiceField(label="Période", required=False, choices=_choices(PERIODS),
                                       widget=forms.CheckboxSelectMultiple)
    document_type = forms.MultipleChoiceField(label="Type documentaire", required=False,
                                              choices=_choices(DOCUMENT_TYPES), widget=forms.CheckboxSelectMultiple)
    material_type = forms.MultipleChoiceField(label="Support", required=False, choices=_choices(MATERIAL_TYPES),
                                              widget=forms.CheckboxSelectMultiple)
    digital_access = forms.MultipleChoiceField(label="Accès numérique", required=False,
                                               choices=_choices(DIGITAL_ACCESS), widget=forms.CheckboxSelectMultiple)
    language = forms.MultipleChoiceField(label="Langue", required=False, choices=_choices(LANGUAGES),
                                         widget=forms.CheckboxSelectMultiple)
    sources = forms.MultipleChoiceField(label="Catalogues interrogés", required=True,
                                        widget=forms.CheckboxSelectMultiple,
                                        error_messages={"required": "Choisissez au moins un catalogue."})
    remember_sources = forms.BooleanField(label="Mémoriser ce choix de catalogues", required=False)
    mode = forms.ChoiceField(label="Mode d'enregistrement", choices=MODES)
    target_collection = forms.ChoiceField(label="Dossier de destination (facultatif)", required=False)

    def __init__(self, *args, user=None, extra_variants=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sources"].choices = [(c.code, c.name) for c in Catalogue.objects.all() if c.is_searchable]
        self.fields["variants"].choices = [(v, v) for v in extra_variants]
        if user is not None:
            from apps.library.models import Collection

            self.fields["target_collection"].choices = [("", "— Bibliothèque uniquement")] + [
                (str(c.pk), c.title) for c in Collection.objects.filter(owner=user)]

    def clean(self):
        data = super().clean()
        has_query = any(data.get(k) for k in ("q", "title", "creator", "subject", "place"))
        has_filter = any(data.get(k) for k in ("period", "document_type", "date_from", "date_to"))
        if not has_query and not has_filter:
            raise forms.ValidationError("Saisissez une requête ou au moins un critère.")
        return data
