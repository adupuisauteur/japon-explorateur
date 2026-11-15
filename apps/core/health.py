"""État de l'installation (2.0.0, lot 0) : contrôles lus par la page « État », la commande
`manage.py etat_installation` et le script `mettre-a-jour.ps1`.

Chaque contrôle renvoie un `Check` (niveau ok / attention / erreur / inconnu, résumé, détails). Aucun
contrôle n'appelle Internet ; aucun texte de l'utilisateur, aucune clé ni aucun nom de compte n'est lu ou
affiché. Le diagnostic copiable reprend ces contrôles, avec les chemins personnels masqués.
"""
import os
import platform
import re
import shutil
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import django
from django.conf import settings
from django.db import connection
from django.utils import timezone

OK, WARNING, ERROR, UNKNOWN = "ok", "warning", "error", "unknown"
LEVEL_LABELS = {OK: "Correct", WARNING: "À surveiller", ERROR: "Problème", UNKNOWN: "Non vérifiable"}
LEVEL_RANK = {OK: 0, UNKNOWN: 1, WARNING: 2, ERROR: 3}
#: espace disque libre en dessous duquel une alerte est affichée
DISK_WARNING_BYTES = 5 * 1024 ** 3


@dataclass
class Check:
    key: str
    label: str
    level: str
    summary: str
    details: list = field(default_factory=list)

    @property
    def level_label(self):
        return LEVEL_LABELS[self.level]


def _fmt_bytes(n):
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unit == "To":
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _ago(dt):
    if dt is None:
        return "jamais"
    delta = timezone.now() - dt
    if delta < timedelta(minutes=1):
        return "à l'instant"
    if delta < timedelta(hours=1):
        return f"il y a {int(delta.total_seconds() // 60)} min"
    if delta < timedelta(days=2):
        return f"il y a {int(delta.total_seconds() // 3600)} h"
    return f"il y a {delta.days} jours"


# --------------------------------------------------------------------------- contrôles


def check_version():
    return Check("version", "Version", OK, f"J-ed {settings.APP_VERSION}", [
        f"Schéma des données exportées : {settings.DATA_SCHEMA_VERSION}",
        f"Python {platform.python_version()} · Django {django.get_version()}",
    ])


def check_database():
    from django.db.migrations.executor import MigrationExecutor

    try:
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute("SHOW server_version")
                version = f"PostgreSQL {cursor.fetchone()[0]}"
            else:
                version = connection.vendor
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception as exc:  # noqa: BLE001 — affiché tel quel
        return Check("base", "Base de données et migrations", ERROR,
                     f"Base injoignable ({exc.__class__.__name__} : {exc})")
    applied = len(executor.loader.applied_migrations)
    if pending:
        names = ", ".join(f"{m.app_label}.{m.name}" for m, _ in pending[:5])
        return Check("base", "Base de données et migrations", ERROR,
                     f"{len(pending)} migration(s) non appliquée(s) : {names}",
                     [version, "Redémarrez le service web : il applique les migrations au démarrage."])
    level = OK if connection.vendor == "postgresql" else WARNING
    details = [version, f"{applied} migration(s) appliquée(s), aucune en attente"]
    if level == WARNING:
        details.append("SQLite : réservé aux essais rapides hors Docker.")
    return Check("base", "Base de données et migrations", level, "À jour", details)


def check_broker():
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return Check("redis", "Redis (file des tâches)", WARNING, "Non utilisé : tâches exécutées immédiatement",
                     ["Mode sans Redis (essai hors Docker) : les tâches longues bloquent la page qui les lance."])
    try:
        import redis

        client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        info = client.info("server")
    except Exception as exc:  # noqa: BLE001
        return Check("redis", "Redis (file des tâches)", ERROR, f"Injoignable ({exc.__class__.__name__} : {exc})",
                     ["Sans Redis, aucune tâche de fond ne part (traductions, synchronisations, exports)."])
    return Check("redis", "Redis (file des tâches)", OK, "Répond", [f"Redis {info.get('redis_version', '?')}"])


