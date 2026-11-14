"""Évolution 1.3.0 — lot 7 : glossaires, contrôle terminologique, envoi à DeepL, mémoire de traduction.

Termes et textes fictifs. DeepL est simulé (httpx.MockTransport) : aucun appel réseau réel.
"""
import json

import httpx
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.ai.crypto import encrypt_secret
from apps.incidents.models import Incident
from apps.translation import glossary as G
from apps.translation import memory as tm
from apps.translation.engines.ai import build_prompt
from apps.translation.engines.base import Segment
from apps.translation.engines.deepl import DeepLEngine
from apps.translation.models import (EngineSetting, Glossary, GlossaryEntry, ProjectGlossary, TranslationDocument,
                                     TranslationJob, TranslationPreference, TranslationProject, TranslationVersion)

from .helpers import AppTestCase

TEXT = "徳川家康は江戸に幕府を開いた。\n\n武士は刀を持つ。"


class FakeDeepL:
    """Service DeepL simulé : traduction, langues des glossaires, création et suppression de glossaires."""

    def __init__(self, translations=None, glossary_langs=("ja", "en", "fr"), create_status=201):
        self.translations = translations or {}
        self.glossary_langs = glossary_langs
        self.create_status = create_status
        self.requests = []
        self.glossaries = {}
        self.counter = 0

    def __call__(self, request):
        path = request.url.path
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, path, body, dict(request.url.params)))
        if path == "/v2/translate":
            return httpx.Response(200, json={"translations": [{"text": self.translations.get(t.strip(), f"FR {t.strip()}")}
                                                              for t in body["text"]]})
        if path == "/v3/languages":
            return httpx.Response(200, json=[{"lang": lang, "name": lang, "usable_as_source": True,
                                              "usable_as_target": True} for lang in self.glossary_langs])
        if path == "/v3/glossaries" and request.method == "POST":
            if self.create_status != 201:
                return httpx.Response(self.create_status, json={"message": "Invalid glossary entries"})
            self.counter += 1
            gid = f"gl-{self.counter}"
            entries = body["dictionaries"][0]["entries"].split("\n")
            self.glossaries[gid] = entries
            return httpx.Response(201, json={"glossary_id": gid, "name": body["name"], "ready": True,
                                             "dictionaries": [{"source_lang": "ja", "target_lang": "fr",
                                                               "entry_count": len(entries)}]})
        if path.startswith("/v3/glossaries/") and request.method == "DELETE":
            gid = path.rsplit("/", 1)[1]
            if gid not in self.glossaries:
                return httpx.Response(404, json={"message": "Glossary not found"})
            del self.glossaries[gid]
            return httpx.Response(204)
        return httpx.Response(404)

    def calls(self, method, path):
        return [r for r in self.requests if r[0] == method and r[1] == path]


class GlossaryTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.researcher
        self.client.force_login(self.owner)
        self.deepl = FakeDeepL()
        DeepLEngine.transport = httpx.MockTransport(self.deepl)
        self.addCleanup(setattr, DeepLEngine, "transport", None)
        EngineSetting.objects.create(user=self.owner, engine="deepl", plan="free", status="ok",
                                     encrypted_key=encrypt_secret("fake-deepl-key-0000000000"))
        EngineSetting.objects.create(user=self.owner, engine="argos", enabled=True)
        TranslationPreference.objects.create(user=self.owner, default_engine="deepl", migrated_from_ai=True)
        self.project = TranslationProject.objects.create(owner=self.owner, title="Projet fictif")
        self.glossary = Glossary.objects.create(owner=self.owner, name="Noms fictifs")
        G.save_entry(self.glossary, {"source_term": "徳川家康", "target_term": "Tokugawa Ieyasu", "category": "person",
                                     "variants": "德川家康", "avoid": "Ieyasu Tokugawa"})
        G.save_entry(self.glossary, {"source_term": "幕府", "target_term": "bakufu", "category": "institution",
                                     "avoid": "shogunat"})
        ProjectGlossary.objects.create(project=self.project, glossary=self.glossary, priority=0)

    def add_document(self, text=TEXT):
        self.client.post(f"/traduction/projets/{self.project.pk}/documents/nouveau/",
                         {"title": "Document fictif", "variety": "modern", "text": text})
        return TranslationDocument.objects.latest("pk")

    def translate_all(self, document):
        self.client.post(f"/traduction/documents/{document.pk}/lot/", {"scope": "untranslated", "action": "translate",
                                                                       "engine": "default"})
        job = TranslationJob.objects.latest("pk")
        self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm", "second_confirmation": "1"})
        job.refresh_from_db()
        return job


