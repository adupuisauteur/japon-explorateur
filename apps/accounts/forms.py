from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.core.forms import BootstrapMixin
from apps.core.models import AppSettings

from .models import User


class FirstRunForm(BootstrapMixin, UserCreationForm):
    display_name = forms.CharField(label="Nom affiché", required=False)
    default_search_mode = forms.ChoiceField(label="Mode d'enregistrement par défaut", choices=AppSettings.SEARCH_MODES,
                                            initial="selective",
                                            help_text="Le mode « Sélectif » est recommandé pour limiter l'encombrement.")
    backup_enabled = forms.BooleanField(label="Activer la sauvegarde quotidienne automatique", required=False, initial=True)
    # 2.0.0 (lot 7) : décoché par défaut — rien n'est téléchargé sans choix explicite (« plus tard » possible).
    install_argos = forms.BooleanField(
        label="Installer maintenant la traduction hors ligne japonais → français (Argos)", required=False,
        initial=False,
        help_text="Téléchargement unique d'environ 200 Mo depuis Internet (paquets japonais → anglais et anglais → "
                  "français). Vous pourrez aussi le faire plus tard, dans Traduction → Moteurs locaux.")
    setup_token = forms.CharField(label="Jeton de configuration (SETUP_TOKEN du fichier .env)", required=False,
                                  widget=forms.PasswordInput(render_value=False),
                                  help_text="Exigé lorsque l'application est accessible en HTTPS par d'autres personnes.")

    class Meta:
        model = User
        fields = ["username", "display_name", "email"]

    def __init__(self, *args, token_required=False, **kwargs):
        super().__init__(*args, **kwargs)
        if token_required:
            self.fields["setup_token"].required = True
        else:
            del self.fields["setup_token"]


class UserCreateForm(BootstrapMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ["username", "display_name", "email", "role"]


class UserEditForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["display_name", "email", "role", "is_active"]


class ProfileForm(BootstrapMixin, forms.ModelForm):
    preferred_sources = forms.MultipleChoiceField(label="Catalogues interrogés par défaut", required=False,
                                                  widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = User
        fields = ["display_name", "email", "default_search_mode", "preferred_sources"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.catalog.models import Catalogue

        self.fields["preferred_sources"].choices = [(c.code, c.name) for c in Catalogue.objects.all() if c.is_searchable]