def check_workers():
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return Check("workers", "Workers (tâches de fond)", WARNING, "Non utilisés (mode sans Redis)")
    try:
        from config.celery import app

        replies = app.control.ping(timeout=1.5) or []
    except Exception as exc:  # noqa: BLE001
        return Check("workers", "Workers (tâches de fond)", ERROR,
                     f"Interrogation impossible ({exc.__class__.__name__} : {exc})")
    if not replies:
        return Check("workers", "Workers (tâches de fond)", ERROR, "Aucun worker ne répond",
                     ["Les traductions, synchronisations, exports et sauvegardes planifiées ne partent pas.",
                      "Vérifiez le conteneur « worker » dans Docker Desktop."])
    names = sorted(name.split("@", 1)[0] for reply in replies for name in reply)
    return Check("workers", "Workers (tâches de fond)", OK, f"{len(replies)} worker(s) répond(ent)",
                 [", ".join(names)])


def check_scheduler():
    from .models import ServiceCheck

    beat = ServiceCheck.objects.filter(name="planificateur").first()
    limit = timedelta(minutes=settings.HEARTBEAT_STALE_MINUTES)
    if beat is None:
        return Check("planificateur", "Planificateur (Celery beat)", UNKNOWN, "Aucun signe de vie reçu pour l'instant",
                     ["Le premier signe de vie arrive dans les 5 minutes qui suivent le démarrage."])
    if timezone.now() - beat.checked_at > limit:
        return Check("planificateur", "Planificateur (Celery beat)", ERROR,
                     f"Dernier signe de vie {_ago(beat.checked_at)}",
                     ["Sauvegardes et synchronisations planifiées ne partent plus.",
                      "Vérifiez les conteneurs « beat » et « worker » dans Docker Desktop."])
    return Check("planificateur", "Planificateur (Celery beat)", OK, f"Signe de vie {_ago(beat.checked_at)}")


def check_argos():
    from apps.translation.argos_selftest import CHECK_NAME
    from apps.translation.engines.argos import ArgosEngine, _path

    from .models import AppSettings, ServiceCheck

    engine = ArgosEngine(None)
    details = []
    if AppSettings.get().argos_demo_mode:
        details.append("Mode démonstration ACTIVÉ : sans le service, les traductions Argos sont simulées.")
    selftest = ServiceCheck.objects.filter(name=CHECK_NAME).first()
    if selftest:
        details.append(f"Traduction d'essai ({_ago(selftest.checked_at)}) : {selftest.message}")
    if not engine.service_url:
        return Check("argos", "Argos (traduction hors ligne)", WARNING, "Service non configuré", details)
    try:
        health = engine.health() or {}
    except Exception as exc:  # noqa: BLE001
        return Check("argos", "Argos (traduction hors ligne)", WARNING,
                     f"Service injoignable ({str(exc).rstrip('.')})",
                     details + ["Le service démarre avec J-ed si la ligne COMPOSE_PROFILES=argos figure dans .env "
                                "(laissée vide, elle le désactive volontairement)."])
    packages = health.get("packages") or []
    listed = ", ".join(f"{p.get('from')}→{p.get('to')} {p.get('version', '?')}"
                       + ("" if p.get("sbd_ready", True) else " (modèle de découpage manquant)") for p in packages)
    details.insert(0, f"Argos {health.get('argos_version', '?')} ; paquets : {listed or 'aucun'}")
    if health.get("busy"):
        details.append("Installation de paquet en cours.")
    from apps.translation.argos_packages import memory_warning

    if memory_warning(health):
        details.append(memory_warning(health))
    if _path("ja", "fr", packages) is None:
        return Check("argos", "Argos (traduction hors ligne)", WARNING,
                     "En service, mais la traduction japonais → français n'est pas installée", details
                     + ["Bouton « Installer la traduction japonais → français » : Traduction → Moteurs locaux."])
    if selftest and not selftest.ok:
        return Check("argos", "Argos (traduction hors ligne)", ERROR, "Traduction d'essai en échec", details)
    return Check("argos", "Argos (traduction hors ligne)", OK if selftest else UNKNOWN,
                 "Prêt" if selftest else "En service ; traduction d'essai non encore faite", details)


