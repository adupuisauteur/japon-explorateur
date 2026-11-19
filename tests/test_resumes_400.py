"""2.0.0 — lot 4 : résumés IA (types, langue, découpage et synthèse, reprise, file, écrans) et textes anciens.

Fournisseur IA simulé (aucun réseau) ; textes fictifs ; Celery en mode immédiat.
"""
import json
from datetime import time, timedelta
from decimal import Decimal
from unittest import mock

from django.utils import timezone

from apps.ai.crypto import encrypt_secret
from apps.ai.models import AIModelPrice, AIProviderCredential, AITask, Summary
from apps.ai.providers import Completion, ProviderError
from apps.catalog.models import Catalogue, Record
from apps.notifications.models import Notification
from apps.translation import queue as Q
from apps.translation import services
from apps.translation import summaries as S
from apps.translation import variety as V
from apps.translation.models import (RecordVariety, TranslationDocument, TranslationJob, TranslationPreference,
                                     TranslationProject)

from .helpers import AppTestCase

MODERN = "架空の説明。江戸時代の地図を集めた資料で、各地の街道が描かれている。図版は多色刷りである。"
BUNGO = "昔、男ありけり。京にすみわびて、東の方に住むべき国求めにとて行きけり。その男、身をえうなきものに思ひなして。"
KANBUN = "学而時習之不亦説乎有朋自遠方来不亦楽乎人不知而不慍不亦君子乎其為人也孝弟而好犯上者鮮矣"
SORO = "一筆啓上致し候。先日は御世話に相成り候段、忝く存じ候。早々申し上げ候。"


class StubProvider:
    """Répond un JSON de résumé ; garde chaque consigne reçue ; peut échouer à la demande."""

    def __init__(self, fail_at=None, kind="technical"):
        self.prompts, self.fail_at, self.kind = [], fail_at, kind

    def complete(self, system, prompt, model, max_tokens=2000):
        self.prompts.append(prompt)
        if self.fail_at is not None and len(self.prompts) == self.fail_at:
            raise ProviderError("Service momentanément injoignable (simulation).", kind=self.kind)
        n = len(self.prompts)
        data = {"summary": f"Résumé fictif n° {n}.", "limits": "Texte fictif."}
        if "fiche d'analyse" in prompt:
            data.update(themes=["cartographie"], persons=[{"name": "架空太郎", "note": "auteur fictif"}],
                        places=[{"name": "江戸", "note": "Edo"}], dates=[{"date": "1800", "note": "copie"}])
        return Completion("<think>raisonnement</think>" + json.dumps(data, ensure_ascii=False), 120, 40, model)


class SummaryCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.researcher
        AIProviderCredential.objects.create(user=self.user, provider="openai", status="ok",
                                            encrypted_key=encrypt_secret("sk-fictif-0123456789abcdef"))
        pref = services.ensure_preference(self.user)
        pref.summary_provider, pref.summary_model = "openai", "gpt-fictif"
        pref.save()
        AIModelPrice.objects.create(provider="openai", model_prefix="gpt-fictif", input_per_million=1,
                                    output_per_million=2)
        self.cat = Catalogue.objects.get(code="codh-pmjt")
        self.record = Record.objects.create(catalogue=self.cat, source_id="lot4-1", original_title="架空の地図帳",
                                            description_original=MODERN)
        from apps.translation import terms

        for key in ("ai:openai", "ai:anthropic"):  # conditions des fournisseurs déjà lues
            terms.acknowledge(self.user, key)
        self.stub = StubProvider()
        patcher = mock.patch("apps.translation.summaries.get_provider", side_effect=lambda cred: self.stub)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_login(self.user)

    def run_summary(self, **kwargs):
        jobs = S.prepare(self.user, **kwargs)
        services.confirm(jobs[0], self.user)
        for job in jobs:
            job.refresh_from_db()
        return jobs

    def document(self, text, project=None):
        project = project or TranslationProject.objects.create(owner=self.user, title="Projet fictif")
        return TranslationDocument.objects.create(project=project, title="Document fictif", original_text=text)


