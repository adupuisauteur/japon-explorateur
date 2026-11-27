<#
.SYNOPSIS
    Réinitialise l'installation D'ESSAI de « Japon — Explorateur documentaire » (version 1.3.0).

.DESCRIPTION
    Ce script efface les conteneurs et les données (base, journal, captures, sauvegardes internes)
    de l'installation d'essai, puis la redémarre avec une base vide.
    Les paquets de langues Argos Translate (volume « argos-packages ») sont CONSERVÉS : ils sont
    longs à télécharger. Ils ne sont effacés qu'avec -Complet.
    Il REFUSE de s'exécuter s'il ne se trouve pas dans le dossier d'une installation d'essai :
    le nom du projet Docker doit contenir « essai » et ne jamais être celui de l'installation
    principale (« japon-explorateur », port 8000) ni celui de l'essai 1.2.0
    (« japon-explorateur-essai », port 8001). Ces deux installations ne sont jamais touchées.
    Seule exception : un essai 1.2.0 MIS À JOUR en 1.3.0 (projet « japon-explorateur-essai ») peut être
    réinitialisé si son fichier .env contient AUTORISER_NOM_PROJET=japon-explorateur-essai. L'installation
    principale ne peut jamais l'être.

.PARAMETER Complet
    Efface aussi les paquets Argos (volume argos-packages) et les images Docker de l'essai
    (application et service Argos), sans redémarrer. Utile avant de supprimer le dossier
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
# 2.0.2-rc5 (R18) : sortie en UTF-8, comme les autres scripts lancés par l'assistant J-ed (sinon les lettres
# accentuées y deviennent illisibles).
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
# 2.0.3 (Linux, décision D1) : ce script sert tel quel sous Windows (Windows PowerShell 5.1) et sous Linux
# (PowerShell 7, lancé par « pwsh -NoProfile -File »). La variable IsLinux n'existe pas sous 5.1 : lue ainsi, elle vaut faux.
$SousLinux = ((Get-Variable -Name IsLinux -ValueOnly -ErrorAction SilentlyContinue) -eq $true)
$TexteDockerLinux = 'Docker ne répond pas. Vérifiez qu''il est démarré (« sudo systemctl start docker ») et que votre compte est dans le groupe docker (après l''y avoir ajouté, se déconnecter puis se reconnecter), puis relancez ce script.'
$NomPrincipal = 'japon-explorateur'
$NomEssai120 = 'japon-explorateur-essai'
$NomAttendu = 'japon-explorateur-essai-130'
$PortAttendu = '8002'
# Volume des paquets Argos (décision E6) : conservé sauf avec -Complet.
$SuffixePaquets = '_argos-packages'
# 2.0.3 (Linux, décision D4) : refus de root. JED_UID_ACTUEL : réservé aux tests automatiques.
function Get-UidLinux {
    if ("$env:JED_UID_ACTUEL" -match '^\d+$') { return [int]$env:JED_UID_ACTUEL }
    $u = "$(& id -u 2>$null)".Trim()
    if ($u -match '^\d+$') { return [int]$u }
    return $null
}
$TexteRoot = 'ne lancez pas ce script en administrateur (sudo ou root) : les fichiers de J-ed appartiendraient à root. Relancez-le depuis votre compte, sans sudo.'

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

function Lire-Reponse([string]$Question) {
    # 2.0.2 : la réponse peut venir de l'assistant J-ed (entrée standard fournie par un programme), sinon de
    # l'écran comme avant (Read-Host n'est pas fiable sur une entrée redirigée sous Windows PowerShell 5.1).
    if ([Console]::IsInputRedirected) {
        # 2.0.2-rc5 (R19) : la question a été posée dans l'assistant ; ne pas afficher « tapez … » ici.
        $r = [Console]::In.ReadLine()
        if ($null -eq $r) { $r = '' }
        Write-Host 'Réponse donnée dans l''assistant J-ed.'
        return $r
    }
    return Read-Host $Question
}

