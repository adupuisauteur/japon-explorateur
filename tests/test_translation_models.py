"""Évolution 1.3.0 — lot 1 : fondations du module de traduction.

Modèles et contraintes, règles de suppression, transfert de propriété (compte anonymisé ou supprimé),
droits d'accès (décisions C2, D3, D4), menu et interface d'administration. Données fictives uniquement.
"""
from django.contrib import admin
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Catalogue, Record
from apps.translation import models as m
from apps.translation.ownership import TransferImpossible, release_user_translation_data
from apps.translation.permissions import (can_edit_project, can_use_translation, can_validate_project,
                                          can_view_project, can_view_project_metadata, projects_metadata_only_for,
                                          projects_with_content_for)

from .helpers import AppTestCase


def make_project(owner, title="Projet fictif", confidential=False):
    return m.TranslationProject.objects.create(owner=owner, title=title, confidential=confidential)


def make_segment(project, text="これは架空の文です。", position=1):
    doc = m.TranslationDocument.objects.create(project=project, title="Document fictif", original_text=text)
    return m.TranslationSegment.objects.create(document=doc, position=position, source_text=text)


def make_version(segment, status="proposed", text="Ceci est une phrase fictive."):
    return m.TranslationVersion.objects.create(segment=segment, text=text, source_text=segment.source_text,
                                               engine="deepl", origin="machine", status=status)


