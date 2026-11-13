import json

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

SESSION_STATUS = {"ok": "Réponse reçue", "warning": "Réponse avec avertissement", "error": "Erreur",
                  "pending": "En attente", "running": "Interrogation…", "empty": "Aucun résultat",
                  "unavailable": "Source indisponible", "unparsable": "Réponse illisible"}
ORIGIN_CHIPS = {"ai": ("chip-ai", "IA"), "user": ("", "utilisateur"), "rule": ("", "règle automatique"),
                "source": ("", "source")}
COMPARISON_CHIPS = {"new": ("chip-new", "Nouveau"), "known": ("", "Déjà connu"), "modified": ("chip-warn", "Modifié"),
                    "unavailable": ("chip-warn", "Indisponible"), "not_comparable": ("", "Non comparable"),
                    "unchanged": ("", "Inchangée"), "missing": ("chip-warn", "Non retrouvée"),
                    "error": ("chip-ai", "Erreur"), "possible_duplicate": ("chip-warn", "Doublon potentiel")}


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def pretty_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


@register.simple_tag
def origin_chip(origin):
    if not origin:
        return ""
    cls, label = ORIGIN_CHIPS.get(origin, ("", origin))
    return format_html('<span class="chip {}" title="Origine de la donnée">{}</span>', cls, label)


@register.simple_tag
def comparison_chip(value):
    if not value:
        return ""
    cls, label = COMPARISON_CHIPS.get(value, ("", value))
    return format_html('<span class="chip {}">{}</span>', cls, label)


@register.filter
def session_status_label(value):
    return SESSION_STATUS.get(value, value)


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Construit une chaîne de requête en remplaçant certains paramètres."""
    query = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            query.pop(k, None)
        else:
            query[k] = v
    return "?" + query.urlencode() if query else "?"


@register.filter
def status_badge(catalogue):
    badge = format_html('<span class="badge badge-status status-{}">{}</span>', catalogue.status,
                        catalogue.get_status_display())
    if catalogue.needs_real_verification:
        badge += format_html(' <span class="badge badge-status status-unverified" title="{}">Non vérifié en conditions '
                             'réelles</span>', "Aucun test réussi sur le service réel : utilisez « Tester le connecteur ».")
    return badge


@register.filter
def unverified_chip(catalogue):
    if catalogue is not None and catalogue.needs_real_verification:
        return mark_safe('<span class="chip chip-warn" title="Aucun test réussi sur le service réel">non vérifié</span>')
    return ""


@register.filter
def yesno_icon(value):
    return mark_safe('<i class="bi bi-check-circle text-success" aria-label="oui"></i>' if value
                     else '<i class="bi bi-dash-circle text-muted" aria-label="non"></i>')


_EXTRA_LABELS = {"record_id": "Identifiant interne", "catalogue_name": "Catalogue", "collected_at": "Date de collecte",
                 "period": "Période (normalisée)", "document_type": "Type (normalisé)", "material_type": "Support (normalisé)",
                 "record_status": "Statut de la notice", "composition_year_start": "Composition : début",
                 "composition_year_end": "Composition : fin", "copy_year_start": "Exemplaire : début",
                 "copy_year_end": "Exemplaire : fin", "composition_date_precision": "Précision (composition)",
                 "copy_date_precision": "Précision (exemplaire)"}
_HIDDEN = {"norm", "catalogue_code", "record_status"}


@register.filter
def field_label(key):
    from apps.updates.importers import FIELD_LABELS

    return FIELD_LABELS.get(key) or _EXTRA_LABELS.get(key) or key


@register.filter
def visible_fields(data):
    """Champs non vides d'un résultat, dans un ordre lisible."""
    from apps.updates.importers import FIELD_LABELS

    order = list(FIELD_LABELS) + list(_EXTRA_LABELS)
    items = [(k, v) for k, v in (data or {}).items() if v not in (None, "") and k not in _HIDDEN]
    return sorted(items, key=lambda kv: order.index(kv[0]) if kv[0] in order else 999)


# --------------------------------------------------------------------------- journal des dysfonctionnements (1.2.0)

SEVERITY_ICONS = {"info": "bi-info-circle", "warning": "bi-exclamation-triangle", "error": "bi-x-octagon",
                  "critical": "bi-exclamation-octagon-fill"}


@register.simple_tag
def severity_chip(incident_or_code, label=None):
    code = getattr(incident_or_code, "severity", incident_or_code)
    if label is None:
        label = incident_or_code.get_severity_display() if hasattr(incident_or_code, "get_severity_display") else code
    return format_html('<span class="chip chip-sev-{}"><i class="bi {}" aria-hidden="true"></i> {}</span>',
                       code, SEVERITY_ICONS.get(code, "bi-circle"), label)


@register.simple_tag
def incident_status_chip(incident):
    return format_html('<span class="chip chip-st-{}">{}</span>', incident.status, incident.get_status_display())