# --------------------------------------------------------------------------- unités


class TerminologyTests(AppTestCase):
    def terms(self, *entries, lang="ja"):
        return [G.Term(src, tgt, [src, *variants], list(avoid), 1, "g", i)
                for i, (src, tgt, variants, avoid) in enumerate(entries)]

    def test_fold_ignores_case_accents_and_macrons(self):
        self.assertEqual(G.fold("Tōkyō"), G.fold("TOKYO"))
        self.assertEqual(G.stems("Les samouraïs"), G.stems("les samourai"))
        self.assertTrue(G.target_contains("Les shoguns Tokugawa", "shogun"))

    def test_missing_expected_term_is_signalled_not_corrected(self):
        terms = self.terms(("幕府", "bakufu", [], []))
        self.assertEqual(G.check_terminology("江戸の幕府", "le gouvernement d'Edo", terms, "ja"),
                         ["glossaire : « 幕府 » devrait être traduit par « bakufu »"])
        self.assertEqual(G.check_terminology("江戸の幕府", "le Bakufu d'Edo", terms, "ja"), [])

    def test_variant_and_avoided_term(self):
        terms = self.terms(("徳川家康", "Tokugawa Ieyasu", ["德川家康"], ["Ieyasu Tokugawa"]))
        alerts = G.check_terminology("德川家康が来た", "Ieyasu Tokugawa arriva", terms, "ja")
        self.assertEqual(len(alerts), 2)
        self.assertIn("« 德川家康 » devrait être traduit par « Tokugawa Ieyasu »", alerts[0])
        self.assertIn("à éviter « Ieyasu Tokugawa »", alerts[1])

    def test_english_source_matches_whole_words_only(self):
        terms = self.terms(("shrine", "sanctuaire", [], []), lang="en")
        self.assertEqual(G.check_terminology("A category of things", "Une catégorie", terms, "en"), [])
        self.assertEqual(len(G.check_terminology("Two Shrines", "Deux temples", terms, "en")), 1)
        self.assertEqual(G.check_terminology("Two Shrines", "Deux sanctuaires", terms, "en"), [])

    def test_ai_prompt_receives_only_present_terms_with_avoid(self):
        bundle = G.GlossaryBundle(terms=self.terms(("幕府", "bakufu", [], ["shogunat"]), ("武士", "bushi", [], [])))
        _, prompt, terms = build_prompt([Segment("1", "江戸の幕府")], "ja", "fr", glossary=bundle)
        self.assertEqual(terms, [("幕府", "bakufu", ["shogunat"])])
        self.assertIn("幕府 → bakufu (à éviter : shogunat)", prompt)
        self.assertNotIn("bushi", prompt)
        # l'ancienne forme (liste de couples) reste acceptée
        _, prompt, _ = build_prompt([Segment("1", "江戸の幕府")], "ja", "fr", glossary=[("幕府", "bakufu")])
        self.assertIn("幕府 → bakufu", prompt)


