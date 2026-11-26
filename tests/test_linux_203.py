"""2.0.3, lots 1 à 3 — Linux : module de l'assistant, menu texte « jumeau » (assistant/menu-j-ed.ps1), lanceur j-ed.sh,
refus de root et droits du dossier des sauvegardes (installer-j-ed.ps1, verifier-j-ed.ps1).

Tout tourne avec PowerShell 7 sous Linux et le faux « docker » (tests/fixtures/mise_a_jour/docker). L'essai réel
se fait sur la machine virtuelle Ubuntu de l'utilisateur. Les tests tournent parfois en root : JED_UID_ACTUEL
simule l'utilisateur, JED_UID_CONTENEUR l'utilisateur du conteneur (réglages réservés aux tests).
"""
import hashlib
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
MODULE = ROOT / "assistant" / "AssistantJed.psm1"
MENU = ROOT / "assistant" / "menu-j-ed.ps1"
LANCEUR = ROOT / "j-ed.sh"
FAKE_DOCKER_DIR = ROOT / "tests" / "fixtures" / "mise_a_jour"
PWSH = shutil.which("pwsh") or ("/opt/pwsh/pwsh" if Path("/opt/pwsh/pwsh").exists() else None)
PROXY = "http://proxy.exemple.fr:8080"   # adresse fictive


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LinuxTestCase(SimpleTestCase):
    def setUp(self):
        if PWSH is None:
            self.skipTest("PowerShell (pwsh) absent")
        self.tmp = Path(tempfile.mkdtemp(prefix="linux-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "maison"
        self.home.mkdir()
        self.log = self.tmp / "docker.log"
        self.outils = self.tmp / "outils"   # faux gsettings, faux xdg-open
        self.outils.mkdir()

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy", "xdg_data_home")}
        env.update(HOME=str(self.home), TMPDIR=str(self.tmp), FAKE_DOCKER_LOG=str(self.log), FAKE_ACTUEL=str(self.tmp),
                   JED_UID_ACTUEL="1000", JED_UID_CONTENEUR=str(os.getuid()),
                   PATH=os.pathsep.join([str(self.outils), str(FAKE_DOCKER_DIR), os.environ.get("PATH", "")]))
        for k, v in extra.items():
            env[k if not k.startswith("fake_") else k.upper()] = str(v)
        return env

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def make_install(self, folder, name, port=8001, version="2.0.2", sauvegardes=None):
        d = self.tmp / folder
        d.mkdir(parents=True)
        (d / "docker-compose.yml").write_text("name: x\n")
        (d / "VERSION").write_text(f"{version}\n")
        env = f"COMPOSE_PROJECT_NAME={name}\nWEB_PORT={port}\nPOSTGRES_PASSWORD=mot-de-passe-fictif\n"
        if sauvegardes:
            env += f"DOSSIER_SAUVEGARDES={sauvegardes}\n"
        (d / ".env").write_text(env, encoding="utf-8")
        return d

    def gsettings(self, mode="manual", host="proxy.exemple.fr", port=8080):
        script = self.outils / "gsettings"
        script.write_text(
            "#!/bin/sh\n"
            f'case "$2 $3" in\n'
            f'  "org.gnome.system.proxy mode") echo "\'{mode}\'" ;;\n'
            f'  "org.gnome.system.proxy.https host"|"org.gnome.system.proxy.http host") echo "\'{host}\'" ;;\n'
            f'  "org.gnome.system.proxy.https port"|"org.gnome.system.proxy.http port") echo "{port}" ;;\n'
            '  *) echo "" ;;\n'
            "esac\n")
        script.chmod(0o755)


# --- Module -----------------------------------------------------------------------------------------------

class ModuleLinuxTests(LinuxTestCase):
    def ps(self, code, **env):
        full = ("$ErrorActionPreference = 'Stop'; "
                f"Import-Module '{MODULE}' -Force; $r = & {{ {code} }}; ConvertTo-Json -InputObject $r -Depth 6 -Compress")
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", full], capture_output=True, text=True,
                           timeout=120, env=self.env(**env))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stdout.strip().splitlines()
        return json.loads(out[-1]) if out else None

    def test_module_knows_it_runs_under_linux(self):
        self.assertTrue(self.ps("Test-LinuxJed"))
        self.assertTrue(self.ps("Get-MoteurPowerShellJed").endswith("pwsh"))
        self.assertEqual(self.ps("Get-UidJed"), 1000)

    def test_list_of_installations_lives_in_local_share(self):
        self.assertEqual(Path(self.ps("Get-FichierListeJed")), self.home / ".local" / "share" / "J-ed" / "installations.txt")
        autre = self.tmp / "donnees"
        self.assertEqual(Path(self.ps("Get-FichierListeJed", XDG_DATA_HOME=str(autre))), autre / "J-ed" / "installations.txt")

    def test_default_places_follow_decision_d5(self):
        self.assertEqual(Path(self.ps("Get-EmplacementParDefautJed -Nom 'jed' -Version '2.0.3'")),
                         self.home / "J-ed" / "jed-2.0.3")
        self.assertEqual(Path(self.ps("Get-DossierTelechargementsJed")).name, "J-ed")

    def test_proposed_name_skips_existing_ones(self):
        d = self.make_install("a", "jed")
        self.assertEqual(self.ps(f"Get-NomProposeJed 'jed' @(Get-InstallationJed '{d}') @()"), "jed-2")
        self.assertEqual(self.ps("Get-NomProposeJed 'jed' @() @()"), "jed")

    def faits(self, **changes):
        base = {"Linux": True, "Windows": False, "Bits64": True, "MemoireGo": 15.5, "Avx": True, "DockerInstalle": True,
                "DockerDemarre": True, "DockerDroits": True, "Root": False, "PowerShell": "'7.6.10'", "DisqueLibreGo": 100}
        base.update(changes)

        def lit(v):
            if v is None:
                return "$null"
            if isinstance(v, bool):
                return "$true" if v else "$false"
            return str(v)
        lignes = "; ".join(f"{k} = {lit(v)}" for k, v in base.items())
        return {c["Cle"]: c for c in self.ps(f"Test-PrerequisJed -Faits ([pscustomobject]@{{ {lignes} }})")}

    def test_linux_prerequisites(self):
        tout = self.faits()
        self.assertEqual({k: c["Niveau"] for k, c in tout.items()},
                         {k: "ok" for k in ("systeme", "memoire", "avx", "docker", "powershell", "disque")})
        self.assertTrue(all(c["Aide"].startswith("AVANT-DE-COMMENCER-LINUX.html#") for c in tout.values()))
        self.assertEqual(tout["docker"]["Libelle"], "Docker Engine")
        c = self.faits(DockerDroits=False, DockerDemarre=False)["docker"]
        self.assertEqual(c["Niveau"], "erreur")
        self.assertIn("sudo usermod -aG docker $USER", c["Conseil"])
        self.assertIn("sudo systemctl start docker", self.faits(DockerDemarre=False)["docker"]["Conseil"])
        self.assertEqual(self.faits(DockerInstalle=False, DockerDemarre=False)["docker"]["Niveau"], "erreur")
        self.assertEqual(self.faits(Root=True)["root"]["Niveau"], "erreur")
        self.assertEqual(self.faits(Avx=False)["avx"]["Niveau"], "attention")
        self.assertIn("host", self.faits(Avx=False)["avx"]["Conseil"])
        self.assertEqual(self.faits(PowerShell="'7.2.1'")["powershell"]["Niveau"], "attention")
        self.assertEqual(self.faits(MemoireGo=6)["memoire"]["Niveau"], "attention")
        self.assertEqual(self.faits(DisqueLibreGo=5)["disque"]["Niveau"], "erreur")

    def test_facts_under_linux(self):
        r = self.ps(f"Get-FaitsSystemeJed -Dossier '{self.tmp}'")
        self.assertTrue(r["Linux"])
        self.assertFalse(r["Root"])
        self.assertTrue(r["DockerDemarre"])
        self.assertTrue(r["DockerDroits"])
        self.assertIsNotNone(r["Avx"])
        self.assertGreater(r["MemoireGo"], 0)
        r = self.ps(f"Get-FaitsSystemeJed -Dossier '{self.tmp}'", fake_docker_info="droits")
        self.assertFalse(r["DockerDroits"])
        self.assertTrue(self.ps(f"(Get-FaitsSystemeJed -Dossier '{self.tmp}').Root", JED_UID_ACTUEL="0"))

    def test_docker_errors_explained_for_linux(self):
        def erreur(texte):
            return self.ps(f"Convert-ErreurDockerJed @'\n{texte}\n'@")
        r = erreur("permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock")
        self.assertEqual(r["Cle"], "droits")
        self.assertIn("usermod -aG docker", r["Solution"])
        r = erreur("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?")
        self.assertEqual(r["Cle"], "docker-arrete")
        self.assertIn("systemctl start docker", r["Solution"])
        self.assertNotIn("Docker Desktop", r["Explication"] + r["Solution"])
        r = erreur("failed to authorize: DeadlineExceeded: context deadline exceeded")
        self.assertEqual(r["Cle"], "internet")
        self.assertIn("/etc/docker/daemon.json", r["Solution"])
        conseil = self.ps(f"Get-ConseilProxyDockerJed '{PROXY}'")
        self.assertIn("/etc/docker/daemon.json", conseil)
        self.assertIn("sudo systemctl restart docker", conseil)

    def test_ubuntu_proxy_settings_are_found(self):
        self.assertIsNone(self.ps("Get-ProxySystemeJed"))
        self.gsettings()
        self.assertEqual(self.ps("Get-ProxySystemeJed"), PROXY)
        self.gsettings(host="http://proxy.exemple.fr/")
        self.assertEqual(self.ps("Get-ProxySystemeJed"), PROXY)
        self.gsettings(mode="none")
        self.assertIsNone(self.ps("Get-ProxySystemeJed"))
        # Le proxy du terminal passe avant celui des réglages.
        self.gsettings()
        self.assertEqual(self.ps("Get-ProxySystemeJed", HTTPS_PROXY="http://autre.exemple.fr:3128/"),
                         "http://autre.exemple.fr:3128")

    def test_windows_texts_are_kept(self):
        code = MODULE.read_text(encoding="utf-8-sig")
        self.assertIn("Docker Desktop n'est pas installé.", code)
        self.assertIn("Lancez Docker Desktop, attendez que la baleine soit immobile", code)
        self.assertIn("$base = $env:LOCALAPPDATA", code)
        self.assertIn("return 'powershell.exe'", code)


# --- Scripts : root et dossier des sauvegardes ----------------------------------------------------------

class ScriptsLinuxTests(LinuxTestCase):
    def archive(self, version="2.0.3", avec_installateur=False):
        archive = self.tmp / f"japon-explorateur-{version}.zip"
        exemple = (ROOT / ".env.example").read_text(encoding="utf-8")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(f"japon-explorateur-{version}/VERSION", f"{version}\n")
            z.writestr(f"japon-explorateur-{version}/docker-compose.yml", "name: ${COMPOSE_PROJECT_NAME}\n")
            z.writestr(f"japon-explorateur-{version}/.env.example", exemple)
        Path(f"{archive}.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + f"  {archive.name}\n")
        return archive

    def installer(self, **env):
        dest = self.tmp / "J-ed" / "jed-2.0.3"
        args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "installer-j-ed.ps1"),
                "-Archive", str(self.archive()), "-Destination", str(dest), "-Nom", "jed", "-Port", str(free_port()),
                "-DossierSauvegardes", str(self.tmp / "sauvegardes"), "-DelaiStabilite", "0", "-DelaiControle", "5"]
        return subprocess.run(args, capture_output=True, text=True, timeout=300, env=self.env(**env)), dest

    def test_installer_refuses_root(self):
        r, dest = self.installer(JED_UID_ACTUEL="0")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("en administrateur (sudo ou root)", r.stdout)
        self.assertFalse(dest.exists())
        self.assertFalse((self.tmp / "sauvegardes").exists(), "rien créé au nom de root")
        self.assertEqual(self.calls(), [])

    def test_installer_warns_when_the_container_cannot_write_backups(self):
        r, dest = self.installer(JED_UID_CONTENEUR="4242")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ne pourra pas écrire dans", r.stdout)
        self.assertIn("chmod o+rwx", r.stdout)
        journal = next((self.tmp / "sauvegardes").glob("installation-*.log")).read_text(encoding="utf-8")
        self.assertIn(" ATTENTION dossier des sauvegardes non accessible", journal)
        # Rien à signaler quand le conteneur peut écrire.
        shutil.rmtree(dest)
        shutil.rmtree(self.tmp / "sauvegardes")
        r, dest = self.installer()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("ne pourra pas écrire", r.stdout)

    def test_folder_rights_are_read_like_linux(self):
        d = self.tmp / "droits"
        d.mkdir()
        fonction = re.search(r"function Test-EcritureConteneur.*?\r?\n}\r?\n",
                             (ROOT / "installer-j-ed.ps1").read_text(encoding="utf-8-sig"), flags=re.S).group(0)

        def peut(mode, uid):
            os.chmod(d, mode)
            r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", f"{fonction}; Test-EcritureConteneur '{d}'"],
                               capture_output=True, text=True, timeout=60, env=self.env(JED_UID_CONTENEUR=str(uid)))
            return r.stdout.strip()
        moi = os.getuid()
        if moi == 0:   # en root (environnement de développement), le dossier est donné à un autre numéro
            os.chown(d, 4242, 4242)
            moi = 4242
        autre = moi + 1
        self.assertEqual(peut(0o755, moi), "True")
        self.assertEqual(peut(0o555, moi), "False")
        self.assertEqual(peut(0o755, autre), "False")
        self.assertEqual(peut(0o757, autre), "True")
        self.assertEqual(peut(0o777, autre), "True")
        self.assertEqual(peut(0o700, 0), "True", "root écrit partout")

    def verifier(self, **env):
        install = self.tmp / "installation"
        if not install.exists():
            self.make_install("installation", "jed-essai", sauvegardes=str(self.tmp / "sauvegardes"))
        (self.tmp / "sauvegardes").mkdir(exist_ok=True)
        args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "verifier-j-ed.ps1"), "-Dossier", str(install)]
        return subprocess.run(args, capture_output=True, text=True, timeout=300, env=self.env(**env))

    def test_verification_refuses_root_and_flags_unwritable_backups(self):
        r = self.verifier(JED_UID_ACTUEL="0")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("en administrateur (sudo ou root)", r.stdout)
        r = self.verifier(JED_UID_CONTENEUR="4242")
        self.assertIn("[À surveiller] Dossier des sauvegardes", r.stdout)
        self.assertIn("ne peut pas y écrire", r.stdout)
        self.assertIn("chmod o+rwx", r.stdout)


    # 2.0.3 (avant la version définitive, accord de l'utilisateur du 26/11) : le .env est réservé au compte.
    def test_installer_keeps_env_for_the_user_only(self):
        r, dest = self.installer()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(stat.S_IMODE((dest / ".env").stat().st_mode), 0o600)

    def test_verification_flags_an_env_readable_by_others(self):
        self.make_install("installation", "jed-essai", sauvegardes=str(self.tmp / "sauvegardes"))
        env = self.tmp / "installation" / ".env"
        env.chmod(0o644)
        r = self.verifier()
        self.assertIn("[À surveiller] Fichier .env : lisible par d'autres comptes", r.stdout)
        self.assertIn(f'chmod 600 "{env}"', r.stdout)
        env.chmod(0o600)
        r = self.verifier()
        self.assertNotIn("lisible par d'autres comptes", r.stdout)


