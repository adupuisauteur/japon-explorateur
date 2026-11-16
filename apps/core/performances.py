"""Mesure des performances (2.0.0, lot 9) — commande `manage.py mesurer_performances`.

Deux parties :

- **Base temporaire** (créée puis supprimée) : notices FICTIVES en nombre (50 000 par défaut), puis mesure de la
  recherche, de la détection des doublons, des pages Bibliothèque, fiche et Consommation. Rien n'est écrit dans la
  base réelle.
- **Vos données, en lecture seule** : les mêmes recherches sur la base réelle, dans une transaction annulée.

Chaque mesure est la médiane de plusieurs essais. Les chiffres servent à décider d'une optimisation : seules les
mesures faites sur le poste de l'utilisateur comptent (Windows et WSL 2 sont plus lents qu'un serveur Linux).
"""
import random
import statistics
import time
from dataclasses import dataclass, field

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

#: Caractères des titres fictifs (kanji et kana courants) ; quelques mots fréquents pour des recherches réalistes.
KANJI = "日本書記物語集抄伝記録和歌源氏平家今昔古事談宇治拾遺方丈徒然枕草子竹取伊勢大和土佐蜻蛉更級"
KANA = "のはをにでとがもへやかなりけるしたつきて"
COMMON = ["物語", "日記", "和歌", "記録", "藤原定家", "源氏", "江戸", "京都"]
AUTHORS = ["架空太郎", "架空花子", "藤原定家", "紀貫之", "本居宣長", "架空一郎", "清少納言", "鴨長明", "兼好"]
INSTITUTIONS = ["架空図書館", "架空大学", "架空文庫", "架空博物館"]


@dataclass
class Measure:
    key: str
    label: str
    ms: float
    queries: int = 0
    detail: str = ""


@dataclass
class Report:
    notices: int = 0
    repetitions: int = 0
    measures: list = field(default_factory=list)
    real: list = field(default_factory=list)
    real_count: int = 0

    def as_dict(self):
        def rows(items):
            return [{"cle": m.key, "libelle": m.label, "ms": round(m.ms, 1), "requetes": m.queries,
                     "detail": m.detail} for m in items]

        return {"notices_fictives": self.notices, "essais": self.repetitions, "mesures": rows(self.measures),
                "vos_donnees": {"notices": self.real_count, "mesures": rows(self.real)}}

    def text(self):
        lines = [f"Base temporaire : {self.notices} notices fictives ; médiane de {self.repetitions} essais.", ""]
        lines += [_line(m) for m in self.measures]
        if self.real:
            lines += ["", f"Vos données (lecture seule) : {self.real_count} notices.", ""]
            lines += [_line(m) for m in self.real]
        return "\n".join(lines)


def _line(m):
    queries = f" · {m.queries} requête(s)" if m.queries else ""
    detail = f" · {m.detail}" if m.detail else ""
    return f"{m.label:<46} {m.ms:>8.0f} ms{queries}{detail}"


def timed(func, repetitions):
    """(médiane en ms, requêtes du dernier essai, résultat du dernier essai)."""
    times, result, queries = [], None, 0
    for _ in range(repetitions):
        with CaptureQueriesContext(connection) as ctx:
            started = time.perf_counter()
            result = func()
            times.append((time.perf_counter() - started) * 1000)
        queries = len(ctx.captured_queries)
    return statistics.median(times), queries, result


# --------------------------------------------------------------------------- données fictives


def _title(rnd):
    parts = [rnd.choice(COMMON) if rnd.random() < 0.35 else "".join(rnd.choice(KANJI) for _ in range(rnd.randint(1, 3)))
             for _ in range(rnd.randint(1, 3))]
    return rnd.choice(KANA).join(parts) + rnd.choice(["", "", "抄", "集", "記"])


