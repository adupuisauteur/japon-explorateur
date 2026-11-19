"""
File des tâches de traduction (2.0.0, lot 3) : lancement immédiat, « maintenant », programmé ou de nuit.

Décisions du 15 novembre 2026 :
- la plage de nuit est choisie par l'utilisateur (aucune valeur par défaut) ; sans plage, pas de file de nuit ;
- une plage qui commence alors que J-ed n'était pas en marche (ordinateur allumé après le début de la plage)
  ne démarre pas d'elle-même : les tâches de nuit attendent une nouvelle confirmation ;
- une tâche programmée dont l'heure est passée pendant un arrêt de J-ed attend aussi une confirmation ;
- un plafond atteint en cours de tâche met la tâche en pause, sans jamais changer de moteur.

L'horloge (`clock`) est appelée chaque minute par Celery beat. Une tâche en cours se met en pause entre deux
paquets (fin de plage, plafond, demande de l'utilisateur), jamais au milieu d'un envoi : rien n'est renvoyé.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

from .models import TranslationJob, TranslationPreference

#: une tâche programmée part si l'horloge la voit au plus tard ce délai après son heure ; au-delà : en retard
SCHEDULE_GRACE = timedelta(minutes=5)
#: même règle pour le début de la plage de nuit
NIGHT_GRACE = timedelta(minutes=5)
ACTIVE = ("confirmed", "running")


class QueueError(Exception):
    pass


# --------------------------------------------------------------------------- plage de nuit


def has_night_window(pref):
    return bool(pref and pref.night_start is not None and pref.night_end is not None
                and pref.night_start != pref.night_end)


def _aware(day, time_value):
    return timezone.make_aware(datetime.combine(day, time_value), timezone.get_current_timezone())


def current_window(pref, now=None):
    """(début, fin) de la plage de nuit en cours, ou None. La plage peut passer minuit (22:00 → 07:00)."""
    if not has_night_window(pref):
        return None
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    overnight = pref.night_end <= pref.night_start
    for day in (today - timedelta(days=1), today):
        start = _aware(day, pref.night_start)
        end = _aware(day + timedelta(days=1) if overnight else day, pref.night_end)
        if start <= now < end:
            return start, end
    return None


def next_window_start(pref, now=None):
    if not has_night_window(pref):
        return None
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    for day in (today, today + timedelta(days=1)):
        start = _aware(day, pref.night_start)
        if start > now:
            return start
    return None


def window_label(pref):
    if not has_night_window(pref):
        return ""
    return f"{pref.night_start:%H:%M} – {pref.night_end:%H:%M}"


# --------------------------------------------------------------------------- lancement


def queue_for(job):
    """File Celery : « maintenant » pour une demande depuis une fiche ou une petite tâche immédiate."""
    if job.launch == "now" or (job.launch == "immediate"
                               and job.total_items <= settings.TRANSLATION_ARGOS_NOW_MAX_ITEMS):
        return "maintenant"
    return "traduction"


def _next_position(user):
    top = TranslationJob.objects.filter(user=user, launch="night").aggregate(m=Max("queue_position"))["m"]
    return (top or 0) + 1


def place(job, launch, *, scheduled_for=None, now=None):
    """Met une tâche confirmée à sa place : départ immédiat (retourne True) ou attente (False)."""
    now = now or timezone.now()
    if launch in ("immediate", "now"):
        job.launch, job.status = launch, "confirmed"
        job.save(update_fields=["launch", "status", "confirmed_at"])
        return True
    if launch == "scheduled":
        if scheduled_for is None or scheduled_for <= now:
            raise QueueError("Choisissez une date et une heure à venir.")
        job.launch, job.status, job.scheduled_for = "scheduled", "scheduled", scheduled_for
        job.save(update_fields=["launch", "status", "scheduled_for", "confirmed_at"])
        return False
    if launch == "night":
        pref = TranslationPreference.objects.filter(user=job.user).first()
        if not has_night_window(pref):
            raise QueueError("Choisissez d'abord la plage de la file de nuit (Traduction → Moteurs).")
        job.launch, job.status, job.queue_position = "night", "scheduled", _next_position(job.user)
        job.save(update_fields=["launch", "status", "queue_position", "confirmed_at"])
        return False
    raise QueueError("Lancement inconnu.")


def _start(job, now):
    """Départ d'une tâche en attente (horloge) : vérifications, puis envoi au worker. Retourne True si lancée."""
    from . import services

    problems = services.blocking_problems(job, resuming=True)
    if problems:
        services._touch(job, status="interrupted", error_summary=("Départ impossible : " + " ".join(problems))[:2000])
        return False
    job.status, job.pause_reason, job.error_summary = "confirmed", "", ""
    job.save(update_fields=["status", "pause_reason", "error_summary"])
    transaction.on_commit(lambda: services.dispatch(job))
    return True


