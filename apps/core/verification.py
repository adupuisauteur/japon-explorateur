"""Vérification des fonctionnalités d'une installation (2.0.0) : `manage.py verifier_fonctionnalites`.

Complète le protocole manuel : chaque fonction principale est réellement exercée avec des données FICTIVES.

Garanties :
- tout se passe dans UNE transaction annulée à la fin : aucune notice, aucun compte, aucun projet n'est
  ajouté ni modifié dans la base ;
- les fichiers produits (exports, imports) vont dans un dossier temporaire supprimé à la fin ;
- aucun appel à Internet, sauf avec --sources (une recherche d'essai par source, demandée explicitement) ;
- aucun texte n'est envoyé à un service en ligne ; Argos (local) traduit une phrase fictive s'il est démarré ;
- seul effet durable possible : le signe de vie du planificateur (contrôle technique, sans contenu).
"""
import logging
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.test import Client, override_settings
from django.utils import timezone

from . import health

OK, WARNING, ERROR, SKIPPED = "ok", "warning", "error", "skipped"
LABELS = {OK: "OK", WARNING: "À surveiller", ERROR: "Problème", SKIPPED: "Non vérifié"}
FICTIVE_TITLE = "架空検証書"  # titre fictif, absent de tout catalogue réel
FICTIVE_TEXT = "これは検証用の架空の文です。次の文も架空です。"


@dataclass
class Result:
    key: str
    label: str
    level: str
    summary: str
    details: list = field(default_factory=list)

    @property
    def level_label(self):
        return LABELS[self.level]


class Context:
    """Données fictives partagées entre les vérifications (créées dans la transaction annulée)."""

    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.admin = self.researcher = self.reader = None
        self.catalogue = self.record = None


# --------------------------------------------------------------------------- vérifications


def check_installation(ctx):
    results = health.collect()
    problems = [r for r in results if r.level == health.ERROR]
    warnings = [r for r in results if r.level == health.WARNING]
    details = [f"{r.label} : {r.summary}" for r in problems + warnings]
    if problems:
        return ERROR, f"{len(problems)} point(s) en erreur sur la page « État de l'installation »", details
    if warnings:
        return WARNING, f"{len(warnings)} point(s) à surveiller sur la page « État de l'installation »", details
    return OK, "Tous les contrôles de la page « État de l'installation » sont corrects", []


def check_accounts(ctx):
    from apps.accounts.models import User

    suffix = uuid.uuid4().hex[:8]  # jamais le nom d'un compte réel
    password = f"Verification-fictive-{uuid.uuid4().hex}"
    ctx.admin = User.objects.create_user(f"verification-admin-{suffix}", password=password, role="admin",
                                         is_staff=True)
    ctx.researcher = User.objects.create_user(f"verification-chercheur-{suffix}", password=password,
                                              role="researcher")
    ctx.reader = User.objects.create_user(f"verification-lecteur-{suffix}", password=password, role="reader")
    admins = User.objects.filter(role="admin", is_active=True).exclude(pk=ctx.admin.pk).count()
    if not admins:
        return WARNING, "Aucun compte administrateur actif (hors compte fictif)", []
    return OK, f"Comptes fictifs créés pour la vérification ; {admins} administrateur(s) réel(s) actif(s)", []


def check_japanese(ctx):
    from apps.core import japanese as jp

    details = []
    folded = jp.search_normalize("カタカナ　ＡＢＣ Tōkyō")
    if folded != "かたかな abc tokyo":
        return ERROR, f"Normalisation de recherche inattendue : « {folded} »", []
    romaji = jp.to_romaji("源氏物語")
    if not romaji:
        return ERROR, "Transcription en rōmaji indisponible (bibliothèque pykakasi)", []
    details.append(f"源氏物語 → {romaji}")
    return OK, "Normalisation (kana, pleine chasse, macrons) et rōmaji fonctionnent", details


