"""AT-11 à AT-16 : dossiers et annotations, exports et leurs exigences."""
import csv
import io
import json
import zipfile
from pathlib import Path

from django.conf import settings
from docx import Document

from apps.catalog.models import EditorialContent, Record
from apps.catalog.services import upsert_record
from apps.exports.models import ExportJob
from apps.library.models import Annotation, Collection, CollectionRecord

from .helpers import AppTestCase


class LibraryExportTests(AppTestCase):
    def setUp(self):
        super().setUp()
        cat = self.catalogue("codh-pmjt")
        self.r1, _ = upsert_record(cat, {"source_id": "A1", "original_title": "五輪書", "reading": "ごりんのしょ",
                                         "creator_original": "宮本武蔵", "composition_date_text": "寛永20年",
                                         "copy_date_text": "江戸後期", "description_original": "兵法書。地水火風空の五巻。",
                                         "source_url": "https://example.org/notice/A1",
                                         "rights_and_access": "Exemple : usage non commercial"})
        self.r2, _ = upsert_record(cat, {"source_id": "A2", "original_title": "葉隠", "reading": "はがくれ",
                                         "creator_original": "山本常朝"})
        self.r1.translated_title = "Traité des cinq roues"
        self.r1.translated_title_origin = "ai"
        self.r1.save()
        EditorialContent.objects.create(record=self.r1, kind="summary", content="Résumé généré (essai).", origin="ai")

    def _collection(self):
        r = self.client.post("/bibliotheque/dossiers/nouveau/", {"title": "Musashi — sources anciennes",
                                                                 "description": "Dossier d'essai", "visibility": "private",
                                                                 "keywords": "Musashi"})
        c = Collection.objects.filter(title="Musashi — sources anciennes").latest("pk")
        self.assertRedirects(r, c.get_absolute_url())
        self.client.post(f"/bibliotheque/dossiers/{c.pk}/sections/", {"title": "Sources primaires"})
        section = c.sections.get()
        self.client.post("/bibliotheque/dossiers/ajouter/", {"collection": c.pk, "record_ids": f"{self.r1.record_id},{self.r2.record_id}",
                                                             "section": section.pk})
        item = CollectionRecord.objects.get(collection=c, record=self.r1)
        self.client.post(f"/bibliotheque/dossiers/{c.pk}/elements/{item.pk}/", {"section": section.pk, "note": "Voir f. 3 r°"})
        self.client.post("/bibliotheque/notes/ajouter/", {"record": self.r1.pk, "body": "Copie tardive à vérifier",
                                                          "visibility": "private", "locator_type": "folio", "locator": "3r"})
        return c

    def test_at11_collection_notes_sections(self):
        c = self._collection()
        self.assertEqual(c.items.count(), 2)
        self.assertEqual(CollectionRecord.objects.get(collection=c, record=self.r1).note, "Voir f. 3 r°")
        note = Annotation.objects.get(record=self.r1)
        self.assertEqual((note.author, note.locator_type), (self.admin, "folio"))
        page = self.client.get(c.get_absolute_url())
        self.assertContains(page, "Sources primaires")
        self.assertContains(page, "五輪書")
        # retirer du dossier ne supprime pas la notice
        item = CollectionRecord.objects.get(collection=c, record=self.r2)
        self.client.post(f"/bibliotheque/dossiers/{c.pk}/elements/{item.pk}/", {"remove": "1"})
        self.assertTrue(Record.objects.filter(pk=self.r2.pk).exists())

    def _export(self, fmt, scope="collection", **extra):
        c = self._collection() if scope == "collection" else None
        params = {"scope": scope, "preset": "dossier", "format": fmt, "title": "Dossier Musashi",
                  "subtitle": "Sources", "subject": "Musashi", "author": "Arnaud", "header_text": "Projet Japon",
                  "footer_text": "Document de travail", "include_ai": "on", "include_notes": "on",
                  "pagination": "on", "toc": "on", "column_profile": "generic", "csv_separator": "semicolon", **extra}
        if c:
            params["collection"] = c.pk
        r = self.client.post("/exports/preparer/", params)
        job = ExportJob.objects.latest("pk")
        self.assertRedirects(r, job.get_absolute_url())
        self.assertEqual(job.status, "done", job.error)
        return job

    def _path(self, job, role="main"):
        return Path(settings.MEDIA_ROOT) / job.files.get(role=role).path

    def test_at13_preparation_and_preview(self):
        c = self._collection()
        r = self.client.post("/exports/apercu/", {"scope": "collection", "collection": c.pk, "preset": "dossier",
                                                  "format": "pdf", "title": "Titre essai", "subject": "Sujet",
                                                  "header_text": "En-tête X", "footer_text": "Pied Y", "include_ai": "on"})
        self.assertContains(r, "Titre essai")
        self.assertContains(r, "En-tête X")
        self.assertContains(r, "Pied Y")
        self.assertContains(r, "Sommaire")
        self.assertContains(r, "CODH")
        page = self.client.get(f"/exports/preparer/?scope=collection&collection={c.pk}")
        self.assertContains(page, "Musashi — sources anciennes")

    def test_at12_docx(self):
        job = self._export("docx")
        d = Document(self._path(job))
        text = "\n".join(p.text for p in d.paragraphs)
        self.assertIn("Dossier Musashi", text)
        self.assertIn("五輪書", text)
        tables = "\n".join(c.text for t in d.tables for row in t.rows for c in row.cells)
        self.assertIn("宮本武蔵", tables)
        self.assertIn("traduction générée par IA", tables)
        self.assertIn("Projet Japon", d.sections[1].header.paragraphs[0].text)
        self.assertIn("PAGE", d.sections[1].footer._element.xml)
        self.assertEqual(job.metadata["contains_ai_content"], True)

    def test_at12_pdf_with_japanese_font(self):
        job = self._export("pdf")
        data = self._path(job).read_bytes()
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 5000)
        from pypdf import PdfReader

        text = "".join(p.extract_text() for p in PdfReader(self._path(job)).pages)
        self.assertIn("五輪書", text)
        self.assertIn("Dossier Musashi", text)

    def test_at12_txt_and_json_and_at15_reimport(self):
        txt = self._path(self._export("txt")).read_text(encoding="utf-8")
        self.assertIn("MÉTADONNÉES DE L'EXPORT", txt.splitlines()[1])
        self.assertIn("五輪書", txt)
        job = self._export("json")
        payload = json.loads(self._path(job).read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["export_metadata"]["export_id"], job.export_uid)
        rec = next(r for r in payload["records"] if r["source"]["source_id"] == "A1")
        self.assertEqual(rec["record_id"], self.r1.record_id)
        self.assertTrue(self._path(job, "schema").exists())
        # réimport : aucune duplication
        before = Record.objects.count()
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.updates.models import ImportJob

        self.client.post("/mises-a-jour/import/nouveau/", {"file": SimpleUploadedFile("export.json", self._path(job).read_bytes()),
                                                           "catalogue": "classeur", "preset": "json_export"})
        imp = ImportJob.objects.latest("pk")
        self.assertEqual(imp.format, "json_export")
        mapping = {f"map_{k}": v for k, v in imp.mapping.items()}
        self.client.post(imp.get_absolute_url(), {"action": "stage", "duplicate_strategy": "version", **mapping})
        imp.refresh_from_db()
        self.assertEqual(imp.counts.get("new", 0), 0, imp.counts)
        self.client.post(imp.get_absolute_url(), {"action": "apply"})
        self.assertEqual(Record.objects.count(), before)

    def test_at14_csv_without_title_rows_and_manifest(self):
        job = self._export("csv", csv_bom="on")
        raw = self._path(job).read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(rows[0][0], "record_id", "première ligne = en-têtes, aucune ligne de titre")
        self.assertIn("五輪書", [c for row in rows for c in row])
        manifest = json.loads(self._path(job, "manifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["csv"]["delimiter"], ";")
        self.assertEqual(manifest["export_metadata"]["title"], "Dossier Musashi")
        comma = self._export("csv", csv_separator="comma")
        self.assertTrue(self._path(comma).read_text(encoding="utf-8").startswith("record_id,"))

    def test_at16_html_site_offline_and_zip(self):
        job = self._export("html")
        with zipfile.ZipFile(self._path(job)) as zf:
            names = zf.namelist()
            prefix = names[0].split("/")[0]
            self.assertIn(f"{prefix}/index.html", names)
            self.assertIn(f"{prefix}/assets/style.css", names)
            self.assertIn(f"{prefix}/assets/search-index.js", names)
            self.assertIn(f"{prefix}/donnees/references.json", names)
            self.assertIn(f"{prefix}/manifest.json", names)
            self.assertIn(f"{prefix}/fiches/{self.r1.record_id}.html", names)
            index = zf.read(f"{prefix}/index.html").decode("utf-8")
            for ref in ("http://", "https://"):
                # aucune ressource externe chargée par la page (seuls des liens vers catalogues sont permis)
                self.assertNotIn(f'src="{ref}', index)
                self.assertNotIn(f'href="{ref}cdn', index)
            fiche = zf.read(f"{prefix}/fiches/{self.r1.record_id}.html").decode("utf-8")
            self.assertIn("五輪書", fiche)
            self.assertIn("../assets/style.css", fiche)
        full = self._export("zip")
        with zipfile.ZipFile(self._path(full)) as zf:
            joined = "\n".join(zf.namelist())
            self.assertIn(".csv", joined)
            self.assertIn(".txt", joined)

    def test_ai_content_can_be_excluded(self):
        job = self._export("json", include_ai="")
        payload = json.loads(self._path(job).read_text(encoding="utf-8"))
        rec = next(r for r in payload["records"] if r["source"]["source_id"] == "A1")
        self.assertEqual(rec["translated_title"], "")
        self.assertEqual(rec["editorial"], [])

    def test_regeneration_detects_changes(self):
        job = self._export("txt")
        self.assertIs(self.client.get(job.get_absolute_url()).context["changed"], False)
        upsert_record(self.catalogue("codh-pmjt"), {"source_id": "A1", "original_title": "五輪書（改）"})
        self.assertIs(self.client.get(job.get_absolute_url()).context["changed"], True)
        r = self.client.post(f"/exports/{job.pk}/regenerer/")
        new = ExportJob.objects.latest("pk")
        self.assertEqual(new.regenerated_from, job)
        self.assertEqual(new.status, "done")
        self.assertEqual(self.client.get(f"/exports/{new.pk}/fichiers/{new.main_file.pk}/").status_code, 200)

    def test_export_download_is_owner_only(self):
        job = self._export("txt")
        self.client.force_login(self.researcher)
        self.assertEqual(self.client.get(f"/exports/{job.pk}/fichiers/{job.main_file.pk}/").status_code, 403)