class EntryTests(GlossaryTestCase):
    def test_duplicates_are_refused_and_version_increments(self):
        version = self.glossary.version
        with self.assertRaisesMessage(G.GlossaryError, "figure déjà"):
            G.save_entry(self.glossary, {"source_term": " 徳川家康 ", "target_term": "autre"})
        with self.assertRaisesMessage(G.GlossaryError, "figure déjà"):  # variante d'une autre entrée
            G.save_entry(self.glossary, {"source_term": "德川家康", "target_term": "autre"})
        self.glossary.refresh_from_db()
        self.assertEqual(self.glossary.version, version)
        G.save_entry(self.glossary, {"source_term": "江戸", "target_term": "Edo", "category": "place"})
        self.glossary.refresh_from_db()
        self.assertEqual(self.glossary.version, version + 1)

    def test_create_and_edit_glossary(self):
        self.assertEqual(self.client.get("/traduction/glossaires/nouveau/").status_code, 200)
        response = self.client.post("/traduction/glossaires/nouveau/", {"name": "Ères fictives", "source_lang": "ja",
                                                                       "target_lang": "fr"})
        created = Glossary.objects.get(name="Ères fictives")
        self.assertRedirects(response, f"/traduction/glossaires/{created.pk}/")
        self.assertEqual(created.owner, self.owner)
        # paire de langues figée tant que le glossaire sert un projet
        response = self.client.post(f"/traduction/glossaires/{self.glossary.pk}/modifier/",
                                    {"name": "Noms fictifs", "source_lang": "en", "target_lang": "fr"})
        self.assertContains(response, "ne peut plus changer")
        self.assertEqual(Glossary.objects.get(pk=self.glossary.pk).source_lang, "ja")

    def test_terms_are_cleaned_for_deepl(self):
        entry = G.save_entry(self.glossary, {"source_term": "江\t戸\n", "target_term": "  Edo  "})
        self.assertEqual((entry.source_term, entry.target_term), ("江 戸", "Edo"))

    def test_views_add_edit_delete_entry(self):
        url = f"/traduction/glossaires/{self.glossary.pk}/"
        self.assertContains(self.client.get(url), "Tokugawa Ieyasu")
        self.client.post(url + "entrees/", {"source_term": "江戸", "target_term": "Edo", "category": "place"})
        entry = GlossaryEntry.objects.get(source_term="江戸")
        self.client.post(url + "entrees/", {"entry": entry.pk, "source_term": "江戸", "target_term": "Edo (Tōkyō)",
                                            "category": "place", "variants": "江都 | 江戸"})
        entry.refresh_from_db()
        self.assertEqual((entry.target_term, entry.variants), ("Edo (Tōkyō)", ["江都"]))
        response = self.client.post(url + "entrees/", {"source_term": "幕府", "target_term": "x", "category": "other"},
                                    follow=True)
        self.assertContains(response, "figure déjà")
        self.client.post(f"{url}entrees/{entry.pk}/supprimer/")
        self.assertFalse(GlossaryEntry.objects.filter(pk=entry.pk).exists())

    def test_access_rules(self):
        other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/traduction/glossaires/{self.glossary.pk}/").status_code, 404)
        self.client.force_login(self.reader)
        self.assertNotEqual(self.client.get("/traduction/glossaires/").status_code, 200)
        # administrateur : voit le glossaire… sauf s'il sert un projet confidentiel d'un autre compte (D3)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/traduction/glossaires/{self.glossary.pk}/").status_code, 200)
        self.project.confidential = True
        self.project.save()
        self.assertEqual(self.client.get(f"/traduction/glossaires/{self.glossary.pk}/").status_code, 404)
        response = self.client.get("/traduction/glossaires/")
        self.assertContains(response, "Métadonnées seulement")
        self.assertNotContains(response, f"/traduction/glossaires/{self.glossary.pk}/")


