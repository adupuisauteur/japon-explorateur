"""2.0.0 — lot 6 : aide intégrée (docs/aide/*.md), « Quoi de neuf », historique des versions (U4)."""
import tempfile
from pathlib import Path
from unittest import mock

from django.urls import get_resolver

from apps.catalog.models import Catalogue, Record
from apps.help import pages as P

from .helpers import AppTestCase

#: Écrans principaux : chacun doit avoir sa page d'aide (cahier des charges § 9, « Contrôle »).
MAIN_SCREENS = [
    "core:home", "core:about", "accounts:profile", "searching:form", "searching:session", "searching:history",
    "searching:saved_list", "catalog:record_detail", "connectors:list", "connectors:detail", "library:index",
    "library:collections", "library:collection_detail", "exports:prepare", "exports:list", "exports:detail",
    "notifications:list", "notifications:preferences", "incidents:report",
    "translation:home", "translation:engines", "translation:local_engines", "translation:job_list",
    "translation:job_detail", "translation:records_prepare", "translation:record_translations", "translation:done",
    "translation:project_list", "translation:project_detail", "translation:document_workbench",
    "translation:segment_detail", "translation:glossary_list", "translation:glossary_detail", "translation:memory",
    "translation:usage", "translation:evaluation", "translation:summary_list", "translation:summary_detail",
    "translation:exports", "ai:preferences", "ai:providers", "ai:tasks",
    "core:admin_hub", "core:state", "core:settings", "core:audit_log", "accounts:users", "backups:list",
    "incidents:list", "incidents:detail", "updates:dashboard", "library:corrections", "catalog:trash",
]


def url_names():
    names = set()

    def walk(resolver, ns=""):
        for p in resolver.url_patterns:
            if hasattr(p, "url_patterns"):
                walk(p, ((ns + ":") if ns else "") + p.namespace if p.namespace else ns)
            else:
                names.add(f"{ns}:{p.name}" if ns else p.name)

    walk(get_resolver())
    return names


class HelpContentTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.reg = P.registry().load()

    def test_every_main_screen_has_a_help_page(self):
        missing = [s for s in MAIN_SCREENS if s not in self.reg.by_screen]
        self.assertEqual(missing, [], "écrans sans page d'aide")

    def test_no_broken_link_anchor_or_unknown_screen(self):
        broken = [(p.slug, href) for p in self.reg.pages.values() for href, ok in p.links if not ok]
        self.assertEqual(broken, [])
        anchors = {p.slug: {i for i, _ in p.headings} for p in self.reg.pages.values()}
        bad_anchors = [(p.slug, href) for p in self.reg.pages.values() for href, _ in p.links
                       if href.startswith("aide:") and "#" in href
                       and href[5:].split("#")[1] not in anchors[href[5:].split("#")[0]]]
        self.assertEqual(bad_anchors, [])
        known = url_names()
        self.assertEqual([(p.slug, s) for p in self.reg.pages.values() for s in p.screens if s not in known], [])

    def test_every_page_has_title_section_and_summary(self):
        for page in self.reg.pages.values():
            self.assertIn(page.section, P.SECTIONS, page.slug)
            self.assertTrue(page.summary, page.slug)
            self.assertNotIn("<", P.plain(page.html).replace("&lt;", ""), page.slug)  # aucun HTML brut résiduel

    def test_raw_html_is_never_interpreted(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "essai.md").write_text(
                "---\ntitre: Essai\nresume: x\n---\n<script>alert(1)</script>\n\n<b>gras</b> [x](javascript:alert(1)) "
                "[y](https://exemple.org) ![i](https://exemple.org/i.png)\n", encoding="utf-8")
            with mock.patch.object(P, "_registry", P.Registry(Path(tmp))):
                html = P.registry().load().pages["essai"].html
        self.assertNotIn("<script", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<b>", html)
        self.assertIn('href="#lien-introuvable"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertNotIn('src="https://exemple.org/i.png"', html)


class HelpScreenTests(AppTestCase):
    def test_pages_by_role(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/aide/rechercher/").status_code, 200)
        self.assertEqual(self.client.get("/aide/resumes-ia/").status_code, 404)  # chercheurs seulement
        self.assertEqual(self.client.get("/aide/sauvegardes/").status_code, 404)
        index = self.client.get("/aide/").content.decode()
        self.assertIn("Rechercher dans les catalogues", index)
        self.assertNotIn("Sauvegardes et restauration", index)
        self.client.force_login(self.researcher)
        self.assertEqual(self.client.get("/aide/resumes-ia/").status_code, 200)
        self.assertEqual(self.client.get("/aide/sauvegardes/").status_code, 404)
        self.client.force_login(self.admin)
        for slug in P.registry().load().pages:
            self.assertEqual(self.client.get(f"/aide/{slug}/").status_code, 200, slug)
        self.client.logout()
        self.assertEqual(self.client.get("/aide/rechercher/").status_code, 302)

    def test_question_mark_opens_the_page_of_the_screen(self):
        cat = Catalogue.objects.get(code="codh-pmjt")
        record = Record.objects.create(catalogue=cat, source_id="aide-1", original_title="架空")
        self.client.force_login(self.researcher)
        page = self.client.get(record.get_absolute_url()).content.decode()
        self.assertIn('href="/aide/lire-une-notice/" title="Aide sur cet écran"', page)
        page = self.client.get("/traduction/taches/").content.decode()
        self.assertIn('href="/aide/taches-et-file-de-nuit/" title="Aide sur cet écran"', page)
        self.assertIn('href="/aide/"><i class="bi bi-question-circle"></i> Aide</a>', page)  # menu à son nom
        self.assertIn('>Quoi de neuf</a>', page)  # bas de page

    def test_search(self):
        self.client.force_login(self.researcher)
        page = self.client.get("/aide/recherche/", {"q": "file de nuit"}).content.decode()
        self.assertIn("Tâches, file de nuit et programmation", page)
        page = self.client.get("/aide/recherche/", {"q": "manifeste"}).content.decode()
        self.assertIn("Comprendre les trois statuts", page)
        page = self.client.get("/aide/recherche/", {"q": "RESTAURER"}).content.decode()
        self.assertNotIn("Sauvegardes et restauration", page)  # page de l'administrateur
        self.assertIn("Aucune page", self.client.get("/aide/recherche/", {"q": "zzzqqq"}).content.decode())
        hits = P.search(self.admin, "sorobun")  # sans macron ni accent
        self.assertIn("japonais-ancien", [p.slug for p, _ in hits])

    def test_whats_new_and_version_history(self):
        self.client.force_login(self.reader)
        page = self.client.get("/aide/quoi-de-neuf/").content.decode()
        self.assertIn("Version 2.0.0", page)
        self.assertNotIn("Version 1.3.0", page)  # seulement la dernière version
        self.assertEqual(self.client.get("/aide/historique-des-versions/").status_code, 403)
        self.client.force_login(self.admin)
        page = self.client.get("/aide/historique-des-versions/").content.decode()
        self.assertIn("Version 1.3.0", page)
        self.assertIn("Version 1.2.0", page)
        self.assertNotIn("orrectif", page)  # évolutions seulement, pas les corrections (U4)
        self.assertIn('href="/aide/historique-des-versions/"', self.client.get("/administration/").content.decode())

    def test_registry_reloads_when_a_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "essai.md")
            path.write_text("---\ntitre: Avant\nresume: x\n---\nTexte.\n", encoding="utf-8")
            with mock.patch.object(P, "_registry", P.Registry(Path(tmp)).load()):
                self.assertEqual(P.fresh_registry().pages["essai"].title, "Avant")
                import os

                path.write_text("---\ntitre: Après\nresume: x\n---\nTexte.\n", encoding="utf-8")
                os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))
                self.assertEqual(P.fresh_registry().pages["essai"].title, "Après")


