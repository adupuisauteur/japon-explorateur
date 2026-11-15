"""2.0.0 — demande du 15 novembre 2026 : valider et adopter en une fois les traductions proposées.

Sur la fiche, sur la page « Traductions » d'une notice et sur la page d'une tâche de traduction de notices.
Réservé à l'administrateur, comme la validation champ par champ (C2). Données fictives ; DeepL simulé.
"""
from datetime import timedelta

from django.utils import timezone

from apps.catalog.models import EditorialContent
from apps.catalog.services import plan_bulk_validation, upsert_record

from .test_translation_records import RecordTranslationTestCase


class BulkValidationTests(RecordTranslationTestCase):
    def proposal(self, field, content, *, minutes_ago=0, source=None, **data):
        ed = EditorialContent.objects.create(
            record=self.record, kind="translation", target_field=field, origin="mt", content=content,
            source_text=source if source is not None else getattr(self.record, field), data=data)
        if minutes_ago:
            EditorialContent.objects.filter(pk=ed.pk).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
        return ed

    def test_a_translation_job_is_validated_in_one_click(self):
        job = self.translate_as(self.admin, fields=("original_title", "description_original", "subjects_original"))
        page = self.client.get(f"/traduction/taches/{job.pk}/")
        self.assertContains(page, "3 traductions proposées")
        self.assertContains(page, "Tout valider et adopter")
        response = self.client.post(f"/traduction/taches/{job.pk}/valider-tout/", follow=True)
        self.assertContains(response, "3 traduction(s) validée(s) et adoptée(s)")
        self.record.refresh_from_db()
        self.assertEqual(self.record.translated_title, "FR 架空の書")
        self.assertEqual(self.record.description_translation, "FR 架空の解題。")
        self.assertEqual(self.record.translated_title_origin, "mt")
        self.assertEqual(EditorialContent.objects.filter(record=self.record, status="validated").count(), 3)
        self.assertNotContains(self.client.get(f"/traduction/taches/{job.pk}/"), "Tout valider et adopter")

    def test_record_page_and_translations_page(self):
        self.proposal("original_title", "Titre fictif")
        self.proposal("description_original", "Description fictive")
        for url in (self.record.get_absolute_url(), f"/traduction/notices/{self.record.record_id}/"):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "Tout valider et adopter")
        response = self.client.post(f"/traduction/notices/{self.record.record_id}/valider-tout/",
                                    {"next": self.record.get_absolute_url() + "#editoriale"})
        self.assertRedirects(response, self.record.get_absolute_url() + "#editoriale", fetch_redirect_response=False)
        self.record.refresh_from_db()
        self.assertEqual((self.record.translated_title, self.record.description_translation),
                         ("Titre fictif", "Description fictive"))

    def test_latest_of_each_field_simulations_and_stale_originals_are_left_aside(self):
        old = self.proposal("original_title", "Ancien titre", minutes_ago=10)
        new = self.proposal("original_title", "Nouveau titre")
        simulated = self.proposal("description_original", "[Simulation]", simulated=True)
        stale = self.proposal("subjects_original", "Sujet", source="un autre original")
        chosen, skipped = plan_bulk_validation(list(EditorialContent.objects.filter(record=self.record)))
        self.assertEqual(chosen, [new])
        self.assertEqual({ed.pk: reason for ed, reason in skipped}, {
            old.pk: "une proposition plus récente du même champ est retenue",
            simulated.pk: "simulation (aucune traduction réelle)",
            stale.pk: "l'original a changé depuis cette traduction"})
        response = self.client.post(f"/traduction/notices/{self.record.record_id}/valider-tout/", follow=True)
        self.assertContains(response, "1 traduction(s) validée(s)")
        self.assertContains(response, "Écartée(s)")
        for ed, status in ((old, "proposed"), (new, "validated"), (simulated, "proposed"), (stale, "proposed")):
            ed.refresh_from_db()
            self.assertEqual(ed.status, status)

    def test_previously_adopted_translation_becomes_proposed_again(self):
        first = EditorialContent.objects.create(record=self.record, kind="translation", target_field="original_title",
                                                source_text="架空の書", content="Premier", origin="user",
                                                status="validated")
        self.proposal("original_title", "Second")
        self.client.post(f"/traduction/notices/{self.record.record_id}/valider-tout/")
        first.refresh_from_db()
        self.assertEqual(first.status, "proposed")
        self.record.refresh_from_db()
        self.assertEqual(self.record.translated_title, "Second")

    def test_reserved_to_the_administrator(self):
        self.proposal("original_title", "Titre fictif")
        job = self.translate_as(self.researcher)
        self.client.force_login(self.researcher)
        self.assertNotContains(self.client.get(self.record.get_absolute_url()), "Tout valider et adopter")
        self.assertNotContains(self.client.get(f"/traduction/taches/{job.pk}/"), "Tout valider et adopter")
        for url in (f"/traduction/notices/{self.record.record_id}/valider-tout/",
                    f"/traduction/taches/{job.pk}/valider-tout/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 403)
        self.assertFalse(EditorialContent.objects.filter(status="validated").exists())

    def test_job_validation_only_touches_that_job(self):
        other_cat = self.catalogue("codh-pmjt")
        other, _ = upsert_record(other_cat, {"source_id": "N2", "original_title": "別の架空の書"})
        foreign = EditorialContent.objects.create(record=other, kind="translation", target_field="original_title",
                                                  source_text="別の架空の書", content="Autre", origin="mt")
        job = self.translate_as(self.admin, fields=("original_title",))
        self.client.post(f"/traduction/taches/{job.pk}/valider-tout/")
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, "proposed")

    def test_unsafe_next_is_ignored(self):
        self.proposal("original_title", "Titre fictif")
        response = self.client.post(f"/traduction/notices/{self.record.record_id}/valider-tout/",
                                    {"next": "https://exemple.invalid/"})
        self.assertRedirects(response, f"/traduction/notices/{self.record.record_id}/", fetch_redirect_response=False)
