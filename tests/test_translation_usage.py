"""Évolution 1.3.0 — lot 10 : consommation (T16) et évaluation sur le corpus de référence (§ 15).

Textes fictifs. DeepL simulé (réponses programmées), Argos en mode simulé : aucun envoi réel.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import User
from apps.ai.models import AITask
from apps.translation import evaluation as E
from apps.translation import projects as P
from apps.translation import services, usage as U
from apps.translation.models import (EngineSetting, TranslationJob, TranslationJobItem, TranslationPreference,
                                     TranslationProject, TranslationVersion)

from .test_translation_projects import ProjectTestCase

CORPUS = "江戸の町。\n\n武士の道。"


# --------------------------------------------------------------------------- consommation


class UsageTests(ProjectTestCase):
    def job(self, engine, chars, costs, *, status="done", kind="segments", currency="EUR", ai=None, months_ago=0):
        document = P.create_document(self.project, title=f"Doc {engine} {chars}", text="一。")
        job = TranslationJob.objects.create(user=self.owner, project=self.project, kind=kind, engine=engine,
                                            status=status, chars_sent=chars, total_items=len(costs),
                                            ai_provider=(ai or ("", ""))[0], ai_model=(ai or ("", ""))[1])
        for i, cost in enumerate(costs):
            version = TranslationVersion.objects.create(segment=document.segments.get(), text="fictif", source_text="一。",
                                                        origin="ai" if engine == "ai" else "machine", engine=engine,
                                                        cost_estimate=cost, currency=currency if cost is not None else "")
            task = None
            if engine == "ai":
                task = AITask.objects.create(user=self.owner, function="translation", provider=ai[0], model=ai[1],
                                             status="done", tokens_in=50, tokens_out=80, cost_estimate=cost,
                                             parameters={"translation_job": job.pk})
            TranslationJobItem.objects.create(job=job, position=i, segment=version.segment, status="done",
                                              version=version, ai_task=task, chars=chars)
        if months_ago:
            TranslationJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=40 * months_ago))
        return job

    def test_monthly_totals_per_engine_equal_the_sum_of_tasks_ai_included(self):
        self.job("deepl", 300, [Decimal("0.003"), Decimal("0.002")])
        self.job("deepl", 100, [Decimal("0.001")])
        self.job("ai", 120, [Decimal("0.010")], currency="USD", ai=("anthropic", "modele-fictif"))
        self.job("argos", 0, [None])
        self.job("deepl", 999, [Decimal("9")], status="draft")  # préparée, jamais envoyée : exclue
        self.job("deepl", 500, [Decimal("5")], months_ago=1)  # mois précédent
        AITask.objects.create(user=self.owner, function="translation", provider="openai", model="ancien",
                              status="done", tokens_in=10, tokens_out=20, cost_estimate=Decimal("0.02"))
        data = U.monthly_usage(self.owner, timezone.localdate().replace(day=1))
        rows = {r["label"]: r for r in data["rows"]}
        self.assertEqual((rows["DeepL"]["jobs"], rows["DeepL"]["chars"], rows["DeepL"]["translations"]), (2, 400, 3))
        self.assertEqual(rows["DeepL"]["costs"], {"EUR": Decimal("0.006")})
        ai = next(r for r in data["rows"] if r["code"] == "ai")
        self.assertEqual((ai["chars"], ai["tokens_in"], ai["tokens_out"], ai["costs"]),
                         (120, 50, 80, {"USD": Decimal("0.010")}))
        self.assertEqual(rows["Argos Translate (local)"]["costs"], {})
        self.assertEqual(data["legacy"]["tasks"], 1)  # ancienne traduction du module IA, comptée à part
        self.assertEqual(data["totals"], {"EUR": Decimal("0.006"), "USD": Decimal("0.030")})
        self.assertEqual(data["chars"], 520)
        self.assertEqual(data["chars"], sum(d["job"].chars_sent for d in data["detail"]))
        previous = U.monthly_usage(self.owner, (timezone.localdate().replace(day=1) - timedelta(days=1)).replace(day=1))
        self.assertEqual(previous["chars"], 500)

    def test_page_presents_estimates_and_caps(self):
        EngineSetting.objects.filter(user=self.owner, engine="deepl").update(monthly_char_cap=1000)
        self.job("deepl", 400, [Decimal("0.004")])
        page = self.client.get("/traduction/consommation/")
        self.assertContains(page, "Les montants sont des estimations ; la facture du fournisseur fait foi.")
        self.assertContains(page, "DeepL : 400 / 1000 caractères")
        self.assertContains(page, "≈ 0,0040 EUR")
        self.assertContains(self.client.get("/traduction/"), 'href="/traduction/consommation/"')

    def test_usage_is_personal(self):
        self.job("deepl", 300, [Decimal("0.003")])
        other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        self.assertEqual(U.monthly_usage(other, timezone.localdate().replace(day=1))["rows"], [])

    def test_real_pipeline_counts_sent_characters(self):
        document = P.create_document(self.project, title="Doc", text="一つ目の文。二つ目の文。")
        job = self.translate_all(document)
        data = U.monthly_usage(self.owner, timezone.localdate().replace(day=1))
        self.assertEqual(data["chars"], job.chars_sent)
        self.assertEqual(data["chars"], len("一つ目の文。二つ目の文。"))
        self.assertEqual(data["translations"], 2)


# --------------------------------------------------------------------------- évaluation


class EvaluationTests(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.corpus = TranslationProject.objects.create(owner=self.owner, title="Corpus fictif", is_reference_corpus=True)
        self.document = P.create_document(self.corpus, title="Phrases fictives", text=CORPUS)
        first = self.document.segments.order_by("position").first()
        P.validate_version(P.add_human_version(first, self.owner, "La ville d'Edo."), self.owner)

    def prepare(self, *engines, follow=False, **extra):
        return self.client.post(f"/traduction/evaluation/{self.corpus.pk}/comparer/", {"engines": list(engines), **extra},
                                follow=follow)

    def test_prepare_sends_nothing_and_includes_validated_segments(self):
        response = self.prepare("deepl", "argos")
        jobs = list(TranslationJob.objects.filter(kind="evaluation").order_by("pk"))
        self.assertEqual([j.engine for j in jobs], ["deepl", "argos"])
        self.assertEqual({j.status for j in jobs}, {"draft"})
        self.assertEqual([j.items.filter(status="pending").count() for j in jobs], [2, 2])  # validé compris
        self.assertEqual(self.sent, [])
        page = self.client.get(response["Location"])
        self.assertContains(page, "Confirmation du coût — rien n'a encore été envoyé")
        self.assertContains(page, "la facture du fournisseur fait foi")
        self.assertContains(page, "gratuit (moteur local)")

    def test_confirm_translates_with_each_engine_and_keeps_dated_results(self):
        location = self.prepare("deepl", "argos")["Location"]
        label = TranslationJob.objects.filter(kind="evaluation").first().scope_label
        self.assertTrue(label.startswith("Comparaison du "))
        self.client.post(f"/traduction/evaluation/{self.corpus.pk}/comparaison/action/", {"c": label, "action": "confirm"})
        jobs = E.comparison_jobs(self.owner, self.corpus, label)
        self.assertEqual([j.status for j in jobs], ["done", "done"])
        self.assertEqual([t.strip() for t in self.sent], ["江戸の町。", "武士の道。"])
        rows = E.rows(jobs)
        self.assertEqual(len(rows), 2)
        deepl, argos = rows[0][1]
        self.assertEqual(deepl.version.text, "FR 江戸の町。")
        self.assertTrue(argos.version.simulated)
        # la version validée existante reste validée ; les résultats sont des propositions datées
        self.assertEqual(self.document.segments.order_by("position").first().versions.get(status="validated").text,
                         "La ville d'Edo.")
        page = self.client.get(location)
        self.assertContains(page, "FR 江戸の町。")
        self.assertContains(page, "Simulation")
        self.assertContains(page, "Aucun score automatique")

    def test_human_rating_and_summary(self):
        self.prepare("deepl")
        job = TranslationJob.objects.get(kind="evaluation")
        self.client.post(f"/traduction/evaluation/{self.corpus.pk}/comparaison/action/",
                         {"c": job.scope_label, "action": "confirm"})
        first, second = [i.version for i in job.items.order_by("position")]
        self.client.post(f"/traduction/versions/{first.pk}/note/", {"rating": "correct", "comment": "bien"})
        self.client.post(f"/traduction/versions/{second.pk}/note/", {"rating": "misreading"})
        first.refresh_from_db()
        self.assertEqual((first.rating, first.rating_comment), ("correct", "bien"))
        summary = E.rating_summary([job])[0]
        self.assertEqual(dict((c, n) for c, _, n in summary["counts"]),
                         {"correct": 1, "acceptable": 0, "faulty": 0, "misreading": 1})
        self.assertEqual(summary["unrated"], 0)
        with self.assertRaises(E.EvaluationError):
            E.rate(first, self.owner, "excellent", "")
        other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        self.client.force_login(other)
        self.assertEqual(self.client.post(f"/traduction/versions/{first.pk}/note/", {"rating": "faulty"}).status_code, 404)

    def test_second_confirmation_and_cancel(self):
        pref = TranslationPreference.objects.get(user=self.owner)
        pref.confirmation_threshold = 1
        pref.save()
        self.prepare("deepl")
        job = TranslationJob.objects.get(kind="evaluation")
        self.assertTrue(job.requires_second_confirmation)
        response = self.client.post(f"/traduction/evaluation/{self.corpus.pk}/comparaison/action/",
                                    {"c": job.scope_label, "action": "confirm"}, follow=True)
        self.assertContains(response, "seconde confirmation")
        job.refresh_from_db()
        self.assertEqual(job.status, "draft")
        self.client.post(f"/traduction/evaluation/{self.corpus.pk}/comparaison/action/",
                         {"c": job.scope_label, "action": "cancel"})
        job.refresh_from_db()
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(self.sent, [])

    def test_confidential_corpus_keeps_local_engines_only(self):
        self.corpus.confidential = True
        self.corpus.save()
        response = self.prepare("deepl", "argos", follow=True)
        self.assertContains(response, "écarté")
        self.assertEqual([j.engine for j in TranslationJob.objects.filter(kind="evaluation")], ["argos"])

    def test_refusals(self):
        self.corpus.is_reference_corpus = False
        self.corpus.save()
        self.assertEqual(self.prepare("deepl").status_code, 404)
        with self.assertRaises(E.EvaluationError):
            E.prepare_comparison(self.owner, self.corpus, [services.EngineChoice("deepl")])
        self.corpus.is_reference_corpus = True
        self.corpus.save()
        with self.assertRaisesMessage(E.EvaluationError, "au moins un moteur"):
            E.prepare_comparison(self.owner, self.corpus, [])
        other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        self.client.force_login(other)
        self.assertEqual(self.prepare("deepl").status_code, 404)

    def test_no_second_engine_proposal_for_comparisons(self):
        self.prepare("deepl")
        job = TranslationJob.objects.get(kind="evaluation")
        with self.assertRaises(services.TranslationUnavailable):
            services.propose_second_engine(job, self.owner)

    def test_home_lists_corpora_and_comparisons(self):
        self.prepare("argos")
        page = self.client.get("/traduction/evaluation/")
        self.assertContains(page, "Corpus fictif")
        self.assertContains(page, "à confirmer")
        self.assertContains(page, "aucun texte confidentiel")
