from django import forms

from apps.core.forms import BootstrapMixin

from .models import MODULES, SEVERITIES, STATUSES

SCREENSHOT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
SCREENSHOT_MAX_BYTES = 5 * 1024 * 1024


class FilterForm(BootstrapMixin, forms.Form):
    q = forms.CharField(label="Identifiant ou texte", required=False)
    date_from = forms.DateField(label="Du", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="Au", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    module = forms.ChoiceField(label="Module", required=False, choices=[("", "Tous")] + MODULES)
    source = forms.ChoiceField(label="Source", required=False, choices=[("", "Toutes")])
    severity = forms.ChoiceField(label="Gravité", required=False, choices=[("", "Toutes")] + SEVERITIES)
    status = forms.ChoiceField(label="Statut", required=False,
                               choices=[("", "Tous"), ("ouverts", "Non résolus")] + STATUSES)
    manual = forms.ChoiceField(label="Type", required=False,
                               choices=[("", "Tous"), ("auto", "Automatiques"), ("manual", "Signalements manuels")])

    def __init__(self, *args, sources=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].choices = [("", "Toutes")] + [(s, s) for s in sources]


class ManualReportForm(BootstrapMixin, forms.Form):
    module = forms.ChoiceField(label="Module concerné", choices=MODULES)
    severity = forms.ChoiceField(label="Gravité perçue", choices=SEVERITIES, initial="warning")
    description = forms.CharField(label="Description du problème", max_length=3000,
                                  widget=forms.Textarea(attrs={"rows": 3}))
    steps = forms.CharField(label="Opérations réalisées", required=False, max_length=3000,
                            widget=forms.Textarea(attrs={"rows": 3}),
                            help_text="Dans l'ordre : page ouverte, boutons cliqués, texte saisi…")
    expected = forms.CharField(label="Résultat attendu", required=False, max_length=2000,
                               widget=forms.Textarea(attrs={"rows": 2}))
    obtained = forms.CharField(label="Résultat obtenu", required=False, max_length=2000,
                               widget=forms.Textarea(attrs={"rows": 2}))
    source_code = forms.CharField(label="Source documentaire (facultatif)", required=False, max_length=50)
    screenshot = forms.FileField(label="Capture d'écran (facultative)", required=False,
                                 help_text="PNG, JPEG, WebP ou GIF, 5 Mo au plus. Vérifiez qu'elle ne montre "
                                           "aucune information confidentielle.")

    def clean_screenshot(self):
        f = self.cleaned_data.get("screenshot")
        if not f:
            return f
        if not f.name.lower().endswith(SCREENSHOT_EXTENSIONS):
            raise forms.ValidationError("Format non accepté (PNG, JPEG, WebP ou GIF).")
        if f.size > SCREENSHOT_MAX_BYTES:
            raise forms.ValidationError("Fichier trop volumineux (5 Mo au plus).")
        head = f.read(12)
        f.seek(0)
        signatures = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")
        if not any(head.startswith(sig) for sig in signatures):
            raise forms.ValidationError("Le fichier ne semble pas être une image.")
        return f


class StatusForm(BootstrapMixin, forms.Form):
    status = forms.ChoiceField(label="Nouveau statut", choices=STATUSES)
    comment = forms.CharField(label="Commentaire", required=False, max_length=2000,
                              widget=forms.Textarea(attrs={"rows": 2}))


class ExportForm(forms.Form):
    format = forms.ChoiceField(choices=[("md", "Texte lisible (Markdown)"), ("json", "Données structurées (JSON)")],
                               initial="md")
    hide_terms = forms.BooleanField(label="Masquer les termes de recherche", required=False)
