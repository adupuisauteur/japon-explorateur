<#
.SYNOPSIS
    J-ed 2.0.3 — « Essais Windows » : les scripts de J-ed sous le vrai Windows PowerShell 5.1 (outil de recette).

.DESCRIPTION
    À lancer avec powershell.exe (Windows PowerShell 5.1), sur une machine Windows jetable de GitHub
    (.github/workflows/essais-docker.yml). Le Docker de ces machines ne fait tourner que des conteneurs Windows :
    J-ed ne peut pas y démarrer. L'outil vérifie donc ce qui ne demande pas J-ed en marche, avec le vrai moteur
    de l'assistant Windows (powershell.exe, lancé par Invoke-ScriptJed comme le fait la fenêtre) :
      W1  syntaxe de tous les .ps1 et .psm1 pour Windows PowerShell 5.1 ; marque UTF-8 (BOM) présente ;
      W2  module de l'assistant chargé en mode strict ; Windows bien reconnu (pas Linux) ; fonctions sans Docker ;
      W3  docker-compose.yml lu par « docker compose config » puis par ConvertFrom-Json de 5.1 (défaut de la
          2.0.2-rc1) ; limite des journaux présente pour chaque service ;
      W4  archives d'essai fabriquées sous 5.1 (outil tests/outils/archives-essai.ps1) ;
      W5  « Vérifier » sur une installation arrêtée : un code prévu, jamais une exception de PowerShell ;
      W6  mise à jour d'une installation arrêtée : arrêt propre (code 1, journal FIN code=1), rien de modifié ;
      W7  les mêmes scripts sans Docker du tout : message clair, jamais une exception (défaut R13 de la 2.0.2).
    Données fictives uniquement ; aucun secret ; rien n'est installé.

.PARAMETER Dossier
    Dossier de travail (copies, archives, journaux).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Dossier,
    [switch]$MachineDEssai
)

$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -and -not $MachineDEssai) {
    Write-Host "ARRÊT : cet outil est fait pour une machine jetable de GitHub (ou, avec -MachineDEssai, une machine d'essai)."
    exit 2
}
if ($PSVersionTable.PSVersion.Major -ne 5) {
    Write-Host "ARRÊT : lancez cet outil avec Windows PowerShell 5.1 (powershell.exe), pas $($PSVersionTable.PSVersion)."
    exit 2
}
$Racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Version = ([System.IO.File]::ReadAllText([System.IO.Path]::Combine($Racine, 'VERSION'))).Trim()
New-Item -ItemType Directory -Force -Path $Dossier | Out-Null
$Dossier = (Resolve-Path -LiteralPath $Dossier).Path
$Journaux = [System.IO.Path]::Combine($Dossier, 'journaux')
New-Item -ItemType Directory -Force -Path $Journaux | Out-Null
$script:Echecs = New-Object System.Collections.Generic.List[string]

function Etape([string]$Titre) { Write-Host ''; Write-Host "==== $Titre"; Write-Host "::notice::$Titre" }
function Verifier([bool]$Condition, [string]$Texte) {
    if ($Condition) { Write-Host "  OK : $Texte" } else { Write-Host "  ÉCHEC : $Texte"; Write-Host "::error::$Texte"; $script:Echecs.Add($Texte) }
}
function Terminer {
    Write-Host ''
    if ($script:Echecs.Count) {
        Write-Host "Essai Windows : $($script:Echecs.Count) échec(s) :"
        $script:Echecs | ForEach-Object { Write-Host "  - $_" }
        exit 1
    }
    Write-Host "Essai Windows réussi : toutes les étapes sont conformes (J-ed $Version, Windows PowerShell $($PSVersionTable.PSVersion))."
    exit 0
}
function Test-SansException([string[]]$Lignes) {
    # Une exception de PowerShell laisse ces traces ; un message prévu par J-ed, non.
    $texte = $Lignes -join "`n"
    return -not ($texte -match 'NativeCommandError|RemoteException|CategoryInfo|FullyQualifiedErrorId|Exception lev|Exception calling')
}
function Lancer-CommeAssistant([string[]]$Arguments, [string]$Nom, [string]$Ici = $Dossier) {
    # Comme la fenêtre : Invoke-ScriptJed lance powershell.exe et lit sortie et erreurs ; aucune question n'est acceptée.
    $r = Invoke-ScriptJed -Arguments $Arguments -Dossier $Ici -SurQuestion { $false }
    $r.Lignes | Set-Content -LiteralPath ([System.IO.Path]::Combine($Journaux, "$Nom.txt")) -Encoding UTF8
    $r.Lignes | ForEach-Object { Write-Host "    $_" }
    return $r
}

