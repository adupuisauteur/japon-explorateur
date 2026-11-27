<#
.SYNOPSIS
    Essai complet de J-ed avec le VRAI Docker, sous Linux (outil de recette, pas une fonction de J-ed).

.DESCRIPTION
    Sert aux « Essais Docker » de GitHub (.github/workflows/essais-docker.yml) : une machine Ubuntu de GitHub, avec
    Docker et PowerShell 7, sous un compte ordinaire. Données fictives uniquement ; aucun secret.

    Déroulé (chaque étape vérifie un code de sortie ou un état réel) :
      E1  installation par installer-j-ed.ps1 (sans Argos) ; .env réservé au compte, journaux limités ;
      E2  compte administrateur fictif et jeu d'essai (notices fictives) ;
      E3  vérification par verifier-j-ed.ps1 ;
      E4  sauvegarde par le module de l'assistant (copiée dans le dossier des sauvegardes) ;
      E5  mise à jour « construction impossible » : code 3, l'ancienne version répond toujours ;
      E6  mise à jour « démarrage impossible » : code 4 (retour automatique), mêmes notices ;
      E7  mise à jour réussie : code 0, nouvelle version en service, mêmes notices, mêmes protections ;
      E8  restauration de la sauvegarde dans une NOUVELLE installation : mêmes notices ;
      E9  vérification après migration (verifier-migration.ps1) de cette nouvelle installation ;
      E10 réinitialisation de cette installation d'essai : base vide ;
      E11 menu texte (j-ed.sh) : les installations sont listées, en marche.

    Scénario « depuis-2.0.2 » (-Scenario depuis-2.0.2), comme sur la machine de l'utilisateur :
      D1  la 2.0.2 publiée est téléchargée depuis sa page de version GitHub (empreinte contrôlée) ;
      D2  elle est installée par SON installer-j-ed.ps1, avec un compte et le jeu d'essai fictifs ;
      D3  elle est mise à jour en 2.0.3 PAR LE MENU (j-ed.sh), réponses données comme au clavier ;
      D4  nouvelle version en service, mêmes notices, .env réservé au compte, journaux limités, « Vérifier ».

    Avec -Proxy (scénario « proxy ») : les installations reçoivent ce proxy (comme le menu le fait), et rien
    d'autre ne le connaît (le terminal n'a pas de proxy, comme dans la recette). L'accès direct à Internet doit
    avoir été coupé avant (tests/outils/reseau-proxy-essai.sh) : l'outil le vérifie d'abord.

    Par sécurité, l'outil refuse de tourner ailleurs que sur GitHub (variable GITHUB_ACTIONS), sauf avec
    -MachineDEssai : il crée des installations et en réinitialise une.

.PARAMETER Dossier
    Dossier de travail (installations, sauvegardes, archives, journaux).

.PARAMETER Scenario
    complet (par défaut : E1 à E11) ou depuis-2.0.2 (D1 à D4).

.PARAMETER Proxy
    Adresse du proxy d'essai (http://adresse:port) ; vide : aucun proxy.

.PARAMETER Port
    Premier port utilisé (le suivant sert à la seconde installation).
#>
[CmdletBinding()]
param(
    [string]$Dossier,
    [int]$Port = 8061,
    [ValidateSet('complet', 'depuis-2.0.2')][string]$Scenario = 'complet',
    [string]$Proxy = '',
    [switch]$MachineDEssai
)

$ErrorActionPreference = 'Continue'
if ($env:GITHUB_ACTIONS -ne 'true' -and -not $MachineDEssai) {
    Write-Host 'ARRÊT : cet outil crée des installations et en réinitialise une ; il tourne sur GitHub, ou avec -MachineDEssai sur une machine d''essai.' -ForegroundColor Red
    exit 2
}
$Racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Dossier) {
    $base = $env:RUNNER_TEMP
    if (-not $base) { $base = [System.IO.Path]::GetTempPath() }
    $Dossier = [System.IO.Path]::Combine($base, 'essai-docker')
}
New-Item -ItemType Directory -Force -Path $Dossier | Out-Null
$Dossier = (Resolve-Path -LiteralPath $Dossier).Path
$Journaux = [System.IO.Path]::Combine($Dossier, 'journaux')
New-Item -ItemType Directory -Force -Path $Journaux | Out-Null
$Version = (Get-Content -LiteralPath ([System.IO.Path]::Combine($Racine, 'VERSION')) -Raw).Trim()
Import-Module ([System.IO.Path]::Combine($Racine, 'assistant', 'AssistantJed.psm1')) -Force

