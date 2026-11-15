"""Évolution 1.3.0 — lot 8 : exports du module de traduction (T19). Textes fictifs, aucun moteur appelé."""
import csv
import io

from apps.accounts.models import User
from apps.translation import exports as X
from apps.translation import projects as P
from apps.translation.models import TranslationProject, TranslationVersion

from .helpers import AppTestCase

TEXT = "一つ目の文。二つ目の文。\n\n三つ目の文。四つ目の文。"


class ExportTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.researcher
        self.client.force_login(self.owner)
        self.project = TranslationProject.objects.create(owner=self.owner, title="Projet fictif d'export")
        self.document = P.create_document(self.project, title="Document fictif", text=TEXT)
        s1, s2, s3, s4 = self.document.segments.order_by("position")
        P.start_chapter(s3, "Chapitre fictif")
        # s1 : validée (humaine) ; s2 : proposition simulée (+ une rejetée) ; s3 : rien ; s4 : validée simulée
        P.validate_version(P.add_human_version(s1, self.owner, "Première phrase."), self.owner)
        P.reject_version(TranslationVersion.objects.create(segment=s2, text="Mauvaise.", source_text=s2.source_text,
                                                           origin="machine", engine="deepl"), self.owner)
        TranslationVersion.objects.create(segment=s2, text="Deuxième phrase.", source_text=s2.source_text,
                                          origin="machine", engine="argos", simulated=True)
        v4 = TranslationVersion.objects.create(segment=s4, text="Quatrième phrase.", source_text=s4.source_text,
                                               origin="machine", engine="argos", simulated=True)
        P.validate_version(v4, self.owner)
        self.segments = (s1, s2, s3, s4)

    def export(self, fmt, mode="validated", **params):
        return self.client.get(f"/traduction/projets/{self.project.pk}/exporter/", {"format": fmt, "mode": mode,
                                                                                    **params})


class CollectTests(ExportTestCase):
    def test_validated_only_versus_fallback(self):
        data = X.collect(self.project, mode="validated")
        self.assertEqual([r.status for r in data.rows], ["validated", "untranslated", "untranslated", "validated"])
        data = X.collect(self.project, mode="fallback")
        self.assertEqual([r.status for r in data.rows], ["validated", "proposed", "untranslated", "validated"])
        self.assertEqual(data.rows[1].text, "Deuxième phrase.")  # jamais la version rejetée
        self.assertEqual(data.rows[1].marks, ["non validée", "Simulation"])
        self.assertEqual(data.validated_share, 0.5)
        self.assertEqual(data.simulated_count, 2)

    def test_header_lists_engines_share_and_simulation(self):
        header = dict(X.header_lines(X.collect(self.project, mode="fallback")))
        self.assertEqual(header["Segments validés"], "2 sur 4 (50 %)")
        self.assertEqual(header["Moteurs utilisés"], "Argos Translate (local) (2) ; Saisie humaine (1)")
        self.assertIn("SIMULÉ", header["Simulation"])
        self.assertNotIn("Confidentialité", header)