class CsvTests(GlossaryTestCase):
    def test_export_then_import_round_trip(self):
        G.save_entry(self.glossary, {"source_term": "江戸", "target_term": "=Edo", "note": "formule fictive"})
        content = self.client.get(f"/traduction/glossaires/{self.glossary.pk}/export.csv").content.decode("utf-8")
        self.assertTrue(content.startswith("﻿source_term,target_term"))
        self.assertIn("'=Edo", content)  # protégé contre l'exécution dans un tableur
        copy = Glossary.objects.create(owner=self.owner, name="Copie")
        report = G.import_csv(copy, content.encode("utf-8"))
        self.assertEqual(len(report.added), 3)
        self.assertEqual(copy.entries.get(source_term="江戸").target_term, "=Edo")
        self.assertEqual(copy.entries.get(source_term="徳川家康").variants, ["德川家康"])

    def test_semicolon_cp932_aliases_duplicates_and_errors(self):
        raw = ("terme_source;terme_cible;categorie;a_eviter\n"
               "江戸;Edo;Lieu;\n"
               "江戸;Yedo;;\n"           # répété dans le fichier
               "幕府;bakufu;;\n"          # déjà présent
               "将軍;;;\n"                # terme cible manquant
               "大名;daimyo;inconnue;\n").encode("cp932")
        report = G.import_csv(self.glossary, raw)
        self.assertEqual(report.delimiter, ";")
        self.assertEqual(report.encoding, "cp932")
        self.assertEqual(report.added, ["江戸"])
        self.assertEqual([s[2] for s in report.skipped], ["répété dans le fichier (ligne 2)", "déjà présent dans le glossaire"])
        self.assertEqual([e[0] for e in report.errors], [5, 6])
        self.assertEqual(self.glossary.entries.get(source_term="江戸").category, "place")

    def test_dry_run_saves_nothing_and_update_existing(self):
        raw = "source_term,target_term\n幕府,Bakufu (gouvernement militaire)\n江戸,Edo\n".encode()
        version = Glossary.objects.get(pk=self.glossary.pk).version
        report = G.import_csv(self.glossary, raw, update_existing=True, dry_run=True)
        self.assertEqual((report.added, report.updated, report.saved), (["江戸"], ["幕府"], False))
        self.assertFalse(self.glossary.entries.filter(source_term="江戸").exists())
        self.assertEqual(Glossary.objects.get(pk=self.glossary.pk).version, version)
        G.import_csv(self.glossary, raw, update_existing=True)
        self.assertEqual(self.glossary.entries.get(source_term="幕府").target_term, "Bakufu (gouvernement militaire)")
        self.assertEqual(Glossary.objects.get(pk=self.glossary.pk).version, version + 1)  # une seule incrémentation

    def test_import_view_checks_before_importing(self):
        url = f"/traduction/glossaires/{self.glossary.pk}/import/"
        raw = "source_term,target_term\n江戸,Edo\n".encode()
        response = self.client.post(url, {"file": SimpleUploadedFile("g.csv", raw), "action": "check"})
        self.assertContains(response, "rien n'a encore été enregistré")
        self.assertFalse(self.glossary.entries.filter(source_term="江戸").exists())
        self.client.post(url, {"file": SimpleUploadedFile("g.csv", raw), "action": "import"})
        self.assertTrue(self.glossary.entries.filter(source_term="江戸").exists())

    def test_bad_header_is_refused(self):
        with self.assertRaisesMessage(G.GlossaryError, "En-tête CSV non reconnu"):
            G.import_csv(self.glossary, b"a,b\nx,y\n")


# --------------------------------------------------------------------------- projets et moteurs