$script:Echecs = New-Object System.Collections.Generic.List[string]
$script:Installations = New-Object System.Collections.Generic.List[string]

function Etape([string]$Texte) {
    Write-Host ''
    Write-Host "==== $Texte" -ForegroundColor Cyan
    if ($env:GITHUB_ACTIONS -eq 'true') { Write-Host "::notice::$Texte" }
}

function Verifier([bool]$Condition, [string]$Texte) {
    if ($Condition) { Write-Host "  OK : $Texte" -ForegroundColor Green; return }
    Write-Host "  ÉCHEC : $Texte" -ForegroundColor Red
    if ($env:GITHUB_ACTIONS -eq 'true') { Write-Host "::error::$Texte" }
    $script:Echecs.Add($Texte)
}

function Lancer([string]$Script, [string[]]$Arguments, [string]$Entree = '', [string]$Ici = $Dossier) {
    # Lance un script PowerShell de J-ed comme le fait l'assistant ; sortie affichée et gardée dans un journal.
    $nom = [System.IO.Path]::GetFileNameWithoutExtension($Script)
    $journal = [System.IO.Path]::Combine($Journaux, "$nom-$(Get-Date -Format 'HHmmss').txt")
    Push-Location -LiteralPath $Ici
    try {
        if ($Entree) { $Entree | & pwsh -NoProfile -File $Script @Arguments 2>&1 | Tee-Object -FilePath $journal | Out-Host }
        else { & pwsh -NoProfile -File $Script @Arguments 2>&1 | Tee-Object -FilePath $journal | Out-Host }
        return $LASTEXITCODE
    } finally { Pop-Location }
}

function Docker-Dans([string]$Ici, [string[]]$Arguments) {
    Push-Location -LiteralPath $Ici
    try {
        $sortie = & docker @Arguments 2>&1
        return [pscustomobject]@{ Code = $LASTEXITCODE; Texte = (($sortie | ForEach-Object { "$_" }) -join "`n").Trim() }
    } finally { Pop-Location }
}

function Test-Sante([string]$Ici, [int]$Secondes = 240) {
    # Page de santé du serveur web, interrogée dans le conteneur (comme mettre-a-jour.ps1), jusqu'à réponse.
    $fin = (Get-Date).AddSeconds($Secondes)
    do {
        $r = Docker-Dans $Ici @('compose', 'exec', '-T', 'web', 'curl', '-fsS', 'http://localhost:8000/sante/')
        if ($r.Code -eq 0) { return $true }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $fin)
    return $false
}

function Get-NombreNotices([string]$Ici) {
    $r = Docker-Dans $Ici @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c',
        'from apps.catalog.models import Record; print("NOTICES=%d" % Record.objects.count())')
    if ($r.Texte -match 'NOTICES=(\d+)') { return [int]$Matches[1] }
    Write-Host $r.Texte
    return -1
}

