"""2.0.2-rc5 : corrections des remarques de la recette des versions candidates rc1 à rc4 (23 et 24 novembre 2026).

La partie « module » de l'assistant est testée dans test_assistant_logique.py (Recette202Rc5ModuleTests) ; ici :
la première configuration (R12), les scripts et la fenêtre (vérifications du code, l'affichage s'essaie sous
Windows), les Dockerfile (R7).
"""
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

ROOT = Path(settings.BASE_DIR)
User = get_user_model()

FORMULAIRE = {"username": "auteur-fictif", "display_name": "Auteur fictif", "email": "",
              "password1": "Une-phrase-solide-2026", "password2": "Une-phrase-solide-2026",
              "default_search_mode": "selective", "backup_enabled": "on"}


def lire(nom):
    return (ROOT / nom).read_text(encoding="utf-8-sig")


class PremiereConfigurationDoubleEnvoiTests(TestCase):
    """R12 : un double clic sur « Terminer la configuration » envoyait deux fois le formulaire ; le second envoi
    provoquait une IntegrityError (erreur 500 et dysfonctionnement « critique ») alors que le compte était créé."""

    URL = "/comptes/premier-demarrage/"

    def test_second_submission_leads_to_login_without_error(self):
        premier = self.client.post(self.URL, FORMULAIRE)
        self.assertRedirects(premier, "/mises-a-jour/import/nouveau/", fetch_redirect_response=False)
        autre = self.client_class()   # le second envoi, sans la session ouverte par le premier
        second = autre.post(self.URL, FORMULAIRE, follow=True)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.redirect_chain[-1][0], "/comptes/connexion/")
        self.assertContains(second, "déjà été créé")
        self.assertEqual(User.objects.count(), 1)

    def test_second_submission_with_the_session_open_goes_home(self):
        self.client.post(self.URL, FORMULAIRE)
        r = self.client.post(self.URL, FORMULAIRE)
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertEqual(User.objects.count(), 1)

    def test_concurrent_creation_never_gives_an_error_500(self):
        """Le second envoi est passé entre les contrôles (le premier n'avait pas encore fini) : l'IntegrityError
        du compte en double est rattrapée ; message clair, aucun second compte, aucun dysfonctionnement."""
        from apps.incidents.models import Incident

        User.objects.create_user("auteur-fictif", password="Une-phrase-solide-2026", role="admin")
        with mock.patch("apps.accounts.views._compte_existe", return_value=False), \
             mock.patch("apps.accounts.forms.FirstRunForm.clean_username",
                        lambda form: form.cleaned_data["username"], create=True), \
             mock.patch("apps.accounts.forms.FirstRunForm.validate_unique", lambda form: None, create=True):
            # Contrôles du formulaire neutralisés : c'est l'état d'un envoi validé juste avant que l'autre crée le
            # compte.
            r = self.client.post(self.URL, FORMULAIRE, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.redirect_chain[-1][0], "/comptes/connexion/")
        self.assertContains(r, "déjà été créé")
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(Incident.objects.exists())

    def test_get_after_creation_still_goes_home(self):
        self.client.post(self.URL, FORMULAIRE)
        self.assertRedirects(self.client.get(self.URL), "/", fetch_redirect_response=False)

    def test_button_is_disabled_after_the_first_click(self):
        page = self.client.get(self.URL)
        self.assertContains(page, 'data-envoi-unique="Création du compte en cours…"')
        js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('hasAttribute("data-envoi-unique")', js)
        self.assertIn("b.disabled = true", js)


