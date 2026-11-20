"""2.0.0, lot 0 — mettre-a-jour.ps1 exécuté par PowerShell avec un faux « docker » (tests/fixtures/mise_a_jour).
2.0.1, lot 1 — mise à jour sûre : construction avant l'arrêt de l'ancienne version, retour automatique, journal,
codes de sortie.

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
#: Mot de passe fictif du .env : il ne doit jamais apparaître dans le journal de la mise à jour.
SECRET_FICTIF = "mot-de-passe-fictif-a-ne-pas-journaliser"
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
        self.write_env(f"COMPOSE_PROJECT_NAME=jed-essai\nWEB_PORT=8000\nPOSTGRES_PASSWORD={SECRET_FICTIF}\n")
        self.archive = self.make_archive("2.0.0")

    def write_env(self, text):
        (self.current / ".env").write_text(text, encoding="utf-8")

    def make_archive(self, version, name=None, corrupt_hash=False, script=None):
        archive = self.tmp / (name or f"jed-{version}.zip")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("VERSION", f"{version}\n")
            if script is not None:
                z.writestr("mettre-a-jour.ps1", script)
            z.writestr("docker-compose.yml", "name: ${COMPOSE_PROJECT_NAME}\n")
            z.writestr("README.md", "fictif\n")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if corrupt_hash:
            digest = "0" * 64
        Path(f"{archive}.sha256").write_text(f"{digest}  {archive.name}\n")
        return archive

    def run_script(self, *extra, oui=True, legacy=False, stdin=None, **fake):
        env = dict(os.environ, FAKE_DOCKER_LOG=str(self.log), FAKE_ACTUEL=str(self.current),
                   PATH=str(FAKE_DOCKER_DIR) + os.pathsep + os.environ.get("PATH", ""))
        env.update({f"FAKE_{k.upper()}": str(v) for k, v in fake.items()})
        # -DelaiStabilite 0 : pas d'attente de 15 s entre les deux interrogations de la page de santé.
        params = ["-Archive", str(self.archive), "-Actuel", str(self.current),
                  "-DossierSauvegardes", str(self.tmp / "sauvegardes"), *(["-Oui"] if oui else []),
                  "-DelaiStabilite", "0", *extra]
        if legacy:
            # Comme Windows PowerShell 5.1, qui retire les guillemets doubles des arguments des programmes (docker).
            quoted = " ".join("'" + a.replace("'", "''") + "'" if not a.startswith("-") else a for a in params)
            args = [PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$PSNativeCommandArgumentPassing = 'Legacy'; & '{SCRIPT}' {quoted}; exit $LASTEXITCODE"]
        else:
            args = [PWSH, "-NoProfile", *([] if stdin is not None else ["-NonInteractive"]), "-File", str(SCRIPT),
                    *params]
        result = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env, input=stdin)
        self.calls = self.log.read_text().splitlines() if self.log.exists() else []
        return result

    def journal(self):
        logs = sorted((self.tmp / "sauvegardes").glob("mise-a-jour-*.log"))
        self.assertEqual(len(logs), 1, "un journal par mise à jour")
        return logs[0].read_text(encoding="utf-8")

    def index(self, predicate):
        for i, call in enumerate(self.calls):
            if predicate(call):
                return i
        self.fail("appel attendu absent :\n" + "\n".join(self.calls))

    def images(self):
        return dict(line.split(" ", 1) for line in (self.tmp / "images.txt").read_text().splitlines())

    def destination(self):
        return self.tmp / self.archive.stem

    def assertStopped(self, result, message, code=1):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
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
        # 2.0.1 : sauvegarde (ancien dossier) → construction du nouveau PENDANT que l'ancien tourne → arrêt de
        # l'ancien → démarrage du nouveau, sans reconstruire → contrôle final
        order = [c for c in self.calls if "manage.py backup" in c or c.endswith("compose build")
                 or c.endswith("compose down") or "up -d" in c or "etat_installation" in c]
        self.assertTrue(order[0].startswith(str(self.current)) and "backup" in order[0])
        self.assertTrue(order[1].startswith(str(dest)) and order[1].endswith("compose build"))
        self.assertTrue(order[2].startswith(str(self.current)) and order[2].endswith("compose down"))
        self.assertTrue(order[3].startswith(str(dest)) and order[3].endswith("compose up -d"))
        self.assertIn("etat_installation", order[4])
        self.assertFalse(any("--build" in c for c in self.calls), "plus de construction après l'arrêt")
        self.assertEqual((self.current / "VERSION").read_text().strip(), "1.3.0", "ancien dossier inchangé")
        self.assertIn("FIN code=0 mise à jour réussie", self.journal())

    def test_outdated_script_is_flagged(self):
        """16 novembre 2026 : un ancien mettre-a-jour.ps1, gardé à côté des archives, ajoutait une ligne
        COMPOSE_PROFILES=hors-ligne à chaque mise à jour. Le script dit maintenant s'il n'est pas celui de l'archive."""
        self.archive = self.make_archive("2.0.0", script=SCRIPT.read_bytes())
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("n'est pas celui de l'archive", result.stdout)
        self.archive = self.make_archive("2.0.0", name="jed-autre.zip", script="# version plus récente\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ce script de mise à jour n'est pas celui de l'archive", result.stdout)
        self.assertIn("Rappel : copiez", result.stdout)

    def test_argos_is_restarted_when_it_was_running(self):
        result = self.run_script(argos=1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 2.0.0 (lot 7) : le fichier .env décide des services démarrés ; plus d'option --profile.
        self.assertTrue(any(c.endswith("compose up -d") for c in self.calls))
        self.assertFalse(any("--profile" in c for c in self.calls))
        env = (self.destination() / ".env").read_text(encoding="utf-8-sig")
        self.assertIn("COMPOSE_PROFILES=argos", env, "Argos redémarrera aussi avec un simple up -d")

    def test_argos_becomes_standard_when_the_line_is_missing(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        env = (self.destination() / ".env").read_text(encoding="utf-8-sig")
        self.assertIn("\nCOMPOSE_PROFILES=argos\n", env)
        self.assertIn("ligne COMPOSE_PROFILES=argos ajoutée", result.stdout)

    def test_existing_profiles_line_is_respected(self):
        for line, message in (("COMPOSE_PROFILES=hors-ligne", ""), ("COMPOSE_PROFILES=", "Argos reste désactivé")):
            with self.subTest(line=line):
                shutil.rmtree(self.destination(), ignore_errors=True)
                self.write_env(f"COMPOSE_PROJECT_NAME=jed-essai\nWEB_PORT=8000\nPOSTGRES_PASSWORD=fictif\n{line}\n")
                result = self.run_script()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                env = (self.destination() / ".env").read_text(encoding="utf-8-sig")
                self.assertEqual(env.count("COMPOSE_PROFILES"), 1, "ligne existante jamais modifiée ni doublée")
                self.assertIn(line, env)
                if message:
                    self.assertIn(message, result.stdout)

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

    # --- 2.0.1, lot 1 : mise à jour sûre ---------------------------------------------------------------------

    def test_build_failure_leaves_the_old_version_running(self):
        """19 novembre 2026, VM derrière un proxy : la construction échouait APRÈS l'arrêt de l'ancienne version."""
        result = self.run_script(build=1)
        self.assertStopped(result, "construction de la nouvelle version impossible", code=3)
        self.assertIn("L'ancienne version est toujours en service", result.stdout)
        self.assertIn("docker pull python:3.12-slim-bookworm", result.stdout)
        self.assertIn("context deadline exceeded", result.stdout, "le message de Docker est montré")
        self.assertFalse(any(c.endswith("compose down") for c in self.calls), "rien n'a été arrêté")
        self.assertFalse(any("up -d" in c for c in self.calls))
        self.assertIn("FIN code=3", self.journal())

    def test_missing_image_is_downloaded_before_stopping_anything(self):
        result = self.run_script(images_absentes="redis:7-alpine")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        pull = self.index(lambda c: c.endswith("compose pull --ignore-buildable"))
        down = self.index(lambda c: c.endswith("compose down"))
        self.assertLess(pull, down, "téléchargement AVANT l'arrêt de l'ancienne version")
        self.assertIn("Téléchargement des images manquantes : redis:7-alpine", result.stdout)

    def test_image_that_cannot_be_downloaded_stops_before_stopping_anything(self):
        result = self.run_script(images_absentes="redis:7-alpine", pull="echec")
        self.assertStopped(result, "image(s) introuvable(s) : redis:7-alpine", code=3)
        self.assertIn("L'ancienne version est toujours en service", result.stdout)

    def test_failed_start_returns_to_the_old_version(self):
        result = self.run_script(up=1)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("démarrage de la nouvelle version impossible", result.stdout)
        self.assertIn("Retour réussi : l'ancienne version (1.3.0) est de nouveau en service, http://localhost:8000",
                      result.stdout)
        self.assertIn("sauvegarde-20261114-220000-full.tar", result.stdout)
        start_new = self.index(lambda c: c.startswith(str(self.destination())) and c.endswith("compose up -d"))
        down_new = self.index(lambda c: c.startswith(str(self.destination())) and c.endswith("compose down"))
        start_old = self.index(lambda c: c.startswith(str(self.current)) and c.endswith("compose up -d"))
        self.assertLess(start_new, down_new)
        self.assertLess(down_new, start_old, "la nouvelle est arrêtée avant de relancer l'ancienne")
        self.assertFalse(any("-v" in c.split() or "--volumes" in c for c in self.calls), "aucun volume effacé")
        self.assertIn("FIN code=4", self.journal())

    def test_failed_final_check_returns_to_the_old_version(self):
        result = self.run_script("-DelaiControle", "1", etat="ko")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("la nouvelle version ne répond pas correctement après 1 s", result.stdout)
        self.assertIn("Retour réussi", result.stdout)

    def test_failed_return_says_what_to_do(self):
        result = self.run_script(up=1, up_ancienne=1)
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("Le retour automatique à l'ancienne version n'a pas abouti", result.stdout)
        self.assertIn(f"dans « {self.current} » : docker compose up -d", result.stdout)
        self.assertIn("restaurez la sauvegarde", result.stdout)
        self.assertIn("FIN code=5", self.journal())

    def test_same_version_gets_its_old_image_back_on_return(self):
        """Versions candidates (rc1 → rc2) : même numéro, donc même étiquette d'image. La construction la reprend ;
        le retour doit remettre l'image d'avant, sinon l'« ancienne » version redémarrerait avec le nouveau code."""
        (self.current / "VERSION").write_text("2.0.0\n")
        result = self.run_script(up=1)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        build = self.index(lambda c: c.endswith("compose build"))
        tag = self.index(lambda c: c.endswith("tag sha256:ancienne japon-explorateur:2.0.0"))
        start_old = self.index(lambda c: c.startswith(str(self.current)) and c.endswith("compose up -d"))
        self.assertLess(build, tag)
        self.assertLess(tag, start_old)
        self.assertEqual(self.images()["japon-explorateur:2.0.0"], "sha256:ancienne")

    def test_different_version_keeps_both_images(self):
        result = self.run_script(up=1)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertFalse(any(" | tag " in c for c in self.calls), "rien à remettre : étiquettes différentes")
        images = self.images()
        self.assertEqual(images["japon-explorateur:1.3.0"], "sha256:ancienne")
        self.assertEqual(images["japon-explorateur:2.0.0"], "sha256:construite")

    def test_answer_other_than_oui_cancels_with_code_2(self):
        result = self.run_script(oui=False, stdin="non\n")
        self.assertStopped(result, "mise à jour annulée à votre demande", code=2)
        self.assertIn("L'ancienne version est toujours en service", result.stdout)
        self.assertTrue(any(c.endswith("compose build") for c in self.calls), "question posée après la construction")

    def test_journal_is_readable_and_never_contains_the_passwords(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        journal = self.journal()
        self.assertIn("Journal de la mise à jour : ", result.stdout)
        self.assertNotIn(SECRET_FICTIF, journal)
        self.assertIn("compose config --format json", journal)
        self.assertIn("RESULTAT code=0 (sortie non journalisée)", journal)
        reperes = {"ETAPE", "INFO", "ATTENTION", "COMMANDE", "RESULTAT", "ERREUR", "FIN"}
        for line in journal.splitlines():
            if line.startswith("    | "):
                continue
            self.assertRegex(line, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [A-Z]+ ")
            self.assertIn(line.split(" ")[2], reperes, line)
        for step in range(1, 8):
            self.assertIn(f" ETAPE {step}/7 ", journal)
        self.assertTrue(journal.rstrip().splitlines()[-1].split(" ", 3)[2:] == ["FIN", "code=0 mise à jour réussie"])

    def test_journal_starts_before_the_first_check(self):
        """Une erreur dès les contrôles est journalisée (le journal reprend les lignes écrites avant son ouverture)."""
        self.archive = self.make_archive("2.0.0", corrupt_hash=True)
        self.run_script()
        journal = self.journal()
        self.assertIn("INFO Mise à jour de J-ed", journal)
        self.assertIn("ERREUR empreinte de l'archive différente", journal)
        self.assertIn("FIN code=1", journal)

    # --- 2.0.1-rc2 : défauts trouvés pendant la recette de la rc1 (20 novembre 2026) --------------------------

    def test_final_check_asks_the_web_server_twice(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        etat = self.index(lambda c: "etat_installation" in c)
        sante = [i for i, c in enumerate(self.calls) if c.endswith("curl -fsS http://localhost:8000/sante/")]
        self.assertEqual(len(sante), 2, "deux interrogations de la page de santé")
        self.assertLess(etat, sante[0])
        self.assertIn("Le serveur web répond ; nouveau contrôle dans 0 s", result.stdout)

    def test_web_server_that_never_answers_returns_to_the_old_version(self):
        """R4 de la recette rc1 : etat_installation répondait pendant que le conteneur préparait la base, puis le
        conteneur s'arrêtait ; le script annonçait « Mise à jour terminée »."""
        result = self.run_script("-DelaiControle", "1", sante="ko")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("le serveur web ne répond pas (page /sante/)", result.stdout)
        self.assertIn("Retour réussi", result.stdout)
        self.assertNotIn("Mise à jour terminée", result.stdout)

    def test_web_server_that_stops_after_one_answer_returns_to_the_old_version(self):
        result = self.run_script("-DelaiControle", "1", sante="une-fois")
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("Le serveur web répond ; nouveau contrôle", result.stdout, "une première réponse…")
        self.assertIn("(page /sante/)", result.stdout, "… puis plus aucune : retour")
        self.assertIn("Retour réussi", result.stdout)
        self.assertNotIn("Mise à jour terminée", result.stdout)

    def test_docker_error_lines_are_shown_as_text(self):
        """R3 de la recette rc1 : « System.Management.Automation.RemoteException » à la place des lignes vides."""
        result = self.run_script(build=1)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("Dockerfile:15", result.stdout)
        self.assertIn("context deadline exceeded", result.stdout)
        self.assertNotIn("RemoteException", result.stdout)
        self.assertNotIn("RemoteException", self.journal())

    def test_docker_error_lines_are_shown_as_text_like_windows_powershell_51(self):
        result = self.run_script(build=1, legacy=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertNotIn("RemoteException", result.stdout + self.journal())

    def test_partial_build_gets_the_old_image_back(self):
        """R3 de la recette rc1 : la construction a ré-étiqueté une image avant d'échouer (même version)."""
        (self.current / "VERSION").write_text("2.0.0\n")
        result = self.run_script(build_partiel=1)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("Image japon-explorateur:2.0.0 remise comme avant la mise à jour.", result.stdout)
        self.assertEqual(self.images()["japon-explorateur:2.0.0"], "sha256:ancienne")
        self.assertFalse(any(c.endswith("compose down") for c in self.calls), "rien n'a été arrêté")

    def test_cancel_after_build_gets_the_old_image_back(self):
        (self.current / "VERSION").write_text("2.0.0\n")
        result = self.run_script(oui=False, stdin="non\n")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.images()["japon-explorateur:2.0.0"], "sha256:ancienne")

    def test_full_update_like_windows_powershell_51(self):
        """Arguments passés comme Windows PowerShell 5.1 ($PSNativeCommandArgumentPassing = 'Legacy')."""
        result = self.run_script(legacy=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(any(c.endswith("image inspect --format {{.Id}} japon-explorateur:1.3.0") for c in self.calls))