function Test-Protections([string]$Ici, [string]$Quand) {
    # Corrections d'après la rc1 : .env réservé au compte (600) ; journaux de chaque conteneur limités (10 Mo × 3).
    $mode = (& stat -c '%a' -- ([System.IO.Path]::Combine($Ici, '.env')) 2>$null | Select-Object -First 1)
    Verifier ("$mode".Trim() -eq '600') "$Quand : .env réservé au compte (droits $("$mode".Trim()), attendus 600)"
    $ids = @((Docker-Dans $Ici @('compose', 'ps', '-q')).Texte -split "`n" | Where-Object { $_.Trim() })
    $limites = @(foreach ($id in $ids) {
        (Docker-Dans $Ici @('inspect', '--format', '{{.Name}} {{.HostConfig.LogConfig.Type}} {{index .HostConfig.LogConfig.Config "max-size"}} {{index .HostConfig.LogConfig.Config "max-file"}}', $id.Trim())).Texte
    })
    $limites | ForEach-Object { Write-Host "    $_" }
    $bonnes = @($limites | Where-Object { $_ -match ' json-file 10m 3$' })
    Verifier ($ids.Count -gt 0 -and $bonnes.Count -eq $ids.Count) "$Quand : journaux limités à 10 Mo × 3 ($($bonnes.Count) conteneur(s) sur $($ids.Count))"
}

function New-DonneesEssai([string]$Ici) {
    # Compte administrateur fictif (mot de passe aléatoire, jamais réutilisé) et jeu d'essai ; renvoie le nombre de notices.
    $motFictif = 'Essai-' + [guid]::NewGuid().ToString('N')
    $r = Docker-Dans $Ici @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c',
        "from apps.accounts.models import User; User.objects.create_user('admin-essai', password='$motFictif', role='admin'); print('COMPTE=' + 'cree')")
    # Le texte attendu n'apparaît pas tel quel dans la commande : un message d'erreur qui la répète ne passe pas pour une réussite.
    Verifier ($r.Code -eq 0 -and $r.Texte -match 'COMPTE=cree') 'compte administrateur fictif créé'
    $r = Docker-Dans $Ici @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'jeu_essai', '--charger')
    Write-Host $r.Texte
    Verifier ($r.Code -eq 0) 'jeu d''essai chargé'
    $n = Get-NombreNotices $Ici
    Verifier ($n -gt 0) "notices présentes ($n)"
    return $n
}

function Get-ArgumentsProxy {
    if ($Proxy) { return @('-Proxy', $Proxy) }
    return @()
}

function Test-ProxyEnv([string]$Ici, [string]$Quand) {
    if (-not $Proxy) { return }
    $lignes = @(Get-Content -LiteralPath ([System.IO.Path]::Combine($Ici, '.env')) -Encoding UTF8)
    Verifier (($lignes -contains "HTTPS_PROXY=$Proxy") -and ($lignes -contains "HTTP_PROXY=$Proxy")) "$Quand : proxy écrit dans le .env"
}

function Save-JournauxDocker {
    foreach ($d in $script:Installations) {
        if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($d, '.env')))) { continue }
        $nom = Split-Path -Leaf $d
        $logs = Docker-Dans $d @('compose', 'logs', '--no-color', '--tail', '400')
        [System.IO.File]::WriteAllText([System.IO.Path]::Combine($Journaux, "docker-$nom.txt"), $logs.Texte)
        $ps = Docker-Dans $d @('compose', 'ps', '-a')
        [System.IO.File]::WriteAllText([System.IO.Path]::Combine($Journaux, "etat-$nom.txt"), $ps.Texte)
    }
}

function Terminer {
    Save-JournauxDocker
    Get-ChildItem -LiteralPath $Dossier -Recurse -Filter '*.log' -File -ErrorAction SilentlyContinue |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $Journaux -Force }
    Write-Host ''
    if ($script:Echecs.Count -eq 0) {
        Write-Host "Essai Docker réussi : toutes les étapes sont conformes (J-ed $Version)." -ForegroundColor Green
        exit 0
    }
    Write-Host "Essai Docker : $($script:Echecs.Count) échec(s) :" -ForegroundColor Red
    foreach ($e in $script:Echecs) { Write-Host "  - $e" -ForegroundColor Red }
    exit 1
}

Write-Host "Essai Docker de J-ed $Version — dossier de travail : $Dossier"
& docker version --format '{{.Server.Version}}' | ForEach-Object { Write-Host "Docker Engine : $_" }
Write-Host "PowerShell : $($PSVersionTable.PSVersion)"