def check_records_and_search(ctx):
    from apps.catalog.models import Catalogue, Record
    from apps.catalog.search import local_search
    from apps.catalog.services import upsert_record
    from apps.connectors.base import SearchQuery

    ctx.catalogue = Catalogue.objects.create(code="verification-fictive", name="Catalogue fictif (vérification)")
    ctx.record, _ = upsert_record(ctx.catalogue, {
        "source_id": "VERIF-1", "original_title": FICTIVE_TITLE, "creator_original": "架空太郎",
        "description_original": "検証のための架空の解題。", "copy_date_text": "慶長五年"}, origin="import")
    found = list(local_search(SearchQuery(text=FICTIVE_TITLE)).values_list("pk", flat=True))
    if ctx.record.pk not in found:
        return ERROR, "La notice fictive n'est pas retrouvée par la recherche locale", []
    by_creator = local_search(SearchQuery(creator="架空太郎")).filter(pk=ctx.record.pk).exists()
    updated, _ = upsert_record(ctx.catalogue, {"source_id": "VERIF-1", "original_title": FICTIVE_TITLE,
                                               "description_original": "修正された架空の解題。"}, origin="import")
    versions = updated.versions.count()
    details = [f"Recherche par auteur : {'oui' if by_creator else 'non'}", f"Versions historisées : {versions}",
               f"{Record.objects.exclude(catalogue=ctx.catalogue).count()} notice(s) déjà présente(s) dans la base (non modifiées)"]
    if not by_creator or versions < 2:
        return ERROR, "Recherche par champ ou historique des versions défaillant", details
    return OK, "Création, recherche libre et par auteur, historique des versions", details


def check_duplicates(ctx):
    from apps.catalog.services import duplicate_candidates, upsert_record

    twin, _ = upsert_record(ctx.catalogue, {"source_id": "VERIF-2", "original_title": FICTIVE_TITLE,
                                            "creator_original": "架空太郎"}, origin="import")
    candidates = [c[0].pk for c in duplicate_candidates(ctx.record)]
    if twin.pk not in candidates:
        return ERROR, "Le doublon fictif n'est pas proposé", []
    return OK, "Un doublon fictif est bien proposé (jamais fusionné automatiquement)", []


def check_import(ctx):
    from apps.updates import importers

    examples = Path(settings.BASE_DIR) / "docs" / "exemples"
    details = []
    for name in ("exemple_inventaire.csv", "exemple_classeur.xlsx"):
        path = examples / name
        if not path.exists():
            return WARNING, f"Fichier d'exemple absent : {name}", details
        copy = ctx.tmp / name
        shutil.copy(path, copy)
        fmt = importers.detect_format(name, copy.read_bytes()[:4096])
        columns, rows, _info = importers.read_rows(copy, fmt)
        rows = list(rows)
        if not rows:
            return ERROR, f"Aucune ligne lue dans {name} (format détecté : {fmt})", details
        mapping = importers.auto_mapping(list(columns))
        details.append(f"{name} : format {fmt}, {len(rows)} ligne(s), {len(mapping)} colonne(s) reconnue(s)")
    return OK, "Lecture des fichiers d'exemple CSV et Excel (rien n'est importé)", details


def check_library(ctx):
    from apps.library.models import Collection, CollectionRecord, LibraryEntry

    LibraryEntry.objects.create(user=ctx.researcher, record=ctx.record)
    collection = Collection.objects.create(owner=ctx.researcher, title="Dossier fictif de vérification")
    CollectionRecord.objects.create(collection=collection, record=ctx.record, added_by=ctx.researcher)
    client = _client(ctx.researcher)
    page = client.get("/bibliotheque/")
    if page.status_code != 200 or FICTIVE_TITLE not in page.content.decode():
        return ERROR, f"La Bibliothèque ne montre pas la notice fictive (HTTP {page.status_code})", []
    return OK, "Ajout à la Bibliothèque et à un dossier, affichage de la Bibliothèque", []


