<#
.SYNOPSIS
    Vérifie une installation de J-ed : poste, Docker, conteneurs, adresse, réglages, puis chaque fonction
    de l'application avec des données fictives. Ne modifie rien.

.DESCRIPTION
    Partie 1, sur l'ordinateur : Docker Desktop, mémoire accordée à Docker, conteneurs attendus, port publié
    seulement sur l'ordinateur, volumes de données, fichier .env (valeurs à remplacer, nom protégé),
    dossier des sauvegardes visible dans Windows, pages qui répondent et politique de sécurité.
    Partie 2, dans l'application : « manage.py verifier_fonctionnalites » exerce la recherche, les notices,
    les doublons, l'import, la Bibliothèque, les exports, les projets de traduction, Argos, les tâches de fond,
    la dernière sauvegarde, les pages et les droits d'accès, avec des données FICTIVES, dans une transaction
    annulée : la base n'est pas modifiée.
    Un rapport texte, sans clé ni nom de compte, est enregistré à côté du dossier de l'installation.

.PARAMETER Dossier
    Dossier de l'installation (celui qui contient docker-compose.yml). Par défaut : le dossier du script.

.PARAMETER AvecSources
    Teste aussi chaque source en ligne (une recherche d'essai par source, sur Internet).

.PARAMETER AvecTests
    Lance aussi la suite de tests automatiques dans le conteneur (base de test séparée, 3 à 10 minutes).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1 -Dossier C:\J-ed\japon-explorateur-2.0.0 -AvecSources
#>
[CmdletBinding()]
param(
    [string]$Dossier,
    [switch]$AvecSources,
    [switch]$AvecTests
)

$ErrorActionPreference = 'Continue'
# Windows PowerShell 5.1 lit la sortie de docker avec la page de code de la console (850, 437…) : les accents
# arrivaient abîmés (« Terminée » lu « Termin├®e », constaté le 15 novembre 2026). La sortie est lue en UTF-8.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
$NomsProteges = @('japon-explorateur', 'japon-explorateur-essai')
$script:Lignes = New-Object System.Collections.Generic.List[string]
$script:Bilan = @{ ok = 0; warning = 0; error = 0; skipped = 0 }

function Noter([string]$Niveau, [string]$Libelle, [string]$Resume, [string[]]$Details = @()) {
    $etiquettes = @{ ok = 'OK'; warning = 'À surveiller'; error = 'Problème'; skipped = 'Non vérifié' }
    $couleurs = @{ ok = 'Green'; warning = 'Yellow'; error = 'Red'; skipped = 'Gray' }
    $script:Bilan[$Niveau] += 1
    $ligne = "[{0}] {1} : {2}" -f $etiquettes[$Niveau], $Libelle, $Resume
    Write-Host $ligne -ForegroundColor $couleurs[$Niveau]
    $script:Lignes.Add($ligne)
    foreach ($d in $Details) {
        if ($d) {
            Write-Host "    $d" -ForegroundColor Gray
            $script:Lignes.Add("    $d")
        }
    }
}

function Titre([string]$Texte) {
    Write-Host ''
    Write-Host "== $Texte" -ForegroundColor Cyan
    $script:Lignes.Add('')
    $script:Lignes.Add("== $Texte")
}

function Docker-Ici([string[]]$Arguments) {
    $sortie = & docker @Arguments 2>&1
    return [pscustomobject]@{ Code = $LASTEXITCODE; Texte = (($sortie | ForEach-Object { "$_" }) -join "`n").Trim() }
}

function Lire-Env([string]$Nom) {
    foreach ($ligne in $script:EnvLignes) {
        if ($ligne -match "^\s*$Nom\s*=(.*)$") { return $Matches[1].Trim() }
    }
    return ''
}

function Masquer([string]$Texte) {
    return ($Texte -replace '(?i)([a-z]:\\users\\)[^\\\s]+', '$1…')
}

function Lire-Json([string]$Texte) {
    $debut = $Texte.IndexOf('{')
    $fin = $Texte.LastIndexOf('}')
    if ($debut -lt 0 -or $fin -le $debut) { return $null }
    try { return $Texte.Substring($debut, $fin - $debut + 1) | ConvertFrom-Json } catch { return $null }
}

if (-not $Dossier) { $Dossier = $PSScriptRoot }
if (-not (Test-Path -LiteralPath $Dossier -PathType Container)) {
    Write-Host "ARRÊT : dossier introuvable : $Dossier" -ForegroundColor Red
    exit 1
}
$Dossier = (Resolve-Path -LiteralPath $Dossier).Path
Set-Location -LiteralPath $Dossier
Write-Host "Vérification de J-ed — $Dossier" -ForegroundColor White
$script:Lignes.Add("Vérification de J-ed — $(Get-Date -Format 'dd/MM/yyyy HH:mm')")

# --- 1. Dossier et réglages ---------------------------------------------------------------------------------
Titre '1. Dossier et fichier de réglages .env'

foreach ($f in @('docker-compose.yml', 'VERSION')) {
    if (-not (Test-Path -LiteralPath $f)) {
        Noter 'error' 'Dossier' "« $f » absent : ce n'est pas le dossier d'une installation de J-ed."
        exit 1
    }
}
$Version = (Get-Content -LiteralPath 'VERSION' -Raw).Trim()
Noter 'ok' 'Version du dossier' "J-ed $Version"

if (-not (Test-Path -LiteralPath '.env')) {
    Noter 'error' 'Fichier .env' 'absent : voir le guide d''installation, étape 3'
    exit 1
}
$script:EnvLignes = Get-Content -LiteralPath '.env' -Encoding UTF8
$Projet = Lire-Env 'COMPOSE_PROJECT_NAME'
$Port = Lire-Env 'WEB_PORT'
if (-not $Port) { $Port = '8000' }
$aRemplacer = @()
foreach ($nom in @('DJANGO_SECRET_KEY', 'AI_KEYS_ENCRYPTION_KEY', 'POSTGRES_PASSWORD')) {
    $valeur = Lire-Env $nom
    if (-not $valeur -or $valeur -like 'à-remplacer*') { $aRemplacer += $nom }
}
if (-not $Projet) {
    Noter 'error' 'Nom de l''installation' 'COMPOSE_PROJECT_NAME est vide dans .env'
} elseif ($NomsProteges -contains $Projet) {
    if ((Lire-Env 'AUTORISER_NOM_PROJET') -eq $Projet) {
        Noter 'ok' 'Nom de l''installation' "« $Projet » (nom protégé, mise à jour autorisée)"
    } else {
        Noter 'error' 'Nom de l''installation' "« $Projet » est protégé et AUTORISER_NOM_PROJET=$Projet manque : J-ed refusera de démarrer"
    }
} else {
    Noter 'ok' 'Nom de l''installation' "« $Projet »"
}
if ($aRemplacer.Count) {
    Noter 'error' 'Mots de passe techniques' ("à renseigner dans .env : " + ($aRemplacer -join ', '))
} else {
    Noter 'ok' 'Mots de passe techniques' 'renseignés (valeurs non affichées)'
}
$Profils = Lire-Env 'COMPOSE_PROFILES'
# 2.0.0 (lot 7) : profil « argos » (installation standard) ; l'ancien profil « hors-ligne » reste accepté.
$ArgosAttendu = $Profils -match '(^|,)\s*(argos|hors-ligne)\s*(,|$)'
$ArgosDesactive = @($script:EnvLignes | Where-Object { $_ -match '^\s*COMPOSE_PROFILES\s*=' }).Count -gt 0
# 2.0.0 (lot 4) : IA locale facultative (profil « ollama »), jamais attendue par défaut.
$OllamaAttendu = $Profils -match '(^|,)\s*ollama\s*(,|$)'

$DossierSauv = Lire-Env 'DOSSIER_SAUVEGARDES'
if (-not $DossierSauv) {
    Noter 'warning' 'Dossier des sauvegardes' 'DOSSIER_SAUVEGARDES absent de .env : les copies restent dans Docker, invisibles dans Windows'
} elseif (-not (Test-Path -LiteralPath $DossierSauv -PathType Container)) {
    Noter 'warning' 'Dossier des sauvegardes' "$DossierSauv n'existe pas encore (il sera créé à la première sauvegarde)"
} else {
    $copies = @(Get-ChildItem -LiteralPath $DossierSauv -Filter 'sauvegarde-*.tar' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    if (-not $copies.Count) {
        Noter 'warning' 'Dossier des sauvegardes' "$DossierSauv : aucune sauvegarde copiée pour l'instant"
    } else {
        $age = (Get-Date) - $copies[0].LastWriteTime
        $taille = [math]::Round((($copies | Measure-Object Length -Sum).Sum) / 1GB, 2)
        $detail = @("Dernière : $($copies[0].Name) ($([math]::Round($copies[0].Length / 1MB, 1)) Mo)",
            "$($copies.Count) copie(s), $taille Go au total (J-ed ne supprime jamais ces copies)")
        if ($age.TotalHours -gt 36) {
            Noter 'warning' 'Dossier des sauvegardes' ("dernière copie il y a {0:N0} h" -f $age.TotalHours) $detail
        } else {
            Noter 'ok' 'Dossier des sauvegardes' ("dernière copie il y a {0:N0} h" -f $age.TotalHours) $detail
        }
    }
}

# --- 2. Docker et conteneurs -------------------------------------------------------------------------------
Titre '2. Docker et conteneurs'

$info = Docker-Ici @('info', '--format', '{{.MemTotal}}|{{.NCPU}}|{{.ServerVersion}}')
if ($info.Code -ne 0) {
    Noter 'error' 'Docker Desktop' 'ne répond pas : démarrez-le, attendez « Engine running », puis relancez'
    $script:Lignes | Set-Content -LiteralPath ([System.IO.Path]::Combine((Split-Path -Parent $Dossier), "verification-j-ed-$(Get-Date -Format 'yyyyMMdd-HHmm').txt")) -Encoding UTF8
    exit 1
}
$parts = $info.Texte.Split('|')
$memoire = [math]::Round([double]$parts[0] / 1GB, 1)
$detailsDocker = @("Docker $($parts[2]) ; mémoire accordée : $memoire Go ; cœurs : $($parts[1])")
if ($memoire -lt 4) {
    Noter 'warning' 'Docker Desktop' "seulement $memoire Go de mémoire pour Docker" ($detailsDocker + 'Argos et les longues traductions risquent d''en manquer.')
} elseif ($ArgosAttendu -and $memoire -lt 6) {
    Noter 'warning' 'Docker Desktop' "$memoire Go de mémoire pour Docker, juste pour Argos" $detailsDocker
} else {
    Noter 'ok' 'Docker Desktop' 'en service' $detailsDocker
}

# 2.0.0 (lot 3) : trois workers (travaux courts, longues traductions, demandes « maintenant »)
$attendus = @('db', 'redis', 'web', 'worker', 'worker-traduction', 'worker-maintenant', 'beat')
if ($ArgosAttendu) { $attendus += 'argos' }
if ($OllamaAttendu) { $attendus += 'ollama' }
$enService = Docker-Ici @('compose', 'ps', '--services', '--status', 'running')
$services = @($enService.Texte -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -notmatch '\s' })
$manquants = @($attendus | Where-Object { $services -notcontains $_ })
if ($enService.Code -ne 0) {
    Noter 'error' 'Conteneurs' "lecture impossible : $($enService.Texte)"
} elseif ($manquants.Count) {
    Noter 'error' 'Conteneurs' ("arrêtés : " + ($manquants -join ', ')) @("Démarrez-les : docker compose up -d", "Détail : docker compose logs --tail 100 $($manquants[0])")
} else {
    Noter 'ok' 'Conteneurs' ("en service : " + ($services -join ', '))
}
if (-not $ArgosAttendu) {
    if ($services -contains 'argos') {
        # Constat du 15 novembre 2026 : Argos démarré par « --profile » mais absent de .env.
        Noter 'warning' 'Argos' 'en service, mais COMPOSE_PROFILES=argos manque dans .env' @(
            'Un simple « docker compose up -d » ne le démarrerait plus. Ajoutez cette ligne à la fin de .env.')
    } elseif ($ArgosDesactive) {
        Noter 'skipped' 'Argos' 'désactivé volontairement (ligne COMPOSE_PROFILES vide dans .env)'
    } else {
        Noter 'warning' 'Argos' 'non démarré : la ligne COMPOSE_PROFILES=argos manque dans .env' @(
            'Argos fait partie de l''installation standard depuis la 2.0.0. Ajoutez cette ligne à la fin de .env,',
            'puis : docker compose up -d --build')
    }
}
if ($OllamaAttendu) {
    if ($services -contains 'ollama') {
        Noter 'ok' 'IA locale' 'service Ollama démarré (modèles : Traduction → Moteurs locaux)'
    }
} elseif ($services -contains 'ollama') {
    Noter 'warning' 'IA locale' 'en service, mais « ollama » manque dans la ligne COMPOSE_PROFILES de .env' @(
        'Un simple « docker compose up -d » ne la démarrerait plus.')
} else {
    Noter 'skipped' 'IA locale' 'non installée (facultative : ajouter ollama à COMPOSE_PROFILES dans .env)'
}

$publie = Docker-Ici @('compose', 'port', 'web', '8000')
if ($publie.Code -ne 0) {
    Noter 'error' 'Port publié' "introuvable : $($publie.Texte)"
} elseif ($publie.Texte -match '^127\.0\.0\.1:') {
    Noter 'ok' 'Port publié' "$($publie.Texte) (accessible seulement depuis cet ordinateur)"
} else {
    Noter 'warning' 'Port publié' "$($publie.Texte) : J-ed est peut-être accessible depuis le réseau"
}

$volumes = Docker-Ici @('volume', 'ls', '--format', '{{.Name}}')
$manquantsV = @(@("${Projet}_db-data", "${Projet}_app-data") | Where-Object { ($volumes.Texte -split "`n") -notcontains $_ })
if ($manquantsV.Count) {
    Noter 'error' 'Volumes de données' ("introuvables : " + ($manquantsV -join ', '))
} else {
    Noter 'ok' 'Volumes de données' "${Projet}_db-data et ${Projet}_app-data présents"
}

# --- 3. Adresse de J-ed ----------------------------------------------------------------------------------
Titre "3. Adresse http://localhost:$Port"

$pages = @(@('/comptes/connexion/', 'Page de connexion'), @('/hors-ligne/', 'Page hors ligne'), @('/sw.js', 'Service worker'), @('/manifest.webmanifest', 'Manifeste'))
foreach ($p in $pages) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$Port$($p[0])" -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        $csp = $r.Headers['Content-Security-Policy']
        if ($p[0] -eq '/comptes/connexion/' -and -not $csp) {
            Noter 'error' $p[1] 'répond, mais sans politique de sécurité (CSP)'
        } else {
            Noter 'ok' $p[1] "répond (HTTP $($r.StatusCode))"
        }
    } catch {
        Noter 'error' $p[1] "ne répond pas : $($_.Exception.Message)"
    }
}

