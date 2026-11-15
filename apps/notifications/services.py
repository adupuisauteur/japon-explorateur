"""Création et lecture des notifications (2.0.0, lot 5).

Règles :

- une notification n'est créée que si son destinataire ne l'a pas désactivée (préférences par type) ;
- une seule notification **non lue** par groupe (`group_key`) : un incident qui se répète, ou une tâche relancée,
  ne multiplie pas les fenêtres ;
- les dysfonctionnements ne vont qu'aux administrateurs, une fenêtre par **nouveau groupe** d'incidents (ou par
  retour d'un problème corrigé), à partir du seuil de gravité choisi par chacun ;
- une erreur ici ne doit jamais faire échouer l'opération qui notifie : elle est journalisée, jamais masquée.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import (ADMIN_ONLY, CONFIGURABLE, DEFAULT_INCIDENT_THRESHOLD, Notification,
                     NotificationPreference)

logger = logging.getLogger(__name__)

INCIDENT_RANK = {"info": 0, "warning": 1, "error": 2, "critical": 3}
POPUP_BATCH = 5


# --------------------------------------------------------------------------- préférences


def preference(user, event_type):
    pref = NotificationPreference.objects.filter(user=user, event_type=event_type, channel="app").first()
    if pref is None:
        return NotificationPreference(user=user, event_type=event_type, channel="app", enabled=True,
                                      min_severity=DEFAULT_INCIDENT_THRESHOLD if event_type == "incident" else "")
    return pref


def wants(user, event_type, *, incident_severity=None):
    if user is None or not user.is_active:
        return False
    if event_type in ADMIN_ONLY and not user.is_admin_role:
        return False
    if event_type not in CONFIGURABLE:
        return True
    pref = preference(user, event_type)
    if not pref.enabled:
        return False
    if event_type == "incident" and incident_severity is not None:
        threshold = pref.min_severity or DEFAULT_INCIDENT_THRESHOLD
        return INCIDENT_RANK.get(incident_severity, 0) >= INCIDENT_RANK.get(threshold, 2)
    return True


def save_preferences(user, enabled_types, incident_threshold=None):
    for event_type in CONFIGURABLE:
        if event_type in ADMIN_ONLY and not user.is_admin_role:
            continue
        pref, _ = NotificationPreference.objects.get_or_create(user=user, event_type=event_type, channel="app")
        pref.enabled = event_type in enabled_types
        if event_type == "incident" and incident_threshold in INCIDENT_RANK:
            pref.min_severity = incident_threshold
        pref.save()


# --------------------------------------------------------------------------- création


def notify(user, event_type, title, *, body="", link="", severity="info", group_key="", incident_severity=None):
    """Crée une notification si l'utilisateur la veut. Retourne la notification, ou None."""
    try:
        if not wants(user, event_type, incident_severity=incident_severity):
            return None
        if group_key and Notification.objects.filter(recipient=user, group_key=group_key,
                                                     read_at__isnull=True).exists():
            return None
        return Notification.objects.create(recipient=user, event_type=event_type, severity=severity,
                                           title=title[:200], body=body[:1000], link=link[:500],
                                           group_key=group_key[:120])
    except Exception:  # noqa: BLE001 — une notification ne fait jamais échouer l'opération notifiée
        logger.exception("Notification non créée (%s, %s)", event_type, title[:60])
        return None


def notify_admins(event_type, title, **kwargs):
    admins = get_user_model().objects.filter(Q(role="admin") | Q(is_superuser=True), is_active=True)
    return [n for n in (notify(admin, event_type, title, **kwargs) for admin in admins) if n]


def notify_after_commit(func, *args, **kwargs):
    """Notifie après la validation de la transaction en cours (jamais pour une opération annulée)."""
    transaction.on_commit(lambda: func(*args, **kwargs))


# --------------------------------------------------------------------------- événements


def incident_group(incident, *, reappeared=False):
    """Nouveau groupe d'incidents (ou problème corrigé qui revient) : fenêtre pour les administrateurs."""
    prefix = "Problème revenu après correction" if reappeared else "Nouveau dysfonctionnement"
    severity = {"critical": "critical", "error": "error", "warning": "warning"}.get(incident.severity, "info")
    return notify_admins(
        "incident", f"{prefix} : {incident.title}"[:200],
        body=f"{incident.get_module_display()} · gravité {incident.get_severity_display().lower()} · {incident.uid}",
        link=reverse("incidents:detail", args=[incident.uid]), severity=severity,
        group_key=f"incident:{incident.uid}", incident_severity=incident.severity)