def check_exports(ctx):
    from apps.exports.models import ExportJob
    from apps.exports.services import generate

    details, failures = [], []
    for fmt in ("docx", "pdf", "txt", "json", "csv", "html"):
        job = ExportJob.objects.create(owner=ctx.researcher, scope="selection", format=fmt,
                                       title="Export fictif de vérification",
                                       scope_params={"record_ids": [ctx.record.record_id]})
        job = generate(job)
        size = sum(f.size for f in job.files.all())
        if job.status != "done" or not size:
            failures.append(f"{fmt} : {job.error or 'fichier vide'}")
        else:
            details.append(f"{fmt} : {size} octets")
    from apps.exports.generators.pdf_gen import font_set

    embedded = font_set()[3]
    details.append("Police japonaise incorporée dans les PDF : " + ("oui" if embedded else "NON (police de secours)"))
    if failures:
        return ERROR, f"{len(failures)} format(s) d'export en échec", failures + details
    return (OK if embedded else WARNING), "Exports Word, PDF, texte, JSON, CSV et site HTML produits", details


def check_translation(ctx):
    from apps.translation import exports as texports
    from apps.translation import glossary as G
    from apps.translation import memory as tm
    from apps.translation import projects as P
    from apps.translation.models import Glossary, TranslationProject

    project = TranslationProject.objects.create(owner=ctx.researcher, title="Projet fictif de vérification")
    document = P.create_document(project, title="Document fictif", text=FICTIVE_TEXT)
    segments = list(document.segments.order_by("position"))
    if len(segments) != 2:
        return ERROR, f"Découpage en segments inattendu : {len(segments)} au lieu de 2", []
    P.validate_version(P.add_human_version(segments[0], ctx.researcher, "Ceci est une phrase fictive."),
                       ctx.researcher)
    memory = tm.lookup(ctx.researcher, tm.memory_key(segments[0].source_text), exclude_segment=segments[1])
    glossary = Glossary.objects.create(owner=ctx.researcher, name="Glossaire fictif")
    G.save_entry(glossary, {"source_term": "架空", "target_term": "fictif"})
    in_source = G.source_contains(FICTIVE_TEXT, "架空", "ja")
    text = texports.bilingual_txt(texports.collect(project))
    details = [f"Mémoire de traduction : {'trouvée' if memory else 'non trouvée'}",
               f"Glossaire : terme repéré dans l'original : {'oui' if in_source else 'non'}",
               f"Export bilingue : {len(text)} caractères"]
    if not memory or not in_source or "Ceci est une phrase fictive." not in text:
        return ERROR, "Projet, mémoire, glossaire ou export bilingue défaillant", details
    return OK, "Projet, découpage, validation, mémoire, glossaire et export bilingue", details


def check_argos(ctx):
    from apps.translation.argos_selftest import run_selftest
    from apps.translation.engines.argos import ArgosEngine

    from .models import AppSettings

    if not ArgosEngine(None).service_url:
        return SKIPPED, "Service Argos non configuré", []
    check = run_selftest()
    demo = AppSettings.get().argos_demo_mode
    details = [check.message] + (["Mode démonstration ACTIVÉ"] if demo else [])
    if check.ok:
        return OK, "Argos traduit la phrase fictive", details + [f"Traduction : {check.data.get('translation', '')}"]
    return WARNING, "Argos ne traduit pas (service arrêté, désactivé ou paquets absents)", details


def check_background_tasks(ctx):
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return SKIPPED, "Tâches exécutées immédiatement (pas de Redis) : rien à vérifier", []
    from .models import ServiceCheck
    from .tasks import heartbeat

    started = timezone.now()
    heartbeat.delay("verification")
    for _ in range(40):
        time.sleep(0.5)
        beat = ServiceCheck.objects.filter(name="planificateur", checked_at__gte=started).first()
        if beat:
            delay = (beat.checked_at - started).total_seconds()
            when = "en moins d'une seconde" if delay < 1 else f"en {delay:.0f} s"
            return OK, f"Un worker a exécuté une tâche d'essai {when}", []
    return ERROR, "Aucun worker n'a exécuté la tâche d'essai en 20 s", [
        "Traductions, exports et sauvegardes planifiées ne partiraient pas. Vérifiez le conteneur « worker »."]


