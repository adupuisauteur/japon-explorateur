from django.conf import settings


def app_context(request):
    ctx = {"APP_VERSION": settings.APP_VERSION, "APP_NAME": settings.APP_NAME, "ai_ui_enabled": False}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_admin_role:
        from apps.incidents.models import Incident

        # Nombre d'incidents « Nouveau » de gravité Erreur ou Critique (entrée « Dysfonctionnements » du menu à
        # son nom et pied de page ; administrateur seulement). Depuis le lot 5, le bouton du menu porte le
        # compteur des notifications non lues.
        ctx["incidents_new_count"] = Incident.objects.filter(status="nouveau",
                                                             severity__in=("error", "critical")).count()
    if user is not None and user.is_authenticated:
        from apps.notifications.services import unread_count

        ctx["notifications_unread"] = unread_count(user)  # 2.0.0 (lot 5) : compteur du menu à son nom
    if user is not None and user.is_authenticated and user.can_edit:  # module IA fermé au Lecteur
        from apps.ai.preferences import active_profile

        profile = active_profile(user)
        ctx["ai_profile"] = profile
        ctx["ai_ui_enabled"] = profile.mode != "disabled"
    return ctx
