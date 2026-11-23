"""2.0.2, lot 1 — logique de l'assistant J-ed (assistant/AssistantJed.psm1), sans la fenêtre.

Le module est chargé dans PowerShell 7 ; les commandes Docker sont simulées par le faux « docker » des tests de
mise à jour (tests/fixtures/mise_a_jour). Ignoré si PowerShell (pwsh) n'est pas installé. L'essai réel sous
Windows PowerShell 5.1, avec la fenêtre, se fait à la recette.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
MODULE = ROOT / "assistant" / "AssistantJed.psm1"
SCRIPT_MAJ = ROOT / "mettre-a-jour.ps1"
FAKE_DOCKER_DIR = ROOT / "tests" / "fixtures" / "mise_a_jour"
SECRET_FICTIF = "mot-de-passe-fictif-de-l-assistant"
PWSH = shutil.which("pwsh") or ("/opt/pwsh/pwsh" if Path("/opt/pwsh/pwsh").exists() else None)


class ModuleFileTests(SimpleTestCase):
    def test_bom_and_crlf_for_windows_powershell_51(self):
        data = MODULE.read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"), "UTF-8 avec BOM")
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""), "fins de ligne CRLF seulement")

    def test_never_removes_volumes_nor_confirms_alone(self):
        code = re.sub(r"<#.*?#>", "", MODULE.read_text(encoding="utf-8-sig"), flags=re.S)
        code = "\n".join(l for l in code.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotRegex(code, r"'down'|\bdown -v\b|'-v'|--volumes")
        self.assertNotIn("'-Oui'", code.replace("$x -ne '-Oui'", ""), "jamais -Oui ajouté par l'assistant")


class AssistantTestCase(SimpleTestCase):
    def setUp(self):
        if PWSH is None:
            self.skipTest("PowerShell (pwsh) absent")
        self.tmp = Path(tempfile.mkdtemp(prefix="assistant-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log = self.tmp / "docker.log"
        self.liste = self.tmp / "liste" / "installations.txt"

    def make_install(self, folder, name, port=8000, version="2.0.1", sauvegardes=None):
        d = self.tmp / folder
        d.mkdir(parents=True)
        (d / "docker-compose.yml").write_text("name: x\n")
        (d / "VERSION").write_text(f"{version}\n")
        env = f"COMPOSE_PROJECT_NAME={name}\nWEB_PORT={port}\nPOSTGRES_PASSWORD={SECRET_FICTIF}\n"
        if sauvegardes:
            env += f"DOSSIER_SAUVEGARDES={sauvegardes}\n"
        (d / ".env").write_text(env, encoding="utf-8")
        return d

    def ps(self, code, **fake):
        """Exécute du PowerShell avec le module chargé ; le résultat est la dernière sortie, en JSON."""
        actuel = fake.pop("actuel", None)
        if actuel is None:
            actuel = self.tmp / "actuel-par-defaut"
            if not actuel.exists():
                self.make_install("actuel-par-defaut", "jed-defaut")
        env = dict(os.environ, FAKE_DOCKER_LOG=str(self.log), FAKE_ACTUEL=str(actuel),
                   PATH=str(FAKE_DOCKER_DIR) + os.pathsep + os.environ.get("PATH", ""))
        env.update({f"FAKE_{k.upper()}": str(v) for k, v in fake.items()})
        full = ("$ErrorActionPreference = 'Stop'; $PSNativeCommandArgumentPassing = 'Legacy'; "
                f"Import-Module '{MODULE}' -Force; $r = & {{ {code} }}; ConvertTo-Json -InputObject $r -Depth 6 -Compress")
        result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", full],
                                capture_output=True, text=True, timeout=300, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout.strip().splitlines()
        return json.loads(out[-1]) if out else None


class InstallationsTests(AssistantTestCase):
    def test_describes_an_installation_without_its_secrets(self):
        d = self.make_install("japon-explorateur-2.0.1", "jed-essai-2", port=8002, sauvegardes="D:/Sauvegardes")
        r = self.ps(f"Get-InstallationJed '{d}'")
        self.assertTrue(r["Valide"])
        self.assertEqual((r["Nom"], r["Port"], r["Version"], r["DossierSauvegardes"]),
                         ("jed-essai-2", 8002, "2.0.1", "D:/Sauvegardes"))
        self.assertTrue(r["Essai"])
        self.assertFalse(r["Protegee"])
        self.assertNotIn(SECRET_FICTIF, json.dumps(r))

    def test_protected_main_installation_is_flagged(self):
        d = self.make_install("principale", "japon-explorateur")
        r = self.ps(f"Get-InstallationJed '{d}'")
        self.assertTrue(r["Protegee"])
        self.assertFalse(r["Essai"])

    def test_folder_that_is_not_jed_is_refused_with_a_reason(self):
        (self.tmp / "autre").mkdir()
        r = self.ps(f"Get-InstallationJed '{self.tmp / 'autre'}'")
        self.assertFalse(r["Valide"])
        self.assertIn("docker-compose.yml absent", r["Probleme"])
        d = self.make_install("sans-env", "x")
        (d / ".env").unlink()
        self.assertIn(".env absent", self.ps(f"Get-InstallationJed '{d}'")["Probleme"])
        r = self.ps(f"Get-InstallationJed '{self.tmp / 'disparu'}'")
        self.assertIn("introuvable", r["Probleme"])

    def test_finds_installations_seen_by_docker_and_remembers_them(self):
        a = self.make_install("a", "jed-a", port=8000)
        b = self.make_install("b", "jed-b", port=8001)
        ls = json.dumps([{"Name": "jed-a", "Status": "running(9)", "ConfigFiles": str(a / "docker-compose.yml")},
                         {"Name": "jed-b", "Status": "exited(9)", "ConfigFiles": str(b / "docker-compose.yml")}])
        r = self.ps(f"Find-InstallationsJed -Fichier '{self.liste}'", compose_ls=ls)
        self.assertEqual([(i["Nom"], i["Etat"]) for i in r], [("jed-a", "en marche"), ("jed-b", "arrêtée")])
        self.assertEqual(len(self.liste.read_text(encoding="utf-8").splitlines()), 2, "gardées dans la liste")
        self.assertNotIn(SECRET_FICTIF, self.liste.read_text(encoding="utf-8"))

    def test_installation_stopped_with_down_is_still_found_from_the_list(self):
        """« docker compose ls » ne voit plus une installation arrêtée par « down » : la liste gardée la retrouve."""
        a = self.make_install("a", "jed-a")
        self.ps(f"Add-InstallationListeJed -Fichier '{self.liste}' -Dossier '{a}'")
        self.ps(f"Add-InstallationListeJed -Fichier '{self.liste}' -Dossier '{a}/'")
        self.assertEqual(len(self.liste.read_text(encoding="utf-8").splitlines()), 1, "sans doublon")
        r = self.ps(f"Find-InstallationsJed -Fichier '{self.liste}'", compose_ls="[]")
        self.assertEqual([(i["Nom"], i["Etat"]) for i in r], [("jed-a", "arrêtée")])

    def test_docker_not_started_still_lists_known_installations(self):
        a = self.make_install("a", "jed-a")
        self.ps(f"Add-InstallationListeJed -Fichier '{self.liste}' -Dossier '{a}'")
        r = self.ps(f"Find-InstallationsJed -Fichier '{self.liste}'", compose_ls="erreur", compose_ls_code=1)
        self.assertEqual([i["Nom"] for i in r], ["jed-a"])


class PrerequisTests(AssistantTestCase):
    def faits(self, **changes):
        base = {"Windows": True, "Bits64": True, "Build": 22631, "MemoireGo": 16, "Virtualisation": True,
                "Wsl": True, "DockerInstalle": True, "DockerDemarre": True, "DisqueLibreGo": 120}
        base.update(changes)
        lines = "; ".join(f"{k} = {self.lit(v)}" for k, v in base.items())
        return f"Test-PrerequisJed -Faits ([pscustomobject]@{{ {lines} }})"

    @staticmethod
    def lit(v):
        if v is None:
            return "$null"
        if isinstance(v, bool):
            return "$true" if v else "$false"
        return str(v)

    def niveaux(self, **changes):
        return {c["Cle"]: (c["Niveau"], c["Aide"]) for c in self.ps(self.faits(**changes))}

    def test_everything_ready(self):
        n = self.niveaux()
        self.assertEqual({k: v[0] for k, v in n.items()},
                         {k: "ok" for k in ("windows", "memoire", "virtualisation", "wsl", "docker", "disque")})

    def test_each_missing_point_is_an_error_with_its_help(self):
        self.assertEqual(self.niveaux(Wsl=False)["wsl"], ("erreur", "AVANT-DE-COMMENCER.html#wsl"))
        self.assertEqual(self.niveaux(DockerInstalle=False, DockerDemarre=False)["docker"],
                         ("erreur", "AVANT-DE-COMMENCER.html#docker"))
        self.assertEqual(self.niveaux(DockerDemarre=False)["docker"],
                         ("erreur", "AVANT-DE-COMMENCER.html#docker-demarre"))
        self.assertEqual(self.niveaux(Virtualisation=False)["virtualisation"][0], "erreur")
        self.assertEqual(self.niveaux(DisqueLibreGo=5)["disque"][0], "erreur")
        self.assertEqual(self.niveaux(MemoireGo=2)["memoire"][0], "erreur")
        self.assertEqual(self.niveaux(Windows=False)["windows"][0], "erreur")

    def test_borderline_points_are_warnings(self):
        self.assertEqual(self.niveaux(MemoireGo=6)["memoire"][0], "attention")
        self.assertEqual(self.niveaux(DisqueLibreGo=15)["disque"][0], "attention")
        self.assertEqual(self.niveaux(Build=19041)["windows"][0], "attention")
        self.assertEqual(self.niveaux(Virtualisation=None)["virtualisation"][0], "attention")

    def test_facts_are_gathered_without_error(self):
        r = self.ps(f"Get-FaitsSystemeJed -Dossier '{self.tmp}'")
        self.assertTrue(r["DockerInstalle"], "faux docker trouvé")
        self.assertTrue(r["DockerDemarre"])
        self.assertGreater(r["DisqueLibreGo"], 0)
        r = self.ps(f"Get-FaitsSystemeJed -Dossier '{self.tmp}'", docker_info=1)
        self.assertFalse(r["DockerDemarre"])


class NouvelleInstallationTests(AssistantTestCase):
    def installs(self):
        a, b = self.tmp / "parent" / "a", self.tmp / "parent" / "b"
        if not a.exists():
            self.make_install("parent/a", "jed-a", port=8000)
            self.make_install("parent/b", "jed-b", port=8001)
        return f"$i = @((Get-InstallationJed '{a}'), (Get-InstallationJed '{b}'));"

    def test_name_rules(self):
        cases = {
            "jed-c": True, "": False, "Jed": False, "jed é": False, "-jed": False, "a" * 41: False,
            "japon-explorateur": False, "jed-a": False, "jed-ancienne": False,
        }
        for nom, ok in cases.items():
            r = self.ps(self.installs() + f"Test-NomProjetJed -Nom '{nom}' -Installations $i "
                        "-Volumes @('jed-ancienne_db-data', 'autre_media')")
            self.assertEqual(r["Ok"], ok, (nom, r["Raison"]))

    def test_old_data_volumes_block_the_name(self):
        r = self.ps(self.installs() + "Test-NomProjetJed -Nom 'jed-ancienne' -Installations $i "
                    "-Volumes (Get-VolumesDockerJed)", volumes="jed-ancienne_db-data jed-ancienne_media")
        self.assertFalse(r["Ok"])
        self.assertIn("existent encore dans Docker", r["Raison"])

    def test_unknown_volumes_refuse_rather_than_risk(self):
        r = self.ps(self.installs() + "Test-NomProjetJed -Nom 'jed-c' -Installations $i -Volumes $null")
        self.assertFalse(r["Ok"])

    def test_port_of_another_installation_is_refused_and_next_free_port_is_proposed(self):
        r = self.ps(self.installs() + "Test-PortJed -Port 8001 -Installations $i -SansEcoute")
        self.assertFalse(r["Ok"])
        self.assertIn("jed-b", r["Raison"])
        self.assertEqual(self.ps(self.installs() + "Get-PortLibreJed -Installations $i"), 8002)
        self.assertFalse(self.ps("Test-PortJed -Port 80 -SansEcoute")["Ok"])

    def test_port_used_by_another_program_is_refused(self):
        code = ("$l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0); $l.Start(); "
                "$p = $l.LocalEndpoint.Port; $r = Test-PortJed -Port $p; $l.Stop(); $r")
        r = self.ps(code)
        self.assertFalse(r["Ok"])
        self.assertIn("autre programme", r["Raison"])

    def test_default_location_is_the_common_parent(self):
        r = self.ps(self.installs() + "Get-EmplacementParDefautJed -Installations $i -Nom 'jed-c' -Version '2.0.2'")
        self.assertEqual(Path(r), self.tmp / "parent" / "jed-c-2.0.2")
        r = self.ps("Get-EmplacementParDefautJed -Nom 'jed-c' -Version '2.0.2'")
        self.assertTrue(r.startswith("C:\\J-ed"), r)


class ArchiveTests(AssistantTestCase):
    def make_archive(self, version="2.0.2", script=b"# script de l'archive\r\n", hash_beside=True):
        archive = self.tmp / f"japon-explorateur-{version}.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(f"japon-explorateur-{version}/VERSION", f"{version}\n")
            z.writestr(f"japon-explorateur-{version}/mettre-a-jour.ps1", script)
        if hash_beside:
            Path(f"{archive}.sha256").write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
        return archive

    def test_hash_beside_the_archive_is_found_and_checked(self):
        a = self.make_archive()
        r = self.ps(f"Test-EmpreinteJed -Archive '{a}'")
        self.assertTrue(r["Ok"], r)
        self.assertEqual(r["Calculee"], hashlib.sha256(a.read_bytes()).hexdigest())

    def test_hash_elsewhere_or_wrong_or_missing(self):
        a = self.make_archive(hash_beside=False)
        r = self.ps(f"Test-EmpreinteJed -Archive '{a}'")
        self.assertFalse(r["Ok"])
        self.assertIn("sélectionnez-le", r["Raison"])
        ailleurs = self.tmp / "e.sha256"
        ailleurs.write_text(hashlib.sha256(a.read_bytes()).hexdigest() + "\n")
        self.assertTrue(self.ps(f"Test-EmpreinteJed -Archive '{a}' -Empreinte '{ailleurs}'")["Ok"])
        ailleurs.write_text("0" * 64 + "\n")
        r = self.ps(f"Test-EmpreinteJed -Archive '{a}' -Empreinte '{ailleurs}'")
        self.assertFalse(r["Ok"])
        self.assertIn("ne correspond pas", r["Raison"])

    def test_version_and_script_come_from_the_archive_unchanged(self):
        contenu = "\ufeff# script de l'archive, accentué\r\n".encode("utf-8")
        a = self.make_archive(script=contenu)
        self.assertEqual(self.ps(f"Get-VersionArchiveJed '{a}'"), "2.0.2")
        chemin = self.ps(f"Export-ScriptArchiveJed -Archive '{a}' -Dossier '{self.tmp / 'temp'}'")
        self.assertEqual(Path(chemin).read_bytes(), contenu, "octet pour octet (contrôle « script de l'archive »)")


class LancementTests(AssistantTestCase):
    def test_update_arguments_never_include_oui(self):
        r = self.ps("New-ArgumentsMiseAJourJed -Script 'C:\\T\\mettre-a-jour.ps1' -Archive 'C:\\A b\\j.zip' "
                    "-Actuel 'D:\\J ed\\' -DossierSauvegardes 'D:\\S' -Empreinte 'C:\\e.sha256' -Autres @('-Oui')")
        self.assertNotIn("-Oui", r)
        self.assertEqual(r[:5], ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:\\T\\mettre-a-jour.ps1"])
        self.assertIn("-Empreinte", r)

    def test_windows_quoting_of_paths(self):
        r = self.ps("Join-ArgumentsJed @('-File', 'C:\\A b\\x.ps1', 'D:\\J ed\\', 'sans', '', 'a\"b')")
        self.assertEqual(r, '-File "C:\\A b\\x.ps1" "D:\\J ed\\\\" sans "" "a\\"b"')

    def test_journal_state(self):
        j = self.tmp / "mise-a-jour.log"
        j.write_text("2026-11-23 12:00:00 ETAPE 6/7 Arrêt\r\n2026-11-23 12:00:01 QUESTION OUI pour arrêter\r\n",
                     encoding="utf-8")
        r = self.ps(f"Get-EtatJournalJed '{j}'")
        self.assertTrue(r["QuestionEnAttente"])
        self.assertEqual(r["Etape"], "6/7 Arrêt")
        with j.open("a", encoding="utf-8") as f:
            f.write("2026-11-23 12:00:05 REPONSE OUI\r\n2026-11-23 12:00:06 RESULTAT code=1\r\n    | ligne 2\r\n"
                    "2026-11-23 12:01:00 FIN code=0 mise à jour réussie\r\n")
        r = self.ps(f"Get-EtatJournalJed '{j}'")
        self.assertFalse(r["QuestionEnAttente"])
        self.assertEqual((r["Fin"], r["Code"], r["Resume"]), (True, 0, "mise à jour réussie"))
        lignes = self.ps(f"Read-JournalJed '{j}'")
        self.assertEqual(lignes[3]["Texte"], "code=1\nligne 2")

    def test_messages_for_every_contract_code(self):
        for code, niveau in [(0, "ok"), (1, "attention"), (2, "attention"), (3, "attention"), (4, "attention"),
                             (5, "erreur"), (9, "erreur")]:
            r = self.ps(f"Get-MessageMiseAJourJed {code}")
            self.assertEqual(r["Niveau"], niveau, code)
            self.assertTrue(r["Titre"] and r["Texte"])
        self.assertEqual(self.ps("Get-MessageVerificationJed 1")["Niveau"], "erreur")

    def test_common_docker_errors_are_explained(self):
        cases = {
            "error during connect: Get http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine": "docker-arrete",
            "Bind for 127.0.0.1:8000 failed: port is already allocated": "port",
            "write /var/lib/docker/x: no space left on device": "disque",
            "failed to solve: python:3.12: failed to resolve source metadata: context deadline exceeded": "internet",
            "docker : Le terme « docker » n'est pas reconnu": "docker-absent",
            "WSL 2 installation is incomplete.": "wsl",
        }
        for texte, cle in cases.items():
            r = self.ps(f"Convert-ErreurDockerJed @'\n{texte}\n'@")
            self.assertEqual(r["Cle"], cle, texte)
        self.assertIsNone(self.ps("Convert-ErreurDockerJed 'tout va bien'"))


class ScriptRunTests(AssistantTestCase):
    """Le vrai mettre-a-jour.ps1, lancé par l'assistant ; l'utilisateur répond à la question du journal."""

    def setUp(self):
        super().setUp()
        self.current = self.make_install("installation-2.0.1", "jed-essai", version="2.0.1")
        archive = self.tmp / "japon-explorateur-2.0.2.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("VERSION", "2.0.2\n")
            z.writestr("docker-compose.yml", "name: ${COMPOSE_PROJECT_NAME}\n")
        Path(f"{archive}.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "\n")
        self.archive = archive

    def run_update(self, reponse):
        code = (
            f"$a = New-ArgumentsMiseAJourJed -Script '{SCRIPT_MAJ}' -Archive '{self.archive}' -Actuel '{self.current}' "
            f"-DossierSauvegardes '{self.tmp / 'sauvegardes'}' -Autres @('-DelaiStabilite', '0'); "
            "$questions = New-Object System.Collections.Generic.List[string]; "
            f"$r = Invoke-ScriptJed -Moteur '{PWSH}' -Arguments $a "
            f"-SurQuestion {{ param($q) $questions.Add($q); ${'true' if reponse else 'false'} }}; "
            "[pscustomobject]@{ Code = $r.Code; Journal = $r.Journal; Questions = $questions.ToArray(); "
            "Etat = (Get-EtatJournalJed $r.Journal); Lignes = $r.Lignes }"
        )
        return self.ps(code, actuel=self.current)

    def test_user_says_oui_and_the_update_succeeds(self):
        r = self.run_update(True)
        self.assertEqual(r["Code"], 0, "\n".join(r["Lignes"]))
        self.assertEqual(r["Questions"], ["OUI pour arrêter l'ancienne version et démarrer la nouvelle"])
        self.assertEqual((r["Etat"]["Fin"], r["Etat"]["Code"]), (True, 0))
        calls = self.log.read_text().splitlines()
        self.assertTrue(any(c.endswith("| compose down") for c in calls))
        self.assertNotIn(SECRET_FICTIF, Path(r["Journal"]).read_text(encoding="utf-8"))

    def test_user_says_no_and_nothing_is_stopped(self):
        r = self.run_update(False)
        self.assertEqual(r["Code"], 2, "\n".join(r["Lignes"]))
        self.assertEqual(len(r["Questions"]), 1)
        calls = self.log.read_text().splitlines()
        self.assertTrue(any(c.endswith("| compose build") for c in calls), "question posée après la construction")
        self.assertFalse(any(c.endswith("| compose down") for c in calls))


class OperationsTests(AssistantTestCase):
    def test_actions_use_stop_and_never_remove_volumes(self):
        self.assertEqual(self.ps("Get-CommandeActionJed 'Arreter'"), ["compose", "stop"])
        self.assertEqual(self.ps("Get-CommandeActionJed 'Demarrer'"), ["compose", "up", "-d"])
        d = self.make_install("a", "jed-a", port=8003)
        self.assertEqual(self.ps(f"Get-AdresseJed (Get-InstallationJed '{d}')"), "http://localhost:8003/")

    def test_backup_is_copied_and_checked(self):
        sauvegardes = self.tmp / "sauvegardes"
        d = self.make_install("a", "jed-a", sauvegardes=str(sauvegardes))
        r = self.ps(f"Invoke-SauvegardeJed (Get-InstallationJed '{d}')", actuel=d)
        self.assertTrue(r["Ok"], r["Message"])
        self.assertEqual(Path(r["Copie"]).parent, sauvegardes)

    def test_failed_backup_is_reported(self):
        d = self.make_install("a", "jed-a", sauvegardes=str(self.tmp / "s"))
        r = self.ps(f"Invoke-SauvegardeJed (Get-InstallationJed '{d}')", actuel=d, backup="echec-130")
        self.assertFalse(r["Ok"])
        self.assertIn("La sauvegarde a échoué", r["Message"])

    def test_last_backup_reminder(self):
        s = self.tmp / "s"
        s.mkdir()
        d = self.make_install("a", "jed-a", sauvegardes=str(s))
        self.assertIsNone(self.ps(f"Get-DerniereSauvegardeJed (Get-InstallationJed '{d}')"))
        (s / "ancienne.tar").write_text("x")
        (s / "recente.tar").write_text("x")
        os.utime(s / "ancienne.tar", (0, 0))
        r = self.ps(f"Get-DerniereSauvegardeJed (Get-InstallationJed '{d}') -Maintenant ((Get-Date).AddDays(12))")
        self.assertEqual((Path(r["Fichier"]).name, r["Jours"], r["Texte"]), ("recente.tar", 12, "il y a 12 jours"))
        self.assertEqual(self.ps("Format-AncienneteJed 0"), "aujourd'hui")