def check_backup(ctx):
    from apps.backups.models import BackupJob
    from apps.backups.services import verify_backup

    last = BackupJob.objects.filter(status="done").order_by("-created_at").first()
    if last is None:
        return WARNING, "Aucune sauvegarde réussie à vérifier", ["Administration → Sauvegardes → Sauvegarder maintenant"]
    ok, message = verify_backup(last)
    detail = [f"Sauvegarde du {timezone.localtime(last.created_at):%d/%m/%Y %H:%M} : {message}"]
    if last.external_copy:
        detail.append("Copie externe : " + ("présente" if Path(last.external_copy).exists() else "INTROUVABLE"))
    return (OK if ok else ERROR), "Intégrité de la dernière sauvegarde" + (" vérifiée" if ok else " en défaut"), detail


PAGES = [
    ("/", "Accueil"), ("/recherche/", "Recherche"), ("/bibliotheque/", "Bibliothèque"),
    ("/bibliotheque/dossiers/", "Dossiers"), ("/traduction/", "Traduction"), ("/traduction/moteurs/", "Moteurs"),
    ("/traduction/moteurs/locaux/", "Moteurs locaux"), ("/sources/", "Sources"), ("/journal/", "Dysfonctionnements"),
    ("/ia/fournisseurs/", "IA — fournisseurs"), ("/administration/", "Administration"),
    ("/administration/etat/", "État de l'installation"), ("/administration/sauvegardes/", "Sauvegardes"),
    ("/administration/parametres/", "Paramètres"), ("/hors-ligne/", "Page hors ligne"), ("/sw.js", "Service worker"),
    ("/manifest.webmanifest", "Manifeste de l'application"),
]


def check_pages(ctx):
    client = _client(ctx.admin)
    failures, csp_missing = [], []
    for url, label in PAGES:
        response = client.get(url)
        if response.status_code != 200:
            failures.append(f"{label} ({url}) : HTTP {response.status_code}")
        elif url.endswith("/") and "Content-Security-Policy" not in response.headers:
            csp_missing.append(label)
    if failures:
        return ERROR, f"{len(failures)} page(s) en erreur pour l'administrateur", failures
    if csp_missing:
        return ERROR, "Politique de sécurité (CSP) absente", csp_missing
    return OK, f"{len(PAGES)} pages principales s'ouvrent pour l'administrateur, avec la politique de sécurité", []


def check_permissions(ctx):
    reader, researcher = _client(ctx.reader), _client(ctx.researcher)
    problems = []
    # Les refus d'accès provoqués ici sont attendus : ils ne doivent pas encombrer le journal.
    request_logger = logging.getLogger("django.request")
    previous = request_logger.level
    request_logger.setLevel(logging.CRITICAL)
    try:
        _permission_probes(ctx, reader, researcher, problems)
    finally:
        request_logger.setLevel(previous)
    if problems:
        return ERROR, "Droits d'accès incorrects", problems
    return OK, "Lecteur, chercheur et visiteur non connecté limités comme prévu", []


def _permission_probes(ctx, reader, researcher, problems):
    if reader.get("/administration/").status_code not in (302, 403):
        problems.append("Le lecteur accède à l'Administration")
    if researcher.get("/administration/sauvegardes/").status_code not in (302, 403):
        problems.append("Le chercheur accède aux sauvegardes")
    if reader.post("/bibliotheque/ajouter/", {"record_ids": ctx.record.record_id}).status_code not in (302, 403):
        problems.append("Le lecteur peut modifier la Bibliothèque")
    anonymous = Client()
    if anonymous.get("/bibliotheque/").status_code != 302:
        problems.append("La Bibliothèque est accessible sans connexion")


def check_sources(ctx):
    from apps.catalog.models import Catalogue
    from apps.connectors.registry import get_connector

    details, failures = [], 0
    for catalogue in Catalogue.objects.filter(enabled_for_search=True).exclude(code="local").order_by("name"):
        try:
            ok, message, _data = get_connector(catalogue).test()
        except Exception as exc:  # noqa: BLE001 — affiché tel quel
            ok, message = False, f"{exc.__class__.__name__} : {exc}"
        failures += 0 if ok else 1
        details.append(f"{catalogue.name} : {'répond' if ok else 'ÉCHEC'} — {str(message)[:150]}")
    if not details:
        return SKIPPED, "Aucune source en ligne activée pour la recherche", []
    if failures:
        return WARNING, f"{failures} source(s) sur {len(details)} ne répondent pas", details
    return OK, f"{len(details)} source(s) en ligne répondent", details


