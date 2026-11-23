"""2.0.2, lot 0 — contrat des scripts Windows (docs/contrat-scripts.md).

L'assistant J-ed lance les scripts PowerShell et lit leurs paramètres, codes de sortie et repères de journal.
Ces tests échouent si un script et le document cessent d'être d'accord : une version suivante (2.0.3, Linux) ne
peut ni retirer ni renommer ce dont l'assistant dépend sans que cela se voie.
"""
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
CONTRAT = ROOT / "docs" / "contrat-scripts.md"
PWSH = shutil.which("pwsh") or ("/opt/pwsh/pwsh" if Path("/opt/pwsh/pwsh").exists() else None)

#: Ce dont dépend l'assistant (2.0.2). On peut ajouter, jamais retirer.
PARAMETRES = {
    "mettre-a-jour.ps1": {"Archive", "Empreinte", "Actuel", "Destination", "DossierSauvegardes", "Oui",
                          "DelaiControle", "DelaiStabilite"},
    "verifier-j-ed.ps1": {"Dossier", "AvecSources", "AvecTests"},
    "verifier-migration.ps1": {"Dossiers"},
    "reinitialiser-essai.ps1": {"Complet", "SansSauvegarde"},
}
CODES_MISE_A_JOUR = {"CodeArret": 1, "CodeAnnule": 2, "CodeConstruction": 3, "CodeRetourReussi": 4,
                     "CodeRetourImpossible": 5}
REPERES = {"ETAPE", "INFO", "ATTENTION", "COMMANDE", "RESULTAT", "ERREUR", "QUESTION", "REPONSE", "FIN"}


def lire(nom):
    return (ROOT / nom).read_text(encoding="utf-8-sig")


class ContratDocumentTests(SimpleTestCase):
    def setUp(self):
        self.texte = CONTRAT.read_text(encoding="utf-8")

    def test_every_script_parameter_is_documented(self):
        for script, parametres in PARAMETRES.items():
            self.assertIn(f"`{script}`", self.texte)
            for nom in parametres:
                self.assertIn(f"`-{nom}`", self.texte, f"{script} : -{nom} absent du contrat")

    def test_every_update_code_and_marker_is_documented(self):
        for code in range(6):
            self.assertRegex(self.texte, rf"\n\| {code} \| ", f"code {code} absent du contrat")
        for repere in REPERES:
            self.assertIn(f"| `{repere}` |", self.texte, f"repère {repere} absent du contrat")


class ContratSourceTests(SimpleTestCase):
    """Lecture du source des scripts (sans PowerShell)."""

    def test_update_exit_codes_keep_their_values(self):
        source = lire("mettre-a-jour.ps1")
        for nom, valeur in CODES_MISE_A_JOUR.items():
            self.assertRegex(source, rf"\${nom} = {valeur}\r?\n", f"${nom} doit valoir {valeur}")

    def test_update_journal_uses_only_contract_markers(self):
        source = lire("mettre-a-jour.ps1")
        utilises = set(re.findall(r"Ecrire-Journal '([A-Z]+)'", source))
        self.assertTrue(utilises, "aucun repère trouvé")
        self.assertLessEqual(utilises, REPERES, "repère hors contrat : à ajouter à docs/contrat-scripts.md")
        self.assertIn("QUESTION", utilises)
        self.assertIn("Journal de la mise à jour : ", source)

    def test_update_reads_the_answer_from_another_program(self):
        source = lire("mettre-a-jour.ps1")
        self.assertIn("[Console]::IsInputRedirected", source)
        self.assertIn("[Console]::In.ReadLine()", source)

    def test_verification_writes_the_report_line(self):
        self.assertIn('Write-Host "Rapport enregistré : $Rapport"', lire("verifier-j-ed.ps1"))

    def test_checks_end_with_code_0_or_1(self):
        for script in ("verifier-j-ed.ps1", "verifier-migration.ps1", "reinitialiser-essai.ps1"):
            codes = set(re.findall(r"\bexit (\d+)", lire(script)))
            self.assertTrue(codes, script)
            self.assertLessEqual(codes, {"0", "1"}, f"{script} : code de sortie hors contrat")

    def test_no_script_removes_volumes(self):
        for script in PARAMETRES:
            # Code seulement : sans le bloc d'aide <# … #> ni les lignes de commentaire.
            code = re.sub(r"<#.*?#>", "", lire(script), flags=re.S)
            code = "\n".join(l for l in code.splitlines() if not l.lstrip().startswith("#"))
            self.assertNotRegex(code, r"down\b[^\n]*['\s]-v\b", script)
            self.assertNotIn("'--volumes'", code, script)


class ContratParametresTests(SimpleTestCase):
    """Paramètres tels que PowerShell les voit (comme l'assistant les passera)."""

    def setUp(self):
        if PWSH is None:
            self.skipTest("PowerShell (pwsh) absent")

    def test_scripts_accept_the_contract_parameters(self):
        for script, attendus in PARAMETRES.items():
            commande = (
                f"(Get-Command -Name '{ROOT / script}').Parameters.Keys | Where-Object {{ "
                "$_ -notin [System.Management.Automation.PSCmdlet]::CommonParameters -and "
                "$_ -notin [System.Management.Automation.PSCmdlet]::OptionalCommonParameters }"
            )
            sortie = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", commande],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(sortie.returncode, 0, sortie.stderr)
            trouves = set(sortie.stdout.split())
            self.assertLessEqual(attendus, trouves, f"{script} : paramètre du contrat absent")
