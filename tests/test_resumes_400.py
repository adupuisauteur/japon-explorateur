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
        self.run_summary(documents=[self.document(MODERN, project=secret)])
        summary = Summary.objects.get()
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
