"""
Journalisation des erreurs du module de traduction (module « traduction » du journal 1.2.0).

Règles (cahier des charges § 17 et § 13) :
- jamais de texte original ni traduit, jamais de clé : seul le diagnostic du client HTTP du module
  (adresse expurgée, code HTTP, durée, nombre de textes et de caractères) est transmis ;
- les erreurs dues à un choix de l'utilisateur (paire non prise en charge, opération non proposée) ne
  créent pas d'incident : elles sont seulement expliquées à l'écran (NOT_AN_INCIDENT de la 1.2.0) ;
- la catégorie vient de `exc.code` quand c'est une catégorie de traduction, sinon de la nature d'erreur.
"""
from apps.connectors.base import NOT_AN_INCIDENT
from apps.core.logging import redact_mapping
from apps.incidents.models import CATEGORIES
from apps.incidents.services import CONNECTOR_KIND_MAP, record_incident

TRANSLATION_CATEGORIES = {code for code, _ in CATEGORIES}

#: champs de diagnostic autorisés dans un incident (liste blanche : rien d'autre ne passe)
ALLOWED_DIAGNOSTIC_KEYS = {"request_id", "url", "method", "engine", "elapsed_ms", "timeout_s", "texts", "chars",
                           "attempts", "http_status", "service_code", "exception", "provider", "model", "path"}

SEVERITY = {"quota_depasse": "warning", "cle_refusee": "warning", "delai_depasse": "warning",
            "paquet_absent": "warning", "lot_interrompu": "warning"}


def record_translation_error(exc, *, engine, operation=""):
    """Enregistre (ou regroupe) un incident pour une erreur de moteur. Retourne l'incident ou None."""
    kind = getattr(exc, "kind", "technical")
    if kind in NOT_AN_INCIDENT:
        return None
    code = getattr(exc, "code", "") or ""
    base_category, base_severity, origin = CONNECTOR_KIND_MAP.get(kind, CONNECTOR_KIND_MAP["technical"])
    category = code if code in TRANSLATION_CATEGORIES else base_category
    severity = SEVERITY.get(category, base_severity)
    diag = {k: v for k, v in (getattr(exc, "diagnostic", {}) or {}).items() if k in ALLOWED_DIAGNOSTIC_KEYS}
    labels = dict(CATEGORIES)
    return record_incident(
        module="traduction", category=category, severity=severity, origin=origin, source_code=engine,
        title=f"{labels.get(category, category)} — {engine}", message=str(exc), operation=operation,
        technical_code=code or kind, http_status=getattr(exc, "http_status", None) or diag.get("http_status"),
        request_id=diag.get("request_id", ""), context=redact_mapping(diag),
    )
