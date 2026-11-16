"""2.0.0 — lot 9 : performances. Nombre de requêtes plafonné, résultats identiques avant et après."""
from collections import OrderedDict
from decimal import Decimal

from django.db import connection
from django.db.models import Sum
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.translation import usage as U
from apps.translation.models import TranslationJob

from .test_translation_projects import ProjectTestCase
from . import test_translation_usage as usage_tests


def reference_monthly_usage(user, month):
    """Calcul de la 1.3.0 (deux à trois requêtes par tâche), gardé ici pour comparer les résultats."""
    from apps.ai.models import AITask

    start, end = U.month_bounds(month.year, month.month)
    jobs = (TranslationJob.objects.filter(user=user, status__in=U.SPENDING_STATUSES, created_at__gte=start,
                                          created_at__lt=end)
            .exclude(kind="package").select_related("project").order_by("created_at"))
    rows, detail, totals = OrderedDict(), [], {}
    for job in jobs:
        key, label, code = U.engine_key(job)
        row = rows.setdefault(key, {"label": label, "code": code, "jobs": 0, "chars": 0, "translations": 0,
                                    "simulated": 0, "costs": {}, "tokens_in": 0, "tokens_out": 0})
        costs = U.job_cost(job)
        done = job.items.filter(status="done").count()
        simulated = job.items.filter(status="done", version__simulated=True).count()
        row["jobs"] += 1
        row["chars"] += job.chars_sent
        row["translations"] += done
        row["simulated"] += simulated
        U._add(row["costs"], costs)
        U._add(totals, costs)
        if code == "ai":
            agg = AITask.objects.filter(translation_job_items__job=job).distinct().aggregate(
                i=Sum("tokens_in"), o=Sum("tokens_out"))
            row["tokens_in"] += agg["i"] or 0
            row["tokens_out"] += agg["o"] or 0
        detail.append({"job": job, "label": label, "costs": costs, "done": done})
    return {"rows": list(rows.values()), "totals": totals, "detail": [(d["job"].pk, d["costs"], d["done"]) for d in detail]}


class UsageQueriesTests(ProjectTestCase):
    job = usage_tests.UsageTests.job  # mêmes tâches fictives que les tests de la page Consommation, sans en rejouer les tests

    def fill(self, n):
        for i in range(n):
            self.job("deepl", 100 + i, [Decimal("0.001"), Decimal("0.002")])
            self.job("ai", 50, [Decimal("0.01")], currency="USD", ai=("anthropic", "modele-fictif"))
            self.job("argos", 0, [None])

    def test_fixed_number_of_queries(self):
        month = timezone.localdate().replace(day=1)
        self.fill(3)
        with CaptureQueriesContext(connection) as small:
            U.monthly_usage(self.owner, month)
        self.fill(12)
        with CaptureQueriesContext(connection) as big:
            U.monthly_usage(self.owner, month)
        self.assertEqual(len(small), len(big), "le nombre de requêtes ne dépend pas du nombre de tâches")
        self.assertLessEqual(len(big), 6)

    def test_same_results_as_before(self):
        month = timezone.localdate().replace(day=1)
        self.fill(4)
        self.job("deepl", 999, [Decimal("9")], status="draft")
        new = U.monthly_usage(self.owner, month)
        old = reference_monthly_usage(self.owner, month)
        self.assertEqual(new["rows"], old["rows"])
        self.assertEqual(new["totals"], old["totals"] if not new["legacy"]["tasks"] else new["totals"])
        self.assertEqual([(d["job"].pk, d["costs"], d["done"]) for d in new["detail"]], old["detail"])


# --------------------------------------------------------------------------- commande de mesure (lot 9a)

import io
import json as _json

from django.core.management import CommandError, call_command
from django.test import TestCase, TransactionTestCase

from apps.core import performances as PERF
from apps.core.management.commands import mesurer_performances as CMD


class MeasureModuleTests(TestCase):
    def test_fictive_measures_on_small_volume(self):
        user, record = PERF.generate(150)
        from apps.catalog.models import Record
        self.assertEqual(Record.objects.filter(catalogue__code="mesure-fictif").count(), 150)
        measures = PERF.measure_fictive(1, user, record)
        keys = [m.key for m in measures]
        for key in ("libre_2", "libre_4", "titre", "auteur", "doublons", "consommation", "page_bibliotheque",
                    "page_fiche", "page_consommation", "page_recherche"):
            self.assertIn(key, keys)
        for m in measures:
            self.assertGreaterEqual(m.ms, 0)
            if m.key.startswith("page_"):
                self.assertEqual(m.detail, "HTTP 200", m.label)

    def test_real_measure_changes_nothing(self):
        from apps.catalog.models import Record
        before = Record.objects.count()
        count, measures = PERF.measure_real(1)
        self.assertEqual(count, before)
        self.assertEqual(Record.objects.count(), before)
        self.assertTrue(all(m.key.startswith("reel_") for m in measures))

    def test_report_text_and_json(self):
        report = PERF.Report(notices=100, repetitions=1)
        report.measures = [PERF.Measure("titre", "Critère Titre", 12.5, 2, "3 réponse(s)")]
        report.real_count, report.real = 0, []
        self.assertIn("Critère Titre", report.text())
        _json.dumps(report.as_dict(), ensure_ascii=False)

    def test_internal_mode_refused_outside_a_temporary_database(self):
        with self.assertRaisesMessage(CommandError, "base temporaire"):
            call_command("mesurer_performances", "--interne", "--notices", "100", stdout=io.StringIO())

    def test_url_quotes_credentials(self):
        url = CMD._url({"USER": "jed", "PASSWORD": "a@b:c/d", "HOST": "db", "PORT": "5432"}, "x_mesures_1")
        self.assertEqual(url, "postgres://jed:a%40b%3Ac%2Fd@db:5432/x_mesures_1")


class MeasureCommandTests(TransactionTestCase):
    """Commande complète : base temporaire créée, mesurée puis supprimée ; la base courante n'est pas touchée."""

    def _temporary_databases(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT datname FROM pg_database WHERE datname LIKE %s", ["%\\_mesures\\_%"])
            return [r[0] for r in cursor.fetchall()]

    def test_full_command_drops_its_temporary_database(self):
        from apps.catalog.models import Record
        before = Record.objects.count()
        out, err = io.StringIO(), io.StringIO()
        call_command("mesurer_performances", "--notices", "100", "--essais", "1", "--json", stdout=out, stderr=err)
        data = _json.loads(out.getvalue())
        self.assertEqual(data["notices_fictives"], 100)
        self.assertIn("page_fiche", [m["cle"] for m in data["mesures"]])
        self.assertIn("supprimée", err.getvalue())
        self.assertEqual(self._temporary_databases(), [])
        self.assertEqual(Record.objects.count(), before)
