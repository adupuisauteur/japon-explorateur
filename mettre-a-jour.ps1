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
      5. construction de la nouvelle version PENDANT QUE L'ANCIENNE RESTE EN SERVICE (2.0.1) : si Docker ne
         joint pas Internet, le script s'arrête ici et l'ancienne version n'a pas été touchée ;
      6. arrêt de l'ancienne version (sans effacer aucune donnée : « docker compose down » sans -v), puis
         démarrage de la nouvelle, sans reconstruire ;
      7. contrôle final : version attendue et base de données à jour (manage.py etat_installation).
    Si la nouvelle version ne démarre pas ou ne répond pas (étapes 6 et 7), le script revient tout seul à
    l'ancienne version (2.0.1) : arrêt de la nouvelle, redémarrage de l'ancienne depuis l'ancien dossier.
    Les données (base, fichiers, paquets Argos) sont dans les volumes Docker du projet : elles sont reprises
    telles quelles parce que le nom du projet (COMPOSE_PROJECT_NAME) ne change pas.

    Journal (2.0.1) : chaque mise à jour écrit le fichier mise-a-jour-AAAAMMJJ-HHMMSS.log dans le dossier des
    sauvegardes. Chaque ligne commence par la date, l'heure et un repère fixe : ETAPE, INFO, ATTENTION, COMMANDE,
    RESULTAT, ERREUR, FIN ; les lignes de suite commencent par « | ». La configuration complète de Docker (qui
    contient les mots de passe) n'y est jamais écrite.

    Codes de sortie (2.0.1) :
      0  mise à jour réussie ;
      1  arrêt pendant les contrôles, la sauvegarde, la décompression ou la reprise du .env : l'installation
         actuelle n'a pas été modifiée ;
      2  mise à jour annulée à votre demande (pas de « OUI ») : l'ancienne version est toujours en service ;
      3  construction de la nouvelle version impossible : l'ancienne version est toujours en service ;
      4  la nouvelle version n'a pas démarré correctement ; retour à l'ancienne version réussi ;
      5  la nouvelle version n'a pas démarré correctement et le retour à l'ancienne a échoué : intervention
         nécessaire (le message et le journal disent quoi faire).

.PARAMETER Archive
    Chemin de l'archive de la nouvelle version (.zip). Le fichier d'empreinte (.sha256) doit être à côté.

.PARAMETER Actuel
    Dossier de l'installation actuelle (celui qui contient docker-compose.yml et .env).

.PARAMETER Destination
    Dossier de la nouvelle version. Par défaut : à côté du dossier actuel, nommé comme l'archive.

.PARAMETER DossierSauvegardes
    Dossier de l'ordinateur où copier la sauvegarde faite avant la mise à jour, et où écrire le journal. Par
    défaut : DOSSIER_SAUVEGARDES du fichier .env s'il existe, sinon un dossier « sauvegardes » à côté du dossier
    actuel.

.PARAMETER Oui
    Ne pas demander de confirmation avant l'arrêt de l'ancienne version.

.PARAMETER DelaiControle
    Temps maximal, en secondes, laissé à la nouvelle version pour répondre au contrôle final (300 par défaut).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.1.zip -Actuel D:\Exemple\japon-explorateur-2.0.0
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$Actuel,
    [string]$Destination,
    [string]$DossierSauvegardes,
    [switch]$Oui,
    [int]$DelaiControle = 300
)

# Les codes de retour de Docker sont contrôlés un par un (compatible Windows PowerShell 5.1).
$ErrorActionPreference = 'Continue'
# Windows PowerShell 5.1 lit la sortie de docker avec la page de code de la console (850, 437…) : les accents
# arrivaient abîmés (« Terminée » lu « Termin├®e », constaté le 15 novembre 2026). La sortie est lue en UTF-8.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
$NomsProteges = @('japon-explorateur', 'japon-explorateur-essai')
$VersionMinimale = [version]'1.3.0'   # première version qui accepte AUTORISER_NOM_PROJET
$DelaiRetourSecondes = 120             # temps laissé à l'ancienne version pour redémarrer en cas de retour