# --- Archives (normale, construction impossible, démarrage impossible) ----------------------------------------
Etape 'Archives d''essai'
$Archives = [System.IO.Path]::Combine($Dossier, 'archives')
$code = Lancer ([System.IO.Path]::Combine($Racine, 'tests', 'outils', 'archives-essai.ps1')) @('-Source', $Racine, '-Version', $Version, '-Sortie', $Archives)
$Normale = [System.IO.Path]::Combine($Archives, "japon-explorateur-$Version-essai.zip")
$Construction = [System.IO.Path]::Combine($Archives, "japon-explorateur-$Version-essai-construction-impossible.zip")
$Demarrage = [System.IO.Path]::Combine($Archives, "japon-explorateur-$Version-essai-demarrage-impossible.zip")
Verifier ($code -eq 0 -and (Test-Path $Normale) -and (Test-Path $Construction) -and (Test-Path $Demarrage)) 'trois archives d''essai fabriquées'
if ($script:Echecs.Count) { Terminer }

# --- Proxy : le terminal n'en connaît aucun ; l'accès direct doit être coupé ------------------------------------
if ($Proxy) {
    Etape "Proxy d'essai : $Proxy (accès direct à Internet coupé)"
    foreach ($nom in @('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy')) {
        [Environment]::SetEnvironmentVariable($nom, $null)
    }
    & curl -sS -m 20 -o /dev/null https://github.com/ 2>&1 | Out-Host
    Verifier ($LASTEXITCODE -ne 0) 'sans proxy, Internet est injoignable (comme un réseau qui impose son proxy)'
    & curl -sS -m 30 -o /dev/null -x $Proxy https://github.com/ 2>&1 | Out-Host
    Verifier ($LASTEXITCODE -eq 0) 'avec le proxy, Internet répond'
    if ($script:Echecs.Count) { Terminer }
}

