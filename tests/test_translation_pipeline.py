"""Évolution 1.3.0 — lot 4 : chaîne de traitement (tâches, confirmation, plafonds, reprise, journal).

Moteurs sur réponses simulées (aucun réseau). Données fictives uniquement.
"""
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

import httpx
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User
from apps.ai.crypto import encrypt_secret
from apps.ai.models import AIModelPrice, AIProviderCredential, AITask
from apps.ai.preferences import active_profile
from apps.ai.providers import AnthropicProvider
from apps.catalog.models import EditorialContent
from apps.catalog.services import upsert_record
from apps.incidents.models import Incident
from apps.translation import memory as tm
from apps.translation import services
from apps.translation.engines.argos import SIMULATION_PREFIX
from apps.translation.engines.deepl import DeepLEngine
from apps.translation.engines.registry import ENGINE_CLASSES
from apps.translation.models import (EngineSetting, TranslationDocument, TranslationJob, TranslationPreference,
                                     TranslationProject, TranslationSegment, TranslationVersion)

from .helpers import AppTestCase, acknowledge_terms, set_argos_demo

SECRET = "秘密の架空文"


class DeepLStub:
    """Faux service DeepL : traduit « X » en « FR:X » ; règles d'échec programmables ; compte les textes reçus."""

    def __init__(self):
        self.texts = []
        self.status = 200
        self.fail_if_contains = None
        self.wrong_count_once = False

    def __call__(self, request):
        body = json.loads(request.content)
        texts = body["text"]
        if self.status != 200:
            return httpx.Response(self.status, json={"message": "erreur simulée"})
        if self.fail_if_contains and any(self.fail_if_contains in t for t in texts):
            if len(texts) > 1:
                return httpx.Response(200, json={"translations": [{"text": "x"}]})  # nombre incorrect
            return httpx.Response(200, json={"translations": []})
        if self.wrong_count_once:
            self.wrong_count_once = False
            return httpx.Response(200, json={"translations": [{"text": "x"}]})
        self.texts.extend(texts)
        return httpx.Response(200, json={"translations": [{"text": f"Traduction de {t}"} for t in texts]})


class PipelineTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(self._reset)
        self.user = self.researcher
        EngineSetting.objects.create(user=self.user, engine="deepl", plan="free",
                                     encrypted_key=encrypt_secret("fake-deepl-key-0000000000"), status="ok")
        TranslationPreference.objects.create(user=self.user, default_engine="deepl")
        self.stub = DeepLStub()
        DeepLEngine.transport = httpx.MockTransport(self.stub)
        self.project = TranslationProject.objects.create(owner=self.user, title="Projet fictif")
        acknowledge_terms(self.user, "deepl", "google_basic", "ai:anthropic")

    def _reset(self):
        for cls in list(ENGINE_CLASSES.values()) + [AnthropicProvider]:
            cls.transport = None

    def doc(self, *texts, project=None, variety="modern"):
        project = project or self.project
        doc = TranslationDocument.objects.create(project=project, title="Document fictif",
                                                 original_text="".join(texts), variety=variety)
        return [TranslationSegment.objects.create(document=doc, position=i, source_text=t,
                                                  memory_key=tm.memory_key(t)) for i, t in enumerate(texts, 1)]

    def run_job(self, job, **kwargs):
        services.confirm(job, self.user, **kwargs)
        job.refresh_from_db()
        return job


