"""2.0.0 — outils de vérification : `manage.py verifier_fonctionnalites` et `verifier-j-ed.ps1`.

La commande est exécutée réellement sur la base de test ; le script PowerShell l'est avec un faux « docker »
(tests/fixtures/verification) et un petit serveur web local qui joue le rôle de J-ed. Ignoré sans pwsh.
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TransactionTestCase

from apps.accounts.models import User
from apps.catalog.models import Catalogue, Record
from apps.core import verification as V
from apps.exports.models import ExportJob
from apps.translation.models import TranslationProject

ROOT = Path(settings.BASE_DIR)
SCRIPT = ROOT / "verifier-j-ed.ps1"
FAKE_DOCKER_DIR = ROOT / "tests" / "fixtures" / "verification"
PWSH = shutil.which("pwsh") or ("/opt/pwsh/pwsh" if Path("/opt/pwsh/pwsh").exists() else None)


def replaced(key, func):
    """La liste CHECKS garde une référence à chaque fonction : on y remplace l'entrée voulue."""
    return mock.patch.object(V, "CHECKS", [(k, label, func if k == key else f, needs)
                                           for k, label, f, needs in V.CHECKS])


class FeatureCheckTests(TransactionTestCase):
    """TransactionTestCase : la commande ouvre et annule sa propre transaction, comme sur une vraie base."""

    def setUp(self):
        call_command("seed_sources", verbosity=0)
        User.objects.create_user("admin-reel", password="motdepasse-solide-1", role="admin")

    def counts(self):
        return (Record.objects.count(), User.objects.count(), Catalogue.objects.count(),
                TranslationProject.objects.count(), ExportJob.objects.count())

    def test_every_feature_check_passes_and_nothing_is_kept(self):
        before = self.counts()
        results = {r.key: r for r in V.run()}
        self.assertEqual(self.counts(), before, "la base n'est pas modifiée")
        for key in ("japonais", "notices", "doublons", "import", "bibliotheque", "exports", "traduction", "pages",
                    "droits", "comptes"):
            with self.subTest(key=key):
                self.assertEqual(results[key].level, V.OK, f"{results[key].summary} {results[key].details}")
        self.assertEqual(results["sources"].level, V.SKIPPED, "aucun appel à Internet sans --sources")
        self.assertEqual(results["taches"].level, V.SKIPPED)  # tests : tâches exécutées immédiatement

    def test_a_failing_check_is_reported_and_the_others_still_run(self):
        with replaced("doublons", mock.Mock(side_effect=RuntimeError("panne fictive"))):
            results = {r.key: r for r in V.run()}
        self.assertEqual(results["doublons"].level, V.ERROR)
        self.assertIn("RuntimeError : panne fictive", results["doublons"].summary)
        self.assertEqual(results["exports"].level, V.OK)

    def test_dependent_checks_are_skipped_when_the_fictive_record_fails(self):
        with replaced("notices", mock.Mock(side_effect=RuntimeError("x"))):
            results = {r.key: r for r in V.run()}
        self.assertEqual(results["exports"].level, V.SKIPPED)
        self.assertIn("Notice fictive indisponible", results["exports"].summary)

    def test_command_json_and_exit_code(self):
        out = StringIO()
        with replaced("japonais", mock.Mock(return_value=(V.ERROR, "panne fictive", []))):
            with self.assertRaises(CommandError):
                call_command("verifier_fonctionnalites", "--json", stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(data["version"], settings.APP_VERSION)
        self.assertEqual(data["etat"], "error")
        self.assertIn("japonais", [v["cle"] for v in data["verifications"]])

    def test_report_masks_personal_paths(self):
        results = [V.Result("x", "Essai", V.OK, r"C:\Users\Arnaud\sauvegardes")]
        self.assertNotIn("Arnaud", V.report_text(results))


class _FakeJed(BaseHTTPRequestHandler):
    health_status = 200

    def do_GET(self):  # noqa: N802
        if self.path == "/sante/" and self.health_status != 200:
            self.send_response(self.health_status)
            self.end_headers()
            return
        self.send_response(200)
        if self.path == "/comptes/connexion/":
            self.send_header("Content-Security-Policy", "default-src 'self'")
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        return


class VerifyScriptRunTests(SimpleTestCase):
    def setUp(self):
        if PWSH is None:
            self.skipTest("PowerShell (pwsh) absent")
        self.tmp = Path(tempfile.mkdtemp(prefix="verif-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.install = self.tmp / "installation"
        self.install.mkdir()
        (self.install / "docker-compose.yml").write_text("name: x\n")
        (self.install / "VERSION").write_text("2.0.0\n")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeJed)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]
        self.backups = self.tmp / "sauvegardes"
        self.backups.mkdir()
        (self.backups / "sauvegarde-20261114-022300-full.tar").write_bytes(b"x" * 10)
        self.write_env()
        self.verif = self.tmp / "verif.json"
        self.verif.write_text(json.dumps({"version": "2.0.0", "etat": "ok", "verifications": [
            {"cle": "exports", "libelle": "Exports", "niveau": "ok", "resume": "6 formats", "details": []},
            {"cle": "argos", "libelle": "Argos", "niveau": "skipped", "resume": "non configuré", "details": []}]}),
            encoding="utf-8")

    def write_env(self, **extra):
        values = {"COMPOSE_PROJECT_NAME": "jed-essai", "WEB_PORT": str(self.port),
                  "DJANGO_SECRET_KEY": "x" * 64, "AI_KEYS_ENCRYPTION_KEY": "y" * 44, "POSTGRES_PASSWORD": "z" * 32,
                  "DOSSIER_SAUVEGARDES": str(self.backups)}
        values.update(extra)
        (self.install / ".env").write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")

    def run_script(self, *extra, **fake):
        env = dict(os.environ, FAKE_DOCKER_LOG=str(self.tmp / "docker.log"), FAKE_PORT=str(self.port),
                   FAKE_VERIF_JSON=str(self.verif),
                   PATH=str(FAKE_DOCKER_DIR) + os.pathsep + os.environ.get("PATH", ""))
        env.update({f"FAKE_{k.upper()}": str(v) for k, v in fake.items()})
        result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), "-Dossier",
                                 str(self.install), *extra], capture_output=True, text=True, timeout=300, env=env)
        self.report = next(self.tmp.glob("verification-j-ed-*.txt"), None)
        return result

    def test_healthy_installation(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for expected in ("[OK] Nom de l'installation : « jed-essai »", "[OK] Mots de passe techniques",
                         "[OK] Conteneurs : en service", "[OK] Port publié", "[OK] Volumes de données",
                         "[OK] Page de connexion : répond", "[OK] Exports : 6 formats", "[OK] Dossier des sauvegardes"):
            self.assertIn(expected, result.stdout)
        self.assertIsNotNone(self.report)
        self.assertNotIn("x" * 64, self.report.read_text(encoding="utf-8-sig"), "aucun secret dans le rapport")

    def test_health_address(self):
        result = self.run_script()
        self.assertIn("[OK] Contrôle de santé : le serveur répond et la base est joignable", result.stdout)
        for status, expected in ((404, "[Non vérifié] Contrôle de santé : adresse /sante/ absente"),
                                 (503, "[Problème] Contrôle de santé : le serveur répond, mais la base de données "
                                       "est injoignable")):
            _FakeJed.health_status = status
            try:
                result = self.run_script()
            finally:
                _FakeJed.health_status = 200
            self.assertIn(expected, result.stdout)

    def test_problems_are_reported_with_exit_code_1(self):
        self.write_env(DJANGO_SECRET_KEY="à-remplacer", COMPOSE_PROJECT_NAME="japon-explorateur-essai")
        result = self.run_script(beat_down=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("[Problème] Mots de passe techniques : à renseigner dans .env : DJANGO_SECRET_KEY", result.stdout)
        self.assertIn("AUTORISER_NOM_PROJET=japon-explorateur-essai manque", result.stdout)
        self.assertIn("[Problème] Conteneurs : arrêtés : beat", result.stdout)

    def test_argos_running_without_the_profile_line_is_flagged(self):
        """15 novembre 2026, poste de l'utilisateur : Argos en service mais « non activé » d'après .env."""
        result = self.run_script(argos=1)
        self.assertIn("[À surveiller] Argos : en service, mais COMPOSE_PROFILES=hors-ligne manque dans .env",
                      result.stdout)

    def test_docker_not_running(self):
        result = self.run_script(docker_info=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Docker Desktop : ne répond pas", result.stdout)

    def test_tests_option_runs_the_suite_in_the_container(self):
        result = self.run_script("-AvecTests")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[OK] Tests automatiques : 440 tests réussis", result.stdout)

    def test_script_file_is_ready_for_windows_powershell_51(self):
        raw = SCRIPT.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        text = raw.decode("utf-8-sig")
        self.assertLess(text.index("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8"),
                        text.index("Docker-Ici @('info'"))
        self.assertNotIn("down -v", text)
        self.assertNotIn("JaponEssai", text)