# 2.0.1 : codes de sortie (voir l'aide du script), lus par l'aide et, plus tard, par l'assistant graphique.
$CodeArret = 1
$CodeAnnule = 2
$CodeConstruction = 3
$CodeRetourReussi = 4
$CodeRetourImpossible = 5

$script:AncienneArretee = $false
$script:SauvegardeLocale = $null
$script:Journal = $null
$script:Tampon = New-Object System.Collections.Generic.List[string]
$script:ImagesAnciennes = [ordered]@{}
$Utf8SansBom = New-Object System.Text.UTF8Encoding($false)

# --- Journal (2.0.1) --------------------------------------------------------------------------------------
function Ecrire-Journal([string]$Repere, [string]$Texte) {
    # Une ligne par événement : « AAAA-MM-JJ HH:MM:SS REPERE texte » ; les lignes de suite commencent par « | ».
    $heure = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $lignes = @(("$Texte" -replace "`r", '') -split "`n")
    $bloc = "$heure $Repere $($lignes[0])`r`n"
    for ($i = 1; $i -lt $lignes.Count; $i++) { $bloc += "    | $($lignes[$i])`r`n" }
    if ($script:Journal) {
        try { [System.IO.File]::AppendAllText($script:Journal, $bloc, $Utf8SansBom) } catch { }
    } else {
        $script:Tampon.Add($bloc)   # journal pas encore ouvert : écrit dès qu'il le sera
    }
}

function Ouvrir-Journal([string]$Dossier) {
    New-Item -ItemType Directory -Force -Path $Dossier -ErrorAction Stop | Out-Null
    $chemin = [System.IO.Path]::Combine($Dossier, "mise-a-jour-$(Get-Date -Format 'yyyyMMdd-HHmmss').log")
    [System.IO.File]::WriteAllText($chemin, ($script:Tampon -join ''), $Utf8SansBom)
    $script:Journal = $chemin
}

function Dire([string]$Message, [string]$Couleur) {
    if ($Couleur) { Write-Host $Message -ForegroundColor $Couleur } else { Write-Host $Message }
    Ecrire-Journal 'INFO' $Message
}

function Avertir([string]$Message) {
    Write-Host $Message -ForegroundColor Yellow
    Ecrire-Journal 'ATTENTION' $Message
}

function Terminer([int]$Code, [string]$Resume) {
    Ecrire-Journal 'FIN' "code=$Code $Resume"
    if ($script:Journal) { Write-Host "Journal de la mise à jour : $script:Journal" }
    exit $Code
}

function Arreter([string]$Message, [int]$Code = $CodeArret) {
    # Arrêt AVANT l'arrêt de l'ancienne version. Après, c'est Revenir qui s'en charge.
    if ($script:AncienneArretee) { Revenir $Message }
    Write-Host ''
    Write-Host "ARRÊT : $Message" -ForegroundColor Red
    Ecrire-Journal 'ERREUR' $Message
    if ($Code -eq $CodeConstruction -or $Code -eq $CodeAnnule) {
        Write-Host 'L''ancienne version est toujours en service : rien n''a été arrêté.' -ForegroundColor Yellow
        Write-Host "Le dossier de la nouvelle version ($Destination) peut être supprimé avant de relancer le script." -ForegroundColor Yellow
    } else {
        Write-Host 'L''installation actuelle n''a pas été modifiée.' -ForegroundColor Yellow
    }
    Terminer $Code 'arrêt sans changement de l''installation actuelle'
}

function Etape([string]$Message) {
    Write-Host ''
    Write-Host "== $Message" -ForegroundColor Cyan
    Ecrire-Journal 'ETAPE' $Message
}

