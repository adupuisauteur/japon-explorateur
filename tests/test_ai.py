"""AT-17, AT-18 et AT-IA-01 à AT-IA-12."""
import json

import httpx

from apps.ai.models import AIPreferenceProfile, AIProviderCredential, AITask
from apps.ai.preferences import active_profile
from apps.ai.providers import AnthropicProvider, GeminiProvider, OpenAIProvider
from apps.catalog.models import EditorialContent, RecordLink
from apps.catalog.services import upsert_record

from .helpers import AppTestCase

CALLS = []


def fake_api(request):
    CALLS.append(str(request.url))
    path = request.url.path
    if path.endswith("/models"):
        if "generativelanguage" in str(request.url):
            return httpx.Response(200, json={"models": [{"name": "models/gemini-test", "supportedGenerationMethods": ["generateContent"]}]})
        return httpx.Response(200, json={"data": [{"id": "claude-test"}, {"id": "gpt-test"}]})
    body = json.loads(request.content)
    text = json.dumps({"records": [{"record_id": RECORD_ID[0], "translated_title": "Traité des cinq anneaux",
                                    "description_translation": None, "uncertainty": "titre usuel",
                                    "summary": "Traité de stratégie."}],
                       "pairs": [{"a": RECORD_ID[0], "b": RECORD_ID[1], "relation": "same_work", "score": 0.8,
                                  "rationale": "même titre"}],
                       "variants": [{"value": "五輪之書", "kind": "graphie", "status": "attestée", "rationale": "…"}]},
                      ensure_ascii=False)
    if "anthropic" in str(request.url):
        assert request.headers["x-api-key"] == "sk-ant-test-0123456789"
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}], "usage": {"input_tokens": 120, "output_tokens": 40},
                                         "model": body["model"]})
    if "generativelanguage" in str(request.url):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}],
                                         "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 30}})
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 90, "completion_tokens": 20}})


RECORD_ID = []


