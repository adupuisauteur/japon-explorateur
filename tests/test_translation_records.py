"""Évolution 1.3.0 — lot 5 : traduction des notices.

- boutons « Traduire… » de la fiche et de la Bibliothèque vers le module de traduction ;
- traduction IA de la 1.2.0 retirée de l'interface, code conservé ;
- valider une traduction de notice = l'adopter dans la fiche, une seule validée par champ (décision) ;
- validation réservée à l'administrateur (C2) ;
- reprise unique de l'ancien réglage IA de traduction ; anciens réglages IA conservés.
Données fictives ; moteur DeepL simulé.
"""
import json

import httpx

from apps.ai.crypto import encrypt_secret
from apps.ai.preferences import active_profile
from apps.catalog.models import EditorialContent, RecordVersion
from apps.catalog.services import upsert_record
from apps.library.models import LibraryEntry
from apps.translation import services
from apps.translation.engines.deepl import DeepLEngine
from apps.translation.models import EngineSetting, TranslationJob, TranslationPreference

from .helpers import AppTestCase, acknowledge_terms


class RecordTranslationTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.sent = []

        def reply(request):
            texts = json.loads(request.content)["text"]
            self.sent.extend(texts)
            return httpx.Response(200, json={"translations": [{"text": f"FR {t}"} for t in texts]})

        DeepLEngine.transport = httpx.MockTransport(reply)
        self.addCleanup(setattr, DeepLEngine, "transport", None)
        for user in (self.admin, self.researcher):
            EngineSetting.objects.create(user=user, engine="deepl", plan="free", status="ok",
                                         encrypted_key=encrypt_secret("fake-deepl-key-0000000000"))
            TranslationPreference.objects.create(user=user, default_engine="deepl", migrated_from_ai=True)
            acknowledge_terms(user, "deepl")
        cat = self.catalogue("codh-pmjt")
        self.record, _ = upsert_record(cat, {"source_id": "N1", "original_title": "架空の書",
                                             "description_original": "架空の解題。", "subjects_original": "架空の主題"})

    def translate_as(self, user, fields=("original_title", "description_original")):
        self.client.force_login(user)
        response = self.client.post("/traduction/notices/preparer/", {"records": self.record.record_id,
                                                                     "fields": list(fields), "engine": "default"})
        job = TranslationJob.objects.latest("pk")
        self.assertRedirects(response, f"/traduction/taches/{job.pk}/", fetch_redirect_response=False)
        self.assertEqual(self.sent, [], "rien n'est envoyé à la préparation")
        self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm"})
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        return job


class EntryPointTests(RecordTranslationTestCase):
    def test_record_page_links_to_the_module(self):
        self.client.force_login(self.researcher)
        page = self.client.get(self.record.get_absolute_url())
        self.assertContains(page, f"/traduction/notices/{self.record.record_id}/")
        self.assertNotContains(page, 'value="translation"', msg_prefix="ancienne traduction IA retirée de la fiche")
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get(self.record.get_absolute_url()), "/traduction/notices/")

    def test_library_selection_goes_to_the_module(self):
        self.client.force_login(self.researcher)
        entry = LibraryEntry.objects.create(user=self.researcher, record=self.record)
        page = self.client.get("/bibliotheque/")
        self.assertContains(page, 'value="translate"')
        self.assertNotContains(page, 'value="ai_translation"')
        response = self.client.post("/bibliotheque/lot/", {"entry_ids": [entry.pk], "action": "translate"})
        self.assertRedirects(response, f"/traduction/notices/preparer/?records={self.record.record_id}",
                             fetch_redirect_response=False)
        page = self.client.get(f"/traduction/notices/preparer/?records={self.record.record_id}")
        self.assertContains(page, "架空の書")
        self.assertContains(page, "Rien n'est envoyé avant votre confirmation")


