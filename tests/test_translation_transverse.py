"""Évolution 1.3.0 — lot 2 : retouches transverses des applications existantes (additives).

- catalog : origine « Traduction automatique » (C3) ;
- exports : l'option d'exclusion des contenus générés couvre aussi la traduction automatique ;
- ai : code HTTP et nature portés par ProviderError, messages inchangés (E2) ;
- core : détection d'encodage avec indice de fiabilité, decode_text déplacée sans changement (E2, E3) ;
- incidents : module « traduction » et catégories propres.
Données fictives uniquement ; aucun appel réseau.
"""
import io
import re

import httpx
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.ai.models import AIProviderCredential
from apps.ai.providers import AnthropicProvider, ProviderError
from apps.catalog.models import GENERATED_ORIGINS, ORIGIN, EditorialContent
from apps.catalog.services import upsert_record
from apps.core.encoding import decode_text as core_decode_text
from apps.core.encoding import detect_text
from apps.core.templatetags.app_tags import origin_chip
from apps.exports.document import _record_dict, build_document
from apps.exports.models import ExportJob
from apps.incidents.models import CATEGORIES, MODULES

from .helpers import AppTestCase

SAMPLE = "葉隠聞書。武士道と云は死ぬ事と見付たり。「架空の引用」"


class OriginTests(SimpleTestCase):
    def test_machine_translation_origin_exists(self):
        self.assertIn(("mt", "Traduction automatique"), ORIGIN)
        self.assertEqual(GENERATED_ORIGINS, ("ai", "mt"))

    def test_existing_origins_unchanged(self):
        for code in ("source", "rule", "user", "ai"):
            self.assertIn(code, dict(ORIGIN))

    def test_origin_chip(self):
        self.assertIn("traduction automatique", origin_chip("mt"))
        self.assertIn("chip-ai", origin_chip("mt"))
        self.assertIn(">IA<", origin_chip("ai"))


class ExportFilterTests(AppTestCase):
    def setUp(self):
        super().setUp()
        cat = self.catalogue("codh-pmjt")
        self.record, _ = upsert_record(cat, {"source_id": "MT1", "original_title": "架空の書",
                                             "description_original": "架空の解題。"})
        self.record.translated_title = "Livre fictif (DeepL)"
        self.record.translated_title_origin = "mt"
        self.record.save()
        EditorialContent.objects.create(record=self.record, kind="translation", target_field="description_original",
                                        source_text="架空の解題。", content="Notice fictive (Google)", origin="mt")
        EditorialContent.objects.create(record=self.record, kind="comment", content="Commentaire humain", origin="user")

    def test_machine_translations_excluded_when_generated_content_is_excluded(self):
        d = _record_dict(self.record, include_ai=False, include_notes=False, user=self.admin)
        self.assertEqual(d["translated_title"], "")
        self.assertEqual([e["content"] for e in d["editorial"]], ["Commentaire humain"])

    def test_machine_translations_included_and_flagged_otherwise(self):
        d = _record_dict(self.record, include_ai=True, include_notes=False, user=self.admin)
        self.assertEqual(d["translated_title"], "Livre fictif (DeepL)")
        self.assertIn("Notice fictive (Google)", [e["content"] for e in d["editorial"]])
        job = ExportJob.objects.create(owner=self.admin, scope="selection", format="json", title="Essai",
                                       scope_params={"record_ids": [self.record.record_id]},
                                       options={"include_ai": True})
        self.assertTrue(build_document(job).metadata["contains_ai_content"])

    def test_export_form_label(self):
        page = self.client.get("/exports/preparer/?scope=selection&records=" + self.record.record_id)
        self.assertContains(page, "Inclure traductions automatiques et contenus IA")

    def test_record_page_shows_machine_translation_chip(self):
        page = self.client.get(self.record.get_absolute_url())
        self.assertContains(page, "traduction automatique")


class ProviderErrorTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.status = 200
        AnthropicProvider.transport = httpx.MockTransport(lambda request: httpx.Response(self.status, json={}))
        from apps.ai.crypto import encrypt_secret

        self.credential = AIProviderCredential.objects.create(user=self.admin, provider="anthropic",
                                                              encrypted_key=encrypt_secret("sk-ant-fictif-0123456789"))

    def tearDown(self):
        AnthropicProvider.transport = None

    def call(self, status):
        self.status = status
        with self.assertRaises(ProviderError) as ctx:
            AnthropicProvider(self.credential).list_models()
        return ctx.exception

    def test_status_and_kind_with_messages_unchanged(self):
        cases = {401: ("auth", "Clé API refusée par le fournisseur (authentification)."),
                 429: ("quota", "Quota ou limite de débit atteint chez le fournisseur."),
                 404: ("not_found", "Modèle ou service introuvable"),
                 503: ("unavailable", "Erreur du fournisseur (HTTP 503)"),
                 400: ("technical", "Erreur du fournisseur (HTTP 400)")}
        for status, (kind, message) in cases.items():
            with self.subTest(status=status):
                exc = self.call(status)
                self.assertEqual(exc.http_status, status)
                self.assertEqual(exc.kind, kind)
                self.assertIn(message, str(exc))

    def test_plain_construction_still_works(self):
        exc = ProviderError("message")
        self.assertEqual((str(exc), exc.http_status, exc.kind), ("message", None, ""))


