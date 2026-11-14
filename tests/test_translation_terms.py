"""Évolution 1.3.0 — conditions des fournisseurs avant le premier envoi (cahier des charges § 13).

DeepL simulé ; aucun envoi réel. Les textes sont fictifs.
"""
import json
from unittest import mock

import httpx

from apps.accounts.models import User
from apps.ai.crypto import encrypt_secret
from apps.core.models import AuditLog
from apps.translation import glossary as G
from apps.translation import projects as P
from apps.translation import terms
from apps.translation.engines.deepl import DeepLEngine
from apps.translation.models import (EngineSetting, Glossary, ProjectGlossary, TranslationJob, TranslationPreference,
                                     TranslationProject)

from .helpers import AppTestCase, set_argos_demo


class ReferenceFileTests(AppTestCase):
    def test_every_online_provider_has_a_dated_summary_with_official_sources(self):
        data = json.loads(terms.TERMS_FILE.read_text(encoding="utf-8"))
        providers = data["providers"]
        for key in ("deepl", "google_basic", "ai:openai", "ai:anthropic", "ai:gemini", "ai:openai_compatible"):
            with self.subTest(key=key):
                entry = providers[key]
                self.assertRegex(entry["verified_on"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(entry["points"])
                for source in entry["sources"]:
                    self.assertTrue(source["url"].startswith("https://"))
        self.assertTrue(all(providers[k]["sources"] for k in providers if k != "ai:openai_compatible"))
        self.assertIn("gratuite", " ".join(providers["deepl"]["points"]))  # différence gratuit / payant

    def test_local_engine_needs_nothing(self):
        self.assertIsNone(terms.needed(self.researcher, "argos"))
        self.assertEqual(terms.provider_key("ai", "gemini"), "ai:gemini")
        self.assertEqual(terms.needed(self.researcher, "ai", "anthropic")["name"], "Anthropic (API Claude)")


class FirstSendTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.researcher
        self.client.force_login(self.owner)
        self.sent = []

        def reply(request):
            body = json.loads(request.content) if request.content else {}
            if request.url.path == "/v2/translate":
                self.sent.extend(body["text"])
                return httpx.Response(200, json={"translations": [{"text": "FR"} for _ in body["text"]]})
            if request.url.path == "/v3/languages":
                return httpx.Response(200, json=[{"lang": "ja"}, {"lang": "fr"}])
            return httpx.Response(201, json={"glossary_id": "gl-1", "dictionaries": []})

        DeepLEngine.transport = httpx.MockTransport(reply)
        self.addCleanup(setattr, DeepLEngine, "transport", None)
        EngineSetting.objects.create(user=self.owner, engine="deepl", plan="free", status="ok",
                                     encrypted_key=encrypt_secret("fake-deepl-key-0000000000"))
        EngineSetting.objects.create(user=self.owner, engine="argos", enabled=True)
        set_argos_demo(True)  # 2.0.0 (D4) : Argos sert ici en mode démonstration
        TranslationPreference.objects.create(user=self.owner, default_engine="deepl", migrated_from_ai=True)
        self.project = TranslationProject.objects.create(owner=self.owner, title="Projet fictif")
        self.document = P.create_document(self.project, title="Doc", text="架空の文。")

    def prepare(self, engine="default"):
        self.client.post(f"/traduction/documents/{self.document.pk}/lot/",
                         {"scope": "untranslated", "action": "translate", "engine": engine})
        return TranslationJob.objects.latest("pk")

    def test_summary_shown_and_acknowledgement_required_before_first_send(self):
        job = self.prepare()
        page = self.client.get(f"/traduction/taches/{job.pk}/")
        self.assertContains(page, "Avant le premier envoi à DeepL API")
        self.assertContains(page, 'name="terms_acknowledged"')
        self.assertContains(page, "https://www.deepl.com/en/privacy")
        response = self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm"}, follow=True)
        self.assertContains(response, "lisez le résumé de ses conditions")
        job.refresh_from_db()
        self.assertEqual((job.status, self.sent), ("draft", []))
        self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm", "terms_acknowledged": "1"})
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertEqual(self.sent, ["架空の文。"])
        log = AuditLog.objects.get(action=terms.ACTION)
        self.assertEqual(log.details["provider"], "deepl")

    def test_not_asked_again_until_the_summary_is_reverified(self):
        terms.acknowledge(self.owner, "deepl")
        job = self.prepare()
        self.assertNotContains(self.client.get(f"/traduction/taches/{job.pk}/"), 'name="terms_acknowledged"')
        self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm"})
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        newer = json.loads(terms.TERMS_FILE.read_text(encoding="utf-8"))
        newer["providers"]["deepl"]["verified_on"] = "2027-01-01"
        with mock.patch.object(terms, "_table", return_value=newer):
            self.assertIsNotNone(terms.needed(self.owner, "deepl"))
        other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        self.assertIsNotNone(terms.needed(other, "deepl"))  # propre à chaque compte

    def test_local_engine_is_never_asked(self):
        pref = TranslationPreference.objects.get(user=self.owner)
        pref.default_engine = "argos"
        pref.save()
        job = self.prepare()
        self.assertEqual(job.engine, "argos")
        self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm"})
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertFalse(AuditLog.objects.filter(action=terms.ACTION).exists())

    def test_glossary_sent_to_deepl_requires_acknowledgement(self):
        glossary = Glossary.objects.create(owner=self.owner, name="Glossaire fictif")
        G.save_entry(glossary, {"source_term": "江戸", "target_term": "Edo"})
        ProjectGlossary.objects.create(project=self.project, glossary=glossary)
        self.assertContains(self.client.get(f"/traduction/glossaires/{glossary.pk}/"), "Avant le premier envoi à DeepL")
        url = f"/traduction/glossaires/{glossary.pk}/deepl/"
        response = self.client.post(url, {"action": "send", "confirm": "1"}, follow=True)
        self.assertContains(response, "Premier envoi à DeepL")
        self.assertEqual(Glossary.objects.get(pk=glossary.pk).remote_copies, {})
        self.client.post(url, {"action": "send", "confirm": "1", "terms_acknowledged": "1"})
        self.assertIn(str(self.owner.pk), Glossary.objects.get(pk=glossary.pk).remote_copies)
        self.assertFalse(terms.needed(self.owner, "deepl"))

    def test_comparison_requires_acknowledgement(self):
        self.project.is_reference_corpus = True
        self.project.save()
        self.client.post(f"/traduction/evaluation/{self.project.pk}/comparer/", {"engines": ["deepl"]})
        job = TranslationJob.objects.get(kind="evaluation")
        page = self.client.get(f"/traduction/evaluation/{self.project.pk}/comparaison/", {"c": job.scope_label})
        self.assertContains(page, "Avant le premier envoi à DeepL API")
        action = f"/traduction/evaluation/{self.project.pk}/comparaison/action/"
        self.client.post(action, {"c": job.scope_label, "action": "confirm"})
        job.refresh_from_db()
        self.assertEqual(job.status, "draft")
        self.client.post(action, {"c": job.scope_label, "action": "confirm", "terms_acknowledged": "1"})
        job.refresh_from_db()
        self.assertEqual(job.status, "done")

    def test_engines_page_lists_every_summary(self):
        page = self.client.get("/traduction/moteurs/")
        self.assertContains(page, "Conditions d'utilisation des textes envoyés")
        for name in ("DeepL API", "Google Cloud Translation (Basic)", "OpenAI (API)", "Anthropic (API Claude)",
                     "Google Gemini (API)"):
            self.assertContains(page, name)
