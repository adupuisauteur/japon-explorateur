"""
Contrôle des adresses personnalisées de fournisseurs d'IA (audit, point 3).

Objectif : empêcher qu'une adresse saisie dans l'application serve à interroger le
réseau interne du serveur (SSRF) ou des services de métadonnées cloud.
Règles :
  - seuls les administrateurs peuvent définir une adresse personnalisée (vues) ;
  - HTTPS obligatoire, sans identifiants dans l'URL ;
  - toutes les adresses IP résolues doivent être publiques ;
  - exception explicite : les adresses listées dans AI_ALLOWED_LOCAL_URLS (ex. un
    modèle local Ollama), saisies par l'exploitant dans .env, jamais depuis l'interface.
"""
import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings


class UnsafeProviderURL(ValueError):
    pass


def _normalize(url):
    return (url or "").strip().rstrip("/")


def allowed_local_urls():
    return {_normalize(u) for u in getattr(settings, "AI_ALLOWED_LOCAL_URLS", []) if u}


def _is_public(ip):
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
                or addr.is_multicast or addr.is_unspecified)


def check_provider_url(url, *, resolve=True):
    """Lève UnsafeProviderURL si l'adresse n'est pas acceptable ; renvoie l'adresse normalisée."""
    url = _normalize(url)
    if not url:
        raise UnsafeProviderURL("Adresse vide.")
    if url in allowed_local_urls():
        return url
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise UnsafeProviderURL("Seules les adresses HTTPS sont acceptées (sauf modèle local autorisé par "
                                "l'exploitant dans AI_ALLOWED_LOCAL_URLS).")
    if parts.username or parts.password:
        raise UnsafeProviderURL("L'adresse ne doit pas contenir d'identifiants.")
    host = parts.hostname
    if not host:
        raise UnsafeProviderURL("Nom d'hôte manquant.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        ips = [str(literal)]
    elif resolve:
        try:
            ips = sorted({info[4][0] for info in socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)})
        except socket.gaierror:
            raise UnsafeProviderURL("Nom d'hôte introuvable.") from None
    else:
        ips = []
    for ip in ips:
        if not _is_public(ip):
            raise UnsafeProviderURL("Adresse interne, privée ou réservée refusée.")
    return url
