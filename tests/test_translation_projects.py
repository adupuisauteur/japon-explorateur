"""Évolution 1.3.0 — lot 6 : projets, documents, segments, versions, confidentialité.

Fichiers d'essai fabriqués pendant les tests (TXT dans plusieurs encodages, DOCX, PDF en japonais).
Textes fictifs. Moteurs simulés (DeepL : réponse programmée ; Argos : mode simulé).
"""
import io
import json
from pathlib import Path

import httpx
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.ai.crypto import encrypt_secret
from apps.catalog.models import EditorialContent
from apps.catalog.services import upsert_record
from apps.translation import projects as P
from apps.translation.engines.deepl import DeepLEngine
from apps.translation.models import (EngineSetting, TranslationDocument, TranslationJob, TranslationPreference,
                                     TranslationProject, TranslationSegment, TranslationVersion)

from .helpers import AppTestCase

TEXT = "武士道と云は死ぬ事と見付たり。彼は「行く。」と言った。\n\n次の段落。"


def pdf_with_japanese(text):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font = next((p for p in settings.PDF_JAPANESE_FONT_CANDIDATES if Path(p).exists()), None)
    if font is None:
        return None
    pdfmetrics.registerFont(TTFont("EssaiJapon", font))
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.setFont("EssaiJapon", 14)
    c.drawString(72, 720, text)
    c.save()
    return buffer.getvalue()


def blank_pdf():
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.rect(100, 100, 200, 200, fill=1)  # une « image » : aucun texte
    c.save()
    return buffer.getvalue()


def docx_with(text_paragraphs, table=None):
    from docx import Document

    d = Document()
    for p in text_paragraphs:
        d.add_paragraph(p)
    if table:
        t = d.add_table(rows=1, cols=len(table))
        for cell, value in zip(t.rows[0].cells, table):
            cell.text = value
    buffer = io.BytesIO()
    d.save(buffer)
    return buffer.getvalue()


class ProjectTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.researcher
        self.client.force_login(self.owner)
        self.sent = []

        def reply(request):
            texts = json.loads(request.content)["text"]
            self.sent.extend(texts)
            return httpx.Response(200, json={"translations": [{"text": f"FR {t.strip()}"} for t in texts]})

        DeepLEngine.transport = httpx.MockTransport(reply)
        self.addCleanup(setattr, DeepLEngine, "transport", None)
        EngineSetting.objects.create(user=self.owner, engine="deepl", plan="free", status="ok",
                                     encrypted_key=encrypt_secret("fake-deepl-key-0000000000"))
        EngineSetting.objects.create(user=self.owner, engine="argos", enabled=True)
        TranslationPreference.objects.create(user=self.owner, default_engine="deepl", migrated_from_ai=True)
        self.project = TranslationProject.objects.create(owner=self.owner, title="Projet fictif")

    def add(self, text=TEXT, title="Document fictif", project=None, **files):
        project = project or self.project
        data = {"title": title, "variety": "modern", "text": text if not files else ""}
        data.update(files)
        return self.client.post(f"/traduction/projets/{project.pk}/documents/nouveau/", data)

    def translate_all(self, document):
        self.client.post(f"/traduction/documents/{document.pk}/lot/", {"scope": "untranslated", "action": "translate",
                                                                       "engine": "default"})
        job = TranslationJob.objects.latest("pk")
        self.client.post(f"/traduction/taches/{job.pk}/action/", {"action": "confirm", "second_confirmation": "1"})
        job.refresh_from_db()
        return job