function Docker-Sortie {
    # Exécute docker et renvoie la sortie standard (les avertissements de Docker sont ignorés).
    param([string[]]$Arguments)
    # 2.0.3 (essais Windows du 27/11) : sans docker, PowerShell écrivait son propre message d'erreur (en anglais)
    # et $LASTEXITCODE gardait la valeur d'une commande précédente. Docker absent = code 127 et un texte clair.
    if (-not (Get-Command docker -CommandType Application -ErrorAction SilentlyContinue)) {
        $absent = "docker n'est pas reconnu : Docker Desktop n'est pas installé."
        if ($SousLinux) { $absent = "docker n'est pas reconnu : Docker n'est pas installé." }
        return [pscustomobject]@{ Code = 127; Texte = $absent }
    }
    $sortie = & docker @Arguments 2>$null
    return [pscustomobject]@{ Code = $LASTEXITCODE; Texte = (($sortie | ForEach-Object { "$_" }) -join "`n").Trim() }
}

Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Réinitialisation d''une installation d''essai de J-ed' -ForegroundColor White
Write-Host "Dossier : $PSScriptRoot"

# --- 1. Contrôles de sécurité -------------------------------------------------------------------
Etape 'Contrôles de sécurité'
if ($SousLinux -and (Get-UidLinux) -eq 0) { Arreter $TexteRoot }

if (-not (Test-Path -LiteralPath 'docker-compose.yml') -or -not (Test-Path -LiteralPath 'VERSION')) {
    Arreter 'ce script doit se trouver dans le dossier de l''installation d''essai (à côté de docker-compose.yml et VERSION).'
}
$Version = (Get-Content -LiteralPath 'VERSION' -Raw).Trim()

if (-not (Test-Path -LiteralPath '.env')) {
    Arreter 'fichier .env absent : l''installation d''essai n''a pas encore été configurée (guide d''installation, étape 4).'
}

if ((Docker-Sortie @('info')).Code -ne 0) {
    if ($SousLinux) { Arreter $TexteDockerLinux }
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
    Arreter "ce dossier utilise le nom « $Projet », celui de l'INSTALLATION PRINCIPALE. Vérifiez COMPOSE_PROJECT_NAME dans .env (valeur attendue : $NomAttendu)."
}
# Essai 1.2.0 mis à jour en 1.3.0 : autorisé seulement par AUTORISER_NOM_PROJET égal au nom du projet.
$Autorisation = $null
try { $Autorisation = [string]$configuration.services.web.environment.AUTORISER_NOM_PROJET } catch { }
$EssaiMisAJour = ($Projet -eq $NomEssai120) -and ($Autorisation -eq $Projet)
if ($EssaiMisAJour) {
    Write-Host "Essai 1.2.0 mis à jour en 1.3.0 : réinitialisation autorisée par AUTORISER_NOM_PROJET." -ForegroundColor Yellow
}
if (($Projet -eq $NomEssai120) -and -not $EssaiMisAJour) {
    Arreter "ce dossier utilise le nom « $Projet », celui de l'INSTALLATION D'ESSAI 1.2.0. Vérifiez COMPOSE_PROJECT_NAME dans .env (valeur attendue : $NomAttendu)."
}
if ($Projet -notlike '*essai*') {
    Arreter "le nom du projet Docker « $Projet » ne contient pas « essai ». Par sécurité, seule une installation d'essai peut être réinitialisée."
}