class ValidationTests(RecordTranslationTestCase):
    def test_researcher_proposes_admin_validates_and_adopts(self):
        self.translate_as(self.researcher)
        title = EditorialContent.objects.get(record=self.record, target_field="original_title")
        self.assertEqual((title.origin, title.status, title.content), ("mt", "proposed", "FR 架空の書"))
        self.assertEqual(self.client.post(f"/traduction/notices/decision/{title.pk}/",
                                          {"action": "validate"}).status_code, 403)
        self.client.force_login(self.admin)
        page = self.client.get(f"/traduction/notices/{self.record.record_id}/")
        self.assertContains(page, "Valider et adopter")
        self.client.post(f"/traduction/notices/decision/{title.pk}/", {"action": "validate"})
        self.record.refresh_from_db()
        self.assertEqual((self.record.translated_title, self.record.translated_title_origin), ("FR 架空の書", "mt"))
        self.assertEqual(self.record.original_title, "架空の書", "la notice source n'est jamais modifiée")
        self.assertTrue(RecordVersion.objects.filter(record=self.record, change_type="editorial",
                                                     changed_fields=["translated_title"]).exists())

    def test_only_one_validated_translation_per_field(self):
        first = EditorialContent.objects.create(record=self.record, kind="translation", target_field="original_title",
                                                source_text="架空の書", content="Premier", origin="user",
                                                status="validated")
        self.translate_as(self.admin)
        second = EditorialContent.objects.filter(target_field="original_title", origin="mt").get()
        self.client.post(f"/traduction/notices/decision/{second.pk}/", {"action": "validate"})
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.status, second.status), ("proposed", "validated"))
        self.record.refresh_from_db()
        self.assertEqual(self.record.translated_title, "FR 架空の書")

    def test_validation_on_record_page_also_adopts(self):
        ed = EditorialContent.objects.create(record=self.record, kind="translation", target_field="original_title",
                                             source_text="架空の書", content="Livre fictif", origin="ai")
        self.client.force_login(self.admin)
        page = self.client.get(self.record.get_absolute_url())
        self.assertContains(page, "Valider et adopter")
        self.client.post(f"/notices/editorial/{ed.pk}/decision/", {"action": "validate"})
        self.record.refresh_from_db()
        self.assertEqual((self.record.translated_title, self.record.translated_title_origin), ("Livre fictif", "ai"))

    def test_non_adoptable_field_is_validated_without_touching_the_record(self):
        self.translate_as(self.admin, fields=("subjects_original",))
        ed = EditorialContent.objects.get(target_field="subjects_original")
        self.client.post(f"/traduction/notices/decision/{ed.pk}/", {"action": "validate"})
        ed.refresh_from_db()
        self.assertEqual(ed.status, "validated")
        self.record.refresh_from_db()
        self.assertEqual(self.record.translated_title, "")

    def test_deleting_a_validated_translation_requires_confirmation(self):
        ed = EditorialContent.objects.create(record=self.record, kind="translation", target_field="original_title",
                                             content="Livre fictif", origin="mt", status="validated", author=self.admin)
        self.client.force_login(self.admin)
        self.client.post(f"/traduction/notices/decision/{ed.pk}/", {"action": "delete"})
        self.assertTrue(EditorialContent.objects.filter(pk=ed.pk).exists())
        self.client.post(f"/traduction/notices/decision/{ed.pk}/", {"action": "delete", "confirm_validated": "1"})
        self.assertFalse(EditorialContent.objects.filter(pk=ed.pk).exists())

    def test_page_shows_original_and_versions(self):
        self.translate_as(self.researcher)
        page = self.client.get(f"/traduction/notices/{self.record.record_id}/")
        self.assertContains(page, "Original (jamais modifié)")
        self.assertContains(page, "FR 架空の解題。")
        self.assertContains(page, "La validation est réservée à l'administrateur")


class AIPreferencesTests(RecordTranslationTestCase):
    def test_translation_line_hidden_but_old_value_kept(self):
        profile = active_profile(self.admin)
        profile.function_overrides = {"translation": {"provider": "anthropic", "model": "claude-ancien"},
                                      "summary": {"provider": "gemini", "model": "gemini-x"}}
        profile.save()
        self.client.force_login(self.admin)
        page = self.client.get("/ia/preferences/")
        self.assertNotContains(page, 'name="ov_translation_provider"')
        self.assertContains(page, "Traduction → Moteurs")
        self.client.post(f"/ia/preferences/?profile={profile.pk}", {
            "name": profile.name, "mode": "demand", "translation_enabled": "on", "alert_threshold_pct": 80,
            "ov_summary_provider": "gemini", "ov_summary_model": "gemini-x"})
        profile.refresh_from_db()
        self.assertEqual(profile.function_overrides["translation"], {"provider": "anthropic", "model": "claude-ancien"})


class TakeoverTests(AppTestCase):
    def test_previous_ai_translation_setting_becomes_the_default_engine_once(self):
        profile = active_profile(self.researcher)
        profile.default_provider, profile.default_model = "anthropic", "claude-ancien"
        profile.save()
        pref = services.ensure_preference(self.researcher)
        self.assertEqual((pref.default_engine, pref.default_ai_provider, pref.default_ai_model),
                         ("ai", "anthropic", "claude-ancien"))
        pref.default_engine = "deepl"
        pref.save()
        self.assertEqual(services.ensure_preference(self.researcher).default_engine, "deepl", "reprise unique")
        profile.refresh_from_db()
        self.assertEqual(profile.default_provider, "anthropic", "préférences IA inchangées")

    def test_no_takeover_when_ai_translation_was_not_allowed(self):
        profile = active_profile(self.researcher)
        profile.default_provider, profile.default_model, profile.translation_enabled = "anthropic", "claude", False
        profile.save()
        self.assertEqual(services.ensure_preference(self.researcher).default_engine, "")