class PreparationTests(PipelineTestCase):
    def test_preparation_sends_nothing(self):
        segs = self.doc("一つ目の文。", "二つ目の文。")
        job = services.prepare_segments_job(self.user, segs, project=self.project)
        self.assertEqual(job.status, "draft")
        self.assertEqual((job.total_items, job.chars_estimated), (2, len("一つ目の文。") + len("二つ目の文。")))
        self.assertEqual(self.stub.texts, [])

    def test_validated_segments_and_memory_are_not_sent(self):
        done, again = self.doc("既に訳した文。", "記憶にある文。")
        TranslationVersion.objects.create(segment=done, text="Déjà validé.", source_text=done.source_text,
                                          origin="human", status="validated")
        other = TranslationProject.objects.create(owner=self.user, title="Autre projet fictif")
        (mem,) = self.doc("記憶にある文。", project=other)  # même texte : forme NFKC identique
        TranslationVersion.objects.create(segment=mem, text="Phrase en mémoire.", source_text=mem.source_text,
                                          origin="human", status="validated", engine="deepl")
        job = services.prepare_segments_job(self.user, [done, again], project=self.project)
        reasons = sorted(job.items.values_list("skip_reason", flat=True))
        self.assertEqual(reasons, ["memory", "validated"])
        self.assertEqual(job.chars_estimated, 0)
        job = self.run_job(job)
        self.assertEqual(self.stub.texts, [], "rien n'est envoyé au moteur")
        copy = again.versions.get()
        self.assertEqual((copy.text, copy.status), ("Phrase en mémoire.", "proposed"))
        self.assertIn("mémoire", copy.alerts[0])

    def test_memory_never_crosses_accounts(self):
        other_user = User.objects.create_user("autre", password="motdepasse-solide-9", role="researcher")
        foreign = TranslationProject.objects.create(owner=other_user, title="Projet d'autrui")
        (seg,) = self.doc("共有されない文。", project=foreign)
        TranslationVersion.objects.create(segment=seg, text="Secret d'autrui.", source_text=seg.source_text,
                                          origin="human", status="validated")
        (mine,) = self.doc("共有されない文。")
        job = services.prepare_segments_job(self.user, [mine], project=self.project)
        self.assertEqual(job.items.get().status, "pending")

    def test_fullwidth_and_spacing_variants_hit_the_memory(self):
        self.assertEqual(tm.memory_key("ＡＢＣ　文。"), tm.memory_key("ABC 文。"))
        self.assertNotEqual(tm.memory_key("文。"), tm.memory_key("文、"))

    def test_no_engine_chosen(self):
        TranslationPreference.objects.filter(user=self.user).update(default_engine="")
        with self.assertRaises(services.TranslationUnavailable) as ctx:
            services.prepare_segments_job(self.user, self.doc("文。"), project=self.project)
        self.assertEqual(ctx.exception.reason, "no_engine")


class ExecutionTests(PipelineTestCase):
    def test_full_run_creates_proposed_versions(self):
        segs = self.doc("一つ目の文。", "二つ目の文。")
        job = self.run_job(services.prepare_segments_job(self.user, segs, project=self.project))
        self.assertEqual((job.status, job.done_items, job.failed_items), ("done", 2, 0))
        self.assertEqual(job.chars_sent, job.chars_estimated)
        v = segs[0].versions.get()
        self.assertEqual((v.text, v.origin, v.engine, v.status), ("Traduction de 一つ目の文。", "machine", "deepl",
                                                                  "proposed"))
        self.assertEqual(v.source_text, "一つ目の文。")
        segs[0].refresh_from_db()
        self.assertEqual(segs[0].state, "proposed")

    def test_second_confirmation_above_threshold(self):
        TranslationPreference.objects.filter(user=self.user).update(confirmation_threshold=1000)
        segs = self.doc("長" * 1200)
        job = services.prepare_segments_job(self.user, segs, project=self.project)
        self.assertTrue(job.requires_second_confirmation)
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        self.assertEqual(self.stub.texts, [])
        job = self.run_job(job, second_confirmation=True)
        self.assertEqual(job.status, "done")

    def test_reception_checks_raise_alerts(self):
        DeepLEngine.transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"translations": [
            {"text": t} for t in json.loads(r.content)["text"]]}))  # renvoie l'original
        (seg,) = self.doc("翻訳されない文。")
        self.run_job(services.prepare_segments_job(self.user, [seg], project=self.project))
        seg.refresh_from_db()
        self.assertEqual(seg.state, "alert")
        self.assertIn("identique", seg.versions.get().alerts[0])

    def test_cancel_draft_sends_nothing(self):
        job = services.prepare_segments_job(self.user, self.doc("文。"), project=self.project)
        services.cancel(job, self.user)
        job.refresh_from_db()
        self.assertEqual(job.status, "cancelled")
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        self.assertEqual(self.stub.texts, [])


