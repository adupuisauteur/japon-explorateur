"""2.0.2 (lot 4) — numéro de version et documents de la version."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Version202Tests(SimpleTestCase):
    def test_version_is_202(self):
        self.assertEqual(read("VERSION").strip(), "2.0.2")
        self.assertEqual(settings.APP_VERSION, "2.0.2")
        compose = read("docker-compose.yml")
        self.assertIn("image: japon-explorateur:2.0.2", compose)
        self.assertIn("image: japon-explorateur-argos:2.0.2", compose)

    def test_changelog_and_history_describe_202_first(self):
        changelog = read("CHANGELOG.md")
        self.assertLess(changelog.index("## 2.0.2"), changelog.index("## 2.0.1"), "la 2.0.2 en tête")
        history = read("docs/aide/historique-des-versions.md")
        self.assertLess(history.index("## Version 2.0.2"), history.index("## Version 2.0.1"))
        for text in (changelog, history):
            self.assertIn("assistant", text.lower())
        self.assertIn("2.0.3", changelog, "changement d'ordre des versions écrit")

    def test_readme_and_beginner_guide(self):
        readme = read("README.md")
        self.assertIn("**Version 2.0.2", readme)
        self.assertIn("J-ed.cmd", readme)
        guide = read("AVANT-DE-COMMENCER.html")
        # chaque bouton « Comment faire ? » de l'assistant mène à une partie qui existe
        for ancre in ("configuration", "virtualisation", "wsl", "docker", "docker-demarre", "disque"):
            self.assertIn(f'id="{ancre}"', guide)
        self.assertTrue((ROOT / "AVANT-DE-COMMENCER.pdf").read_bytes().startswith(b"%PDF"))
        self.assertIn("wsl --install", guide)