def translation_job_ended(job):
    """Tâche de traduction terminée, terminée avec des erreurs, en échec ou interrompue."""
    if job.user_id is None or job.status not in ("done", "failed", "interrupted"):
        return None
    link = reverse("translation:job_detail", args=[job.pk])
    label = job.scope_label or f"tâche n° {job.pk}"
    counts = f"{job.done_items} traduit(s), {job.failed_items} en échec, {job.skipped_items} ignoré(s)"
    if job.status == "interrupted":
        return notify(job.user, "task_paused", f"Traduction interrompue : {label}",
                      body=(job.error_summary or "La tâche peut être reprise.")[:600], link=link,
                      severity="warning", group_key=f"translation:{job.pk}:paused")
    if job.status == "failed" or job.failed_items:
        return notify(job.user, "task_errors",
                      f"Traduction {'en échec' if job.status == 'failed' else 'terminée avec des erreurs'} : {label}",
                      body=f"{counts}. {job.error_summary}".strip()[:600], link=link, severity="error",
                      group_key=f"translation:{job.pk}:end")
    return notify(job.user, "task_done", f"Traduction terminée : {label}", body=counts, link=link,
                  severity="success", group_key=f"translation:{job.pk}:end")


def export_ended(job):
    link = job.get_absolute_url()
    if job.status == "done":
        return notify(job.owner, "task_done", f"Export prêt : {job.title}"[:200],
                      body=f"{job.get_format_display()} · {job.export_uid}", link=link, severity="success",
                      group_key=f"export:{job.pk}")
    if job.status == "failed":
        return notify(job.owner, "task_errors", f"Export en échec : {job.title}"[:200],
                      body=(job.error or "")[:600], link=link, severity="error", group_key=f"export:{job.pk}")
    return None


def sync_ended(job):
    """Synchronisation d'une source : son auteur ; une synchronisation planifiée va aux administrateurs."""
    link = job.get_absolute_url()
    name = job.catalogue.name if job.catalogue_id else "source"
    if job.status == "failed":
        args = ("task_errors", f"Synchronisation en échec : {name}")
        kwargs = {"body": (getattr(job, "message", "") or "")[:600], "severity": "error"}
    elif job.status == "review":
        args = ("task_done", f"Synchronisation à valider : {name}")
        kwargs = {"body": "Des notices nouvelles, modifiées ou disparues attendent votre décision.",
                  "severity": "info"}
    elif job.status == "done":
        if job.triggered_by_id is None:
            return []  # synchronisation planifiée sans changement : pas de fenêtre
        args = ("task_done", f"Synchronisation terminée : {name}")
        kwargs = {"body": "Aucun changement à valider.", "severity": "success"}
    else:
        return []
    kwargs.update(link=link, group_key=f"sync:{job.pk}")
    if job.triggered_by_id:
        n = notify(job.triggered_by, *args, **kwargs)
        return [n] if n else []
    return notify_admins(*args, **kwargs)


def test(user, *, kind="task"):
    """Notification d'essai, demandée par l'utilisateur (toujours remise)."""
    if kind == "incident" and user.is_admin_role:
        # Présentée exactement comme une vraie alerte (en-tête, icône, bouton), seul le titre dit « [Essai] ».
        return Notification.objects.create(
            recipient=user, event_type="incident", severity="error",
            title="[Essai] Nouveau dysfonctionnement : exemple d'alerte",
            body="Alerte fictive : aucun incident n'a été enregistré. Le bouton « Vu » la marque comme lue.",
            link=reverse("incidents:list"))
    return Notification.objects.create(
        recipient=user, event_type="test", severity="success",
        title="[Essai] Tâche terminée : exemple de notification",
        body="Notification fictive, demandée depuis vos préférences. Aucune tâche n'a été lancée.",
        link=reverse("notifications:list"))


# --------------------------------------------------------------------------- lecture


def unread_count(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def take_popups(user, limit=POPUP_BATCH):
    """Fenêtres à afficher (pas encore affichées, non lues), marquées comme affichées.

    Les fenêtres d'un utilisateur absent attendent sa prochaine visite.
    """
    pending = list(Notification.objects.filter(recipient=user, popup_shown_at__isnull=True, read_at__isnull=True)
                   .order_by("created_at", "pk")[:limit])
    if pending:
        Notification.objects.filter(pk__in=[n.pk for n in pending]).update(popup_shown_at=timezone.now())
    return pending


def mark_read(user, ids=None):
    qs = Notification.objects.filter(recipient=user, read_at__isnull=True)
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    return qs.update(read_at=timezone.now(), popup_shown_at=timezone.now())