#: (clé, libellé, fonction, prérequis) — prérequis : "comptes" (comptes fictifs), "notice" (notice fictive),
#: "internet" (seulement avec --sources)
CHECKS = [
    ("installation", "État de l'installation", check_installation, ()),
    ("comptes", "Comptes fictifs de vérification", check_accounts, ()),
    ("japonais", "Traitement du japonais", check_japanese, ()),
    ("notices", "Notices et recherche locale", check_records_and_search, ()),
    ("doublons", "Détection des doublons", check_duplicates, ("notice",)),
    ("import", "Lecture des fichiers d'import", check_import, ()),
    ("bibliotheque", "Bibliothèque et dossiers", check_library, ("comptes", "notice")),
    ("exports", "Exports", check_exports, ("comptes", "notice")),
    ("traduction", "Projets de traduction", check_translation, ("comptes",)),
    ("argos", "Traduction hors ligne (Argos)", check_argos, ()),
    ("taches", "Tâches de fond (worker)", check_background_tasks, ()),
    ("sauvegarde", "Dernière sauvegarde", check_backup, ()),
    ("pages", "Pages principales", check_pages, ("comptes",)),
    ("droits", "Droits d'accès", check_permissions, ("comptes", "notice")),
    ("sources", "Sources en ligne (avec --sources)", check_sources, ("internet",)),
]


def _client(user):
    client = Client()
    client.force_login(user)
    return client


class _Rollback(Exception):
    pass


def _missing(ctx, needs, with_sources):
    if "internet" in needs and not with_sources:
        return "Non demandé (option --sources : une recherche d'essai par source, sur Internet)"
    if "comptes" in needs and ctx.admin is None:
        return "Comptes fictifs indisponibles (voir la ligne « Comptes fictifs »)"
    if "notice" in needs and ctx.record is None:
        return "Notice fictive indisponible (voir la ligne « Notices et recherche locale »)"
    return ""


def run(*, with_sources=False):
    """Exécute les vérifications dans une transaction annulée ; retourne la liste des résultats."""
    results = []
    tmp = tempfile.mkdtemp(prefix="jed-verification-")
    hosts = list(settings.ALLOWED_HOSTS) + ["testserver"]
    try:
        with override_settings(MEDIA_ROOT=str(Path(tmp) / "fichiers"), ALLOWED_HOSTS=hosts):
            try:
                with transaction.atomic():
                    ctx = Context(tmp)
                    for key, label, func, needs in CHECKS:
                        missing = _missing(ctx, needs, with_sources)
                        if missing:
                            results.append(Result(key, label, SKIPPED, missing))
                            continue
                        try:
                            with transaction.atomic():  # point de reprise : un échec n'arrête pas la suite
                                level, summary, details = func(ctx)
                        except Exception as exc:  # noqa: BLE001 — l'erreur est le résultat, jamais masquée
                            level, summary, details = ERROR, f"Erreur inattendue ({exc.__class__.__name__} : {exc})", []
                            if key == "comptes":
                                ctx.admin = ctx.researcher = ctx.reader = None
                            if key == "notices":
                                ctx.record = None
                        results.append(Result(key, label, level, summary, list(details)))
                    raise _Rollback  # annule TOUT ce qui a été créé
            except _Rollback:
                pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return results


def overall(results):
    rank = {OK: 0, SKIPPED: 0, WARNING: 1, ERROR: 2}
    return max((r.level for r in results), key=rank.get, default=OK)


def report_text(results):
    lines = [f"Vérification des fonctionnalités — J-ed {settings.APP_VERSION} — {timezone.localtime():%d/%m/%Y %H:%M}",
             "Données fictives, transaction annulée : la base n'a pas été modifiée.", ""]
    for r in results:
        lines.append(f"[{r.level_label}] {r.label} : {r.summary}")
        lines.extend(f"    {d}" for d in r.details)
    counts = {level: sum(1 for r in results if r.level == level) for level in LABELS}
    lines += ["", "Bilan : " + ", ".join(f"{LABELS[k]} {v}" for k, v in counts.items())]
    return health.mask_personal("\n".join(lines))