# --------------------------------------------------------------------------- horloge


def clock(now=None):
    """Appelée chaque minute. Retourne un petit bilan (pour les tests et le journal)."""
    now = now or timezone.now()
    report = {"started": [], "late": [], "night_reports": 0}
    _scheduled(now, report)
    _after(now, report)
    for pref in TranslationPreference.objects.exclude(night_start=None).exclude(night_end=None).select_related("user"):
        _night(pref, now, report)
    return report


def _after(now, report):
    """Filet de sécurité : résumé « après la traduction » dont la traduction est déjà terminée ou annulée."""
    from .summaries import start_after

    for job in TranslationJob.objects.filter(launch="after", status="scheduled"):
        before = TranslationJob.objects.filter(pk=(job.options or {}).get("after_job")).first()
        if before is None or before.status in ("done", "failed", "cancelled"):
            if before is None:
                _start(job, now)
            else:
                start_after(before)
            report["started"].append(job.pk)


def _scheduled(now, report):
    from apps.notifications.services import notify

    for job in TranslationJob.objects.filter(launch="scheduled", status="scheduled",
                                             scheduled_for__lte=now).select_related("user", "project"):
        if now - job.scheduled_for <= SCHEDULE_GRACE:
            if _start(job, now):
                report["started"].append(job.pk)
            continue
        job.status = "late"
        job.save(update_fields=["status"])
        report["late"].append(job.pk)
        if job.user_id:
            notify(job.user, "task_paused", f"Traduction en retard : {job.scope_label or f'tâche n° {job.pk}'}"[:200],
                   body=(f"Elle était prévue le {timezone.localtime(job.scheduled_for):%d/%m/%Y à %H:%M}, alors que "
                         "J-ed était arrêté. Elle ne part jamais d'elle-même : confirmez-la, reprogrammez-la ou "
                         "annulez-la."), link=reverse("translation:job_detail", args=[job.pk]), severity="warning",
                   group_key=f"translation:{job.pk}:late")


def _night_jobs(user):
    return TranslationJob.objects.filter(user=user, launch="night")


def _night(pref, now, report):
    from apps.notifications.services import notify

    from . import services

    user = pref.user
    window = current_window(pref, now)
    if window is None:
        if pref.night_window_open and pref.night_window_seen:
            _morning_report(pref, now)
            report["night_reports"] += 1
            pref.night_window_open = False
            pref.save(update_fields=["night_window_open"])
        return
    start, _end = window
    if pref.night_window_seen != start:
        on_time = now - start <= NIGHT_GRACE
        pref.night_window_seen, pref.night_window_open = start, on_time
        pref.save(update_fields=["night_window_seen", "night_window_open"])
        if not on_time:
            waiting = _night_jobs(user).filter(Q_waiting())
            ids = list(waiting.values_list("pk", flat=True))
            if ids:
                TranslationJob.objects.filter(pk__in=ids).update(status="late")
                report["late"].extend(ids)
                notify(user, "task_paused", "File de nuit non lancée : à confirmer",
                       body=(f"J-ed n'était pas en marche au début de la plage ({window_label(pref)}). "
                             f"{len(ids)} tâche(s) de nuit attendent votre confirmation : elles ne partent jamais "
                             "d'elles-mêmes après un démarrage en retard."),
                       link=reverse("translation:job_list"), severity="warning",
                       group_key=f"night:{user.pk}:{start:%Y%m%d}")
    if not pref.night_window_open:
        return
    active = list(_night_jobs(user).filter(status__in=ACTIVE))
    for job in active:
        if services.is_stale(job):  # worker arrêté pendant la nuit : la tâche reprend là où elle s'était arrêtée
            if _start(job, now):
                report["started"].append(job.pk)
            return
    if active:
        return
    waiting = sorted(_night_jobs(user).filter(Q_waiting()).select_related("project"),
                     # 2.0.0 (lot 4) : « résumer après l'ensemble » passe après toutes les traductions de la file
                     key=lambda j: (bool((j.options or {}).get("after_all")), j.queue_position or 0, j.created_at))
    for job in waiting:
        if _start(job, now):
            report["started"].append(job.pk)
            return


