"""2.0.0-rc1 : jeu d'essai fictif et procédure « Essayer J-ed »."""
from django.core.management import call_command

from apps.catalog.models import Catalogue, Record
from apps.catalog.services import duplicate_candidates, upsert_record
from apps.core import jeu_essai as J

from .helpers import AppTestCase


def services_sources():
    from apps.catalog.models import Catalogue

    return list(Catalogue.objects.filter(enabled_for_search=True).values_list("code", flat=True))


class DemoDatasetTests(AppTestCase):
    def test_load_is_complete_idempotent_and_separate(self):
        real, _ = upsert_record(self.catalogue("ndl"), {"source_id": "VRAI-1", "original_title": "五輪書"})
        summary = J.load(self.admin)
        self.assertEqual(summary["notices"], 38)
        self.assertEqual(J.load(self.admin)["créées"], 0)  # recharger ne duplique rien
        demo = Record.objects.filter(catalogue__code="jeu-essai")
        self.assertEqual(demo.count(), 38)
        self.assertTrue(all("fictive" in r.rights_and_access for r in demo))
        self.assertTrue(Record.objects.filter(pk=real.pk).exists())
        from apps.library.models import Collection, LibraryEntry
        from apps.translation.models import TranslationProject
        folder = Collection.objects.get(title=J.FOLDER_TITLE)
        self.assertEqual(folder.items.count(), 8)
        self.assertEqual(LibraryEntry.objects.filter(user=self.admin, record__catalogue__code="jeu-essai").count(), 8)
        project = TranslationProject.objects.get(title=J.PROJECT_TITLE)
        self.assertEqual(sorted(project.documents.values_list("variety", flat=True)), ["classical", "modern"])

    def test_procedure_expectations_hold(self):
        """Résultats annoncés par la page d'aide « Essayer J-ed »."""
        from apps.catalog.search import local_search
        from apps.connectors.base import SearchQuery

        J.load(self.admin)
        old = Record.objects.get(source_id="ESSAI-101")
        found = [r.source_id for r, _score, _reasons in duplicate_candidates(old)]
        self.assertIn("ESSAI-102", found)  # 架空國史略 ↔ 架空国史略
        self.assertGreaterEqual(local_search(SearchQuery(text="架空")).count(), 15)
        # une seule fois par recherche : la source du jeu d'essai n'a pas de connecteur propre
        from apps.searching import services
        session = services.run_all_sources(services.create_session(self.admin, query="架空国史略",
                                                                   sources=services_sources()))
        ids = list(session.results.values_list("source_id", flat=True))
        self.assertEqual(len(ids), len(set(ids)), ids)
        self.client.force_login(self.admin)
        page = self.client.get(Record.objects.get(source_id="ESSAI-003").get_absolute_url())
        self.assertContains(page, "example.org/jeu-essai/003")

    def test_remove_only_touches_the_dataset_and_keeps_used_records(self):
        real, _ = upsert_record(self.catalogue("ndl"), {"source_id": "VRAI-1", "original_title": "五輪書"})
        J.load(self.admin)
        from apps.library.models import Collection
        Collection.objects.create(owner=self.admin, title="Mon dossier")
        summary = J.remove()
        self.assertEqual(summary["notices"], 38)
        self.assertFalse(Catalogue.objects.filter(code="jeu-essai").exists())
        self.assertTrue(Record.objects.filter(pk=real.pk).exists())
        self.assertTrue(Collection.objects.filter(title="Mon dossier").exists())
        self.assertEqual(J.present(), 0)

    def test_admin_page_and_command(self):
        self.client.force_login(self.admin)
        page = self.client.get("/administration/jeu-essai/")
        self.assertContains(page, "Charger le jeu d'essai")
        self.client.post("/administration/jeu-essai/", {"action": "charger"})
        self.assertEqual(J.present(), 38)
        loaded = self.client.get("/administration/jeu-essai/")
        self.assertContains(loaded, "Retirer le jeu d'essai")
        # Recette rc1 (18 novembre 2026) : la procédure s'ouvre dans un nouvel onglet, pour la suivre à côté.
        self.assertContains(loaded, 'href="/aide/essayer-j-ed/" target="_blank" rel="noopener"')
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post("/administration/jeu-essai/", {"action": "retirer"}).status_code, 403)
        self.assertEqual(J.present(), 38)
        import io
        out = io.StringIO()
        call_command("jeu_essai", "--retirer", stdout=out)
        self.assertIn("38 notice(s)", out.getvalue())
        call_command("jeu_essai", "--charger", stdout=out)
        self.assertEqual(J.present(), 38)
