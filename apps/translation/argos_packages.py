"""
Gestion des paquets de langues Argos Translate (plan 1.3.0, lot 9 ; décisions A1, E6 et F).

Décision F (14 novembre 2026) : c'est l'utilisateur qui choisit de télécharger ou non les paquets. Rien
n'est téléchargé sans son action explicite et confirmée dans Traduction → Moteurs locaux ; il peut aussi
installer un fichier .argosmodel obtenu par ailleurs (installation sans Internet).

Une installation est une opération longue (plusieurs centaines de Mo) : elle est suivie en base comme
une tâche (TranslationJob de nature « package », un élément par paquet), exécutée par le worker dans la
file « traduction », et peut être relancée après une interruption ; un paquet déjà installé n'est pas
téléchargé à nouveau. Les paquets sont communs à toute l'installation : leur gestion est réservée à
l'administrateur.
"""
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .engines.argos import NEEDED, ArgosEngine, _path
from .engines.base import TranslationEngineError
from .journal import record_translation_error
from .models import TranslationJob, TranslationJobItem

INDEX_PREFIX = "index:"
FILE_PREFIX = "fichier:"
SBD_PREFIX = "decoupage:"
PAIR = re.compile(r"^(ja|en|fr)→(ja|en|fr)$")
#: 2.0.0 (lot 7) : paquets du bouton unique « Installer la traduction japonais → français »
JA_FR_CODES = ["ja→en", "en→fr"]
JA_FR_LABEL = "Installation de la traduction japonais → français"
#: taille annoncée avant confirmation (cahier des charges § 9 bis) ; la taille exacte dépend de l'index Argos
JA_FR_SIZE = "environ 200 Mo"
#: en dessous, la mémoire vue par le service est signalée comme insuffisante (8 Go conseillés sur l'ordinateur)
MEMORY_WARNING_MB = 4096


class PackageError(Exception):
    pass


def client(user=None):
    return ArgosEngine(user)


def service_state(user=None):
    """(health ou None, message d'erreur). Aucun appel à Internet : le service local seulement."""
    engine = client(user)
    if not engine.service_url:
        return None, "Service Argos non configuré (TRANSLATION_ARGOS_URL)."
    try:
        return engine.health(), ""
    except Exception as exc:  # noqa: BLE001 — affiché tel quel, jamais masqué
        return None, (f"Service Argos injoignable ({exc}). Il démarre avec J-ed si la ligne COMPOSE_PROFILES=argos "
                      "figure dans le fichier .env ; juste après le démarrage, il lui faut quelques secondes.")


def needed_status(health):
    """Pour chaque paire du module : paquets nécessaires, installés ou manquants."""
    installed = {(p.get("from"), p.get("to")): p for p in (health or {}).get("packages") or []}
    rows = []
    for (source, target), packages in NEEDED.items():
        rows.append({"pair": f"{source}→{target}", "packages": [
            {"code": f"{a}→{b}", "installed": installed.get((a, b))} for a, b in packages]})
    return rows


def running_job():
    """Installation de paquets en cours (hors installations interrompues), ou None."""
    for job in TranslationJob.objects.filter(kind="package", status__in=("confirmed", "running")).order_by("-created_at"):
        if not is_stale(job):
            return job
    return None


def ja_fr_ready(health):
    return _path("ja", "fr", (health or {}).get("packages") or []) is not None


def memory_warning(health):
    """Message si la mémoire vue par le service Argos paraît insuffisante, sinon ''."""
    memory = (health or {}).get("memory") or {}
    values = [v for v in (memory.get("total_mb"), memory.get("limit_mb")) if v]
    if not values or min(values) >= MEMORY_WARNING_MB:
        return ""
    return (f"Le service Argos ne dispose que de {min(values) / 1024:.1f} Go de mémoire : une traduction risque "
            "d'échouer faute de mémoire. 8 Go sont conseillés sur l'ordinateur ; augmentez la mémoire accordée à "
            "Docker, ou la limite ARGOS_MEMOIRE_MAX du fichier .env.")


