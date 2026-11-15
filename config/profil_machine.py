"""
Profils de machine (2.0.0, lot 3 ; décisions D7 et D8). Sans dépendance à Django : lu aussi par la
configuration du serveur web (config/gunicorn.conf.py).

Le profil est calculé AU DÉMARRAGE des conteneurs, d'après la mémoire et les cœurs que Docker accorde ;
l'application ne peut pas redémarrer ses propres conteneurs. Il peut être imposé par JED_PROFIL dans .env
(econome, normal ou puissant), suivi de « docker compose up -d ».
"""
import os
from pathlib import Path

PROFILES = {
    # web : processus du serveur web ; courts : travaux courts en parallèle (exports, synchronisations…) ;
    # argos_jour / argos_nuit : segments par paquet envoyé à Argos (petits le jour pour qu'une demande
    # « maintenant » attende peu, plus grands la nuit).
    "econome": {"label": "Économe", "web": 2, "courts": 1, "argos_jour": 10, "argos_nuit": 25},
    "normal": {"label": "Normal", "web": 3, "courts": 2, "argos_jour": 10, "argos_nuit": 50},
    "puissant": {"label": "Puissant", "web": 4, "courts": 3, "argos_jour": 20, "argos_nuit": 50},
}
GIB = 1024 ** 3


def cgroup_memory_limit(paths=("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes")):
    for path in paths:
        try:
            raw = Path(path).read_text().strip()
        except OSError:
            continue
        if raw.isdigit() and int(raw) < 1 << 60:
            return int(raw)
    return None


def resources(meminfo="/proc/meminfo"):
    """Mémoire (octets) et cœurs accordés par Docker à ce conteneur."""
    total = None
    try:
        for line in Path(meminfo).read_text().splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError):
        pass
    limit = cgroup_memory_limit()
    memory = min(x for x in (total, limit) if x) if (total or limit) else None
    try:
        cpus = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cpus = os.cpu_count()
    return {"memory_bytes": memory, "cpus": cpus}


def choose(memory_bytes, cpus):
    """(nom du profil, raison) d'après les ressources."""
    if not memory_bytes or not cpus:
        return "normal", "ressources non lisibles : profil normal par défaut"
    gb = memory_bytes / GIB
    seen = f"{gb:.1f} Go et {cpus} cœur(s) accordés par Docker"
    if gb < 6 or cpus < 4:
        return "econome", f"{seen} (moins de 6 Go ou de 4 cœurs)"
    if gb >= 12 and cpus >= 8:
        return "puissant", f"{seen} (au moins 12 Go et 8 cœurs)"
    return "normal", seen


def current(environ=None, res=None):
    """Profil retenu : JED_PROFIL s'il est valide, sinon calculé. Dictionnaire complet (valeurs comprises)."""
    environ = os.environ if environ is None else environ
    res = res or resources()
    forced = (environ.get("JED_PROFIL") or "").strip().lower().replace("é", "e")
    if forced in PROFILES:
        name, reason, imposed = forced, "imposé par la ligne JED_PROFIL du fichier .env", True
    else:
        name, reason = choose(res["memory_bytes"], res["cpus"])
        imposed = False
        if forced:
            reason += f" — valeur JED_PROFIL « {environ.get('JED_PROFIL')} » non reconnue, ignorée"
    return dict(PROFILES[name], name=name, reason=reason, imposed=imposed, **res)
