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
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
        env.update(FAKE_DOCKER_LOG=str(self.log), FAKE_ACTUEL=str(actuel),
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


class FenetreFileTests(SimpleTestCase):
    """2.0.2, lot 2 — la fenêtre (assistant-j-ed.ps1) et J-ed.cmd. L'affichage lui-même s'essaie sous Windows."""

    FENETRE = ROOT / "assistant" / "assistant-j-ed.ps1"
    CMD = ROOT / "J-ed.cmd"

    def test_window_script_is_bom_crlf_and_never_confirms_alone(self):
        data = self.FENETRE.read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        code = re.sub(r"<#.*?#>", "", data.decode("utf-8-sig"), flags=re.S)
        self.assertNotIn("-Oui", code)
        self.assertNotRegex(code, r"down -v|'-v'|--volumes")

    def test_cmd_launches_the_window_without_console(self):
        data = self.CMD.read_bytes()
        self.assertTrue(data.isascii(), "J-ed.cmd en ASCII (pas d'accent pour cmd.exe)")
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        texte = data.decode("ascii")
        self.assertIn('-ExecutionPolicy Bypass', texte)
        self.assertIn('-Sta', texte)
        self.assertIn('"%~dp0assistant\\assistant-j-ed.ps1"', texte)

    def test_scripts_parse_and_every_called_function_exists(self):
        if PWSH is None:
            self.skipTest("PowerShell (pwsh) absent")
        code = (
            "$e = $null; $t = $null; "
            f"$ast = [System.Management.Automation.Language.Parser]::ParseFile('{self.FENETRE}', [ref]$t, [ref]$e); "
            "if ($e.Count) { throw ($e | ForEach-Object { $_.Message + ' ligne ' + $_.Extent.StartLineNumber }) -join '; ' }; "
            "$definies = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) | ForEach-Object { $_.Name }); "
            "$appelees = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true) | "
            "ForEach-Object { $_.GetCommandName() } | Where-Object { $_ -like '*Jed' } | Sort-Object -Unique); "
            f"Import-Module '{MODULE}' -Force; $module = @(Get-Command -Module AssistantJed | ForEach-Object {{ $_.Name }}); "
            "@($appelees | Where-Object { $_ -notin $definies -and $_ -notin $module })"
        )
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "", "fonctions appelées mais définies nulle part")


class RaccourcisEtCompteRenduTests(AssistantTestCase):
    def test_shortcut_to_jed_uses_the_port_of_the_instance(self):
        d = self.make_install("a", "jed-essai-2", port=8002)
        bureau, menu = self.tmp / "Bureau", self.tmp / "Menu"
        r = self.ps(f"New-RaccourcisJed (Get-InstallationJed '{d}') '{d}' -Dossiers @('{bureau}', '{menu}')")
        self.assertEqual(sorted(Path(x).name for x in r), ["J-ed - jed-essai-2.url"] * 2)
        texte = (bureau / "J-ed - jed-essai-2.url").read_text(encoding="ascii")
        self.assertIn("URL=http://localhost:8002/", texte)

    def test_secrets_are_masked(self):
        texte = ("POSTGRES_PASSWORD=abc123 DJANGO_SECRET_KEY: \"zz9\" postgres://jed:motdepasse@db:5432/jed "
                 "contact prenom.nom@exemple.fr valeur-fictive-du-env")
        r = self.ps(f"Protect-TexteJed @'\n{texte}\n'@ @('valeur-fictive-du-env')")
        for secret in ("abc123", "zz9", "motdepasse", "prenom.nom@exemple.fr", "valeur-fictive-du-env"):
            self.assertNotIn(secret, r)
        self.assertIn("POSTGRES_PASSWORD=***", r)

    def test_report_contains_no_secret_and_no_env_file(self):
        sauvegardes = self.tmp / "sauvegardes"
        sauvegardes.mkdir()
        (sauvegardes / "mise-a-jour-20261123-120000.log").write_text(
            f"2026-11-23 12:00:00 INFO mot {SECRET_FICTIF} dans le journal\r\n", encoding="utf-8")
        d = self.make_install("a", "jed-a", sauvegardes=str(sauvegardes))
        logs = f"web-1 | connexion avec {SECRET_FICTIF} ; utilisateur auteur@exemple.org connecté"
        zip_path = self.ps(f"New-CompteRenduJed -Installation (Get-InstallationJed '{d}') -Destination '{self.tmp / 'bureau'}' "
                           "-VersionAssistant '2.0.2'", actuel=d, logs=logs)
        with zipfile.ZipFile(zip_path) as z:
            noms = z.namelist()
            contenu = "\n".join(z.read(n).decode("utf-8") for n in noms)
        self.assertIn("compte-rendu.txt", noms)
        self.assertIn("mise-a-jour-20261123-120000.log", noms)
        self.assertNotIn(".env", noms)
        self.assertNotIn(SECRET_FICTIF, contenu)
        self.assertNotIn("auteur@exemple.org", contenu)
        self.assertIn("Docker (moteur) : 29.9.3", contenu)
        self.assertIn("Nom : jed-a", contenu)

    def test_docker_from_the_window_runs_as_a_separate_process(self):
        """Avec -SurAttente, la commande Docker tourne à part (la fenêtre reste active) et rend le même résultat."""
        d = self.make_install("a", "jed-a")
        r = self.ps(f"$n = 0; $x = Invoke-DockerJed '{d}' @('compose', 'ps', '-a') -SurAttente {{ $n++ }}; $x", actuel=d)
        self.assertEqual(r["Code"], 0)
        self.assertIn("x-web-1", r["Texte"])
        self.assertTrue(self.log.read_text().splitlines()[-1].startswith(f"{d} | compose ps -a"), "dans le dossier")

    def test_verification_report_path_is_read(self):
        r = self.ps("Get-RapportVerificationJed @('…', 'Rapport enregistré : C:\\J-ed\\verification-j-ed-20261123-1200.txt')")
        self.assertEqual(r, "C:\\J-ed\\verification-j-ed-20261123-1200.txt")


