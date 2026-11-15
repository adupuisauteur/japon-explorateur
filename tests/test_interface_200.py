"""2.0.0 — lot 1 : nom J-ed, page « À propos », menus, droits sur le journal, page hors ligne, bas de page des
exports (demande U2). Données fictives uniquement."""
import html
import io
import re
import zipfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.db.utils import OperationalError
from django.test import Client
from docx import Document

from apps.catalog.services import upsert_record
from apps.core.models import AppSettings
from apps.exports.models import ExportJob
from apps.incidents.models import Incident
from apps.incidents.services import record_incident
from apps.translation import projects as P
from apps.translation.models import TranslationProject

from .helpers import AppTestCase

ROOT = Path(settings.BASE_DIR)
OLD_NAME = "Explorateur documentaire"


def main_menu(html):
    """Contenu de la liste principale du menu (hors menu utilisateur et pied de page)."""
    match = re.search(r'<ul class="navbar-nav me-auto">(.*?)</ul>', html, re.S)
    return match.group(1) if match else ""


def footer(html):
    match = re.search(r'<footer class="app-footer">(.*?)</footer>', html, re.S)
    return match.group(1) if match else ""


class NameTests(AppTestCase):
    def test_pages_show_only_j_ed(self):
        page = self.client.get("/").content.decode()
        self.assertIn("<title>Accueil — J-ed</title>", page)
        self.assertIn('<span class="brand-name">J-ed</span>', page)
        self.assertNotIn(OLD_NAME, page)
        self.client.logout()
        login = self.client.get("/comptes/connexion/").content.decode()
        self.assertIn("J-ed", login)
        self.assertNotIn(OLD_NAME, login)

    def test_installable_application_is_named_j_ed(self):
        data = self.client.get("/manifest.webmanifest").json()
        self.assertEqual((data["name"], data["short_name"]), ("J-ed", "J-ed"))

    def test_user_agent_and_diagnostic_headers(self):
        self.assertTrue(settings.CONNECTOR_USER_AGENT.startswith(f"J-ed/{settings.APP_VERSION} "))
        from apps.incidents import report

        incident = record_incident(module="recherche", category="erreur_technique", severity="error", title="Essai")
        self.assertIn("Rapport de diagnostic — J-ed", report.build_markdown([incident]))

    def test_new_installation_default_and_existing_value_kept(self):
        self.assertEqual(AppSettings._meta.get_field("instance_name").default, "J-ed")
        settings_obj = AppSettings.get()
        settings_obj.instance_name = "Japon — Explorateur documentaire"
        settings_obj.save()
        self.assertEqual(AppSettings.get().instance_name, "Japon — Explorateur documentaire")

    def test_backup_manifest_keeps_its_technical_value(self):
        source = (ROOT / "apps/backups/services.py").read_text(encoding="utf-8")
        self.assertIn('"application": "Japon — Explorateur documentaire"', source)

    def test_technical_names_unchanged(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("name: ${COMPOSE_PROJECT_NAME:?", compose)
        self.assertIn("japon-explorateur", compose)


class AboutTests(AppTestCase):
    def test_every_account_sees_version_and_origin(self):
        for user in (self.admin, self.researcher, self.reader):
            self.client.force_login(user)
            page = self.client.get("/a-propos/")
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, f"<dd class=\"col-sm-8\">{settings.APP_VERSION}</dd>", html=False)
            self.assertContains(page, "Origine du projet")
            self.assertContains(page, "Japon — Explorateur documentaire")
        # Demande U3 : lien « À propos » en bas de page, plus dans le menu utilisateur.
        page = self.client.get("/").content.decode()
        self.assertIn('<a href="/a-propos/">À propos</a>', footer(page))
        dropdown = page.split('<ul class="dropdown-menu dropdown-menu-end">')[1].split("</ul>")[0]
        self.assertNotIn("/a-propos/", dropdown)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.get("/a-propos/").status_code, 302)


class MenuTests(AppTestCase):
    def setUp(self):
        super().setUp()
        record_incident(module="recherche", category="erreur_technique", severity="error", title="Essai")

    def test_admin_entries_left_the_main_menu(self):
        page = self.client.get("/").content.decode()
        menu = main_menu(page)
        self.assertIn("Rechercher", menu)
        self.assertNotIn("Administration", menu)
        self.assertNotIn("Dysfonctionnements", menu)

    def test_admin_finds_them_in_footer_and_user_menu(self):
        page = self.client.get("/").content.decode()
        self.assertIn('href="/administration/">Administration</a>', footer(page))
        self.assertIn('href="/journal/">Dysfonctionnements</a>', footer(page))
        dropdown = page.split('<ul class="dropdown-menu dropdown-menu-end">')[1].split("</ul>")[0]
        self.assertIn("Administration", dropdown)
        self.assertIn("Dysfonctionnements", dropdown)
        self.assertIn("nav-badge", page)  # pastille sur le bouton du menu utilisateur

    def test_researcher_and_reader_see_neither(self):
        for user in (self.researcher, self.reader):
            self.client.force_login(user)
            response = self.client.get("/")
            page = response.content.decode()
            self.assertNotIn("Dysfonctionnements", page)
            self.assertNotIn('href="/administration/"', page)
            self.assertNotIn("nav-badge", page)
            self.assertNotIn("incidents_new_count", response.context)
            self.assertIn("Signaler un problème", footer(page))
            self.assertIn(f"v{settings.APP_VERSION}", footer(page))


class IncidentRightsTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.incident = record_incident(module="recherche", category="erreur_technique", severity="error",
                                        title="Essai")

    def test_journal_is_reserved_to_admin(self):
        uid = self.incident.uid
        urls = ["/journal/", f"/journal/{uid}/", "/journal/analyse/", "/journal/export/", f"/journal/{uid}/export/",
                f"/journal/{uid}/capture/"]
        for user in (self.researcher, self.reader):
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403, (user.username, url))
        self.client.force_login(self.admin)
        for url in urls[:5]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_researcher_can_still_report_and_returns_to_his_page(self):
        self.client.force_login(self.researcher)
        self.assertEqual(self.client.get("/journal/signaler/?from=/recherche/").status_code, 200)
        response = self.client.post("/journal/signaler/", {
            "module": "recherche", "severity": "warning", "description": "Lecture absente (essai fictif)",
            "from_path": "/recherche/"}, follow=True)
        self.assertRedirects(response, "/recherche/")
        incident = Incident.objects.get(is_manual=True)
        page = html.unescape(response.content.decode())
        self.assertIn(f"Signalement enregistré sous l'identifiant {incident.uid}", page)
        self.assertIn("L'administrateur en est informé", page)

    def test_report_never_returns_outside_or_to_the_journal(self):
        self.client.force_login(self.researcher)
        for target in ("https://example.org/", "//example.org/", "/journal/", "javascript:alert(1)"):
            response = self.client.post("/journal/signaler/", {
                "module": "recherche", "severity": "info", "description": f"Essai {target}", "from_path": target})
            self.assertEqual(response["Location"], "/", target)

    def test_admin_report_goes_to_the_incident(self):
        response = self.client.post("/journal/signaler/", {"module": "recherche", "severity": "info",
                                                           "description": "Essai administrateur"})
        self.assertRedirects(response, Incident.objects.get(is_manual=True).get_absolute_url())

    def test_source_page_hides_the_journal_from_researcher(self):
        self.client.force_login(self.researcher)
        page = self.client.get(self.catalogue("ndl").get_absolute_url())
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Dysfonctionnements de cette source")
        self.assertNotContains(page, 'href="/journal/?')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.catalogue("ndl").get_absolute_url()), "Dysfonctionnements de cette source")