def invite(user, health=None, problem=None):
    """Que proposer pour « Installer la traduction japonais → français » ? None si Argos est prêt.

    Aucun appel à Internet : seul le service local est interrogé (sauf si son état est fourni).
    """
    if health is None and problem is None:
        health, problem = service_state(user)
    if health is not None and ja_fr_ready(health):
        return None
    installed = {f"{p.get('from')}→{p.get('to')}" for p in (health or {}).get("packages") or []}
    running = running_job()
    return {"health": health, "problem": problem, "running": running, "size": JA_FR_SIZE,
            "missing": [c for c in JA_FR_CODES if c not in installed],
            "can_install": bool(user.is_admin_role and health is not None and running is None),
            "is_admin": user.is_admin_role}


def invite_for_choice(user, project=None):
    """Invitation si le moteur par défaut ou le deuxième moteur (du projet ou de l'utilisateur) est Argos."""
    from .services import resolve_choice

    codes = {getattr(resolve_choice(user, project=project, which=w), "code", "") for w in ("default", "second")}
    return invite(user) if "argos" in codes else None


def prepare_ja_fr(user):
    """Bouton unique (lot 7) : paquets ja→en et en→fr manquants, dans une seule tâche reprenable.

    Argos est aussi activé dans les moteurs de l'utilisateur qui a fait la demande (moteur local : rien ne quitte
    l'ordinateur). Retourne None si la traduction japonais → français est déjà installée.
    """
    if running_job() is not None:
        raise PackageError("Une installation est déjà en cours : suivez sa progression ci-dessous.")
    health, problem = service_state(user)
    if health is None:
        raise PackageError(problem)
    from .models import EngineSetting

    EngineSetting.objects.update_or_create(user=user, engine="argos", defaults={"enabled": True})
    installed = {f"{p.get('from')}→{p.get('to')}" for p in health.get("packages") or []}
    missing = [c for c in JA_FR_CODES if c not in installed]
    if not missing:
        return None
    return _new_job(user, f"{JA_FR_LABEL} : " + ", ".join(missing), [INDEX_PREFIX + c for c in missing])


def _pair(code):
    m = PAIR.match(code or "")
    if not m or m.group(1) == m.group(2):
        raise PackageError(f"Paquet non pris en charge : « {code} ».")
    return m.group(1), m.group(2)


def _new_job(user, label, fields):
    job = TranslationJob.objects.create(user=user, kind="package", engine="argos", scope_label=label[:300],
                                        status="confirmed", confirmed_at=timezone.now(), total_items=len(fields))
    for i, value in enumerate(fields):
        TranslationJobItem.objects.create(job=job, position=i, record_field=value)
    return job


def prepare_index_install(user, codes):
    """Prépare le téléchargement des paquets choisis (« ja→en »…). La confirmation a eu lieu dans le formulaire."""
    codes = list(dict.fromkeys(codes))
    if not codes:
        raise PackageError("Choisissez au moins un paquet.")
    for code in codes:
        _pair(code)
    return _new_job(user, "Téléchargement depuis l'index Argos : " + ", ".join(codes),
                    [INDEX_PREFIX + c for c in codes])


def prepare_sbd_install(user, code):
    """Modèle de découpage en phrases d'un paquet installé depuis un fichier (Internet, sur choix explicite)."""
    _pair(code)
    return _new_job(user, f"Téléchargement du modèle de découpage en phrases ({code})", [SBD_PREFIX + code])