def Q_waiting():  # noqa: N802 — filtre réutilisé
    from django.db.models import Q

    return Q(status="scheduled") | Q(status="paused", pause_reason="night_end")


def _morning_report(pref, now):
    """Compte rendu du matin : ce qui a été traduit, ce qui reste, les erreurs et le coût estimé."""
    from apps.notifications.services import notify

    from .services import estimate

    jobs = list(_night_jobs(pref.user).filter(started_at__isnull=False, heartbeat_at__gte=pref.night_window_seen))
    if not jobs:
        return
    done = sum(j.done_items for j in jobs)
    failed = sum(j.failed_items for j in jobs)
    remaining = sum(j.items.filter(status="pending").count() for j in jobs)
    cost, currency = Decimal("0"), ""
    for j in jobs:
        c = estimate(j.engine, j.chars_sent, ai_provider=j.ai_provider, ai_model=j.ai_model)
        if c.get("amount") is not None:
            cost += Decimal(str(c["amount"]))
            currency = c.get("currency") or currency
    interrupted = sum(1 for j in jobs if j.status == "interrupted")
    body = f"{len(jobs)} tâche(s) : {done} élément(s) terminé(s), {remaining} restant(s), {failed} en échec"
    body += f" ; coût estimé {cost:.4f} {currency or 'USD'}." if cost else " ; aucun coût."
    if interrupted:
        body += f" {interrupted} tâche(s) interrompue(s) pendant la nuit (ordinateur en veille, Docker arrêté ?)."
    if remaining:
        body += " Le reste continue la nuit prochaine."
    notify(pref.user, "task_errors" if failed or interrupted else "task_done", "Compte rendu de la nuit",
           body=body[:1000], link=reverse("translation:job_list"), severity="warning" if failed or interrupted
           else "success", group_key=f"night-report:{pref.user_id}:{pref.night_window_seen:%Y%m%d}")


# --------------------------------------------------------------------------- pendant l'exécution


def pause_reason_before_chunk(job, chunk_chars, chunk_cost=None, now=None):
    """Raison de mettre la tâche en pause avant d'envoyer le paquet suivant, ou ('', '')."""
    if job.launch == "night":
        pref = TranslationPreference.objects.filter(user=job.user).first()
        if current_window(pref, now) is None:
            return "night_end", (f"Fin de la plage de nuit ({window_label(pref)}) : la tâche reprendra la nuit "
                                 "prochaine, sans rien renvoyer.")
    problem = cap_problem(job, chunk_chars, chunk_cost)
    if problem:
        return "cap", problem
    return "", ""


def cap_problem(job, chunk_chars, chunk_cost=None):
    """Plafonds mensuels vérifiés AU MOMENT DE CHAQUE ENVOI (2.0.0, lot 3)."""
    from .models import EngineSetting
    from .services import monthly_chars

    setting = EngineSetting.objects.filter(user=job.user, engine=job.engine).first()
    if setting and setting.monthly_char_cap is not None:
        used = monthly_chars(job.user, job.engine)
        if used + chunk_chars > setting.monthly_char_cap:
            return (f"Plafond mensuel de {setting.get_engine_display()} atteint : {used} caractères utilisés, "
                    f"{chunk_chars} pour le paquet suivant, plafond {setting.monthly_char_cap}. La tâche est en "
                    "pause ; aucun autre moteur n'est utilisé à sa place.")
    if job.engine == "ai":
        from apps.ai.preferences import active_profile
        from apps.ai.services import monthly_spend

        profile = active_profile(job.user)
        if profile.monthly_budget is not None:
            spent = monthly_spend(job.user)
            planned = Decimal(str(chunk_cost or 0))
            if spent + planned > profile.monthly_budget:
                return (f"Plafond mensuel IA atteint : {spent:.4f} USD consommés, {planned:.4f} USD pour le paquet "
                        f"suivant, plafond {profile.monthly_budget} USD. La tâche est en pause.")
    return ""


