from django.conf import settings


def app_context(request):
    ctx = {"APP_VERSION": settings.APP_VERSION, "ai_ui_enabled": False}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.can_edit:  # module IA fermé au Lecteur
        from apps.ai.preferences import active_profile

        profile = active_profile(user)
        ctx["ai_profile"] = profile
        ctx["ai_ui_enabled"] = profile.mode != "disabled"
    return ctx
