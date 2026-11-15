"""Enregistrement des incidents : point d'entrée unique pour tous les modules.

Règles :
- Une absence de résultat n'est jamais enregistrée comme incident (§2.7).
- Tout texte est expurgé *avant* écriture (secrets, adresses e-mail, dossiers personnels).
- Les incidents semblables sont regroupés par empreinte ; un incident corrigé qui
  se reproduit est rouvert et marqué « réapparu » (§3.8, §3.9).
- L'enregistrement ne doit jamais faire échouer l'opération qui le déclenche.
"""
import hashlib
import logging
import re
import traceback
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.logging import redact, redact_mapping

from .models import FIXED_STATUSES, SEVERITY_RANK, Incident, IncidentEvent, IncidentOccurrence

logger = logging.getLogger(__name__)

#: Nombre maximal d'occurrences détaillées conservées par incident (le compteur, lui, reste exact).
MAX_OCCURRENCES = 200

#: Correspondance nature d'échec du connecteur → (catégorie, gravité, origine probable).
CONNECTOR_KIND_MAP = {
    "unavailable": ("indisponibilite", "warning", "source_distante"),
    "technical": ("erreur_technique", "error", "connecteur"),
    "unparsable": ("reponse_illisible", "error", "connecteur"),
    "processing": ("erreur_traitement", "error", "traitement"),
    "config": ("configuration", "warning", "connecteur"),
}

_DIGITS = re.compile(r"\d+")
_URL = re.compile(r"https?://\S+")


def normalize_message(message):
    """Forme stable d'un message pour le regroupement (chiffres, adresses et durées neutralisés)."""
    text = _URL.sub("<url>", message or "")
    text = _DIGITS.sub("#", text)
    return " ".join(text.lower().split())[:300]


def fingerprint(module, source_code, category, technical_code, message):
    key = "|".join([module, source_code or "", category, technical_code or "", normalize_message(message)])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _new_uid():
    return f"INC-{timezone.localtime():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def record_incident(*, module, category, severity, title, message="", source_code="", origin="application",
                    operation="", technical_code="", http_status=None, request_id="", context=None,
                    group=True):
    """Enregistre (ou regroupe) un incident. Retourne l'incident, ou None si l'écriture a échoué."""
    try:
        return _record(module=module, category=category, severity=severity, title=title, message=message,
                       source_code=source_code, origin=origin, operation=operation, technical_code=technical_code,
                       http_status=http_status, request_id=request_id, context=context, group=group)
    except Exception:  # le journal ne doit jamais bloquer l'opération principale
        logger.exception("Impossible d'enregistrer l'incident « %s »", title)
        return None


def _record(*, module, category, severity, title, message, source_code, origin, operation, technical_code,
            http_status, request_id, context, group):
    version = settings.APP_VERSION
    now = timezone.now()
    title = redact(title)[:300]
    message = redact(message or "")[:4000]
    operation = redact(operation or "")[:300]
    context = redact_mapping(context or {})
    fp = fingerprint(module, source_code, category, technical_code, message or title)
    new_group = reappeared = False
    with transaction.atomic():
        incident = None
        if group:
            incident = (Incident.objects.select_for_update().filter(fingerprint=fp, is_manual=False)
                        .order_by("-last_seen_at").first())
        if incident is None:
            incident = Incident.objects.create(
                uid=_new_uid(), fingerprint=fp, module=module, source_code=source_code or "", category=category,
                severity=severity, origin=origin, operation=operation, title=title, message=message,
                technical_code=technical_code or "", http_status=http_status, last_request_id=request_id or "",
                context=context, first_seen_at=now, last_seen_at=now, first_seen_version=version,
                last_seen_version=version,
            )
            IncidentEvent.objects.create(incident=incident, kind="created", to_status="nouveau", app_version=version,
                                         comment="Enregistrement automatique.")
            new_group = True
        else:
            incident.occurrence_count += 1
            incident.last_seen_at = now
            incident.last_seen_version = version
            incident.last_request_id = request_id or incident.last_request_id
            incident.context = context or incident.context
            incident.http_status = http_status or incident.http_status
            if SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(incident.severity, 0):
                incident.severity = severity
            if incident.status in FIXED_STATUSES:
                previous = incident.status
                incident.status = "a_analyser"
                incident.reappeared_count += 1
                reappeared = True
                IncidentEvent.objects.create(
                    incident=incident, kind="reappeared", from_status=previous, to_status="a_analyser",
                    app_version=version,
                    comment=(f"Le problème s'est reproduit après correction"
                             f"{' (corrigé en ' + incident.fixed_in_version + ')' if incident.fixed_in_version else ''}."))
            incident.save()
        IncidentOccurrence.objects.create(incident=incident, occurred_at=now, app_version=version,
                                          request_id=request_id or "", operation=operation, message=message,
                                          http_status=http_status, context=context)
        _trim(incident)
    if new_group or reappeared:
        # 2.0.0 (lot 5) : une fenêtre par nouveau groupe d'incidents, après validation de l'enregistrement.
        from apps.notifications.services import incident_group, notify_after_commit

        notify_after_commit(incident_group, incident, reappeared=reappeared)
    return incident


