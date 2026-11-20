"""2.0.1 — lot 0 : licence AGPL-3.0-or-later dans l'application (README, « À propos », pied de page, CONTRIBUTING)."""
from pathlib import Path

from django.conf import settings
from django.test import override_settings

from apps.core.views import ABOUT_COMPONENTS

from .helpers import AppTestCase

BASE = Path(settings.BASE_DIR)
DEPOT = "https://github.com/adupuisauteur/japon-explorateur"


class LicenceFilesTests(AppTestCase):
    def test_license_file_is_the_official_agpl_v3(self):
        text = (BASE / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", text)
        self.assertIn("Version 3, 19 November 2007", text)

    def test_readme_states_the_or_later_choice(self):
        readme = (BASE / "README.md").read_text(encoding="utf-8")
        self.assertIn("## 10. Licence", readme)
        self.assertIn("version 3 ou (à votre choix) toute version ultérieure", readme)
        self.assertIn("AGPL-3.0-or-later", readme)
        self.assertIn("CODE_SOURCE_URL", readme)

    def test_contributing_receives_contributions_under_the_same_licence(self):
        text = (BASE / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("AGPL-3.0-or-later", text)
        self.assertIn("sous la même licence", text)

    def test_env_example_documents_the_source_url(self):
        self.assertIn("# CODE_SOURCE_URL=" + DEPOT, (BASE / ".env.example").read_text(encoding="utf-8"))

    def test_license_is_not_excluded_from_the_archive_or_the_image(self):
        # L'archive est faite par « git archive » : un « export-ignore » en retirerait LICENSE.
        attributes = BASE / ".gitattributes"
        if attributes.exists():
            self.assertNotIn("LICENSE", attributes.read_text(encoding="utf-8"))
        self.assertNotIn("LICENSE", (BASE / ".dockerignore").read_text(encoding="utf-8"))


class AboutPageTests(AppTestCase):
    def test_about_shows_licence_source_link_and_pykakasi(self):
        page = self.client.get("/a-propos/").content.decode()
        self.assertIn("GNU AGPL v3.0 ou toute version ultérieure", page)
        self.assertIn("<code>AGPL-3.0-or-later</code>", page)
        self.assertIn(f'href="{DEPOT}"', page)
        self.assertIn("pykakasi", page)
        self.assertIn("sans aucune garantie", page)

    def test_pykakasi_listed_with_its_licence(self):
        roles = dict(ABOUT_COMPONENTS)
        self.assertIn("GPL v3 ou ultérieure", roles["pykakasi"])

    @override_settings(SOURCE_CODE_URL="https://exemple.invalid/ma-version-de-j-ed")
    def test_source_url_can_point_to_a_modified_version(self):
        page = self.client.get("/a-propos/").content.decode()
        self.assertIn('href="https://exemple.invalid/ma-version-de-j-ed"', page)
        self.assertNotIn(f'href="{DEPOT}"', page)


class FooterTests(AppTestCase):
    def test_footer_links_to_source_code_when_logged_in(self):
        page = self.client.get("/").content.decode()
        self.assertIn(f'<a href="{DEPOT}" target="_blank" rel="noopener">Code source</a>', page)

    def test_footer_links_to_source_code_before_login(self):
        # Article 13 de l'AGPL : toute personne qui utilise J-ed par le réseau doit pouvoir obtenir le code source,
        # y compris sur la page de connexion.
        self.client.logout()
        page = self.client.get("/comptes/connexion/").content.decode()
        self.assertIn("logiciel libre (AGPL v3)", page)
        self.assertIn(f'<a href="{DEPOT}" target="_blank" rel="noopener">Code source</a>', page)

    def test_reader_sees_the_source_link_too(self):
        self.client.force_login(self.reader)
        self.assertIn(f'href="{DEPOT}"', self.client.get("/a-propos/").content.decode())