class ProjectFormTests(ProjectTestCase):
    def test_create_project(self):
        response = self.client.post("/traduction/projets/nouveau/", {"title": "Nouveau projet fictif", "source_lang": "ja",
                                                                     "target_lang": "fr"})
        project = TranslationProject.objects.get(title="Nouveau projet fictif")
        self.assertRedirects(response, f"/traduction/projets/{project.pk}/")
        self.assertEqual(project.owner, self.owner)

    def test_confidential_project_refuses_online_engines_in_its_settings(self):
        self.client.post("/traduction/projets/nouveau/", {"title": "Secret fictif", "source_lang": "ja", "target_lang": "fr",
                                                         "confidential": "on", "default_engine": "deepl"})
        self.assertFalse(TranslationProject.objects.filter(title="Secret fictif").exists())
        self.client.post("/traduction/projets/nouveau/", {"title": "Secret fictif", "source_lang": "ja", "target_lang": "fr",
                                                         "confidential": "on", "default_engine": "argos"})
        self.assertTrue(TranslationProject.objects.get(title="Secret fictif").confidential)

    def test_delete_requires_exact_title(self):
        self.client.post(f"/traduction/projets/{self.project.pk}/supprimer/", {"confirm_title": "autre"})
        self.assertTrue(TranslationProject.objects.filter(pk=self.project.pk).exists())
        self.client.post(f"/traduction/projets/{self.project.pk}/supprimer/", {"confirm_title": "Projet fictif"})
        self.assertFalse(TranslationProject.objects.filter(pk=self.project.pk).exists())


class ImportTests(ProjectTestCase):
    def test_pasted_text_is_kept_exactly_and_segmented(self):
        self.add()
        document = TranslationDocument.objects.get()
        self.assertEqual(document.original_text, TEXT)
        self.assertTrue(P.integrity_ok(document))
        self.assertEqual(list(document.segments.values_list("source_text", flat=True)),
                         ["武士道と云は死ぬ事と見付たり。", "彼は「行く。」と言った。\n\n", "次の段落。"])

    def test_txt_in_japanese_encodings(self):
        for i, enc in enumerate(("utf-8", "cp932", "euc_jp")):
            with self.subTest(enc=enc):
                self.add(title=f"Fichier {enc}", file=SimpleUploadedFile(f"texte-{i}.txt", TEXT.encode(enc)))
                document = TranslationDocument.objects.get(title=f"Fichier {enc}")
                self.assertEqual(document.original_text, TEXT)
                self.assertEqual(document.source_kind, "txt")

    def test_uncertain_encoding_needs_confirmation(self):
        raw = "かな".encode("utf-16-le")  # octets ASCII : ambigu
        response = self.add(title="Ambigu", file=SimpleUploadedFile("ambigu.txt", raw))
        self.assertContains(response, "Encodage incertain")
        self.assertFalse(TranslationDocument.objects.exists())
        self.client.post(f"/traduction/projets/{self.project.pk}/documents/nouveau/", {
            "title": "Ambigu", "variety": "modern", "confirmed_text": "かな", "source_kind": "txt",
            "filename": "ambigu.txt", "encoding": "utf-16-le", "confirm_encoding": "1"})
        document = TranslationDocument.objects.get()
        self.assertEqual((document.original_text, document.encoding_confidence), ("かな", "uncertain"))

    def test_docx(self):
        self.add(title="Word", file=SimpleUploadedFile("essai.docx", docx_with(["一つ目の段落。", "二つ目の段落。"],
                                                                              table=["表の文。", "セル。"])))
        document = TranslationDocument.objects.get()
        self.assertEqual(document.original_text, "一つ目の段落。\n二つ目の段落。\n表の文。\tセル。")

    def test_pdf_with_text_and_pdf_without_text(self):
        data = pdf_with_japanese("架空の文書です。")
        if data is None:
            self.skipTest("aucune police japonaise installée pour fabriquer le PDF d'essai")
        self.add(title="PDF", file=SimpleUploadedFile("essai.pdf", data))
        document = TranslationDocument.objects.get()
        self.assertIn("架空の文書です。", document.original_text)
        response = self.add(title="Image", file=SimpleUploadedFile("image.pdf", blank_pdf()))
        self.assertContains(response, "OCR", status_code=200)
        self.assertEqual(TranslationDocument.objects.count(), 1)

    def test_unsupported_format(self):
        response = self.add(title="Ancien Word", file=SimpleUploadedFile("vieux.doc", b"\xd0\xcf\x11\xe0"))
        self.assertContains(response, "Format non pris en charge")


