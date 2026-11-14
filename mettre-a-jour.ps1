<#
.SYNOPSIS
    Met à jour une installation de J-ed vers la version de l'archive fournie, en gardant ses données.

.DESCRIPTION
    Étapes, chacune contrôlée ; à la moindre anomalie, le script s'arrête avec un message clair :
      1. contrôles : Docker Desktop, empreinte SHA-256 de l'archive, version de l'archive (jamais plus
         ancienne), dossier actuel, nom du projet Docker et autorisation de mise à jour ;
      2. sauvegarde vérifiée de l'installation actuelle, puis copie hors de Docker (dossier de l'ordinateur)
         et contrôle de l'empreinte de la copie ;
      3. décompression de l'archive dans un NOUVEAU dossier (l'ancien dossier n'est jamais modifié) ;
      4. reprise du fichier .env de l'installation actuelle ;
      5. arrêt de l'ancienne version (sans effacer aucune donnée : « docker compose down » sans -v), puis
         démarrage de la nouvelle ;
      6. contrôle final : version attendue et base de données à jour (manage.py etat_installation).
    Les données (base, fichiers, paquets Argos) sont dans les volumes Docker du projet : elles sont reprises
    telles quelles parce que le nom du projet (COMPOSE_PROJECT_NAME) ne change pas.

.PARAMETER Archive
    Chemin de l'archive de la nouvelle version (.zip). Le fichier d'empreinte (.sha256) doit être à côté.

.PARAMETER Actuel
    Dossier de l'installation actuelle (celui qui contient docker-compose.yml et .env).

.PARAMETER Destination
    Dossier de la nouvelle version. Par défaut : à côté du dossier actuel, nommé comme l'archive.

.PARAMETER DossierSauvegardes
    Dossier de l'ordinateur où copier la sauvegarde faite avant la mise à jour. Par défaut :
    DOSSIER_SAUVEGARDES du fichier .env s'il existe, sinon un dossier « sauvegardes » à côté du dossier actuel.

.PARAMETER Oui
    Ne pas demander de confirmation avant l'arrêt de l'ancienne version.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.0.zip -Actuel D:\Exemple\japon-explorateur-1.3.0
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$Actuel,
    [string]$Destination,
    [string]$DossierSauvegardes,
    [switch]$Oui
)

# Les codes de retour de Docker sont contrôlés un par un (compatible Windows PowerShell 5.1).
$ErrorActionPreference = 'Continue'
$NomsProteges = @('japon-explorateur', 'japon-explorateur-essai')
$VersionMinimale = [version]'1.3.0'   # première version qui accepte AUTORISER_NOM_PROJET
$DelaiControleSecondes = 300

$script:AncienneArretee = $false
$script:SauvegardeLocale = $null

function Arreter([string]$Message) {
    Write-Host ''
    Write-Host "ARRÊT : $Message" -ForegroundColor Red
    if ($script:AncienneArretee) {
        Write-Host 'L''ancienne version a été arrêtée. Pour revenir en arrière :' -ForegroundColor Yellow
        Write-Host "  1. dans « $Destination » : docker compose down" -ForegroundColor Yellow
        Write-Host "  2. dans « $Actuel » : docker compose up -d" -ForegroundColor Yellow
        if ($script:SauvegardeLocale) {
            Write-Host "  3. si l'ancienne version ne démarre pas (base déjà mise à jour), restaurez la sauvegarde :" -ForegroundColor Yellow
            Write-Host "     $script:SauvegardeLocale (guide d'installation, « Restaurer une sauvegarde »)" -ForegroundColor Yellow
        }
    } else {
        Write-Host 'L''installation actuelle n''a pas été modifiée.' -ForegroundColor Yellow
    }
    exit 1
}

function Etape([string]$Message) {
    Write-Host ''
    Write-Host "== $Message" -ForegroundColor Cyan
}

