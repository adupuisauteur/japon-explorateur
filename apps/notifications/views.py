"""Pages des notifications (2.0.0, lot 5) : fenêtres, historique, préférences, essai."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import services
from .models import ADMIN_ONLY, CONFIGURABLE, EVENT_TYPES, INCIDENT_THRESHOLDS, Notification


def _internal(url, request):
    return bool(url) and url.startswith("/") and url_has_allowed_host_and_scheme(url, {request.get_host()})


@login_required
def notification_list(request):
    if request.method == "POST" and request.POST.get("action") == "all_read":
        n = services.mark_read(request.user)
        messages.success(request, f"{n} notification(s) marquée(s) comme lue(s).")
        return redirect("notifications:list")
    qs = Notification.objects.filter(recipient=request.user)
    state, kind = request.GET.get("etat", ""), request.GET.get("type", "")
    if state == "non-lues":
        qs = qs.filter(read_at__isnull=True)
    elif state == "lues":
        qs = qs.filter(read_at__isnull=False)
    if kind in dict(EVENT_TYPES):
        qs = qs.filter(event_type=kind)
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    types = [t for t in EVENT_TYPES if t[0] not in ADMIN_ONLY or request.user.is_admin_role]
    return render(request, "notifications/list.html", {"page": page, "state": state, "kind": kind, "types": types,
                                                       "unread": services.unread_count(request.user)})


@never_cache
@login_required
def popups(request):
    """Fenêtres en attente (appelé par HTMX à chaque page puis périodiquement) et compteur à jour."""
    return render(request, "notifications/_popups.html", {"popups": services.take_popups(request.user),
                                                           "unread": services.unread_count(request.user)})


@login_required
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    services.mark_read(request.user, [notification.pk])
    if request.headers.get("HX-Request"):
        return render(request, "notifications/_counter.html", {"unread": services.unread_count(request.user),
                                                               "oob": True})
    target = request.POST.get("next", "")
    return redirect(target if _internal(target, request) else "notifications:list")


@login_required
def open_notification(request, pk):
    """Ouvre le lien d'une notification et la marque comme lue."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    services.mark_read(request.user, [notification.pk])
    return redirect(notification.link if _internal(notification.link, request) else "notifications:list")


@login_required
def preferences(request):
    user = request.user
    configurable = [t for t in EVENT_TYPES if t[0] in CONFIGURABLE and (t[0] not in ADMIN_ONLY or user.is_admin_role)]
    if request.method == "POST":
        services.save_preferences(user, set(request.POST.getlist("types")), request.POST.get("incident_threshold"))
        messages.success(request, "Préférences de notification enregistrées.")
        return redirect("notifications:preferences")
    rows = [{"code": code, "label": label, "enabled": services.preference(user, code).enabled}
            for code, label in configurable]
    return render(request, "notifications/preferences.html", {
        "rows": rows, "thresholds": INCIDENT_THRESHOLDS,
        "threshold": services.preference(user, "incident").min_severity if user.is_admin_role else ""})


@login_required
@require_POST
def send_test(request):
    kind = "incident" if request.POST.get("kind") == "incident" and request.user.is_admin_role else "task"
    services.test(request.user, kind=kind)
    messages.info(request, "Notification d'essai envoyée : la fenêtre s'affiche dans quelques secondes, en bas à "
                           "droite, et le compteur du menu à votre nom augmente.")
    return redirect("notifications:preferences")