class SegmentOperationTests(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.document = P.create_document(self.project, title="Doc", text="一つ目。二つ目。三つ目。")
        self.s1, self.s2, self.s3 = self.document.segments.order_by("position")

    def version(self, segment, status="proposed", text="Traduction fictive."):
        return TranslationVersion.objects.create(segment=segment, text=text, source_text=segment.source_text,
                                                 origin="machine", engine="deepl", status=status)

    def test_merge_keeps_versions_and_integrity(self):
        v2 = self.version(self.s2)
        self.client.post(f"/traduction/segments/{self.s1.pk}/action/", {"action": "merge"})
        self.assertTrue(P.integrity_ok(self.document))
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.source_text, "一つ目。二つ目。")
        self.assertTrue(self.s1.source_changed)
        v2.refresh_from_db()
        self.assertEqual(v2.segment, self.s1, "la version du segment absorbé est conservée")
        self.assertEqual(list(self.document.segments.values_list("position", flat=True)), [1, 2])

    def test_merge_refused_when_both_are_validated(self):
        self.version(self.s1, "validated")
        self.version(self.s2, "validated")
        with self.assertRaises(P.ProjectError):
            P.merge_with_next(self.s1)
        self.assertEqual(self.document.segments.count(), 3)

    def test_split_requires_an_exact_prefix(self):
        self.client.post(f"/traduction/segments/{self.s1.pk}/action/", {"action": "split", "first_part": "一つ"})
        self.assertTrue(P.integrity_ok(self.document))
        self.assertEqual(list(self.document.segments.order_by("position").values_list("source_text", flat=True)),
                         ["一つ", "目。", "二つ目。", "三つ目。"])
        for bad in ("二つ", "", "一つ目。"):
            with self.assertRaises(P.ProjectError):
                P.split_segment(TranslationSegment.objects.get(document=self.document, position=1), bad)

    def test_chapters(self):
        chapter = P.start_chapter(self.s2, "Deuxième partie")
        self.assertEqual(list(chapter.segments.order_by("position").values_list("position", flat=True)), [2, 3])
        page = self.client.get(f"/traduction/documents/{self.document.pk}/?chapitre={chapter.pk}")
        self.assertContains(page, "二つ目。")
        self.assertNotContains(page, "一つ目。")


class VersionWorkflowTests(ProjectTestCase):
    def test_translate_correct_and_validate(self):
        self.add()
        document = TranslationDocument.objects.get()
        job = self.translate_all(document)
        self.assertEqual(job.status, "done")
        seg = document.segments.get(position=1)
        machine = seg.versions.get()
        page = self.client.get(f"/traduction/documents/{document.pk}/")
        self.assertContains(page, "FR 武士道と云は死ぬ事と見付たり。")
        # correction : nouvelle version liée, l'ancienne est conservée
        self.client.post(f"/traduction/segments/{seg.pk}/action/", {"action": "human", "parent": machine.pk,
                                                                    "text": "Traduction corrigée."})
        corrected = seg.versions.get(origin="human_edit")
        self.assertEqual(corrected.parent, machine)
        self.client.post(f"/traduction/versions/{machine.pk}/action/", {"action": "validate"})
        self.client.post(f"/traduction/versions/{corrected.pk}/action/", {"action": "validate"})
        machine.refresh_from_db()
        corrected.refresh_from_db()
        self.assertEqual((machine.status, corrected.status), ("proposed", "validated"))
        seg.refresh_from_db()
        self.assertEqual(seg.state, "validated")
        self.assertEqual(seg.versions.count(), 2, "rien n'est écrasé")

    def test_bulk_validation_of_latest_proposals(self):
        self.add()
        document = TranslationDocument.objects.get()
        self.translate_all(document)
        self.client.post(f"/traduction/documents/{document.pk}/lot/", {
            "scope": "selected", "action": "validate", "segments": list(document.segments.values_list("pk", flat=True))})
        self.assertEqual(document.segments.filter(state="validated").count(), 3)

    def test_untranslatable_segments_are_not_sent(self):
        P.create_document(self.project, title="Ponctuation", text="文一。\n。」\n")
        document = TranslationDocument.objects.get(title="Ponctuation")
        self.translate_all(document)
        self.assertEqual(self.sent, ["文一。\n"])