Write-Host "Essai Windows de J-ed $Version — Windows PowerShell $($PSVersionTable.PSVersion), $([Environment]::OSVersion.VersionString)"
Write-Host "Dossier de travail : $Dossier"

# --- W1 Syntaxe 5.1 -----------------------------------------------------------------------------------------
Etape 'W1 Syntaxe de tous les scripts pour Windows PowerShell 5.1, marque UTF-8'
# Avec -LiteralPath, Windows PowerShell 5.1 ignore -Include : le tri se fait sur l'extension.
$fichiers = @(Get-ChildItem -LiteralPath $Racine -Recurse -File |
    Where-Object { @('.ps1', '.psm1') -contains $_.Extension.ToLowerInvariant() -and $_.FullName -notmatch '[\\/](\.git|node_modules)[\\/]' })
$mauvais = @()
foreach ($f in $fichiers) {
    $erreurs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$null, [ref]$erreurs)
    if ($erreurs -and $erreurs.Count) { $mauvais += "$($f.Name) : $($erreurs[0].Message) (ligne $($erreurs[0].Extent.StartLineNumber))" }
    $debut = [System.IO.File]::ReadAllBytes($f.FullName)
    if ($debut.Length -lt 3 -or $debut[0] -ne 0xEF -or $debut[1] -ne 0xBB -or $debut[2] -ne 0xBF) { $mauvais += "$($f.Name) : pas de marque UTF-8 (BOM)" }
}
$mauvais | ForEach-Object { Write-Host "    $_" }
Verifier ($fichiers.Count -ge 10 -and $mauvais.Count -eq 0) "$($fichiers.Count) fichiers lus par Windows PowerShell 5.1 sans erreur, tous avec la marque UTF-8"

# --- W2 Module ----------------------------------------------------------------------------------------------
Etape 'W2 Module de l''assistant (mode strict), Windows reconnu, fonctions sans Docker'
try {
    Set-StrictMode -Version Latest
    Import-Module ([System.IO.Path]::Combine($Racine, 'assistant', 'AssistantJed.psm1')) -Force
    Verifier $true 'module AssistantJed.psm1 chargé en mode strict'
} catch { Verifier $false "module non chargé : $($_.Exception.Message)"; Terminer }
Verifier (-not (Test-LinuxJed)) 'Windows reconnu (Test-LinuxJed faux)'
Verifier ((Get-MoteurPowerShellJed) -eq 'powershell.exe') 'les scripts seront lancés par powershell.exe (5.1)'
$temp = Get-DossierTemporaireJed -Nom 'essai'
Verifier ($temp -like "$([System.IO.Path]::GetTempPath().TrimEnd('\'))*" -and $temp -notmatch 'J-ed-\d+') "dossier temporaire de Windows, sans numéro de compte ($temp)"
Verifier ((Compare-VersionJed '2.0.3' '2.0.2') -eq 1 -and (Compare-VersionJed '2.0.2' '2.0.10') -eq -1) 'comparaison des versions'
Verifier ((Test-AdresseProxyJed 'http://proxy.exemple.fr:3128').Ok -and -not (Test-AdresseProxyJed 'proxy sans forme').Ok) 'contrôle d''une adresse de proxy'
Verifier ((Join-ArgumentsJed @('-File', 'C:\Dossier avec espace\a.ps1', 'x"y')) -eq '-File "C:\Dossier avec espace\a.ps1" "x\"y"') 'arguments écrits selon les règles de Windows'
$secret = [System.IO.Path]::Combine($Dossier, 'secret-fictif.env')
Set-Content -LiteralPath $secret -Value 'CLE=fictive' -Encoding UTF8
try { Protect-FichierSecretJed $secret; Verifier $true 'Protect-FichierSecretJed sans effet ni erreur sous Windows (chmod est propre à Linux)' }
catch { Verifier $false "Protect-FichierSecretJed : $($_.Exception.Message)" }
try {
    $faits = Get-FaitsSystemeJed
    # Test-PrerequisJed renvoie une liste protégée (,$liste) : la parcourir, ne pas l'entourer de @() (piège du lot 1).
    $controles = @(Test-PrerequisJed $faits | ForEach-Object { $_ })
    $controles | ForEach-Object { Write-Host "    [$($_.Niveau)] $($_.Libelle) : $($_.Detail)" }
    Verifier ($controles.Count -ge 4) "prérequis de Windows évalués sans exception ($($controles.Count) points)"
} catch { Verifier $false "prérequis : $($_.Exception.Message)" }
Set-StrictMode -Off