def _trim(incident):
    ids = list(incident.occurrences.order_by("-occurred_at", "-pk").values_list("pk", flat=True)[MAX_OCCURRENCES:])
    if ids:
        IncidentOccurrence.objects.filter(pk__in=ids).delete()


# --------------------------------------------------------------------------- aides par module


def record_connector_error(exc, *, module="recherche", source_code="", operation="", extra=None):
    """Journalise un ConnectorError en tenant compte de sa nature (indisponibilité ≠ défaut du connecteur)."""
    kind = getattr(exc, "kind", "technical")
    category, severity, origin = CONNECTOR_KIND_MAP.get(kind, CONNECTOR_KIND_MAP["technical"])
    diag = dict(getattr(exc, "diagnostic", {}) or {})
    if kind == "unavailable" and diag.get("network_hint") == "dns":
        origin = "reseau"
    if extra:
        diag.update(extra)
    labels = dict(Incident._meta.get_field("category").choices)
    return record_incident(
        module=module, category=category, severity=severity, origin=origin, source_code=source_code,
        title=f"{labels.get(category, category)} — {source_code or 'source inconnue'}",
        message=str(exc), operation=operation, technical_code=getattr(exc, "code", "") or kind,
        http_status=getattr(exc, "http_status", None) or diag.get("http_status"),
        request_id=diag.get("request_id", ""), context=diag,
    )


def short_traceback(exc, limit=6):
    """Dernières lignes de la pile d'appels, limitées au code de l'application (expurgées)."""
    frames = traceback.extract_tb(exc.__traceback__)
    lines = [f"{f.filename.split('/apps/')[-1] if '/apps/' in f.filename else f.filename.rsplit('/', 1)[-1]}"
             f":{f.lineno} {f.name}" for f in frames[-limit:]]
    return [redact(line) for line in lines]


def record_exception(exc, *, module, operation="", source_code="", category="erreur_application",
                     severity="error", origin="application", extra=None, request_id=""):
    """Journalise une exception inattendue (avec un extrait court de la pile d'appels)."""
    context = {"exception": exc.__class__.__name__, "traceback": short_traceback(exc)}
    if extra:
        context.update(extra)
    return record_incident(
        module=module, category=category, severity=severity, origin=origin, source_code=source_code,
        title=f"{exc.__class__.__name__} pendant : {operation or module}"[:300], message=str(exc)[:2000],
        operation=operation, technical_code=exc.__class__.__name__, context=context,
        request_id=request_id or context.get("request_id", ""),
    )


def record_database_error(exc, *, module="base_de_donnees", operation="", source_code="", request_id=""):
    """Erreur de base de données : alerte prioritaire (risque de perte ou de corruption de données)."""
    return record_exception(exc, module=module, operation=operation, source_code=source_code,
                            category="erreur_critique", severity="critical", origin="application",
                            request_id=request_id)


def note_source_recovered(source_code):
    """Ajoute à l'historique des indisponibilités ouvertes que la source répond de nouveau (sans changer le statut)."""
    try:
        open_unavail = Incident.objects.filter(source_code=source_code, category="indisponibilite",
                                               status__in=("nouveau", "a_analyser"))
        for incident in open_unavail:
            last = incident.events.order_by("-at").first()
            if last and last.kind == "recovered":
                continue
            IncidentEvent.objects.create(incident=incident, kind="recovered", app_version=settings.APP_VERSION,
                                         comment="La source a répondu normalement à une recherche ultérieure : "
                                                 "l'indisponibilité était temporaire.")
    except Exception:
        logger.exception("Mise à jour des indisponibilités impossible")


def change_status(incident, new_status, user=None, comment=""):
    previous = incident.status
    if new_status == previous and not comment:
        return incident
    incident.status = new_status
    if new_status == "corrige":
        incident.fixed_at = timezone.now()
        incident.fixed_in_version = incident.fixed_in_version or settings.APP_VERSION
    incident.save()
    IncidentEvent.objects.create(incident=incident, kind="status" if new_status != previous else "comment",
                                 from_status=previous, to_status=new_status, comment=redact(comment)[:2000],
                                 user=user, app_version=settings.APP_VERSION)
    return incident


def before_after_fix(incident):
    """Compare les occurrences avant et après la dernière correction (§3.8)."""
    fixed_event = incident.events.filter(to_status="corrige").order_by("-at").first()
    if fixed_event is None:
        return None
    occ = incident.occurrences
    before = occ.filter(occurred_at__lt=fixed_event.at)
    after = occ.filter(occurred_at__gte=fixed_event.at)
    return {"fixed_at": fixed_event.at, "fixed_in_version": incident.fixed_in_version,
            "before": before.count(), "after": after.count(),
            "last_before": before.order_by("-occurred_at").first(),
            "first_after": after.order_by("occurred_at").first()}
