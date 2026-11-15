"""Tâches de traduction : confirmation, suivi (HTMX), annulation, reprise, relance des échecs, deuxième moteur."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.permissions import admin_required, researcher_required
from apps.core.redirects import safe_next

from .. import queue as Q
from .. import services
from ..models import TranslationJob


def _own_job(request, pk):
    # Une tâche n'est visible que par son auteur (elle peut citer un projet confidentiel).
    # Les installations de paquets Argos ont leur propre page (Traduction → Moteurs locaux).
    return get_object_or_404(TranslationJob.objects.select_related("project").exclude(kind="package"), pk=pk,
                             user=request.user)


def _parse_when(value):
    """Champ « date et heure » du navigateur (AAAA-MM-JJTHH:MM, heure locale) → date avec fuseau, ou None."""
    from datetime import datetime

    from django.utils import timezone

    try:
        return timezone.make_aware(datetime.fromisoformat((value or "").strip()), timezone.get_current_timezone())
    except ValueError:
        return None


@researcher_required
def job_list(request):
    """2.0.0 (lot 3) : page « Tâches » — en cours, file d'attente (ordre modifiable), à décider, terminées.

    L'administrateur peut voir les tâches de tous les comptes, sans le titre d'un projet confidentiel d'autrui.
    """
    from ..queue import has_night_window, next_window_start, window_label

    show_all = request.user.is_admin_role and request.GET.get("tous") == "1"
    base = TranslationJob.objects.exclude(kind="package").select_related("project", "user")
    if not show_all:
        base = base.filter(user=request.user)

    def rows(qs):
        out = []
        for job in qs:
            hidden = job.user_id != request.user.pk and job.project_id and job.project.confidential
            out.append({"job": job, "stale": services.is_stale(job), "engine": services.engine_label(job),
                        "label": "Projet confidentiel" if hidden else job.scope_label,
                        "mine": job.user_id == request.user.pk})
        return out

    pref = services.ensure_preference(request.user)
    return render(request, "translation/job_list.html", {
        "running": rows(base.filter(status__in=("confirmed", "running")).order_by("confirmed_at")),
        "night": rows(base.filter(launch="night", status__in=("scheduled",)).order_by("user", "queue_position",
                                                                                         "created_at")),
        "scheduled": rows(base.filter(launch="scheduled", status="scheduled").order_by("scheduled_for")),
        "waiting": rows(base.filter(status__in=("paused", "late", "interrupted", "blocked", "draft"))
                        .order_by("-created_at")[:100]),
        "finished": rows(base.filter(status__in=("done", "failed", "cancelled")).order_by("-created_at")[:100]),
        "show_all": show_all, "night_window": window_label(pref) if has_night_window(pref) else "",
        "next_night": next_window_start(pref),
    })


@researcher_required
def job_detail(request, pk):
    job = _own_job(request, pk)
    items = job.items.select_related("segment", "record", "version", "editorial").order_by("position")[:500]
    from ..queue import has_night_window, next_window_start, window_label

    pref = services.ensure_preference(request.user)
    context = {"job": job, "items": items, "stale": services.is_stale(job), "engine_label": services.engine_label(job),
               "polling": job.status in ("confirmed", "running") and not services.is_stale(job),
               "night_window": window_label(pref) if has_night_window(pref) else "",
               "next_night": next_window_start(pref), "report": services.job_report(job)}
    if job.status == "draft":
        context["summary"] = services.summary(job)
        asked = request.GET.get("lancement", "")
        context["default_launch"] = {"nuit": "night", "programme": "scheduled"}.get(asked) or (
            "now" if job.launch == "now" else "immediate")
    if job.kind == "records" and request.user.is_admin_role:
        from apps.catalog.models import EditorialContent
        from apps.catalog.services import plan_bulk_validation

        editorials = EditorialContent.objects.filter(translation_job_items__job=job, kind="translation",
                                                     status="proposed").select_related("record").distinct()
        context["bulk"], context["bulk_skipped"] = plan_bulk_validation(list(editorials))
    if request.headers.get("HX-Request"):
        return render(request, "translation/_job_status.html", context)
    return render(request, "translation/job_detail.html", context)


@researcher_required
@require_POST
def job_action(request, pk):
    job = _own_job(request, pk)
    action = request.POST.get("action", "")
    try:
        if action == "confirm":
            launch = request.POST.get("launch", "immediate")
            if launch not in ("immediate", "now", "scheduled", "night"):
                launch = "immediate"
            services.confirm(job, request.user, second_confirmation=bool(request.POST.get("second_confirmation")),
                             terms_acknowledged=bool(request.POST.get("terms_acknowledged")), launch=launch,
                             scheduled_for=_parse_when(request.POST.get("scheduled_for")))
            log_action(request, "translation.job_confirmed", job,
                       f"{services.engine_label(job)} : {job.chars_estimated} caractère(s) prévus ({job.get_launch_display()})")
            messages.success(request, {
                "scheduled": "Traduction programmée : elle partira à l'heure prévue si J-ed est en marche.",
                "night": "Traduction ajoutée à la file de nuit : elle partira pendant la plage choisie.",
            }.get(launch, "Traduction lancée."))
        elif action == "pause":
            Q.pause(job, request.user)
            messages.info(request, "Pause demandée : la tâche s'arrête après le paquet en cours ; rien n'est renvoyé "
                                   "à la reprise.")
        elif action == "night":
            Q.back_to_night(job, request.user)
            messages.success(request, "Tâche remise dans la file de nuit.")
        elif action == "reschedule":
            Q.reschedule(job, request.user, _parse_when(request.POST.get("scheduled_for")))
            messages.success(request, "Tâche reprogrammée.")
        elif action in ("up", "down"):
            Q.move(job, request.user, action)
            return redirect(safe_next(request, reverse("translation:job_list")))
        elif action == "cancel":
            services.cancel(job, request.user)
            messages.info(request, "Tâche annulée." + (" Rien n'a été envoyé." if not job.chars_sent else ""))
        elif action == "resume":
            services.resume(job, request.user)
            messages.success(request, "Reprise lancée : seuls les éléments non traduits seront envoyés.")
        elif action == "retry":
            services.retry_failed(job, request.user)
            messages.success(request, "Relance des éléments en échec.")
        elif action == "second":
            new = services.propose_second_engine(job, request.user)
            messages.info(request, "Nouvelle tâche préparée avec le deuxième moteur : vérifiez-la, puis confirmez.")
            return redirect("translation:job_detail", pk=new.pk)
    except (services.TranslationUnavailable, Q.QueueError) as exc:
        messages.error(request, str(exc))
    return redirect("translation:job_detail", pk=job.pk)


@admin_required
@require_POST
def job_validate_all(request, pk):
    """2.0.0 : valider et adopter en une fois les traductions de notices produites par une tâche."""
    from apps.catalog.models import EditorialContent
    from apps.catalog.services import bulk_validation_message, validate_translations

    job = _own_job(request, pk)
    editorials = EditorialContent.objects.filter(translation_job_items__job=job, kind="translation",
                                                 status="proposed").select_related("record").distinct()
    chosen, skipped = validate_translations(list(editorials), request.user)
    for ed in chosen:
        log_action(request, "editorial.validate", ed, f"Traduction validée et adoptée (tâche n° {job.pk})")
    (messages.success if chosen else messages.info)(request, bulk_validation_message(chosen, skipped))
    return redirect("translation:job_detail", pk=job.pk)


@researcher_required
def job_mini(request, pk):
    """2.0.0 (lot 3) : état d'une tâche « maintenant » sur la fiche (actualisé tant qu'elle tourne)."""
    job = _own_job(request, pk)
    return render(request, "translation/_job_mini.html", {"job": job, "stale": services.is_stale(job)})
