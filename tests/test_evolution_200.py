"""Évolution 2.0.0 (J-ed) — lot 0 : numéro de version et règles de nommage de l'installation.

Ces tests lisent les fichiers de configuration livrés et exécutent docker/entrypoint.sh avec /bin/sh ;
ils n'exécutent pas Docker (indisponible dans l'environnement de développement).
"""
import json
import os
import re
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8-sig")


class VersionTests(SimpleTestCase):
    def test_version_is_200_everywhere(self):
        self.assertEqual(read("VERSION").strip(), "2.0.0")
        self.assertEqual(settings.APP_VERSION, "2.0.0")
        compose = read("docker-compose.yml")
        self.assertIn("image: japon-explorateur:2.0.0", compose)
        self.assertIn("image: japon-explorateur-argos:2.0.0", compose)
        self.assertIn("## 2.0.0", read("CHANGELOG.md"))

    def test_no_stale_install_values(self):
        compose = read("docker-compose.yml")
        for stale in ("japon-explorateur:1.3.0", "japon-explorateur-argos:1.3.0", "essai-130", "WEB_PORT:-8002"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, compose)
        self.assertNotIn("essai-130", read("docker/entrypoint.sh"))


class NamingTests(SimpleTestCase):
    """Décision D3 : aucun nom de projet par défaut ; il doit figurer dans .env."""

    def test_project_name_is_mandatory_in_compose(self):
        compose = read("docker-compose.yml")
        self.assertRegex(compose, r"(?m)^name: \$\{COMPOSE_PROJECT_NAME:\?[^}]+\}$")
        self.assertNotIn("COMPOSE_PROJECT_NAME:-", compose)

    def test_every_container_receives_the_project_check(self):
        """web hérite de x-app ; worker, beat et argos redéfinissent « environment » et doivent la porter."""
        self.assertEqual(read("docker-compose.yml").count("COMPOSE_PROJECT_CHECK: ${COMPOSE_PROJECT_NAME}"), 4)

    def test_default_port_and_loopback_only(self):
        self.assertIn('"127.0.0.1:${WEB_PORT:-8000}:8000"', read("docker-compose.yml"))

    def test_env_example_leaves_the_name_to_fill(self):
        env = read(".env.example")
        self.assertRegex(env, r"(?m)^COMPOSE_PROJECT_NAME=$")
        self.assertRegex(env, r"(?m)^WEB_PORT=8000$")
        self.assertRegex(env, r"(?m)^# AUTORISER_NOM_PROJET=$")


class BackupFolderTests(SimpleTestCase):
    """Sauvegardes visibles dans Windows : DOSSIER_SAUVEGARDES monté sur /backups-externes."""

    def test_backup_copy_is_mounted_for_web_and_worker(self):
        compose = read("docker-compose.yml")
        self.assertIn("- ${DOSSIER_SAUVEGARDES:-sauvegardes-externes}:/backups-externes", compose)
        self.assertRegex(compose, r"(?m)^  sauvegardes-externes:$")
        # web (x-app) et worker (environment redéfini) : la sauvegarde planifiée tourne dans le worker.
        self.assertEqual(compose.count("BACKUP_EXTERNAL_DIR: /backups-externes"), 2)

    def test_image_prepares_the_folder_for_the_application_user(self):
        dockerfile = read("docker/Dockerfile")
        self.assertIn("/backups-externes", dockerfile)
        self.assertRegex(dockerfile, r"chown -R japon:japon [^\n]*/backups-externes")

    def test_env_example_documents_the_windows_folder(self):
        self.assertRegex(read(".env.example"), r"(?m)^# DOSSIER_SAUVEGARDES=")


class ComposeConfigTests(SimpleTestCase):
    """`docker compose config` fonctionne sans le service Docker : la configuration résolue est vérifiée."""

    def compose_config(self, env_text):
        if shutil.which("docker") is None:
            self.skipTest("Docker Compose absent")
        tmp = Path(tempfile.mkdtemp(prefix="compose-200-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copy(ROOT / "docker-compose.yml", tmp)
        (tmp / ".env").write_text(env_text, encoding="utf-8")
        env = dict(os.environ, POSTGRES_PASSWORD="fictif-pour-test")
        for name in ("COMPOSE_PROJECT_NAME", "DOSSIER_SAUVEGARDES", "WEB_PORT"):
            env.pop(name, None)
        return subprocess.run(["docker", "compose", "config", "--format", "json"], cwd=tmp, capture_output=True,
                              text=True, timeout=60, env=env)

    def test_missing_project_name_stops_compose(self):
        result = self.compose_config("WEB_PORT=8000\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("COMPOSE_PROJECT_NAME", result.stderr)

    def test_backup_copy_defaults_to_a_docker_volume(self):
        result = self.compose_config("COMPOSE_PROJECT_NAME=jed-essai\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(config["name"], "jed-essai")
        for service in ("web", "worker"):
            with self.subTest(service=service):
                mounts = {v["target"]: v for v in config["services"][service]["volumes"]}
                self.assertEqual(mounts["/backups-externes"]["type"], "volume")
                self.assertEqual(mounts["/backups-externes"]["source"], "sauvegardes-externes")
        self.assertEqual(config["services"]["web"]["ports"][0]["published"], "8000")

    def test_windows_backup_folder_becomes_a_bind_mount(self):
        result = self.compose_config("COMPOSE_PROJECT_NAME=jed-essai\nDOSSIER_SAUVEGARDES=/srv/jed/sauvegardes\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        mounts = {v["target"]: v for v in config["services"]["worker"]["volumes"]}
        self.assertEqual(mounts["/backups-externes"]["type"], "bind")
        self.assertEqual(mounts["/backups-externes"]["source"], "/srv/jed/sauvegardes")
        # le chemin vu depuis l'ordinateur parvient à l'application (affichage sur la page Sauvegardes)
        self.assertEqual(config["services"]["web"]["environment"].get("DOSSIER_SAUVEGARDES"),
                         "/srv/jed/sauvegardes")


class EntrypointNamingTests(SimpleTestCase):
    def run_entrypoint(self, project, authorise=None):
        env = dict(os.environ, DATABASE_URL="", RUN_MIGRATIONS="0",
                   PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
        env.pop("AUTORISER_NOM_PROJET", None)
        env.pop("COMPOSE_PROJECT_CHECK", None)
        if project is not None:
            env["COMPOSE_PROJECT_CHECK"] = project
        if authorise is not None:
            env["AUTORISER_NOM_PROJET"] = authorise
        return subprocess.run(["sh", str(ROOT / "docker" / "entrypoint.sh"), "echo", "demarrage-autorise"],
                              env=env, capture_output=True, text=True, timeout=60)

    def test_missing_or_empty_project_name_is_refused(self):
        for value in (None, ""):
            with self.subTest(value=value):
                result = self.run_entrypoint(value)
                self.assertEqual(result.returncode, 1)
                self.assertIn("COMPOSE_PROJECT_NAME n'est pas défini", result.stderr)
                self.assertNotIn("demarrage-autorise", result.stdout)

    def test_a_new_installation_name_is_accepted(self):
        for name in ("jed", "jed-essai", "japon-explorateur-essai-130"):
            with self.subTest(name=name):
                result = self.run_entrypoint(name)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("demarrage-autorise", result.stdout)

    def test_protected_names_message_names_the_exact_authorisation(self):
        result = self.run_entrypoint("japon-explorateur")
        self.assertEqual(result.returncode, 1)
        self.assertIn("AUTORISER_NOM_PROJET=japon-explorateur", result.stderr)
        self.assertNotRegex(result.stderr, re.compile(r"1\.[23]\.0"))