class ConstraintTests(AppTestCase):
    def test_only_one_validated_version_per_segment(self):
        seg = make_segment(make_project(self.researcher))
        make_version(seg, "validated")
        make_version(seg, "proposed")
        make_version(seg, "rejected")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_version(seg, "validated")

    def test_validated_versions_allowed_on_different_segments(self):
        project = make_project(self.researcher)
        make_version(make_segment(project, position=1), "validated")
        make_version(make_segment(project, position=1), "validated")  # autre document

    def test_one_setting_per_user_and_engine(self):
        m.EngineSetting.objects.create(user=self.researcher, engine="deepl")
        m.EngineSetting.objects.create(user=self.admin, engine="deepl")
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.EngineSetting.objects.create(user=self.researcher, engine="deepl")

    def test_one_glossary_entry_per_source_term(self):
        g = m.Glossary.objects.create(owner=self.researcher, name="Ères fictives")
        m.GlossaryEntry.objects.create(glossary=g, source_term="元禄", target_term="ère Genroku")
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.GlossaryEntry.objects.create(glossary=g, source_term="元禄", target_term="Genroku")

    def test_segment_positions_can_be_swapped_in_one_transaction(self):
        """Contrainte différée : la renumérotation (fusion, division) ne viole rien en cours de transaction."""
        project = make_project(self.researcher)
        a = make_segment(project, "一。", 1)
        b = m.TranslationSegment.objects.create(document=a.document, position=2, source_text="二。")
        with transaction.atomic():
            m.TranslationSegment.objects.filter(pk=a.pk).update(position=2)
            m.TranslationSegment.objects.filter(pk=b.pk).update(position=1)
        a.refresh_from_db()
        self.assertEqual(a.position, 2)

    def test_duplicate_segment_position_is_refused_at_commit(self):
        """La vérification a lieu à la validation de la transaction ; on la force ici, dans un point de reprise."""
        project = make_project(self.researcher)
        a = make_segment(project, "一。", 1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                m.TranslationSegment.objects.create(document=a.document, position=1, source_text="二。")
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS translation_segment_position IMMEDIATE")
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS translation_segment_position DEFERRED")
        self.assertEqual(m.TranslationSegment.objects.filter(document=a.document).count(), 1)


class DeletionRuleTests(AppTestCase):
    def test_project_deletion_cascades_to_content_but_keeps_jobs(self):
        project = make_project(self.researcher)
        seg = make_segment(project)
        version = make_version(seg)
        job = m.TranslationJob.objects.create(user=self.researcher, project=project, engine="deepl")
        m.TranslationJobItem.objects.create(job=job, position=1, segment=seg, version=version)
        project.delete()
        self.assertFalse(m.TranslationSegment.objects.exists())
        self.assertFalse(m.TranslationVersion.objects.exists())
        job.refresh_from_db()
        self.assertIsNone(job.project)
        item = job.items.get()
        self.assertIsNone(item.segment)
        self.assertIsNone(item.version)

    def test_edited_version_survives_deletion_of_its_parent(self):
        seg = make_segment(make_project(self.researcher))
        parent = make_version(seg)
        child = m.TranslationVersion.objects.create(segment=seg, text="Corrigé.", source_text=seg.source_text,
                                                    origin="human_edit", parent=parent)
        parent.delete()
        child.refresh_from_db()
        self.assertIsNone(child.parent)

    def test_glossary_deletion_only_removes_the_link(self):
        project = make_project(self.researcher)
        g = m.Glossary.objects.create(owner=self.researcher, name="Glossaire fictif")
        m.ProjectGlossary.objects.create(project=project, glossary=g)
        g.delete()
        self.assertTrue(m.TranslationProject.objects.filter(pk=project.pk).exists())
        self.assertFalse(m.ProjectGlossary.objects.exists())

    def test_record_deletion_keeps_the_document(self):
        record = Record.objects.create(catalogue=Catalogue.objects.get(code="codh-pmjt"), source_id="essai-1",
                                       original_title="架空の書")
        project = make_project(self.researcher)
        doc = m.TranslationDocument.objects.create(project=project, title="Notice copiée", original_text="架空の書",
                                                   source_kind="record", record=record)
        record.delete()
        doc.refresh_from_db()
        self.assertIsNone(doc.record)
        self.assertEqual(doc.original_text, "架空の書")


class OwnershipTransferTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.project = make_project(self.researcher, "Projet du chercheur", confidential=True)
        self.glossary = m.Glossary.objects.create(owner=self.researcher, name="Glossaire du chercheur")
        m.EngineSetting.objects.create(user=self.researcher, engine="deepl", encrypted_key="chiffré-fictif")
        m.TranslationPreference.objects.create(user=self.researcher, default_engine="deepl")

    def test_anonymisation_gives_projects_to_the_acting_admin_and_erases_keys(self):
        response = self.client.post(f"/comptes/utilisateurs/{self.researcher.pk}/anonymiser/")
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.glossary.refresh_from_db()
        self.assertEqual(self.project.owner, self.admin)
        self.assertEqual(self.glossary.owner, self.admin)
        self.assertEqual(self.project.transferred_from, "chercheur")
        self.assertIsNotNone(self.project.transferred_at)
        self.assertFalse(m.EngineSetting.objects.filter(user=self.researcher).exists())
        self.assertFalse(m.TranslationPreference.objects.filter(user=self.researcher).exists())
        self.assertTrue(self.project.confidential, "le projet reste confidentiel")
        self.assertTrue(can_view_project(self.admin, self.project), "devenu propriétaire, l'administrateur le lit")
        self.researcher.refresh_from_db()
        self.assertFalse(self.researcher.is_active)

    def test_real_deletion_of_an_account_transfers_instead_of_deleting(self):
        self.researcher.delete()
        self.project.refresh_from_db()
        self.assertEqual(self.project.owner, self.admin)
        self.assertEqual(m.TranslationProject.objects.count(), 1)
        self.assertEqual(m.Glossary.objects.count(), 1)

    def test_deletion_refused_without_another_active_admin(self):
        lone_admin = self.admin
        make_project(lone_admin, "Projet de l'administrateur")
        # La suppression Django n'ouvre pas de point de reprise : le refus annule la transaction englobante.
        with self.assertRaises(TransferImpossible):
            with transaction.atomic():
                lone_admin.delete()
        self.assertTrue(User.objects.filter(pk=lone_admin.pk).exists())
        self.assertEqual(m.TranslationProject.objects.filter(owner=lone_admin).count(), 1)

    def test_recipient_must_be_an_active_admin(self):
        with self.assertRaises(TransferImpossible):
            release_user_translation_data(self.researcher, recipient=self.reader)
        self.project.refresh_from_db()
        self.assertEqual(self.project.owner, self.researcher, "rien n'a été transféré")
        self.assertTrue(m.EngineSetting.objects.filter(user=self.researcher).exists(), "rien n'a été effacé")

    def test_account_without_projects_is_released_without_recipient(self):
        recipient, projects, glossaries = release_user_translation_data(self.reader)
        self.assertEqual((recipient, projects, glossaries), (None, 0, 0))


class PermissionTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.other = User.objects.create_user("autre", password="motdepasse-solide-4", role="researcher")
        self.public = make_project(self.researcher, "Projet ordinaire")
        self.secret = make_project(self.researcher, "Projet confidentiel", confidential=True)

    def test_reader_has_no_access(self):
        self.assertFalse(can_use_translation(self.reader))
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/traduction/").status_code, 403)

    def test_owner_has_full_rights(self):
        for project in (self.public, self.secret):
            self.assertTrue(can_view_project(self.researcher, project))
            self.assertTrue(can_edit_project(self.researcher, project))
            self.assertTrue(can_validate_project(self.researcher, project))

    def test_other_researcher_sees_nothing(self):
        for project in (self.public, self.secret):
            self.assertFalse(can_view_project(self.other, project))
            self.assertFalse(can_view_project_metadata(self.other, project))
        self.assertFalse(projects_with_content_for(self.other).exists())

    def test_admin_reads_ordinary_projects_but_only_metadata_of_confidential_ones(self):
        self.assertTrue(can_view_project(self.admin, self.public))
        self.assertFalse(can_view_project(self.admin, self.secret))
        self.assertTrue(can_view_project_metadata(self.admin, self.secret))
        self.assertEqual(list(projects_metadata_only_for(self.admin)), [self.secret])
        self.assertNotIn(self.secret, projects_with_content_for(self.admin))

    def test_only_the_owner_validates(self):
        self.assertFalse(can_validate_project(self.admin, self.public))
        self.assertFalse(can_validate_project(self.other, self.public))

    def test_home_page_lists_own_and_others_projects(self):
        self.client.force_login(self.researcher)
        page = self.client.get("/traduction/")
        self.assertContains(page, "Projet ordinaire")
        self.assertContains(page, "Projet confidentiel")
        self.client.force_login(self.admin)
        page = self.client.get("/traduction/")
        self.assertContains(page, "métadonnées seulement")


class MenuAndAdminTests(AppTestCase):
    def test_menu_entry_for_researcher_not_for_reader(self):
        self.client.force_login(self.researcher)
        self.assertContains(self.client.get("/"), 'href="/traduction/"')
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get("/"), 'href="/traduction/"')

    def test_project_content_is_not_exposed_in_django_admin(self):
        for model in (m.TranslationProject, m.TranslationDocument, m.TranslationSegment, m.TranslationVersion):
            self.assertFalse(admin.site.is_registered(model), model.__name__)

    def test_engine_keys_are_never_shown_in_django_admin(self):
        model_admin = admin.site._registry[m.EngineSetting]
        self.assertIn("encrypted_key", model_admin.exclude)


class NoExistingTableTouchedTests(TestCase):
    def test_initial_migration_only_targets_translation_tables(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("sqlmigrate", "translation", "0001", stdout=out)
        sql = out.getvalue()
        import re

        tables = set(re.findall(r'(?:CREATE TABLE|ALTER TABLE) "([a-z_]+)"', sql))
        self.assertTrue(tables)
        self.assertTrue(all(t.startswith("translation_") for t in tables), tables)