def check_backups():
    from apps.backups.models import BackupJob

    from .models import AppSettings

    app_settings = AppSettings.get()
    last = BackupJob.objects.filter(status="done").order_by("-created_at").first()
    last_failure = BackupJob.objects.filter(status="failed").order_by("-created_at").first()
    details = []
    if settings.BACKUP_EXTERNAL_HOST_DIR:
        details.append(f"Copie dans le dossier de l'ordinateur : {settings.BACKUP_EXTERNAL_HOST_DIR}")
    elif settings.BACKUP_EXTERNAL_DIR:
        details.append("Copie externe dans un volume Docker (ajoutez DOSSIER_SAUVEGARDES dans .env pour la voir "
                       "dans Windows).")
    else:
        details.append("Aucune copie externe configurée.")
    details.append("Sauvegarde automatique quotidienne : " + ("activée" if app_settings.backup_enabled else "DÉSACTIVÉE"))
    if last is None:
        return Check("sauvegardes", "Sauvegardes", WARNING, "Aucune sauvegarde réussie pour l'instant", details)
    details.insert(0, f"Dernière réussie : {timezone.localtime(last.created_at):%d/%m/%Y %H:%M} "
                      f"({_fmt_bytes(last.size)}{', vérifiée' if last.verified_at else ''})")
    if last_failure and last_failure.created_at > last.created_at:
        details.append(f"Échec plus récent : {last_failure.message[:200]}")
    age = timezone.now() - last.created_at
    if age > timedelta(days=7):
        return Check("sauvegardes", "Sauvegardes", ERROR, f"Dernière sauvegarde réussie {_ago(last.created_at)}",
                     details)
    if age > timedelta(hours=36) or (last_failure and last_failure.created_at > last.created_at) \
            or (settings.BACKUP_EXTERNAL_DIR and not last.external_copy):
        if settings.BACKUP_EXTERNAL_DIR and not last.external_copy:
            details.append("La dernière sauvegarde n'a pas été copiée dans le dossier externe.")
        return Check("sauvegardes", "Sauvegardes", WARNING, f"Dernière sauvegarde réussie {_ago(last.created_at)}",
                     details)
    return Check("sauvegardes", "Sauvegardes", OK, f"Dernière sauvegarde réussie {_ago(last.created_at)}", details)


def check_keys():
    """Clés des services en ligne : nombre de clés par fournisseur et résultat du dernier test (sans nom de compte)."""
    from collections import Counter

    from apps.ai.models import AIProviderCredential
    from apps.translation.models import EngineSetting

    rows = Counter()
    for provider, status in AIProviderCredential.objects.exclude(encrypted_key="").values_list("provider", "status"):
        rows[(f"IA {provider}", status)] += 1
    for engine, status in EngineSetting.objects.exclude(encrypted_key="").values_list("engine", "status"):
        rows[(engine, status)] += 1
    if not rows:
        return Check("cles", "Clés des services en ligne", OK, "Aucune clé enregistrée",
                     ["Les moteurs en ligne restent « testés en simulation ; test réel à confirmer »."])
    labels = {"ok": "test réussi", "error": "dernier test en échec", "untested": "jamais testée", "revoked": "effacée"}
    details = [f"{name} : {n} clé(s), {labels.get(status, status)}" for (name, status), n in sorted(rows.items())]
    errors = sum(n for (_name, status), n in rows.items() if status == "error")
    untested = sum(n for (_name, status), n in rows.items() if status == "untested")
    if errors:
        return Check("cles", "Clés des services en ligne", WARNING, f"{errors} clé(s) dont le dernier test a échoué",
                     details)
    if untested:
        return Check("cles", "Clés des services en ligne", WARNING, f"{untested} clé(s) jamais testée(s)", details)
    return Check("cles", "Clés des services en ligne", OK, "Toutes les clés ont été testées avec succès", details)


def _disk_line(label, path):
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return None, f"{label} : illisible ({exc.__class__.__name__})"
    return usage, f"{label} : {_fmt_bytes(usage.free)} libres sur {_fmt_bytes(usage.total)}"