# --------------------------------------------------------------------------- actions de l'utilisateur


def pause(job, user):
    if job.user_id != user.pk or job.status not in ("confirmed", "running", "scheduled"):
        raise QueueError("Cette tâche ne peut pas être mise en pause.")
    job.status, job.pause_reason = "paused", "user"
    job.save(update_fields=["status", "pause_reason"])


def back_to_night(job, user):
    """Remettre une tâche (en pause, en retard, interrompue) dans la file de nuit."""
    if job.user_id != user.pk or job.status not in ("paused", "late", "interrupted", "scheduled"):
        raise QueueError("Cette tâche ne peut pas être remise dans la file de nuit.")
    pref = TranslationPreference.objects.filter(user=user).first()
    if not has_night_window(pref):
        raise QueueError("Choisissez d'abord la plage de la file de nuit (Traduction → Moteurs).")
    if job.launch != "night":
        job.queue_position = _next_position(user)
    job.launch, job.status, job.pause_reason = "night", "scheduled", ""
    job.save(update_fields=["launch", "status", "pause_reason", "queue_position"])


def reschedule(job, user, when, now=None):
    now = now or timezone.now()
    if job.user_id != user.pk or job.status not in ("scheduled", "late", "paused"):
        raise QueueError("Cette tâche ne peut pas être reprogrammée.")
    if when is None or when <= now:
        raise QueueError("Choisissez une date et une heure à venir.")
    job.launch, job.status, job.scheduled_for, job.pause_reason = "scheduled", "scheduled", when, ""
    job.save(update_fields=["launch", "status", "scheduled_for", "pause_reason"])


def move(job, user, direction):
    """Monter ou descendre une tâche de nuit pas encore commencée (ou en pause) dans la file."""
    if job.user_id != user.pk or job.launch != "night" or job.status not in ("scheduled", "paused", "late"):
        raise QueueError("Seule une tâche de la file de nuit en attente peut changer de place.")
    queue = list(_night_jobs(user).filter(status__in=("scheduled", "paused", "late"))
                 .order_by("queue_position", "created_at"))
    for position, item in enumerate(queue, start=1):  # numérotation compacte
        item.queue_position = position
    index = next(i for i, item in enumerate(queue) if item.pk == job.pk)
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(queue):
        queue[index].queue_position, queue[other].queue_position = queue[other].queue_position, queue[index].queue_position
    for item in queue:
        TranslationJob.objects.filter(pk=item.pk).update(queue_position=item.queue_position)


def _running(user):
    limit = timezone.now() - timedelta(minutes=settings.TRANSLATION_STALE_MINUTES)
    from django.db.models import Q

    return (TranslationJob.objects.filter(user=user).exclude(kind="package")
            .filter(Q(status="running", heartbeat_at__gte=limit) | Q(status="confirmed", confirmed_at__gte=limit)))


def running_count(user):
    """Tâches en cours de l'utilisateur, hors tâches sans signe d'activité (indicateur de la barre de menu)."""
    return _running(user).count()


def running_label(user):
    """Texte de l'indicateur : « 1 traduction en cours », « 1 résumé en cours », « 2 traductions et 1 résumé en cours »
    (2.0.0, lot 4 : un résumé n'est pas une traduction). Vide s'il n'y a rien en cours."""
    kinds = list(_running(user).values_list("kind", flat=True))
    summaries = kinds.count("summary")
    translations = len(kinds) - summaries
    parts = []
    if translations:
        parts.append(f"{translations} traduction{'s' if translations > 1 else ''}")
    if summaries:
        parts.append(f"{summaries} résumé{'s' if summaries > 1 else ''}")
    return f"{' et '.join(parts)} en cours" if parts else ""
