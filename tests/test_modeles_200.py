"""2.0.0 — lot 8 : choix du modèle d'IA dans une liste. Réponses des fournisseurs simulées ; clés fictives."""
from pathlib import Path
from unittest import mock

import httpx
from django.conf import settings

from apps.ai.crypto import encrypt_secret
from apps.ai.models import AIModelPrice, AIProviderCredential
from apps.ai.providers import AnthropicProvider, GeminiProvider, OpenAIProvider, ProviderError, text_models
from apps.translation.models import TranslationProject

from .helpers import AppTestCase

ROOT = Path(settings.BASE_DIR)
OPENAI_LIST = ["gpt-4o", "gpt-4o-mini", "dall-e-3", "gpt-image-1", "text-embedding-3-small", "whisper-1", "tts-1",
               "omni-moderation-latest", "gpt-4o-realtime-preview", "gpt-4o-mini-transcribe", "davinci-002",
               "gpt-4o-audio-preview", "o3-mini"]


class FilterTests(AppTestCase):
    def test_only_text_models_are_kept(self):
        self.assertEqual(text_models("openai", OPENAI_LIST), ["gpt-4o", "gpt-4o-mini", "o3-mini"])
        self.assertEqual(text_models("gemini", ["gemini-2.5-pro", "gemini-2.5-flash-preview-tts", "imagen-4",
                                                "text-embedding-004", "gemini-2.0-flash"]),
                         ["gemini-2.5-pro", "gemini-2.0-flash"])
        self.assertEqual(text_models("anthropic", ["claude-fictif-1", "claude-fictif-1", ""]), ["claude-fictif-1"])
        self.assertEqual(text_models("openai_compatible", ["llama-fictif", "nomic-embed-text", "bge-reranker"]),
                         ["llama-fictif"])

    def test_connection_test_stores_the_filtered_list(self):
        self.client.force_login(self.researcher)
        AIProviderCredential.objects.create(user=self.researcher, provider="openai", status="untested",
                                            encrypted_key=encrypt_secret("sk-fictif-0123456789abcdef"))
        self.addCleanup(setattr, OpenAIProvider, "transport", None)
        OpenAIProvider.transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"data": [{"id": m} for m in OPENAI_LIST]}))
        response = self.client.post("/ia/fournisseurs/openai/", {"action": "test"}, follow=True)
        self.assertContains(response, "3 modèle(s) de texte disponible(s)")
        self.assertEqual(AIProviderCredential.objects.get(user=self.researcher).available_models,
                         ["gpt-4o", "gpt-4o-mini", "o3-mini"])