function Docker-Dans {
    # Exécute docker dans le dossier indiqué et renvoie le code et la sortie (standard et erreurs).
    # -Discret : la sortie n'est pas écrite dans le journal (configuration complète, avec les mots de passe).
    param([string]$Dossier, [string[]]$Arguments, [switch]$Discret)
    Ecrire-Journal 'COMMANDE' "$Dossier > docker $($Arguments -join ' ')"
    Push-Location -LiteralPath $Dossier
    try {
        $sortie = & docker @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $texte = (($sortie | ForEach-Object { "$_" }) -join "`n").Trim()
    if ($Discret) { Ecrire-Journal 'RESULTAT' "code=$code (sortie non journalisée)" }
    elseif ($texte) { Ecrire-Journal 'RESULTAT' "code=$code`n$texte" }
    else { Ecrire-Journal 'RESULTAT' "code=$code" }
    return [pscustomobject]@{ Code = $code; Texte = $texte }
}

function Lire-Env([string]$Fichier, [string]$Nom) {
    # Comme Docker Compose : si une variable figure plusieurs fois, c'est la DERNIÈRE ligne qui compte.
    $valeur = ''
    foreach ($ligne in (Get-Content -LiteralPath $Fichier -Encoding UTF8)) {
        if ($ligne -match "^\s*$Nom\s*=(.*)$") { $valeur = $Matches[1].Trim() }
    }
    return $valeur
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

function Script-Different([string]$Zip) {
    # 2.0.0 (lot 6) : le script lancé est-il celui de l'archive ? Un ancien script garde d'anciens défauts
    # (16 novembre 2026 : celui du lot 0 ajoutait une ligne COMPOSE_PROFILES=hors-ligne à chaque mise à jour).
    if (-not $PSCommandPath) { return $false }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $z = [System.IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        $entree = $z.Entries | Where-Object { $_.FullName -match '^([^/]+/)?mettre-a-jour\.ps1$' } | Select-Object -First 1
        if (-not $entree) { return $false }
        $flux = $entree.Open()
        try {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            $dansArchive = [System.BitConverter]::ToString($sha.ComputeHash($flux)).Replace('-', '')
        } finally { $flux.Close() }
    } finally { $z.Dispose() }
    $lance = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash
    return $dansArchive -ne $lance
}

function Images-Du-Dossier([string]$Dossier) {
    # Noms des images utilisées par l'installation du dossier (services des profils actifs du .env).
    $r = Docker-Dans $Dossier @('compose', 'config', '--images')
    if ($r.Code -ne 0) { return $null }
    $liste = @($r.Texte -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique)
    return ,$liste   # la virgule garde un tableau, même vide ou d'un seul élément
}

function Id-Image([string]$Dossier, [string]$Nom) {
    # Identifiant de l'image (sha256:…), ou $null si elle n'existe pas sur cet ordinateur.
    # Format sans guillemets : Windows PowerShell 5.1 retire les guillemets doubles des arguments de docker.
    $r = Docker-Dans $Dossier @('image', 'inspect', '--format', '{{.Id}}', $Nom)
    if ($r.Code -ne 0) { return $null }
    return (($r.Texte -split "`n")[0]).Trim()
}

function Revenir([string]$Raison) {
    # 2.0.1 : retour automatique à l'ancienne version, sans question. Aucune donnée n'est effacée.
    Write-Host ''
    Write-Host "ARRÊT : $Raison" -ForegroundColor Red
    Ecrire-Journal 'ERREUR' $Raison
    Etape 'Retour automatique à l''ancienne version'
    $arretNouvelle = Docker-Dans $Destination @('compose', 'down')
    if ($arretNouvelle.Code -ne 0) { Avertir "Arrêt de la nouvelle version incomplet : $($arretNouvelle.Texte)" }
    # Même numéro de version (versions candidates) : la construction a repris l'étiquette de l'ancienne image.
    # On lui rend l'image d'avant la mise à jour, relevée à l'étape 5.
    foreach ($nom in @($script:ImagesAnciennes.Keys)) {
        $avant = $script:ImagesAnciennes[$nom]
        if ((Id-Image $Actuel $nom) -ne $avant) {
            $t = Docker-Dans $Actuel @('tag', $avant, $nom)
            if ($t.Code -eq 0) { Dire "Image $nom remise comme avant la mise à jour." }
            else { Avertir "Image $nom : impossible de remettre l'image d'avant la mise à jour ($($t.Texte))." }
        }
    }
    $relance = Docker-Dans $Actuel @('compose', 'up', '-d')
    $ok = $false
    if ($relance.Code -eq 0) {
        $fin = (Get-Date).AddSeconds($DelaiRetourSecondes)
        while ((Get-Date) -lt $fin) {
            $etatAncien = Docker-Dans $Actuel @('compose', 'ps', '--services', '--status', 'running')
            $enMarche = @($etatAncien.Texte -split "`n" | ForEach-Object { $_.Trim() })
            if ($etatAncien.Code -eq 0 -and $enMarche -contains 'web') { $ok = $true; break }
            Start-Sleep -Seconds 5
        }
    }
    $PortAncien = Lire-Env $EnvActuel 'WEB_PORT'
    if (-not $PortAncien) { $PortAncien = '8000' }
    Write-Host ''
    if ($ok) {
        Write-Host "Retour réussi : l'ancienne version ($VersionActuelle) est de nouveau en service, http://localhost:$PortAncien" -ForegroundColor Green
        Ecrire-Journal 'INFO' "Retour réussi : ancienne version $VersionActuelle en service."
        Write-Host "Aucune donnée n'a été effacée. Sauvegarde faite avant la mise à jour : $script:SauvegardeLocale"
        Write-Host "Le dossier de la nouvelle version ($Destination) peut être gardé pour comprendre l'échec, puis supprimé."
        Terminer $CodeRetourReussi 'nouvelle version en échec, retour à l''ancienne réussi'
    }
    Write-Host 'Le retour automatique à l''ancienne version n''a pas abouti. Aucune donnée n''a été effacée.' -ForegroundColor Red
    if ($relance.Code -ne 0) { Write-Host $relance.Texte }
    Write-Host 'Pour remettre l''ancienne version en service :' -ForegroundColor Yellow
    Write-Host "  1. dans « $Destination » : docker compose down" -ForegroundColor Yellow
    Write-Host "  2. dans « $Actuel » : docker compose up -d" -ForegroundColor Yellow
    if ($script:SauvegardeLocale) {
        Write-Host "  3. si l'ancienne version ne démarre pas (base déjà mise à jour), restaurez la sauvegarde :" -ForegroundColor Yellow
        Write-Host "     $script:SauvegardeLocale (guide d'installation, « Restaurer une sauvegarde »)" -ForegroundColor Yellow
    }
    Terminer $CodeRetourImpossible 'nouvelle version en échec, retour à l''ancienne impossible : intervention nécessaire'
}

Write-Host 'Mise à jour de J-ed' -ForegroundColor White
Ecrire-Journal 'INFO' "Mise à jour de J-ed ; archive : $Archive ; installation actuelle : $Actuel"

# --- 1. Contrôles ---------------------------------------------------------------------------------
Etape '1/7 Contrôles'

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

# 2.0.1 : le dossier des sauvegardes est connu dès le début, pour y écrire le journal de la mise à jour.
if (-not $DossierSauvegardes) { $DossierSauvegardes = Lire-Env $EnvActuel 'DOSSIER_SAUVEGARDES' }
if (-not $DossierSauvegardes) { $DossierSauvegardes = [System.IO.Path]::Combine((Split-Path -Parent $Actuel), 'sauvegardes') }
try {
    Ouvrir-Journal $DossierSauvegardes
} catch {
    Arreter "impossible d'écrire dans le dossier des sauvegardes $DossierSauvegardes : $($_.Exception.Message)"
}
Write-Host "Journal de la mise à jour : $script:Journal"

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
Dire "Empreinte de l'archive vérifiée : $Calculee"

$VersionNouvelle = Version-Archive $Archive
$ScriptAncien = Script-Different $Archive
if ($ScriptAncien) {
    Avertir ("Attention : ce script de mise à jour n'est pas celui de l'archive ; il peut contenir d'anciens défauts. " +
        "Après la mise à jour, remplacez « $PSCommandPath » par le fichier mettre-a-jour.ps1 du nouveau dossier.")
}
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
    Avertir "Attention : l'archive contient la même version que l'installation actuelle ($VersionActuelle) : réinstallation."
}
Dire "Version actuelle : $VersionActuelle ; nouvelle version : $VersionNouvelle"

$Projet = Lire-Env $EnvActuel 'COMPOSE_PROJECT_NAME'
if (-not $Projet) { Arreter 'COMPOSE_PROJECT_NAME absent du fichier .env actuel : impossible de retrouver les données.' }
if ($NomsProteges -contains $Projet) {
    $Autorisation = Lire-Env $EnvActuel 'AUTORISER_NOM_PROJET'
    if ($Autorisation -ne $Projet) {
        Arreter "le projet « $Projet » est protégé. Pour le mettre à jour en gardant ses données, ajoutez d'abord la ligne AUTORISER_NOM_PROJET=$Projet dans $EnvActuel, puis relancez ce script."
    }
    Avertir "Projet protégé « $Projet » : mise à jour autorisée par AUTORISER_NOM_PROJET."
}
Dire "Projet Docker : $Projet (ses volumes de données seront repris)"

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

if ((Docker-Dans $Actuel @('info') -Discret).Code -ne 0) {
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
Etape '2/7 Sauvegarde de l''installation actuelle'

$Sauvegarde = Docker-Dans $Actuel @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'backup', '--verify')
Write-Host $Sauvegarde.Texte
# Les versions 1.2.0 et 1.3.0 affichent « Échec » sans code d'erreur : le texte est aussi contrôlé.
# Les motifs tolèrent un accent abîmé (1 à 3 caractères à la place de « é » ou « É ») : ceinture et bretelles.
if ($Sauvegarde.Code -ne 0 -or $Sauvegarde.Texte -notmatch 'Termin.{1,3}e : ' -or $Sauvegarde.Texte -notmatch 'Int.{1,3}grit.{1,3} v.{1,3}rifi' -or $Sauvegarde.Texte -cmatch '(?m)^.{1,3}chec :') {
    Arreter 'la sauvegarde a échoué (message ci-dessus) : rien n''a été mis à jour.'
}
if ($Sauvegarde.Texte -notmatch 'Termin.{1,3}e : (\S+\.tar)') { Arreter 'chemin de la sauvegarde introuvable dans la réponse.' }
$CheminDocker = $Matches[1]
$NomSauvegarde = Split-Path -Leaf $CheminDocker

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
Dire "Sauvegarde copiée et vérifiée : $CopieLocale" 'Green'

# --- 3. Décompression ---------------------------------------------------------------------------------
Etape '3/7 Décompression de la nouvelle version'

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
Dire "Nouvelle version dans : $Destination"

# --- 4. Fichier .env ------------------------------------------------------------------------------------
Etape '4/7 Reprise du fichier .env'

$EnvNouveau = [System.IO.Path]::Combine($Destination, '.env')
Copy-Item -LiteralPath $EnvActuel -Destination $EnvNouveau
if ($PSBoundParameters.ContainsKey('DossierSauvegardes') -and -not (Lire-Env $EnvNouveau 'DOSSIER_SAUVEGARDES')) {
    Add-Content -LiteralPath $EnvNouveau -Value "`r`n# Ajouté par mettre-a-jour.ps1 : copie des sauvegardes visible dans Windows`r`nDOSSIER_SAUVEGARDES=$DossierSauvegardes" -Encoding UTF8
}
# 2.0.0 (lot 7) : Argos fait partie de l'installation standard. La ligne COMPOSE_PROFILES le démarre avec J-ed ;
# elle n'est ajoutée que si elle manque. Laissée vide (« COMPOSE_PROFILES= »), elle désactive Argos : respecté.
$LigneProfils = @(Get-Content -LiteralPath $EnvNouveau -Encoding UTF8 | Where-Object { $_ -match '^\s*COMPOSE_PROFILES\s*=' })
$Profils = Lire-Env $EnvNouveau 'COMPOSE_PROFILES'
if ($LigneProfils.Count -gt 1) {
    Avertir "Attention : la ligne COMPOSE_PROFILES figure $($LigneProfils.Count) fois dans .env ; seule la dernière compte (COMPOSE_PROFILES=$Profils). Gardez-en une seule."
}
if ($LigneProfils.Count -eq 0) {
    Add-Content -LiteralPath $EnvNouveau -Value "`r`n# Ajouté par mettre-a-jour.ps1 : Argos (traduction hors ligne) démarre avec J-ed. Pour ne pas le démarrer`r`n# (poste à mémoire limitée), laissez la ligne vide : COMPOSE_PROFILES=`r`nCOMPOSE_PROFILES=argos" -Encoding UTF8
    Dire 'Argos fait désormais partie de l''installation standard : ligne COMPOSE_PROFILES=argos ajoutée au nouveau .env.'
    $Profils = 'argos'
} elseif ($Profils -notmatch '(^|,)\s*(argos|hors-ligne)\s*(,|$)') {
    Avertir "Argos reste désactivé (COMPOSE_PROFILES=$Profils dans .env) : il ne sera pas démarré."
    if ($AvecArgos) { Avertir 'Il était pourtant en service : ajoutez « argos » à cette ligne pour le garder.' }
}
# La configuration complète contient les mots de passe du .env : sa sortie n'est pas journalisée.
$Config = Docker-Dans $Destination @('compose', 'config', '--format', 'json') -Discret
if ($Config.Code -ne 0) { Arreter "configuration de la nouvelle version invalide (commande « docker compose config » dans $Destination)." }
try { $Nom = [string](($Config.Texte | ConvertFrom-Json).name) } catch { $Nom = '' }
if ($Nom -ne $Projet) { Arreter "nom de projet inattendu dans la nouvelle configuration (« $Nom » au lieu de « $Projet »)." }
Dire 'Fichier .env repris ; configuration valide.'

# --- 5. Construction, pendant que l'ancienne version reste en service (2.0.1) ----------------------------
Etape '5/7 Construction de la nouvelle version (l''ancienne reste en service)'

# Images de l'ancienne version, relevées pour pouvoir revenir en arrière sans rien reconstruire. Avec le même
# numéro de version (versions candidates), la construction reprend l'étiquette : le retour la remettra.
$ImagesActuelles = Images-Du-Dossier $Actuel
if ($null -eq $ImagesActuelles) {
    Avertir 'Images de la version actuelle impossibles à lister : en cas de retour, Docker devra peut-être les reconstruire.'
} else {
    $absentes = @()
    foreach ($nom in $ImagesActuelles) {
        $id = Id-Image $Actuel $nom
        if ($id) { $script:ImagesAnciennes[$nom] = $id } else { $absentes += $nom }
    }
    if ($absentes.Count -gt 0) {
        Avertir "Image(s) de la version actuelle introuvable(s) sur cet ordinateur : $($absentes -join ', '). En cas de retour, Docker devra les reconstruire ou les télécharger."
    }
}

Dire 'Construction de la nouvelle version (plusieurs minutes la première fois). L''ancienne version reste utilisable pendant ce temps…'
$Construction = Docker-Dans $Destination @('compose', 'build')
if ($Construction.Code -ne 0) {
    $fin = $Construction.Texte
    if ($fin.Length -gt 3000) { $fin = '…' + $fin.Substring($fin.Length - 3000) }
    Write-Host $fin
    Arreter ("construction de la nouvelle version impossible (message ci-dessus). Le plus souvent, Docker ne joint pas " +
        "Internet : essayez « docker pull python:3.12-slim-bookworm » ; derrière un proxy, voyez l'aide « Mettre à jour J-ed ».") $CodeConstruction
}
$ImagesNouvelles = Images-Du-Dossier $Destination
if ($null -eq $ImagesNouvelles) { Arreter 'images de la nouvelle version impossibles à lister (docker compose config --images).' $CodeConstruction }
$Manquantes = @($ImagesNouvelles | Where-Object { -not (Id-Image $Destination $_) })
if ($Manquantes.Count -gt 0) {
    # Images fournies telles quelles (base de données, Redis, IA locale) absentes de cet ordinateur : téléchargées
    # maintenant, avant d'arrêter quoi que ce soit.
    Dire "Téléchargement des images manquantes : $($Manquantes -join ', ')…"
    $null = Docker-Dans $Destination @('compose', 'pull', '--ignore-buildable')
    $Manquantes = @($ImagesNouvelles | Where-Object { -not (Id-Image $Destination $_) })
    if ($Manquantes.Count -gt 0) {
        Arreter ("image(s) introuvable(s) : $($Manquantes -join ', '). Docker ne joint sans doute pas Internet : essayez " +
            "« docker pull python:3.12-slim-bookworm » ; derrière un proxy, voyez l'aide « Mettre à jour J-ed ».") $CodeConstruction
    }
}
Dire 'Nouvelle version prête : toutes ses images sont sur cet ordinateur.' 'Green'

# --- 6. Arrêt de l'ancienne version, démarrage de la nouvelle -------------------------------------------------
Etape '6/7 Arrêt de l''ancienne version et démarrage de la nouvelle'

if (-not $Oui) {
    $reponse = Read-Host "L'ancienne version va être arrêtée (aucune donnée effacée). Taper OUI pour continuer"
    if ($reponse.Trim() -ne 'OUI') { Arreter 'mise à jour annulée à votre demande.' $CodeAnnule }
}
$script:AncienneArretee = $true
$arret = Docker-Dans $Actuel @('compose', 'down')
if ($arret.Code -ne 0) { Revenir "arrêt de l'ancienne version incomplet : $($arret.Texte)" }

# Les services démarrés (Argos compris) sont ceux que décide le fichier .env (COMPOSE_PROFILES). Pas de
# reconstruction : les images ont été construites à l'étape 5.
Dire 'Démarrage de la nouvelle version…'
$lancement = Docker-Dans $Destination @('compose', 'up', '-d')
if ($lancement.Code -ne 0) { Revenir "démarrage de la nouvelle version impossible :`n$($lancement.Texte)" }

# --- 7. Contrôle final ------------------------------------------------------------------------------------
Etape '7/7 Contrôle final'

$fin = (Get-Date).AddSeconds($DelaiControle)
$etat = $null
$dernier = ''
while ($true) {
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
    $reste = ($fin - (Get-Date)).TotalSeconds
    if ($reste -le 0) { break }
    Start-Sleep -Seconds ([int][Math]::Ceiling([Math]::Min(10, $reste)))
}
if (-not $etat) { Revenir "la nouvelle version ne répond pas correctement après $DelaiControle s. Dernière réponse :`n$dernier" }

foreach ($c in $etat.controles) {
    $couleur = 'Gray'
    if ($c.niveau -eq 'ok') { $couleur = 'Green' } elseif ($c.niveau -eq 'warning') { $couleur = 'Yellow' } elseif ($c.niveau -eq 'error') { $couleur = 'Red' }
    Dire ("  {0} : {1}" -f $c.libelle, $c.resume) $couleur
}
$Port = Lire-Env $EnvNouveau 'WEB_PORT'
if (-not $Port) { $Port = '8000' }
Write-Host ''
Dire "Mise à jour terminée : J-ed $VersionNouvelle, http://localhost:$Port" 'Green'
Dire "Sauvegarde faite avant la mise à jour : $CopieLocale"
Dire "L'ancien dossier ($Actuel) n'a pas été modifié ; gardez-le jusqu'à ce que la nouvelle version vous convienne."
if ($ScriptAncien) {
    Avertir "Rappel : copiez « $([System.IO.Path]::Combine($Destination, 'mettre-a-jour.ps1')) » à la place de « $PSCommandPath » pour les prochaines mises à jour."
}
Terminer 0 'mise à jour réussie'
