<#
.SYNOPSIS
    Réinitialise l'installation D'ESSAI de « Japon — Explorateur documentaire » (version 1.2.0).

.DESCRIPTION
    Ce script efface les conteneurs et les données (base, journal, captures, sauvegardes internes)
    de l'installation d'essai, puis la redémarre avec une base vide.
    Il REFUSE de s'exécuter s'il ne se trouve pas dans le dossier d'une installation d'essai :
    le nom du projet Docker doit contenir « essai » et ne jamais être celui de l'installation
    principale (« japon-explorateur »). L'installation principale n'est jamais touchée.

.PARAMETER Complet
    Efface aussi l'image Docker de l'essai, sans redémarrer. Utile avant de supprimer le dossier
    pour refaire une installation complète à partir de l'archive.

.PARAMETER SansSauvegarde
    Ne propose pas de sauvegarde de l'essai avant l'effacement.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\reinitialiser-essai.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\reinitialiser-essai.ps1 -Complet
#>
[CmdletBinding()]
param(
    [switch]$Complet,
    [switch]$SansSauvegarde
)

# Les messages d'erreur de Docker sont contrôlés par leur code de retour (compatible Windows PowerShell 5.1).
$ErrorActionPreference = 'Continue'
$NomPrincipal = 'japon-explorateur'

function Arreter([string]$Message) {
    Write-Host ''
    Write-Host "ARRÊT : $Message" -ForegroundColor Red
    Write-Host 'Rien n''a été effacé.' -ForegroundColor Red
    exit 1
}

function Etape([string]$Message) {
    Write-Host ''
    Write-Host "== $Message" -ForegroundColor Cyan
}

function Docker-Sortie {
    # Exécute docker et renvoie la sortie standard (les avertissements de Docker sont ignorés).
    param([string[]]$Arguments)
    $sortie = & docker @Arguments 2>$null
    return [pscustomobject]@{ Code = $LASTEXITCODE; Texte = (($sortie | ForEach-Object { "$_" }) -join "`n").Trim() }
}

Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Réinitialisation de l''installation d''essai — Japon · Explorateur documentaire' -ForegroundColor White
Write-Host "Dossier : $PSScriptRoot"

# --- 1. Contrôles de sécurité -------------------------------------------------------------------
Etape 'Contrôles de sécurité'

if (-not (Test-Path -LiteralPath 'docker-compose.yml') -or -not (Test-Path -LiteralPath 'VERSION')) {
    Arreter 'ce script doit se trouver dans le dossier de l''installation d''essai (à côté de docker-compose.yml et VERSION).'
}
$Version = (Get-Content -LiteralPath 'VERSION' -Raw).Trim()

if (-not (Test-Path -LiteralPath '.env')) {
    Arreter 'fichier .env absent : l''installation d''essai n''a pas encore été configurée (guide d''installation, étape 4).'
}

if ((Docker-Sortie @('info')).Code -ne 0) {
    Arreter 'Docker Desktop ne répond pas. Démarrez-le, attendez « Engine running », puis relancez ce script.'
}

$config = Docker-Sortie @('compose', 'config', '--format', 'json')
if ($config.Code -ne 0 -or -not $config.Texte) {
    Arreter 'impossible de lire la configuration Docker de ce dossier (fichier .env incomplet ?). Lancez « docker compose config » pour voir le message.'
}
try {
    $configuration = $config.Texte | ConvertFrom-Json
} catch {
    Arreter 'configuration Docker illisible.'
}
$Projet = [string]$configuration.name

if (-not $Projet) {
    Arreter 'nom du projet Docker introuvable.'
}
if ($Projet -eq $NomPrincipal) {
    Arreter "ce dossier utilise le nom « $Projet », celui de l'INSTALLATION PRINCIPALE. Vérifiez COMPOSE_PROJECT_NAME dans .env (valeur attendue : japon-explorateur-essai)."
}
if ($Projet -notlike '*essai*') {
    Arreter "le nom du projet Docker « $Projet » ne contient pas « essai ». Par sécurité, seule une installation d'essai peut être réinitialisée."
}

$Port = $null
try { $Port = $configuration.services.web.ports[0].published } catch { }
if ("$Port" -eq '8000') {
    Arreter 'cette installation utilise le port 8000, celui de l''installation principale. Vérifiez WEB_PORT dans .env (valeur attendue : 8001).'
}

Write-Host "Projet Docker : $Projet (version $Version, port $Port)" -ForegroundColor Green

# Ce qui sera effacé : uniquement les volumes de CE projet.
$volumes = @((Docker-Sortie @('volume', 'ls', '-q', '--filter', "label=com.docker.compose.project=$Projet")).Texte -split "`n" |
    Where-Object { $_ })
foreach ($v in $volumes) {
    if (-not $v.StartsWith("${Projet}_")) {
        Arreter "volume inattendu « $v » : nom non conforme au projet d'essai."
    }
}
$principaux = @((Docker-Sortie @('volume', 'ls', '-q', '--filter', "label=com.docker.compose.project=$NomPrincipal")).Texte -split "`n" |
    Where-Object { $_ })

