"""2.0.2, lot 3 — installer-j-ed.ps1 (nouvelle installation, deuxième instance), Docker simulé.

Le script réel est lancé de bout en bout par PowerShell 7 ; seules les commandes Docker sont simulées
(tests/fixtures/mise_a_jour/docker). Ignoré si pwsh est absent. L'essai réel se fait à la recette.
"""
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
SCRIPT = ROOT / "installer-j-ed.ps1"
FAKE_DOCKER_DIR = ROOT / "tests" / "fixtures" / "mise_a_jour"
PWSH = shutil.which("pwsh") or ("/opt/pwsh/pwsh" if Path("/opt/pwsh/pwsh").exists() else None)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class InstallerFileTests(SimpleTestCase):
    def test_bom_crlf_and_never_removes_anything_of_another_installation(self):
        data = SCRIPT.read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        code = re.sub(r"<#.*?#>", "", data.decode("utf-8-sig"), flags=re.S)
        self.assertNotRegex(code, r"'down'|down -v|volume', 'rm'|'rmi'|image', 'rm'")


class InstallerRunTests(SimpleTestCase):
    def setUp(self):
        if PWSH is None:
            self.skipTest("PowerShell (pwsh) absent")
        self.tmp = Path(tempfile.mkdtemp(prefix="installation-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log = self.tmp / "docker.log"
        actuel = self.tmp / "autre-installation"
        actuel.mkdir()
        (actuel / "VERSION").write_text("2.0.1\n")
        (actuel / ".env").write_text("COMPOSE_PROJECT_NAME=jed-autre\nWEB_PORT=8001\n")
        (actuel / "docker-compose.yml").write_text("name: x\n")
        self.autre = actuel
        self.archive = self.tmp / "japon-explorateur-2.0.2.zip"
        exemple = (ROOT / ".env.example").read_text(encoding="utf-8")
        with zipfile.ZipFile(self.archive, "w") as z:
            z.writestr("japon-explorateur-2.0.2/VERSION", "2.0.2\n")
            z.writestr("japon-explorateur-2.0.2/docker-compose.yml", "name: ${COMPOSE_PROJECT_NAME}\n")
            z.writestr("japon-explorateur-2.0.2/.env.example", exemple)
        Path(f"{self.archive}.sha256").write_text(hashlib.sha256(self.archive.read_bytes()).hexdigest() + "\n")
        self.dest = self.tmp / "J-ed" / "jed-2-2.0.2"
        self.port = free_port()

    def run_script(self, *extra, nom="jed-2", port=None, **fake):
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy")}
        env.update(FAKE_DOCKER_LOG=str(self.log), FAKE_ACTUEL=str(self.autre),
                   PATH=str(FAKE_DOCKER_DIR) + os.pathsep + os.environ.get("PATH", ""))
        env.update({f"FAKE_{k.upper()}": str(v) for k, v in fake.items()})
        args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), "-Archive", str(self.archive),
                "-Destination", str(self.dest), "-Nom", nom, "-Port", str(port or self.port),
                "-DossierSauvegardes", str(self.tmp / "sauvegardes"), "-DelaiStabilite", "0", "-DelaiControle", "5",
                *extra]
        r = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
        self.calls = self.log.read_text().splitlines() if self.log.exists() else []
        return r

    def env_values(self):
        values = {}
        for line in (self.dest / ".env").read_text(encoding="utf-8").splitlines():
            m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line)
            if m:
                values[m.group(1)] = m.group(2)
        return values

    def journal(self):
        logs = list((self.tmp / "sauvegardes").glob("installation-*.log"))
        self.assertEqual(len(logs), 1)
        return logs[0].read_text(encoding="utf-8")

    def test_new_instance_is_installed_with_its_own_secrets(self):
        r = self.run_script("-Proxy", "http://proxy.exemple:3128")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("/comptes/premier-demarrage/", r.stdout)
        v = self.env_values()
        self.assertEqual((v["COMPOSE_PROJECT_NAME"], v["WEB_PORT"]), ("jed-2", str(self.port)))
        self.assertEqual(v["DOSSIER_SAUVEGARDES"], str(self.tmp / "sauvegardes"))
        self.assertEqual(v["COMPOSE_PROFILES"], "argos")
        self.assertEqual(v["HTTPS_PROXY"], "http://proxy.exemple:3128")
        self.assertIn("ollama", v["NO_PROXY"])
        self.assertEqual(len(v["DJANGO_SECRET_KEY"]), 64)
        self.assertEqual(len(v["POSTGRES_PASSWORD"]), 32)
        self.assertRegex(v["POSTGRES_PASSWORD"], r"^[A-Za-z0-9]+$")
        self.assertRegex(v["AI_KEYS_ENCRYPTION_KEY"], r"^[A-Za-z0-9_-]{43}=$")
        self.assertNotIn("à-remplacer", "".join(v.values()), "aucune valeur à remplacer (hors commentaires)")
        journal = self.journal()
        for secret in (v["DJANGO_SECRET_KEY"], v["POSTGRES_PASSWORD"], v["AI_KEYS_ENCRYPTION_KEY"]):
            self.assertNotIn(secret, journal + r.stdout)
        self.assertTrue(journal.rstrip().endswith("FIN code=0 installation réussie"))
        # toutes les commandes de l'installation se font dans le nouveau dossier, jamais dans l'autre
        self.assertFalse(any(c.startswith(str(self.autre)) for c in self.calls))
        build = next(i for i, c in enumerate(self.calls) if c.endswith("| compose build"))
        up = next(i for i, c in enumerate(self.calls) if c.endswith("| compose up -d"))
        self.assertLess(build, up)

    def test_two_installations_never_share_secrets(self):
        self.assertEqual(self.run_script().returncode, 0)
        premier = self.env_values()
        shutil.move(str(self.dest), str(self.tmp / "premiere"))
        shutil.rmtree(self.tmp / "sauvegardes")
        self.assertEqual(self.run_script(nom="jed-3", port=free_port()).returncode, 0)
        second = self.env_values()
        for cle in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD", "AI_KEYS_ENCRYPTION_KEY"):
            self.assertNotEqual(premier[cle], second[cle])

    def test_name_of_an_existing_installation_is_refused(self):
        ls = json.dumps([{"Name": "jed-autre", "Status": "running(5)", "ConfigFiles": str(self.autre / "docker-compose.yml")}])
        r = self.run_script(nom="jed-autre", compose_ls=ls)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("existe déjà", r.stdout)
        self.assertFalse(self.dest.exists())

    def test_old_data_volumes_block_the_name(self):
        r = self.run_script(volumes="jed-2_db-data jed-2_app-data")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("existent encore dans Docker", r.stdout)
        self.assertFalse(self.dest.exists())

    def test_port_of_another_installation_or_program_is_refused(self):
        ls = json.dumps([{"Name": "jed-autre", "Status": "exited(5)", "ConfigFiles": str(self.autre / "docker-compose.yml")}])
        r = self.run_script(port=8001, compose_ls=ls)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("déjà celui de l'installation « jed-autre »", r.stdout)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen()
            r = self.run_script(port=s.getsockname()[1])
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("autre programme", r.stdout)
        self.assertFalse(self.dest.exists())

    def test_reserved_name_bad_hash_proxy_with_password_are_refused(self):
        self.assertIn("nom réservé", self.run_script(nom="japon-explorateur").stdout)
        self.assertIn("refusé", self.run_script(nom="Jed").stdout)
        self.assertIn("proxy refusé", self.run_script("-Proxy", "http://jean:secret@proxy:3128").stdout)
        Path(f"{self.archive}.sha256").write_text("0" * 64 + "\n")
        self.assertIn("empreinte de l'archive différente", self.run_script().stdout)
        self.assertFalse(self.dest.exists())
        self.assertFalse(any("compose build" in c for c in self.calls))

    def test_build_failure_gives_code_3_and_starts_nothing(self):
        r = self.run_script(build=1)
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertTrue((self.dest / ".env").exists(), "dossier gardé, jamais supprimé")
        self.assertIn("peut être supprimé", r.stdout)
        self.assertFalse(any(c.endswith("compose up -d") for c in self.calls))

    def test_jed_that_does_not_answer_gives_code_5(self):
        r = self.run_script(sante="ko")
        self.assertEqual(r.returncode, 5, r.stdout)
        self.assertIn("ne répond pas", r.stdout)

    def test_without_argos(self):
        self.assertEqual(self.run_script("-SansArgos").returncode, 0)
        self.assertEqual(self.env_values()["COMPOSE_PROFILES"], "")