def check_disk():
    level, details = OK, []
    seen = set()
    for label, path in (("Données", settings.DATA_DIR), ("Sauvegardes", settings.BACKUP_DIR),
                        ("Copie externe", settings.BACKUP_EXTERNAL_DIR)):
        if not path or not Path(path).exists():
            continue
        usage, line = _disk_line(label, path)
        if usage is not None:
            ident = (usage.total, usage.free // (1024 ** 2))
            if ident in seen:
                continue
            seen.add(ident)
            if usage.free < DISK_WARNING_BYTES or usage.free < usage.total * 0.05:
                level = WARNING
        else:
            level = WARNING
        details.append(line)
    summary = "Espace suffisant" if level == OK else "Espace disque faible ou illisible"
    return Check("disque", "Espace disque", level, summary, details)


def _cgroup_memory_limit():
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            raw = Path(path).read_text().strip()
        except OSError:
            continue
        if raw.isdigit() and int(raw) < 1 << 60:
            return int(raw)
    return None


def machine_resources():
    """Mémoire et cœurs accordés par Docker à ce conteneur (2.0.0 ; les profils viennent au lot 3)."""
    total = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) * 1024
                break
    except OSError:
        pass
    limit = _cgroup_memory_limit()
    memory = min(x for x in (total, limit) if x) if (total or limit) else None
    try:
        cpus = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cpus = os.cpu_count()
    return {"memory_bytes": memory, "cpus": cpus}


def check_resources():
    res = machine_resources()
    memory = _fmt_bytes(res["memory_bytes"]) if res["memory_bytes"] else "inconnue"
    details = [f"Mémoire vue par l'application : {memory}", f"Cœurs du processeur : {res['cpus'] or 'inconnu'}",
               "Sous Windows, Docker ne voit par défaut que la moitié de la mémoire de l'ordinateur (WSL 2)."]
    level = OK
    if res["memory_bytes"] and res["memory_bytes"] < 4 * 1024 ** 3:
        level = WARNING
        details.append("Moins de 4 Go : Argos et les longues traductions risquent de manquer de mémoire.")
    return Check("ressources", "Ressources accordées par Docker", level, f"{memory}, {res['cpus'] or '?'} cœur(s)",
                 details)


CHECKS = (check_version, check_database, check_broker, check_workers, check_scheduler, check_argos, check_backups,
          check_keys, check_disk, check_resources)
#: libellés affichés si un contrôle échoue lui-même (exception)
CHECK_LABELS = {
    "check_version": "Version", "check_database": "Base de données et migrations",
    "check_broker": "Redis (file des tâches)", "check_workers": "Workers (tâches de fond)",
    "check_scheduler": "Planificateur (Celery beat)", "check_argos": "Argos (traduction hors ligne)",
    "check_backups": "Sauvegardes", "check_keys": "Clés des services en ligne", "check_disk": "Espace disque",
    "check_resources": "Ressources accordées par Docker",
}


def collect():
    results = []
    for func in CHECKS:
        try:
            results.append(func())
        except Exception as exc:  # noqa: BLE001 — un contrôle défaillant est affiché, il n'arrête pas la page
            message = " ".join(str(exc).split())[:300]
            results.append(Check(func.__name__.removeprefix("check_"), CHECK_LABELS.get(func.__name__, func.__name__),
                                 ERROR, f"Contrôle impossible ({exc.__class__.__name__} : {message})"))
    return results


def overall(results):
    return max((r.level for r in results), key=LEVEL_RANK.get, default=UNKNOWN)


# --------------------------------------------------------------------------- diagnostic copiable

_PERSONAL_PATTERNS = [
    (re.compile(r"(?i)([a-z]:\\users\\)[^\\\s]+"), r"\1…"),  # C:\Users\<nom>
    (re.compile(r"(/home/|/Users/)[^/\s]+"), r"\1…"),
]


def mask_personal(text):
    for pattern, repl in _PERSONAL_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def diagnostic_text(results=None):
    results = results if results is not None else collect()
    lines = [f"Diagnostic J-ed {settings.APP_VERSION} — {timezone.localtime():%d/%m/%Y %H:%M}",
             f"État général : {LEVEL_LABELS[overall(results)]}", ""]
    for r in results:
        lines.append(f"[{r.level_label}] {r.label} : {r.summary}")
        lines.extend(f"    {d}" for d in r.details)
    lines += ["", "Ce texte ne contient ni clé, ni nom de compte, ni texte de recherche ou de traduction."]
    return mask_personal("\n".join(lines))
