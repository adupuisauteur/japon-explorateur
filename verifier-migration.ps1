<#
.SYNOPSIS
    Après le passage de J-ed sur un nouvel ordinateur : fait l'inventaire de toutes les installations J-ed
    présentes dans Docker et vérifie que leurs données sont là. Ne modifie rien.

.DESCRIPTION
    Pour chaque installation trouvée dans Docker (volumes et conteneurs), le script indique :
      - les volumes de données présents (base, fichiers, Argos, IA locale) ;
      - les conteneurs et leur état ; il ne démarre rien, il dit seulement comment démarrer ;
      - le dossier de l'installation sur l'ordinateur, son fichier .env (nom, port, autorisation des noms
        protégés, dossier des sauvegardes) et sa version ;
      - si la base tourne : le nombre de notices, d'entrées de bibliothèque, de dossiers, de projets de
        traduction, de comptes et de sauvegardes, et les dernières migrations appliquées
        (requêtes en lecture seule) ;
      - si l'application tourne : la réponse de son adresse.
    Comparez ces nombres avec ceux de l'ancien ordinateur. Pour une installation 2.0.0 qui tourne, lancez
    ensuite son propre verifier-j-ed.ps1, qui essaie chaque fonction.
    Un rapport texte, sans mot de passe, sans clé et sans nom de compte, est enregistré dans le dossier courant.

.PARAMETER Dossiers
    Dossiers d'installation à examiner en plus (ceux qui contiennent docker-compose.yml et .env), si le
    script ne les retrouve pas seul, par exemple parce qu'aucun conteneur n'a encore été créé sur cet ordinateur.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\verifier-migration.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\verifier-migration.ps1 -Dossiers C:\J-ed\japon-explorateur-1.1.0,D:\JaponEssai\japon-explorateur-2.0.0-rc1
