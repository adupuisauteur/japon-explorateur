from django.shortcuts import redirect
from django.urls import reverse

_EXEMPT_PREFIXES = ("/static/", "/comptes/premier-demarrage", "/sw.js", "/manifest.webmanifest", "/hors-ligne")


class FirstRunMiddleware:
    """Redirige vers l'assistant de première configuration tant qu'aucun compte n'existe."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._has_users = False

    def __call__(self, request):
        if not self._has_users and not request.path.startswith(_EXEMPT_PREFIXES):
            from django.contrib.auth import get_user_model

            if get_user_model().objects.exists():
                self._has_users = True
            else:
                return redirect(reverse("accounts:first_run"))
        return self.get_response(request)


CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",  # attributs style= et styles injectés par HTMX (pas de script)
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])


class ContentSecurityPolicyMiddleware:
    """En-tête Content-Security-Policy : aucun script en ligne ni ressource externe ne peut s'exécuter."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
