from django import forms

from .models import AppSettings


class BootstrapMixin:
    """Ajoute les classes Bootstrap aux widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class AppSettingsForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = ["instance_name", "default_search_mode", "temporary_session_days", "backup_enabled",
                  "backup_retention", "export_default_author", "export_default_header", "export_default_footer"]