def depot_dir():
    path = settings.TRANSLATION_ARGOS_DEPOT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_file_install(user, uploaded):
    """Copie le fichier envoyé dans le dossier de dépôt partagé avec le service, puis prépare la tâche."""
    original = uploaded.name or ""
    if not original.lower().endswith(".argosmodel"):
        raise PackageError("Fichier refusé : un paquet Argos se termine par « .argosmodel ».")
    if uploaded.size > settings.TRANSLATION_ARGOS_MAX_UPLOAD:
        raise PackageError("Fichier trop volumineux.")
    head = uploaded.read(4)
    uploaded.seek(0)
    if head != b"PK\x03\x04":  # un .argosmodel est une archive zip
        raise PackageError("Fichier refusé : ce n'est pas une archive de paquet Argos (.argosmodel).")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", original[: -len(".argosmodel")])[:22].strip("-.") or "paquet"
    # Nom court : il est conservé dans l'élément de tâche (60 caractères au plus, préfixe compris).
    name = f"{timezone.now():%y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}-{stem}.argosmodel"
    if len(FILE_PREFIX + name) > 60:  # garde-fou : ne peut pas arriver avec le format ci-dessus
        raise PackageError("Nom de fichier de transfert trop long.")
    with open(depot_dir() / name, "wb") as fh:
        for chunk in uploaded.chunks():
            fh.write(chunk)
    return _new_job(user, f"Installation du fichier {original[:200]}", [FILE_PREFIX + name])


def is_stale(job):
    """Installation sans signe d'activité au-delà du délai maximal d'installation (worker arrêté…)."""
    if job.status not in ("confirmed", "running"):
        return False
    limit = timezone.now() - timedelta(seconds=settings.TRANSLATION_ARGOS_INSTALL_TIMEOUT) - timedelta(minutes=5)
    return (job.heartbeat_at or job.started_at or job.confirmed_at or job.created_at) < limit


def dispatch(job):
    from .tasks import run_package_job

    run_package_job.delay(job.pk)


def relaunch(job):
    """Reprise : les paquets en échec ou restés en attente sont réessayés ; ceux installés ne bougent pas."""
    if job.kind != "package":
        raise PackageError("Tâche d'une autre nature.")
    if job.status in ("confirmed", "running") and not is_stale(job):
        raise PackageError("L'installation est encore en cours.")
    job.items.filter(status="failed").update(status="pending", error_kind="", error_message="")
    job.status, job.finished_at, job.error_summary = "confirmed", None, ""
    job.heartbeat_at = timezone.now()
    job.save(update_fields=["status", "finished_at", "error_summary", "heartbeat_at"])
    dispatch(job)


def _installed_codes(engine):
    try:
        health = engine.health() or {}
    except TranslationEngineError:
        return set()
    return {f"{p.get('from')}→{p.get('to')}" for p in health.get("packages") or []}


def _install_item(engine, item):
    value = item.record_field
    if value.startswith(INDEX_PREFIX):
        code = value[len(INDEX_PREFIX):]
        if code in _installed_codes(engine):
            return "déjà installé"
        source, target = _pair(code)
        result = engine.install(source, target) or {}
        detail = f"version {result.get('version', '?')}"
        if result.get("sbd_model"):
            detail += f" ; modèle de découpage en phrases « {result['sbd_model']} » téléchargé"
        return detail
    if value.startswith(SBD_PREFIX):
        source, target = _pair(value[len(SBD_PREFIX):])
        result = engine.install_sbd(source, target) or {}
        return (f"modèle « {result['sbd_model']} » téléchargé" if result.get("sbd_model")
                else "aucun modèle à télécharger")
    if value.startswith(FILE_PREFIX):
        name = value[len(FILE_PREFIX):]
        engine.install_file(name)
        try:  # copie de transfert seulement (le fichier d'origine reste sur le poste de l'utilisateur)
            (depot_dir() / name).unlink()
        except OSError:
            pass
        return "installé depuis le fichier"
    raise PackageError("Élément de tâche inconnu.")