class ProjectTermTests(GlossaryTestCase):
    def test_priority_and_contradictions(self):
        second = Glossary.objects.create(owner=self.owner, name="Second")
        G.save_entry(second, {"source_term": "幕府", "target_term": "shogunat"})
        G.save_entry(second, {"source_term": "武士", "target_term": "bushi"})
        ProjectGlossary.objects.create(project=self.project, glossary=second, priority=1)
        terms = {t.source: t.target for t in G.project_terms(self.project)}
        self.assertEqual(terms["幕府"], "bakufu")  # le premier glossaire l'emporte
        self.assertEqual(terms["武士"], "bushi")
        contradictions = G.project_contradictions(self.project)
        self.assertEqual([c[0] for c in contradictions], ["幕府"])
        response = self.client.get(f"/traduction/projets/{self.project.pk}/")
        self.assertContains(response, "Contradictions entre glossaires")

    def test_project_glossary_management(self):
        url = f"/traduction/projets/{self.project.pk}/glossaires/"
        second = Glossary.objects.create(owner=self.owner, name="Second")
        english = Glossary.objects.create(owner=self.owner, name="Anglais", source_lang="en")
        self.client.post(url, {"action": "add", "glossary": english.pk})  # paire différente : refusé
        self.client.post(url, {"action": "add", "glossary": second.pk})
        self.assertEqual(list(self.project.glossary_links.values_list("glossary__name", flat=True)),
                         ["Noms fictifs", "Second"])
        link = self.project.glossary_links.get(glossary=second)
        self.client.post(url, {"action": "up", "link": link.pk})
        self.assertEqual(list(self.project.glossary_links.order_by("priority").values_list("glossary__name", flat=True)),
                         ["Second", "Noms fictifs"])
        self.client.post(url, {"action": "remove", "link": link.pk})
        self.assertTrue(Glossary.objects.filter(pk=second.pk).exists())
        self.assertEqual(self.project.glossary_links.count(), 1)

    def test_bundle_per_engine(self):
        bundle = G.bundle_for(self.project, self.owner, "google_basic")
        self.assertIn("moteur sans glossaire", bundle.notes[0])
        self.assertEqual(bundle.refs[0]["application"], "controle")
        self.assertEqual(G.bundle_for(self.project, self.owner, "ai").refs[0]["application"], "consigne")
        bundle = G.bundle_for(self.project, self.owner, "deepl")
        self.assertEqual(bundle.deepl_glossary_id, "")
        self.assertIn("non envoyé à DeepL", bundle.notes[0])
        self.assertIsNone(G.bundle_for(TranslationProject.objects.create(owner=self.owner, title="Vide"), self.owner,
                                       "deepl"))


class PipelineTests(GlossaryTestCase):
    def test_deepl_without_remote_copy_local_check_only(self):
        self.deepl.translations = {"徳川家康は江戸に幕府を開いた。": "Ieyasu Tokugawa ouvrit un shogunat à Edo."}
        document = self.add_document()
        job = self.translate_all(document)
        self.assertEqual(job.status, "done")
        body = self.deepl.calls("POST", "/v2/translate")[0][2]
        self.assertNotIn("glossary_id", body)
        first = document.segments.order_by("position").first().versions.get()
        self.assertTrue(any("non envoyé à DeepL" in a for a in first.alerts))
        self.assertTrue(any("devrait être traduit par « Tokugawa Ieyasu »" in a for a in first.alerts))
        self.assertTrue(any("à éviter « shogunat »" in a for a in first.alerts))
        self.assertEqual(first.text, "Ieyasu Tokugawa ouvrit un shogunat à Edo.")  # rien n'est corrigé
        self.assertEqual(first.glossaries, [{"id": self.glossary.pk, "name": "Noms fictifs",
                                             "version": self.glossary.version, "application": "controle"}])
        self.assertEqual(first.segment.state, "alert")
        last = document.segments.order_by("position").last().versions.get()  # aucun terme : aucune alerte glossaire
        self.assertFalse(any("glossaire" in a for a in last.alerts))

    def test_deepl_uses_current_remote_copy(self):
        G.send_to_deepl(self.glossary, self.owner)
        self.glossary.refresh_from_db()
        self.deepl.translations = {"徳川家康は江戸に幕府を開いた。": "Tokugawa Ieyasu ouvrit le bakufu à Edo."}
        document = self.add_document()
        self.translate_all(document)
        body = self.deepl.calls("POST", "/v2/translate")[0][2]
        self.assertEqual(body["glossary_id"], "gl-1")
        self.assertEqual(body["source_lang"], "JA")
        version = document.segments.order_by("position").first().versions.get()
        self.assertEqual(version.alerts, [])
        self.assertEqual(version.glossaries[0]["application"], "native")
        # glossaire modifié : la copie distante est périmée et n'est plus utilisée
        G.save_entry(self.glossary, {"source_term": "江戸", "target_term": "Edo"})
        bundle = G.bundle_for(self.project, self.owner, "deepl")
        self.assertEqual(bundle.deepl_glossary_id, "")
        self.assertIn("périmée", bundle.notes[0])

    def test_confirmation_screen_shows_glossary_application(self):
        document = self.add_document()
        self.client.post(f"/traduction/documents/{document.pk}/lot/", {"scope": "untranslated", "action": "translate",
                                                                       "engine": "default"})
        job = TranslationJob.objects.latest("pk")
        response = self.client.get(f"/traduction/taches/{job.pk}/")
        self.assertContains(response, "Noms fictifs (v")
        self.assertContains(response, "contrôle local")

    def test_human_version_is_checked_too(self):
        document = self.add_document()
        segment = document.segments.order_by("position").first()
        self.client.post(f"/traduction/segments/{segment.pk}/action/", {"action": "human", "text": "Ieyasu ouvrit le bakufu."})
        version = segment.versions.get()
        self.assertEqual(version.alerts, ["glossaire : « 徳川家康 » devrait être traduit par « Tokugawa Ieyasu »"])

    def test_add_term_from_segment_page(self):
        document = self.add_document()
        segment = document.segments.order_by("position").last()
        page = self.client.get(f"/traduction/segments/{document.segments.order_by('position').first().pk}/")
        self.assertContains(page, "Termes du glossaire présents")
        self.client.post(f"/traduction/segments/{segment.pk}/glossaire/",
                         {"glossary": self.glossary.pk, "source_term": "武士", "target_term": "bushi", "category": "historical"})
        self.assertTrue(self.glossary.entries.filter(source_term="武士", target_term="bushi").exists())