class FormatTests(ExportTestCase):
    def test_bilingual_txt(self):
        response = self.export("bilingual_txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        text = response.content.decode("utf-8")
        self.assertIn("[1] 一つ目の文。\n    → Première phrase.", text)
        self.assertIn("[2] 二つ目の文。\n    → [non traduit — segment 2]", text)
        self.assertIn("--- Chapitre fictif ---", text)
        self.assertIn("→ Quatrième phrase. [Simulation]", text)
        self.assertNotIn("Mauvaise", text)

    def test_bilingual_md_fallback_marks_unvalidated(self):
        text = self.export("bilingual_md", mode="fallback").content.decode("utf-8")
        self.assertTrue(text.startswith("# Projet fictif d'export — Document fictif\n"))
        self.assertIn("> 二つ目の文。", text)
        self.assertIn("Deuxième phrase. *(non validée, Simulation)*", text)
        self.assertIn("### Chapitre fictif", text)

    def test_translation_only_keeps_paragraphs_and_legend(self):
        text = self.export("translation_txt", mode="fallback").content.decode("utf-8")
        self.assertIn("Légende : [*] traduction non validée", text)
        self.assertIn("Première phrase. Deuxième phrase. [*][S]\n\n--- Chapitre fictif ---\n\n", text)
        self.assertIn("[non traduit — segment 3] Quatrième phrase. [S]", text)
        self.assertIn("Moteurs utilisés :", text)
        self.assertIn("Segments validés : 2 sur 4 (50 %)", text)
        md = self.export("translation_md").content.decode("utf-8")
        self.assertIn("- **Segments validés** : 2 sur 4 (50 %)", md)

    def test_csv_table(self):
        content = self.export("table_csv", mode="fallback").content.decode("utf-8")
        self.assertTrue(content.startswith("﻿"))
        rows = list(csv.DictReader(io.StringIO(content.lstrip("﻿"))))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["original"], "一つ目の文。")
        self.assertEqual(rows[0]["statut"], "validée")
        self.assertEqual(rows[0]["validée par"], str(self.owner))
        self.assertEqual((rows[1]["statut"], rows[1]["simulation"], rows[1]["moteur"]),
                         ("non validée", "oui", "Argos Translate (local)"))
        self.assertEqual((rows[2]["chapitre"], rows[2]["statut"], rows[2]["traduction"]),
                         ("Chapitre fictif", "non traduit", ""))
        self.assertEqual(rows[0]["identifiant"], "D1-S1")

    def test_docx_bilingual_table_with_japanese_font(self):
        from docx import Document
        from docx.oxml.ns import qn

        response = self.export("bilingual_docx", mode="fallback")
        self.assertEqual(response["Content-Type"],
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        d = Document(io.BytesIO(response.content))
        fonts = d.styles["Normal"].element.rPr.find(qn("w:rFonts"))
        self.assertEqual(fonts.get(qn("w:eastAsia")), "Yu Mincho")
        self.assertEqual(len(d.tables), 2)  # un tableau avant le chapitre, un pour le chapitre
        first = d.tables[0]
        self.assertEqual([c.text for c in first.rows[0].cells], ["Japonais", "Français"])
        self.assertEqual(len(first.columns), 2)
        self.assertIn("一つ目の文。", first.rows[1].cells[0].text)
        self.assertEqual(first.rows[1].cells[1].text, "Première phrase.")
        self.assertIn("non validée · Simulation", first.rows[2].cells[1].text)
        self.assertIn("[non traduit — segment 3]", d.tables[1].rows[1].cells[1].text)
        self.assertTrue(any("Simulation" in p.text for p in d.paragraphs))

    def test_single_document_and_several_documents(self):
        other = P.create_document(self.project, title="Second document", text="五つ目の文。")
        text = self.export("bilingual_txt", document=other.pk).content.decode("utf-8")
        self.assertIn("Second document", text.splitlines()[0])
        self.assertNotIn("一つ目", text)
        whole = self.export("bilingual_txt").content.decode("utf-8")
        self.assertIn("=== Document fictif ===", whole)
        self.assertIn("=== Second document ===", whole)

    def test_translation_only_keeps_paragraph_breaks(self):
        other = P.create_document(self.project, title="Paragraphes", text="五つ目の文。六つ目の文。\n\n七つ目の文。")
        for segment, text in zip(other.segments.order_by("position"), ("Cinq.", "Six.", "Sept.")):
            P.validate_version(P.add_human_version(segment, self.owner, text), self.owner)
        body = self.export("translation_txt", document=other.pk).content.decode("utf-8")
        # 2.0.0 (U2) : la ligne de production suit le texte, séparée par un trait.
        self.assertIn("Cinq. Six.\n\nSept.\n\n" + "-" * 40 + "\nProduit le ", body)

    def test_original_is_never_modified(self):
        before = self.document.original_text
        for fmt in X.FORMATS:
            self.export(fmt, mode="fallback")
        self.document.refresh_from_db()
        self.assertEqual(self.document.original_text, before)
        self.assertTrue(P.integrity_ok(self.document))

    def test_confidential_mention(self):
        self.project.confidential = True
        self.project.save()
        self.assertIn("Confidentialité : projet confidentiel", self.export("bilingual_txt").content.decode("utf-8"))


class AccessTests(ExportTestCase):
    def test_export_reserved_to_owner_even_admin(self):
        self.client.force_login(self.admin)  # projet non confidentiel : l'admin le voit, mais ne l'exporte pas (E4)
        self.assertEqual(self.client.get(f"/traduction/projets/{self.project.pk}/").status_code, 200)
        self.assertEqual(self.export("bilingual_txt").status_code, 404)
        other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        self.client.force_login(other)
        self.assertEqual(self.export("table_csv").status_code, 404)
        self.client.force_login(self.reader)
        self.assertNotEqual(self.export("table_csv").status_code, 200)

    def test_bad_parameters(self):
        self.assertEqual(self.export("pdf").status_code, 400)
        self.assertEqual(self.export("bilingual_txt", mode="tout").status_code, 400)
        self.assertEqual(self.export("bilingual_txt", document=999999).status_code, 404)

    def test_pages_and_audit(self):
        from apps.core.models import AuditLog

        self.assertContains(self.client.get("/traduction/exports/"), "Projet fictif d&#x27;export")
        page = self.client.get(f"/traduction/projets/{self.project.pk}/exporter/")
        self.assertContains(page, "Word bilingue en tableau")
        self.assertContains(page, "4 segment(s) à traduire — 2 validé(s), 1 avec une proposition seulement")
        self.export("table_csv")
        log = AuditLog.objects.filter(action="translation.exported").get()
        self.assertNotIn("一つ目", log.summary)
        self.assertContains(self.client.get("/traduction/"), 'href="/traduction/exports/"')

    def test_record_exports_unchanged(self):
        """La fonction Word partagée garde son ancien nom (exports de notices 1.2.0)."""
        from apps.exports.generators import docx_gen

        self.assertIs(docx_gen._set_fonts, docx_gen.set_fonts)