# --- W3 docker-compose.yml lu par 5.1 ------------------------------------------------------------------------
Etape 'W3 docker-compose.yml : docker compose config, puis ConvertFrom-Json de Windows PowerShell 5.1'
$copie = [System.IO.Path]::Combine($Dossier, 'config')
New-Item -ItemType Directory -Force -Path $copie | Out-Null
Copy-Item -LiteralPath ([System.IO.Path]::Combine($Racine, 'docker-compose.yml')) -Destination $copie
$modele = Get-Content -LiteralPath ([System.IO.Path]::Combine($Racine, '.env.example')) -Encoding UTF8
$modele | ForEach-Object { if ($_ -match '^COMPOSE_PROJECT_NAME=') { 'COMPOSE_PROJECT_NAME=jed-essai-win' } else { $_ } } |
    Set-Content -LiteralPath ([System.IO.Path]::Combine($copie, '.env')) -Encoding UTF8
foreach ($d in @('docker')) { $s = [System.IO.Path]::Combine($Racine, $d); if (Test-Path -LiteralPath $s) { Copy-Item -LiteralPath $s -Destination $copie -Recurse } }
$cfg = Invoke-DockerJed -Dossier $copie -Arguments @('compose', '--profile', 'argos', '--profile', 'ollama', 'config', '--format', 'json')
if ($cfg.Code -ne 0) { Write-Host $cfg.Texte }
Verifier ($cfg.Code -eq 0) "docker compose config (code $($cfg.Code))"
$objet = $null
try { $objet = $cfg.Texte | ConvertFrom-Json } catch { Write-Host "    $($_.Exception.Message)" }
Verifier ($null -ne $objet) 'configuration lisible par ConvertFrom-Json de 5.1'
if ($objet) {
    $services = @($objet.services.PSObject.Properties | ForEach-Object { $_.Name })
    $limites = @($services | Where-Object {
        $l = $objet.services.$_.logging
        $l -and $l.driver -eq 'json-file' -and $l.options.'max-size' -eq '10m' -and "$($l.options.'max-file')" -eq '3'
    })
    Write-Host "    services : $($services -join ', ')"
    Verifier ($services.Count -ge 7 -and $limites.Count -eq $services.Count) "journaux limités pour chaque service ($($limites.Count) sur $($services.Count))"
}

# --- W4 Archives d'essai sous 5.1 ---------------------------------------------------------------------------
Etape 'W4 Archives d''essai fabriquées sous Windows PowerShell 5.1'
$Archives = [System.IO.Path]::Combine($Dossier, 'archives')
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File ([System.IO.Path]::Combine($Racine, 'tests', 'outils', 'archives-essai.ps1')) -Version $Version -Sortie $Archives 2>&1 | Out-Host
$Normale = [System.IO.Path]::Combine($Archives, "japon-explorateur-$Version-essai.zip")
$e = Test-EmpreinteJed -Archive $Normale -Empreinte "$Normale.sha256"
Verifier ($LASTEXITCODE -eq 0 -and $e.Ok) 'archive normale et son empreinte, contrôlée par l''assistant'
Verifier ((Get-VersionArchiveJed $Normale) -eq $Version) "l'assistant lit la version de l'archive ($Version)"
if (-not $e.Ok) { Terminer }

# --- Une installation arrêtée (jamais démarrée : le Docker de cette machine ne fait pas tourner J-ed) -------
$Install = [System.IO.Path]::Combine($Dossier, 'jed-essai-win')
Expand-Archive -LiteralPath $Normale -DestinationPath ([System.IO.Path]::Combine($Dossier, 'decompresse')) -Force
Move-Item -LiteralPath ([System.IO.Path]::Combine($Dossier, 'decompresse', "japon-explorateur-$Version")) -Destination $Install
$modele | ForEach-Object { if ($_ -match '^COMPOSE_PROJECT_NAME=') { 'COMPOSE_PROJECT_NAME=jed-essai-win' } elseif ($_ -match '^WEB_PORT=') { 'WEB_PORT=8071' } else { $_ } } |
    Set-Content -LiteralPath ([System.IO.Path]::Combine($Install, '.env')) -Encoding UTF8
$Sauv = [System.IO.Path]::Combine($Dossier, 'sauvegardes-jed-essai-win')
New-Item -ItemType Directory -Force -Path $Sauv | Out-Null
$i = Get-InstallationJed -Dossier $Install
Verifier ($i.Valide -and $i.Nom -eq 'jed-essai-win' -and $i.Version -eq $Version) "l'assistant reconnaît l'installation (nom $($i.Nom), version $($i.Version), état $($i.Etat))"

