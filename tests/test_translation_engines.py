"""Évolution 1.3.0 — lot 3 : moteurs de traduction et page Traduction → Moteurs.

Tous les appels passent par des réponses enregistrées FICTIVES (tests/fixtures/traduction/) ; un
garde-fou refuse tout appel réseau réel pendant les tests. Statut de chaque moteur à l'issue du lot :
« développé et testé en simulation » ; test réel à confirmer par l'utilisateur.
"""
import json
from pathlib import Path

import httpx
from django.test import override_settings

from apps.ai.crypto import encrypt_secret
from apps.ai.models import AIProviderCredential
from apps.ai.preferences import active_profile
from apps.ai.providers import AnthropicProvider
from apps.incidents.models import Incident
from apps.translation.engines import ai as ai_module
from apps.translation.engines.argos import SIMULATION_PREFIX, ArgosEngine
from apps.translation.engines.base import Segment, TranslationEngineError
from apps.translation.engines.deepl import DeepLEngine
from apps.translation.engines.google_basic import GoogleBasicEngine
from apps.translation.engines.registry import ENGINE_CLASSES, get_engine
from apps.translation.http import NetworkBlocked
from apps.translation.journal import record_translation_error
from apps.translation.models import EngineSetting, TranslationPreference

from .helpers import AppTestCase

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "traduction"
SECRET_TEXT = "秘密の架空原文"  # sert à vérifier qu'aucun texte n'atteint le journal ni les diagnostics
FAKE_DEEPL_KEY = "00000000-fake-deepl-key-for-tests"
FAKE_GOOGLE_KEY = "AIzaFAKEgoogleKEYforTESTSonly0000000"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class Recorder:
    """Transport httpx simulé : enregistre les requêtes, renvoie des réponses programmées."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        status, body = item
        if isinstance(body, (dict, list)):
            return httpx.Response(status, json=body)
        return httpx.Response(status, content=body.encode("utf-8") if isinstance(body, str) else body)

    @property
    def transport(self):
        return httpx.MockTransport(self)


class EngineTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(self._reset_transports)

    def _reset_transports(self):
        for cls in list(ENGINE_CLASSES.values()) + [AnthropicProvider]:
            cls.transport = None

    def use(self, engine_cls, recorder):
        engine_cls.transport = recorder.transport
        return recorder

    def deepl(self, plan="free"):
        EngineSetting.objects.update_or_create(user=self.researcher, engine="deepl", defaults={
            "encrypted_key": encrypt_secret(FAKE_DEEPL_KEY), "plan": plan})
        return get_engine("deepl", self.researcher)

    def google(self):
        EngineSetting.objects.update_or_create(user=self.researcher, engine="google_basic", defaults={
            "encrypted_key": encrypt_secret(FAKE_GOOGLE_KEY)})
        return get_engine("google_basic", self.researcher)

    def segs(self, *texts):
        return [Segment(str(i), t) for i, t in enumerate(texts, start=1)]

    def assert_no_secret(self, exc):
        dump = json.dumps(getattr(exc, "diagnostic", {}), ensure_ascii=False) + str(exc)
        for secret in (SECRET_TEXT, FAKE_DEEPL_KEY, FAKE_GOOGLE_KEY):
            self.assertNotIn(secret, dump)


class NetworkGuardTests(EngineTestCase):
    def test_real_network_call_is_refused_during_tests(self):
        engine = self.deepl()
        with self.assertRaises(NetworkBlocked):
            engine.translate(self.segs("架空の文。"), "ja", "fr")


class DeepLTests(EngineTestCase):
    def test_translation_request_and_result(self):
        rec = self.use(DeepLEngine, Recorder((200, fixture("deepl_translate_ok.json"))))
        result = self.deepl("free").translate(self.segs("一つ目の架空の文。", "二つ目の架空の文。"), "ja", "fr")
        self.assertEqual(result.translations["2"], "Ceci est une seconde phrase fictive.")
        self.assertEqual(result.chars_sent, len("一つ目の架空の文。") + len("二つ目の架空の文。"))
        self.assertFalse(result.simulated)
        req = rec.requests[0]
        self.assertEqual(str(req.url), "https://api-free.deepl.com/v2/translate")
        self.assertEqual(req.headers["Authorization"], f"DeepL-Auth-Key {FAKE_DEEPL_KEY}")
        body = json.loads(req.content)
        self.assertEqual((body["source_lang"], body["target_lang"]), ("JA", "FR"))
        self.assertEqual(len(body["text"]), 2)

    def test_pro_plan_uses_pro_address(self):
        rec = self.use(DeepLEngine, Recorder((200, fixture("deepl_translate_ok.json"))))
        self.deepl("pro").translate(self.segs("一。", "二。"), "ja", "fr")
        self.assertTrue(str(rec.requests[0].url).startswith("https://api.deepl.com/"))

    def test_batches_of_fifty_texts(self):
        def reply(request):
            n = len(json.loads(request.content)["text"])
            return httpx.Response(200, json={"translations": [{"text": "x"}] * n})

        DeepLEngine.transport = httpx.MockTransport(reply)
        calls = []
        DeepLEngine.transport = httpx.MockTransport(lambda r: calls.append(r) or reply(r))
        result = self.deepl().translate(self.segs(*["文。"] * 60), "ja", "fr")
        self.assertEqual(len(result.translations), 60)
        self.assertEqual([len(json.loads(c.content)["text"]) for c in calls], [50, 10])

    def test_errors_are_classified(self):
        cases = [
            ((403, fixture("deepl_error.json")), "config", "cle_refusee", 1),
            ((456, fixture("deepl_error.json")), "unavailable", "quota_depasse", 1),  # jamais réessayé
            ((429, {}), "unavailable", "quota_depasse", 3),  # réessayé deux fois
            ((503, "panne"), "unavailable", "", 3),
            ((400, {"message": "Value for 'target_lang' not supported."}), "technical", "", 1),
            ((200, "pas du JSON"), "unparsable", "reponse_vide", 1),
            ((200, {"translations": []}), "unparsable", "reponse_vide", 1),
        ]
        for response, kind, code, calls in cases:
            with self.subTest(status=response[0], body=str(response[1])[:20]):
                rec = self.use(DeepLEngine, Recorder(response))
                with self.assertRaises(TranslationEngineError) as ctx:
                    self.deepl().translate(self.segs(SECRET_TEXT), "ja", "fr")
                self.assertEqual((ctx.exception.kind, ctx.exception.code), (kind, code))
                self.assertEqual(len(rec.requests), calls)
                self.assert_no_secret(ctx.exception)

    def test_timeout(self):
        self.use(DeepLEngine, Recorder(httpx.ReadTimeout("délai")))
        with self.assertRaises(TranslationEngineError) as ctx:
            self.deepl().translate(self.segs(SECRET_TEXT), "ja", "fr")
        self.assertEqual((ctx.exception.kind, ctx.exception.code), ("unavailable", "delai_depasse"))

    def test_missing_plan_or_key(self):
        EngineSetting.objects.create(user=self.researcher, engine="deepl", encrypted_key=encrypt_secret("k" * 20))
        with self.assertRaises(TranslationEngineError) as ctx:
            get_engine("deepl", self.researcher).translate(self.segs("文。"), "ja", "fr")
        self.assertEqual(ctx.exception.kind, "config")
        EngineSetting.objects.all().delete()
        with self.assertRaises(TranslationEngineError) as ctx:
            get_engine("deepl", self.researcher).translate(self.segs("文。"), "ja", "fr")
        self.assertEqual(ctx.exception.code, "cle_refusee")

    def test_usage_test_sends_no_text(self):
        rec = self.use(DeepLEngine, Recorder((200, fixture("deepl_usage.json"))))
        engine = self.deepl()
        message = engine.test()
        self.assertIn("180 118", message)
        self.assertEqual(rec.requests[0].method, "GET")
        self.assertEqual(rec.requests[0].url.path, "/v2/usage")
        self.assertEqual(engine.setting.quota_info["character_limit"], 500000)

    def test_unsupported_pair(self):
        with self.assertRaises(TranslationEngineError) as ctx:
            self.deepl().translate(self.segs("文。"), "ja", "en")  # japonais → anglais reporté (B2)
        self.assertEqual((ctx.exception.kind, ctx.exception.code), ("unsupported", "langue_non_prise"))


class GoogleTests(EngineTestCase):
    def test_translation_request_and_result(self):
        rec = self.use(GoogleBasicEngine, Recorder((200, fixture("google_translate_ok.json"))))
        result = self.google().translate(self.segs("一。", "二。"), "en", "fr")
        self.assertEqual(result.translations["1"], "Ceci est une première phrase fictive.")
        req = rec.requests[0]
        self.assertEqual(req.url.path, "/language/translate/v2")
        self.assertEqual(req.url.params["key"], FAKE_GOOGLE_KEY)
        body = json.loads(req.content)
        self.assertEqual((body["source"], body["target"], body["format"]), ("en", "fr", "text"))

    def test_errors_are_classified(self):
        cases = [((400, fixture("google_error_key.json")), "config", "cle_refusee"),
                 ((403, {"error": {"code": 403, "message": "Forbidden", "status": "PERMISSION_DENIED"}}),
                  "config", "cle_refusee"),
                 ((429, fixture("google_error_quota.json")), "unavailable", "quota_depasse"),
                 ((200, {"data": {"translations": [{"translatedText": "seul"}]}}), "unparsable", "reponse_vide")]
        for response, kind, code in cases:
            with self.subTest(status=response[0]):
                self.use(GoogleBasicEngine, Recorder(response))
                with self.assertRaises(TranslationEngineError) as ctx:
                    self.google().translate(self.segs(SECRET_TEXT, "二。"), "ja", "fr")
                self.assertEqual((ctx.exception.kind, ctx.exception.code), (kind, code))
                self.assert_no_secret(ctx.exception)

    def test_test_button_translates_a_fixed_fictitious_phrase(self):
        rec = self.use(GoogleBasicEngine, Recorder((200, {"data": {"translations": [{"translatedText": "Essai."}]}})))
        self.assertIn("Essai.", self.google().test())
        self.assertEqual(json.loads(rec.requests[0].content)["q"], ["これは動作確認のための架空の文です。"])


class ArgosTests(EngineTestCase):
    def enable(self):
        EngineSetting.objects.create(user=self.researcher, engine="argos", enabled=True)
        return get_engine("argos", self.researcher)

    def test_not_activated_without_setting(self):
        self.assertFalse(get_engine("argos", self.researcher).status().usable)

    def test_simulation_when_service_is_not_activated(self):
        engine = self.enable()
        status = engine.status()
        self.assertTrue(status.simulated)
        result = engine.translate(self.segs("架空の文。"), "ja", "fr")
        self.assertTrue(result.simulated)
        self.assertEqual(result.translations["1"], SIMULATION_PREFIX + "架空の文。")
        self.assertEqual(result.chars_sent, 0)

    @override_settings(TRANSLATION_ARGOS_URL="http://argos:5000")
    def test_real_translation_through_english_pivot(self):
        def reply(request):
            if request.url.path == "/health":
                return httpx.Response(200, json=fixture("argos_health.json"))
            body = json.loads(request.content)
            return httpx.Response(200, json={"translations": [f"FR:{t}" for t in body["texts"]],
                                              "path": ["ja", "en", "fr"]})

        ArgosEngine.transport = httpx.MockTransport(reply)
        engine = self.enable()
        self.assertEqual(engine.status().label, "Disponible hors ligne")
        result = engine.translate(self.segs("架空の文。"), "ja", "fr")
        self.assertFalse(result.simulated)
        self.assertEqual(result.translations["1"], "FR:架空の文。")
        self.assertIn("ja→en 1.1", result.engine_version)
        self.assertIn("en→fr 1.9", result.engine_version)

    @override_settings(TRANSLATION_ARGOS_URL="http://argos:5000")
    def test_simulation_when_packages_are_missing_or_service_down(self):
        ArgosEngine.transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"argos_version": "1.11.0", "packages": []}))
        engine = self.enable()
        self.assertIn("paquets", engine.status().detail)
        self.assertTrue(engine.translate(self.segs("文。"), "ja", "fr").simulated)
        ArgosEngine.transport = httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("arrêt")))
        self.assertTrue(engine.status().simulated)


class AIEngineTests(EngineTestCase):
    def setUp(self):
        super().setUp()
        AIProviderCredential.objects.create(user=self.researcher, provider="anthropic", status="ok",
                                            encrypted_key=encrypt_secret("sk-ant-fictif-0123456789"))
        self.prompts = []
        self.reply_text = json.dumps(fixture("ai_translation_ok.json"), ensure_ascii=False)
        self.status_code = 200

        def reply(request):
            self.prompts.append(json.loads(request.content))
            if self.status_code != 200:
                return httpx.Response(self.status_code, json={})
            return httpx.Response(200, json={"content": [{"type": "text", "text": self.reply_text}],
                                             "usage": {"input_tokens": 100, "output_tokens": 40},
                                             "model": "claude-fictif"})

        AnthropicProvider.transport = httpx.MockTransport(reply)
        self.engine = get_engine("ai", self.researcher, ai_provider="anthropic", ai_model="claude-fictif")

    def test_translation_with_glossary_and_variety(self):
        result = self.engine.translate(self.segs("元禄の架空の文。", "二つ目。"), "ja", "fr",
                                       glossary=[("元禄", "ère Genroku"), ("寛永", "ère Kan'ei")], variety="classical")
        self.assertEqual(result.translations["1"], "Ceci est une première phrase fictive.")
        self.assertEqual((result.tokens_in, result.tokens_out, result.model), (100, 40, "claude-fictif"))
        prompt = self.prompts[0]["messages"][0]["content"]
        self.assertIn("元禄 → ère Genroku", prompt)
        self.assertNotIn("寛永", prompt, "seules les entrées présentes dans les segments sont envoyées")
        self.assertIn("japonais classique", prompt)

    def test_missing_extra_or_duplicate_ids_are_rejected(self):
        for payload in ({"translations": [{"id": "1", "text": "a"}]},
                        {"translations": [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}, {"id": "9", "text": "c"}]},
                        {"translations": [{"id": "1", "text": "a"}, {"id": "1", "text": "b"}]},
                        {"autre": []}):
            with self.subTest(payload=payload):
                self.reply_text = json.dumps(payload)
                with self.assertRaises(TranslationEngineError) as ctx:
                    self.engine.translate(self.segs("一。", "二。"), "ja", "fr")
                self.assertEqual((ctx.exception.kind, ctx.exception.code), ("unparsable", "reponse_vide"))

    def test_comment_outside_json_and_comment_in_text_raise_alerts(self):
        self.reply_text = ('Voici la traduction : {"translations": [{"id": "1", "text": "Traduction : une phrase."}, '
                           '{"id": "2", "text": "Deux."}]}')
        result = self.engine.translate(self.segs("一。", "二。"), "ja", "fr")
        self.assertIn("commentaire hors traduction", " ".join(result.alerts["1"]))
        self.assertTrue(any("commentaire" in a for a in result.alerts["1"][1:]))

    def test_consent_rules(self):
        profile = active_profile(self.researcher)
        profile.translation_enabled = False
        profile.save()
        self.assertFalse(self.engine.status().usable)
        with self.assertRaises(TranslationEngineError) as ctx:
            self.engine.translate(self.segs("一。"), "ja", "fr")
        self.assertEqual(ctx.exception.kind, "config")
        self.assertEqual(self.prompts, [], "aucun envoi sans consentement")
        profile.translation_enabled, profile.mode = True, "disabled"
        profile.save()
        self.assertFalse(self.engine.status().usable)

    def test_provider_errors_are_converted(self):
        self.status_code = 401
        with self.assertRaises(TranslationEngineError) as ctx:
            self.engine.translate(self.segs("一。"), "ja", "fr")
        self.assertEqual((ctx.exception.kind, ctx.exception.code, ctx.exception.http_status),
                         ("config", "cle_refusee", 401))

    def test_prompts_file_is_versioned(self):
        self.assertTrue(ai_module.prompts()["version"])


class JournalTests(EngineTestCase):
    def test_incident_without_text_or_key(self):
        self.use(DeepLEngine, Recorder((456, fixture("deepl_error.json"))))
        with self.assertRaises(TranslationEngineError) as ctx:
            self.deepl().translate(self.segs(SECRET_TEXT), "ja", "fr")
        incident = record_translation_error(ctx.exception, engine="deepl", operation="Essai")
        self.assertEqual((incident.module, incident.category), ("traduction", "quota_depasse"))
        occurrence = incident.occurrences.get()
        dump = json.dumps(occurrence.context, ensure_ascii=False) + incident.title + occurrence.message
        for secret in (SECRET_TEXT, FAKE_DEEPL_KEY):
            self.assertNotIn(secret, dump)
        self.assertEqual(occurrence.context["chars"], len(SECRET_TEXT))

    def test_user_choices_are_not_incidents(self):
        with self.assertRaises(TranslationEngineError) as ctx:
            self.deepl().translate(self.segs("文。"), "ja", "en")
        self.assertIsNone(record_translation_error(ctx.exception, engine="deepl"))
        self.assertFalse(Incident.objects.exists())


class EnginesPageTests(EngineTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)

    def test_page_access(self):
        self.assertEqual(self.client.get("/traduction/moteurs/").status_code, 200)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/traduction/moteurs/").status_code, 403)

    def test_key_is_encrypted_and_never_shown(self):
        self.client.post("/traduction/moteurs/deepl/", {"action": "save", "api_key": FAKE_DEEPL_KEY, "plan": "free",
                                                         "enabled": "on"})
        setting = EngineSetting.objects.get(user=self.researcher, engine="deepl")
        self.assertTrue(setting.has_key)
        self.assertNotIn(FAKE_DEEPL_KEY, setting.encrypted_key)
        page = self.client.get("/traduction/moteurs/")
        self.assertNotContains(page, FAKE_DEEPL_KEY)
        self.assertContains(page, "Clé enregistrée (chiffrée)")
        # champ vide = clé conservée
        self.client.post("/traduction/moteurs/deepl/", {"action": "save", "api_key": "", "plan": "pro", "enabled": "on"})
        setting.refresh_from_db()
        self.assertTrue(setting.has_key)
        self.assertEqual(setting.plan, "pro")

    def test_test_button_success_and_failure(self):
        self.client.post("/traduction/moteurs/deepl/", {"action": "save", "api_key": FAKE_DEEPL_KEY, "plan": "free",
                                                         "enabled": "on"})
        self.use(DeepLEngine, Recorder((200, fixture("deepl_usage.json"))))
        self.client.post("/traduction/moteurs/deepl/", {"action": "test"})
        self.assertEqual(EngineSetting.objects.get(engine="deepl").status, "ok")
        self.use(DeepLEngine, Recorder((403, fixture("deepl_error.json"))))
        response = self.client.post("/traduction/moteurs/deepl/", {"action": "test"}, follow=True)
        self.assertContains(response, "Échec du test")
        self.assertEqual(EngineSetting.objects.get(engine="deepl").status, "error")
        self.assertTrue(Incident.objects.filter(module="traduction", category="cle_refusee").exists())

    def test_revoke(self):
        self.client.post("/traduction/moteurs/google_basic/", {"action": "save", "api_key": FAKE_GOOGLE_KEY,
                                                                "enabled": "on"})
        self.client.post("/traduction/moteurs/google_basic/", {"action": "revoke"})
        setting = EngineSetting.objects.get(engine="google_basic")
        self.assertFalse(setting.has_key)
        self.assertEqual(setting.encrypted_key, "")

    def test_settings_are_per_user(self):
        self.client.post("/traduction/moteurs/deepl/", {"action": "save", "api_key": FAKE_DEEPL_KEY, "plan": "free",
                                                         "enabled": "on"})
        self.client.force_login(self.admin)
        page = self.client.get("/traduction/moteurs/")
        self.assertNotContains(page, "Clé enregistrée (chiffrée)")
        self.assertFalse(EngineSetting.objects.filter(user=self.admin).exists())

    def test_preferences_validation(self):
        base = {"confirmation_threshold": 20000}
        self.client.post("/traduction/moteurs/choix/", {**base, "default_engine": "ai"})
        self.assertEqual(TranslationPreference.objects.get(user=self.researcher).default_engine, "")
        self.client.post("/traduction/moteurs/choix/", {**base, "default_engine": "deepl", "second_engine": "deepl"})
        self.assertEqual(TranslationPreference.objects.get(user=self.researcher).default_engine, "")
        self.client.post("/traduction/moteurs/choix/", {**base, "default_engine": "deepl", "second_engine": "ai",
                                                         "second_ai_provider": "anthropic",
                                                         "second_ai_model": "claude-fictif"})
        pref = TranslationPreference.objects.get(user=self.researcher)
        self.assertEqual((pref.default_engine, pref.second_engine, pref.second_ai_provider),
                         ("deepl", "ai", "anthropic"))

    def test_saving_settings_never_translates(self):
        rec = self.use(DeepLEngine, Recorder((200, fixture("deepl_translate_ok.json"))))
        self.client.post("/traduction/moteurs/deepl/", {"action": "save", "api_key": FAKE_DEEPL_KEY, "plan": "free",
                                                         "enabled": "on"})
        self.client.post("/traduction/moteurs/choix/", {"confirmation_threshold": 20000, "default_engine": "deepl"})
        self.client.get("/traduction/moteurs/")
        self.assertEqual(rec.requests, [])