def run_package_job(job_id):
    job = TranslationJob.objects.filter(pk=job_id, kind="package").first()
    if job is None or job.status not in ("confirmed", "running"):
        return
    from apps.ai import local

    if local.is_install_job(job):  # 2.0.0 (lot 4) : modèle de l'IA locale
        return local.run_install_job(job)
    now = timezone.now()
    job.status, job.started_at, job.heartbeat_at = "running", job.started_at or now, now
    job.save(update_fields=["status", "started_at", "heartbeat_at"])
    engine = client(job.user)
    for item in job.items.filter(status="pending").order_by("position"):
        job.heartbeat_at = timezone.now()
        job.save(update_fields=["heartbeat_at"])
        try:
            detail = _install_item(engine, item)
            item.status, item.error_kind, item.error_message = "done", "", detail[:500]
        except TranslationEngineError as exc:
            record_translation_error(exc, engine="argos", operation=f"Installation de paquet Argos (tâche n° {job.pk})")
            item.status, item.error_kind, item.error_message = "failed", exc.code or exc.kind, str(exc)[:500]
        except PackageError as exc:
            item.status, item.error_kind, item.error_message = "failed", "requete", str(exc)[:500]
        item.attempts += 1
        item.save(update_fields=["status", "error_kind", "error_message", "attempts", "updated_at"])
        job.refresh_from_db(fields=["status"])
        if job.status == "cancelled":
            return
    statuses = list(job.items.values_list("status", flat=True))
    job.done_items, job.failed_items = statuses.count("done"), statuses.count("failed")
    job.status = "done" if job.failed_items == 0 else "failed"
    job.finished_at = job.heartbeat_at = timezone.now()
    if job.failed_items:
        job.error_summary = f"{job.failed_items} paquet(s) non installé(s) : voir le détail."
    job.save(update_fields=["status", "done_items", "failed_items", "finished_at", "heartbeat_at", "error_summary"])
    check = None
    if job.done_items:
        # 2.0.0 : test de démarrage — traduction d'une phrase fictive, résultat sur la page « État ».
        from .argos_selftest import run_selftest

        check = run_selftest()
    _notify_end(job, check)


def _notify_end(job, check):
    """2.0.0 (lot 7) : fenêtre de notification à la fin d'une installation (réussite, essai ou échec)."""
    if job.user_id is None:
        return
    from django.urls import reverse

    from apps.notifications.services import notify

    link = reverse("translation:local_engines")
    label = job.scope_label.split(" : ")[0]
    if job.status == "failed":
        notify(job.user, "task_errors", f"Échec : {label}"[:200], body=job.error_summary, link=link,
               severity="error", group_key=f"argos:{job.pk}:end")
    elif check is not None and not check.ok:
        notify(job.user, "task_errors", f"Paquets installés, mais l'essai a échoué : {label}"[:200],
               body=check.message, link=link, severity="error", group_key=f"argos:{job.pk}:end")
    else:
        notify(job.user, "task_done", f"Terminé : {label}"[:200], body=check.message if check else "",
               link=link, severity="success", group_key=f"argos:{job.pk}:end")


def run_safely(job_id):
    """Une erreur imprévue est journalisée et la tâche marquée en échec (jamais masquée)."""
    from apps.incidents.services import record_incident, short_traceback

    try:
        run_package_job(job_id)
    except Exception as exc:  # noqa: BLE001
        record_incident(module="traduction", category="erreur_application", severity="error", origin="application",
                        title=f"{exc.__class__.__name__} pendant : installation de paquet Argos n° {job_id}",
                        message="Erreur inattendue pendant une installation de paquet Argos (voir la pile d'appels).",
                        operation=f"Installation de paquet Argos n° {job_id}", technical_code=exc.__class__.__name__,
                        context={"exception": exc.__class__.__name__, "traceback": short_traceback(exc)})
        TranslationJob.objects.filter(pk=job_id).update(status="failed", finished_at=timezone.now(),
                                                        error_summary=f"Erreur inattendue : {exc.__class__.__name__}")


def remove(code):
    source, target = _pair(code)
    try:
        return client().remove(source, target)
    except TranslationEngineError as exc:
        record_translation_error(exc, engine="argos", operation=f"Désinstallation du paquet Argos {code}")
        raise


def index_packages():
    """Consultation de l'index (Internet, par le service) — appelée seulement sur action explicite."""
    try:
        return client().index()
    except TranslationEngineError as exc:
        record_translation_error(exc, engine="argos", operation="Consultation de l'index des paquets Argos")
        raise