# --- Scénario « depuis-2.0.2 » : la version publiée, mise à jour par le menu -------------------------------------
if ($Scenario -eq 'depuis-2.0.2') {
    $Ancienne = '2.0.2'
    Etape "D1 Télécharger la $Ancienne publiée (page de version GitHub)"
    $zip = [System.IO.Path]::Combine($Archives, "japon-explorateur-$Ancienne.zip")
    $adresse = "https://github.com/adupuisauteur/japon-explorateur/releases/download/$Ancienne/japon-explorateur-$Ancienne.zip"
    $telechargement = @('-fsSL', '-m', '300', '-o', $zip, $adresse)
    if ($Proxy) { $telechargement = @('-x', $Proxy) + $telechargement }
    & curl @telechargement 2>&1 | Out-Host
    $telechargement[-2] = "$zip.sha256"; $telechargement[-1] = "$adresse.sha256"
    & curl @telechargement 2>&1 | Out-Host
    $e = Test-EmpreinteJed -Archive $zip -Empreinte "$zip.sha256"
    Verifier ([bool]$e.Ok) "archive $Ancienne téléchargée, empreinte conforme $($e.Raison)"
    if (-not $e.Ok) { Terminer }

    Etape "D2 Installation de la $Ancienne (son propre installer-j-ed.ps1), compte et jeu d'essai"
    $ext = [System.IO.Path]::Combine($Dossier, "code-$Ancienne")
    Expand-Archive -LiteralPath $zip -DestinationPath $ext -Force
    $installateur = Get-ChildItem -LiteralPath $ext -Recurse -Filter 'installer-j-ed.ps1' -File | Select-Object -First 1
    $A = [System.IO.Path]::Combine($Dossier, "jed-essai-ci-$Ancienne")
    $SauvA = [System.IO.Path]::Combine($Dossier, 'sauvegardes-jed-essai-ci')
    New-Item -ItemType Directory -Force -Path $SauvA | Out-Null
    & chmod o+rwx $SauvA
    $script:Installations.Add($A)
    # La 2.0.2 ne donne pas le proxy à la commande docker (ajouté en 2.0.3, lot 0) : comme l'utilisateur sur sa
    # machine le 26/11, le proxy est « exporté » pour cette seule installation. La mise à jour (D3) se fait sans.
    if ($Proxy) { foreach ($nom in @('HTTP_PROXY', 'HTTPS_PROXY')) { [Environment]::SetEnvironmentVariable($nom, $Proxy) } }
    $code = Lancer $installateur.FullName @('-Archive', $zip, '-Empreinte', "$zip.sha256", '-Destination', $A,
        '-Nom', 'jed-essai-ci', '-Port', "$Port", '-DossierSauvegardes', $SauvA, '-SansArgos' + (Get-ArgumentsProxy))
    foreach ($nom in @('HTTP_PROXY', 'HTTPS_PROXY')) { [Environment]::SetEnvironmentVariable($nom, $null) }
    Verifier ($code -eq 0) "installation de la $Ancienne réussie (code $code, attendu 0)"
    if ($code -ne 0) { Terminer }
    Verifier (Test-Sante $A) "la $Ancienne répond"
    Verifier ((Get-InstallationJed $A).Version -eq $Ancienne) "version $Ancienne en service"
    $Notices = New-DonneesEssai $A

    Etape "D3 Mise à jour $Ancienne → $Version par le menu (j-ed.sh de la $Version, réponses comme au clavier)"
    # Ordre des questions du menu (Update-InstallationJed) : choix 1 ; installation unique prise d'office ; proxy ;
    # archive (2 = déjà téléchargée, puis son chemin ; l'empreinte voisine est trouvée seule) ; dossier des
    # sauvegardes (Entrée) ; Docker joint-il Internet ? (Entrée = oui) ;
    # « Continuer ? » quand la nouvelle version est prête : o ; Entrée ; 0 Fermer.
    $reponses = @('1')
    if ($Proxy) { $reponses += @('o', $Proxy) } else { $reponses += 'n' }
    $reponses += @('2', $Normale, '', '')   # l'installation de D2 a déjà le proxy dans son .env : pas de question de plus
    $reponses += @('o', '', '0')
    $journalMenu = [System.IO.Path]::Combine($Journaux, 'menu-mise-a-jour.txt')
    $sortie = (($reponses -join "`n") + "`n") | & bash ([System.IO.Path]::Combine($Racine, 'j-ed.sh')) 2>&1 |
        ForEach-Object { "$_" } | Tee-Object -FilePath $journalMenu
    $texte = $sortie -join "`n"
    Write-Host $texte
    Verifier ($texte -match "Archive de la version $([regex]::Escape($Version)) : empreinte conforme") 'le menu accepte l''archive et son empreinte'
    Verifier ($texte -match 'Docker joint Internet') 'le menu : « Docker joint Internet »'
    Verifier ($texte -match 'La nouvelle version est prête') 'le menu pose la question quand la nouvelle version est prête'
    Verifier ($texte -match 'Mise à jour réussie') 'le menu annonce « Mise à jour réussie »'
    $B = ''
    if ($texte -match 'Nouvelle version dans : (.+)') { $B = $Matches[1].Trim() }
    Verifier ([bool]$B -and (Test-Path -LiteralPath $B)) "dossier de la nouvelle version : $B"
    if (-not $B -or -not (Test-Path -LiteralPath $B)) { Terminer }
    $script:Installations.Add($B)
    if ($texte -match 'Journal : (.+)') {
        $j = $Matches[1].Trim()
        Verifier ((Test-Path -LiteralPath $j) -and ((Get-Content -LiteralPath $j -Raw) -match 'FIN code=0')) 'journal de la mise à jour : FIN code=0'
    } else { Verifier $false 'le menu donne le chemin du journal' }

    Etape "D4 Contrôles de la $Version"
    Verifier (Test-Sante $B) 'la nouvelle version répond'
    Verifier ((Get-InstallationJed $B).Version -eq $Version) "version $Version en service"
    Verifier ((Get-NombreNotices $B) -eq $Notices) "mêmes notices après la mise à jour ($Notices)"
    Verifier (Test-Path -LiteralPath ([System.IO.Path]::Combine($A, '.env'))) 'l''ancien dossier est gardé'
    Test-Protections $B 'après la mise à jour par le menu'
    Test-ProxyEnv $B 'après la mise à jour par le menu'
    $code = Lancer ([System.IO.Path]::Combine($B, 'verifier-j-ed.ps1')) @('-Dossier', $B)
    Verifier ($code -eq 0) "« Vérifier » sans problème (code $code, attendu 0)"
    $menu = "0`n" | & bash ([System.IO.Path]::Combine($B, 'j-ed.sh')) 2>&1 | ForEach-Object { "$_" }
    $liste = $menu -join "`n"
    Write-Host $liste
    Verifier ($liste -match "jed-essai-ci\s+$([regex]::Escape($Version))\s+port\s+\d+\s+en marche") "le menu liste « jed-essai-ci » en $Version, en marche"
    Terminer
}