class ScriptsRc5Tests(SimpleTestCase):
    def test_r18_every_script_run_by_the_assistant_writes_utf8(self):
        for script in ("mettre-a-jour.ps1", "installer-j-ed.ps1", "verifier-j-ed.ps1", "verifier-migration.ps1",
                       "reinitialiser-essai.ps1"):
            source = lire(script)
            self.assertIn("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8", source, script)
            self.assertIn("$OutputEncoding = [System.Text.Encoding]::UTF8", source, script)

    def test_r19_reset_script_uses_the_name_j_ed_and_does_not_ask_twice(self):
        source = lire("reinitialiser-essai.ps1")
        code = re.sub(r"<#.*?#>", "", source, flags=re.S)
        self.assertNotIn("Explorateur documentaire", code)
        self.assertIn("Réinitialisation d''une installation d''essai de J-ed", code)
        branche = code[code.index("if ([Console]::IsInputRedirected) {"):code.index("return Read-Host $Question")]
        self.assertNotIn("$Question", branche, "question déjà posée dans l'assistant : pas affichée")
        self.assertIn("Réponse donnée dans l''assistant J-ed.", branche)

    def test_r21_complete_reset_announces_kept_images_and_assistant_advice(self):
        source = lire("reinitialiser-essai.ps1")
        self.assertIn("sauf si d''autres installations de J-ed s''en servent", source)
        self.assertIn("bouton « Démarrer » de l''assistant J-ed", source)

    def test_r7_pip_waits_longer_and_retries(self):
        for dockerfile in ("docker/Dockerfile", "docker/argos/Dockerfile"):
            source = (ROOT / dockerfile).read_text(encoding="utf-8")
            self.assertRegex(source, r"RUN pip install --timeout 120 --retries 10 ", dockerfile)


class FenetreRc5Tests(SimpleTestCase):
    """Fenêtre de l'assistant : vérifications du code (l'affichage s'essaie sous Windows, à la recette)."""

    def setUp(self):
        self.code = lire("assistant/assistant-j-ed.ps1")

    def fonction(self, nom):
        debut = self.code.index(f"function {nom}")
        suite = self.code.find("\nfunction ", debut + 10)
        return self.code[debut:suite if suite > 0 else len(self.code)]

    def test_r1_r2_close_button_and_help_label(self):
        accueil = self.fonction("Show-AssistantJed")
        self.assertIn("New-BoutonJed 'Fermer'", accueil)
        self.assertIn("$bFermer.Add_Click({ $f.Close() })", accueil)
        self.assertIn("'Aide : avant de commencer'", accueil)
        self.assertNotIn("Aide : Avant", self.code)

    def test_r4_protected_warning_before_writing_the_proxy(self):
        maj = self.fonction("Show-MiseAJourJed")
        self.assertLess(maj.index("Get-TexteProtegeeJed $i"), maj.index("Set-ProxyEnvJed"))
        self.assertNotIn("sans doute votre installation principale)", self.code)

    def test_r14_list_refresh_keeps_the_chosen_installation(self):
        liste = self.fonction("Update-ListeJed")
        self.assertLess(liste.index("$choisie = Get-CleCheminJed"), liste.index("$lv.Items.Clear()"))
        self.assertIn("$item.Selected = $true", liste)

    def test_r10_old_folder_is_grey_and_confirmed(self):
        self.assertIn("if ($i.Ancien) { $item.ForeColor = [System.Drawing.Color]::Gray }", self.fonction("Update-ListeJed"))
        self.assertIn("Confirm-ChoixJed $texte 'Ancien dossier'", self.fonction("Get-ChoixJed"))

    def test_r15_download_message_cleared_when_another_archive_is_chosen(self):
        self.assertEqual(self.code.count("$infoGitHub.Text = ''"), 2)

    def test_r20_reset_options_are_presented_as_independent(self):
        reset = self.fonction("Start-ReinitialisationJed")
        self.assertIn("Options (vous pouvez cocher les deux) :", reset)
        self.assertIn("Get-MessageReinitialisationJed", reset)

    def test_r22_list_reread_after_the_prerequisites(self):
        self.assertIn("Update-ListeJed", self.fonction("Show-PrerequisJed"))

    def test_r23_location_button_label_fits(self):
        self.assertNotIn("Choisir l''emplacement", self.code)

    def test_r8_r9_update_shows_folder_advice_and_current_step(self):
        maj = self.fonction("Show-MiseAJourJed")
        self.assertIn("-SurEtape $surEtape", maj)
        self.assertIn("Get-ConseilDossierMiseAJourJed $x.Code $x.Lignes", maj)

    def test_r16_installation_for_a_restoration(self):
        nouvelle = self.fonction("Show-NouvelleInstallationJed")
        self.assertIn("Get-MessageInstallationJed $x.Code -PourRestauration:$restauration", nouvelle)
        self.assertIn("Convert-LigneInstallationJed $l -PourRestauration:$restauration", nouvelle)