$Port = $null
try { $Port = $configuration.services.web.ports[0].published } catch { }
if ("$Port" -eq '8000') {
    Arreter "cette installation utilise le port 8000, celui de l'installation principale. Vérifiez WEB_PORT dans .env (valeur attendue : $PortAttendu)."
}
if (("$Port" -eq '8001') -and -not $EssaiMisAJour) {
    Arreter "cette installation utilise le port 8001, celui de l'installation d'essai 1.2.0. Vérifiez WEB_PORT dans .env (valeur attendue : $PortAttendu)."
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
$paquets = @($volumes | Where-Object { $_ -eq "${Projet}${SuffixePaquets}" })
if ($Complet) {
    $aEffacer = $volumes
} else {
    $aEffacer = @($volumes | Where-Object { $_ -ne "${Projet}${SuffixePaquets}" })
}
$principaux = @((Docker-Sortie @('volume', 'ls', '-q', '--filter', "label=com.docker.compose.project=$NomPrincipal")).Texte -split "`n" |
    Where-Object { $_ })

Write-Host ''
Write-Host 'Seront EFFACÉS (installation d''essai) :' -ForegroundColor Yellow
Write-Host "  - les conteneurs du projet $Projet"
if ($aEffacer.Count -gt 0) {
    foreach ($v in $aEffacer) { Write-Host "  - le volume $v" }
} else {
    Write-Host '  - (aucun volume de données existant)'
}
Write-Host '    soit : base de données, journal des dysfonctionnements, captures, sauvegardes internes de l''essai'
if ($Complet) {
    Write-Host "  - les images Docker japon-explorateur:$Version et japon-explorateur-argos:$Version,"
    Write-Host '    sauf si d''autres installations de J-ed s''en servent (elles sont alors gardées)'
    if ($paquets.Count -gt 0) { Write-Host '    (dont les paquets de langues Argos : à retélécharger ou réinstaller ensuite)' }
} elseif ($paquets.Count -gt 0) {
    Write-Host ''
    Write-Host 'CONSERVÉ (essai) :' -ForegroundColor Green
    Write-Host "  - le volume $($paquets[0]) : paquets de langues Argos (effacé seulement avec -Complet)"
}
if ($principaux.Count -gt 0) {
    Write-Host ''
    Write-Host 'Ne seront PAS touchés (installation principale) :' -ForegroundColor Green
    foreach ($v in $principaux) { Write-Host "  - le volume $v" }
}

# --- 2. Sauvegarde facultative ------------------------------------------------------------------
$enMarche = (Docker-Sortie @('compose', '--profile', 'hors-ligne', 'ps', '--status', 'running', '--services')).Texte -split "`n"
$argosEnMarche = $enMarche -contains 'argos'
if (-not $SansSauvegarde -and ($enMarche -contains 'web')) {
    Etape 'Sauvegarde avant effacement (facultative)'
    Write-Host 'Pensez aussi à exporter vos diagnostics (Dysfonctionnements → Exporter un diagnostic) si vous voulez les envoyer.'
    $reponse = Lire-Reponse 'Faire une sauvegarde complète de l''essai dans le dossier « sauvegardes-essai » ? (O/N)'
    if ($reponse -match '^[oOyY]') {
        & docker compose exec -T web python manage.py backup --verify
        if ($LASTEXITCODE -ne 0) { Arreter 'la sauvegarde a échoué.' }
        $chemin = (Docker-Sortie @('compose', 'exec', '-T', 'web', 'sh', '-c', 'ls -t /data/backups/*.tar 2>/dev/null | head -n 1')).Texte
        if (-not $chemin) { Arreter 'fichier de sauvegarde introuvable dans le conteneur.' }
        New-Item -ItemType Directory -Force -Path 'sauvegardes-essai' | Out-Null
        # 2.0.3 : séparateur du système (sous Linux, « .\…\ » serait un nom de fichier, pas un dossier).
        $cibleCopie = 'sauvegardes-essai' + [System.IO.Path]::DirectorySeparatorChar
        & docker compose cp "web:$chemin" $cibleCopie
        if ($LASTEXITCODE -ne 0) { Arreter 'la copie de la sauvegarde hors du conteneur a échoué.' }
        Write-Host "Sauvegarde copiée dans : $([System.IO.Path]::Combine($PSScriptRoot, 'sauvegardes-essai'))" -ForegroundColor Green
    }
} elseif (-not $SansSauvegarde) {
    Write-Host ''
    Write-Host 'L''essai n''est pas démarré : aucune sauvegarde ne peut être faite avant l''effacement.' -ForegroundColor Yellow
}

# --- 3. Confirmation ----------------------------------------------------------------------------
Etape 'Confirmation'
$saisie = Lire-Reponse 'Pour effacer l''installation d''essai, tapez REINITIALISER (en majuscules)'
if ($saisie -cne 'REINITIALISER') {
    Write-Host 'Annulé : rien n''a été effacé.' -ForegroundColor Yellow
    exit 0
}

# --- 4. Effacement ------------------------------------------------------------------------------
Etape "Arrêt et effacement de $Projet"
# Arrêt de tous les services, y compris le service Argos facultatif (profil « hors-ligne »), sans effacer
# les volumes : ils sont effacés ensuite un par un, pour pouvoir conserver les paquets Argos.
& docker compose --profile hors-ligne down --remove-orphans
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERREUR : « docker compose down » a échoué. Lisez le message ci-dessus.' -ForegroundColor Red
    exit 1
}
foreach ($v in $aEffacer) {
    if (-not $v.StartsWith("${Projet}_")) { Arreter "volume inattendu « $v »." }
    & docker volume rm $v
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERREUR : le volume $v n'a pas pu être effacé. Lisez le message ci-dessus." -ForegroundColor Red
        exit 1
    }
}
$restants = @((Docker-Sortie @('volume', 'ls', '-q', '--filter', "label=com.docker.compose.project=$Projet")).Texte -split "`n" |
    Where-Object { $_ -and ($Complet -or $_ -ne "${Projet}${SuffixePaquets}") })
