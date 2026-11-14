"""Évolution 1.3.0 — lot 0 : numéro de version et isolation de l'installation d'essai.

L'essai 1.3.0 doit pouvoir tourner à côté de l'installation principale (projet « japon-explorateur »,
port 8000) et de l'essai 1.2.0 (projet « japon-explorateur-essai », port 8001) sans jamais utiliser
leurs volumes. Ces tests lisent les fichiers de configuration livrés ; ils n'exécutent pas Docker.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
RESERVED = ("japon-explorateur", "japon-explorateur-essai")
EXPECTED_PROJECT = "japon-explorateur-essai-130"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8-sig")


class VersionTests(SimpleTestCase):
    def test_version_is_130_everywhere(self):
        self.assertEqual(read("VERSION").strip(), "1.3.0")
        self.assertEqual(settings.APP_VERSION, "1.3.0")
        self.assertIn("image: japon-explorateur:1.3.0", read("docker-compose.yml"))
        self.assertIn("## 1.3.0", read("CHANGELOG.md"))

    def test_no_stale_120_install_values(self):
        compose = read("docker-compose.yml")
        self.assertNotIn("japon-explorateur:1.2.0", compose)
        self.assertNotIn("WEB_PORT:-8001", compose)
        self.assertNotIn("COMPOSE_PROJECT_NAME:-japon-explorateur-essai}", compose)


class IsolationTests(SimpleTestCase):
    def test_compose_defaults_are_specific_to_130(self):
        compose = read("docker-compose.yml")
        self.assertIn("name: ${COMPOSE_PROJECT_NAME:-%s}" % EXPECTED_PROJECT, compose)
        self.assertIn('"127.0.0.1:${WEB_PORT:-8002}:8000"', compose)

    def test_every_app_container_receives_the_project_check(self):
        """web hérite de x-app ; worker et beat redéfinissent « environment » et doivent la porter aussi.

        1.3.0, lot 9 : le service Argos facultatif la porte aussi (quatrième occurrence)."""
        compose = read("docker-compose.yml")
        self.assertEqual(compose.count("COMPOSE_PROJECT_CHECK: ${COMPOSE_PROJECT_NAME:-%s}" % EXPECTED_PROJECT), 4)

    def test_env_example_values(self):
        env = read(".env.example")
        self.assertRegex(env, r"(?m)^COMPOSE_PROJECT_NAME=%s$" % re.escape(EXPECTED_PROJECT))
        self.assertRegex(env, r"(?m)^WEB_PORT=8002$")

    def test_reset_script_refuses_main_and_120_installations(self):
        script = read("reinitialiser-essai.ps1")
        self.assertIn("$NomEssai120 = 'japon-explorateur-essai'", script)
        self.assertIn("if ($Projet -eq $NomEssai120)", script)
        self.assertIn("if (\"$Port\" -eq '8001')", script)
        self.assertIn("if (\"$Port\" -eq '8000')", script)
        self.assertIn("$NomAttendu = '%s'" % EXPECTED_PROJECT, script)

    def test_reset_script_keeps_bom_and_crlf(self):
        raw = (ROOT / "reinitialiser-essai.ps1").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 requis par Windows PowerShell 5.1")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "fins de ligne CRLF attendues")


class EntrypointGuardTests(SimpleTestCase):
    """Exécute réellement docker/entrypoint.sh avec /bin/sh, hors Docker."""

    def run_entrypoint(self, project):
        env = dict(os.environ, COMPOSE_PROJECT_CHECK=project, DATABASE_URL="", RUN_MIGRATIONS="0",
                   PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
        return subprocess.run(["sh", str(ROOT / "docker" / "entrypoint.sh"), "echo", "demarrage-autorise"],
                              env=env, capture_output=True, text=True, timeout=60)

    def test_reserved_project_names_are_refused(self):
        for name in RESERVED:
            with self.subTest(name=name):
                result = self.run_entrypoint(name)
                self.assertEqual(result.returncode, 1)
                self.assertIn("ARRÊT", result.stderr)
                self.assertNotIn("demarrage-autorise", result.stdout)

    def test_130_project_name_is_accepted(self):
        result = self.run_entrypoint(EXPECTED_PROJECT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("demarrage-autorise", result.stdout)

    def test_close_but_different_names_are_accepted(self):
        """Seuls les deux noms exacts sont refusés (pas de faux refus sur un nom voisin)."""
        result = self.run_entrypoint("japon-explorateur-essai-130-bis")
        self.assertEqual(result.returncode, 0, result.stderr)
