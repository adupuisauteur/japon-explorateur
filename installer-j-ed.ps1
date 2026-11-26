<#
.SYNOPSIS
    Installe une NOUVELLE instance de J-ed à partir de l'archive d'une version (2.0.2), à côté des autres
    installations, sans jamais toucher à leurs données.

.DESCRIPTION
    Utilisé par l'assistant J-ed (bouton « Nouvelle installation ») ; peut aussi être lancé en ligne de commande.
    Étapes, chacune contrôlée :
      1. contrôles : archive et empreinte SHA-256, nom du projet NEUF (jamais celui d'une installation existante,
         ni d'anciens volumes de données, ni un nom réservé), port libre, dossier neuf, Docker démarré ;
      2. décompression de l'archive dans le nouveau dossier ;
      3. fichier .env : nom, port, secrets NEUFS (rien n'est copié d'une autre installation), dossier des
         sauvegardes, Argos, proxy éventuel (sans mot de passe) ;
      4. construction de J-ed (plusieurs minutes la première fois ; Internet nécessaire) ;
      5. démarrage ;
      6. contrôle : version et base de données (manage.py etat_installation), puis la page de santé du serveur
         web, deux fois à quelques secondes d'intervalle.
    Rien n'est jamais supprimé : en cas d'échec, le nouveau dossier reste, et le message dit quoi faire.

    Journal : fichier installation-AAAAMMJJ-HHMMSS.log dans le dossier des sauvegardes (sinon à côté du nouveau
    dossier), mêmes repères que la mise à jour (docs/contrat-scripts.md). Le fichier .env n'y est jamais écrit.

    Codes de sortie :
      0  installation réussie ;
      1  arrêt pendant les contrôles : rien n'a été créé ;
      3  construction impossible (Internet, proxy ?) : le dossier est créé, rien n'est démarré ;
      5  J-ed ne démarre pas ou ne répond pas : le dossier est créé, le message et le journal disent quoi faire.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\installer-j-ed.ps1 -Archive .\japon-explorateur-2.0.2.zip -Destination C:\J-ed\jed-2-2.0.2 -Nom jed-2 -Port 8003 -DossierSauvegardes C:\J-ed\sauvegardes-jed-2
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [string]$Empreinte,
    [Parameter(Mandatory = $true)][string]$Destination,
    [Parameter(Mandatory = $true)][string]$Nom,
    [int]$Port = 8000,
    [string]$DossierSauvegardes,
    [string]$Proxy,
    [switch]$SansArgos,
    [int]$DelaiControle = 600,
    [int]$DelaiStabilite = 15
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
# 2.0.3 (Linux, décision D1) : ce script sert tel quel sous Windows (Windows PowerShell 5.1) et sous Linux
# (PowerShell 7, lancé par « pwsh -NoProfile -File »). La variable IsLinux n'existe pas sous 5.1 : lue ainsi, elle vaut faux.
$SousLinux = ((Get-Variable -Name IsLinux -ValueOnly -ErrorAction SilentlyContinue) -eq $true)
$TexteDockerLinux = 'Docker ne répond pas. Vérifiez qu''il est démarré (« sudo systemctl start docker ») et que votre compte est dans le groupe docker (après l''y avoir ajouté, se déconnecter puis se reconnecter), puis recommencez.'
# 2.0.3 (Linux) : pendant une construction, la commande docker elle-même demande un jeton d'accès à Docker Hub ;
# elle ne lit pas le proxy du service Docker (/etc/docker/daemon.json) et attend alors jusqu'à « failed to
# authorize: DeadlineExceeded » (essai du 26/11/2026 sur Ubuntu 26.04). Docker Desktop (Windows) s'en charge seul :
# rien ne change sous Windows. Le proxy n'est donné qu'à ce script et aux commandes qu'il lance ; un proxy déjà
# réglé dans le terminal est gardé tel quel.
function Donner-Proxy-A-Docker([string]$Adresse) {
    if (-not $SousLinux -or -not $Adresse) { return }
    foreach ($nom in @('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy')) {
        if ([Environment]::GetEnvironmentVariable($nom)) {
            Dire 'Proxy déjà réglé dans ce terminal : il est gardé pour les commandes docker.'
            return
        }
    }
    [Environment]::SetEnvironmentVariable('HTTP_PROXY', $Adresse)
    [Environment]::SetEnvironmentVariable('HTTPS_PROXY', $Adresse)
    if (-not ([Environment]::GetEnvironmentVariable('NO_PROXY') -or [Environment]::GetEnvironmentVariable('no_proxy'))) {
        [Environment]::SetEnvironmentVariable('NO_PROXY', 'localhost,127.0.0.1')
    }
    Dire "Proxy donné à la commande docker (constructions) : $Adresse"
}
$NomsReserves = @('japon-explorateur', 'japon-explorateur-essai')
$CodeArret = 1
$CodeConstruction = 3
$CodeDemarrage = 5
$script:Journal = $null
$script:Tampon = New-Object System.Collections.Generic.List[string]
$script:DossierCree = $false
$Utf8SansBom = New-Object System.Text.UTF8Encoding($false)
# 2.0.3 (Linux, décisions D4 et D5) : jamais en root (les fichiers de J-ed appartiendraient à root) ; le conteneur
# (utilisateur 1000) copie lui-même chaque sauvegarde dans le dossier des sauvegardes : il doit pouvoir y écrire.
# JED_UID_ACTUEL et JED_UID_CONTENEUR : réservés aux tests automatiques.
function Get-UidLinux {
    if ("$env:JED_UID_ACTUEL" -match '^\d+$') { return [int]$env:JED_UID_ACTUEL }
    $u = "$(& id -u 2>$null)".Trim()
    if ($u -match '^\d+$') { return [int]$u }
    return $null
}
function Test-EcritureConteneur([string]$Chemin) {
    # Vrai si l'utilisateur du conteneur peut écrire dans ce dossier, faux sinon, $null si on ne sait pas.
    $uidConteneur = 1000
    if ("$env:JED_UID_CONTENEUR" -match '^\d+$') { $uidConteneur = [int]$env:JED_UID_CONTENEUR }
    if ($uidConteneur -eq 0) { return $true }
    $s = "$(& stat -c '%u %g %a' $Chemin 2>$null)".Trim()
    if ($s -notmatch '^(\d+) (\d+) ([0-7]{3,4})$') { return $null }
    $uid = [int]$Matches[1]; $gid = [int]$Matches[2]
    $mode = [Convert]::ToInt32($Matches[3].Substring($Matches[3].Length - 3), 8)
    if ($uid -eq $uidConteneur) { return (($mode -band 0x80) -ne 0 -and ($mode -band 0x40) -ne 0) }   # u+w, u+x
    if ($gid -eq $uidConteneur) { return (($mode -band 0x10) -ne 0 -and ($mode -band 0x8) -ne 0) }    # g+w, g+x
    return (($mode -band 0x2) -ne 0 -and ($mode -band 0x1) -ne 0)                                      # o+w, o+x
}
$TexteRoot = 'ne lancez pas ce script en administrateur (sudo ou root) : les fichiers de J-ed appartiendraient à root. Relancez-le depuis votre compte, sans sudo.'

function Ecrire-Journal([string]$Repere, [string]$Texte) {
    $heure = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $lignes = @(("$Texte" -replace "`r", '') -split "`n")
    $bloc = "$heure $Repere $($lignes[0])`r`n"
    for ($i = 1; $i -lt $lignes.Count; $i++) { $bloc += "    | $($lignes[$i])`r`n" }
    if ($script:Journal) { try { [System.IO.File]::AppendAllText($script:Journal, $bloc, $Utf8SansBom) } catch { } }
    else { $script:Tampon.Add($bloc) }
}

function Dire([string]$Message, [string]$Couleur) {
    if ($Couleur) { Write-Host $Message -ForegroundColor $Couleur } else { Write-Host $Message }
    Ecrire-Journal 'INFO' $Message
}

function Terminer([int]$Code, [string]$Resume) {
    Ecrire-Journal 'FIN' "code=$Code $Resume"
    if ($script:Journal) { Write-Host "Journal de l'installation : $script:Journal" }
    exit $Code
}

function Arreter([string]$Message, [int]$Code = $CodeArret) {
    Write-Host ''
    Write-Host "ARRÊT : $Message" -ForegroundColor Red
    Ecrire-Journal 'ERREUR' $Message
    if ($script:DossierCree) {
        Write-Host "Le dossier $Destination a été créé ; il peut être supprimé avant de recommencer. Aucune autre installation n'a été touchée." -ForegroundColor Yellow
    } else {
        Write-Host 'Rien n''a été créé ; aucune autre installation n''a été touchée.' -ForegroundColor Yellow
    }
    $resume = 'arrêt pendant les contrôles, rien n''a été créé'
    if ($Code -eq $CodeConstruction) { $resume = 'construction impossible, rien n''a été démarré' }
    if ($Code -eq $CodeDemarrage) { $resume = 'J-ed ne démarre pas ou ne répond pas' }
    Terminer $Code $resume
}

function Etape([string]$Message) {
    Write-Host ''
    Write-Host "== $Message" -ForegroundColor Cyan
    Ecrire-Journal 'ETAPE' $Message
}

function Docker-Dans {
    param([string]$Dossier, [string[]]$Arguments, [switch]$Discret)
    Ecrire-Journal 'COMMANDE' "$Dossier > docker $($Arguments -join ' ')"
    if ($Dossier) { Push-Location -LiteralPath $Dossier }
    try {
        $sortie = & docker @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        if ($Dossier) { Pop-Location }
    }
    $lignes = $sortie | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" } }
    $texte = (@($lignes) -join "`n").Trim()
    if ($Discret) { Ecrire-Journal 'RESULTAT' "code=$code (sortie non journalisée)" }
    elseif ($texte) { Ecrire-Journal 'RESULTAT' "code=$code`n$texte" }
    else { Ecrire-Journal 'RESULTAT' "code=$code" }
    return [pscustomobject]@{ Code = $code; Texte = $texte }
}

function Lire-Env([string]$Fichier, [string]$Variable) {
    $valeur = ''
    foreach ($ligne in (Get-Content -LiteralPath $Fichier -Encoding UTF8)) {
        if ($ligne -match "^\s*$Variable\s*=(.*)$") { $valeur = $Matches[1].Trim() }
    }
    return $valeur
}

function Aleatoire([int]$Longueur, [string]$Alphabet) {
    $octets = New-Object byte[] ($Longueur * 2)
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $rng.GetBytes($octets)
    $sb = New-Object System.Text.StringBuilder
    foreach ($o in $octets) {
        if ($sb.Length -ge $Longueur) { break }
        # Tirage sans biais : on écarte les octets au-delà du plus grand multiple de la taille de l'alphabet.
        if ($o -lt (256 - (256 % $Alphabet.Length))) { [void]$sb.Append($Alphabet[$o % $Alphabet.Length]) }
    }
    while ($sb.Length -lt $Longueur) {
        $un = New-Object byte[] 1; $rng.GetBytes($un)
        if ($un[0] -lt (256 - (256 % $Alphabet.Length))) { [void]$sb.Append($Alphabet[$un[0] % $Alphabet.Length]) }
    }
    return $sb.ToString()
}

function Cle-Fernet {
    # Clé de chiffrement des clés d'API (même format que « manage.py generate_secrets ») : 32 octets en base64url.
    $octets = New-Object byte[] 32
    (New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($octets)
    return [Convert]::ToBase64String($octets).Replace('+', '-').Replace('/', '_')
}

function Sante-Web([string]$Dossier) {
    return Docker-Dans $Dossier @('compose', 'exec', '-T', 'web', 'curl', '-fsS', 'http://localhost:8000/sante/')
}

Write-Host 'Nouvelle installation de J-ed' -ForegroundColor White
Ecrire-Journal 'INFO' "Nouvelle installation ; archive : $Archive ; dossier : $Destination ; nom : $Nom ; port : $Port"

# --- 1. Contrôles ---------------------------------------------------------------------------------------
Etape '1/6 Contrôles'

if ($SousLinux -and (Get-UidLinux) -eq 0) { Arreter $TexteRoot }
$Destination = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\', '/')
$DossierJournal = $DossierSauvegardes
if (-not $DossierJournal) { $DossierJournal = Split-Path -Parent $Destination }
try {
    New-Item -ItemType Directory -Force -Path $DossierJournal -ErrorAction Stop | Out-Null
    $script:Journal = [System.IO.Path]::Combine($DossierJournal, "installation-$(Get-Date -Format 'yyyyMMdd-HHmmss').log")
    [System.IO.File]::WriteAllText($script:Journal, ($script:Tampon -join ''), $Utf8SansBom)
} catch {
    Write-Host "ARRÊT : impossible d'écrire dans $DossierJournal : $($_.Exception.Message)" -ForegroundColor Red
    exit $CodeArret
}
Write-Host "Journal de l'installation : $script:Journal"
if ($SousLinux -and $DossierSauvegardes -and (Test-EcritureConteneur $DossierSauvegardes) -eq $false) {
    # Pas un arrêt : J-ed garde la sauvegarde dans Docker et l'assistant sait la copier lui-même ; mais la copie
    # automatique de J-ed (« Copie externe ») échouerait.
    Write-Host ("Attention : J-ed (utilisateur 1000 de son conteneur) ne pourra pas écrire dans $DossierSauvegardes. " +
        "Pour le lui permettre : chmod o+rwx `"$DossierSauvegardes`"") -ForegroundColor Yellow
    Ecrire-Journal 'ATTENTION' "dossier des sauvegardes non accessible en écriture à l'utilisateur 1000 du conteneur : $DossierSauvegardes"
}

if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) { Arreter "archive introuvable : $Archive" }
$Archive = (Resolve-Path -LiteralPath $Archive).Path
if ($Empreinte) {
    if (-not (Test-Path -LiteralPath $Empreinte -PathType Leaf)) { Arreter "fichier d'empreinte introuvable : $Empreinte" }
    $FichierEmpreinte = $Empreinte
} else {
    $FichierEmpreinte = @("$Archive.sha256", [System.IO.Path]::ChangeExtension($Archive, '.sha256')) |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $FichierEmpreinte) { Arreter "fichier d'empreinte absent (attendu : $Archive.sha256). Téléchargez-le avec l'archive." }
}
$Attendue = ((Get-Content -LiteralPath $FichierEmpreinte -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
$Calculee = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Attendue -ne $Calculee) {
    Arreter "empreinte de l'archive différente de celle attendue (archive incomplète, abîmée ou ancienne).`n  attendue : $Attendue`n  calculée : $Calculee"
}
Dire "Empreinte de l'archive vérifiée : $Calculee"

if ($Nom -cnotmatch '^[a-z0-9][a-z0-9_-]{0,39}$') {
    Arreter "nom « $Nom » refusé : lettres minuscules sans accent, chiffres, « - » ou « _ » (40 au plus)."
}
if ($NomsReserves -contains $Nom) { Arreter "« $Nom » est un nom réservé : choisissez-en un autre." }
if ($Port -lt 1024 -or $Port -gt 65535) { Arreter "port $Port refusé : choisissez-en un entre 1024 et 65535." }
if (Test-Path -LiteralPath $Destination) { Arreter "le dossier $Destination existe déjà : choisissez-en un autre." }
if ($Proxy -and ($Proxy -notmatch '^https?://[^\s/@]+$')) {
    Arreter 'proxy refusé : adresse attendue sous la forme http://nom-ou-adresse:port (sans identifiant ni mot de passe).'
}

if ((Docker-Dans '' @('info') -Discret).Code -ne 0) {
    if ($SousLinux) { Arreter $TexteDockerLinux }
    Arreter 'Docker Desktop ne répond pas. Démarrez-le, attendez « Engine running », puis recommencez.'
}
# Nom neuf : ni un projet connu de Docker, ni d'anciens volumes de données portant ce nom.
$projets = Docker-Dans '' @('compose', 'ls', '-a', '--format', 'json')
$connus = @()
if ($projets.Code -eq 0 -and $projets.Texte) {
    try { $connus = @(($projets.Texte | ConvertFrom-Json) | ForEach-Object { $_ }) } catch { $connus = @() }
}
foreach ($p in $connus) {
    if ($p.Name -eq $Nom) { Arreter "une installation nommée « $Nom » existe déjà ($($p.ConfigFiles)) : choisissez un autre nom." }
}
$volumes = Docker-Dans '' @('volume', 'ls', '-q')
if ($volumes.Code -ne 0) { Arreter 'lecture des volumes de Docker impossible.' }
$anciens = @($volumes.Texte -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_.StartsWith("$($Nom)_") })
if ($anciens.Count -gt 0) {
    Arreter "des données d'une installation « $Nom » existent encore dans Docker ($($anciens -join ', ')) : choisissez un autre nom."
}
# Port libre : ni celui d'une autre installation (même arrêtée, d'après son .env), ni un port déjà écouté.
foreach ($p in $connus) {
    foreach ($f in ("$($p.ConfigFiles)" -split ',')) {
        $envAutre = [System.IO.Path]::Combine((Split-Path -Parent $f.Trim()), '.env')
        if ((Test-Path -LiteralPath $envAutre) -and ((Lire-Env $envAutre 'WEB_PORT') -eq "$Port")) {
            Arreter "le port $Port est déjà celui de l'installation « $($p.Name) » : choisissez-en un autre."
        }
    }
}
$ecoute = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
try { $ecoute.Start(); $ecoute.Stop() } catch { Arreter "le port $Port est déjà utilisé par un autre programme : choisissez-en un autre." }
Dire "Nom « $Nom » et port $Port libres."

# --- 2. Décompression -------------------------------------------------------------------------------
Etape '2/6 Décompression'
$Parent = Split-Path -Parent $Destination
New-Item -ItemType Directory -Force -Path $Parent | Out-Null
$Partiel = "$Destination.partiel"
if (Test-Path -LiteralPath $Partiel) { Arreter "un dossier $Partiel existe déjà (essai précédent interrompu ?) : supprimez-le, puis recommencez." }
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
        Arreter "docker-compose.yml introuvable dans l'archive : ce n'est pas une archive de J-ed (le dossier $Partiel peut être supprimé)."
    }
}
Move-Item -LiteralPath $Racine -Destination $Destination
if (Test-Path -LiteralPath $Partiel) { Remove-Item -LiteralPath $Partiel -Recurse -Force }
$script:DossierCree = $true
$Version = '?'
$fichierVersion = [System.IO.Path]::Combine($Destination, 'VERSION')
if (Test-Path -LiteralPath $fichierVersion) { $Version = (Get-Content -LiteralPath $fichierVersion -Raw).Trim() }
Dire "J-ed $Version décompressé dans : $Destination"

# --- 3. Fichier .env ------------------------------------------------------------------------------------
Etape '3/6 Réglages (fichier .env)'
$Modele = [System.IO.Path]::Combine($Destination, '.env.example')
if (-not (Test-Path -LiteralPath $Modele)) { Arreter '.env.example absent de l''archive : version trop ancienne pour ce script.' }
$sur = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
$alnum = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
$valeurs = [ordered]@{
    COMPOSE_PROJECT_NAME = $Nom
    WEB_PORT = "$Port"
    DJANGO_SECRET_KEY = (Aleatoire 64 $sur)
    AI_KEYS_ENCRYPTION_KEY = (Cle-Fernet)
    POSTGRES_PASSWORD = (Aleatoire 32 $alnum)
    COMPOSE_PROFILES = $(if ($SansArgos) { '' } else { 'argos' })
}
if ($DossierSauvegardes) { $valeurs['DOSSIER_SAUVEGARDES'] = $DossierSauvegardes }
if ($Proxy) {
    $valeurs['HTTP_PROXY'] = $Proxy
    $valeurs['HTTPS_PROXY'] = $Proxy
    $valeurs['NO_PROXY'] = 'localhost,127.0.0.1,db,redis,argos,ollama,web'
}
$faits = @{}
$lignes = New-Object System.Collections.Generic.List[string]
foreach ($ligne in (Get-Content -LiteralPath $Modele -Encoding UTF8)) {
    # Une variable du modèle (même en commentaire « # NOM= ») reçoit sa valeur à sa place habituelle.
    if ($ligne -match '^\s*#?\s*([A-Z_][A-Z0-9_]*)\s*=' -and $valeurs.Contains($Matches[1]) -and -not $faits.ContainsKey($Matches[1])) {
        $cle = $Matches[1]
        $lignes.Add("$cle=$($valeurs[$cle])")
        $faits[$cle] = $true
    } else {
        $lignes.Add($ligne)
    }
}
$reste = @($valeurs.Keys | Where-Object { -not $faits.ContainsKey($_) })
if ($reste.Count -gt 0) {
    $lignes.Add('')
    $lignes.Add('# Ajouté par installer-j-ed.ps1 (assistant J-ed)')
    foreach ($cle in $reste) { $lignes.Add("$cle=$($valeurs[$cle])") }
}
$FichierEnv = [System.IO.Path]::Combine($Destination, '.env')
[System.IO.File]::WriteAllText($FichierEnv, (($lignes -join "`r`n") + "`r`n"), $Utf8SansBom)
Dire 'Fichier .env créé avec des secrets neufs (jamais écrits dans ce journal).'
if ($Proxy) { Dire "Proxy : $Proxy (services internes de J-ed exclus)." }
Donner-Proxy-A-Docker $Proxy

# --- 4. Construction ---------------------------------------------------------------------------------
Etape '4/6 Construction de J-ed (plusieurs minutes la première fois)'
$construction = Docker-Dans $Destination @('compose', 'build')
if ($construction.Code -ne 0) {
    Write-Host $construction.Texte
    $conseilProxy = 'derrière un proxy, réglez-le dans Docker Desktop (Settings → Resources → Proxies).'
    if ($SousLinux) {
        $conseilProxy = 'derrière un proxy, indiquez-le à ce script (-Proxy) et au service Docker (/etc/docker/daemon.json, voir « Avant de commencer »).'
    }
    Arreter ("construction impossible. Le plus souvent, Docker ne joint pas Internet : essayez « docker pull python:3.12-slim-bookworm » ; " +
        $conseilProxy) $CodeConstruction
}
Dire 'J-ed est construit.' 'Green'

# --- 5. Démarrage ------------------------------------------------------------------------------------
Etape '5/6 Démarrage'
$lancement = Docker-Dans $Destination @('compose', 'up', '-d')
if ($lancement.Code -ne 0) {
    Write-Host $lancement.Texte
    Arreter "démarrage impossible : $($lancement.Texte)" $CodeDemarrage
}

# --- 6. Contrôle ---------------------------------------------------------------------------------------
Etape '6/6 Contrôle'
$fin = (Get-Date).AddSeconds($DelaiControle)
$reussi = $false
$dernier = ''
while ($true) {
    $r = Docker-Dans $Destination @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'etat_installation', '--json')
    $lu = $null
    $debut = $r.Texte.IndexOf('{'); $finJson = $r.Texte.LastIndexOf('}')
    if ($debut -ge 0 -and $finJson -gt $debut) {
        try { $lu = $r.Texte.Substring($debut, $finJson - $debut + 1) | ConvertFrom-Json } catch { $lu = $null }
    }
    $etatOk = $false
    if ($lu -and $lu.version -eq $Version) {
        $base = $lu.controles | Where-Object { $_.cle -eq 'base' } | Select-Object -First 1
        $etatOk = ($base -and $base.niveau -eq 'ok')
    }
    if (-not $etatOk) {
        $dernier = $r.Texte
    } else {
        if ((Sante-Web $Destination).Code -eq 0) {
            Dire "Le serveur web répond ; nouveau contrôle dans $DelaiStabilite s…"
            Start-Sleep -Seconds $DelaiStabilite
            if ((Sante-Web $Destination).Code -eq 0) { $reussi = $true; break }
            $dernier = 'le serveur web a cessé de répondre (page /sante/).'
        } else {
            $dernier = 'le serveur web ne répond pas (page /sante/).'
        }
    }
    $reste = ($fin - (Get-Date)).TotalSeconds
    if ($reste -le 0) { break }
    Start-Sleep -Seconds ([int][Math]::Ceiling([Math]::Min(10, $reste)))
}
if (-not $reussi) {
    Arreter ("J-ed ne répond pas correctement après $DelaiControle s. Dernière réponse :`n$dernier`n" +
        "Utilisez « Ça ne marche pas » dans l'assistant pour préparer un compte rendu.") $CodeDemarrage
}

Write-Host ''
Dire "Installation terminée : J-ed $Version, http://localhost:$Port" 'Green'
Dire "Créez maintenant le compte administrateur : http://localhost:$Port/comptes/premier-demarrage/"
Terminer 0 'installation réussie'