if ($restants.Count -gt 0) {
    Write-Host "ATTENTION : volumes encore présents : $($restants -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host 'Conteneurs et données de l''essai effacés.' -ForegroundColor Green
if (-not $Complet -and $paquets.Count -gt 0) { Write-Host 'Paquets de langues Argos conservés.' -ForegroundColor Green }

if ($Complet) {
    Etape "Suppression de l'image japon-explorateur:$Version"
    # 2.0.2 : deux installations de la même version partagent ces images. Si une autre installation de J-ed existe
    # sur cet ordinateur (ses données sont dans un volume « <nom>_db-data », même si elle est arrêtée), les images
    # sont gardées : la supprimer l'obligerait à reconstruire, Internet compris.
    $autres = @((Docker-Sortie @('volume', 'ls', '-q')).Texte -split "`n" | ForEach-Object { $_.Trim() } |
        Where-Object { $_ -like '*_db-data' -and -not $_.StartsWith("${Projet}_") })
    if ($autres.Count -gt 0) {
        Write-Host "Images gardées : d'autres installations de J-ed existent sur cet ordinateur et peuvent s'en servir ($($autres -join ', '))." -ForegroundColor Yellow
    } else {
        foreach ($nomImage in @("japon-explorateur:$Version", "japon-explorateur-argos:$Version")) {
            $image = Docker-Sortie @('image', 'inspect', $nomImage)
            if ($image.Code -eq 0) {
                & docker image rm $nomImage
            } else {
                Write-Host "Image $nomImage déjà absente."
            }
        }
    }
    Write-Host ''
    Write-Host 'Réinitialisation complète terminée : l''essai est arrêté et vide.' -ForegroundColor Green
    if ([Console]::IsInputRedirected) {
        # 2.0.2-rc5 (R21) : lancé par l'assistant J-ed : consignes de l'assistant, pas de la ligne de commande.
        Write-Host 'Pour vous en servir de nouveau : bouton « Démarrer » de l''assistant J-ed.'
    } else {
        Write-Host 'Pour une installation neuve : supprimez ce dossier (après avoir mis de côté « sauvegardes-essai » si besoin),'
        Write-Host 'puis reprenez le guide d''installation à l''étape 3. Pour réutiliser ce dossier : docker compose up -d --build'
    }
    exit 0
}

# --- 5. Redémarrage avec une base vide -----------------------------------------------------------
Etape 'Redémarrage avec une base vide'
# --build : l'image de l'application est (re)construite sur ce poste, jamais téléchargée.
if ($argosEnMarche) {
    # Le service Argos était démarré : il redémarre aussi, avec ses paquets conservés.
    & docker compose --profile hors-ligne up -d --build
} else {
    & docker compose up -d --build
}
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