class GitHubTests(AssistantTestCase):
    """Dernière version publiée : réponses de GitHub simulées par un petit serveur local."""

    def setUp(self):
        super().setUp()
        import http.server
        import threading

        self.site = self.tmp / "site"
        (self.site / "repos" / "x" / "y" / "releases").mkdir(parents=True)
        (self.site / "dl").mkdir()
        archive = self.site / "dl" / "japon-explorateur-2.0.2.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("japon-explorateur-2.0.2/VERSION", "2.0.2\n")
        (self.site / "dl" / "japon-explorateur-2.0.2.zip.sha256").write_text(
            f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
        site = str(self.site)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=site, **k)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def release(self, tag="2.0.2", assets=("japon-explorateur-2.0.2.zip", "japon-explorateur-2.0.2.zip.sha256")):
        data = {"tag_name": tag, "published_at": "2026-11-30T15:00:00Z", "assets": [
            {"name": n, "size": (self.site / "dl" / n).stat().st_size, "browser_download_url": f"{self.base}/dl/{n}"}
            for n in assets]}
        (self.site / "repos" / "x" / "y" / "releases" / "latest").write_text(json.dumps(data))

    def test_newer_release_is_found_downloaded_and_checked(self):
        self.release()
        info = self.ps(f"Get-DerniereVersionGitHubJed -Api '{self.base}' -Depot 'x/y'")
        self.assertTrue(info["Ok"], info)
        self.assertEqual(info["Version"], "2.0.2")
        self.assertEqual(self.ps("Compare-VersionJed '2.0.2' '2.0.1'"), 1)
        self.assertEqual(self.ps("Compare-VersionJed '2.0.1' '2.0.1'"), 0)
        self.assertEqual(self.ps("Compare-VersionJed 'v2.0.1' '2.0.2-apercu'"), -1)
        dossier = self.tmp / "Telechargements"
        r = self.ps(f"$i = Get-DerniereVersionGitHubJed -Api '{self.base}' -Depot 'x/y'; Save-DerniereVersionJed $i '{dossier}'")
        self.assertTrue(r["Ok"], r)
        self.assertEqual(Path(r["Archive"]).read_bytes(), (self.site / "dl" / "japon-explorateur-2.0.2.zip").read_bytes())

    def test_release_without_hash_file_is_refused(self):
        self.release(assets=("japon-explorateur-2.0.2.zip",))
        info = self.ps(f"Get-DerniereVersionGitHubJed -Api '{self.base}' -Depot 'x/y'")
        self.assertFalse(info["Ok"])
        self.assertIn("à la main", info["Raison"])

    def test_github_unreachable_gives_a_clear_reason(self):
        info = self.ps("Get-DerniereVersionGitHubJed -Api 'http://127.0.0.1:9' -Depot 'x/y'")
        self.assertFalse(info["Ok"])
        self.assertIn("GitHub ne répond pas", info["Raison"])