class DeepLSyncTests(GlossaryTestCase):
    def test_send_requires_confirmation_and_sends_variants_not_avoided_terms(self):
        url = f"/traduction/glossaires/{self.glossary.pk}/deepl/"
        self.client.post(url, {"action": "send"})
        self.assertEqual(self.deepl.calls("POST", "/v3/glossaries"), [])
        self.client.post(url, {"action": "send", "confirm": "1"})
        _, _, body, _ = self.deepl.calls("POST", "/v3/glossaries")[0]
        self.assertEqual(body["dictionaries"][0]["source_lang"], "ja")
        self.assertEqual(body["dictionaries"][0]["entries_format"], "tsv")
        self.assertEqual(sorted(body["dictionaries"][0]["entries"].split("\n")),
                         sorted(["徳川家康\tTokugawa Ieyasu", "德川家康\tTokugawa Ieyasu", "幕府\tbakufu"]))
        self.assertNotIn("shogunat", json.dumps(body, ensure_ascii=False))
        self.assertEqual(self.deepl.calls("GET", "/v3/languages")[0][3], {"resource": "glossary"})
        self.glossary.refresh_from_db()
        copy = self.glossary.remote_copies[str(self.owner.pk)]
        self.assertEqual((copy["glossary_id"], copy["version"], copy["plan"]), ("gl-1", self.glossary.version, "free"))

    def test_resend_replaces_and_deletes_previous_copy(self):
        G.send_to_deepl(self.glossary, self.owner)
        G.save_entry(self.glossary, {"source_term": "江戸", "target_term": "Edo"})
        message = G.send_to_deepl(self.glossary, self.owner)
        self.assertIn("ancienne copie DeepL a été supprimée", message)
        self.assertEqual(list(self.deepl.glossaries), ["gl-2"])

    def test_delete_remote_copy_and_already_deleted(self):
        G.send_to_deepl(self.glossary, self.owner)
        self.glossary.refresh_from_db()
        self.assertEqual(G.delete_remote(self.glossary, self.owner), "Copie DeepL supprimée.")
        self.assertEqual(Glossary.objects.get(pk=self.glossary.pk).remote_copies, {})
        G.send_to_deepl(self.glossary, self.owner)
        self.deepl.glossaries.clear()  # supprimée côté DeepL entre-temps
        self.assertIn("ne connaissait plus", G.delete_remote(self.glossary, self.owner))

    def test_refusals(self):
        other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        with self.assertRaisesMessage(G.GlossaryError, "Seul le propriétaire"):
            G.send_to_deepl(self.glossary, other)
        self.deepl.glossary_langs = ("en", "fr")
        with self.assertRaisesMessage(G.GlossaryError, "n'accepte pas de glossaire"):
            G.send_to_deepl(self.glossary, self.owner)
        self.project.confidential = True
        self.project.save()
        with self.assertRaisesMessage(G.GlossaryError, "projet confidentiel"):
            G.send_to_deepl(self.glossary, self.owner)
        self.assertEqual(self.deepl.calls("POST", "/v3/glossaries"), [])

    def test_refused_glossary_is_journaled_and_reported(self):
        self.deepl.create_status = 400
        response = self.client.post(f"/traduction/glossaires/{self.glossary.pk}/deepl/",
                                    {"action": "send", "confirm": "1"}, follow=True)
        self.assertContains(response, "Glossaire refusé par DeepL")
        incident = Incident.objects.filter(module="traduction", category="glossaire_refuse").get()
        self.assertNotIn("徳川", json.dumps(incident.context, ensure_ascii=False))
        self.assertEqual(Glossary.objects.get(pk=self.glossary.pk).remote_copies, {})

    def test_local_delete_refused_while_remote_copy_exists(self):
        G.send_to_deepl(self.glossary, self.owner)
        url = f"/traduction/glossaires/{self.glossary.pk}/supprimer/"
        self.client.post(url, {"confirm_name": "Noms fictifs"})
        self.assertTrue(Glossary.objects.filter(pk=self.glossary.pk).exists())
        G.delete_remote(Glossary.objects.get(pk=self.glossary.pk), self.owner)
        self.client.post(url, {"confirm_name": "Noms fictifs"})
        self.assertFalse(Glossary.objects.filter(pk=self.glossary.pk).exists())
        self.assertEqual(self.project.glossary_links.count(), 0)


