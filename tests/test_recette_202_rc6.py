"""2.0.2-rc6 : remarques N1 à N12 de la recette de la rc5 (24 novembre 2026) : essai sur un Windows 11 neuf (T16)
et vérification courte V0 à V8. Le guide, l'aide et la fenêtre sont vérifiés dans leur texte (l'affichage s'essaie
sous Windows) ; la logique du module l'est dans test_assistant_logique.py (Recette202Rc6ModuleTests).
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

ROOT = Path(settings.BASE_DIR)


def lire(nom):
    return (ROOT / nom).read_text(encoding="utf-8-sig")


class GuideAvantDeCommencerTests(SimpleTestCase):
    def setUp(self):
        self.guide = lire("AVANT-DE-COMMENCER.html")

    def section(self, ancre):
        debut = self.guide.index(f'id="{ancre}"')
        fin = self.guide.find("<h2", debut + 10)
        return self.guide[debut:fin if fin > 0 else len(self.guide)]

    def test_n1_close_terminal_then_restart_after_wsl(self):
        self.assertIn("Fermez alors le\nTerminal", self.section("wsl"))
        self.assertIn("redémarrez l'ordinateur</strong>, même si Windows ne le demande pas", self.section("wsl"))

    def test_n2_virtual_machine_platform(self):
        docker = self.section("docker")
        self.assertIn("Virtual Machine Platform is not enabled", docker)
        self.assertIn("Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All", docker)
        self.assertIn("Virtual Machine Platform is not enabled", self.section("problemes"))

    def test_n3_waiting_for_the_window(self):
        self.assertIn("jusqu'à une demi-minute la première fois", self.section("assistant"))
        self.assertIn("sans double-cliquer une seconde fois", self.section("assistant"))
        self.assertNotIn("PowerShell <strong>vide</strong>", self.guide, "R6 corrigé : plus de fenêtre vide")

    def test_n4_proxy_comes_before_the_installation(self):
        ordre = [self.guide.index(f'<h2 id="{a}">') for a in ("disque", "proxy", "telecharger", "assistant", "installer")]
        self.assertEqual(ordre, sorted(ordre))
        sommaire = self.guide[:self.guide.index('<h2 id="configuration">')]
        liens = re.findall(r'<a href="#([a-z-]+)">', sommaire)
        self.assertLess(liens.index("proxy"), liens.index("telecharger"))
        proxy = self.section("proxy")
        self.assertIn("<strong>avant</strong>", proxy)
        self.assertIn("Manual proxy configuration", proxy)
        self.assertIn("docker pull python:3.12-slim-bookworm", proxy)
        adresses = re.findall(r"https?://[^\s\"<]*proxy[^\s\"<]*", self.guide)
        self.assertTrue(adresses and all("exemple" in a for a in adresses), "seulement des adresses fictives")

    def test_n6_two_proxy_settings_explained(self):
        proxy = self.section("proxy")
        self.assertIn("Deux réglages, deux rôles", proxy)
        self.assertIn("HTTP_PROXY", proxy)
        aide = lire("docs/aide/assistant-j-ed.md")
        self.assertIn("il faut **deux réglages**", aide)
        self.assertIn("Sur un réseau **sans** proxy", aide)

    def test_n10_keys_created_by_the_assistant(self):
        installer = self.section("installer")
        self.assertIn("Aucune clé ni aucun mot de passe technique à inventer", installer)
        self.assertIn("Gardez une copie de ce fichier <code>.env</code> en lieu sûr", installer)
        self.assertIn("**Gardez une copie de ce fichier en lieu sûr**", lire("docs/aide/assistant-j-ed.md"))

    def test_pdf_follows_the_html(self):
        from pypdf import PdfReader

        texte = " ".join(p.extract_text() for p in PdfReader(str(ROOT / "AVANT-DE-COMMENCER.pdf")).pages)
        texte = re.sub(r"\s+", " ", texte)
        for attendu in ("Virtual Machine Platform", "Deux réglages, deux rôles", "demi-minute", "en lieu sûr"):
            self.assertIn(attendu, texte)


class FenetreRc6Tests(SimpleTestCase):
    def setUp(self):
        self.code = lire("assistant/assistant-j-ed.ps1")

    def fonction(self, nom):
        debut = self.code.index(f"function {nom}")
        suite = self.code.find("\nfunction ", debut + 10)
        return self.code[debut:suite if suite > 0 else len(self.code)]

    def test_n4_docker_check_in_new_installation(self):
        nouvelle = self.fonction("Show-NouvelleInstallationJed")
        self.assertIn("New-BoutonJed 'Docker joint-il Internet ?'", nouvelle)
        self.assertIn("Invoke-DockerJed '' (Get-CommandeAccesRegistreJed)", nouvelle)

    def test_n5_elapsed_minutes_in_the_step_title(self):
        operation = self.fonction("Start-OperationJed")
        self.assertIn("Format-TitreEtapeJed $chrono.Titre $m", operation)
        self.assertIn("$chrono.Debut = [DateTime]::Now", operation)

    def test_n8_n10_end_of_installation(self):
        fin = self.fonction("Show-FinInstallationJed")
        self.assertIn("appuyez sur F5", fin)
        self.assertIn("Gardez-en une copie en lieu sûr", fin)
        self.assertIn("'.env'", fin)

    def test_n9_previous_choices_kept_after_a_failure(self):
        nouvelle = self.fonction("Show-NouvelleInstallationJed")
        echec = nouvelle.index("$script:DerniersChoixInstallation = @{")
        succes = nouvelle.index("$script:DerniersChoixInstallation = $null")
        self.assertLess(echec, succes)
        self.assertIn("Argos = $cArgos.Checked", nouvelle)
        self.assertIn("$cArgos.Checked = $avant.Argos", nouvelle)
        self.assertIn("Choix de la tentative précédente repris.", nouvelle)
        self.assertIn("$script:DerniersChoixInstallation = $null", self.code[:self.code.index("function ")])

    def test_n11_j_ed_icon(self):
        ico = (ROOT / "assistant" / "j-ed.ico").read_bytes()
        self.assertEqual(ico[:4], b"\x00\x00\x01\x00", "fichier .ico")
        self.assertGreaterEqual(int.from_bytes(ico[4:6], "little"), 4, "plusieurs tailles")
        self.assertIn("if ($script:IconeJed) { $f.Icon = $script:IconeJed }", self.fonction("New-FenetreJed"))
        self.assertIn("if ($script:IconeJed) { $f.Icon = $script:IconeJed }", self.fonction("Show-AssistantJed"))
        self.assertIn("SetCurrentProcessExplicitAppUserModelID('J-ed.Assistant')", self.code)
        module = lire("assistant/AssistantJed.psm1")
        self.assertIn('$r.IconLocation = "$icone,0"', module)

    def test_n12_restore_choice_on_two_lines(self):
        restauration = self.fonction("Show-RestaurationJed")
        self.assertIn("REMPLACÉE`n(une sauvegarde de sécurité est faite avant)", restauration)
        self.assertIn("Size(640, 44)", restauration)


class PremiereConfigurationSansArgosTests(TestCase):
    """N7 : la première configuration proposait d'installer la traduction hors ligne sur une installation faite sans
    Argos (case décochée dans l'assistant : COMPOSE_PROFILES vide)."""

    URL = "/comptes/premier-demarrage/"

    @override_settings(ARGOS_SERVICE_INSTALLE=False)
    def test_no_argos_checkbox_without_the_service(self):
        page = self.client.get(self.URL)
        self.assertNotContains(page, 'name="install_argos"')
        self.assertContains(page, "non installée sur cet ordinateur")

    @override_settings(ARGOS_SERVICE_INSTALLE=True)
    def test_checkbox_with_the_service(self):
        page = self.client.get(self.URL)
        self.assertContains(page, 'name="install_argos"')
        self.assertNotContains(page, "non installée sur cet ordinateur")

    @override_settings(ARGOS_SERVICE_INSTALLE=None)
    def test_checkbox_when_unknown(self):
        self.assertContains(self.client.get(self.URL), 'name="install_argos"')

    def test_setting_reads_compose_profiles(self):
        source = lire("config/settings.py")
        self.assertIn('_profils = os.environ.get("COMPOSE_PROFILES")', source)
        self.assertIn('{"argos", "hors-ligne"}', source)
        compose = lire("docker-compose.yml")
        self.assertIn("env_file: .env", compose, "COMPOSE_PROFILES parvient aux conteneurs par le fichier .env")