Write-Host ''
Write-Host 'Seront EFFACÉS (installation d''essai) :' -ForegroundColor Yellow
Write-Host "  - les conteneurs du projet $Projet"
if ($volumes.Count -gt 0) {
    foreach ($v in $volumes) { Write-Host "  - le volume $v" }
} else {
    Write-Host '  - (aucun volume de données existant)'
}
Write-Host '    soit : base de données, journal des dysfonctionnements, captures, sauvegardes internes de l''essai'
if ($Complet) { Write-Host "  - l'image Docker japon-explorateur:$Version" }
if ($principaux.Count -gt 0) {
    Write-Host ''
    Write-Host 'Ne seront PAS touchés (installation principale) :' -ForegroundColor Green
    foreach ($v in $principaux) { Write-Host "  - le volume $v" }
}

# --- 2. Sauvegarde facultative ------------------------------------------------------------------
$enMarche = (Docker-Sortie @('compose', 'ps', '--status', 'running', '--services')).Texte -split "`n"
if (-not $SansSauvegarde -and ($enMarche -contains 'web')) {
    Etape 'Sauvegarde avant effacement (facultative)'
    Write-Host 'Pensez aussi à exporter vos diagnostics (Dysfonctionnements → Exporter un diagnostic) si vous voulez les envoyer.'
    $reponse = Read-Host 'Faire une sauvegarde complète de l''essai dans le dossier « sauvegardes-essai » ? (O/N)'
    if ($reponse -match '^[oOyY]') {
        & docker compose exec -T web python manage.py backup --verify
        if ($LASTEXITCODE -ne 0) { Arreter 'la sauvegarde a échoué.' }
        $chemin = (Docker-Sortie @('compose', 'exec', '-T', 'web', 'sh', '-c', 'ls -t /data/backups/*.tar 2>/dev/null | head -n 1')).Texte
        if (-not $chemin) { Arreter 'fichier de sauvegarde introuvable dans le conteneur.' }
        New-Item -ItemType Directory -Force -Path 'sauvegardes-essai' | Out-Null
        & docker compose cp "web:$chemin" '.\sauvegardes-essai\'
        if ($LASTEXITCODE -ne 0) { Arreter 'la copie de la sauvegarde hors du conteneur a échoué.' }
        Write-Host "Sauvegarde copiée dans : $PSScriptRoot\sauvegardes-essai" -ForegroundColor Green
    }
} elseif (-not $SansSauvegarde) {
    Write-Host ''
    Write-Host 'L''essai n''est pas démarré : aucune sauvegarde ne peut être faite avant l''effacement.' -ForegroundColor Yellow
}

# --- 3. Confirmation ----------------------------------------------------------------------------
Etape 'Confirmation'
$saisie = Read-Host 'Pour effacer l''installation d''essai, tapez REINITIALISER (en majuscules)'
if ($saisie -cne 'REINITIALISER') {
    Write-Host 'Annulé : rien n''a été effacé.' -ForegroundColor Yellow
    exit 0
}

# --- 4. Effacement ------------------------------------------------------------------------------
Etape "Arrêt et effacement de $Projet"
& docker compose down -v --remove-orphans
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERREUR : « docker compose down -v » a échoué. Lisez le message ci-dessus.' -ForegroundColor Red
    exit 1
}
$restants = @((Docker-Sortie @('volume', 'ls', '-q', '--filter', "label=com.docker.compose.project=$Projet")).Texte -split "`n" |
    Where-Object { $_ })
if ($restants.Count -gt 0) {
    Write-Host "ATTENTION : volumes encore présents : $($restants -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host 'Conteneurs et données de l''essai effacés.' -ForegroundColor Green

if ($Complet) {
    Etape "Suppression de l'image japon-explorateur:$Version"
    $image = Docker-Sortie @('image', 'inspect', "japon-explorateur:$Version")
    if ($image.Code -eq 0) {
        & docker image rm "japon-explorateur:$Version"
    } else {
        Write-Host 'Image déjà absente.'
    }
    Write-Host ''
    Write-Host 'Réinitialisation complète terminée.' -ForegroundColor Green
    Write-Host 'Pour une installation neuve : supprimez ce dossier (après avoir mis de côté « sauvegardes-essai » si besoin),'
    Write-Host 'puis reprenez le guide d''installation à l''étape 3. Pour réutiliser ce dossier : docker compose up -d --build'
    exit 0
}

# --- 5. Redémarrage avec une base vide -----------------------------------------------------------
Etape 'Redémarrage avec une base vide'
# --build : l'image de l'application est (re)construite sur ce poste, jamais téléchargée.
& docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERREUR : le redémarrage a échoué. Lisez le message ci-dessus, ou lancez « docker compose logs --tail 100 web ».' -ForegroundColor Red
    exit 1
}
$adresse = "http://localhost:$Port/"
Write-Host "Attente de l'application sur $adresse (2 minutes au plus)…"
$pret = $false
for ($i = 0; $i -lt 40 -and -not $pret; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri ($adresse + 'hors-ligne/') -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $pret = $true }
    } catch { }
}
Write-Host ''
if ($pret) {
    Write-Host "Terminé. Ouvrez $adresse : l'assistant de première configuration va créer le compte administrateur." -ForegroundColor Green
} else {
    Write-Host "L'application ne répond pas encore. Patientez une minute puis ouvrez $adresse ;" -ForegroundColor Yellow
    Write-Host 'si rien ne s''affiche : docker compose logs --tail 100 web'
}