class PrepareAndRunTests(SummaryCase):
    def test_record_summary_end_to_end(self):
        (job,) = self.run_summary(records=[self.record])
        self.assertEqual((job.kind, job.status, job.done_items), ("summary", "done", 1))
        summary = Summary.objects.get()
        self.assertEqual((summary.kind, summary.language, summary.source_kind), ("court", "fr", "record_original"))
        self.assertEqual(summary.content, "Résumé fictif n° 1.")  # bloc <think> retiré
        self.assertIn("Rédige en français un résumé court", self.stub.prompts[0])
        self.assertIn(MODERN, self.stub.prompts[0])  # l'original japonais est lu
        task = AITask.objects.get(function="summary")
        self.assertEqual((task.tokens_in, task.tokens_out, task.parameters["job"]), (120, 40, job.pk))
        self.assertGreater(task.cost_estimate, 0)
        self.assertTrue(Notification.objects.filter(recipient=self.user, title__startswith="Résumés prêts").exists())
        # nouvelle demande : nouvelle version, l'ancienne est gardée
        self.run_summary(records=[self.record])
        latest = Summary.objects.order_by("-created_at").first()
        self.assertEqual(latest.previous, summary)
        self.assertEqual(latest.history(), [summary])

    def test_analysis_and_language(self):
        self.run_summary(records=[self.record], kind="analyse", language="en")
        summary = Summary.objects.get()
        self.assertEqual(summary.language, "en")
        self.assertEqual(summary.data["themes"], ["cartographie"])
        self.assertEqual(summary.data["places"][0]["name"], "江戸")
        self.assertIn("Rédige en anglais une fiche d'analyse", self.stub.prompts[0])

    def test_long_document_parts_then_synthesis_and_resume_without_resending(self):
        text = "\n".join(f"第{i}段。" + "架空の記述である。" * 60 for i in range(30))  # environ 17 000 caractères
        document = self.document(text)
        parts = S.split_parts(text, S.PART_CHARS)
        self.assertGreater(len(parts), 2)
        self.assertEqual("".join(p.replace("\n", "") for p in parts), text.replace("\n", ""))
        jobs = S.prepare(self.user, documents=[document], kind="detaille")
        self.assertEqual(jobs[0].options["calls"], len(parts) + 1)
        self.stub.fail_at, self.stub.kind = 2, "unavailable"  # coupure au deuxième appel
        services.confirm(jobs[0], self.user)
        job = TranslationJob.objects.get(pk=jobs[0].pk)
        self.assertEqual(job.status, "interrupted")
        self.assertEqual(len(job.items.get().data["partials"]), 1)
        self.stub.fail_at = None
        services.resume(job, self.user)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        # 1 réussi + 1 échoué + (parties restantes) + synthèse : la première partie n'a jamais été renvoyée
        self.assertEqual(len(self.stub.prompts), len(parts) + 2)
        self.assertEqual(sum(1 for p in self.stub.prompts if parts[0][:50] in p), 1)
        self.assertIn("À partir des résumés des parties", self.stub.prompts[-1])
        summary = Summary.objects.get()
        self.assertEqual((summary.document, summary.calls, summary.source_kind), (document, len(parts) + 1,
                                                                                  "document_original"))

    def test_translation_source_is_marked(self):
        document = self.document("一つ目の文。二つ目の文。")
        jobs = S.prepare(self.user, documents=[document], source="translation")
        self.assertEqual(jobs[0].options["source"], "translation")
        text, kind = S.document_text(document, "translation")
        self.assertEqual(kind, "document_original")  # aucune traduction : l'original est lu

    def test_problems(self):
        pref = TranslationPreference.objects.get(user=self.user)
        pref.summary_provider, pref.summary_model = "anthropic", "claude-fictif"
        pref.save()
        (job,) = S.prepare(self.user, records=[self.record])
        self.assertIn("Aucune clé enregistrée pour Anthropic", " ".join(S.problems(job)))
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        with self.assertRaises(S.SummaryUnavailable):
            S.prepare(self.user)

    def test_budget_checked_before_each_call(self):
        from apps.ai.preferences import active_profile

        profile = active_profile(self.user)
        profile.monthly_budget = Decimal("0.01")
        profile.save()
        text = "\n".join("架空の記述である。" * 100 for _ in range(10))
        jobs = S.prepare(self.user, documents=[self.document(text)])
        TranslationJob.objects.filter(pk=jobs[0].pk).update(status="running", started_at=timezone.now())
        AITask.objects.create(user=self.user, function="summary", provider="openai", model="gpt-fictif",
                              status="done", cost_estimate=Decimal("0.0099"))
        services.process_next_chunk(jobs[0].pk)
        job = TranslationJob.objects.get(pk=jobs[0].pk)
        self.assertEqual((job.status, job.pause_reason), ("paused", "cap"))
        self.assertEqual(self.stub.prompts, [])