# --------------------------------------------------------------------------- mémoire


class MemoryTests(GlossaryTestCase):
    def validated(self):
        document = self.add_document("江戸の町。")
        segment = document.segments.get()
        self.client.post(f"/traduction/segments/{segment.pk}/action/", {"action": "human", "text": "La ville d'Edo."})
        version = segment.versions.get()
        self.client.post(f"/traduction/versions/{version.pk}/action/", {"action": "validate"})
        version.refresh_from_db()
        return version

    def test_memory_list_search_and_exclusion(self):
        version = self.validated()
        response = self.client.get("/traduction/memoire/?q=Edo")
        self.assertContains(response, "La ville d&#x27;Edo.")
        self.assertIsNotNone(tm.lookup(self.owner, version.segment.memory_key))
        self.client.post(f"/traduction/memoire/{version.pk}/", {"action": "exclude"})
        version.refresh_from_db()
        self.assertTrue(version.excluded_from_memory)
        self.assertIsNone(tm.lookup(self.owner, version.segment.memory_key))
        self.assertContains(self.client.get("/traduction/memoire/?etat=exclues"), "Réintégrer")
        self.client.post(f"/traduction/memoire/{version.pk}/", {"action": "include"})
        self.assertIsNotNone(tm.lookup(self.owner, version.segment.memory_key))

    def test_memory_is_private_even_for_admin(self):
        version = self.validated()
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get("/traduction/memoire/"), "La ville d&#x27;Edo.")
        self.assertEqual(self.client.post(f"/traduction/memoire/{version.pk}/", {"action": "exclude"}).status_code, 404)
        self.assertFalse(TranslationVersion.objects.get(pk=version.pk).excluded_from_memory)

    def test_home_links_are_active(self):
        response = self.client.get("/traduction/")
        self.assertContains(response, 'href="/traduction/glossaires/"')
        self.assertContains(response, 'href="/traduction/memoire/"')
