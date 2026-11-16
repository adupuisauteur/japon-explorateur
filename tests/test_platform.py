"""AT-19 (sauvegarde/restauration), AT-20 (interface), premier démarrage, rôles, PWA, outils japonais."""
import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import Client, TransactionTestCase, override_settings

from apps.accounts.models import User
from apps.backups.models import BackupJob
from apps.backups.services import create_backup, restore_backup, verify_backup
from apps.catalog.models import Record
from apps.catalog.services import upsert_record
from apps.core import japanese as jp
from apps.library.models import Collection

from .helpers import TMP, AppTestCase

MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"


class PlatformTests(AppTestCase):
    def test_backup_ui(self):
        self.assertEqual(self.client.post("/administration/sauvegardes/creer/", {"kind": "db"}).status_code, 302)
        job = BackupJob.objects.latest("pk")
        self.assertEqual(job.status, "done")
        self.assertContains(self.client.get("/administration/sauvegardes/"), "Sauvegardes")
        r = self.client.post(f"/administration/sauvegardes/{job.pk}/restaurer/", {"confirmation": "non"}, follow=True)
        self.assertContains(r, "Tapez RESTAURER")

    def test_at20_main_pages_render_desktop_and_mobile(self):
        cat = self.catalogue("codh-pmjt")
        r, _ = upsert_record(cat, {"source_id": "U1", "original_title": "太平記", "copy_date_text": "慶長八年"})
        c = Collection.objects.create(owner=self.admin, title="Dossier test")
        urls = ["/", "/recherche/", "/bibliotheque/", "/bibliotheque/dossiers/", "/sources/", "/sources/kokusho/",
                "/mises-a-jour/", "/mises-a-jour/import/nouveau/", "/administration/", "/administration/parametres/",
                "/administration/journal/", "/administration/sauvegardes/", "/ia/preferences/", "/ia/fournisseurs/",
                "/ia/taches/", "/ia/tarifs/", "/exports/", f"/exports/preparer/?scope=collection&collection={c.pk}",
                r.get_absolute_url(), c.get_absolute_url(), "/recherche/historique/", "/recherche/enregistrees/",
                "/comptes/mon-compte/", "/comptes/utilisateurs/", "/bibliotheque/corrections/", "/notices/corbeille/",
                "/hors-ligne/"]
        for ua in ("Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0", MOBILE_UA):
            client = Client(HTTP_USER_AGENT=ua)
            client.force_login(self.admin)
            for url in urls:
                resp = client.get(url)
                self.assertEqual(resp.status_code, 200, f"{url} → {resp.status_code}")
                if url != "/hors-ligne/":
                    self.assertContains(resp, 'name="viewport"')
        page = self.client.get("/")
        for label in ("Accueil", "Rechercher", "Bibliothèque", "Dossiers", "Sources", "Administration"):
            self.assertContains(page, label)
        self.assertContains(page, "navbar-toggler")  # navigation compacte sur mobile

    def test_quick_search_from_every_page_and_session(self):
        upsert_record(self.catalogue("codh-pmjt"), {"source_id": "Q1", "original_title": "葉隠"})
        r = self.client.get("/recherche/rapide/", {"q": "葉隠"}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Interrogation des sources")
        session_url = r.redirect_chain[-1][0]
        posted = self.client.post(session_url + "source/local/")
        results = self.client.get(session_url + "resultats/")
        if "葉隠" not in results.content.decode():  # 2.0.0, lot 9 : test parfois instable, on garde la cause
            from apps.catalog.models import Catalogue
            from apps.searching.models import SearchSession

            session = SearchSession.objects.order_by("-pk").first()
            self.fail("Résultat local absent. Diagnostic : "
                      f"POST source → {posted.status_code} ; GET résultats → {results.status_code} ; "
                      f"sources={getattr(session, 'sources', None)} ; stats={getattr(session, 'source_stats', None)} ; "
                      f"résultats en base={session.results.count() if session else None} ; "
                      f"notices={list(Record.objects.values_list('original_title', 'record_status'))} ; "
                      f"catalogues={list(Catalogue.objects.values_list('code', 'status', 'enabled_for_search'))}")

    def test_pwa_manifest_and_service_worker(self):
        m = self.client.get("/manifest.webmanifest").json()
        self.assertEqual(m["display"], "standalone")
        self.assertTrue(any(i["sizes"] == "512x512" for i in m["icons"]))
        sw = self.client.get("/sw.js")
        self.assertEqual(sw["Content-Type"], "application/javascript")
        self.assertIn("fiches-v1", sw.content.decode())

    def test_roles_reader_cannot_modify(self):
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "R1", "original_title": "吾妻鏡"})
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post("/bibliotheque/ajouter/", {"record_ids": record.record_id}).status_code, 403)
        self.assertEqual(self.client.get("/administration/").status_code, 403)
        self.assertEqual(self.client.post(f"/notices/{record.record_id}/statut/", {"status": "deleted"}).status_code, 403)
        self.assertEqual(self.client.get(record.get_absolute_url()).status_code, 200)
        self.client.force_login(self.researcher)
        self.client.post(f"/bibliotheque/corrections/{record.record_id}/proposer/",
                         {"field": "original_title", "proposed_value": "x", "justification": "y"})
        record.refresh_from_db()
        self.assertEqual(record.original_title, "吾妻鏡", "la donnée source n'est jamais corrigeable")
        self.client.post(f"/bibliotheque/corrections/{record.record_id}/proposer/",
                         {"field": "period", "proposed_value": "kamakura", "justification": "chronique de Kamakura"})
        self.client.force_login(self.admin)
        from apps.library.models import CorrectionProposal

        prop = CorrectionProposal.objects.get(field="period")
        self.client.post(f"/bibliotheque/corrections/{prop.pk}/decision/", {"decision": "accept"})
        record.refresh_from_db()
        self.assertEqual(record.period, "kamakura")
        self.assertEqual(record.versions.first().change_type, "editorial")

    def test_soft_delete_is_reversible(self):
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "D1", "original_title": "平家物語"})
        self.client.post(f"/notices/{record.record_id}/statut/", {"status": "deleted"})
        record.refresh_from_db()
        self.assertEqual(record.record_status, "deleted")
        self.assertContains(self.client.get("/notices/corbeille/"), "平家物語")
        self.client.post(f"/notices/{record.record_id}/statut/", {"status": "active"})
        record.refresh_from_db()
        self.assertEqual(record.record_status, "active")

    def test_japanese_helpers(self):
        self.assertEqual(jp.parse_historical_date("寛永五年")["start"], 1628)
        self.assertEqual(jp.parse_historical_date("元禄頃")["precision"], "estimated")
        self.assertEqual(jp.parse_historical_date("XVIIe siècle")["end"], 1700)
        self.assertEqual(jp.romaji_to_hiragana("Gorin no shō"), "ごりん の しょう")
        self.assertEqual(jp.to_shinjitai("國學"), "国学")
        self.assertEqual(jp.search_normalize("ゴリン　Shō"), "ごりん sho")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class FirstRunTests(AppTestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        from apps.core.middleware import FirstRunMiddleware  # noqa: F401

    def test_first_run_wizard_creates_admin_and_sources(self):
        from apps.catalog.models import Catalogue

        r = self.client.get("/", follow=False)
        self.assertRedirects(r, "/comptes/premier-demarrage/")
        r = self.client.post("/comptes/premier-demarrage/", {
            "username": "arnaud", "display_name": "Arnaud", "email": "", "password1": "Une-phrase-solide-2026",
            "password2": "Une-phrase-solide-2026", "default_search_mode": "selective", "backup_enabled": "on"})
        self.assertRedirects(r, "/mises-a-jour/import/nouveau/")
        u = User.objects.get(username="arnaud")
        self.assertEqual(u.role, "admin")
        self.assertTrue(Catalogue.objects.filter(code="kokusho").exists())
        self.assertEqual(self.client.get("/comptes/premier-demarrage/").status_code, 302)


@override_settings(MEDIA_ROOT=TMP + "/files-restore", BACKUP_DIR=Path(TMP) / "backups-restore")
class BackupRestoreTests(TransactionTestCase):
    """Restauration réelle (pg_restore ou loaddata) : hors transaction de test."""

    def setUp(self):
        call_command("seed_sources", verbosity=0)
        self.admin = User.objects.create_user("admin", password="motdepasse-solide-1", role="admin")

    def catalogue(self, code):
        from apps.catalog.models import Catalogue

        return Catalogue.objects.get(code=code)

    def test_at19_backup_and_restore(self):
        cat = self.catalogue("codh-pmjt")
        upsert_record(cat, {"source_id": "B1", "original_title": "平家物語"})
        upsert_record(cat, {"source_id": "B2", "original_title": "太平記"})
        Path(settings.MEDIA_ROOT, "import").mkdir(parents=True, exist_ok=True)
        Path(settings.MEDIA_ROOT, "import", "fichier.csv").write_text("id,titre\n1,五輪書\n", encoding="utf-8")
        job = create_backup("full", user=self.admin)
        self.assertEqual(job.status, "done", job.message)
        with tarfile.open(job.path) as tar:
            names = tar.getnames()
        self.assertIn("manifest.json", names)
        self.assertTrue(any(n.startswith("database") for n in names))
        self.assertIn("files.tar.gz", names)
        ok, msg = verify_backup(job)
        self.assertTrue(ok, msg)
        n = Record.objects.count()
        Record.objects.filter(source_id="B1").delete()
        Path(settings.MEDIA_ROOT, "import", "fichier.csv").unlink()
        self.assertEqual(Record.objects.count(), n - 1)
        from django.db import connection

        connection.close()
        restore_backup(job.path, restore_files=True)
        self.assertEqual(Record.objects.count(), n)
        self.assertTrue(Record.objects.filter(source_id="B1", original_title="平家物語").exists())
        self.assertTrue(User.objects.filter(username="admin").exists())
        self.assertIn("五輪書", Path(settings.MEDIA_ROOT, "import", "fichier.csv").read_text(encoding="utf-8"))