function Docker-Dans {
    # Exécute docker dans le dossier indiqué et renvoie le code et la sortie (standard et erreurs).
    param([string]$Dossier, [string[]]$Arguments)
    Push-Location -LiteralPath $Dossier
    try {
        $sortie = & docker @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    return [pscustomobject]@{ Code = $code; Texte = (($sortie | ForEach-Object { "$_" }) -join "`n").Trim() }
}

function Lire-Env([string]$Fichier, [string]$Nom) {
    foreach ($ligne in (Get-Content -LiteralPath $Fichier -Encoding UTF8)) {
        if ($ligne -match "^\s*$Nom\s*=(.*)$") { return $Matches[1].Trim() }
    }
    return ''
}

function Version-Archive([string]$Zip) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $z = [System.IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        $entree = $z.Entries | Where-Object { $_.FullName -eq 'VERSION' -or $_.FullName -match '^[^/]+/VERSION$' } |
            Select-Object -First 1
        if (-not $entree) { return $null }
        $lecteur = New-Object System.IO.StreamReader($entree.Open())
        try { return $lecteur.ReadToEnd().Trim() } finally { $lecteur.Close() }
    } finally {
        $z.Dispose()
    }
}

Write-Host 'Mise à jour de J-ed' -ForegroundColor White

# --- 1. Contrôles ---------------------------------------------------------------------------------
Etape '1/6 Contrôles'

if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) { Arreter "archive introuvable : $Archive" }
$Archive = (Resolve-Path -LiteralPath $Archive).Path
if (-not (Test-Path -LiteralPath $Actuel -PathType Container)) { Arreter "dossier de l'installation actuelle introuvable : $Actuel" }
$Actuel = (Resolve-Path -LiteralPath $Actuel).Path
foreach ($f in @('docker-compose.yml', '.env', 'VERSION')) {
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Actuel, $f)))) {
        Arreter "« $f » absent de $Actuel : ce n'est pas le dossier d'une installation de J-ed."
    }
}
$EnvActuel = [System.IO.Path]::Combine($Actuel, '.env')

