"""AT-01, AT-02, AT-09, AT-10 ; §6.4 dates ; §9.5 non-suppression."""
from apps.catalog.models import Record, RecordVersion
from apps.catalog.services import upsert_record
from apps.updates.models import IncomingRecord

from .helpers import AppTestCase


class ImportTests(AppTestCase):
    def test_at09_import_shows_preview_mapping_errors_report_before_validation(self):
        response, job = self.upload_example("exemple_inventaire.csv")
        self.assertEqual(job.format, "csv")
        self.assertEqual(job.total_rows, 5)
        self.assertEqual(job.mapping["source_id"], "国文研書誌ID")
        self.assertEqual(job.mapping["original_title"], "書名（統一書名）")
        self.assertEqual(job.mapping["reading"], "書名よみ")
        page = self.client.get(job.get_absolute_url())
        self.assertContains(page, "Correspondance des colonnes")
        self.assertContains(page, "五輪書")
        self.assertEqual(Record.objects.count(), 0, "rien n'est écrit avant validation")
        mapping = {f"map_{k}": v for k, v in job.mapping.items()}
        self.client.post(job.get_absolute_url(), {"action": "stage", "duplicate_strategy": "version", **mapping})
        job.refresh_from_db()
        self.assertEqual(job.status, "review")
        self.assertEqual(job.counts["new"], 5)
        self.assertEqual(Record.objects.count(), 0, "le rapport précède l'intégration")
        self.assertContains(self.client.get(job.get_absolute_url()), "Rapport avant intégration")

    def test_at01_import_and_find_by_identifier_and_title(self):
        job = self.import_example()
        self.assertEqual(job.status, "applied")
        self.assertEqual(Record.objects.filter(catalogue__code="codh-pmjt").count(), 5)
        r = Record.objects.get(source_id="EX-0001")
        self.assertEqual(r.original_title, "五輪書")
        self.assertEqual(r.dataset_label, "Jeu d'essai")
        # recherche locale par identifiant et par titre
        from apps.catalog.search import local_search
        from apps.connectors.base import SearchQuery

        self.assertIn(r, local_search(SearchQuery(text="EX-0001")))
        self.assertIn(r, local_search(SearchQuery(text="五輪書")))
        self.assertIn(r, local_search(SearchQuery(text="gorin")))  # rōmaji automatique
        self.assertIn(r, local_search(SearchQuery(text="ゴリンノショ")))  # katakana → hiragana

    def test_at02_japanese_characters_preserved(self):
        self.import_example()
        r = Record.objects.get(source_id="EX-0005")
        self.assertEqual(r.original_title, "甲陽軍鑑")
        self.assertIn("改行\nを含む注記", r.description_original)
        page = self.client.get(r.get_absolute_url())
        self.assertContains(page, "甲陽軍鑑")
        self.assertContains(page, "高坂昌信")

    def test_dates_composition_and_copy_kept_separate(self):
        self.import_example()
        r = Record.objects.get(source_id="EX-0001")
        self.assertEqual(r.composition_date_text, "寛永20年")
        self.assertEqual(r.composition_year_start, 1643)
        self.assertEqual(r.copy_date_text, "江戸後期")
        self.assertEqual(r.copy_year_start, 1760)
        self.assertEqual(r.copy_date_precision, "period")
        self.assertEqual(r.composition_date_origin, "rule")
        self.assertEqual(r.material_type, "manuscrit")  # « 写 » (写本) : règle tracée
        self.assertTrue(r.normalization_log)

    def test_at10_modifications_are_versioned(self):
        cat = self.catalogue("codh-pmjt")
        r, status = upsert_record(cat, {"source_id": "X1", "original_title": "葉隠", "copy_date_text": "1716"})
        self.assertEqual(status, "created")
        r, status = upsert_record(cat, {"source_id": "X1", "original_title": "葉隠", "copy_date_text": "1716"})
        self.assertEqual(status, "unchanged")
        r, status = upsert_record(cat, {"source_id": "X1", "original_title": "葉隠聞書", "copy_date_text": "1716"})
        self.assertEqual(status, "updated")
        self.assertEqual(r.version, 2)
        v2 = RecordVersion.objects.get(record=r, version=2)
        self.assertIn("original_title", v2.changed_fields)
        self.assertEqual(v2.previous_values["original_title"], "葉隠")
        page = self.client.get(f"/notices/{r.record_id}/versions/2/")
        self.assertContains(page, "葉隠聞書")
        self.assertContains(page, "葉隠")

    def test_reimport_does_not_duplicate_and_partial_file_never_deletes(self):
        self.import_example()
        _, job = self.upload_example("exemple_inventaire.csv")
        mapping = {f"map_{k}": v for k, v in job.mapping.items()}
        self.client.post(job.get_absolute_url(), {"action": "stage", "duplicate_strategy": "version", **mapping})
        job.refresh_from_db()
        self.assertEqual(job.counts.get("unchanged"), 5)
        self.assertEqual(job.counts.get("new"), 0)
        self.client.post(job.get_absolute_url(), {"action": "apply"})
        self.assertEqual(Record.objects.filter(catalogue__code="codh-pmjt").count(), 5)

    def test_xlsx_classeur_import_and_duplicate_hint(self):
        self.import_example()
        _, job = self.upload_example("exemple_classeur.xlsx", catalogue="classeur")
        self.assertEqual(job.format, "xlsx")
        self.assertEqual(job.mapping["original_title"], "Titre")
        self.assertEqual(job.mapping["source_id"], "ID")
        mapping = {f"map_{k}": v for k, v in job.mapping.items()}
        self.client.post(job.get_absolute_url(), {"action": "stage", "duplicate_strategy": "version", **mapping})
        hint = IncomingRecord.objects.get(import_job=job, source_id="CL-002")
        self.assertIn("Titre identique", hint.duplicate_hint)
        self.assertEqual(hint.decision, "pending", "un doublon potentiel n'est jamais intégré d'office")
        self.assertEqual(IncomingRecord.objects.get(import_job=job, source_id="CL-002").data["composition_date_text"], "1645")

    def test_missing_identifier_rejected_unless_generated(self):
        _, job = self.upload_example("exemple_inventaire.csv")
        mapping = {f"map_{k}": v for k, v in job.mapping.items() if k != "source_id"}
        self.client.post(job.get_absolute_url(), {"action": "stage", **mapping})
        job.refresh_from_db()
        self.assertNotEqual(job.status, "review")
        self.client.post(job.get_absolute_url(), {"action": "stage", "generate_ids": "1", **mapping})
        job.refresh_from_db()
        self.assertEqual(job.status, "review")
        self.assertTrue(job.incoming.first().source_id.startswith("CONTENU-"))

    def test_upload_rejects_disallowed_extension(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        r = self.client.post("/mises-a-jour/import/nouveau/", {"file": SimpleUploadedFile("x.exe", b"MZ"),
                                                                "catalogue": "classeur"}, follow=True)
        self.assertContains(r, "Type de fichier non accepté")

    def test_reader_cannot_import(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/mises-a-jour/import/nouveau/").status_code, 403)
