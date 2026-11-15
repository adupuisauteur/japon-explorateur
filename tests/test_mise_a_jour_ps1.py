"""2.0.0, lot 0 — mettre-a-jour.ps1 exécuté par PowerShell avec un faux « docker » (tests/fixtures/mise_a_jour).

Le script réel est lancé de bout en bout ; seules les commandes Docker sont simulées (journalisées pour vérifier
leur ordre). Ignoré si PowerShell (pwsh) n'est pas installé. Le test réel sous Windows reste à faire sur le poste
de l'utilisateur (protocole de vérification).
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
SCRIPT = ROOT / "mettre-a-jour.ps1"
FAKE_DOCKER_DIR = ROOT / "tests" / "fixtures" / "mise_a_jour"
PWSH = shutil.which("pwsh") or ("/opt/pwsh/pwsh" if Path("/opt/pwsh/pwsh").exists() else None)


class ScriptFileTests(SimpleTestCase):
    def test_bom_and_crlf_for_windows_powershell_51(self):
        raw = SCRIPT.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 requis par Windows PowerShell 5.1")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "fins de ligne CRLF attendues")

    def test_no_installation_specific_name_or_path(self):
        text = SCRIPT.read_text(encoding="utf-8-sig")
        for specific in ("JaponEssai", "essai-130", "8001", "8002"):
            self.assertNotIn(specific, text)

    def test_never_removes_volumes(self):
        text = SCRIPT.read_text(encoding="utf-8-sig")
        self.assertIn("@('compose', 'down')", text)
        self.assertNotIn("'down', '-v'", text)
        self.assertNotIn("--volumes", text)


class UpdateScriptRunTests(SimpleTestCase):
    def setUp(self):
        if PWSH is None:
            self.skipTest("PowerShell (pwsh) absent")
        self.tmp = Path(tempfile.mkdtemp(prefix="maj-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log = self.tmp / "docker.log"
        self.current = self.tmp / "installation-1.3.0"
        self.current.mkdir()
        (self.current / "docker-compose.yml").write_text("name: x\n")
        (self.current / "VERSION").write_text("1.3.0\n")
        self.write_env("COMPOSE_PROJECT_NAME=jed-essai\nWEB_PORT=8000\nPOSTGRES_PASSWORD=fictif\n")
        self.archive = self.make_archive("2.0.0")

    def write_env(self, text):
        (self.current / ".env").write_text(text, encoding="utf-8")

    def make_archive(self, version, name=None, corrupt_hash=False):
        archive = self.tmp / (name or f"jed-{version}.zip")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("VERSION", f"{version}\n")
            z.writestr("docker-compose.yml", "name: ${COMPOSE_PROJECT_NAME}\n")
            z.writestr("README.md", "fictif\n")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if corrupt_hash:
            digest = "0" * 64
        Path(f"{archive}.sha256").write_text(f"{digest}  {archive.name}\n")
        return archive

    def run_script(self, *extra, **fake):
        env = dict(os.environ, FAKE_DOCKER_LOG=str(self.log),
                   PATH=str(FAKE_DOCKER_DIR) + os.pathsep + os.environ.get("PATH", ""))
        env.update({f"FAKE_{k.upper()}": str(v) for k, v in fake.items()})
        args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), "-Archive", str(self.archive),
                "-Actuel", str(self.current), "-DossierSauvegardes", str(self.tmp / "sauvegardes"), "-Oui", *extra]
        result = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
        self.calls = self.log.read_text().splitlines() if self.log.exists() else []
        return result

    def destination(self):
        return self.tmp / self.archive.stem

    def assertStopped(self, result, message):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ARRÊT", result.stdout)
        self.assertIn(message, result.stdout)
        self.assertFalse(any(c.endswith("| compose down") for c in self.calls), "l'ancienne version reste en service")

    def test_full_update(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Mise à jour terminée : J-ed 2.0.0", result.stdout)
        dest = self.destination()
        self.assertEqual((dest / "VERSION").read_text().strip(), "2.0.0")
        env = (dest / ".env").read_text(encoding="utf-8-sig")
        self.assertIn("COMPOSE_PROJECT_NAME=jed-essai", env)
        self.assertIn(f"DOSSIER_SAUVEGARDES={self.tmp / 'sauvegardes'}", env)
        self.assertEqual((self.tmp / "sauvegardes" / "sauvegarde-20261114-220000-full.tar").read_text(), "contenu-fictif")
        # ordre : sauvegarde (ancien dossier) → arrêt de l'ancien → démarrage du nouveau → contrôle final
        order = [c for c in self.calls if "manage.py backup" in c or c.endswith("compose down") or "up -d" in c
                 or "etat_installation" in c]
        self.assertTrue(order[0].startswith(str(self.current)) and "backup" in order[0])
        self.assertTrue(order[1].startswith(str(self.current)) and order[1].endswith("compose down"))
        self.assertTrue(order[2].startswith(str(dest)) and "up -d --build" in order[2])
        self.assertIn("etat_installation", order[3])
        self.assertEqual((self.current / "VERSION").read_text().strip(), "1.3.0", "ancien dossier inchangé")

    def test_argos_is_restarted_when_it_was_running(self):
        result = self.run_script(argos=1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(any("compose --profile hors-ligne up -d --build" in c for c in self.calls))
        env = (self.destination() / ".env").read_text(encoding="utf-8-sig")
        self.assertIn("COMPOSE_PROFILES=hors-ligne", env, "Argos redémarrera aussi avec un simple up -d")

    def test_profiles_line_is_not_added_without_argos(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("COMPOSE_PROFILES", (self.destination() / ".env").read_text(encoding="utf-8-sig"))

    def test_wrong_hash_stops_before_anything(self):
        self.archive = self.make_archive("2.0.0", corrupt_hash=True)
        result = self.run_script()
        self.assertStopped(result, "empreinte de l'archive différente")
        self.assertFalse(self.destination().exists())
        self.assertFalse(any("backup" in c for c in self.calls))

    def test_older_archive_is_refused(self):
        self.archive = self.make_archive("1.2.0")
        self.assertStopped(self.run_script(), "trop ancienne")

    def test_downgrade_is_refused(self):
        (self.current / "VERSION").write_text("2.1.0\n")
        self.assertStopped(self.run_script(), "plus ancienne que la version installée")

    def test_failed_backup_of_a_130_installation_is_detected(self):
        """La 1.3.0 affiche « Échec » avec un code de sortie 0 : le script lit aussi le texte."""
        result = self.run_script(backup="echec-130")
        self.assertStopped(result, "la sauvegarde a échoué")
        self.assertFalse(self.destination().exists())

    def test_damaged_accents_from_windows_powershell_are_understood(self):
        """15 novembre 2026, poste de l'utilisateur : « Terminée » lu « Termin├®e » ; la sauvegarde avait réussi."""
        result = self.run_script(backup="accents-abimes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.tmp / "sauvegardes" / "sauvegarde-20261114-220000-full.tar").exists())

    def test_a_failure_with_damaged_accents_still_stops(self):
        self.assertStopped(self.run_script(backup="echec-accents-abimes"), "la sauvegarde a échoué")

    def test_docker_output_is_read_as_utf8_before_any_call(self):
        text = SCRIPT.read_text(encoding="utf-8-sig")
        self.assertLess(text.index("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8"),
                        text.index("Docker-Dans $Actuel @('info')"))

    def test_protected_project_needs_the_existing_authorisation(self):
        self.write_env("COMPOSE_PROJECT_NAME=japon-explorateur-essai\nWEB_PORT=8000\n")
        self.assertStopped(self.run_script(), "AUTORISER_NOM_PROJET=japon-explorateur-essai")
        self.write_env("COMPOSE_PROJECT_NAME=japon-explorateur-essai\nWEB_PORT=8000\n"
                       "AUTORISER_NOM_PROJET=japon-explorateur-essai\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("AUTORISER_NOM_PROJET=japon-explorateur-essai",
                      (self.destination() / ".env").read_text(encoding="utf-8-sig"))

    def test_existing_destination_is_never_overwritten(self):
        self.destination().mkdir()
        (self.destination() / "fichier-a-garder.txt").write_text("à garder")
        self.assertStopped(self.run_script(), "le dossier de destination existe déjà")
        self.assertEqual((self.destination() / "fichier-a-garder.txt").read_text(), "à garder")

    def test_docker_not_running(self):
        self.assertStopped(self.run_script(docker_info=1), "Docker Desktop ne répond pas")

    def test_failed_start_explains_how_to_go_back(self):
        result = self.run_script(up=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("démarrage de la nouvelle version impossible", result.stdout)
        self.assertIn("Pour revenir en arrière", result.stdout)
        self.assertIn("sauvegarde-20261114-220000-full.tar", result.stdout)