# Empreinte : « <archive>.sha256 » ou « <nom sans .zip>.sha256 », à côté de l'archive.
$CandidatsEmpreinte = @("$Archive.sha256", ([System.IO.Path]::ChangeExtension($Archive, '.sha256')))
$FichierEmpreinte = $CandidatsEmpreinte | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $FichierEmpreinte) {
    Arreter "fichier d'empreinte absent (attendu : $($CandidatsEmpreinte[0])). Téléchargez-le avec l'archive."
}
$Attendue = ((Get-Content -LiteralPath $FichierEmpreinte -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
$Calculee = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Attendue -ne $Calculee) {
    Arreter "empreinte de l'archive différente de celle attendue (archive incomplète, abîmée ou ancienne).`n  attendue : $Attendue`n  calculée : $Calculee"
}
Write-Host "Empreinte de l'archive vérifiée : $Calculee"

$VersionNouvelle = Version-Archive $Archive
if (-not $VersionNouvelle) { Arreter 'fichier VERSION introuvable dans l''archive : ce n''est pas une archive de J-ed.' }
$VersionActuelle = (Get-Content -LiteralPath ([System.IO.Path]::Combine($Actuel, 'VERSION')) -Raw).Trim()
try {
    $vN = [version]$VersionNouvelle
    $vA = [version]$VersionActuelle
} catch {
    Arreter "numéro de version illisible (actuelle : « $VersionActuelle », archive : « $VersionNouvelle »)."
}
if ($vN -lt $VersionMinimale) {
    Arreter "l'archive contient la version $VersionNouvelle : trop ancienne pour ce script (version $VersionMinimale au moins)."
}
if ($vN -lt $vA) {
    Arreter "l'archive contient la version $VersionNouvelle, plus ancienne que la version installée ($VersionActuelle). Pour revenir en arrière, suivez la procédure de retour de la version installée."
}
if ($vN -eq $vA) {
    Write-Host "Attention : l'archive contient la même version que l'installation actuelle ($VersionActuelle) : réinstallation." -ForegroundColor Yellow
}
Write-Host "Version actuelle : $VersionActuelle ; nouvelle version : $VersionNouvelle"

$Projet = Lire-Env $EnvActuel 'COMPOSE_PROJECT_NAME'
if (-not $Projet) { Arreter 'COMPOSE_PROJECT_NAME absent du fichier .env actuel : impossible de retrouver les données.' }
if ($NomsProteges -contains $Projet) {
    $Autorisation = Lire-Env $EnvActuel 'AUTORISER_NOM_PROJET'
    if ($Autorisation -ne $Projet) {
        Arreter "le projet « $Projet » est protégé. Pour le mettre à jour en gardant ses données, ajoutez d'abord la ligne AUTORISER_NOM_PROJET=$Projet dans $EnvActuel, puis relancez ce script."
    }
    Write-Host "Projet protégé « $Projet » : mise à jour autorisée par AUTORISER_NOM_PROJET." -ForegroundColor Yellow
}
Write-Host "Projet Docker : $Projet (ses volumes de données seront repris)"

if (-not $Destination) {
    $Destination = [System.IO.Path]::Combine((Split-Path -Parent $Actuel), [System.IO.Path]::GetFileNameWithoutExtension($Archive))
}
$Destination = [System.IO.Path]::GetFullPath($Destination)
if ($Destination.TrimEnd('\', '/') -eq $Actuel.TrimEnd('\', '/')) {
    Arreter 'le dossier de destination est le dossier actuel : choisissez un nouveau dossier (-Destination).'
}
if (Test-Path -LiteralPath $Destination) {
    Arreter "le dossier de destination existe déjà : $Destination. Supprimez-le ou choisissez-en un autre (-Destination)."
}
$Parent = Split-Path -Parent $Destination
try {
    $essai = [System.IO.Path]::Combine($Parent, "jed-essai-ecriture-$PID.tmp")
    Set-Content -LiteralPath $essai -Value 'essai' -ErrorAction Stop
    Remove-Item -LiteralPath $essai -Force -ErrorAction Stop
} catch {
    Arreter "impossible d'écrire dans $Parent (dossier verrouillé ou protégé) : $($_.Exception.Message)"
}

if ((Docker-Dans $Actuel @('info')).Code -ne 0) {
    Arreter 'Docker Desktop ne répond pas. Démarrez-le, attendez « Engine running », puis relancez ce script.'
}
$EnService = Docker-Dans $Actuel @('compose', 'ps', '--services', '--status', 'running')
if ($EnService.Code -ne 0) { Arreter "lecture de l'état des conteneurs impossible : $($EnService.Texte)" }
$Services = @($EnService.Texte -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($Services -notcontains 'web') {
    Arreter "l'installation actuelle n'est pas démarrée (service « web » arrêté). Démarrez-la (docker compose up -d dans $Actuel) pour que la sauvegarde puisse être faite."
}
$AvecArgos = $Services -contains 'argos'

# --- 2. Sauvegarde ----------------------------------------------------------------------------------
Etape '2/6 Sauvegarde de l''installation actuelle'

$Sauvegarde = Docker-Dans $Actuel @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'backup', '--verify')
Write-Host $Sauvegarde.Texte
# Les versions 1.2.0 et 1.3.0 affichent « Échec » sans code d'erreur : le texte est aussi contrôlé.
if ($Sauvegarde.Code -ne 0 -or $Sauvegarde.Texte -notmatch 'Terminée' -or $Sauvegarde.Texte -notmatch 'Intégrité vérifiée' -or $Sauvegarde.Texte -cmatch '(?m)^Échec') {
    Arreter 'la sauvegarde a échoué (message ci-dessus) : rien n''a été mis à jour.'
}
if ($Sauvegarde.Texte -notmatch 'Terminée : (\S+\.tar)') { Arreter 'chemin de la sauvegarde introuvable dans la réponse.' }
$CheminDocker = $Matches[1]
$NomSauvegarde = Split-Path -Leaf $CheminDocker

if (-not $DossierSauvegardes) { $DossierSauvegardes = Lire-Env $EnvActuel 'DOSSIER_SAUVEGARDES' }
if (-not $DossierSauvegardes) { $DossierSauvegardes = [System.IO.Path]::Combine((Split-Path -Parent $Actuel), 'sauvegardes') }
New-Item -ItemType Directory -Force -Path $DossierSauvegardes | Out-Null
$CopieLocale = [System.IO.Path]::Combine($DossierSauvegardes, $NomSauvegarde)
if (-not (Test-Path -LiteralPath $CopieLocale)) {
    $copie = Docker-Dans $Actuel @('compose', 'cp', "web:$CheminDocker", $CopieLocale)
    if ($copie.Code -ne 0 -or -not (Test-Path -LiteralPath $CopieLocale)) {
        Arreter "copie de la sauvegarde hors de Docker impossible : $($copie.Texte)"
    }
}
$EmpreinteDocker = Docker-Dans $Actuel @('compose', 'exec', '-T', 'web', 'sha256sum', $CheminDocker)
$EmpreinteLocale = (Get-FileHash -LiteralPath $CopieLocale -Algorithm SHA256).Hash.ToLowerInvariant()
if ($EmpreinteDocker.Code -ne 0 -or (($EmpreinteDocker.Texte -split '\s+')[0]).ToLowerInvariant() -ne $EmpreinteLocale) {
    Arreter "la copie de la sauvegarde ($CopieLocale) ne correspond pas à l'original."
}
$script:SauvegardeLocale = $CopieLocale
Write-Host "Sauvegarde copiée et vérifiée : $CopieLocale" -ForegroundColor Green

# --- 3. Décompression ---------------------------------------------------------------------------------
Etape '3/6 Décompression de la nouvelle version'

$Partiel = "$Destination.partiel"
if (Test-Path -LiteralPath $Partiel) { Remove-Item -LiteralPath $Partiel -Recurse -Force }
try {
    Expand-Archive -LiteralPath $Archive -DestinationPath $Partiel -ErrorAction Stop
} catch {
    Arreter "décompression impossible : $($_.Exception.Message)"
}
$Racine = $Partiel
if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Partiel, 'docker-compose.yml')))) {
    $sous = @(Get-ChildItem -LiteralPath $Partiel -Directory)
    if ($sous.Count -eq 1 -and (Test-Path -LiteralPath ([System.IO.Path]::Combine($sous[0].FullName, 'docker-compose.yml')))) {
        $Racine = $sous[0].FullName
    } else {
        Arreter 'docker-compose.yml introuvable dans l''archive.'
    }
}
try {
    Move-Item -LiteralPath $Racine -Destination $Destination -ErrorAction Stop
    if (Test-Path -LiteralPath $Partiel) { Remove-Item -LiteralPath $Partiel -Recurse -Force }
} catch {
    Arreter "impossible de créer $Destination : $($_.Exception.Message)"
}
Write-Host "Nouvelle version dans : $Destination"