# 2.0.0 (lot 1) : contrôle de santé utilisé par Docker (le serveur répond et la base est joignable).
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$Port/sante/" -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
    Noter 'ok' 'Contrôle de santé' "le serveur répond et la base est joignable (HTTP $($r.StatusCode))"
} catch {
    $code = 0
    if ($_.Exception.Response) { try { $code = [int]$_.Exception.Response.StatusCode } catch { $code = 0 } }
    if ($code -eq 404) {
        Noter 'skipped' 'Contrôle de santé' 'adresse /sante/ absente : version antérieure au lot 1 de la 2.0.0'
    } elseif ($code -eq 503) {
        Noter 'error' 'Contrôle de santé' 'le serveur répond, mais la base de données est injoignable (HTTP 503)'
    } else {
        Noter 'error' 'Contrôle de santé' "ne répond pas : $($_.Exception.Message)"
    }
}

# --- 4. Fonctions de l'application ---------------------------------------------------------------------------
Titre '4. Fonctions de l''application (données fictives, base non modifiée)'

$commande = @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'verifier_fonctionnalites', '--json')
if ($AvecSources) { $commande += '--sources' }
Write-Host 'Vérification en cours (une à trois minutes)…' -ForegroundColor Gray
$verif = Docker-Ici $commande
$resultat = Lire-Json $verif.Texte
if (-not $resultat) {
    Noter 'error' 'Vérification dans l''application' 'impossible à lancer' @(($verif.Texte -split "`n" | Select-Object -Last 5))
} else {
    if ($resultat.version -ne $Version) {
        Noter 'error' 'Version en service' "l'application répond en $($resultat.version), le dossier contient la $Version : redémarrez (docker compose up -d --build)"
    }
    foreach ($v in $resultat.verifications) {
        Noter $v.niveau $v.libelle $v.resume @($v.details)
    }
}