class PickerTests(AppTestCase):
    VALS = {"provider_field": "default_provider", "model_field": "default_model", "provider_id": "id_default_provider",
            "model_id": "id_default_model"}

    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)
        self.cred = AIProviderCredential.objects.create(
            user=self.researcher, provider="anthropic", status="ok",
            encrypted_key=encrypt_secret("sk-ant-fictif-0123456789"),
            available_models=["claude-fictif-haiku", "claude-fictif-sonnet"])
        AIModelPrice.objects.create(provider="anthropic", model_prefix="claude-fictif-sonnet", input_per_million=3,
                                    output_per_million=15)

    def picker(self, provider="anthropic", model=""):
        return self.client.get("/ia/modeles/choix/", {**self.VALS, "default_provider": provider,
                                                       "default_model": model}).content.decode()

    def test_list_with_prices_free_entry_and_date(self):
        html = self.picker(model="claude-fictif-sonnet")
        self.assertIn('data-model-select="#id_default_model"', html)
        self.assertIn('<option value="claude-fictif-sonnet" selected>claude-fictif-sonnet — ≈ 3 $ / 15 $ par million '
                      'de jetons</option>', html)
        self.assertIn('<option value="claude-fictif-haiku">claude-fictif-haiku</option>', html)
        self.assertIn("Autre modèle (saisie libre)…", html)
        self.assertIn("2 modèles de texte", html)
        self.assertIn("Actualiser la liste", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("n'apparaît pas", html)

    def test_saved_model_missing_from_the_list_is_kept_with_a_warning(self):
        html = self.picker(model="claude-retire")
        self.assertIn('<option value="__libre__" selected>', html)
        self.assertIn("Le modèle « claude-retire » n'apparaît pas dans la liste de ce fournisseur", html)
        self.assertIn("Il est conservé tel quel", html)

    def test_no_provider_no_key_empty_list(self):
        self.assertIn("Choisissez d'abord le fournisseur", self.picker(provider=""))
        self.assertIn("Aucune clé enregistrée pour Google (Gemini)", self.picker(provider="gemini"))
        self.cred.available_models = []
        self.cred.save()
        self.assertIn("La liste des modèles de Anthropic (Claude) est vide", self.picker())

    def test_old_unfiltered_lists_are_filtered_on_display(self):
        AIProviderCredential.objects.create(user=self.researcher, provider="openai", status="ok",
                                            encrypted_key=encrypt_secret("sk-fictif-0123456789abcdef"),
                                            available_models=OPENAI_LIST)
        html = self.picker(provider="openai")
        self.assertIn('value="gpt-4o"', html)
        self.assertNotIn("dall-e-3", html)
        self.assertNotIn("whisper-1", html)

    def test_refresh_asks_the_provider_only_on_request(self):
        self.addCleanup(setattr, AnthropicProvider, "transport", None)
        calls = []

        def reply(request):
            calls.append(str(request.url))
            return httpx.Response(200, json={"data": [{"id": "claude-fictif-opus"}], "has_more": False})

        AnthropicProvider.transport = httpx.MockTransport(reply)
        self.picker()
        self.assertEqual(calls, [])  # afficher la liste n'interroge jamais le fournisseur
        html = self.client.post("/ia/modeles/actualiser/", {**self.VALS, "default_provider": "anthropic",
                                                             "default_model": ""}).content.decode()
        self.assertEqual(len(calls), 1)
        self.assertIn('value="claude-fictif-opus"', html)
        self.cred.refresh_from_db()
        self.assertEqual(self.cred.available_models, ["claude-fictif-opus"])
        self.assertIsNotNone(self.cred.last_tested_at)

    def test_refresh_failure_keeps_the_list_and_shows_the_error(self):
        with mock.patch.object(AnthropicProvider, "list_models", side_effect=ProviderError("Clé refusée (401).")):
            html = self.client.post("/ia/modeles/actualiser/", {**self.VALS, "default_provider": "anthropic"}
                                    ).content.decode()
        self.assertIn("Actualisation impossible : Clé refusée (401).", html)
        self.assertIn('value="claude-fictif-haiku"', html)
        self.cred.refresh_from_db()
        self.assertEqual(self.cred.status, "error")
        self.assertEqual(self.cred.available_models, ["claude-fictif-haiku", "claude-fictif-sonnet"])

    def test_access(self):
        self.assertEqual(self.client.get("/ia/modeles/actualiser/").status_code, 405)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/ia/modeles/choix/", self.VALS).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get("/ia/modeles/choix/", self.VALS).status_code, 302)

    def test_other_users_keys_are_never_used(self):
        AIProviderCredential.objects.create(user=self.admin, provider="gemini", status="ok",
                                            encrypted_key=encrypt_secret("cle-gemini-fictive-0123"),
                                            available_models=["gemini-fictif"])
        self.assertIn("Aucune clé enregistrée pour Google (Gemini)", self.picker(provider="gemini"))
        with mock.patch.object(GeminiProvider, "list_models") as listing:
            self.client.post("/ia/modeles/actualiser/", {**self.VALS, "default_provider": "gemini"})
        listing.assert_not_called()


class ScreensTests(AppTestCase):
    """Les cinq écrans du cahier (et la fiche projet relevée à l'audit) proposent la liste."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)

    def test_ai_preferences_default_and_per_function(self):
        page = self.client.get("/ia/preferences/").content.decode()
        self.assertIn('id="mp-id_default_model"', page)
        self.assertIn('hx-include="#id_default_provider, #id_default_model"', page)
        self.assertIn('id="mp-ov-summary-model"', page)
        self.assertIn('hx-trigger="load, change from:#ov-summary-provider"', page)

    def test_translation_engines_project_form_and_evaluation(self):
        page = self.client.get("/traduction/moteurs/").content.decode()
        for name in ("default_ai", "second_ai"):
            self.assertIn(f'id="mp-id_{name}_model"', page)
        page = self.client.get("/traduction/projets/nouveau/").content.decode()
        self.assertIn('id="mp-id_default_ai_model"', page)
        self.assertIn('id="mp-id_second_ai_model"', page)
        project = TranslationProject.objects.create(owner=self.researcher, title="Corpus fictif",
                                                    is_reference_corpus=True)
        page = self.client.get("/traduction/evaluation/").content.decode()
        self.assertIn(f'id="mp-ai-model-{project.pk}-1"', page)
        self.assertIn(f'"provider_field": "ai_provider_2"', page)

    def test_unavailable_page(self):
        text = (ROOT / "templates/ai/unavailable.html").read_text(encoding="utf-8")
        self.assertIn('provider_id="alt-provider"', text)
        self.assertNotIn("required aria-label=\"Modèle\"", text)  # champ masqué quand un modèle est choisi

    def test_saved_value_is_still_the_text_field(self):
        self.client.post("/traduction/moteurs/choix/", {"default_engine": "ai", "default_ai_provider": "anthropic",
                                                        "default_ai_model": "claude-fictif-sonnet",
                                                        "confirmation_threshold": 5000})
        from apps.translation.models import TranslationPreference

        self.assertEqual(TranslationPreference.objects.get(user=self.researcher).default_ai_model,
                         "claude-fictif-sonnet")

    def test_front_end_sync(self):
        js = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
        self.assertIn('select.getAttribute("data-model-select")', js)
        self.assertIn('select.value === "__libre__"', js)