# --- 4. Fichier .env ------------------------------------------------------------------------------------
Etape '4/6 Reprise du fichier .env'

$EnvNouveau = [System.IO.Path]::Combine($Destination, '.env')
Copy-Item -LiteralPath $EnvActuel -Destination $EnvNouveau
if ($PSBoundParameters.ContainsKey('DossierSauvegardes') -and -not (Lire-Env $EnvNouveau 'DOSSIER_SAUVEGARDES')) {
    Add-Content -LiteralPath $EnvNouveau -Value "`r`n# Ajouté par mettre-a-jour.ps1 : copie des sauvegardes visible dans Windows`r`nDOSSIER_SAUVEGARDES=$DossierSauvegardes" -Encoding UTF8
}
$Config = Docker-Dans $Destination @('compose', 'config', '--format', 'json')
if ($Config.Code -ne 0) { Arreter "configuration de la nouvelle version invalide : $($Config.Texte)" }
try { $Nom = [string](($Config.Texte | ConvertFrom-Json).name) } catch { $Nom = '' }
if ($Nom -ne $Projet) { Arreter "nom de projet inattendu dans la nouvelle configuration (« $Nom » au lieu de « $Projet »)." }
Write-Host 'Fichier .env repris ; configuration valide.'

# --- 5. Arrêt de l'ancienne version, démarrage de la nouvelle -------------------------------------------------
Etape '5/6 Arrêt de l''ancienne version et démarrage de la nouvelle'

