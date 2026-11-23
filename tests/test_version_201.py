"""2.0.1 (lot 3) — numéro de version et documents de la version."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Version201Tests(SimpleTestCase):
    # 2.0.2 : le numéro de version courant est vérifié par tests/test_version_202.py ; ici, la 2.0.1 reste décrite.

    def test_changelog_and_history_describe_201(self):
        changelog = read("CHANGELOG.md")
        self.assertLess(changelog.index("## 2.0.1"), changelog.index("## 2.0.0"))
        history = read("docs/aide/historique-des-versions.md")
        self.assertLess(history.index("## Version 2.0.1"), history.index("## Version 2.0.0"))
        for text in (changelog, history):
            self.assertIn("AGPL", text)
            self.assertIn("retour", text)

    def test_readme_mentions_201(self):
        self.assertIn("**2.0.1** du 23 novembre 2026", read("README.md"))