# --- E1 Installation ----------------------------------------------------------------------------------------
Etape 'E1 Installation (installer-j-ed.ps1, sans Argos)'
$A = [System.IO.Path]::Combine($Dossier, "jed-essai-ci-$Version")
$SauvA = [System.IO.Path]::Combine($Dossier, 'sauvegardes-jed-essai-ci')
New-Item -ItemType Directory -Force -Path $SauvA | Out-Null
& chmod o+rwx $SauvA   # comme le conseille le guide : le conteneur (utilisateur 1000) y copie ses sauvegardes
$script:Installations.Add($A)
$code = Lancer ([System.IO.Path]::Combine($Racine, 'installer-j-ed.ps1')) @('-Archive', $Normale, '-Destination', $A,
    '-Nom', 'jed-essai-ci', '-Port', "$Port", '-DossierSauvegardes', $SauvA, '-SansArgos' + (Get-ArgumentsProxy))
Verifier ($code -eq 0) "installation réussie (code $code, attendu 0)"
if ($code -ne 0) { Terminer }
Verifier (Test-Sante $A) 'la page de santé répond'
Test-Protections $A 'après l''installation'
Test-ProxyEnv $A 'après l''installation'

# --- E2 Compte et jeu d'essai --------------------------------------------------------------------------------
Etape 'E2 Compte administrateur fictif et jeu d''essai'
$Notices = New-DonneesEssai $A

# --- E3 Vérification ----------------------------------------------------------------------------------------
Etape 'E3 Vérification (verifier-j-ed.ps1)'
$code = Lancer ([System.IO.Path]::Combine($Racine, 'verifier-j-ed.ps1')) @('-Dossier', $A)
Verifier ($code -eq 0) "vérification sans problème (code $code, attendu 0)"

# --- E4 Sauvegarde ------------------------------------------------------------------------------------------
Etape 'E4 Sauvegarde (module de l''assistant)'
$s = Invoke-SauvegardeJed -Installation (Get-InstallationJed $A) -SurLigne { param($l) Write-Host "  $l" }
Verifier ([bool]$s.Ok) "sauvegarde faite : $($s.Message)"
$Tar = Get-ChildItem -LiteralPath $SauvA -Filter 'sauvegarde-*.tar' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
Verifier ($null -ne $Tar) 'sauvegarde copiée dans le dossier des sauvegardes'

# --- E5 à E7 Mises à jour -----------------------------------------------------------------------------------
$MettreAJour = [System.IO.Path]::Combine($Racine, 'mettre-a-jour.ps1')
Etape 'E5 Mise à jour « construction impossible »'
$code = Lancer $MettreAJour @('-Archive', $Construction, '-Actuel', $A, '-DossierSauvegardes', $SauvA, '-Oui')
Verifier ($code -eq 3) "construction impossible (code $code, attendu 3)"
Verifier (Test-Sante $A) 'l''ancienne version répond toujours'

Etape 'E6 Mise à jour « démarrage impossible » (retour automatique)'
$code = Lancer $MettreAJour @('-Archive', $Demarrage, '-Actuel', $A, '-DossierSauvegardes', $SauvA, '-Oui', '-DelaiControle', '120')
Verifier ($code -eq 4) "retour automatique à l'ancienne version (code $code, attendu 4)"
Verifier (Test-Sante $A) 'l''ancienne version répond après le retour'
Verifier ((Get-NombreNotices $A) -eq $Notices) "mêmes notices après le retour ($Notices)"