class NowAndQueueTests(SummaryCase):
    def test_now_needs_confirmation_unless_threshold(self):
        response = self.client.post("/traduction/resumes/demander/", {"records": self.record.record_id, "mode": "now",
                                                                       "next": self.record.get_absolute_url()})
        job = TranslationJob.objects.get(kind="summary")
        self.assertRedirects(response, f"/traduction/taches/{job.pk}/", fetch_redirect_response=False)
        page = self.client.get(f"/traduction/taches/{job.pk}/").content.decode()
        self.assertIn("généré par IA", page)
        self.assertIn("1 appel(s)", page)
        TranslationPreference.objects.filter(user=self.user).update(confirm_below=Decimal("1"))
        response = self.client.post("/traduction/resumes/demander/", {"records": self.record.record_id, "mode": "now",
                                                                       "next": self.record.get_absolute_url()})
        self.assertRedirects(response, self.record.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(Summary.objects.count(), 1)
        page = self.client.get(self.record.get_absolute_url()).content.decode()
        self.assertIn("Résumé fictif n° 1.", page)
        self.assertIn("Résumer maintenant", page)

    def test_night_queue(self):
        pref = TranslationPreference.objects.get(user=self.user)
        pref.night_start, pref.night_end = time(22), time(7)
        pref.save()
        response = self.client.post("/traduction/resumes/demander/", {"records": self.record.record_id,
                                                                       "mode": "night"})
        job = TranslationJob.objects.get(kind="summary")
        self.assertRedirects(response, f"/traduction/taches/{job.pk}/?lancement=nuit", fetch_redirect_response=False)
        services.confirm(job, self.user, launch="night")
        job.refresh_from_db()
        self.assertEqual((job.status, job.launch), ("scheduled", "night"))
        self.assertEqual(Q.queue_for(job), "traduction")

    def test_library_and_workbench_and_reader(self):
        from apps.library.models import LibraryEntry

        entry = LibraryEntry.objects.create(user=self.user, record=self.record)
        page = self.client.get("/bibliotheque/").content.decode()
        self.assertIn('value="summarize_now"', page)
        TranslationPreference.objects.filter(user=self.user).update(confirm_below=Decimal("1"))
        self.client.post("/bibliotheque/lot/", {"action": "summarize_now", "entry_ids": [entry.pk]})
        self.assertEqual(Summary.objects.count(), 1)
        document = self.document(MODERN)
        page = self.client.get(f"/traduction/documents/{document.pk}/").content.decode()
        self.assertIn('name="documents" value="%d"' % document.pk, page)
        self.client.force_login(self.reader)
        response = self.client.post("/traduction/resumes/demander/", {"records": self.record.record_id})
        self.assertEqual(response.status_code, 403)

    def test_confidential_document_summary_is_private(self):
        secret = TranslationProject.objects.create(owner=self.user, title="Secret fictif", confidential=True)
        document = self.document(MODERN, project=secret)
        (job,) = S.prepare(self.user, documents=[document])
        self.assertIn("Projet confidentiel", " ".join(S.problems(job)))  # IA en ligne refusée
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        self.assertEqual(self.stub.prompts, [])
        # par l'IA locale : permis ; le résumé reste privé
        with mock.patch("apps.ai.local.service_problem", return_value=""):
            TranslationPreference.objects.filter(user=self.user).update(summary_provider="ollama",
                                                                        summary_model="qwen3:4b")
            self.run_summary(documents=[document])
        summary = Summary.objects.get()
        self.assertEqual(summary.provider, "ollama")
        self.assertEqual(self.client.get(f"/traduction/resumes/{summary.pk}/").status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/traduction/resumes/{summary.pk}/").status_code, 403)
        self.assertNotIn("Secret fictif", self.client.get("/traduction/resumes/").content.decode())


class AncientTests(SummaryCase):
    def test_detection(self):
        self.assertEqual(V.detect(MODERN)[0], "modern")
        variety, reasons = V.detect(BUNGO)
        self.assertEqual(variety, "classical")
        self.assertIn("けり", reasons[0])
        self.assertEqual(V.detect(KANBUN)[0], "kanbun")
        self.assertEqual(V.detect("学ビテ時ニ之ヲ習フ。㆑")[0], "modern")  # trop court
        self.assertEqual(V.detect("学而時習之、不亦説乎。㆑ 有朋自遠方来、不亦楽乎。")[0], "kanbun")
        variety, reasons = V.detect(SORO)
        self.assertEqual(variety, "classical")
        self.assertIn("候", reasons[0])
        self.assertEqual(V.detect("架空の書名")[0], "modern")

    def test_record_annotation_is_a_suggestion_until_confirmed(self):
        old = Record.objects.create(catalogue=self.cat, source_id="lot4-bungo", original_title="架空物語",
                                    description_original=BUNGO)
        page = self.client.get(old.get_absolute_url()).content.decode()
        self.assertIn("Japonais classique (bungo) — probable", page)
        self.client.post(f"/traduction/notices/{old.record_id}/variete/", {"variety": "modern"})
        annotation = RecordVariety.objects.get(record=old)
        self.assertEqual((annotation.variety, annotation.origin), ("modern", "user"))
        self.assertEqual(V.variety_of_record(Record.objects.get(pk=old.pk)), "modern")
        V.annotate_record(old)  # un nouveau repérage ne remplace jamais une confirmation
        self.assertEqual(RecordVariety.objects.get(record=old).origin, "user")

    def test_ancient_texts_go_to_the_chosen_ai_in_a_sibling_job(self):
        AIProviderCredential.objects.create(user=self.user, provider="anthropic", status="ok",
                                            encrypted_key=encrypt_secret("sk-ant-fictif-0123456789"))
        pref = TranslationPreference.objects.get(user=self.user)
        pref.summary_ancient_provider, pref.summary_ancient_model = "anthropic", "claude-fictif"
        pref.save()
        old = Record.objects.create(catalogue=self.cat, source_id="lot4-bungo", original_title="架空物語",
                                    description_original=BUNGO)
        jobs = S.prepare(self.user, records=[self.record, old])
        self.assertEqual(len(jobs), 2)
        modern, ancient = jobs
        self.assertEqual((modern.ai_provider, ancient.ai_provider), ("openai", "anthropic"))
        self.assertTrue(ancient.options["ancient"])
        self.assertEqual(modern.options["sibling"], ancient.pk)
        page = self.client.get(f"/traduction/taches/{modern.pk}/").content.decode()
        self.assertIn("Japonais ancien", page)
        self.assertIn("Japonais moderne", page)
        services.confirm(modern, self.user)
        ancient.refresh_from_db()
        self.assertEqual(ancient.status, "done")  # confirmée avec la première
        self.assertIn("japonais classique (bungo)", self.stub.prompts[-1])
        # annuler une partie préparée annule l'autre
        jobs = S.prepare(self.user, records=[self.record, old])
        services.cancel(jobs[0], self.user)
        jobs[1].refresh_from_db()
        self.assertEqual(jobs[1].status, "cancelled")


class ExportTests(SummaryCase):
    def export(self, **extra):
        from pathlib import Path

        from django.conf import settings

        from apps.exports.models import ExportJob

        self.client.post("/exports/preparer/", {"scope": "selection", "records": self.record.record_id,
                                                "preset": "bibliography", "format": "json", "title": "Résumés",
                                                "column_profile": "bibliography", "csv_separator": "semicolon",
                                                **extra})
        job = ExportJob.objects.latest("pk")
        self.assertEqual(job.status, "done", job.error)
        return json.loads((Path(settings.MEDIA_ROOT) / job.files.get(role="main").path).read_text(encoding="utf-8"))

    def editorial(self, data):
        records = data.get("records") or [r for s in data.get("sections", []) for r in s.get("records", [])]
        return [e for r in records for e in r["editorial"]]

    def test_summaries_only_when_asked_and_marked(self):
        self.run_summary(records=[self.record])
        self.assertEqual([e for e in self.editorial(self.export()) if e["kind_code"] == "ai_summary"], [])
        self.assertEqual([e for e in self.editorial(self.export(include_summaries="on")) if e["kind_code"] == "ai_summary"],
                         [])  # contenus générés exclus : résumés exclus aussi
        data = self.export(include_summaries="on", include_ai="on")
        (entry,) = [e for e in self.editorial(data) if e["kind_code"] == "ai_summary"]
        self.assertEqual((entry["origin"], entry["status"]), ("Généré par IA", "Non vérifié"))
        self.assertIn("Résumé fictif n° 1.", entry["content"])
        self.assertTrue(data["export_metadata"]["ai_summaries_included"])


class ChainTests(SummaryCase):
    """U9 : résumer juste après chaque traduction, ou après l'ensemble des traductions."""

    def setUp(self):
        super().setUp()
        import httpx

        from apps.translation.engines.deepl import DeepLEngine
        from apps.translation.models import EngineSetting

        from .test_translation_pipeline import DeepLStub

        EngineSetting.objects.create(user=self.user, engine="deepl", plan="free", status="ok",
                                     encrypted_key=encrypt_secret("fake-deepl-key-0000000000"))
        DeepLEngine.transport = httpx.MockTransport(DeepLStub())
        self.addCleanup(setattr, DeepLEngine, "transport", None)
        from apps.translation import terms

        terms.acknowledge(self.user, "deepl")

    def translation_job(self, record):
        return services.prepare_records_job(self.user, [record], ["description_original"],
                                            choice=services.EngineChoice("deepl"))

    def confirm(self, job, **extra):
        return self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm", "then_summary": "1",
                                                                         "summary_kind": "court",
                                                                         "summary_language": "fr", **extra})

    def test_offer_on_confirmation_screen(self):
        job = self.translation_job(self.record)
        page = self.client.get(f"/traduction/taches/{job.pk}/").content.decode()
        self.assertIn("Résumer aussi 1 notice(s) ou document(s) avec OpenAI", page)
        self.assertIn("juste après chaque traduction", page)

    def test_immediate_translation_then_summary(self):
        job = self.translation_job(self.record)
        with self.captureOnCommitCallbacks(execute=True):
            self.confirm(job, summary_mode="each")
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        summary_job = TranslationJob.objects.get(kind="summary")
        self.assertEqual((summary_job.status, summary_job.options["after_job"]), ("done", job.pk))
        self.assertEqual(Summary.objects.get().record, self.record)

    def test_summary_problem_blocks_everything(self):
        TranslationPreference.objects.filter(user=self.user).update(summary_provider="anthropic",
                                                                    summary_model="claude-fictif")
        job = self.translation_job(self.record)
        response = self.client.post(f"/traduction/taches/{job.pk}/action/", {
            "action": "confirm", "then_summary": "1", "summary_kind": "court", "summary_mode": "each"}, follow=True)
        job.refresh_from_db()
        self.assertEqual(job.status, "draft")  # rien n'est parti
        self.assertFalse(TranslationJob.objects.filter(kind="summary").exists())
        self.assertContains(response, "Résumés : Aucune clé enregistrée pour Anthropic")

    def test_night_each_and_all_ordering(self):
        pref = TranslationPreference.objects.get(user=self.user)
        pref.night_start, pref.night_end = time(22), time(7)
        pref.save()
        other = Record.objects.create(catalogue=self.cat, source_id="lot4-2", original_title="架空二",
                                      description_original=MODERN)
        first, second = self.translation_job(self.record), self.translation_job(other)
        self.confirm(first, launch="night", summary_mode="all")
        self.client.post(f"/traduction/taches/{second.pk}/action/", {"action": "confirm", "launch": "night"})
        summary_job = TranslationJob.objects.get(launch="night", kind="summary")
        self.assertTrue(summary_job.options["after_all"])
        jobs = [None, summary_job]
        # la nuit : les deux traductions d'abord, puis le résumé
        started = []
        for minute in range(4):
            with mock.patch("django.utils.timezone.now", return_value=_at(0, 22, minute)), \
                    self.captureOnCommitCallbacks(execute=True):
                started += Q.clock(_at(0, 22, minute))["started"]
        self.assertEqual(started, [first.pk, second.pk, jobs[1].pk])

    def test_each_at_night_is_placed_right_after(self):
        pref = TranslationPreference.objects.get(user=self.user)
        pref.night_start, pref.night_end = time(22), time(7)
        pref.save()
        other = Record.objects.create(catalogue=self.cat, source_id="lot4-3", original_title="架空三",
                                      description_original=MODERN)
        first, second = self.translation_job(self.record), self.translation_job(other)
        self.client.post(f"/traduction/taches/{first.pk}/action/", {"action": "confirm", "launch": "night"})
        self.client.post(f"/traduction/taches/{second.pk}/action/", {"action": "confirm", "launch": "night"})
        first.refresh_from_db()
        S.chain(first, self.user, kind="court", language="fr", mode="each", launch="night")
        order = list(TranslationJob.objects.filter(launch="night").order_by("queue_position")
                     .values_list("kind", "pk"))
        self.assertEqual([k for k, _ in order], ["records", "summary", "records"])
        self.assertEqual(order[0][1], first.pk)

    def test_local_pair_forces_all(self):
        job = TranslationJob(engine="argos")
        self.assertTrue(S.forced_all(job, "ollama"))
        self.assertFalse(S.forced_all(job, "openai"))

    def test_cancelled_translation_cancels_its_summaries(self):
        job = self.translation_job(self.record)
        services.confirm(job, self.user, launch="scheduled", scheduled_for=timezone.now() + timedelta(hours=2))
        (summary_job,) = S.chain(job, self.user, kind="court", language="fr", mode="each", launch="scheduled")
        self.assertEqual((summary_job.status, summary_job.launch), ("scheduled", "after"))
        services.cancel(job, self.user)
        summary_job.refresh_from_db()
        self.assertEqual(summary_job.status, "cancelled")