class ConfidentialityAndLimitsTests(PipelineTestCase):
    def test_confidential_project_refuses_online_engines(self):
        self.project.confidential = True
        self.project.save()
        with self.assertRaises(services.TranslationUnavailable) as ctx:
            services.prepare_segments_job(self.user, self.doc("機密の文。"), project=self.project)
        self.assertEqual(ctx.exception.reason, "confidential")

    def test_confidential_check_is_repeated_at_confirmation(self):
        job = services.prepare_segments_job(self.user, self.doc("機密の文。"), project=self.project)
        TranslationProject.objects.filter(pk=self.project.pk).update(confidential=True)
        job.refresh_from_db()
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        job.refresh_from_db()
        self.assertEqual(job.status, "blocked")
        self.assertEqual(self.stub.texts, [])

    def test_confidential_project_can_use_argos_simulation(self):
        self.project.confidential = True
        self.project.save()
        EngineSetting.objects.create(user=self.user, engine="argos", enabled=True)
        set_argos_demo(True)  # 2.0.0 (D4) : Argos sert ici en mode démonstration
        segs = self.doc("機密の文。")
        job = services.prepare_segments_job(self.user, segs, project=self.project,
                                            choice=services.EngineChoice("argos"))
        job = self.run_job(job)
        v = segs[0].versions.get()
        self.assertTrue(v.simulated)
        self.assertTrue(v.text.startswith(SIMULATION_PREFIX))
        self.assertEqual(job.chars_sent, 0)
        self.assertIn("Simulation", v.alerts[0])

    def test_engine_monthly_cap(self):
        EngineSetting.objects.filter(user=self.user, engine="deepl").update(monthly_char_cap=5)
        job = services.prepare_segments_job(self.user, self.doc("上限を超える長い文。"), project=self.project)
        self.assertTrue(any("Plafond mensuel" in p for p in services.blocking_problems(job)))
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        self.assertEqual(self.stub.texts, [])


class AIPipelineTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        AIProviderCredential.objects.create(user=self.user, provider="anthropic", status="ok",
                                            encrypted_key=encrypt_secret("sk-ant-fictif-0123456789"))
        AIModelPrice.objects.create(provider="anthropic", model_prefix="claude-fictif", input_per_million=3,
                                    output_per_million=15)

        def reply(request):
            prompt = json.loads(request.content)["messages"][0]["content"]
            data = json.loads(prompt.split("SEGMENTS :\n", 1)[1])
            out = {"translations": [{"id": s["id"], "text": "IA : " + s["text"]} for s in data["segments"]]}
            return httpx.Response(200, json={"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                                             "usage": {"input_tokens": 1000, "output_tokens": 500},
                                             "model": "claude-fictif"})

        AnthropicProvider.transport = httpx.MockTransport(reply)
        self.choice = services.EngineChoice("ai", "anthropic", "claude-fictif")

    def test_each_ai_call_creates_an_ai_task(self):
        segs = self.doc("一。", "二。")
        job = self.run_job(services.prepare_segments_job(self.user, segs, project=self.project, choice=self.choice),
                           second_confirmation=True)
        self.assertEqual(job.status, "done")
        task = AITask.objects.get()
        self.assertEqual((task.function, task.status, task.tokens_in, task.tokens_out), ("translation", "done", 1000, 500))
        self.assertEqual(task.cost_estimate, Decimal("0.0105"))
        self.assertNotIn("segments", task.input_payload, "contenu non conservé (préférence IA par défaut)")
        v = segs[0].versions.get()
        self.assertEqual((v.origin, v.text), ("ai", "IA : 一。"))

    def test_ai_budget_blocks_before_sending(self):
        profile = active_profile(self.user)
        profile.monthly_budget = Decimal("0.0000001")
        profile.save()
        job = services.prepare_segments_job(self.user, self.doc("一。"), project=self.project, choice=self.choice)
        self.assertTrue(any("Plafond mensuel IA" in p for p in services.blocking_problems(job)))
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(job, self.user)
        self.assertFalse(AITask.objects.exists())

    def test_ai_consent_is_required(self):
        profile = active_profile(self.user)
        profile.translation_enabled = False
        profile.save()
        with self.assertRaises(services.TranslationUnavailable):
            services.prepare_segments_job(self.user, self.doc("一。"), project=self.project, choice=self.choice)