if ($AvecTests) {
    Titre '5. Tests automatiques (base de test séparée)'
    Write-Host 'Tests en cours (3 à 10 minutes)…' -ForegroundColor Gray
    $tests = Docker-Ici @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'test', 'tests', '--noinput')
    $ran = [regex]::Match($tests.Texte, 'Ran (\d+) tests?')
    if ($tests.Code -eq 0 -and $tests.Texte -match '(?m)^OK') {
        Noter 'ok' 'Tests automatiques' "$($ran.Groups[1].Value) tests réussis"
    } else {
        $echecs = @($tests.Texte -split "`n" | Where-Object { $_ -match '^(FAIL|ERROR):' } | Select-Object -First 10)
        Noter 'error' 'Tests automatiques' "échec ($($ran.Groups[1].Value) tests lancés)" $echecs
    }
}

# --- Bilan ---------------------------------------------------------------------------------------------
Titre 'Bilan'
$resume = "OK : $($script:Bilan.ok) ; à surveiller : $($script:Bilan.warning) ; problèmes : $($script:Bilan.error) ; non vérifié : $($script:Bilan.skipped)"
Write-Host $resume
$script:Lignes.Add($resume)
$script:Lignes.Add('Rapport sans clé, sans nom de compte et sans texte de recherche ou de traduction.')
$Rapport = [System.IO.Path]::Combine((Split-Path -Parent $Dossier), "verification-j-ed-$(Get-Date -Format 'yyyyMMdd-HHmm').txt")
($script:Lignes | ForEach-Object { Masquer $_ }) | Set-Content -LiteralPath $Rapport -Encoding UTF8
Write-Host "Rapport enregistré : $Rapport"
if ($script:Bilan.error) { exit 1 }
exit 0