class ProxyTests(AssistantTestCase):
    def test_system_proxy_is_found(self):
        # PowerShell 7 sous Linux lit le proxy dans les variables d'environnement (au démarrage) ; Windows, dans
        # ses réglages (PAC compris).
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
        env.update(HTTPS_PROXY="http://proxy.exemple:3128", HTTP_PROXY="http://proxy.exemple:3128")
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                            f"Import-Module '{MODULE}'; Get-ProxySystemeJed"], capture_output=True, text=True,
                           timeout=60, env=env)
        self.assertEqual(r.stdout.strip(), "http://proxy.exemple:3128", r.stderr)

    def test_proxy_address_rules(self):
        self.assertTrue(self.ps("Test-AdresseProxyJed 'http://proxy.exemple:3128'")["Ok"])
        for mauvais in ("proxy:3128", "http://jean:secret@proxy:3128", ""):
            self.assertFalse(self.ps(f"Test-AdresseProxyJed '{mauvais}'")["Ok"], mauvais)

    def test_env_gets_the_proxy_and_keeps_everything_else(self):
        env = self.tmp / ".env"
        avant = "﻿COMPOSE_PROJECT_NAME=jed-a\r\nHTTP_PROXY=http://ancien:1\r\nPOSTGRES_PASSWORD=x\r\n"
        env.write_bytes(avant.encode("utf-8"))
        self.ps(f"Set-ProxyEnvJed -Fichier '{env}' -Proxy 'http://proxy.exemple:3128'")
        data = env.read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"), "BOM gardé")
        texte = data.decode("utf-8-sig")
        self.assertIn("COMPOSE_PROJECT_NAME=jed-a\r\n", texte)
        self.assertIn("POSTGRES_PASSWORD=x\r\n", texte)
        self.assertNotIn("ancien", texte)
        self.assertIn("HTTPS_PROXY=http://proxy.exemple:3128\r\n", texte)
        self.assertIn("NO_PROXY=localhost,127.0.0.1,db,redis,argos,ollama,web\r\n", texte)
        copies = list(self.tmp.glob(".env.avant-proxy-*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), avant.encode("utf-8"), "ancien .env gardé à côté")
        self.ps(f"Set-ProxyEnvJed -Fichier '{env}' -Proxy 'http://proxy.exemple:3128'")
        self.assertEqual(env.read_text(encoding="utf-8-sig").count("HTTPS_PROXY="), 1, "jamais en double")

    def test_env_never_gets_a_password(self):
        env = self.tmp / ".env"
        env.write_text("A=1\n")
        code = f"try {{ Set-ProxyEnvJed -Fichier '{env}' -Proxy 'http://jean:secret@proxy:3128'; 'ecrit' }} catch {{ 'refuse' }}"
        self.assertEqual(self.ps(code), "refuse")
        self.assertEqual(env.read_text(), "A=1\n")

    def test_compose_passes_the_proxy_empty_by_default(self):
        texte = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        for nom in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
            valeur = "${" + nom + ":-}"
            # arguments de construction (application et Argos, majuscules et minuscules), conteneurs Argos et Ollama
            self.assertEqual(texte.count(f"{nom}: {valeur}"), 4, nom)
            self.assertEqual(texte.count(f"{nom.lower()}: {valeur}"), 2, nom)
        self.assertIn("  env_file: .env\n", texte, "les conteneurs de J-ed reçoivent le .env")

    def test_numbers_are_written_the_french_way(self):
        self.assertEqual(self.ps("Format-NombreJed 15.94"), "15,9")
        self.assertEqual(self.ps("Format-NombreJed 16"), "16")

    def test_backup_already_copied_by_jed_is_not_copied_again(self):
        sauvegardes = self.tmp / "sauvegardes"
        sauvegardes.mkdir()
        (sauvegardes / "sauvegarde-20261114-220000-full.tar").write_bytes(b"contenu-fictif")
        d = self.make_install("a", "jed-a", sauvegardes=str(sauvegardes))
        r = self.ps(f"Invoke-SauvegardeJed (Get-InstallationJed '{d}')", actuel=d)
        self.assertTrue(r["Ok"], r["Message"])
        self.assertFalse(any("compose cp" in c for c in self.log.read_text().splitlines()))


class MaintenanceTests(AssistantTestCase):
    """2.0.2, lot 3 — mot de passe oublié, restauration, réinitialisation, nouvelle installation (arguments)."""

    def test_accounts_are_listed(self):
        d = self.make_install("a", "jed-a")
        r = self.ps(f"Get-ComptesJed (Get-InstallationJed '{d}')", actuel=d)
        self.assertTrue(r["Ok"], r)
        self.assertEqual(r["Comptes"][0]["identifiant"], "auteur-fictif")

    def test_password_goes_through_stdin_only(self):
        d = self.make_install("a", "jed-a")
        mot = "Nouveau-Mot-De-Passe-2026"
        r = self.ps(f"Set-MotDePasseJed (Get-InstallationJed '{d}') 'auteur-fictif' '{mot}'", actuel=d)
        self.assertTrue(r["Ok"], r)
        self.assertIn("Mot de passe changé pour « auteur-fictif »", r["Message"])
        self.assertEqual((self.tmp / "mot-recu").read_text(), mot, "reçu par l'entrée standard")
        self.assertNotIn(mot, self.log.read_text(), "jamais dans les arguments de la commande")

    def test_refused_password_is_reported_without_echoing_it(self):
        d = self.make_install("a", "jed-a")
        r = self.ps(f"Set-MotDePasseJed (Get-InstallationJed '{d}') 'auteur-fictif' 'Xy-123'", actuel=d)
        self.assertFalse(r["Ok"])
        self.assertIn("trop court", r["Message"])

    def test_restore_copies_restores_with_safety_backup_and_restarts(self):
        d = self.make_install("a", "jed-a")
        tar = self.tmp / "sauvegarde-20261120-100000-full.tar"
        tar.write_bytes(b"fictif")
        r = self.ps(f"Invoke-RestaurationJed (Get-InstallationJed '{d}') '{tar}'", actuel=d)
        self.assertTrue(r["Ok"], r)
        self.assertIn("sauvegarde-20261123-150000-full.tar", r["Securite"])
        calls = [c.split(" | ", 1)[1] for c in self.log.read_text().splitlines()]
        cp = next(i for i, c in enumerate(calls) if c.startswith("compose cp "))
        rest = next(i for i, c in enumerate(calls) if "restore_backup" in c)
        restart = calls.index("compose restart")
        self.assertLess(cp, rest)
        self.assertLess(rest, restart)
        self.assertFalse(any("--sans-securite" in c for c in calls), "jamais sans sauvegarde de sécurité")

    def test_failed_restore_mentions_the_safety_backup_and_does_not_restart(self):
        d = self.make_install("a", "jed-a")
        tar = self.tmp / "s.tar"
        tar.write_bytes(b"fictif")
        r = self.ps(f"Invoke-RestaurationJed (Get-InstallationJed '{d}') '{tar}'", actuel=d, restore="ko")
        self.assertFalse(r["Ok"])
        self.assertIn("Sauvegarde de sécurité faite juste avant", r["Message"])
        self.assertNotIn("compose restart", self.log.read_text())
        self.assertFalse(self.ps(f"Invoke-RestaurationJed (Get-InstallationJed '{d}') '{self.tmp / 'x.zip'}'")["Ok"])

    def test_reset_arguments_always_without_the_script_backup(self):
        r = self.ps("New-ArgumentsReinitialisationJed 'C:\\J\\reinitialiser-essai.ps1' -Complet")
        self.assertEqual(r[-2:], ["-SansSauvegarde", "-Complet"])

    def test_installation_arguments(self):
        r = self.ps("New-ArgumentsInstallationJed -Script 'C:\\T\\installer-j-ed.ps1' -Archive 'C:\\a.zip' "
                    "-Destination 'C:\\J-ed\\jed-2-2.0.2' -Nom 'jed-2' -Port 8003 -Proxy 'http://p:3128' -SansArgos")
        self.assertEqual(r[r.index("-Nom") + 1], "jed-2")
        self.assertEqual(r[r.index("-Port") + 1], "8003")
        self.assertIn("-SansArgos", r)
        for code, niveau in [(0, "ok"), (1, "attention"), (3, "attention"), (5, "erreur")]:
            self.assertEqual(self.ps(f"Get-MessageInstallationJed {code}")["Niveau"], niveau)

    def test_new_installation_through_the_assistant(self):
        """Le vrai installer-j-ed.ps1 lancé par l'assistant ; le journal d'installation est retrouvé."""
        archive = self.tmp / "japon-explorateur-2.0.2.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("j/VERSION", "2.0.2\n")
            z.writestr("j/docker-compose.yml", "name: x\n")
            z.writestr("j/.env.example", (ROOT / ".env.example").read_text(encoding="utf-8"))
        Path(f"{archive}.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "\n")
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        dest = self.tmp / "J-ed" / "jed-2-2.0.2"
        code = (f"$a = New-ArgumentsInstallationJed -Script '{ROOT / 'installer-j-ed.ps1'}' -Archive '{archive}' "
                f"-Destination '{dest}' -Nom 'jed-2' -Port {port} -DossierSauvegardes '{self.tmp / 's'}' "
                "-Autres @('-DelaiStabilite', '0'); "
                f"$r = Invoke-ScriptJed -Moteur '{PWSH}' -Arguments $a; "
                "[pscustomobject]@{ Code = $r.Code; Journal = $r.Journal; Fin = (Get-EtatJournalJed $r.Journal) }")
        r = self.ps(code)
        self.assertEqual(r["Code"], 0, r)
        self.assertTrue(Path(r["Journal"]).name.startswith("installation-"))
        self.assertEqual(r["Fin"]["Code"], 0)
        self.assertEqual(self.ps(f"(Get-InstallationJed '{dest}').Nom"), "jed-2")