Etape 'E7 Mise à jour réussie'
$B = [System.IO.Path]::Combine($Dossier, "japon-explorateur-$Version-essai")
$script:Installations.Add($B)
$code = Lancer $MettreAJour @('-Archive', $Normale, '-Actuel', $A, '-DossierSauvegardes', $SauvA, '-Oui')
Verifier ($code -eq 0) "mise à jour réussie (code $code, attendu 0)"
Verifier (Test-Sante $B) 'la nouvelle version répond'
Verifier ((Get-NombreNotices $B) -eq $Notices) "mêmes notices après la mise à jour ($Notices)"
Test-Protections $B 'après la mise à jour'
Test-ProxyEnv $B 'après la mise à jour'

# --- E8 Restauration dans une nouvelle installation ------------------------------------------------------------
Etape 'E8 Restauration de la sauvegarde dans une nouvelle installation'
$C = [System.IO.Path]::Combine($Dossier, "jed-essai-ci-copie-$Version")
$SauvC = [System.IO.Path]::Combine($Dossier, 'sauvegardes-jed-essai-ci-copie')
New-Item -ItemType Directory -Force -Path $SauvC | Out-Null
& chmod o+rwx $SauvC
$script:Installations.Add($C)
$code = Lancer ([System.IO.Path]::Combine($Racine, 'installer-j-ed.ps1')) @('-Archive', $Normale, '-Destination', $C,
    '-Nom', 'jed-essai-ci-copie', '-Port', "$($Port + 1)", '-DossierSauvegardes', $SauvC, '-SansArgos' + (Get-ArgumentsProxy))
Verifier ($code -eq 0) "seconde installation réussie (code $code, attendu 0)"
if ($code -eq 0 -and $Tar) {
    $x = Invoke-RestaurationJed (Get-InstallationJed $C) $Tar.FullName -SurLigne { param($l) Write-Host "  $l" }
    Verifier ([bool]$x.Ok) "sauvegarde restaurée : $($x.Message)"
    Verifier (Test-Sante $C) 'la copie répond après la restauration'
    Verifier ((Get-NombreNotices $C) -eq $Notices) "mêmes notices dans la copie ($Notices)"

    # --- E9 Vérification après migration -------------------------------------------------------------------
    Etape 'E9 Vérification après migration (verifier-migration.ps1)'
    $code = Lancer ([System.IO.Path]::Combine($Racine, 'verifier-migration.ps1')) @('-Dossiers', $C)
    Verifier ($code -eq 0) "vérification après migration sans problème (code $code, attendu 0)"

    # --- E10 Réinitialisation de l'essai ---------------------------------------------------------------------
    Etape 'E10 Réinitialisation de l''installation d''essai (copie)'
    $code = Lancer ([System.IO.Path]::Combine($C, 'reinitialiser-essai.ps1')) @('-SansSauvegarde') -Entree "REINITIALISER`n" -Ici $C
    Verifier ($code -eq 0) "réinitialisation (code $code, attendu 0)"
    Verifier (Test-Sante $C 300) 'l''essai réinitialisé répond'
    Verifier ((Get-NombreNotices $C) -eq 0) 'base vide après la réinitialisation'
    Verifier ((Get-NombreNotices $B) -eq $Notices) "l'autre installation n'est pas touchée ($Notices notices)"
}

# --- E11 Menu texte ----------------------------------------------------------------------------------------
Etape 'E11 Menu texte (j-ed.sh) : liste des installations'
$menu = "0`n" | & bash ([System.IO.Path]::Combine($B, 'j-ed.sh')) 2>&1 | ForEach-Object { "$_" }
$texte = $menu -join "`n"
Write-Host $texte
Verifier ($texte -match 'jed-essai-ci\s+\S+\s+port\s+\d+\s+en marche') 'le menu liste les installations, en marche'
Verifier ($texte -match 'Prérequis') 'le menu affiche les prérequis'

Terminer