# --- Lanceur j-ed.sh ----------------------------------------------------------------------------------------

class LanceurTests(LinuxTestCase):
    def test_file_is_a_bash_script_with_unix_line_endings(self):
        data = LANCEUR.read_bytes()
        self.assertTrue(data.startswith(b"#!/usr/bin/env bash\n"))
        self.assertNotIn(b"\r", data)
        self.assertEqual(subprocess.run(["bash", "-n", str(LANCEUR)]).returncode, 0)
        mode = subprocess.run(["git", "ls-files", "-s", "j-ed.sh"], cwd=ROOT, capture_output=True, text=True).stdout
        if mode:   # dépôt git présent (environnement de développement, GitHub)
            self.assertTrue(mode.startswith("100755"), "exécutable dans le dépôt")

    def test_refuses_root(self):
        r = subprocess.run(["bash", str(LANCEUR)], capture_output=True, text=True, timeout=60,
                           env=self.env(JED_UID_ACTUEL="0"), input="0\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("sans sudo", r.stderr)

    def test_explains_missing_powershell(self):
        # PATH réduit aux seuls outils du lanceur (pwsh est parfois dans /usr/bin, comme sur GitHub).
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        for outil in ("readlink", "dirname", "id"):
            (bin_ / outil).symlink_to(shutil.which(outil))
        env = self.env()
        env["PATH"] = str(bin_)
        r = subprocess.run([shutil.which("bash"), str(LANCEUR)], capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("PowerShell 7 n'est pas installé", r.stderr)

    def test_starts_the_menu(self):
        r = subprocess.run(["bash", str(LANCEUR)], capture_output=True, text=True, timeout=120, env=self.env(), input="0\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("J-ed — Assistant (Linux)", r.stdout)
        self.assertIn("Au revoir.", r.stdout)


# --- Menu texte -------------------------------------------------------------------------------------------

class MenuTests(LinuxTestCase):
    MENU_ACCUEIL = ["1. Mettre à jour une installation", "2. Nouvelle installation", "3. Démarrer", "4. Arrêter",
                    "5. Ouvrir J-ed", "6. Vérifier", "7. Créer les raccourcis", "8. Ajouter une installation…",
                    "9. Voir les prérequis", "10. Opérations de maintenance", "11. Ça ne marche pas",
                    "12. Aide : avant de commencer", "0. Fermer"]

    def menu(self, *reponses, **env):
        entree = "".join(f"{r}\n" for r in reponses)
        r = subprocess.run([PWSH, "-NoProfile", "-File", str(MENU)], capture_output=True, text=True, timeout=300,
                           env=self.env(**env), input=entree)
        self.sortie = r.stdout
        return r

    def liste(self):
        return self.home / ".local" / "share" / "J-ed" / "installations.txt"

    def ajouter(self, *dossiers):
        self.liste().parent.mkdir(parents=True, exist_ok=True)
        self.liste().write_text("".join(f"{d}\n" for d in dossiers), encoding="utf-8")

    def test_home_screen_is_the_twin_of_the_windows_window(self):
        r = self.menu("0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        menu = self.sortie[self.sortie.index("Prérequis :"):]
        positions = [menu.index(item) for item in self.MENU_ACCUEIL]
        self.assertEqual(positions, sorted(positions), "même ordre que la fenêtre Windows")
        self.assertIn("aucune pour l'instant", self.sortie)
        # Selon la machine des tests (place sur le disque…), « prêt » avec ou sans points à surveiller.
        self.assertRegex(self.sortie, r"Prérequis : (tout est prêt\.|prêt, \d+ point)")
        # Mêmes libellés que les boutons de la fenêtre Windows.
        fenetre = (ROOT / "assistant" / "assistant-j-ed.ps1").read_text(encoding="utf-8-sig")
        for libelle in ("Mettre à jour une installation", "Nouvelle installation", "Démarrer", "Arrêter", "Ouvrir J-ed",
                        "Vérifier", "Créer les raccourcis", "Ajouter une installation…", "Voir les prérequis",
                        "Opérations de maintenance", "Ça ne marche pas", "Aide : avant de commencer", "Fermer",
                        "Créer une sauvegarde", "Dossier des sauvegardes", "Restaurer une sauvegarde",
                        "Mot de passe oublié", "Vérifier la migration", "Réinitialiser l''essai"):
            self.assertIn(f"'{libelle}'", fenetre, libelle)

    def test_refuses_root_and_ends_cleanly_without_input(self):
        r = self.menu(JED_UID_ACTUEL="0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("sans sudo", self.sortie)
        r = self.menu()   # aucune réponse : fin propre, pas de boucle sans fin
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Fin de l'assistant.", self.sortie)

    def test_lists_installations_and_starts_or_stops_the_chosen_one(self):
        a = self.make_install("jed-a-2.0.2", "jed-a", port=8001)
        b = self.make_install("jed-b-2.0.2", "jed-b", port=8002)
        self.ajouter(a, b)
        r = self.menu("3", "2", "", "4", "1", "", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(self.sortie, r"\[1\] jed-a\s+2\.0\.2\s+port 8001")
        self.assertRegex(self.sortie, r"\[2\] jed-b\s+2\.0\.2\s+port 8002")
        self.assertIn(f"{b} | compose up -d", self.calls())
        self.assertIn(f"{a} | compose stop", self.calls())
        self.assertFalse(any("down" in c for c in self.calls()), "Arrêter = stop, jamais down")
        self.assertIn("J-ed est arrêté. Ses données sont intactes.", self.sortie)

    def test_open_needs_a_running_installation(self):
        a = self.make_install("jed-a-2.0.2", "jed-a", port=8001)
        self.ajouter(a)
        self.menu("5", "", "0")
        self.assertIn("est arrêtée : choisissez d'abord « 3. Démarrer »", self.sortie)
        ls = json.dumps([{"Name": "jed-a", "Status": "running(8)", "ConfigFiles": str(a / "docker-compose.yml")}])
        ouvert = self.tmp / "ouvert.txt"
        xdg = self.outils / "xdg-open"
        xdg.write_text(f'#!/bin/sh\necho "$1" > "{ouvert}"\n')
        xdg.chmod(0o755)
        self.menu("5", "", "0", fake_compose_ls=ls)
        self.assertIn("http://localhost:8001/", self.sortie)
        for _ in range(50):
            if ouvert.exists():
                break
            subprocess.run(["sleep", "0.1"])
        self.assertEqual(ouvert.read_text().strip(), "http://localhost:8001/")

    def test_prerequisites_give_the_linux_advice(self):
        self.menu("9", "", "0", fake_docker_info="droits")
        self.assertIn("[Problème] Docker Engine", self.sortie)
        self.assertIn("sudo usermod -aG docker $USER", self.sortie)
        self.assertIn("point(s) à régler avant d'installer", self.sortie)

    def test_new_installation_stops_when_prerequisites_are_missing(self):
        self.menu("2", "", "0", fake_docker_info="1")
        self.assertIn("Des prérequis ne sont pas remplis", self.sortie)
        self.assertIn("sudo systemctl start docker", self.sortie)

    def test_help_opens_the_linux_guide(self):
        """Lot 4 : « 12. Aide » ouvre AVANT-DE-COMMENCER-LINUX.html (xdg-open), et l'adresse est affichée."""
        recu = self.tmp / "ouvert.txt"
        outil = self.outils / "xdg-open"
        outil.write_text(f"#!/bin/sh\necho \"$1\" >> '{recu}'\n")
        outil.chmod(0o755)
        self.menu("12", "", "0")
        page = ROOT / "AVANT-DE-COMMENCER-LINUX.html"
        self.assertIn(str(page), self.sortie)
        for _ in range(50):   # xdg-open est lancé sans attendre
            if recu.exists():
                break
            time.sleep(0.1)
        self.assertEqual(recu.read_text().strip(), str(page))
        self.assertNotIn("arrive avec le lot", MENU.read_text(encoding="utf-8-sig"))

    def test_add_installation(self):
        self.menu("8", str(self.tmp / "nulle-part"), "", "0")
        self.assertIn("Dossier non ajouté", self.sortie)
        a = self.make_install("jed-a-2.0.2", "jed-a")
        self.menu("8", str(a), "", "0")
        self.assertIn("Installation « jed-a » ajoutée", self.sortie)
        self.assertEqual(self.liste().read_text(encoding="utf-8").split(), [str(a)])

    def test_backup_is_copied_into_the_backups_folder(self):
        sauv = self.tmp / "sauvegardes-jed-a"
        a = self.make_install("jed-a-2.0.2", "jed-a", sauvegardes=str(sauv))
        self.ajouter(a)
        r = self.menu("10", "1", "", "0", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Sauvegarde faite", self.sortie)
        self.assertTrue((sauv / "sauvegarde-20261114-220000-full.tar").exists())
        self.assertIn("sauvegarde : aujourd'hui", self.sortie)

    def test_verification_runs_the_installation_script(self):
        a = self.make_install("jed-a-2.0.2", "jed-a")
        self.ajouter(a)
        recu = self.tmp / "arguments.txt"
        (a / "verifier-j-ed.ps1").write_text(
            "param([string]$Dossier, [switch]$AvecSources, [switch]$AvecTests)\n"
            f"\"$Dossier|$AvecTests|$AvecSources\" | Set-Content '{recu}'\n"
            "Write-Host '[OK] Conteneurs : en service'\nWrite-Host 'Rapport enregistré : /tmp/rapport-fictif.txt'\nexit 0\n",
            encoding="utf-8")
        r = self.menu("6", "o", "n", "", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(recu.read_text().strip(), f"{a}|True|False")
        self.assertIn("[OK] Conteneurs : en service", self.sortie)
        self.assertIn("Tout va bien", self.sortie)
        self.assertIn("Rapport : /tmp/rapport-fictif.txt", self.sortie)

    def archive(self, version="2.0.3"):
        archive = self.tmp / "telechargements" / f"japon-explorateur-{version}.zip"
        archive.parent.mkdir()
        exemple = (ROOT / ".env.example").read_text(encoding="utf-8")
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(f"japon-explorateur-{version}/VERSION", f"{version}\n")
            z.writestr(f"japon-explorateur-{version}/docker-compose.yml", "name: ${COMPOSE_PROJECT_NAME}\n")
            z.writestr(f"japon-explorateur-{version}/.env.example", exemple)
        Path(f"{archive}.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + f"  {archive.name}\n")
        return archive

    def test_new_installation_from_start_to_end(self):
        """Comme la fenêtre Windows : proxy, archive et empreinte, nom, port, emplacement, sauvegardes, Argos,
        « Docker joint-il Internet ? », récapitulatif, installation par installer-j-ed.ps1, fin guidée."""
        archive = self.archive()
        self.gsettings()   # proxy réglé dans Ubuntu : proposé d'office
        port = free_port()
        r = self.menu("2",
                      "",              # utiliser le proxy trouvé
                      "2", str(archive),  # archive déjà téléchargée (empreinte trouvée à côté)
                      "",              # nom proposé : jed
                      str(port),
                      "",              # emplacement proposé : ~/J-ed/jed-2.0.3
                      "",              # sauvegardes proposées : ~/J-ed/sauvegardes-jed
                      "n",             # sans Argos
                      "",              # Docker joint-il Internet ? oui
                      "",              # Installer ? oui
                      "2", "0",        # fin guidée : jeu d'essai, puis terminé
                      "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dest = self.home / "J-ed" / "jed-2.0.3"
        self.assertIn(f"Proxy trouvé dans les réglages : {PROXY}", self.sortie)
        self.assertIn("Archive de la version 2.0.3 : empreinte conforme.", self.sortie)
        self.assertIn("pull python:3.12-slim-bookworm", "\n".join(self.calls()))
        self.assertIn("OK — Installation réussie", self.sortie)
        self.assertIn("Jeu d'essai chargé", self.sortie)
        valeurs = dict(l.split("=", 1) for l in (dest / ".env").read_text(encoding="utf-8").splitlines()
                       if re.match(r"^[A-Z_]+=", l))
        self.assertEqual(valeurs["COMPOSE_PROJECT_NAME"], "jed")
        self.assertEqual(valeurs["WEB_PORT"], str(port))
        self.assertEqual(valeurs["HTTPS_PROXY"], PROXY)
        self.assertEqual(valeurs["COMPOSE_PROFILES"], "")
        self.assertEqual(Path(valeurs["DOSSIER_SAUVEGARDES"]), self.home / "J-ed" / "sauvegardes-jed")
        self.assertIn(str(dest), self.liste().read_text(encoding="utf-8"))
        # La construction a vu le proxy (commande docker, essai réel du 26/11).
        proxy = (self.tmp / "proxy.log").read_text().splitlines()
        self.assertIn(f"compose build | {PROXY}", proxy)

    def test_menu_file_format(self):
        data = MENU.read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        code = re.sub(r"<#.*?#>", "", data.decode("utf-8-sig"), flags=re.S)
        self.assertIn("Import-Module ([System.IO.Path]::Combine($PSScriptRoot, 'AssistantJed.psm1'))", code)
        self.assertNotRegex(code, r"'down'|down -v|'-v'|--volumes|'-Oui'")


# --- Lot 2 : mise à jour sûre sous Linux --------------------------------------------------------------------

class MiseAJourLinuxTests(LinuxTestCase):
    """2.0.3, lot 2 — « 1. Mettre à jour une installation » du menu, et mettre-a-jour.ps1 sous Linux."""

    def setUp(self):
        super().setUp()
        from tests.test_mise_a_jour_ps1 import compose_build_args
        self.build_args = " ".join(compose_build_args())
        self.sauv = self.tmp / "sauvegardes-jed-essai"
        self.install = self.make_install("jed-essai-2.0.2", "jed-essai", port=8001, sauvegardes=str(self.sauv))
        self.liste = self.home / ".local" / "share" / "J-ed" / "installations.txt"
        self.liste.parent.mkdir(parents=True)
        self.liste.write_text(f"{self.install}\n", encoding="utf-8")
        self.en_marche = json.dumps([{"Name": "jed-essai", "Status": "running(8)",
                                      "ConfigFiles": str(self.install / "docker-compose.yml")}])

    def archive(self, version="2.0.3", avec_script=True):
        archive = self.tmp / "telechargements" / f"japon-explorateur-{version}.zip"
        archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive, "w") as z:
            racine = f"japon-explorateur-{version}/"
            z.writestr(racine + "VERSION", f"{version}\n")
            z.writestr(racine + "docker-compose.yml", "name: ${COMPOSE_PROJECT_NAME}\n")
            if avec_script:
                z.writestr(racine + "mettre-a-jour.ps1", (ROOT / "mettre-a-jour.ps1").read_bytes())
        Path(f"{archive}.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + f"  {archive.name}\n")
        return archive

    def menu(self, *reponses, **env):
        env.setdefault("fake_compose_ls", self.en_marche)
        entree = "".join(f"{r}\n" for r in reponses)
        r = subprocess.run([PWSH, "-NoProfile", "-File", str(MENU)], capture_output=True, text=True, timeout=600,
                           env=self.env(FAKE_ACTUEL=str(self.install), FAKE_BUILD_ARGS=self.build_args, **env),
                           input=entree)
        self.sortie = r.stdout
        return r

    def mise_a_jour(self, *apres_archive, archive=None, avant_archive=("",), **env):
        """1 Mettre à jour ; proxy ; 2 archive locale ; puis les réponses suivantes ; enfin retour et Fermer."""
        archive = archive or self.archive()
        return self.menu("1", *avant_archive, "2", str(archive), *apres_archive, "", "0", **env)

    def nouveau(self):
        return self.tmp / "japon-explorateur-2.0.3"

    def test_update_through_the_menu(self):
        # sauvegardes : proposé ; Docker joint Internet : oui ; confirmation de la nouvelle version : o
        r = self.mise_a_jour("", "", "o")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Archive de la version 2.0.3 : empreinte conforme.", self.sortie)
        self.assertIn("La nouvelle version est prête.", self.sortie)
        self.assertIn("Confirmation donnée dans l'assistant J-ed (réponse « oui »).", self.sortie)
        self.assertIn("OK — Mise à jour réussie", self.sortie)
        self.assertIn(f"Nouvelle version dans : {self.nouveau()}", self.sortie)
        appels = self.calls()
        construction = appels.index(f"{self.nouveau()} | compose build")
        arret = next(i for i, c in enumerate(appels) if c == f"{self.install} | compose down")
        self.assertLess(construction, arret, "construction AVANT l'arrêt de l'ancienne version")
        self.assertFalse(any(" -v" in c or "--volumes" in c for c in appels))
        self.assertIn(str(self.nouveau()), self.liste.read_text(encoding="utf-8"))
        journal = next(self.sauv.glob("mise-a-jour-*.log")).read_text(encoding="utf-8")
        self.assertIn(" QUESTION ", journal)
        self.assertIn(" REPONSE OUI", journal)
        self.assertTrue(journal.rstrip().endswith("FIN code=0 mise à jour réussie"), journal[-300:])
        self.assertTrue(any(self.sauv.glob("sauvegarde-*.tar")), "sauvegarde copiée avant la mise à jour")
        self.assertEqual(stat.S_IMODE((self.nouveau() / ".env").stat().st_mode), 0o600, ".env réservé au compte")

    def test_existing_shortcuts_follow_the_new_version(self):
        applications = self.home / ".local" / "share" / "applications"
        applications.mkdir(parents=True)
        ancien = applications / "j-ed-jed-essai.desktop"
        ancien.write_text("[Desktop Entry]\nName=ancien\n", encoding="utf-8")
        r = self.mise_a_jour("", "", "o", "o")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Mettre à jour les raccourcis « J-ed » du menu Applications ?", self.sortie)
        self.assertIn("Raccourcis mis à jour", self.sortie)
        self.assertIn("Name=J-ed - jed-essai", ancien.read_text(encoding="utf-8"))

    def test_refusing_keeps_the_old_version(self):
        r = self.mise_a_jour("", "", "n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Mise à jour annulée", self.sortie)
        self.assertNotIn(f"{self.install} | compose down", self.calls())

    def test_build_failure_explains_and_names_the_folder_to_remove(self):
        r = self.mise_a_jour("", "", fake_build="1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Nouvelle version impossible à préparer", self.sortie)
        self.assertIn("/etc/docker/daemon.json", self.sortie)
        self.assertIn("supprimez ce dossier (par exemple dans l'application Fichiers)", self.sortie)
        self.assertIn(str(self.nouveau()), self.sortie)
        self.assertNotIn(f"{self.install} | compose down", self.calls())

    def test_stopped_installation_is_started_first(self):
        r = self.mise_a_jour("", "", "n", avant_archive=("o", ""), fake_compose_ls="[]")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("est arrêtée. Elle doit être en marche", self.sortie)
        self.assertIn(f"{self.install} | compose up -d", self.calls())

    def test_protected_installation_is_warned_before_anything_is_written(self):
        protegee = self.make_install("essai-protege", "japon-explorateur-essai", port=8005)
        with open(protegee / ".env", "a", encoding="utf-8") as f:
            f.write("AUTORISER_NOM_PROJET=japon-explorateur-essai\n")
        self.liste.write_text(f"{protegee}\n", encoding="utf-8")
        avant = (protegee / ".env").read_text(encoding="utf-8")
        self.gsettings()
        r = self.menu("1", "", "2", str(self.archive()), "", "", "n", "", "0", fake_compose_ls=json.dumps(
            [{"Name": "japon-explorateur-essai", "Status": "running(8)", "ConfigFiles": str(protegee / "docker-compose.yml")}]))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("installation protégée", self.sortie)
        self.assertEqual((protegee / ".env").read_text(encoding="utf-8"), avant, ".env non touché")
        self.assertFalse(any("compose build" in c for c in self.calls()))

    def test_proxy_is_written_in_env_then_given_to_docker(self):
        self.gsettings()
        # proxy proposé : oui ; …, écrire le proxy dans .env : oui ; confirmation : o
        r = self.mise_a_jour("", "", "", "o")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"Le proxy {PROXY} va être écrit dans le fichier .env", self.sortie)
        texte = (self.install / ".env").read_text(encoding="utf-8")
        self.assertIn(f"HTTPS_PROXY={PROXY}", texte)
        self.assertTrue(list(self.install.glob(".env.avant-proxy-*")), "copie de l'ancien .env gardée")
        self.assertIn(f"HTTPS_PROXY={PROXY}", (self.nouveau() / ".env").read_text(encoding="utf-8"))
        self.assertIn(f"compose build | {PROXY}", (self.tmp / "proxy.log").read_text().splitlines())
        self.assertIn("OK — Mise à jour réussie", self.sortie)

    def test_archive_without_update_script_is_refused(self):
        r = self.mise_a_jour("", "", archive=self.archive(avec_script=False))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("mettre-a-jour.ps1 est absent de l'archive", self.sortie)
        self.assertFalse(any("backup" in c for c in self.calls()))

    def script(self, **env):
        args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "mettre-a-jour.ps1"), "-Archive",
                str(self.archive()), "-Actuel", str(self.install), "-DossierSauvegardes", str(self.sauv), "-Oui",
                "-DelaiStabilite", "0"]
        return subprocess.run(args, capture_output=True, text=True, timeout=300,
                              env=self.env(FAKE_ACTUEL=str(self.install), FAKE_BUILD_ARGS=self.build_args, **env))

    def test_update_script_refuses_root(self):
        r = self.script(JED_UID_ACTUEL="0")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("en administrateur (sudo ou root)", r.stdout)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.sauv.exists(), "rien créé au nom de root")

    def test_update_script_warns_when_the_container_cannot_write_backups(self):
        r = self.script(JED_UID_CONTENEUR="4242")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ne pourra pas écrire dans", r.stdout)
        journal = next(self.sauv.glob("mise-a-jour-*.log")).read_text(encoding="utf-8")
        self.assertIn(" ATTENTION Attention : J-ed (utilisateur 1000", journal)


class ArchivesEssaiTests(LinuxTestCase):
    """2.0.3, lot 2 : outil de recette tests/outils/archives-essai.ps1 (trois archives d'essai de la mise à jour)."""

    OUTIL = ROOT / "tests" / "outils" / "archives-essai.ps1"

    def fabriquer(self):
        source = self.tmp / "code"
        (source / "docker").mkdir(parents=True)
        (source / ".git").mkdir()
        (source / "__pycache__").mkdir()
        (source / "docker-compose.yml").write_text("name: essai\n", encoding="utf-8")
        (source / "VERSION").write_text("2.0.2\n", encoding="utf-8")
        (source / ".env").write_text("SECRET_KEY=fictive\n", encoding="utf-8")
        (source / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
        (source / "__pycache__" / "x.pyc").write_bytes(b"\0")
        (source / "docker" / "Dockerfile").write_text("FROM python:3.12-slim-bookworm\r\nRUN pip install x\r\n",
                                                       encoding="utf-8")
        (source / "docker" / "entrypoint.sh").write_text("#!/bin/sh\nset -e\necho suite\nexec \"$@\"\n",
                                                         encoding="utf-8")
        lanceur = source / "j-ed.sh"
        lanceur.write_text("#!/bin/sh\n", encoding="utf-8")
        lanceur.chmod(0o755)
        sortie = self.tmp / "archives"
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(self.OUTIL), "-Source", str(source),
                            "-Version", "2.0.3", "-Sortie", str(sortie)], capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return sortie

    def lire(self, sortie, suffixe):
        chemin = sortie / f"japon-explorateur-2.0.3-essai{suffixe}.zip"
        attendu = (sortie / f"{chemin.name}.sha256").read_text(encoding="utf-8").split()
        self.assertEqual(attendu, [hashlib.sha256(chemin.read_bytes()).hexdigest(), chemin.name])
        z = zipfile.ZipFile(chemin)
        noms = z.namelist()
        self.assertEqual({n.split("/")[0] for n in noms}, {"japon-explorateur-2.0.3"})   # un seul dossier racine
        relatifs = {n.split("/", 1)[1] for n in noms}
        self.assertNotIn(".env", relatifs)
        self.assertFalse([n for n in relatifs if n.startswith(".git/") or "__pycache__" in n])
        self.assertEqual(z.read("japon-explorateur-2.0.3/VERSION"), b"2.0.3\n")
        self.assertEqual((z.getinfo("japon-explorateur-2.0.3/j-ed.sh").external_attr >> 16) & 0o777, 0o755)
        return z, relatifs

    def test_three_archives(self):
        sortie = self.fabriquer()
        z, relatifs = self.lire(sortie, "")
        self.assertNotIn("ESSAI-LISEZMOI.txt", relatifs)
        self.assertEqual(z.read("japon-explorateur-2.0.3/docker/Dockerfile"),
                         b"FROM python:3.12-slim-bookworm\r\nRUN pip install x\r\n")   # archive normale intacte

        z, relatifs = self.lire(sortie, "-construction-impossible")
        self.assertIn("ESSAI-LISEZMOI.txt", relatifs)
        dockerfile = z.read("japon-explorateur-2.0.3/docker/Dockerfile").decode()
        self.assertTrue(dockerfile.startswith("FROM python:3.12-slim-bookworm\nRUN pip install x\n"))
        self.assertTrue(dockerfile.rstrip().endswith("&& exit 1"))   # après pip : le cache de pip sert

        z, relatifs = self.lire(sortie, "-demarrage-impossible")
        self.assertIn("ESSAI-LISEZMOI.txt", relatifs)
        script = self.tmp / "entrypoint.sh"
        script.write_bytes(z.read("japon-explorateur-2.0.3/docker/entrypoint.sh"))
        web = subprocess.run(["sh", str(script), "gunicorn", "config.wsgi:application"], capture_output=True, text=True)
        self.assertEqual(web.returncode, 1)
        self.assertIn("démarrage impossible volontaire", web.stderr)
        autre = subprocess.run(["sh", str(script), "true"], capture_output=True, text=True)
        self.assertEqual((autre.returncode, autre.stdout), (0, "suite\n"))   # les autres services démarrent

    def test_tool_is_bom_crlf(self):
        brut = self.OUTIL.read_bytes()
        self.assertTrue(brut.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", brut.replace(b"\r\n", b""))


class DossierTemporaireTests(LinuxTestCase):
    """2.0.3, lot 2 : sous Linux, /tmp est commun à tous les comptes ; l'assistant y a son propre dossier."""

    def test_temp_folder_is_per_user(self):
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                            f"Import-Module '{MODULE}'; Get-DossierTemporaireJed 'mise-a-jour-1'"],
                           capture_output=True, text=True, timeout=120, env=self.env(JED_UID_ACTUEL="4242"))
        self.assertEqual(r.returncode, 0, r.stderr)
        # Numéro RÉEL du compte, pas celui que simulent les tests (le dossier doit lui appartenir).
        self.assertEqual(r.stdout.strip(), str(self.tmp / f"J-ed-{os.getuid()}" / "mise-a-jour-1"))
        self.assertNotIn("GetTempPath(), 'J-ed'", MENU.read_text(encoding="utf-8-sig"))


# --- Lot 3 : maintenance, raccourcis, « Ça ne marche pas » --------------------------------------------------

class MaintenanceLinuxTests(LinuxTestCase):
    """2.0.3, lot 3 — mêmes opérations que la fenêtre Windows, dans le menu texte."""

    liste = MenuTests.liste
    ajouter = MenuTests.ajouter
    archive = MenuTests.archive

    def setUp(self):
        super().setUp()
        self.sauv = self.tmp / "sauvegardes-jed-essai"
        self.sauv.mkdir()
        self.install = self.make_install("jed-essai-2.0.2", "jed-essai", port=8001, sauvegardes=str(self.sauv))
        self.ajouter(self.install)
        self.en_marche = json.dumps([{"Name": "jed-essai", "Status": "running(8)",
                                      "ConfigFiles": str(self.install / "docker-compose.yml")}])

    def menu(self, *reponses, **env):
        env.setdefault("fake_compose_ls", self.en_marche)
        env.setdefault("FAKE_ACTUEL", str(self.install))   # images de départ du faux docker (fichier VERSION)
        return MenuTests.menu(self, *reponses, **env)

    # Raccourcis
    def test_shortcuts_in_the_applications_menu(self):
        # Comme la fenêtre : les raccourcis visent l'installation elle-même (son j-ed.sh et son logo).
        (self.install / "j-ed.sh").write_text("#!/bin/sh\n")
        (self.install / "static" / "img").mkdir(parents=True)
        (self.install / "static" / "img" / "logo-j-ed.svg").write_text("<svg/>")
        r = self.menu("7", "", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        applications = self.home / ".local" / "share" / "applications"
        web = (applications / "j-ed-jed-essai.desktop").read_text(encoding="utf-8")
        self.assertIn("Name=J-ed - jed-essai\n", web)
        self.assertIn('Exec=xdg-open "http://localhost:8001/"\n', web)
        self.assertIn("Terminal=false", web)
        self.assertIn(f"Icon={self.install / 'static' / 'img' / 'logo-j-ed.svg'}", web)
        assistant = (applications / "j-ed-assistant.desktop").read_text(encoding="utf-8")
        self.assertIn(f'Exec=bash "{self.install / "j-ed.sh"}"\n', assistant)
        self.assertIn(f"Path={self.install}\n", assistant)
        self.assertIn("Terminal=true", assistant)
        self.assertIn("Raccourcis créés", self.sortie)
        self.assertIn("menu Applications", self.sortie)

    def test_desktop_exec_argument_is_escaped(self):
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                            f"Import-Module '{MODULE}'; ConvertTo-ArgumentDesktopJed '/home/a b/$x\\\"%`'"],
                           capture_output=True, text=True, timeout=120, env=self.env())
        self.assertEqual(r.stdout.strip(), '"/home/a b/\\$x\\\\\\"%%\\`"', r.stderr)

    # « Ça ne marche pas »
    def test_report_without_secret(self):
        bureau = self.home / "Bureau"
        bureau.mkdir()
        outil = self.outils / "xdg-user-dir"
        outil.write_text(f"#!/bin/sh\n[ \"$1\" = DESKTOP ] && echo '{bureau}'\n")
        outil.chmod(0o755)
        r = self.menu("11", "", "0", fake_logs="web-1 | POSTGRES_PASSWORD=mot-de-passe-fictif ecrit@exemple.fr")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        zips = list(bureau.glob("compte-rendu-j-ed-*.zip"))
        self.assertEqual(len(zips), 1, self.sortie)
        texte = zipfile.ZipFile(zips[0]).read("compte-rendu.txt").decode("utf-8")
        self.assertNotIn("mot-de-passe-fictif", texte)
        self.assertNotIn("ecrit@exemple.fr", texte)
        self.assertIn("Nom : jed-essai", texte)
        self.assertIn("[ok] Linux", texte)
        if Path("/etc/os-release").exists():
            self.assertIn("Distribution : ", texte)
        self.assertIn("Compte rendu prêt", self.sortie)
        self.assertEqual(list(self.tmp.glob("J-ed-*/compte-rendu-*")), [])   # dossier temporaire effacé

    def test_report_without_any_installation(self):
        self.liste().unlink()
        r = self.menu("11", "", "0", fake_compose_ls="[]")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(list(self.home.glob("compte-rendu-j-ed-*.zip"))), 1, self.sortie)

    # Mot de passe oublié
    def test_forgotten_password(self):
        mot = "Motdepasse-solide-42"
        r = self.menu("10", "4", "", mot, mot, "", "0", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1. auteur-fictif — Auteur fictif (Administrateur)", self.sortie)
        self.assertIn("Mot de passe changé pour « auteur-fictif »", self.sortie)
        self.assertEqual((self.tmp / "mot-recu").read_text(), mot)
        self.assertNotIn(mot, self.sortie + r.stderr)                      # jamais affiché
        self.assertNotIn(mot, "\n".join(self.calls()))                     # ni en argument de docker

    def test_forgotten_password_two_different_entries(self):
        self.menu("10", "4", "", "Motdepasse-solide-42", "Motdepasse-solide-43", "", "0", "0")
        self.assertIn("Les deux saisies sont différentes", self.sortie)
        self.assertNotIn("--utilisateur", "\n".join(self.calls()))

    def test_forgotten_password_refused_when_stopped(self):
        self.menu("10", "4", "", "0", "0", fake_compose_ls="[]")
        self.assertIn("est arrêtée", self.sortie)
        self.assertNotIn("mot_de_passe_oublie", "\n".join(self.calls()))

    # Restaurer une sauvegarde
    def tar(self):
        f = self.sauv / "sauvegarde-20261126-120000-full.tar"
        f.write_bytes(b"contenu-fictif")
        return f

    def test_restore_into_the_chosen_installation(self):
        f = self.tar()
        r = self.menu("10", "3", "", "2", "RESTAURER", "", "0", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"[{f}]", self.sortie)                                # dernière sauvegarde proposée
        appels = "\n".join(self.calls())
        self.assertIn(f"{self.install} | compose cp {f} web:/data/restauration-{f.name}", appels)
        self.assertIn(f"restore_backup /data/restauration-{f.name} --yes", appels)
        self.assertIn(f"{self.install} | compose restart", appels)
        self.assertIn("Sauvegarde restaurée", self.sortie)
        self.assertIn("Sauvegarde de sécurité faite juste avant", self.sortie)

    def test_restore_needs_the_exact_word(self):
        self.tar()
        self.menu("10", "3", "", "2", "restaurer", "", "0", "0")
        self.assertIn("Annulé : rien n'a changé.", self.sortie)
        self.assertNotIn("restore_backup", "\n".join(self.calls()))

    def test_restore_into_a_new_installation(self):
        f = self.tar()
        archive = self.archive()
        port = free_port()
        r = self.menu("10", "3", "", "1",
                      "",                  # pas de proxy
                      "2", str(archive),   # archive déjà téléchargée
                      "",                  # nom proposé : jed-essai-copie
                      str(port), "", "", "n", "", "",
                      "", "0", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Nouvelle installation pour y restaurer la sauvegarde", self.sortie)
        self.assertIn("[jed-essai-copie]", self.sortie)
        self.assertIn("les comptes viendront de la sauvegarde", self.sortie)
        self.assertNotIn("encore deux étapes", self.sortie)                # pas de fin guidée
        dest = self.tmp / "jed-essai-copie-2.0.3"   # à côté de l'installation existante
        appels = "\n".join(self.calls())
        self.assertIn(f"{dest} | compose cp {f} web:/data/restauration-{f.name}", appels)
        self.assertIn(f"{dest} | compose restart", appels)
        self.assertNotIn(f"{self.install} | compose restart", appels)      # l'installation d'origine n'est pas touchée
        self.assertIn("Sauvegarde restaurée", self.sortie)

    # Vérifier la migration
    def test_migration_check_runs_the_installation_script(self):
        recu = self.tmp / "migration.txt"
        (self.install / "verifier-migration.ps1").write_text(
            f"param([string[]]$Dossiers)\n($Dossiers -join ';') | Set-Content '{recu}'\n"
            "Write-Host '[OK] Données : présentes'\nexit 0\n", encoding="utf-8")
        r = self.menu("10", "5", "", "0", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(recu.read_text().strip(), str(self.install))
        self.assertIn("[OK] Données : présentes", self.sortie)
        self.assertIn("Tout va bien", self.sortie)

    # Réinitialiser l'essai
    def faux_reinitialiser(self):
        recu = self.tmp / "reinit.txt"
        (self.install / "reinitialiser-essai.ps1").write_text(
            "param([switch]$SansSauvegarde, [switch]$Complet)\n$l = [Console]::In.ReadLine()\n"
            f"\"$SansSauvegarde|$Complet|$l|$((Get-Location).Path)\" | Set-Content '{recu}'\n"
            "Write-Host '== Arrêt et effacement'\nexit 0\n", encoding="utf-8")
        return recu

    def test_reset_trial_with_backup_and_complete(self):
        recu = self.faux_reinitialiser()
        r = self.menu("10", "6", "", "o", "REINITIALISER", "", "0", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(recu.read_text().strip(), f"True|True|REINITIALISER|{self.install}")
        appels = "\n".join(self.calls())
        self.assertIn("backup --verify", appels)
        self.assertIn("Essai réinitialisé (réinitialisation complète)", self.sortie)
        self.assertIn("choisissez « 3. Démarrer »", self.sortie)

    def test_reset_trial_needs_the_exact_word(self):
        recu = self.faux_reinitialiser()
        self.menu("10", "6", "n", "n", "non", "", "0", "0")
        self.assertIn("Annulé : rien n'a changé.", self.sortie)
        self.assertFalse(recu.exists())
        self.assertNotIn("backup --verify", "\n".join(self.calls()))

    def test_reset_refused_outside_a_trial(self):
        autre = self.make_install("jed-2.0.2", "jed", port=8002)
        self.ajouter(autre)
        self.menu("10", "6", "", "", "0", "0", fake_compose_ls="[]")
        self.assertIn("n'est pas une installation d'essai", self.sortie)


class ScriptsLot3Tests(LinuxTestCase):
    """2.0.3, lot 3 — refus de root dans reinitialiser-essai.ps1 et verifier-migration.ps1 (D4)."""

    def lancer(self, script, *args, **env):
        return subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(ROOT / script), *args],
                              capture_output=True, text=True, timeout=120, cwd=self.tmp, env=self.env(**env))

    def test_reset_refuses_root(self):
        r = self.lancer("reinitialiser-essai.ps1", "-SansSauvegarde", JED_UID_ACTUEL="0")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("sans sudo", r.stdout)
        self.assertIn("Rien n'a été effacé.", r.stdout)
        self.assertEqual(self.calls(), [])

    def test_migration_check_refuses_root(self):
        r = self.lancer("verifier-migration.ps1", "-Dossiers", str(self.tmp), JED_UID_ACTUEL="0")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("sans sudo", r.stdout)
        self.assertEqual(self.calls(), [])

    def test_reset_backup_copy_uses_the_system_separator(self):
        source = (ROOT / "reinitialiser-essai.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("'.\\sauvegardes-essai\\'", source)
        self.assertIn("[System.IO.Path]::DirectorySeparatorChar", source)

    def test_migration_check_gives_the_linux_command(self):
        source = (ROOT / "verifier-migration.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("pwsh -NoProfile -File ./verifier-j-ed.ps1", source)


class EssaisDockerTests(LinuxTestCase):
    """2.0.3 : « Essais Docker » sur GitHub (vrai Docker sous Linux), lancés à la main avant une version candidate."""

    OUTIL = ROOT / "tests" / "outils" / "essai-docker.ps1"
    FLUX = ROOT / ".github" / "workflows" / "essais-docker.yml"

    def test_workflow_runs_the_tool_on_demand_only(self):
        texte = self.FLUX.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", texte)
        self.assertNotIn("push:", texte)          # trop long pour chaque envoi (construction des images)
        self.assertIn("pwsh -NoProfile -File tests/outils/essai-docker.ps1", texte)
        self.assertIn("permissions:\n  contents: read", texte)
        self.assertIn("if: always()", texte)       # journaux joints même en cas d'échec

    def test_tool_refuses_to_run_outside_github(self):
        env = self.env()
        env.pop("GITHUB_ACTIONS", None)
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(self.OUTIL), "-Dossier", str(self.tmp / "x")],
                           capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("il tourne sur GitHub", r.stdout)
        self.assertFalse((self.tmp / "x").exists())   # rien n'est créé

    def test_tool_covers_every_step_and_never_deletes_volumes(self):
        brut = self.OUTIL.read_bytes()
        self.assertTrue(brut.startswith(b"\xef\xbb\xbf"))
        source = brut.decode("utf-8-sig")
        for etape in ("installer-j-ed.ps1", "verifier-j-ed.ps1", "Invoke-SauvegardeJed", "mettre-a-jour.ps1",
                      "Invoke-RestaurationJed", "verifier-migration.ps1", "reinitialiser-essai.ps1", "j-ed.sh",
                      "(code $code, attendu 3)", "(code $code, attendu 4)", "(code $code, attendu 0)"):
            self.assertIn(etape, source)
        self.assertNotIn("down -v", source)
        self.assertNotIn("'--volumes'", source)
        self.assertNotIn("volume', 'rm", source)


class RobustesseTests(LinuxTestCase):
    """2.0.3 (avant la version définitive, accord de l'utilisateur du 26/11) : journaux limités, .env protégé."""

    def test_every_service_has_a_log_size_limit(self):
        d = self.tmp / "compose"
        d.mkdir()
        shutil.copy(ROOT / "docker-compose.yml", d / "docker-compose.yml")
        (d / ".env").write_text("COMPOSE_PROJECT_NAME=jed-essai-journaux\nPOSTGRES_PASSWORD=fictif\n", encoding="utf-8")
        docker = shutil.which("docker", path="/usr/bin:/usr/local/bin:/bin")
        self.assertIsNotNone(docker, "client docker absent")
        r = subprocess.run([docker, "compose", "--profile", "argos", "--profile", "ollama", "config", "--format", "json"],
                           cwd=d, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        services = json.loads(r.stdout)["services"]
        self.assertEqual(set(services), {"db", "redis", "web", "worker", "worker-traduction", "worker-maintenant", "beat",
                                         "argos", "ollama"})
        for nom, service in services.items():
            self.assertEqual(service.get("logging"), {"driver": "json-file",
                                                      "options": {"max-size": "10m", "max-file": "3"}}, nom)

    def test_proxy_written_by_the_assistant_keeps_env_private(self):
        d = self.make_install("installation", "jed-essai")
        env = d / ".env"
        env.chmod(0o644)
        r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                            f"Import-Module '{MODULE}'; Set-ProxyEnvJed -Fichier '{env}' -Proxy '{PROXY}'"],
                           capture_output=True, text=True, timeout=120, env=self.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o600)
        copies = list(d.glob(".env.avant-proxy-*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(stat.S_IMODE(copies[0].stat().st_mode), 0o600, "la copie contient les mêmes secrets")
        self.assertIn(f"HTTPS_PROXY={PROXY}", env.read_text(encoding="utf-8"))

    def test_readme_says_macos_was_never_tried(self):
        self.assertIn("## 1. Installation (Windows et Linux ; macOS non essayé)",
                      (ROOT / "README.md").read_text(encoding="utf-8"))