class EncodingTests(SimpleTestCase):
    def test_decode_text_moved_without_change(self):
        from apps.updates import importers

        self.assertIs(importers.decode_text, core_decode_text)
        self.assertEqual(core_decode_text(SAMPLE.encode("utf-8")), (SAMPLE, "utf-8-sig"))
        self.assertEqual(core_decode_text(SAMPLE.encode("cp932")), (SAMPLE, "cp932"))
        self.assertEqual(core_decode_text(b"\x85\x00\xff")[1], "latin-1")  # aucun autre encodage ne convient

    def test_detects_japanese_encodings_with_confidence(self):
        for enc, expected in (("utf-8", "utf-8"), ("cp932", "cp932"), ("euc_jp", "euc_jp")):
            with self.subTest(enc=enc):
                result = detect_text(SAMPLE.encode(enc))
                self.assertEqual(result.text, SAMPLE)
                self.assertEqual(result.encoding, expected)
                self.assertIn(result.confidence, ("sure", "probable"))

    def test_euc_jp_is_not_mistaken_for_shift_jis(self):
        """Un texte EUC-JP se décode aussi en cp932, en caractères illisibles : la vraisemblance tranche."""
        result = detect_text(SAMPLE.encode("euc_jp"))
        self.assertEqual(result.encoding, "euc_jp")
        self.assertTrue(any("cp932" in n for n in result.notes))

    def test_bom_and_utf16(self):
        self.assertEqual(detect_text(("﻿" + SAMPLE).encode("utf-8")).confidence, "sure")
        self.assertEqual(detect_text(SAMPLE.encode("utf-16")).text, SAMPLE)
        for enc in ("utf-16-le", "utf-16-be"):
            with self.subTest(enc=enc):
                no_bom = detect_text(SAMPLE.encode(enc))
                self.assertEqual((no_bom.text, no_bom.encoding), (SAMPLE, enc))
        ascii_heavy = detect_text("Edo period, 葉隠".encode("utf-16-le"))
        self.assertEqual(ascii_heavy.encoding, "utf-16-le")

    def test_kana_only_utf16_is_not_taken_for_ascii(self):
        raw = "かな".encode("utf-16-le")
        self.assertTrue(raw.isascii(), "« かな » en UTF-16 ne contient que des octets ASCII")
        result = detect_text(raw)
        self.assertEqual((result.text, result.confidence), ("かな", "uncertain"))
        self.assertEqual(detect_text("ひらがな".encode("utf-16-le")).text, "ひらがな")
        for ascii_text in (b"Hello world, plain ASCII text.", b"2024-01-01;Edo;0000", b"0000"):
            with self.subTest(ascii_text=ascii_text):
                self.assertEqual(detect_text(ascii_text).encoding, "utf-8")

    def test_shift_jis_with_even_length_is_not_taken_for_utf16(self):
        raw = SAMPLE.encode("cp932")
        self.assertEqual(len(raw) % 2, 0)
        self.assertEqual(detect_text(raw).encoding, "cp932")

    def test_undecodable_text_is_flagged_uncertain(self):
        result = detect_text(bytes(range(128, 256)))
        self.assertEqual(result.confidence, "uncertain")
        self.assertTrue(result.notes)


class IncidentChoicesTests(SimpleTestCase):
    def test_translation_module_and_categories(self):
        self.assertIn("traduction", dict(MODULES))
        for code in ("cle_refusee", "quota_depasse", "langue_non_prise", "glossaire_refuse", "paquet_absent",
                     "reponse_vide", "delai_depasse", "lot_interrompu"):
            self.assertIn(code, dict(CATEGORIES))

    def test_existing_choices_unchanged(self):
        for code in ("recherche", "connecteur", "importation", "application", "interface"):
            self.assertIn(code, dict(MODULES))
        for code in ("indisponibilite", "erreur_technique", "reponse_illisible", "signalement"):
            self.assertIn(code, dict(CATEGORIES))


class NoSqlMigrationTests(TestCase):
    def test_choice_migrations_emit_no_sql(self):
        for app, number in (("catalog", "0005"), ("incidents", "0002")):
            out = io.StringIO()
            call_command("sqlmigrate", app, number, stdout=out)
            statements = [line for line in out.getvalue().splitlines()
                          if line.strip() and not line.startswith("--") and line.strip() not in ("BEGIN;", "COMMIT;")]
            with self.subTest(app=app):
                self.assertEqual(statements, [], f"{app} {number} ne doit produire aucune instruction SQL")
                self.assertFalse(re.search(r"ALTER|CREATE|DROP", out.getvalue()))