class AITests(AppTestCase):
    def setUp(self):
        super().setUp()
        CALLS.clear()
        for cls in (OpenAIProvider, AnthropicProvider, GeminiProvider):
            cls.transport = httpx.MockTransport(fake_api)
        cat = self.catalogue("codh-pmjt")
        self.r1, _ = upsert_record(cat, {"source_id": "A1", "original_title": "五輪書", "description_original": "兵法書"})
        self.r2, _ = upsert_record(cat, {"source_id": "A2", "original_title": "五輪之書"})
        RECORD_ID[:] = [self.r1.record_id, self.r2.record_id]

    def tearDown(self):
        for cls in (OpenAIProvider, AnthropicProvider, GeminiProvider):
            cls.transport = None

    def _configure(self, provider="anthropic", key="sk-ant-test-0123456789", model="claude-test"):
        self.client.post(f"/ia/fournisseurs/{provider}/", {"action": "save", "api_key": key})
        self.client.post(f"/ia/fournisseurs/{provider}/", {"action": "test"})
        profile = active_profile(self.admin)
        profile.default_provider, profile.default_model = provider, model
        profile.save()
        return profile

    def test_ia01_initial_preferences(self):
        p = active_profile(self.researcher)
        self.assertEqual(p.mode, "demand")
        self.assertTrue(p.translation_enabled)
        self.assertTrue(p.summary_enabled)
        self.assertFalse(p.classification_enabled)
        self.assertTrue(p.duplicates_enabled)

    def test_ia02_save_and_reload_preferences(self):
        p = active_profile(self.admin)
        r = self.client.post(f"/ia/preferences/?profile={p.pk}", {
            "name": "Prudent", "mode": "confirm", "translation_enabled": "on", "default_provider": "gemini",
            "default_model": "gemini-test", "alert_threshold_pct": 80, "ov_translation_provider": "anthropic",
            "ov_translation_model": "claude-test"})
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual((p.name, p.mode, p.summary_enabled), ("Prudent", "confirm", False))
        self.assertEqual(p.provider_for("translation"), ("anthropic", "claude-test"))
        self.assertEqual(p.provider_for("summary"), ("gemini", "gemini-test"))
        self.assertEqual(AITask.objects.count(), 0)

    def test_ia03_and_at17_disable_ai(self):
        p = self._configure()
        p.mode = "disabled"
        p.save()
        page = self.client.get(self.r1.get_absolute_url())
        self.assertNotContains(page, "Fonctions IA")
        r = self.client.post("/ia/lancer/", {"function": "translation", "record_ids": self.r1.record_id})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(len([c for c in CALLS if "/messages" in c]), 0)
        # fonctions documentaires intactes
        self.assertEqual(self.client.get("/recherche/rapide/?q=五輪", follow=True).status_code, 200)
        self.assertEqual(self.client.get("/bibliotheque/").status_code, 200)
        p.mode = "demand"
        p.translation_enabled = False
        p.save()
        r = self.client.post("/ia/lancer/", {"function": "translation", "record_ids": self.r1.record_id})
        self.assertContains(r, "pas activée", status_code=409)

    def test_ia04_import_and_sync_never_trigger_ai(self):
        self._configure()
        CALLS.clear()
        self.import_example()
        from apps.updates.models import SyncJob
        from apps.updates.services import run_sync

        run_sync(SyncJob.objects.create(catalogue=self.catalogue("local"), kind="test"))
        self.assertEqual(AITask.objects.count(), 0)
        self.assertEqual(CALLS, [])

    def test_ia05_switch_profile_triggers_nothing(self):
        self._configure()
        CALLS.clear()
        other = AIPreferenceProfile.objects.create(user=self.admin, name="Autre", mode="demand", classification_enabled=True)
        self.client.post(f"/ia/preferences/{other.pk}/", {"action": "activate"})
        self.assertEqual(active_profile(self.admin), other)
        self.assertEqual((AITask.objects.count(), CALLS), (0, []))

    def test_at18_and_ia06_explicit_launch_and_confirmation(self):
        self._configure()
        CALLS.clear()
        r = self.client.post("/ia/lancer/", {"function": "translation", "record_ids": self.r1.record_id})
        task = AITask.objects.get()
        self.assertRedirects(r, f"/ia/taches/{task.pk}/")
        self.assertEqual(task.status, "draft")
        self.assertEqual(CALLS, [], "aucun envoi avant confirmation")
        page = self.client.get(f"/ia/taches/{task.pk}/")
        self.assertContains(page, "Catégories de données transmises")
        self.assertContains(page, "Anthropic")
        self.assertContains(page, "claude-test")
        self.client.post(f"/ia/taches/{task.pk}/", {"action": "confirm"})
        task.refresh_from_db()
        self.assertEqual(task.status, "done", task.error)
        ed = EditorialContent.objects.get(record=self.r1, kind="translation")
        self.assertEqual((ed.origin, ed.status, ed.content), ("ai", "proposed", "Traité des cinq anneaux"))
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.original_title, "五輪書", "le texte source est conservé")
        self.assertEqual(self.r1.translated_title, "", "la traduction IA n'est pas adoptée sans action")
        self.client.post(f"/notices/editorial/{ed.pk}/decision/", {"action": "adopt"})
        self.r1.refresh_from_db()
        self.assertEqual((self.r1.translated_title, self.r1.translated_title_origin), ("Traité des cinq anneaux", "ai"))
        # doublons IA : proposition, jamais de fusion
        prof = active_profile(self.admin)
        prof.batch_extra_confirmation = True
        prof.save()
        self.client.post("/ia/lancer/", {"function": "duplicates", "record_ids": f"{self.r1.record_id},{self.r2.record_id}"})
        dup = AITask.objects.filter(function="duplicates").get()
        self.client.post(f"/ia/taches/{dup.pk}/", {"action": "confirm"})
        dup.refresh_from_db()
        self.assertEqual(dup.status, "draft", "un lot exige la confirmation supplémentaire")
        self.client.post(f"/ia/taches/{dup.pk}/", {"action": "confirm", "confirm_batch": "1"})
        dup.refresh_from_db()
        self.assertEqual(dup.status, "done")
        link = RecordLink.objects.get()
        self.assertEqual((link.origin, link.status, link.link_type), ("ai", "proposed", "same_work"))
        # classification désactivée par défaut
        r = self.client.post("/ia/lancer/", {"function": "classification", "record_ids": self.r1.record_id})
        self.assertEqual(r.status_code, 409)

    def test_confirm_mode_shows_payload(self):
        p = self._configure()
        p.mode = "confirm"
        p.save()
        self.client.post("/ia/lancer/", {"function": "summary", "record_ids": self.r1.record_id})
        page = self.client.get(f"/ia/taches/{AITask.objects.get().pk}/")
        self.assertContains(page, "Données exactes qui seront envoyées")
        self.assertContains(page, "兵法書")

    def test_ia07_configure_and_test_each_provider(self):
        for provider, key in (("openai", "sk-proj-test-0123456789"), ("anthropic", "sk-ant-test-0123456789"),
                              ("gemini", "AIzaTestKey0123456789012345")):
            self.client.post(f"/ia/fournisseurs/{provider}/", {"action": "save", "api_key": key})
            cred = AIProviderCredential.objects.get(user=self.admin, provider=provider)
            self.assertNotIn(key, cred.encrypted_key, "clé chiffrée au repos")
            self.client.post(f"/ia/fournisseurs/{provider}/", {"action": "test"})
            cred.refresh_from_db()
            self.assertEqual(cred.status, "ok", cred.last_error)
            self.assertTrue(cred.available_models)
        page = self.client.get("/ia/fournisseurs/")
        self.assertNotContains(page, "sk-ant-test")
        self.assertNotContains(page, "AIzaTestKey")

    def test_ia08_ia09_default_and_per_function_provider(self):
        self._configure("gemini", "AIzaTestKey0123456789012345", "gemini-test")
        self.client.post("/ia/fournisseurs/anthropic/", {"action": "save", "api_key": "sk-ant-test-0123456789"})
        self.client.post("/ia/fournisseurs/anthropic/", {"action": "test"})
        p = active_profile(self.admin)
        p.function_overrides = {"translation": {"provider": "anthropic", "model": "claude-test"}}
        p.save()
        self.client.post("/ia/lancer/", {"function": "summary", "record_ids": self.r1.record_id})
        self.client.post("/ia/lancer/", {"function": "translation", "record_ids": self.r1.record_id})
        summary, translation = AITask.objects.order_by("pk")
        self.assertEqual((summary.provider, summary.model), ("gemini", "gemini-test"))
        self.assertEqual((translation.provider, translation.model), ("anthropic", "claude-test"))
        self.client.post(f"/ia/taches/{summary.pk}/", {"action": "confirm"})
        summary.refresh_from_db()
        self.assertEqual(summary.status, "done", summary.error)
        self.assertEqual(summary.tokens_in, 100)

    def test_ia10_unavailable_provider_no_silent_fallback(self):
        self._configure("anthropic")
        self.client.post("/ia/fournisseurs/openai/", {"action": "save", "api_key": "sk-proj-test-0123456789"})
        self.client.post("/ia/fournisseurs/anthropic/", {"action": "revoke"})
        r = self.client.post("/ia/lancer/", {"function": "summary", "record_ids": self.r1.record_id})
        self.assertEqual(r.status_code, 409)
        self.assertContains(r, "pas configuré", status_code=409)
        self.assertContains(r, "autre fournisseur", status_code=409)
        self.assertEqual(AITask.objects.count(), 0)

    def test_ia11_replace_and_revoke_key(self):
        self._configure()
        cred = AIProviderCredential.objects.get(provider="anthropic")
        old = cred.encrypted_key
        self.client.post("/ia/fournisseurs/anthropic/", {"action": "save", "api_key": "sk-ant-new-key-0123456789"})
        cred.refresh_from_db()
        self.assertNotEqual(cred.encrypted_key, old)
        self.assertEqual(cred.status, "untested")
        self.client.post("/ia/fournisseurs/anthropic/", {"action": "revoke"})
        cred.refresh_from_db()
        self.assertEqual((cred.encrypted_key, cred.status), ("", "revoked"))

    def test_ia12_saving_key_is_not_consent(self):
        p = active_profile(self.admin)
        p.mode = "disabled"
        p.save()
        self._configure()
        p.refresh_from_db()
        self.assertEqual(p.mode, "disabled")
        self.assertEqual(AITask.objects.count(), 0)
        self.assertFalse([c for c in CALLS if "/messages" in c])

    def test_budget_cap_blocks(self):
        p = self._configure()
        p.monthly_budget = 0
        p.save()
        self.client.post("/ia/lancer/", {"function": "summary", "record_ids": self.r1.record_id})
        task = AITask.objects.get()
        self.client.post(f"/ia/taches/{task.pk}/", {"action": "confirm"})
        task.refresh_from_db()
        self.assertEqual(task.status, "blocked")

    def test_secrets_redacted_in_logs(self):
        from apps.core.logging import redact

        self.assertNotIn("sk-ant-test-0123456789", redact("erreur avec sk-ant-test-0123456789 dans le message"))
        self.assertNotIn("AIzaTestKey0123456789012345", redact("key=AIzaTestKey0123456789012345"))