def _at(day, hour, minute=0):
    from datetime import datetime

    return timezone.make_aware(datetime(2026, 11, 16 + day, hour, minute), timezone.get_current_timezone())


class FakeOllama:
    """Faux service Ollama : /api/version, /api/tags, /api/pull (en flux), /api/delete."""

    def __init__(self, models=()):
        self.models, self.pulls, self.cut_pull = list(models), [], False

    def __call__(self, request):
        import httpx

        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": "0.30.9"})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m, "size": 2_500_000_000} for m in self.models]})
        if path == "/api/pull":
            model = json.loads(request.content)["model"]
            self.pulls.append(model)
            lines = [{"status": "pulling manifest"}, {"status": "pulling abc", "total": 100, "completed": 40}]
            if self.cut_pull:
                self.cut_pull = False
                lines.append({"error": "connexion coupée (simulation)"})
            else:
                lines += [{"status": "pulling abc", "total": 100, "completed": 100}, {"status": "success"}]
                self.models.append(model)
            return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines).encode())
        if path == "/api/delete":
            self.models.remove(json.loads(request.content)["model"])
            return httpx.Response(200)
        return httpx.Response(404)


class LocalAITests(AppTestCase):
    def setUp(self):
        import os

        import httpx

        super().setUp()
        self.fake = FakeOllama()
        overrides = self.settings(OLLAMA_URL="http://ollama:11434", OLLAMA_TRANSPORT=httpx.MockTransport(self.fake))
        overrides.enable()
        self.addCleanup(overrides.disable)
        env = mock.patch.dict(os.environ, {"COMPOSE_PROFILES": "argos,ollama"})
        env.start()
        self.addCleanup(env.stop)
        self.client.force_login(self.admin)

    def test_not_installed_when_profile_absent(self):
        import os

        from apps.ai import local
        from apps.core.health import check_local_ai

        with mock.patch.dict(os.environ, {"COMPOSE_PROFILES": "argos"}):
            self.assertEqual(local.base_url(), "")
            self.assertIsNone(check_local_ai())
            page = self.client.get("/traduction/moteurs/locaux/").content.decode()
            self.assertIn("Non installée", page)
            self.assertIn("COMPOSE_PROFILES=argos,ollama", page)

    def test_install_is_tracked_then_tested(self):
        from apps.ai import local
        from apps.core.health import check_local_ai

        page = self.client.get("/traduction/moteurs/locaux/").content.decode()
        self.assertIn("En service", page)
        self.assertIn("télécharger 2,5 Go depuis Internet", page)
        self.assertEqual(check_local_ai().summary, "En service, mais aucun modèle installé")
        self.client.post("/traduction/moteurs/locaux/ia/installer/", {"model": "qwen3:4b"})
        self.assertEqual(self.fake.pulls, [])  # sans confirmation : rien n'est téléchargé
        self.client.post("/traduction/moteurs/locaux/ia/installer/", {"model": "inconnu:1b", "confirm": "1"})
        self.assertEqual(self.fake.pulls, [])
        stub = StubProvider()
        with mock.patch("apps.ai.providers.get_provider", return_value=stub):
            self.client.post("/traduction/moteurs/locaux/ia/installer/", {"model": "qwen3:4b", "confirm": "1"})
        job = TranslationJob.objects.get(kind="package")
        self.assertEqual((job.status, job.ai_model), ("done", "qwen3:4b"))
        self.assertEqual(job.items.get().error_message, "Modèle qwen3:4b installé.")
        self.assertEqual(self.fake.pulls, ["qwen3:4b"])
        check = local.last_selftest()
        self.assertTrue(check.ok)
        self.assertEqual(check.data["summary"], "Résumé fictif n° 1.")
        self.assertIn("/no_think", stub.prompts[0])
        self.assertTrue(Notification.objects.filter(recipient=self.admin, title__startswith="Terminé : IA locale")
                        .exists())
        self.assertEqual(check_local_ai().summary, "Prête")
        page = self.client.get("/traduction/moteurs/locaux/").content.decode()
        self.assertIn("résumé d'un texte fictif", page)

    def test_cut_download_is_resumed(self):
        from apps.translation import argos_packages as A

        self.fake.cut_pull = True
        with mock.patch("apps.ai.providers.get_provider", return_value=StubProvider()):
            self.client.post("/traduction/moteurs/locaux/ia/installer/", {"model": "qwen3:1.7b", "confirm": "1"})
            job = TranslationJob.objects.get(kind="package")
            self.assertEqual(job.status, "failed")
            self.assertIn("connexion coupée", job.items.get().error_message)
            A.relaunch(job)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(self.fake.pulls, ["qwen3:1.7b", "qwen3:1.7b"])

    def test_researcher_cannot_install_and_remove_needs_confirmation(self):
        self.fake.models = ["qwen3:4b"]
        self.client.post("/traduction/moteurs/locaux/ia/supprimer/", {"model": "qwen3:4b"})
        self.assertEqual(self.fake.models, ["qwen3:4b"])
        self.client.post("/traduction/moteurs/locaux/ia/supprimer/", {"model": "qwen3:4b", "confirm": "1"})
        self.assertEqual(self.fake.models, [])
        self.client.force_login(self.researcher)
        response = self.client.post("/traduction/moteurs/locaux/ia/installer/", {"model": "qwen3:4b", "confirm": "1"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.fake.pulls, [])

    def test_picker_and_providers_page(self):
        self.fake.models = ["qwen3:4b"]
        page = self.client.get("/ia/modeles/choix/", {"provider_field": "summary_provider", "model_field": "summary_model",
                                               "summary_provider": "ollama"}).content.decode()
        self.assertIn("qwen3:4b", page)
        self.assertIn("gratuit, sur cet ordinateur", page)
        self.assertNotIn("IA locale (Ollama", self.client.get("/ia/fournisseurs/").content.decode())

    def test_local_summary_is_free_and_smaller_parts(self):
        from apps.translation import terms

        self.fake.models = ["qwen3:4b"]
        self.assertEqual(S.part_size("ollama"), 3000)
        est = S.estimate("ollama", "qwen3:4b", ["架空" * 2000], "court")
        self.assertEqual(est["amount"], Decimal("0"))
        self.assertGreaterEqual(est["calls"], 3)
        self.assertIsNone(terms.needed(self.admin, "ai", "ollama"))


class AncientTranslationTests(SummaryCase):
    """U10 : « Pour le japonais ancien, utiliser… » — tâche mixte en deux parties, confirmées ensemble."""

    def setUp(self):
        super().setUp()
        import httpx

        from apps.translation.engines.deepl import DeepLEngine
        from apps.translation.models import EngineSetting

        from .test_translation_pipeline import DeepLStub

        EngineSetting.objects.create(user=self.user, engine="deepl", plan="free", status="ok",
                                     encrypted_key=encrypt_secret("fake-deepl-key-0000000000"))
        self.deepl = DeepLStub()
        DeepLEngine.transport = httpx.MockTransport(self.deepl)
        self.addCleanup(setattr, DeepLEngine, "transport", None)
        from apps.translation import terms

        terms.acknowledge(self.user, "deepl")
        self.old = Record.objects.create(catalogue=self.cat, source_id="lot4-old", original_title="架空物語",
                                         description_original=BUNGO)

    def prepare(self, records):
        return services.prepare_records_job(self.user, records, ["description_original"],
                                            choice=services.EngineChoice("deepl"))

    def test_without_setting_nothing_changes(self):
        job = self.prepare([self.record, self.old])
        self.assertEqual((job.engine, job.total_items, services.job_siblings(job)), ("deepl", 2, []))

    def test_mixed_job_has_two_parts_confirmed_together(self):
        TranslationPreference.objects.filter(user=self.user).update(
            ancient_engine="ai", ancient_ai_provider="openai", ancient_ai_model="gpt-fictif")
        job = self.prepare([self.record, self.old])
        (sister,) = services.job_siblings(job)
        self.assertEqual((job.engine, job.total_items), ("deepl", 1))
        self.assertEqual((sister.engine, sister.ai_provider, sister.total_items), ("ai", "openai", 1))
        self.assertTrue(sister.options["ancient"])
        self.assertEqual(sister.items.get().record, self.old)
        page = self.client.get(f"/traduction/taches/{job.pk}/").content.decode()
        self.assertIn("Tâche en deux parties", page)
        self.assertIn("Japonais ancien</strong> : 1 élément(s), 54 caractère(s) → OpenAI — gpt-fictif", page)
        self.assertIn("Résumer aussi 2 notice(s)", page)
        # la partie ancienne est bloquée (pas de clé) : rien ne part, ni l'une ni l'autre
        AIProviderCredential.objects.filter(user=self.user, provider="openai").delete()
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        job.refresh_from_db()
        self.assertEqual(job.status, "draft")
        self.assertEqual(self.deepl.texts, [])

    def test_confirmed_together_and_ai_receives_the_classical_note(self):
        TranslationPreference.objects.filter(user=self.user).update(
            ancient_engine="ai", ancient_ai_provider="openai", ancient_ai_model="gpt-fictif")
        job = self.prepare([self.record, self.old])
        (sister,) = services.job_siblings(job)
        captured = []

        def fake_translate(engine, segments, source, target, **kwargs):
            from apps.translation.engines.base import EngineResult

            captured.append(kwargs.get("variety"))
            return EngineResult({s.id: f"Traduction fictive de {s.text}" for s in segments},
                                chars_sent=sum(len(s.text) for s in segments), model="gpt-fictif")

        with mock.patch("apps.translation.engines.ai.AIEngine.translate", autospec=True, side_effect=fake_translate):
            services.confirm(job, self.user)
        sister.refresh_from_db()
        self.assertNotEqual(sister.status, "draft")
        self.assertEqual(captured, ["classical"])
        self.assertEqual(len(self.deepl.texts), 1)

    def test_all_ancient_goes_to_the_ancient_engine(self):
        TranslationPreference.objects.filter(user=self.user).update(
            ancient_engine="ai", ancient_ai_provider="openai", ancient_ai_model="gpt-fictif")
        job = self.prepare([self.old])
        self.assertEqual((job.engine, job.options["ancient"]), ("ai", True))
        page = self.client.get(f"/traduction/taches/{job.pk}/").content.decode()
        self.assertIn("Tous les textes sont repérés comme anciens", page)

    def test_user_correction_wins(self):
        TranslationPreference.objects.filter(user=self.user).update(
            ancient_engine="ai", ancient_ai_provider="openai", ancient_ai_model="gpt-fictif")
        V.confirm_record(self.old, "modern", self.user)
        job = self.prepare([self.record, Record.objects.get(pk=self.old.pk)])
        self.assertEqual((job.engine, job.total_items, services.job_siblings(job)), ("deepl", 2, []))


class LocalPickerStateTests(AppTestCase):
    """16 novembre 2026, poste de l'utilisateur : « Actualiser la liste » de l'IA locale semblait ne rien faire."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)
        self.params = {"provider_field": "summary_provider", "model_field": "summary_model",
                       "summary_provider": "ollama", "provider_id": "id_summary_provider",
                       "model_id": "id_summary_model"}

    def test_refresh_says_why_the_list_is_empty(self):
        import os

        with mock.patch.dict(os.environ, {"COMPOSE_PROFILES": "argos"}):
            page = self.client.post("/ia/modeles/actualiser/", self.params).content.decode()
        self.assertIn("IA locale non installée : ajoutez « ollama » à la ligne COMPOSE_PROFILES", page)
        self.assertIn("Liste du ", page)  # l'actualisation est datée
        self.assertNotIn("Liste jamais actualisée", page)

    def test_service_without_model(self):
        import os

        import httpx

        fake = FakeOllama()
        with self.settings(OLLAMA_URL="http://ollama:11434", OLLAMA_TRANSPORT=httpx.MockTransport(fake)), \
                mock.patch.dict(os.environ, {"COMPOSE_PROFILES": "argos,ollama"}):
            page = self.client.post("/ia/modeles/actualiser/", self.params).content.decode()
            self.assertIn("aucun modèle n&#x27;est installé", page)
            fake.models = ["qwen3:4b"]
            page = self.client.post("/ia/modeles/actualiser/", self.params).content.decode()
        self.assertIn("qwen3:4b — gratuit, sur cet ordinateur", page)
        self.assertNotIn("aucun modèle", page)


class IndicatorTests(SummaryCase):
    """16 novembre 2026, poste de l'utilisateur : un résumé en cours s'affichait « 1 traduction en cours »."""

    def test_summary_is_not_called_a_translation(self):
        (job,) = S.prepare(self.user, records=[self.record])
        TranslationJob.objects.filter(pk=job.pk).update(status="running", heartbeat_at=timezone.now())
        page = self.client.get("/traduction/taches/").content.decode()
        self.assertIn("1 résumé en cours", page)
        self.assertNotIn("traduction en cours", page)
        self.assertEqual(Q.running_label(self.user), "1 résumé en cours")
        other = TranslationJob.objects.create(user=self.user, kind="records", engine="argos", status="running",
                                              heartbeat_at=timezone.now())
        self.assertEqual(Q.running_label(self.user), "1 traduction et 1 résumé en cours")
        TranslationJob.objects.filter(pk__in=[job.pk, other.pk]).update(status="done")
        self.assertEqual(Q.running_label(self.user), "")


class OllamaNativeCallTests(AppTestCase):
    """16 novembre 2026, poste de l'utilisateur : qwen3:4b, « La réponse de l'IA n'est pas au format JSON attendu »."""

    def setUp(self):
        import httpx

        from apps.ai.providers import OllamaProvider

        super().setUp()
        self.bodies, self.reply = [], {}

        def handler(request):
            self.bodies.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json=self.reply)

        OllamaProvider.transport = httpx.MockTransport(handler)
        self.addCleanup(setattr, OllamaProvider, "transport", None)
        overrides = self.settings(OLLAMA_URL="http://ollama:11434")
        overrides.enable()
        self.addCleanup(overrides.disable)

    def provider(self):
        from apps.ai import local
        from apps.ai.providers import get_provider

        return get_provider(local.credential_for(self.researcher))

    def test_native_api_without_thinking_with_json_and_context(self):
        self.reply = {"model": "qwen3:4b", "message": {"role": "assistant", "content": '{"summary": "Fictif."}'},
                      "done_reason": "stop", "prompt_eval_count": 210, "eval_count": 12}
        completion = self.provider().complete("Système", "Consigne", "qwen3:4b", max_tokens=800)
        path, body = self.bodies[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual((body["think"], body["format"], body["stream"]), (False, "json", False))
        self.assertEqual(body["options"], {"num_predict": 800, "num_ctx": 8192})
        self.assertEqual((completion.text, completion.tokens_in, completion.tokens_out), ('{"summary": "Fictif."}',
                                                                                          210, 12))
        self.assertEqual(S.parse(completion.text)["summary"], "Fictif.")

    def test_empty_or_cut_replies_are_explained(self):
        self.reply = {"message": {"content": ""}, "done_reason": "length"}
        with self.assertRaisesMessage(ProviderError, "limite de longueur a été atteinte avant la réponse"):
            self.provider().complete("S", "P", "qwen3:4b")
        self.reply = {"message": {"content": '{"summary": "Début coup'}, "done_reason": "length"}
        text = self.provider().complete("S", "P", "qwen3:4b").text
        with self.assertRaisesMessage(ProviderError, "Début de la réponse : « {\"summary\": \"Début coup"):
            S.parse(text)

    def test_parse_shows_what_was_received(self):
        with self.assertRaisesMessage(ProviderError, "Début de la réponse : « Voici le résumé demandé"):
            S.parse("Voici le résumé demandé, sans JSON.")
        with self.assertRaisesMessage(ProviderError, "ne contient que son raisonnement, sans résumé"):
            S.parse("<think>raisonnement jamais refermé")
        with self.assertRaisesMessage(ProviderError, "Réponse vide."):
            S.parse("")
        self.assertEqual(S.parse('<think>a</think>```json\n{"summary": "Oui."}\n```')["summary"], "Oui.")


class WordingTests(SummaryCase):
    """16 novembre 2026, tâche n° 15 sur le poste de l'utilisateur : « Tâche de traduction », « 1 traduit(s) »,
    « Traduit » pour un résumé."""

    def test_summary_job_page_speaks_of_summaries(self):
        (job,) = self.run_summary(records=[self.record])
        page = self.client.get(f"/traduction/taches/{job.pk}/").content.decode()
        self.assertIn("<h1>Demande de résumés n° ", page)
        self.assertIn("1 résumé(s) / 1", page)
        self.assertIn("caractère(s) lu(s) par l&#x27;IA", page)
        self.assertIn('<td class="small">Résumé</td>', page)
        self.assertNotIn("Tâche de traduction", page)
        self.assertNotIn("traduit(s)", page)


class LocalAutoSelftestTests(AppTestCase):
    """16 novembre 2026 : « Résumé d'essai en échec » restait affiché, l'essai datant d'avant le correctif 4."""

    def setUp(self):
        import os

        import httpx

        super().setUp()
        self.fake = FakeOllama(models=["qwen3:4b"])
        overrides = self.settings(OLLAMA_URL="http://ollama:11434", OLLAMA_TRANSPORT=httpx.MockTransport(self.fake))
        overrides.enable()
        self.addCleanup(overrides.disable)
        env = mock.patch.dict(os.environ, {"COMPOSE_PROFILES": "argos,ollama"})
        env.start()
        self.addCleanup(env.stop)

    def test_failed_selftest_is_redone_at_startup_then_left_alone(self):
        from apps.ai import local
        from apps.core.models import ServiceCheck

        ServiceCheck.record(local.CHECK_NAME, False, "Essai de résumé en échec : ancien format", model="qwen3:4b")
        with mock.patch("apps.ai.providers.get_provider", return_value=StubProvider()):
            self.assertEqual(local.auto_selftest(), "fait")
            self.assertTrue(local.last_selftest().ok)
            self.assertEqual(local.auto_selftest(), "inutile")  # déjà réussi avec un modèle installé

    def test_old_failure_just_after_restart_is_only_pending(self):
        """Rapport du 16/11, 20:26 : vérification lancée une minute après la mise à jour, avant l'essai automatique."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.ai import local
        from apps.core import health
        from apps.core.models import ServiceCheck

        ServiceCheck.record(local.CHECK_NAME, False, "Essai de résumé en échec : ancien format", model="qwen3:4b")
        ServiceCheck.objects.filter(name=local.CHECK_NAME).update(checked_at=timezone.now() - timedelta(hours=2))
        just_started = timezone.now() - timedelta(minutes=1)
        with mock.patch.object(health, "container_started_at", return_value=just_started):
            check = health.check_local_ai()
        self.assertEqual((check.level, check.summary), (health.WARNING, "Essai automatique en attente"))
        self.assertTrue(any("refait automatiquement vers" in d for d in check.details))
        long_ago = timezone.now() - timedelta(hours=1)  # démarrage ancien : l'essai automatique aurait dû avoir lieu
        with mock.patch.object(health, "container_started_at", return_value=long_ago):
            self.assertEqual(health.check_local_ai().level, health.ERROR)
        with mock.patch.object(health, "container_started_at", return_value=None):
            self.assertEqual(health.check_local_ai().level, health.ERROR)

    def test_failure_followed_by_a_real_summary_is_ok(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.ai import local
        from apps.ai.models import AITask
        from apps.core import health
        from apps.core.models import ServiceCheck

        ServiceCheck.record(local.CHECK_NAME, False, "Essai de résumé en échec : ancien format", model="qwen3:4b")
        with mock.patch.object(health, "container_started_at", return_value=None):
            self.assertEqual(health.check_local_ai().level, health.ERROR)
            AITask.objects.create(user=self.admin, function="summary", provider="openai", status="done",
                                  finished_at=timezone.now() + timedelta(seconds=1))
            self.assertEqual(health.check_local_ai().level, health.ERROR)  # autre fournisseur : ne prouve rien
            AITask.objects.create(user=self.admin, function="summary", provider="ollama", status="done",
                                  finished_at=timezone.now() + timedelta(seconds=1))
            check = health.check_local_ai()
        self.assertEqual((check.level, check.summary), (health.OK, "Prête"))
        self.assertTrue(any("vrai résumé" in d for d in check.details))

    def test_verifier_shows_the_cause(self):
        from apps.ai import local
        from apps.core import health, verification
        from apps.core.models import ServiceCheck

        ServiceCheck.record(local.CHECK_NAME, False, "Essai de résumé en échec : délai dépassé", model="qwen3:4b")
        with mock.patch.object(health, "container_started_at", return_value=None):
            level, _summary, details = verification.check_installation(None)
        self.assertEqual(level, health.ERROR)
        self.assertTrue(any("délai dépassé" in d for d in details), details)

    def test_nothing_without_service_or_model(self):
        import os

        from apps.ai import local

        self.fake.models = []
        self.assertEqual(local.auto_selftest(), "inutile")
        with mock.patch.dict(os.environ, {"COMPOSE_PROFILES": "argos"}):
            self.assertEqual(local.auto_selftest(), "inutile")


class SelftestPromptTests(AppTestCase):
    """16 novembre 2026, 18 h 59 : qwen3:4b répondait {"error": "No input text provided..."} à l'ancienne consigne."""

    def test_selftest_uses_the_real_summary_prompt(self):
        from apps.ai import local

        stub = StubProvider()
        with mock.patch("apps.ai.providers.get_provider", return_value=stub), \
                mock.patch("apps.ai.local.get_provider", create=True, return_value=stub):
            check = local.run_selftest(self.admin, "qwen3:4b")
        self.assertTrue(check.ok)
        prompt = stub.prompts[0]
        self.assertIn("Rédige en français un résumé court", prompt)
        self.assertIn("TEXTE :\n" + local.TEST_TEXT, prompt)
        self.assertTrue(prompt.endswith("/no_think"))