def generate(count, seed=2026):
    """Crée `count` notices fictives (et ce qu'il faut autour) dans la base courante. À n'appeler que dans une base
    temporaire : la commande le garantit."""
    from apps.accounts.models import User
    from apps.catalog.models import Catalogue, Record, new_uid
    from apps.catalog.normalization import normalize_record
    from apps.library.models import LibraryEntry

    rnd = random.Random(seed)
    catalogue, _ = Catalogue.objects.get_or_create(code="mesure-fictif", defaults={"name": "Catalogue fictif (mesure)"})
    batch = []
    for i in range(count):
        record = Record(catalogue=catalogue, source_id=f"fictif-{i}", original_title=_title(rnd),
                        creator_original=rnd.choice(AUTHORS), holding_institution_text=rnd.choice(INSTITUTIONS),
                        description_original=" ".join(_title(rnd) for _ in range(rnd.randint(3, 15))),
                        copy_year_start=rnd.randint(1600, 1900))
        record.record_id = new_uid("REC")
        normalize_record(record)
        batch.append(record)
        if len(batch) == 2000:
            Record.objects.bulk_create(batch)
            batch = []
    if batch:
        Record.objects.bulk_create(batch)
    user, _ = User.objects.get_or_create(username="mesure-fictif", defaults={"role": "admin"})
    records = list(Record.objects.filter(catalogue=catalogue).order_by("pk")[:2000])
    LibraryEntry.objects.bulk_create([LibraryEntry(user=user, record=r) for r in records], ignore_conflicts=True)
    _usage_jobs(user, 300)
    return user, records[0]


def _usage_jobs(user, count):
    """Tâches de traduction fictives du mois, pour la page Consommation (aucun envoi : données seules)."""
    from decimal import Decimal

    from apps.translation.models import TranslationJob, TranslationJobItem

    jobs = TranslationJob.objects.bulk_create([
        TranslationJob(user=user, kind="records", engine="deepl" if i % 3 else "argos", status="done",
                       chars_sent=1000, total_items=10, cost_estimate=Decimal("0.01")) for i in range(count)])
    TranslationJobItem.objects.bulk_create([TranslationJobItem(job=j, position=k, status="done", record_field="titre")
                                            for j in jobs for k in range(10)])


# --------------------------------------------------------------------------- mesures


def _searches():
    from apps.connectors.base import SearchQuery

    return [
        ("libre_2", "Recherche libre, 2 caractères (物語)", SearchQuery(text="物語")),
        ("libre_4", "Recherche libre, 4 caractères (藤原定家)", SearchQuery(text="藤原定家")),
        ("titre", "Critère Titre (源氏)", SearchQuery(title="源氏")),
        ("auteur", "Critère Auteur (鴨長明)", SearchQuery(creator="鴨長明")),
    ]


def measure_searches(repetitions, prefix=""):
    from apps.catalog.search import local_search

    out = []
    for key, label, query in _searches():
        def run(q=query):
            qs = local_search(q)
            return qs.count(), list(qs[:20])

        ms, queries, (total, _first) = timed(run, repetitions)
        out.append(Measure(prefix + key, label, ms, queries, f"{total} réponse(s)"))
    return out


def measure_fictive(repetitions, user, record):
    from django.test import Client
    from django.test.utils import override_settings
    from django.utils import timezone

    from apps.catalog.services import duplicate_candidates
    from apps.translation.usage import monthly_usage

    out = measure_searches(repetitions)
    ms, queries, found = timed(lambda: duplicate_candidates(record), repetitions)
    out.append(Measure("doublons", "Détection des doublons d'une notice", ms, queries, f"{len(found)} candidat(s)"))
    month = timezone.localdate().replace(day=1)
    ms, queries, _ = timed(lambda: monthly_usage(user, month), repetitions)
    out.append(Measure("consommation", "Calcul de la page Consommation (300 tâches)", ms, queries))
    client = Client()
    client.force_login(user)
    pages = [("page_bibliotheque", "Page Bibliothèque (2 000 notices)", "/bibliotheque/"),
             ("page_fiche", "Page d'une fiche", record.get_absolute_url()),
             ("page_consommation", "Page Consommation", "/traduction/consommation/"),
             ("page_recherche", "Page Rechercher", "/recherche/")]
    with override_settings(ALLOWED_HOSTS=["*"]):
        for key, label, url in pages:
            ms, queries, response = timed(lambda u=url: client.get(u), repetitions)
            out.append(Measure(key, label, ms, queries, f"HTTP {response.status_code}"))
    return out


def measure_real(repetitions):
    """Recherches sur la base réelle, dans une transaction annulée : rien n'est modifié."""
    from apps.catalog.models import Record

    class _Rollback(Exception):
        pass

    result = []
    try:
        with transaction.atomic():
            count = Record.objects.count()
            result = measure_searches(repetitions, prefix="reel_")
            raise _Rollback
    except _Rollback:
        pass
    return count, result