class FailureAndResumeTests(PipelineTestCase):
    def test_one_failing_segment_does_not_stop_the_job(self):
        self.stub.fail_if_contains = "壊"
        segs = self.doc("一つ目。", "壊れた" + SECRET, "三つ目。")
        job = self.run_job(services.prepare_segments_job(self.user, segs, project=self.project))
        self.assertEqual((job.status, job.done_items, job.failed_items), ("done", 2, 1))
        failed = job.items.get(status="failed")
        self.assertEqual(failed.segment, segs[1])
        self.assertEqual(failed.error_kind, "reponse_vide")
        incident = Incident.objects.get(module="traduction")
        dump = json.dumps(incident.occurrences.first().context, ensure_ascii=False) + incident.title
        self.assertNotIn(SECRET, dump)
        self.assertNotIn(SECRET, failed.error_message)

    def test_quota_stops_the_job_and_resume_sends_only_the_rest(self):
        segs = self.doc("一。", "二。", "三。")
        self.stub.status = 456
        job = self.run_job(services.prepare_segments_job(self.user, segs, project=self.project))
        self.assertEqual(job.status, "failed")
        self.assertIn("Arrêt", job.error_summary)
        self.assertEqual(job.items.filter(status="pending").count(), 3, "rien n'est perdu : tout reste en attente")
        self.assertTrue(Incident.objects.filter(module="traduction", category="quota_depasse").exists())
        self.stub.status = 200
        services.resume(job, self.user)
        job.refresh_from_db()
        self.assertEqual((job.status, job.done_items), ("done", 3))
        self.assertEqual(sorted(self.stub.texts), sorted(["一。", "二。", "三。"]))

    def test_interrupted_job_resumes_without_resending(self):
        segs = self.doc("一。", "二。", "三。")
        self.addCleanup(setattr, DeepLEngine, "max_items", DeepLEngine.max_items)
        DeepLEngine.max_items = 1  # paquets d'un segment : l'interruption tombe au milieu de la tâche
        job = services.prepare_segments_job(self.user, segs, project=self.project)
        with mock.patch("apps.translation.services.dispatch"):  # worker arrêté : rien ne s'exécute
            services.confirm(job, self.user)
        services.process_next_chunk(job.pk)  # premier paquet traité… puis arrêt de Docker
        self.assertEqual(self.stub.texts, ["一。"])
        job.refresh_from_db()
        sent_before = list(self.stub.texts)
        TranslationJob.objects.filter(pk=job.pk).update(status="running",
                                                        heartbeat_at=timezone.now() - timedelta(minutes=30))
        job.refresh_from_db()
        self.assertTrue(services.is_stale(job))
        services.resume(job, self.user)
        job.refresh_from_db()
        self.assertEqual((job.status, job.done_items), ("done", 3))
        self.assertEqual(self.stub.texts, sent_before + ["二。", "三。"], "aucun segment déjà traduit n'est renvoyé")
        self.assertTrue(Incident.objects.filter(category="lot_interrompu").exists())

    def test_resume_after_last_chunk_just_closes_the_job(self):
        segs = self.doc("一。")
        job = services.prepare_segments_job(self.user, segs, project=self.project)
        with mock.patch("apps.translation.services.dispatch"):
            services.confirm(job, self.user)
        services.process_next_chunk(job.pk)
        TranslationJob.objects.filter(pk=job.pk).update(heartbeat_at=timezone.now() - timedelta(minutes=30))
        job.refresh_from_db()
        services.resume(job, self.user)
        job.refresh_from_db()
        self.assertEqual((job.status, job.done_items), ("done", 1))
        self.assertEqual(self.stub.texts, ["一。"])

    def test_retry_failed_items(self):
        self.stub.fail_if_contains = "壊"
        segs = self.doc("一。", "壊。")
        job = self.run_job(services.prepare_segments_job(self.user, segs, project=self.project))
        self.stub.fail_if_contains = None
        services.retry_failed(job, self.user)
        job.refresh_from_db()
        self.assertEqual((job.done_items, job.failed_items), (2, 0))

    def test_second_engine_is_proposed_never_used_automatically(self):
        EngineSetting.objects.create(user=self.user, engine="argos", enabled=True)
        set_argos_demo(True)  # 2.0.0 (D4) : Argos sert ici en mode démonstration
        TranslationPreference.objects.filter(user=self.user).update(second_engine="argos")
        self.stub.status = 503
        segs = self.doc("一。")
        job = self.run_job(services.prepare_segments_job(self.user, segs, project=self.project))
        self.assertEqual(job.failed_items, 1)
        self.assertFalse(TranslationJob.objects.filter(engine="argos").exists(), "aucune bascule automatique")
        proposal = services.propose_second_engine(job, self.user)
        self.assertEqual((proposal.engine, proposal.status, proposal.total_items), ("argos", "draft", 1))

    def test_unexpected_error_is_logged_without_text(self):
        segs = self.doc(SECRET)
        job = services.prepare_segments_job(self.user, segs, project=self.project)
        with mock.patch("apps.translation.services._store", side_effect=ValueError(SECRET)):
            self.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")
        incident = Incident.objects.get(module="traduction", category="erreur_application")
        self.assertNotIn(SECRET, incident.title + incident.occurrences.first().message)


