"""2.0.2 (lot 4) — numéro de version et documents de la version."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Version202Tests(SimpleTestCase):
    # 2.0.3 : le numéro de version courant est vérifié par tests/test_version_203.py ; ici, la 2.0.2 reste décrite.

    def test_changelog_and_history_describe_202(self):
        changelog = read("CHANGELOG.md")
        self.assertLess(changelog.index("## 2.0.2"), changelog.index("## 2.0.1"))
        history = read("docs/aide/historique-des-versions.md")
        self.assertLess(history.index("## Version 2.0.2"), history.index("## Version 2.0.1"))
        for text in (changelog, history):
            self.assertIn("assistant", text.lower())
        self.assertIn("2.0.3", changelog, "changement d'ordre des versions écrit")

    def test_readme_and_beginner_guide(self):
        readme = read("README.md")
        self.assertIn("**2.0.2** du 24 novembre 2026", readme)
        self.assertIn("J-ed.cmd", readme)
        guide = read("AVANT-DE-COMMENCER.html")
        # chaque bouton « Comment faire ? » de l'assistant mène à une partie qui existe
        for ancre in ("configuration", "virtualisation", "wsl", "docker", "docker-demarre", "disque"):
            self.assertIn(f'id="{ancre}"', guide)
        self.assertTrue((ROOT / "AVANT-DE-COMMENCER.pdf").read_bytes().startswith(b"%PDF"))
        self.assertIn("wsl --install", guide)
