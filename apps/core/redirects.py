"""Redirections sûres : seules les adresses internes à l'application sont suivies (audit, correction 5)."""
from django.utils.http import url_has_allowed_host_and_scheme


def safe_url(request, candidate, default="/"):
    """Renvoie `candidate` s'il désigne une page de l'application, sinon `default`."""
    if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()},
                                                     require_https=request.is_secure()):
        return candidate
    return default


def safe_next(request, default="/"):
    return safe_url(request, request.POST.get("next") or request.GET.get("next"), default)
