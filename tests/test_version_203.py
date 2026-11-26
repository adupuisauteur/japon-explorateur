"""2.0.3 (lot 4) — numéro de version et documents de la version (Linux)."""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Version203Tests(SimpleTestCase):
    def test_version_is_203(self):
        self.assertEqual(read("VERSION").strip(), "2.0.3")
        self.assertEqual(settings.APP_VERSION, "2.0.3")
        compose = read("docker-compose.yml")
        self.assertIn("image: japon-explorateur:2.0.3", compose)
        self.assertIn("image: japon-explorateur-argos:2.0.3", compose)

    def test_changelog_and_history_describe_203_first(self):
        changelog = read("CHANGELOG.md")
        self.assertLess(changelog.index("## 2.0.3"), changelog.index("## 2.0.2"), "la 2.0.3 en tête")
        history = read("docs/aide/historique-des-versions.md")
        self.assertLess(history.index("## Version 2.0.3"), history.index("## Version 2.0.2"))
        for text in (changelog, history):
            self.assertIn("Linux", text)
            self.assertIn("AVANT-DE-COMMENCER-LINUX.html", text)

    def test_readme_mentions_linux(self):
        readme = read("README.md")
        self.assertIn("**Version 2.0.3", readme)
        self.assertIn("AVANT-DE-COMMENCER-LINUX.html", readme)
        self.assertIn("bash j-ed.sh", readme)

    def test_linux_guide_has_every_part_the_prerequisites_point_to(self):
        """Chaque « Comment faire ? » des prérequis Linux (module) mène à une partie qui existe."""
        guide = read("AVANT-DE-COMMENCER-LINUX.html")
        module = (ROOT / "assistant" / "AssistantJed.psm1").read_text(encoding="utf-8-sig")
        linux = module[module.index("function Test-PrerequisLinuxJed"):module.index("function Test-PrerequisJed")]
        ancres = set(re.findall(r"New-ControleJed '[^']+' '[^']+' '[^']+' (?:'(?:[^']|'')*'|\"[^\"]*\") '([a-z-]+)'", linux))
        self.assertEqual(ancres, {"compte", "configuration", "processeur", "docker", "groupe-docker", "powershell",
                                  "disque"})
        for ancre in ancres | {"proxy", "docker-proxy", "telecharger", "assistant", "installer", "problemes"}:
            self.assertIn(f'id="{ancre}"', guide, ancre)
        for href in re.findall(r'href="#([^"]+)"', guide):
            self.assertIn(f'id="{href}"', guide, href)
        self.assertTrue((ROOT / "AVANT-DE-COMMENCER-LINUX.pdf").read_bytes().startswith(b"%PDF"))

    def test_linux_guide_commands(self):
        guide = read("AVANT-DE-COMMENCER-LINUX.html")
        for commande in ("sudo usermod -aG docker $USER", "docker run --rm hello-world",
                         "81a5a944702b116ea74c88b01ba5f1f46b1cd7c42c36d85e1bae90de1230b4d1",
                         "/etc/docker/daemon.json", "/etc/apt/apt.conf.d/95proxy", "bash ~/Téléchargements/"):
            self.assertIn(commande, guide)
        self.assertNotIn("<ol>\n<span", guide)   # jamais de cadre de commande dans une liste numérotée
        # adresse de proxy : seulement la forme à remplacer ou l'exemple fictif
        for adresse in re.findall(r"https?://[A-Za-z0-9.-]+:\d+", guide):
            self.assertRegex(adresse, r"NOM-DU-PROXY|proxy\.exemple\.fr")