if (-not $Oui) {
    $reponse = Read-Host "L'ancienne version va être arrêtée (aucune donnée effacée). Taper OUI pour continuer"
    if ($reponse.Trim() -ne 'OUI') { Arreter 'mise à jour annulée à votre demande. Le nouveau dossier peut être supprimé.' }
}
$arret = Docker-Dans $Actuel @('compose', 'down')
if ($arret.Code -ne 0) { Arreter "arrêt de l'ancienne version impossible : $($arret.Texte)" }
$script:AncienneArretee = $true

$demarrage = @('compose')
if ($AvecArgos) { $demarrage += @('--profile', 'hors-ligne') }
$demarrage += @('up', '-d', '--build')
Write-Host 'Construction et démarrage (plusieurs minutes la première fois)…'
$lancement = Docker-Dans $Destination $demarrage
if ($lancement.Code -ne 0) { Arreter "démarrage de la nouvelle version impossible :`n$($lancement.Texte)" }

# --- 6. Contrôle final ------------------------------------------------------------------------------------
Etape '6/6 Contrôle final'

$fin = (Get-Date).AddSeconds($DelaiControleSecondes)
$etat = $null
$dernier = ''
while ((Get-Date) -lt $fin) {
    $r = Docker-Dans $Destination @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'etat_installation', '--json')
    $debut = $r.Texte.IndexOf('{')
    $finJson = $r.Texte.LastIndexOf('}')
    if ($debut -ge 0 -and $finJson -gt $debut) {
        try { $etat = $r.Texte.Substring($debut, $finJson - $debut + 1) | ConvertFrom-Json } catch { $etat = $null }
    }
    if ($etat -and $etat.version -eq $VersionNouvelle) {
        $base = $etat.controles | Where-Object { $_.cle -eq 'base' } | Select-Object -First 1
        if ($base -and $base.niveau -eq 'ok') { break }
    }
    $dernier = $r.Texte
    $etat = $null
    Start-Sleep -Seconds 10
}
if (-not $etat) { Arreter "la nouvelle version ne répond pas correctement après $DelaiControleSecondes s. Dernière réponse :`n$dernier" }

foreach ($c in $etat.controles) {
    $couleur = 'Gray'
    if ($c.niveau -eq 'ok') { $couleur = 'Green' } elseif ($c.niveau -eq 'warning') { $couleur = 'Yellow' } elseif ($c.niveau -eq 'error') { $couleur = 'Red' }
    Write-Host ("  {0} : {1}" -f $c.libelle, $c.resume) -ForegroundColor $couleur
}
$Port = Lire-Env $EnvNouveau 'WEB_PORT'
if (-not $Port) { $Port = '8000' }
Write-Host ''
Write-Host "Mise à jour terminée : J-ed $VersionNouvelle, http://localhost:$Port" -ForegroundColor Green
Write-Host "Sauvegarde faite avant la mise à jour : $CopieLocale"
Write-Host "L'ancien dossier ($Actuel) n'a pas été modifié ; gardez-le jusqu'à ce que la nouvelle version vous convienne."
exit 0