# --- W5 Vérifier ---------------------------------------------------------------------------------------------
Etape 'W5 « Vérifier » sur une installation arrêtée, lancé comme par la fenêtre'
$r = Lancer-CommeAssistant (New-ArgumentsVerificationJed -Script ([System.IO.Path]::Combine($Install, 'verifier-j-ed.ps1')) -Dossier $Install) 'verifier-arretee'
Verifier ($r.Code -eq 1) "code $($r.Code) (attendu 1 : « Problème détecté », J-ed n'est pas démarré)"
Verifier (Test-SansException $r.Lignes) 'aucune exception de PowerShell, seulement des messages de J-ed'
$m = Get-MessageVerificationJed $r.Code
Verifier ($m.Titre -eq 'Problème détecté') "message de la fenêtre : « $($m.Titre) »"

# --- W6 Mise à jour ------------------------------------------------------------------------------------------
Etape 'W6 Mise à jour d''une installation arrêtée : arrêt propre, rien de modifié'
$avant = (Get-ChildItem -LiteralPath $Install -Recurse -File | Measure-Object).Count
$envAvant = [System.IO.File]::ReadAllText([System.IO.Path]::Combine($Install, '.env'))
$arguments = New-ArgumentsMiseAJourJed -Script ([System.IO.Path]::Combine($Install, 'mettre-a-jour.ps1')) -Archive $Normale -Actuel $Install -DossierSauvegardes $Sauv -Empreinte "$Normale.sha256"
$r = Lancer-CommeAssistant $arguments 'mise-a-jour-arretee'
$m = Get-MessageMiseAJourJed $r.Code
Verifier ($r.Code -eq 1) "code $($r.Code) (attendu 1 : arrêt pendant les contrôles, rien n'a changé) ; fenêtre : « $($m.Titre) »"
Verifier (Test-SansException $r.Lignes) 'aucune exception de PowerShell'
if ($r.Journal -and (Test-Path -LiteralPath $r.Journal)) {
    Verifier ((Get-Content -LiteralPath $r.Journal -Raw -Encoding UTF8) -match 'FIN code=1') "journal de la mise à jour : FIN code=1 ($($r.Journal))"
    Copy-Item -LiteralPath $r.Journal -Destination $Journaux
} else { Verifier $false 'le chemin du journal de la mise à jour est donné' }
Verifier (((Get-ChildItem -LiteralPath $Install -Recurse -File | Measure-Object).Count -eq $avant) -and
    ([System.IO.File]::ReadAllText([System.IO.Path]::Combine($Install, '.env')) -eq $envAvant)) 'installation inchangée (fichiers, .env)'
$nouvelles = @(Get-ChildItem -LiteralPath $Dossier -Directory | Where-Object { $_.Name -like 'japon-explorateur-*' })
Verifier ($nouvelles.Count -eq 0) 'aucun dossier de nouvelle version laissé'

# --- W7 Sans Docker du tout ----------------------------------------------------------------------------------
Etape 'W7 Sans Docker du tout (Docker Desktop absent ou arrêté) : message clair, jamais une exception'
$cheminAvant = $env:PATH
$env:PATH = (($env:PATH -split ';') | Where-Object { $_ -and -not (Test-Path -LiteralPath ([System.IO.Path]::Combine($_, 'docker.exe'))) }) -join ';'
try {
    Verifier (-not (Get-Command docker -ErrorAction SilentlyContinue)) 'docker retiré du chemin des programmes'
    $d = Invoke-DockerJed -Arguments @('compose', 'ls')
    Verifier ($d.Code -ne 0 -and (Convert-ErreurDockerJed $d.Texte)) "l'assistant traduit l'absence de Docker ($($d.Code))"
    try { $liste = @(Find-InstallationsJed -Fichier ([System.IO.Path]::Combine($Dossier, 'liste.json'))); Verifier $true "liste des installations sans exception ($($liste.Count))" }
    catch { Verifier $false "liste des installations : $($_.Exception.Message)" }
    $r = Lancer-CommeAssistant (New-ArgumentsVerificationJed -Script ([System.IO.Path]::Combine($Install, 'verifier-j-ed.ps1')) -Dossier $Install) 'verifier-sans-docker'
    Verifier ($r.Code -ne 0 -and (Test-SansException $r.Lignes)) "« Vérifier » sans Docker : code $($r.Code), aucune exception"
    $r = Lancer-CommeAssistant $arguments 'mise-a-jour-sans-docker'
    Verifier ($r.Code -eq 1 -and (Test-SansException $r.Lignes)) "mise à jour sans Docker : code $($r.Code) (attendu 1), aucune exception"
} finally { $env:PATH = $cheminAvant }

Terminer