class RecordJobTests(PipelineTestCase):
    def test_record_fields_go_to_editorial_layer(self):
        cat = self.catalogue("codh-pmjt")
        record, _ = upsert_record(cat, {"source_id": "T1", "original_title": "架空の書",
                                        "description_original": "架空の解題。"})
        record.language = "lzh"
        record.save()
        job = self.run_job(services.prepare_records_job(self.user, [record]))
        self.assertEqual((job.kind, job.done_items), ("records", 2))
        eds = EditorialContent.objects.filter(record=record, kind="translation").order_by("target_field")
        self.assertEqual([e.target_field for e in eds], ["description_original", "original_title"])
        title = eds.get(target_field="original_title")
        self.assertEqual((title.origin, title.status, title.content), ("mt", "proposed", "Traduction de 架空の書"))
        self.assertEqual((title.data["engine"], title.data["variety"]), ("deepl", "kanbun"))
        record.refresh_from_db()
        self.assertEqual(record.original_title, "架空の書", "la notice d'origine n'est jamais modifiée")
        self.assertEqual(record.translated_title, "", "traduction proposée, pas adoptée")


class JobViewTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.job = services.prepare_segments_job(self.user, self.doc("一。"), project=self.project)

    def test_confirmation_page_and_launch(self):
        page = self.client.get(f"/traduction/taches/{self.job.pk}/")
        self.assertContains(page, "rien n'a encore été envoyé")
        self.assertEqual(self.stub.texts, [])
        self.client.post(f"/traduction/taches/{self.job.pk}/action/", {"action": "confirm"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "done")
        self.assertContains(self.client.get(f"/traduction/taches/{self.job.pk}/", HTTP_HX_REQUEST="true"),
                            "Traduction de 一。")

    def test_job_is_private(self):
        other = User.objects.create_user("autre2", password="motdepasse-solide-8", role="researcher")
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/traduction/taches/{self.job.pk}/").status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/traduction/taches/{self.job.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/traduction/taches/{self.job.pk}/action/",
                                          {"action": "confirm"}).status_code, 404)

    def test_job_list(self):
        self.assertContains(self.client.get("/traduction/taches/"), "Projet fictif")


class InfrastructureTests(PipelineTestCase):
    def test_dedicated_celery_queue(self):
        self.assertEqual(settings.CELERY_TASK_ROUTES["apps.translation.tasks.*"]["queue"], "traduction")
        compose = (Path(settings.BASE_DIR) / "docker-compose.yml").read_text(encoding="utf-8")
        # 2.0.0 (lot 3) : un worker par file
        for queue in ("celery", "traduction", "maintenant"):
            self.assertIn(f'"-Q", "{queue}"]', compose)