class OfflineAndHealthTests(AppTestCase):
    def test_offline_page_is_standalone(self):
        self.client.logout()
        response = self.client.get("/hors-ligne/")
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        self.assertIn("J-ed ne répond pas", page)
        self.assertIn("Docker Desktop", page)
        self.assertNotIn("navbar", page)
        self.assertNotIn(settings.APP_VERSION, page)
        self.assertNotIn("hors ligne</h1>", page)  # ne parle plus d'Internet
        self.assertNotIn("<script", page)
        self.assertIn("Content-Security-Policy", response.headers)

    def test_health_answers_without_account(self):
        response = Client().get("/sante/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok\n")
        self.assertIn("no-store", response["Cache-Control"])

    def test_health_reports_an_unreachable_database(self):
        with mock.patch("django.db.backends.base.base.BaseDatabaseWrapper.cursor",
                        side_effect=OperationalError("fictif")):
            response = Client().get("/sante/")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"OperationalError", response.content)

    def test_docker_healthcheck_uses_the_dedicated_address(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn('"http://localhost:8000/sante/"', compose)
        self.assertNotIn('"http://localhost:8000/hors-ligne/"', compose)

    def test_first_run_does_not_redirect_health(self):
        from apps.core.middleware import _EXEMPT_PREFIXES

        self.assertTrue("/sante/".startswith(_EXEMPT_PREFIXES))


class ExportFooterTests(AppTestCase):
    """Demande U2 : date, heure, J-ed et sa version, identifiant de l'utilisateur en bas de chaque page."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)
        cat = self.catalogue("codh-pmjt")
        self.record, _ = upsert_record(cat, {"source_id": "U2-1", "original_title": "五輪書", "reading": "ごりんのしょ"})

    def export(self, fmt, **extra):
        params = {"scope": "selection", "records": self.record.record_id, "preset": "bibliography", "format": fmt,
                  "title": "Essai U2", "author": "", "footer_text": "Document de travail", "pagination": "on",
                  "toc": "on", "column_profile": "generic", "csv_separator": "semicolon", **extra}
        self.client.post("/exports/preparer/", params)
        job = ExportJob.objects.latest("pk")
        self.assertEqual(job.status, "done", job.error)
        return job, Path(settings.MEDIA_ROOT) / job.files.get(role="main").path

    def expected_line(self, job):
        return f"Produit le {job.metadata['generated_at_display'].replace(' ', ' à ')} · J-ed {settings.APP_VERSION}"

    def test_docx_footer(self):
        job, path = self.export("docx")
        footer_text = "\n".join(p.text for p in Document(path).sections[1].footer.paragraphs)
        self.assertIn("Document de travail", footer_text)
        self.assertIn(self.expected_line(job) + " · par chercheur", footer_text)
        self.assertIn(job.export_uid, footer_text)
        self.assertIn("page", footer_text)
        self.assertEqual(job.metadata["produced_by"], "chercheur")

    def test_pdf_footer_on_every_page(self):
        from pypdf import PdfReader

        job, path = self.export("pdf")
        pages = PdfReader(path).pages
        self.assertGreater(len(pages), 1)
        for page in pages[1:]:
            text = page.extract_text()
            self.assertIn("par chercheur", text)
            self.assertIn(f"J-ed {settings.APP_VERSION}", text)
            self.assertIn(job.export_uid, text)

    def test_html_footer(self):
        job, path = self.export("html")
        with zipfile.ZipFile(path) as zf:
            index = next(n for n in zf.namelist() if n.endswith("/index.html"))
            page = zf.read(index).decode("utf-8")
        self.assertIn(self.expected_line(job) + " · par chercheur — export " + job.export_uid, page)

    def test_txt_ends_with_the_line(self):
        job, path = self.export("txt")
        self.assertIn(self.expected_line(job) + " · par chercheur", path.read_text(encoding="utf-8"))

    def test_user_can_hide_his_identifier(self):
        job, path = self.export("docx", hide_user="on")
        self.assertTrue(job.options["hide_user"])
        self.assertEqual(job.metadata["produced_by"], "")
        d = Document(path)
        footer_text = "\n".join(p.text for p in d.sections[1].footer.paragraphs)
        self.assertIn(self.expected_line(job), footer_text)
        self.assertNotIn("chercheur", footer_text + "\n".join(p.text for p in d.paragraphs))

    def test_regeneration_keeps_the_choice(self):
        from apps.exports.services import clone_for_regeneration

        job, _ = self.export("txt", hide_user="on")
        self.assertTrue(clone_for_regeneration(job).options.get("hide_user"))

    def test_preparation_page_offers_the_checkbox(self):
        page = self.client.get(f"/exports/preparer/?scope=selection&records={self.record.record_id}")
        self.assertContains(page, "Ne pas indiquer mon identifiant en bas de page")


class TranslationExportFooterTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)
        self.project = TranslationProject.objects.create(owner=self.researcher, title="Projet fictif U2")
        document = P.create_document(self.project, title="Document fictif", text="一つ目の文。")
        segment = document.segments.get()
        P.validate_version(P.add_human_version(segment, self.researcher, "Première phrase."), self.researcher)

    def export(self, fmt, **params):
        response = self.client.get(f"/traduction/projets/{self.project.pk}/exporter/", {"format": fmt, **params})
        self.assertEqual(response.status_code, 200)
        return response.content

    def test_bilingual_word_has_a_footer_on_every_page(self):
        d = Document(io.BytesIO(self.export("bilingual_docx")))
        footer_p = d.sections[0].footer.paragraphs[0]
        self.assertIn(f"J-ed {settings.APP_VERSION} · par chercheur", footer_p.text)
        self.assertIn("Produit le ", footer_p.text)
        self.assertIn("PAGE", d.sections[0].footer._element.xml)
        header = "\n".join(p.text for p in d.paragraphs)
        self.assertIn("Exporté par : chercheur", header)

    def test_text_and_markdown_end_with_the_line(self):
        for fmt in ("bilingual_txt", "translation_txt", "bilingual_md", "translation_md"):
            text = self.export(fmt).decode("utf-8").rstrip()
            self.assertTrue(text.endswith("par chercheur") or text.endswith("par chercheur*"), (fmt, text[-80:]))

    def test_identifier_can_be_hidden(self):
        d = Document(io.BytesIO(self.export("bilingual_docx", sans_identifiant="1")))
        self.assertNotIn("chercheur", d.sections[0].footer.paragraphs[0].text)
        self.assertNotIn("Exporté par", "\n".join(p.text for p in d.paragraphs))
        self.assertNotIn("chercheur", self.export("bilingual_txt", sans_identifiant="1").decode("utf-8"))
        page = self.client.get(f"/traduction/projets/{self.project.pk}/exporter/")
        self.assertContains(page, "Ne pas indiquer mon identifiant")