class AccessTests(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.document = P.create_document(self.project, title="Doc", text="一つ目。二つ目。")
        self.secret = TranslationProject.objects.create(owner=self.owner, title="Projet secret fictif", confidential=True)
        self.secret_doc = P.create_document(self.secret, title="Doc secret", text="秘密の文。")
        self.other = User.objects.create_user("autre", password="motdepasse-solide-5", role="researcher")

    def test_other_researcher_gets_404_everywhere(self):
        self.client.force_login(self.other)
        seg = self.document.segments.first()
        for url in (f"/traduction/projets/{self.project.pk}/", f"/traduction/documents/{self.document.pk}/",
                    f"/traduction/segments/{seg.pk}/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertEqual(self.client.post(f"/traduction/segments/{seg.pk}/action/", {"action": "merge"}).status_code, 404)

    def test_admin_reads_ordinary_project_but_cannot_validate(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(f"/traduction/documents/{self.document.pk}/"), "一つ目。")
        seg = self.document.segments.first()
        v = TranslationVersion.objects.create(segment=seg, text="x", source_text=seg.source_text, origin="human")
        self.assertEqual(self.client.post(f"/traduction/versions/{v.pk}/action/", {"action": "validate"}).status_code, 403)

    def test_admin_sees_only_metadata_of_confidential_project(self):
        self.client.force_login(self.admin)
        page = self.client.get(f"/traduction/projets/{self.secret.pk}/")
        self.assertContains(page, "Projet secret fictif")
        self.assertContains(page, "confidentiel")
        self.assertNotContains(page, "Doc secret")
        self.assertEqual(self.client.get(f"/traduction/documents/{self.secret_doc.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/traduction/segments/{self.secret_doc.segments.first().pk}/").status_code, 404)
        listing = self.client.get("/traduction/projets/")
        self.assertContains(listing, "Projet secret fictif")
        self.assertNotContains(listing, f"/traduction/projets/{self.secret.pk}/\"")


class ConfidentialNoticeTests(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.secret = TranslationProject.objects.create(owner=self.owner, title="Projet secret fictif", confidential=True)
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "C1", "original_title": "架空の書",
                                                                "description_original": "架空の解題。続き。"})
        record.language = "lzh"
        record.save()
        self.record = record

    def test_copy_translate_locally_and_publish_explicitly(self):
        self.client.post(f"/traduction/notices/{self.record.record_id}/copier/",
                         {"project": self.secret.pk, "fields": ["description_original"]})
        document = TranslationDocument.objects.get(project=self.secret)
        self.assertEqual((document.source_kind, document.variety, P.notice_field(document)),
                         ("record", "kanbun", "description_original"))
        self.assertFalse(EditorialContent.objects.exists(), "rien n'est publié dans la notice")
        # moteur en ligne refusé (projet confidentiel) ; Argos simulé autorisé
        self.client.post(f"/traduction/documents/{document.pk}/lot/", {"scope": "untranslated", "action": "translate"})
        self.assertFalse(TranslationJob.objects.exists())
        self.secret.default_engine = "argos"
        self.secret.save()
        job = self.translate_all(document)
        self.assertEqual((job.engine, job.status, job.chars_sent), ("argos", "done", 0))
        self.assertEqual(self.sent, [], "aucun texte envoyé en ligne")
        # publication : refusée sans confirmation, puis proposition dans la notice
        self.client.post(f"/traduction/documents/{document.pk}/lot/", {
            "scope": "selected", "action": "validate", "segments": list(document.segments.values_list("pk", flat=True))})
        self.client.post(f"/traduction/documents/{document.pk}/publier/", {})
        self.assertFalse(EditorialContent.objects.exists())
        self.client.post(f"/traduction/documents/{document.pk}/publier/", {"confirm_publish": "1"})
        ed = EditorialContent.objects.get()
        self.assertEqual((ed.status, ed.target_field), ("proposed", "description_original"))
        self.assertTrue(ed.data["confidential_project"])
        self.assertTrue(ed.data["simulated"])
        self.assertIn("[Simulation Argos", ed.content)
        self.record.refresh_from_db()
        self.assertEqual(self.record.description_translation, "", "publier ne vaut pas adopter")

    def test_publish_requires_all_segments_validated(self):
        documents = P.copy_record_to_project(self.record, self.project, ["description_original"])
        with self.assertRaises(P.ProjectError):
            P.publish_to_record(documents[0], self.owner)