#>
[CmdletBinding()]
param(
    [string[]]$Dossiers = @()
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
# 2.0.3 (Linux, décision D1) : ce script sert tel quel sous Windows (Windows PowerShell 5.1) et sous Linux
# (PowerShell 7, lancé par « pwsh -NoProfile -File »). La variable IsLinux n'existe pas sous 5.1 : lue ainsi, elle vaut faux.
$SousLinux = ((Get-Variable -Name IsLinux -ValueOnly -ErrorAction SilentlyContinue) -eq $true)
$ConseilDocker = 'ne répond pas : démarrez Docker Desktop, attendez « Engine running », puis relancez ce script'
$ConseilMemoire = 'Docker Desktop → Settings → Resources (ou fichier .wslconfig).'
if ($SousLinux) {
    $ConseilDocker = 'ne répond pas : vérifiez qu''il est démarré (« sudo systemctl start docker ») et que votre compte est dans le groupe docker, puis relancez ce script'
    $ConseilMemoire = 'Sous Linux, Docker utilise la mémoire de l''ordinateur : en ajouter à la machine (ou à la machine virtuelle).'
}
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

function Lire-Env([string[]]$EnvLignes, [string]$Nom) {
    # Comme Docker Compose : si une variable figure plusieurs fois, c'est la DERNIÈRE ligne qui compte.
    $valeur = ''
    foreach ($ligne in $EnvLignes) {
        if ($ligne -match "^\s*$Nom\s*=(.*)$") { $valeur = $Matches[1].Trim().Trim('"').Trim("'") }
    }
    return $valeur
}

function Chemin([string]$Dossier, [string]$Fichier) {
    # Join-Path échoue sur un lecteur absent (E:\ de l'ancien ordinateur) ; Combine ne vérifie rien.
    return [System.IO.Path]::Combine($Dossier, $Fichier)
}

function Existe([string]$Chemin) {
    try { return [bool](Test-Path -LiteralPath $Chemin -ErrorAction Stop) } catch { return $false }
}

function Etiquette([string]$Etiquettes, [string]$Cle) {
    if ($Etiquettes -match ("(?:^|,)" + [regex]::Escape($Cle) + "=([^,]*)")) { return $Matches[1].Trim() }
    return ''
}

function Taille([double]$Octets) {
    if ($Octets -ge 1GB) { return '{0:N1} Go' -f ($Octets / 1GB) }
    if ($Octets -ge 1MB) { return '{0:N1} Mo' -f ($Octets / 1MB) }
    return '{0:N0} Ko' -f ($Octets / 1KB)
}

$debut = Get-Date
$script:Lignes.Add("Vérification après migration de J-ed — $($debut.ToString('dd/MM/yyyy HH:mm'))")
$script:Lignes.Add("Ordinateur : $([Environment]::MachineName)")
Write-Host "Vérification après migration de J-ed — $($debut.ToString('dd/MM/yyyy HH:mm')) (rien n'est modifié)" -ForegroundColor Cyan

# ---------------------------------------------------------------------------------------------------------
Titre '1. Docker sur cet ordinateur'
$info = Docker-Ici @('info', '--format', '{{.ServerVersion}}|{{.MemTotal}}|{{.NCPU}}|{{.OperatingSystem}}')
if ($info.Code -ne 0 -or -not $info.Texte -or $info.Texte -notmatch '\|') {
    Noter 'error' 'Docker' $ConseilDocker @($info.Texte -split "`n" | Select-Object -First 3)
    $script:Lignes | Set-Content -Path (Join-Path (Get-Location) ("verification-migration-{0}.txt" -f $debut.ToString('yyyyMMdd-HHmm'))) -Encoding UTF8
    exit 1
}
$p = $info.Texte.Split('|')
$memoire = 0.0
[void][double]::TryParse($p[1], [ref]$memoire)
$niveauMemoire = 'ok'
if ($memoire -gt 0 -and $memoire -lt 6GB) { $niveauMemoire = 'warning' }
Noter $niveauMemoire 'Docker' "en service, version $($p[0])" @("Mémoire accordée à Docker : $(Taille $memoire) ; cœurs : $($p[2]) ; $($p[3])")
if ($niveauMemoire -eq 'warning') {
    Noter 'warning' 'Mémoire' 'moins de 6 Go accordés à Docker : Argos et l''IA locale risquent de manquer de place' @($ConseilMemoire)
}

# ---------------------------------------------------------------------------------------------------------
# Inventaire : volumes, conteneurs, dossiers donnés en paramètre.
$volumes = @{}
# Pas de guillemets doubles dans les arguments : Windows PowerShell 5.1 les retire en appelant docker
# ({{.Label "…"}} devenait {{.Label …}}, refusé ; constaté le 18 novembre 2026). Les étiquettes sont lues
# dans {{.Labels}} (« clé=valeur,clé=valeur »).
$v = Docker-Ici @('volume', 'ls', '--format', '{{.Name}}|{{.Labels}}')
if ($v.Code -ne 0) {
    Noter 'error' 'Liste des volumes' 'docker volume ls a échoué' @($v.Texte -split "`n" | Select-Object -First 3)
}
foreach ($ligne in ($v.Texte -split "`n")) {
    if ($v.Code -ne 0 -or $ligne -notmatch '\|') { continue }
    $morceaux = $ligne.Split('|', 2)
    $volumes[$morceaux[0].Trim()] = Etiquette $morceaux[1] 'com.docker.compose.project'
}
$conteneurs = @()
$c = Docker-Ici @('ps', '-a', '--format', '{{.State}}|{{.Names}}|{{.Ports}}|{{.Labels}}')
if ($c.Code -ne 0) {
    Noter 'error' 'Liste des conteneurs' 'docker ps a échoué' @($c.Texte -split "`n" | Select-Object -First 3)
}
foreach ($ligne in ($c.Texte -split "`n")) {
    if ($c.Code -ne 0 -or $ligne -notmatch '\|') { continue }
    $m = $ligne.Split('|', 4)
    $conteneurs += [pscustomobject]@{
        Projet = Etiquette $m[3] 'com.docker.compose.project'; Service = Etiquette $m[3] 'com.docker.compose.service'
        Etat = $m[0]; Nom = $m[1]; Ports = $m[2]; Dossier = Etiquette $m[3] 'com.docker.compose.project.working_dir'
    }
}
$dossiersEnv = @{}
foreach ($d in $Dossiers) {
    $envFichier = Chemin $d '.env'
    if (Existe $envFichier) {
        $nom = Lire-Env (Get-Content -LiteralPath $envFichier -Encoding UTF8) 'COMPOSE_PROJECT_NAME'
        if ($nom) { $dossiersEnv[$nom] = $d }
    }
}

# Une installation J-ed = un projet Docker qui a un volume <nom>_db-data (ou des conteneurs web + db).
$projets = New-Object System.Collections.Generic.SortedSet[string]
foreach ($nom in $volumes.Keys) {
    if ($nom -match '^(.+)_db-data$') { [void]$projets.Add($Matches[1]) }
}
foreach ($k in ($conteneurs | Group-Object Projet)) {
    if ($k.Name -and ($k.Group.Service -contains 'web') -and ($k.Group.Service -contains 'db')) { [void]$projets.Add($k.Name) }
}
foreach ($nom in $dossiersEnv.Keys) { [void]$projets.Add($nom) }

Titre '2. Installations J-ed trouvées'
if ($projets.Count -eq 0) {
    Noter 'error' 'Installations' 'aucune trouvée dans Docker : ni volume « …_db-data », ni conteneurs J-ed' @(
        'Si les données ont été copiées autrement, indiquez les dossiers d''installation avec -Dossiers.')
} else {
    Noter 'ok' 'Installations' "$($projets.Count) trouvée(s) : $([string]::Join(', ', $projets))"
}

$sql = @"
select t, (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I', t), false, true, '')))[1]::text
from unnest(array['catalog_record','library_libraryentry','library_collection','translation_translationproject',
                  'translation_translationdocument','accounts_user','catalog_catalogue','backups_backupjob']) as t
where to_regclass(t) is not null;
"@
$libelles = @{
    catalog_record = 'Notices'; library_libraryentry = 'Entrées de bibliothèque'; library_collection = 'Dossiers'
    translation_translationproject = 'Projets de traduction'; translation_translationdocument = 'Documents à traduire'
    accounts_user = 'Comptes'; catalog_catalogue = 'Sources'; backups_backupjob = 'Sauvegardes enregistrées'
}
$comparaison = New-Object System.Collections.Generic.List[string]

foreach ($projet in $projets) {
    $protege = $NomsProteges -contains $projet
    $suffixe = ''
    if ($protege) { $suffixe = ' (nom protégé)' }
    Titre "Installation « $projet »$suffixe"

    # Volumes
    $manquants = @()
    foreach ($req in @('db-data', 'app-data')) {
        if (-not $volumes.ContainsKey("${projet}_$req")) { $manquants += "${projet}_$req" }
    }
    $facultatifs = @()
    foreach ($opt in @('argos-packages', 'argos-depot', 'ollama-models', 'sauvegardes-externes')) {
        if ($volumes.ContainsKey("${projet}_$opt")) { $facultatifs += $opt }
    }
    if ($manquants.Count -gt 0) {
        Noter 'error' 'Volumes de données' "absent(s) : $([string]::Join(', ', $manquants))" @(
            'Sans ces volumes, la base ou les fichiers de cette installation ne sont pas sur cet ordinateur.')
    } else {
        $detail = 'aucun volume facultatif'
        if ($facultatifs.Count -gt 0) { $detail = "aussi : $([string]::Join(', ', $facultatifs))" }
        Noter 'ok' 'Volumes de données' "${projet}_db-data et ${projet}_app-data présents" @($detail)
    }

    # Conteneurs
    $siens = @($conteneurs | Where-Object { $_.Projet -eq $projet })
    $dossier = ''
    if ($dossiersEnv.ContainsKey($projet)) { $dossier = $dossiersEnv[$projet] }
    if (-not $dossier) {
        $avecDossier = $siens | Where-Object { $_.Dossier } | Select-Object -First 1
        if ($avecDossier) { $dossier = $avecDossier.Dossier }
    }
    $db = $siens | Where-Object { $_.Service -eq 'db' } | Select-Object -First 1
    $web = $siens | Where-Object { $_.Service -eq 'web' } | Select-Object -First 1
    if ($siens.Count -eq 0) {
        Noter 'warning' 'Conteneurs' 'aucun sur cet ordinateur' @(
            'Normal si seuls les volumes ont été copiés. Pour démarrer : dans le dossier de l''installation, docker compose up -d')
    } else {
        $enService = @($siens | Where-Object { $_.Etat -eq 'running' } | ForEach-Object { $_.Service } | Sort-Object)
        $arretes = @($siens | Where-Object { $_.Etat -ne 'running' } | ForEach-Object { "$($_.Service) ($($_.Etat))" } | Sort-Object)
        $niveau = 'ok'
        $resume = "en service : $([string]::Join(', ', $enService))"
        if ($enService.Count -eq 0) { $niveau = 'warning'; $resume = 'tous arrêtés' }
        $details = @()
        if ($arretes.Count -gt 0) { $details += "Arrêtés : $([string]::Join(', ', $arretes))" }
        if ($enService.Count -eq 0) { $details += 'Pour démarrer : dans le dossier de l''installation, docker compose up -d (puis relancez ce script).' }
        Noter $niveau 'Conteneurs' $resume $details
    }

    # Dossier et .env
    $port = ''
    if (-not $dossier) {
        Noter 'skipped' 'Dossier de l''installation' 'inconnu : indiquez-le avec -Dossiers pour vérifier son .env'
    } elseif (-not (Existe (Chemin $dossier 'docker-compose.yml'))) {
        Noter 'warning' 'Dossier de l''installation' "« $dossier » introuvable ici, ou sans docker-compose.yml" @(
            'C''est souvent le chemin de l''ancien ordinateur, gardé par les conteneurs copiés. Copiez le dossier au',
            'même endroit, ou indiquez son nouvel emplacement avec -Dossiers.')
    } else {
        $version = '(fichier VERSION absent)'
        $fichierVersion = Chemin $dossier 'VERSION'
        if (Existe $fichierVersion) { $version = "J-ed $((Get-Content -LiteralPath $fichierVersion -TotalCount 1).Trim())" }
        $envFichier = Chemin $dossier '.env'
        if (-not (Existe $envFichier)) {
            Noter 'error' 'Dossier de l''installation' "$dossier — $version, mais .env absent" @(
                'Le fichier .env contient les mots de passe techniques : sans lui, l''installation ne démarre pas.',
                'Recopiez-le depuis l''ancien ordinateur (il ne doit pas être recréé : les clés changeraient).')
        } else {
            $envLignes = Get-Content -LiteralPath $envFichier -Encoding UTF8
            $nomEnv = Lire-Env $envLignes 'COMPOSE_PROJECT_NAME'
            $port = Lire-Env $envLignes 'WEB_PORT'
            if (-not $port) { $port = '8000' }
            $details = @("$version ; port $port")
            $niveau = 'ok'
            if ($nomEnv -ne $projet) {
                $niveau = 'error'
                $details += "COMPOSE_PROJECT_NAME vaut « $nomEnv » dans .env, au lieu de « $projet » : ce dossier n'utiliserait pas ces données."
            }
            if ($protege -and (Lire-Env $envLignes 'AUTORISER_NOM_PROJET') -ne $projet) {
                $niveau = 'error'
                $details += "Nom protégé sans « AUTORISER_NOM_PROJET=$projet » dans .env : J-ed refusera de démarrer."
            }
            foreach ($cle in @('POSTGRES_PASSWORD', 'DJANGO_SECRET_KEY')) {
                $val = Lire-Env $envLignes $cle
                if (-not $val -or $val -match 'remplacer') {
                    $niveau = 'error'
                    $details += "$cle vide ou à remplacer dans .env : ce n'est pas le .env de l'ancien ordinateur."
                }
            }
            Noter $niveau 'Dossier de l''installation' $dossier $details

            $sauvegardes = Lire-Env $envLignes 'DOSSIER_SAUVEGARDES'
            if (-not $sauvegardes) {
                Noter 'skipped' 'Dossier des sauvegardes' 'non réglé dans .env (DOSSIER_SAUVEGARDES)'
            } elseif (-not (Existe $sauvegardes)) {
                Noter 'warning' 'Dossier des sauvegardes' "« $sauvegardes » introuvable sur cet ordinateur" @(
                    'Créez-le ou recopiez-le, sinon les copies externes des sauvegardes échoueront.')
            } else {
                $copies = @(Get-ChildItem -LiteralPath $sauvegardes -Filter 'sauvegarde-*.tar' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
                if ($copies.Count -eq 0) {
                    Noter 'warning' 'Dossier des sauvegardes' "$sauvegardes : présent, mais aucune sauvegarde dedans"
                } else {
                    $total = ($copies | Measure-Object Length -Sum).Sum
                    Noter 'ok' 'Dossier des sauvegardes' "$sauvegardes : $($copies.Count) copie(s), $(Taille $total)" @(
                        "Dernière : $($copies[0].Name) ($(Taille $copies[0].Length))")
                }
            }
        }
    }

    # Base de données (lecture seule)
    if (-not $db -or $db.Etat -ne 'running') {
        Noter 'skipped' 'Contenu de la base' 'base arrêtée : démarrez l''installation pour compter les données'
    } else {
        $r = Docker-Ici @('exec', $db.Nom, 'psql', '-U', 'japon', '-d', 'japon', '-tA', '-F', '|', '-v', 'ON_ERROR_STOP=1', '-c', $sql)
        if ($r.Code -ne 0) {
            Noter 'error' 'Contenu de la base' 'lecture impossible' @($r.Texte -split "`n" | Select-Object -First 3)
        } else {
            $details = @()
            $notices = -1
            foreach ($ligne in ($r.Texte -split "`n")) {
                if ($ligne -notmatch '\|') { continue }
                $m = $ligne.Split('|')
                $details += "{0} : {1}" -f $libelles[$m[0]], $m[1]
                $comparaison.Add(("{0,-28} {1,-28} {2}" -f $projet, $libelles[$m[0]], $m[1]))
                if ($m[0] -eq 'catalog_record') { $notices = [int]$m[1] }
            }
            $niveau = 'ok'
            if ($notices -eq 0) { $niveau = 'warning' }
            Noter $niveau 'Contenu de la base' "$notices notice(s)" $details
            $mig = Docker-Ici @('exec', $db.Nom, 'psql', '-U', 'japon', '-d', 'japon', '-tA', '-F', ' ', '-c',
                "select app, name from django_migrations where id in (select max(id) from django_migrations group by app) and app in ('catalog','core','translation','library','ai') order by app;")
            if ($mig.Code -eq 0 -and $mig.Texte) {
                Noter 'ok' 'Dernières migrations' 'appliquées dans la base' @($mig.Texte -split "`n")
            }
        }
    }

    # Adresse de l'application
    if (-not $web -or $web.Etat -ne 'running') {
        Noter 'skipped' 'Adresse de l''application' 'application arrêtée'
    } else {
        $portPublie = ''
        if ($web.Ports -match '(127\.0\.0\.1|0\.0\.0\.0|\[::\]|::):(\d+)->8000') { $portPublie = $Matches[2] }
        if (-not $portPublie) { $portPublie = $port }
        if (-not $portPublie) {
            Noter 'skipped' 'Adresse de l''application' 'port publié inconnu'
        } else {
            $adresse = "http://localhost:$portPublie/"
            $code = 0
            foreach ($chemin in @('sante/', '')) {
                try {
                    $rep = Invoke-WebRequest -Uri ($adresse + $chemin) -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
                    $code = [int]$rep.StatusCode
                } catch {
                    $code = 0
                    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
                }
                if ($code -gt 0 -and $code -lt 400) { break }
            }
            if ($code -gt 0 -and $code -lt 400) {
                Noter 'ok' 'Adresse de l''application' "$adresse répond (HTTP $code)"
            } else {
                Noter 'error' 'Adresse de l''application' "$adresse ne répond pas (HTTP $code)" @(
                    'Attendez une minute après le démarrage, puis relancez. Sinon : docker compose logs --tail 100 web')
            }
        }
    }

    if ($dossier -and (Existe (Chemin $dossier 'verifier-j-ed.ps1')) -and $web -and $web.Etat -eq 'running') {
        $script:Lignes.Add("    Ensuite, pour essayer chaque fonction : cd `"$dossier`" puis powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1")
        Write-Host "    Ensuite, pour essayer chaque fonction : cd `"$dossier`"" -ForegroundColor Gray
        Write-Host '    puis : powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1' -ForegroundColor Gray
    }
}

# ---------------------------------------------------------------------------------------------------------
Titre '3. Images Docker de J-ed'
$i = Docker-Ici @('images', '--format', '{{.Repository}}:{{.Tag}}|{{.Size}}')
$images = @($i.Texte -split "`n" | Where-Object { $_ -match '^(japon-explorateur|postgres|redis|ollama/ollama)' })
if ($i.Code -ne 0) {
    Noter 'error' 'Images' 'docker images a échoué' @($i.Texte -split "`n" | Select-Object -First 3)
} elseif ($images.Count -eq 0) {
    Noter 'warning' 'Images' 'aucune image de J-ed : elles seront reconstruites ou téléchargées au premier démarrage (Internet nécessaire)'
} else {
    Noter 'ok' 'Images' "$($images.Count) image(s)" @($images | ForEach-Object { $_.Replace('|', ' — ') })
}

# ---------------------------------------------------------------------------------------------------------
if ($comparaison.Count -gt 0) {
    Titre '4. À comparer avec l''ancien ordinateur'
    foreach ($l in $comparaison) {
        Write-Host "    $l"
        $script:Lignes.Add("    $l")
    }
}

Titre 'Bilan'
$bilan = "OK : $($script:Bilan.ok) ; à surveiller : $($script:Bilan.warning) ; problèmes : $($script:Bilan.error) ; non vérifié : $($script:Bilan.skipped)"
Write-Host $bilan
$script:Lignes.Add($bilan)
$script:Lignes.Add('Rapport sans mot de passe, sans clé et sans nom de compte. Rien n''a été modifié.')
$fichier = Join-Path (Get-Location) ("verification-migration-{0}.txt" -f $debut.ToString('yyyyMMdd-HHmm'))
try {
    $script:Lignes | Set-Content -LiteralPath $fichier -Encoding UTF8
    Write-Host "Rapport enregistré : $fichier" -ForegroundColor Cyan
} catch {
    Write-Host "Rapport non enregistré ($($_.Exception.Message))" -ForegroundColor Yellow
}
if ($script:Bilan.error -gt 0) { exit 1 }
exit 0