class LogoTests(AppTestCase):
    """Logo de J-ed (16 novembre 2026) : barre de menu (logo seul), onglet, application installée, connexion,
    « À propos », en-têtes des exports PDF, Word et site HTML."""

    def export(self, fmt):
        from django.conf import settings

        from apps.exports.models import ExportJob

        cat = Catalogue.objects.get(code="codh-pmjt")
        record = Record.objects.create(catalogue=cat, source_id=f"logo-{fmt}", original_title="架空の書")
        self.client.force_login(self.researcher)
        self.client.post("/exports/preparer/", {"scope": "selection", "records": record.record_id,
                                                "preset": "bibliography", "format": fmt, "title": "Essai du logo",
                                                "column_profile": "bibliography", "csv_separator": "semicolon"})
        job = ExportJob.objects.latest("pk")
        self.assertEqual(job.status, "done", job.error)
        return Path(settings.MEDIA_ROOT) / job.files.get(role="main").path

    def test_pdf_has_the_logo_on_title_page_and_headers(self):
        from pypdf import PdfReader

        reader = PdfReader(str(self.export("pdf")))
        self.assertGreaterEqual(len(reader.pages[0].images), 1)
        self.assertGreaterEqual(len(reader.pages[-1].images), 1)

    def test_word_has_the_logo(self):
        import zipfile

        with zipfile.ZipFile(self.export("docx")) as z:
            media = [n for n in z.namelist() if n.startswith("word/media/")]
            header = next(n for n in z.namelist() if n.startswith("word/header"))
            self.assertTrue(media)
            self.assertIn("<pic:pic", z.read(header).decode())

    def test_html_site_has_the_logo(self):
        import zipfile

        with zipfile.ZipFile(self.export("html")) as z:
            names = z.namelist()
            self.assertTrue(any(n.endswith("assets/logo-j-ed.png") for n in names))
            index = z.read(next(n for n in names if n.endswith("/index.html"))).decode()
        self.assertIn('class="logo"', index)

    def test_icons_and_pages(self):
        from django.contrib.staticfiles import finders
        from PIL import Image

        for name, size in (("icons/icon-192.png", 192), ("icons/icon-512.png", 512),
                           ("icons/icon-maskable-512.png", 512), ("icons/favicon-32.png", 32)):
            with Image.open(finders.find(name)) as im:
                self.assertEqual(im.size, (size, size), name)
        self.client.logout()
        self.assertIn("img/logo-j-ed.png", self.client.get("/comptes/connexion/").content.decode())
        self.client.force_login(self.reader)
        self.assertIn("img/logo-j-ed-grand.png", self.client.get("/a-propos/").content.decode())
        self.assertIn("icons/favicon-32.png", self.client.get("/").content.decode())
