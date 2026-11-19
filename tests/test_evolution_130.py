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


class IsolationTests(SimpleTestCase):
    # 2.0.0 : les tests de numéro de version et des valeurs par défaut de l'essai 1.3.0 (nom de projet
    # « japon-explorateur-essai-130 », port 8002, image 1.3.0) sont remplacés par
    # tests/test_evolution_200.py (décision D3 : plus de nom de projet par défaut). Le script
    # reinitialiser-essai.ps1, propre à l'essai 1.3.0, est conservé tel quel : ses tests restent ici.

    def test_reset_script_refuses_main_and_120_installations(self):
        script = read("reinitialiser-essai.ps1")
        self.assertIn("$NomEssai120 = 'japon-explorateur-essai'", script)
        self.assertIn("if (($Projet -eq $NomEssai120) -and -not $EssaiMisAJour)", script)
        self.assertIn("if ((\"$Port\" -eq '8001') -and -not $EssaiMisAJour)", script)
        # l'exception exige l'autorisation explicite ET ne vaut jamais pour l'installation principale
        self.assertIn("$EssaiMisAJour = ($Projet -eq $NomEssai120) -and ($Autorisation -eq $Projet)", script)
        self.assertIn("if ($Projet -eq $NomPrincipal) {", script)
        self.assertIn("if (\"$Port\" -eq '8000')", script)
        self.assertIn("$NomAttendu = '%s'" % EXPECTED_PROJECT, script)

    def test_reset_script_keeps_bom_and_crlf(self):
        raw = (ROOT / "reinitialiser-essai.ps1").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 requis par Windows PowerShell 5.1")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "fins de ligne CRLF attendues")


class EntrypointGuardTests(SimpleTestCase):
    """Exécute réellement docker/entrypoint.sh avec /bin/sh, hors Docker."""

    def run_entrypoint(self, project, authorise=None):
        env = dict(os.environ, COMPOSE_PROJECT_CHECK=project, DATABASE_URL="", RUN_MIGRATIONS="0",
                   PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
        env.pop("AUTORISER_NOM_PROJET", None)
        if authorise is not None:
            env["AUTORISER_NOM_PROJET"] = authorise
        return subprocess.run(["sh", str(ROOT / "docker" / "entrypoint.sh"), "echo", "demarrage-autorise"],
                              env=env, capture_output=True, text=True, timeout=60)

    def test_reserved_project_names_are_refused(self):
        for name in RESERVED:
            with self.subTest(name=name):
                result = self.run_entrypoint(name)
                self.assertEqual(result.returncode, 1)
                self.assertIn("ARRÊT", result.stderr)
                self.assertNotIn("demarrage-autorise", result.stdout)

    def test_explicit_authorisation_allows_updating_an_existing_installation(self):
        for name in RESERVED:
            with self.subTest(name=name):
                result = self.run_entrypoint(name, authorise=name)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("demarrage-autorise", result.stdout)
                self.assertIn("autorisé par AUTORISER_NOM_PROJET", result.stderr)

    def test_authorisation_must_match_the_project_name_exactly(self):
        for wrong in ("japon-explorateur", "oui", "japon-explorateur-essai-130", " japon-explorateur-essai"):
            with self.subTest(wrong=wrong):
                result = self.run_entrypoint("japon-explorateur-essai", authorise=wrong)
                self.assertEqual(result.returncode, 1)
                self.assertIn("AUTORISER_NOM_PROJET=japon-explorateur-essai", result.stderr)

    def test_130_project_name_is_accepted(self):
        result = self.run_entrypoint(EXPECTED_PROJECT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("demarrage-autorise", result.stdout)

    def test_close_but_different_names_are_accepted(self):
        """Seuls les deux noms exacts sont refusés (pas de faux refus sur un nom voisin)."""
        result = self.run_entrypoint("japon-explorateur-essai-130-bis")
        self.assertEqual(result.returncode, 0, result.stderr)
