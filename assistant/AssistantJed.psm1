<#
.SYNOPSIS
    Logique de l'assistant J-ed (2.0.2) : tout ce que fait la fenêtre, sans la fenêtre.

.DESCRIPTION
    Ce module ne contient aucune logique d'installation ni de mise à jour : il retrouve les installations,
    vérifie les prérequis, prépare les paramètres des scripts de J-ed, les lance et lit ce qu'ils rendent
    (journal, codes de sortie), comme le décrit docs/contrat-scripts.md. Il est séparé de l'affichage pour être
    testé automatiquement (PowerShell 7, docker simulé). Compatible Windows PowerShell 5.1.

    Règles : jamais « docker compose down -v » ; jamais l'option -Oui du script de mise à jour (la confirmation
    vient toujours de l'utilisateur) ; aucun secret du fichier .env n'est renvoyé ni écrit.
#>

$script:NomsProteges = @('japon-explorateur', 'japon-explorateur-essai')
$script:Utf8SansBom = New-Object System.Text.UTF8Encoding($false)
$script:PageAide = 'AVANT-DE-COMMENCER.html'

# --- Outils ------------------------------------------------------------------------------------------------

function Join-CheminJed([string]$Parent, [string]$Enfant) {
    return [System.IO.Path]::Combine($Parent, $Enfant)
}

function Get-CleCheminJed([string]$Chemin) {
    # Forme comparable d'un chemin de dossier (sans séparateur final, sans casse).
    if (-not $Chemin) { return '' }
    try { $plein = [System.IO.Path]::GetFullPath($Chemin) } catch { $plein = $Chemin }
    return $plein.TrimEnd('\', '/').ToLowerInvariant()
}

function Invoke-DockerJed {
    <# Lance docker (dans un dossier si demandé) ; renvoie le code et le texte (sortie et erreurs). #>
    param([string]$Dossier, [string[]]$Arguments, [scriptblock]$SurAttente, [scriptblock]$SurLigne)
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Code = 127; Texte = "docker n'est pas reconnu : Docker Desktop n'est pas installé." }
    }
    if ($SurAttente -or $SurLigne) {
        # Depuis la fenêtre : processus à part, pour qu'elle reste active pendant une longue commande.
        $moteur = (Get-Command docker).Source
        $r = Invoke-ScriptJed -Moteur $moteur -Arguments $Arguments -Dossier $Dossier -SurAttente $SurAttente -SurLigne $SurLigne
        return [pscustomobject]@{ Code = $r.Code; Texte = (@($r.Lignes) -join "`n").Trim() }
    }
    # Windows PowerShell 5.1 : avec « Stop » (réglage de la fenêtre), une seule ligne écrite par docker sur la
    # sortie d'erreur arrêterait tout (exception non gérée). Ici, ces lignes sont du texte à lire : « Continue ».
    $ErrorActionPreference = 'Continue'
    if ($Dossier) { Push-Location -LiteralPath $Dossier }
    try {
        $sortie = & docker @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        if ($Dossier) { Pop-Location }
    }
    # Une ligne de la sortie d'erreur arrive comme ErrorRecord : on garde son texte (voir mettre-a-jour.ps1).
    $lignes = @($sortie | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
    })
    return [pscustomobject]@{ Code = $code; Texte = ($lignes -join "`n").Trim() }
}

function Read-EnvJed([string]$Fichier) {
    <# Variables d'un fichier .env ; comme Docker Compose, la dernière ligne d'une variable compte.
       Usage interne : ne jamais afficher ni journaliser le résultat (il contient les mots de passe). #>
    $valeurs = @{}
    foreach ($ligne in [System.IO.File]::ReadAllLines($Fichier, [System.Text.Encoding]::UTF8)) {
        if ($ligne -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') { $valeurs[$Matches[1]] = $Matches[2].Trim() }
    }
    return $valeurs
}

# --- Installations ---------------------------------------------------------------------------------------

function Get-InstallationJed {
    <# Décrit l'installation d'un dossier : nom du projet, port, version, dossier des sauvegardes. #>
    param([Parameter(Mandatory = $true)][string]$Dossier)
    try { $d = [System.IO.Path]::GetFullPath($Dossier).TrimEnd('\', '/') } catch { $d = $Dossier }
    $res = [pscustomobject]@{
        Dossier = $d; Nom = ''; Port = 8000; Version = ''; DossierSauvegardes = ''; Essai = $false
        Protegee = $false; Valide = $false; Probleme = ''; Etat = 'inconnu'; Ancien = $false; Remplacant = ''
    }
    if (-not (Test-Path -LiteralPath $d -PathType Container)) {
        $res.Probleme = 'dossier introuvable (déplacé ou supprimé ?)'
        return $res
    }
    if (-not (Test-Path -LiteralPath (Join-CheminJed $d 'docker-compose.yml'))) {
        $res.Probleme = "docker-compose.yml absent : ce n'est pas le dossier d'une installation de J-ed"
        return $res
    }
    $fichierEnv = Join-CheminJed $d '.env'
    if (-not (Test-Path -LiteralPath $fichierEnv)) {
        $res.Probleme = 'fichier .env absent : installation pas encore configurée'
        return $res
    }
    $valeurs = Read-EnvJed $fichierEnv
    $nom = "$($valeurs['COMPOSE_PROJECT_NAME'])"
    if (-not $nom) {
        $res.Probleme = 'COMPOSE_PROJECT_NAME absent du fichier .env'
        return $res
    }
    $res.Nom = $nom
    if ("$($valeurs['WEB_PORT'])" -match '^\d+$') { $res.Port = [int]$valeurs['WEB_PORT'] }
    $fichierVersion = Join-CheminJed $d 'VERSION'
    if (Test-Path -LiteralPath $fichierVersion) {
        $res.Version = ([System.IO.File]::ReadAllText($fichierVersion)).Trim()
    } else {
        $res.Version = '?'
    }
    $res.DossierSauvegardes = "$($valeurs['DOSSIER_SAUVEGARDES'])"
    $res.Essai = $nom -match 'essai'
    $res.Protegee = $script:NomsProteges -contains $nom
    $res.Valide = $true
    return $res
}

function Get-TexteProtegeeJed($Installation) {
    <# 2.0.2-rc5 (R3) : phrase d'avertissement d'une installation protégée, propre à chacun des deux noms. #>
    if ($Installation.Nom -eq 'japon-explorateur') {
        return "« $($Installation.Nom) » est une installation protégée : c'est sans doute votre installation principale."
    }
    return "« $($Installation.Nom) » est une installation protégée : c'est votre installation d'essai de référence."
}

function Get-FichierListeJed {
    <# Fichier où l'assistant garde les dossiers d'installation déjà vus (chemins seulement). #>
    $base = $env:LOCALAPPDATA
    if (-not $base) { $base = [System.IO.Path]::GetTempPath() }
    return Join-CheminJed (Join-CheminJed $base 'J-ed') 'installations.txt'
}

function Read-ListeInstallationsJed([string]$Fichier) {
    if (-not $Fichier -or -not (Test-Path -LiteralPath $Fichier)) { return ,@() }
    $vus = @{}
    $liste = New-Object System.Collections.Generic.List[string]
    foreach ($ligne in [System.IO.File]::ReadAllLines($Fichier, [System.Text.Encoding]::UTF8)) {
        $chemin = $ligne.Trim()
        if (-not $chemin) { continue }
        $cle = Get-CleCheminJed $chemin
        if (-not $vus.ContainsKey($cle)) { $vus[$cle] = $true; $liste.Add($chemin) }
    }
    return ,$liste.ToArray()
}

function Add-InstallationListeJed {
    <# Ajoute un dossier à la liste gardée (sans doublon). Ne renvoie rien. #>
    param([string]$Fichier, [string]$Dossier)
    $actuels = Read-ListeInstallationsJed $Fichier
    $cle = Get-CleCheminJed $Dossier
    foreach ($c in $actuels) { if ((Get-CleCheminJed $c) -eq $cle) { return } }
    $parent = Split-Path -Parent $Fichier
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $plein = [System.IO.Path]::GetFullPath($Dossier).TrimEnd('\', '/')
    [System.IO.File]::AppendAllText($Fichier, "$plein`r`n", $script:Utf8SansBom)
}

function Find-InstallationsJed {
    <# Toutes les installations connues : celles que Docker voit (docker compose ls -a) et celles de la liste
       gardée (une installation arrêtée par « down » n'apparaît plus dans Docker). Les nouvelles installations
       valides trouvées par Docker sont ajoutées à la liste. #>
    param([string]$Fichier = (Get-FichierListeJed))
    $dossiers = New-Object System.Collections.Generic.List[string]
    $etats = @{}
    $ls = Invoke-DockerJed '' @('compose', 'ls', '-a', '--format', 'json')
    # 2.0.2-rc5 (R22) : si Docker ne répond pas, l'état des installations est inconnu (et non « arrêtée »).
    $dockerMuet = ($ls.Code -ne 0)
    if ($ls.Code -eq 0 -and $ls.Texte) {
        $projets = @()
        try { $projets = @(($ls.Texte | ConvertFrom-Json) | ForEach-Object { $_ }) } catch { $projets = @() }
        foreach ($projet in $projets) {
            foreach ($f in ("$($projet.ConfigFiles)" -split ',')) {
                if (-not $f.Trim()) { continue }
                $dossier = Split-Path -Parent $f.Trim()
                $dossiers.Add($dossier)
                $etats[(Get-CleCheminJed $dossier)] = "$($projet.Status)"
            }
        }
    }
    foreach ($d in (Read-ListeInstallationsJed $Fichier)) { $dossiers.Add($d) }

    $vus = @{}
    $resultat = New-Object System.Collections.Generic.List[object]
    foreach ($d in $dossiers) {
        $cle = Get-CleCheminJed $d
        if ($vus.ContainsKey($cle)) { continue }
        $vus[$cle] = $true
        $inst = Get-InstallationJed $d
        if ($etats.ContainsKey($cle)) {
            if ($etats[$cle] -match 'running') { $inst.Etat = 'en marche' } else { $inst.Etat = 'arrêtée' }
            if ($inst.Valide -and $Fichier) { Add-InstallationListeJed $Fichier $inst.Dossier }
        } elseif ($inst.Valide) {
            if ($dockerMuet) { $inst.Etat = '? (Docker arrêté)' } else { $inst.Etat = 'arrêtée' }
        }
        $resultat.Add($inst)
    }
    Set-AnciensDossiersJed $resultat
    return ,@($resultat | Sort-Object -Property Nom, Dossier)
}

function Set-AnciensDossiersJed {
    <# 2.0.2-rc5 (R10) : après une mise à jour, l'ancien dossier (gardé exprès) porte le même nom de projet que la
       nouvelle version. Dans chaque groupe de même nom, l'installation en service est celle qui est en marche ;
       si aucune ne l'est, celle de la version la plus récente. Les autres sont marquées « ancien dossier ». #>
    param($Installations)
    $groupes = @{}
    foreach ($i in $Installations) {
        if (-not $i.Valide -or -not $i.Nom) { continue }
        $cle = $i.Nom.ToLowerInvariant()
        if (-not $groupes.ContainsKey($cle)) { $groupes[$cle] = New-Object System.Collections.Generic.List[object] }
        $groupes[$cle].Add($i)
    }
    foreach ($g in $groupes.Values) {
        if ($g.Count -lt 2) { continue }
        $actuelle = $null
        foreach ($i in $g) { if ($i.Etat -eq 'en marche') { $actuelle = $i; break } }
        if (-not $actuelle) {
            foreach ($i in $g) {
                if (-not $actuelle -or (Compare-VersionJed $i.Version $actuelle.Version) -gt 0) { $actuelle = $i }
            }
        }
        foreach ($i in $g) {
            if ([object]::ReferenceEquals($i, $actuelle)) { continue }
            if ($i.Etat -eq 'en marche') { continue }
            $i.Ancien = $true
            $i.Remplacant = $actuelle.Dossier
            $i.Etat = "ancien dossier (en service : $($actuelle.Version))"
        }
    }
}

# --- Prérequis ---------------------------------------------------------------------------------------------

function Get-FaitsSystemeJed {
    <# Relève les faits utiles aux prérequis. Chaque valeur inconnue vaut $null. #>
    param([string]$Dossier)
    $faits = [ordered]@{
        Windows = ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT)
        Bits64 = [Environment]::Is64BitOperatingSystem
        Build = [Environment]::OSVersion.Version.Build
        MemoireGo = $null; Virtualisation = $null; Wsl = $null
        DockerInstalle = [bool](Get-Command docker -ErrorAction SilentlyContinue)
        DockerDemarre = $false; DisqueLibreGo = $null
    }
    if ($faits.Windows) {
        try {
            $ordi = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
            $faits.MemoireGo = [Math]::Round($ordi.TotalPhysicalMemory / 1GB, 1)
            # Un hyperviseur déjà actif (WSL 2, Hyper-V) prouve que la virtualisation est disponible.
            if ($ordi.HypervisorPresent) { $faits.Virtualisation = $true }
        } catch { }
        if ($null -eq $faits.Virtualisation) {
            try {
                $proc = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop)[0]
                $faits.Virtualisation = [bool]$proc.VirtualizationFirmwareEnabled
            } catch { }
        }
        if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
            $ErrorActionPreference = 'Continue'   # voir Invoke-DockerJed (Windows PowerShell 5.1)
            & wsl.exe --status *> $null
            $faits.Wsl = ($LASTEXITCODE -eq 0)
        } else {
            $faits.Wsl = $false
        }
    }
    if ($faits.DockerInstalle) { $faits.DockerDemarre = ((Invoke-DockerJed '' @('info')).Code -eq 0) }
    try {
        $racine = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($(if ($Dossier) { $Dossier } else { '.' })))
        $faits.DisqueLibreGo = [Math]::Round((New-Object System.IO.DriveInfo($racine)).AvailableFreeSpace / 1GB, 1)
    } catch { }
    return [pscustomobject]$faits
}

function Format-NombreJed([double]$Nombre) {
    <# 15,9 et non 15.9 : nombres à la française dans les messages. #>
    return $Nombre.ToString('0.#', [System.Globalization.CultureInfo]::GetCultureInfo('fr-FR'))
}

function New-ControleJed([string]$Cle, [string]$Libelle, [string]$Niveau, [string]$Detail, [string]$Ancre) {
    return [pscustomobject]@{
        Cle = $Cle; Libelle = $Libelle; Niveau = $Niveau; Detail = $Detail; Aide = "$($script:PageAide)#$Ancre"
    }
}

function Test-PrerequisJed {
    <# Évalue les faits relevés : un contrôle par point, niveau ok, attention ou erreur. #>
    param([Parameter(Mandatory = $true)]$Faits)
    $c = New-Object System.Collections.Generic.List[object]
    if (-not $Faits.Windows) {
        $c.Add((New-ControleJed 'windows' 'Windows' 'erreur' "L'assistant fonctionne sous Windows 10 ou 11." 'configuration'))
    } elseif (-not $Faits.Bits64) {
        $c.Add((New-ControleJed 'windows' 'Windows 64 bits' 'erreur' 'Docker Desktop demande un Windows 64 bits.' 'configuration'))
    } elseif ($Faits.Build -lt 19045 -or ($Faits.Build -ge 22000 -and $Faits.Build -lt 22631)) {
        # Docker Desktop demande Windows 10 22H2 (19045) ou Windows 11 23H2 (22631) au moins (documentation, 23/11/2026).
        $c.Add((New-ControleJed 'windows' 'Version de Windows' 'attention' "Windows trop ancien pour Docker Desktop (version $($Faits.Build)) : faites les mises à jour de Windows." 'configuration'))
    } else {
        $c.Add((New-ControleJed 'windows' 'Windows' 'ok' 'Windows 64 bits à jour.' 'configuration'))
    }
    if ($null -eq $Faits.MemoireGo) {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'attention' 'Mémoire inconnue : 8 Go sont conseillés.' 'configuration'))
    } elseif ($Faits.MemoireGo -lt 4) {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'erreur' "$(Format-NombreJed $Faits.MemoireGo) Go : trop peu pour Docker et J-ed (8 Go conseillés)." 'configuration'))
    } elseif ($Faits.MemoireGo -lt 7.5) {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'attention' "$(Format-NombreJed $Faits.MemoireGo) Go : J-ed fonctionnera, lentement ; 8 Go sont conseillés." 'configuration'))
    } else {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'ok' "$(Format-NombreJed $Faits.MemoireGo) Go." 'configuration'))
    }
    if ($null -eq $Faits.Virtualisation) {
        $c.Add((New-ControleJed 'virtualisation' 'Virtualisation' 'attention' 'Impossible de savoir si la virtualisation est active.' 'virtualisation'))
    } elseif ($Faits.Virtualisation) {
        $c.Add((New-ControleJed 'virtualisation' 'Virtualisation' 'ok' 'Active.' 'virtualisation'))
    } else {
        $c.Add((New-ControleJed 'virtualisation' 'Virtualisation' 'erreur' "Désactivée : elle s'active dans les réglages de démarrage de l'ordinateur (BIOS)." 'virtualisation'))
    }
    if ($Faits.Wsl) {
        $c.Add((New-ControleJed 'wsl' 'WSL' 'ok' 'Installé.' 'wsl'))
    } else {
        $c.Add((New-ControleJed 'wsl' 'WSL' 'erreur' "Pas installé : une commande suffit, puis un redémarrage." 'wsl'))
    }
    if (-not $Faits.DockerInstalle) {
        $c.Add((New-ControleJed 'docker' 'Docker Desktop' 'erreur' "Pas installé." 'docker'))
    } elseif (-not $Faits.DockerDemarre) {
        $c.Add((New-ControleJed 'docker' 'Docker Desktop' 'erreur' "Installé mais pas démarré : lancez Docker Desktop et attendez la baleine immobile." 'docker-demarre'))
    } else {
        $c.Add((New-ControleJed 'docker' 'Docker Desktop' 'ok' 'Démarré.' 'docker'))
    }
    if ($null -eq $Faits.DisqueLibreGo) {
        $c.Add((New-ControleJed 'disque' 'Place sur le disque' 'attention' 'Place libre inconnue : 20 Go sont conseillés.' 'disque'))
    } elseif ($Faits.DisqueLibreGo -lt 10) {
        $c.Add((New-ControleJed 'disque' 'Place sur le disque' 'erreur' "$(Format-NombreJed $Faits.DisqueLibreGo) Go libres : trop peu (20 Go conseillés)." 'disque'))
    } elseif ($Faits.DisqueLibreGo -lt 20) {
        $c.Add((New-ControleJed 'disque' 'Place sur le disque' 'attention' "$(Format-NombreJed $Faits.DisqueLibreGo) Go libres : juste (20 Go conseillés)." 'disque'))
    } else {
        $c.Add((New-ControleJed 'disque' 'Place sur le disque' 'ok' "$(Format-NombreJed $Faits.DisqueLibreGo) Go libres." 'disque'))
    }
    return ,$c.ToArray()
}

# --- Nouvelle installation -----------------------------------------------------------------------------

function Get-VolumesDockerJed {
    $r = Invoke-DockerJed '' @('volume', 'ls', '--format', '{{.Name}}')
    if ($r.Code -ne 0) { return $null }
    return ,@($r.Texte -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Test-NomProjetJed {
    <# Un nom de projet neuf : jamais celui d'une installation existante, ni d'anciens volumes de données. #>
    param([string]$Nom, $Installations = @(), $Volumes = @())
    $ko = { param($r) [pscustomobject]@{ Ok = $false; Raison = $r } }
    if (-not $Nom) { return & $ko 'Choisissez un nom.' }
    if ($Nom -cnotmatch '^[a-z0-9][a-z0-9_-]{0,39}$') {
        return & $ko 'Lettres minuscules sans accent, chiffres, « - » ou « _ » seulement (40 au plus), en commençant par une lettre ou un chiffre.'
    }
    if ($script:NomsProteges -contains $Nom) { return & $ko "« $Nom » est un nom réservé : choisissez-en un autre." }
    foreach ($i in @($Installations)) {
        if ($i.Nom -eq $Nom) { return & $ko "« $Nom » est déjà le nom de l'installation de $($i.Dossier)." }
    }
    if ($null -eq $Volumes) { return & $ko 'Impossible de lire la liste des volumes de Docker : Docker Desktop est-il démarré ?' }
    foreach ($v in @($Volumes)) {
        if ($v.StartsWith("$($Nom)_")) {
            return & $ko "Des données d'une installation « $Nom » existent encore dans Docker ($v) : choisissez un autre nom."
        }
    }
    return [pscustomobject]@{ Ok = $true; Raison = '' }
}

function Test-EcouteLibreJed([int]$Port) {
    <# Vrai si aucun programme n'écoute déjà sur ce port de l'ordinateur. #>
    $ecoute = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
    try { $ecoute.Start(); return $true } catch { return $false } finally { try { $ecoute.Stop() } catch { } }
}

function Test-PortJed {
    param([int]$Port, $Installations = @(), [switch]$SansEcoute)
    if ($Port -lt 1024 -or $Port -gt 65535) { return [pscustomobject]@{ Ok = $false; Raison = 'Choisissez un port entre 1024 et 65535.' } }
    foreach ($i in @($Installations)) {
        if ($i.Valide -and $i.Port -eq $Port) {
            return [pscustomobject]@{ Ok = $false; Raison = "Le port $Port est déjà celui de l'installation « $($i.Nom) »." }
        }
    }
    if (-not $SansEcoute -and -not (Test-EcouteLibreJed $Port)) {
        return [pscustomobject]@{ Ok = $false; Raison = "Le port $Port est déjà utilisé par un autre programme." }
    }
    return [pscustomobject]@{ Ok = $true; Raison = '' }
}

function Get-PortLibreJed {
    param($Installations = @(), [int]$Debut = 8000)
    for ($p = $Debut; $p -lt $Debut + 200; $p++) {
        if ((Test-PortJed $p $Installations).Ok) { return $p }
    }
    return $null
}

function Get-EmplacementParDefautJed {
    <# Dossier parent commun des installations existantes s'il y en a un, sinon C:\J-ed ; puis « nom-version ». #>
    param($Installations = @(), [string]$Nom, [string]$Version)
    $parents = @(@($Installations) | Where-Object { $_.Valide } |
        ForEach-Object { Split-Path -Parent $_.Dossier } | Sort-Object -Unique)
    $parent = 'C:\J-ed'
    if ($parents.Count -eq 1) { $parent = $parents[0] }
    $feuille = $Nom
    if ($Version) { $feuille = "$Nom-$Version" }
    return Join-CheminJed $parent $feuille
}

# --- Archive et empreinte ------------------------------------------------------------------------------

function Find-FichierEmpreinteJed([string]$Archive) {
    <# Comme mettre-a-jour.ps1 : « archive.zip.sha256 », puis « archive.sha256 », à côté de l'archive. #>
    foreach ($c in @("$Archive.sha256", [System.IO.Path]::ChangeExtension($Archive, '.sha256'))) {
        if (Test-Path -LiteralPath $c -PathType Leaf) { return $c }
    }
    return $null
}

function Test-EmpreinteJed {
    param([string]$Archive, [string]$Empreinte)
    $res = [pscustomobject]@{ Ok = $false; Attendue = ''; Calculee = ''; Raison = '' }
    if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) { $res.Raison = "Archive introuvable : $Archive"; return $res }
    if (-not $Empreinte) { $Empreinte = Find-FichierEmpreinteJed $Archive }
    if (-not $Empreinte -or -not (Test-Path -LiteralPath $Empreinte -PathType Leaf)) {
        $res.Raison = "Fichier d'empreinte (.sha256) introuvable : sélectionnez-le."
        return $res
    }
    $texte = ([System.IO.File]::ReadAllText($Empreinte)).Trim()
    $res.Attendue = (($texte -split '\s+')[0]).ToLowerInvariant()
    $res.Calculee = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($res.Attendue -ne $res.Calculee) {
        $res.Raison = "L'empreinte ne correspond pas : archive incomplète, abîmée, ou empreinte d'une autre version."
        return $res
    }
    $res.Ok = $true
    return $res
}

function Get-EntreeArchiveJed($Zip, [string]$Nom) {
    $motif = '^([^/]+/)?' + [regex]::Escape($Nom) + '$'
    return $Zip.Entries | Where-Object { $_.FullName -match $motif } | Select-Object -First 1
}

function Get-VersionArchiveJed([string]$Archive) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $z = [System.IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $e = Get-EntreeArchiveJed $z 'VERSION'
        if (-not $e) { return $null }
        $lecteur = New-Object System.IO.StreamReader($e.Open())
        try { return $lecteur.ReadToEnd().Trim() } finally { $lecteur.Close() }
    } finally { $z.Dispose() }
}

function Export-ScriptArchiveJed {
    <# Copie un script de l'archive (octet pour octet) dans un dossier : c'est le script de la NOUVELLE
       version qui fait la mise à jour, comme le demande l'aide. #>
    param([string]$Archive, [string]$Nom = 'mettre-a-jour.ps1', [string]$Dossier)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Force -Path $Dossier | Out-Null
    $z = [System.IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $e = Get-EntreeArchiveJed $z $Nom
        if (-not $e) { return $null }
        $cible = Join-CheminJed $Dossier $Nom
        $entree = $e.Open()
        $sortie = [System.IO.File]::Create($cible)
        try { $entree.CopyTo($sortie) } finally { $sortie.Close(); $entree.Close() }
        return $cible
    } finally { $z.Dispose() }
}

# --- Lancer un script ----------------------------------------------------------------------------------

function New-ArgumentsMiseAJourJed {
    <# Arguments de powershell.exe pour mettre-a-jour.ps1. Jamais -Oui : l'utilisateur confirme lui-même. #>
    param([string]$Script, [string]$Archive, [string]$Actuel, [string]$DossierSauvegardes, [string]$Empreinte,
          [string[]]$Autres = @())
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Script, '-Archive', $Archive, '-Actuel', $Actuel)
    if ($DossierSauvegardes) { $a += @('-DossierSauvegardes', $DossierSauvegardes) }
    if ($Empreinte) { $a += @('-Empreinte', $Empreinte) }
    foreach ($x in $Autres) { if ($x -ne '-Oui') { $a += $x } }
    return ,$a
}

function New-ArgumentsVerificationJed {
    param([string]$Script, [string]$Dossier, [switch]$AvecTests, [switch]$AvecSources)
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Script, '-Dossier', $Dossier)
    if ($AvecTests) { $a += '-AvecTests' }
    if ($AvecSources) { $a += '-AvecSources' }
    return ,$a
}

function ConvertTo-ArgumentWindowsJed([string]$Argument) {
    <# Met un argument entre guillemets selon les règles de Windows (CommandLineToArgvW). #>
    if ($Argument -and $Argument -notmatch '[\s"]') { return $Argument }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"')
    $barres = 0
    foreach ($ch in $Argument.ToCharArray()) {
        if ($ch -eq '\') { $barres++; continue }
        if ($ch -eq '"') { [void]$sb.Append('\' * ($barres * 2 + 1)); [void]$sb.Append('"') }
        else { [void]$sb.Append('\' * $barres); [void]$sb.Append($ch) }
        $barres = 0
    }
    [void]$sb.Append('\' * ($barres * 2))
    [void]$sb.Append('"')
    return $sb.ToString()
}

function Join-ArgumentsJed([string[]]$Arguments) {
    return (@($Arguments | ForEach-Object { ConvertTo-ArgumentWindowsJed $_ }) -join ' ')
}

function Read-JournalJed([string]$Fichier) {
    <# Lignes du journal de mise à jour (format du contrat), lues sans gêner le script qui écrit. #>
    $entrees = New-Object System.Collections.Generic.List[object]
    if (-not $Fichier -or -not (Test-Path -LiteralPath $Fichier)) { return ,$entrees.ToArray() }
    $flux = [System.IO.File]::Open($Fichier, 'Open', 'Read', 'ReadWrite')
    try {
        $lecteur = New-Object System.IO.StreamReader($flux, [System.Text.Encoding]::UTF8)
        $texte = $lecteur.ReadToEnd()
    } finally { $flux.Close() }
    foreach ($ligne in ($texte -split "`r?`n")) {
        if ($ligne -match '^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ([A-Z]+) ?(.*)$') {
            $entrees.Add([pscustomobject]@{ Heure = $Matches[1]; Repere = $Matches[2]; Texte = $Matches[3] })
        } elseif ($ligne -match '^    \| ?(.*)$' -and $entrees.Count -gt 0) {
            $entrees[$entrees.Count - 1].Texte += "`n" + $Matches[1]
        }
    }
    return ,$entrees.ToArray()
}

function Get-EtatJournalJed([string]$Fichier) {
    $etat = [pscustomobject]@{ Etape = ''; QuestionEnAttente = $false; Question = ''; Fin = $false; Code = $null; Resume = '' }
    $derniereQuestion = -1; $derniereReponse = -1; $i = 0
    foreach ($e in (Read-JournalJed $Fichier)) {
        switch ($e.Repere) {
            'ETAPE' { $etat.Etape = $e.Texte }
            'QUESTION' { $derniereQuestion = $i; $etat.Question = $e.Texte }
            'REPONSE' { $derniereReponse = $i }
            'FIN' {
                $etat.Fin = $true
                if ($e.Texte -match '^code=(\d+) ?(.*)$') { $etat.Code = [int]$Matches[1]; $etat.Resume = $Matches[2] }
            }
        }
        $i++
    }
    $etat.QuestionEnAttente = ($derniereQuestion -gt $derniereReponse) -and -not $etat.Fin
    return $etat
}

function Invoke-ScriptJed {
    <# Lance un script dans un autre PowerShell, transmet chaque ligne affichée à -SurLigne, et répond à la
       question du journal (repère QUESTION) par ce que renvoie -SurQuestion : OUI si vrai, sinon refus.
       -SurAttente est appelé pendant l'attente (la fenêtre y garde la main). Renvoie le code de sortie, les
       lignes affichées et le chemin du journal. #>
    param([string]$Moteur = 'powershell.exe', [string[]]$Arguments, [scriptblock]$SurLigne,
          [scriptblock]$SurQuestion, [scriptblock]$SurAttente, [string]$Dossier, [string]$Entree, [scriptblock]$SurEtape)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Moteur
    if ($Dossier) { $psi.WorkingDirectory = $Dossier }
    $psi.Arguments = Join-ArgumentsJed $Arguments
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $p = [System.Diagnostics.Process]::Start($psi)
    if ($PSBoundParameters.ContainsKey('Entree')) {
        # Réponses connues d'avance (mot de passe, confirmation) : écrites puis entrée fermée. Jamais en argument.
        $p.StandardInput.Write($Entree)
        $p.StandardInput.Close()
    }
    $lignes = New-Object System.Collections.Generic.List[string]
    $journal = $null
    $repondu = $false
    $lectures = @{ 'sortie' = $p.StandardOutput.ReadLineAsync(); 'erreurs' = $p.StandardError.ReadLineAsync() }
    $flux = @{ 'sortie' = $p.StandardOutput; 'erreurs' = $p.StandardError }
    while ($lectures.Count -gt 0) {
        $actif = $false
        foreach ($nom in @($lectures.Keys)) {
            $t = $lectures[$nom]
            if (-not $t.IsCompleted) { continue }
            $actif = $true
            $ligne = $t.Result
            if ($null -eq $ligne) { $lectures.Remove($nom); continue }
            $lignes.Add($ligne)
            if (-not $journal -and $ligne -match '^Journal de (la mise .{1,3} jour|l.installation) : (.+)$') { $journal = $Matches[2].Trim() }
            if ($SurLigne) { & $SurLigne $ligne }
            $lectures[$nom] = $flux[$nom].ReadLineAsync()
        }
        if (-not $repondu -and $journal -and -not $PSBoundParameters.ContainsKey('Entree')) {
            $etat = Get-EtatJournalJed $journal
            if ($etat.QuestionEnAttente) {
                # 2.0.2-rc5 (R9) : la dernière ligne affichée par le script peut arriver après la question ; l'étape en
                # cours est donc prise dans le journal, écrit sans délai, avant d'afficher la question.
                if ($SurEtape -and $etat.Etape) { & $SurEtape $etat.Etape }
                $oui = $false
                if ($SurQuestion) { $oui = [bool](& $SurQuestion $etat.Question) }
                if ($oui) { $p.StandardInput.WriteLine('OUI') } else { $p.StandardInput.WriteLine('non') }
                $p.StandardInput.Close()
                $repondu = $true
            }
        }
        if (-not $actif) {
            if ($SurAttente) { & $SurAttente }
            Start-Sleep -Milliseconds 100
        }
    }
    $p.WaitForExit()
    $code = $p.ExitCode
    $p.Dispose()
    return [pscustomobject]@{ Code = $code; Lignes = $lignes.ToArray(); Journal = $journal; QuestionPosee = $repondu }
}

# --- Messages ------------------------------------------------------------------------------------------

function Test-ProxyEnvJed {
    <# 2.0.2 (N13) : le fichier .env contient-il déjà ce proxy (HTTP_PROXY et HTTPS_PROXY) ? Alors rien à demander
       ni à écrire. Ne renvoie qu'un booléen (le .env contient des secrets). #>
    param([string]$Fichier, [string]$Proxy)
    if (-not $Proxy -or -not (Test-Path -LiteralPath $Fichier)) { return $false }
    $v = Read-EnvJed $Fichier
    return ($v['HTTP_PROXY'] -eq $Proxy -and $v['HTTPS_PROXY'] -eq $Proxy)
}

function Get-DossierNouvelleVersionJed([string[]]$Lignes = @()) {
    <# 2.0.2 (N14) : dossier de la nouvelle version, d'après la sortie de mettre-a-jour.ps1. #>
    foreach ($l in $Lignes) { if ($l -match 'Nouvelle version dans : (.+)$') { return $Matches[1].Trim() } }
    return ''
}

function Get-ConseilDossierInstallationJed {
    <# 2.0.2 (N15) : après une installation qui n'a pas abouti, nommer le dossier à supprimer avant de recommencer
       (comme pour la mise à jour, R8). #>
    param([int]$Code, [string[]]$Lignes = @())
    if ($Code -eq 0) { return '' }
    foreach ($l in $Lignes) {
        if ($l -match '^Le dossier (.+?) a .{1,3}t.{1,3} cr.{1,3}. ; il peut') {
            return ("Avant de recommencer, supprimez ce dossier (par exemple dans l'Explorateur de fichiers) :`n$($Matches[1])`n" +
                "Il ne contient aucune de vos données. L'assistant ne le supprime pas lui-même.")
        }
    }
    return ''
}

function Get-ConseilDossierMiseAJourJed {
    <# 2.0.2-rc5 (R8) : après un échec, le dossier de la nouvelle version empêche de relancer la mise à jour.
       Dire lequel supprimer, et qu'il ne contient aucune donnée. L'assistant ne supprime rien lui-même ; il ne
       propose pas d'autre nom (décision du 23/11 : noms de dossiers cohérents). Pas de conseil pour le code 5 :
       le dossier sert alors aux instructions affichées. #>
    param([int]$Code, [string[]]$Lignes = @())
    if ($Code -notin @(1, 3, 4)) { return '' }
    $dossier = ''
    foreach ($l in $Lignes) {
        if ($l -match 'le dossier de destination existe déjà : (.+?)\. Supprimez') { $dossier = $Matches[1].Trim(); break }
        if ($l -match 'Nouvelle version dans : (.+)$') { $dossier = $Matches[1].Trim() }
    }
    if (-not $dossier) { return '' }
    return ("Avant de relancer la mise à jour, supprimez ce dossier (par exemple dans l'Explorateur de fichiers) :`n$dossier`n" +
        "Il ne contient que les fichiers de la nouvelle version, aucune de vos données (elles sont gardées par Docker). " +
        "L'assistant ne le supprime pas lui-même.")
}

function Get-MessageMiseAJourJed([int]$Code) {
    $m = @{
        0 = @('ok', 'Mise à jour réussie', 'La nouvelle version est en service.')
        1 = @('attention', 'Mise à jour arrêtée avant de commencer', "Rien n'a été modifié : votre installation fonctionne comme avant. Le message affiché et le journal disent pourquoi.")
        2 = @('attention', 'Mise à jour annulée', "Vous n'avez pas confirmé : l'ancienne version est toujours en service.")
        3 = @('attention', 'Nouvelle version impossible à préparer', "Le plus souvent, Docker ne joint pas Internet (ou un proxy le bloque). L'ancienne version est toujours en service.")
        4 = @('attention', "Retour à l'ancienne version", "La nouvelle version n'a pas démarré correctement : l'assistant est revenu tout seul à l'ancienne. Aucune donnée n'a été effacée.")
        5 = @('erreur', 'Intervention nécessaire', "La nouvelle version n'a pas démarré et le retour à l'ancienne a échoué. Aucune donnée n'a été effacée. Suivez les instructions affichées, ou utilisez « Ça ne marche pas ».")
    }
    if ($m.ContainsKey($Code)) {
        $v = $m[$Code]
        return [pscustomobject]@{ Code = $Code; Niveau = $v[0]; Titre = $v[1]; Texte = $v[2] }
    }
    return [pscustomobject]@{ Code = $Code; Niveau = 'erreur'; Titre = "Résultat inattendu (code $Code)"; Texte = 'Gardez le journal et utilisez « Ça ne marche pas ».' }
}

function Get-MessageVerificationJed([int]$Code) {
    if ($Code -eq 0) { return [pscustomobject]@{ Code = 0; Niveau = 'ok'; Titre = 'Tout va bien'; Texte = 'La vérification ne signale aucune erreur.' } }
    return [pscustomobject]@{ Code = $Code; Niveau = 'erreur'; Titre = 'Problème détecté'; Texte = 'Au moins un contrôle est en erreur : lisez le rapport.' }
}

$script:ErreursDocker = @(
    @('docker-absent', "(?i)docker.{0,40}(not recognized|n'est pas reconnu|introuvable)|command not found",
      "Docker Desktop n'est pas installé.", "Installez-le (voir « Avant de commencer »), puis relancez l'assistant."),
    @('docker-arrete', '(?i)error during connect|dockerDesktopLinuxEngine|Cannot connect to the Docker daemon|daemon is not running|The system cannot find the file specified',
      "Docker Desktop n'est pas démarré.", "Lancez Docker Desktop, attendez que la baleine soit immobile, puis recommencez."),
    @('wsl', '(?i)WSL ?2? (installation is incomplete|is not installed)|wsl --update|Virtual Machine Platform',
      "WSL n'est pas installé ou pas à jour.", "Suivez la partie « WSL » de « Avant de commencer »."),
    @('port', '(?i)port is already allocated|address already in use|Only one usage of each socket address',
      "Le port choisi est déjà utilisé par un autre programme.", "Arrêtez l'autre programme, ou choisissez un autre port pour cette installation."),
    @('disque', '(?i)no space left on device|not enough space|espace insuffisant',
      "Le disque est plein.", "Libérez de la place (20 Go conseillés), puis recommencez."),
    @('internet', '(?i)context deadline exceeded|TLS handshake timeout|dial tcp|proxyconnect|i/o timeout|Temporary failure in name resolution|no such host|failed to resolve source metadata',
      "Docker ne joint pas Internet.", "Vérifiez la connexion. Derrière un proxy, réglez-le dans Docker Desktop (Settings → Resources → Proxies).")
)

function Convert-ErreurDockerJed([string]$Texte) {
    <# Explication en français de l'erreur Docker reconnue dans le texte, ou $null. #>
    if (-not $Texte) { return $null }
    foreach ($e in $script:ErreursDocker) {
        if ($Texte -match $e[1]) {
            return [pscustomobject]@{ Cle = $e[0]; Explication = $e[2]; Solution = $e[3] }
        }
    }
    return $null
}

# --- Opérations courantes ------------------------------------------------------------------------------

function Get-CommandeActionJed([string]$Action) {
    <# Arguments de docker pour une opération courante. Arrêter = « stop » (décision du 23/11) ; jamais -v. #>
    switch ($Action) {
        'Demarrer' { return ,@('compose', 'up', '-d') }
        'Arreter' { return ,@('compose', 'stop') }
        'Sauvegarder' { return ,@('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'backup', '--verify') }
    }
    throw "Action inconnue : $Action"
}

function Get-AdresseJed($Installation) {
    return "http://localhost:$($Installation.Port)/"
}

function Get-DerniereSauvegardeJed {
    param($Installation, [datetime]$Maintenant = (Get-Date))
    $d = $Installation.DossierSauvegardes
    if (-not $d -or -not (Test-Path -LiteralPath $d -PathType Container)) { return $null }
    $f = Get-ChildItem -LiteralPath $d -Filter '*.tar' -File -ErrorAction SilentlyContinue |
        Sort-Object -Property LastWriteTime -Descending | Select-Object -First 1
    if (-not $f) { return $null }
    $jours = [int][Math]::Floor(($Maintenant - $f.LastWriteTime).TotalDays)
    if ($jours -lt 0) { $jours = 0 }
    return [pscustomobject]@{ Fichier = $f.FullName; Date = $f.LastWriteTime; Jours = $jours; Texte = (Format-AncienneteJed $jours) }
}

function Format-AncienneteJed([int]$Jours) {
    if ($Jours -le 0) { return "aujourd'hui" }
    if ($Jours -eq 1) { return 'hier' }
    return "il y a $Jours jours"
}

function Invoke-SauvegardeJed {
    <# Sauvegarde vérifiée de l'installation, copiée dans son dossier des sauvegardes s'il est réglé, avec
       contrôle de l'empreinte de la copie (comme mettre-a-jour.ps1). #>
    param($Installation, [scriptblock]$SurAttente, [scriptblock]$SurLigne)
    $res = [pscustomobject]@{ Ok = $false; Fichier = ''; Copie = ''; Message = '' }
    $r = Invoke-DockerJed $Installation.Dossier (Get-CommandeActionJed 'Sauvegarder') -SurAttente $SurAttente -SurLigne $SurLigne
    if ($r.Code -ne 0 -or $r.Texte -notmatch 'Termin.{1,3}e : (\S+\.tar)' -or $r.Texte -notmatch 'Int.{1,3}grit.{1,3} v.{1,3}rifi') {
        $res.Message = "La sauvegarde a échoué.`n$($r.Texte)"
        return $res
    }
    $chemin = ([regex]::Match($r.Texte, 'Termin.{1,3}e : (\S+\.tar)')).Groups[1].Value
    $res.Fichier = $chemin
    $d = $Installation.DossierSauvegardes
    if (-not $d) {
        $res.Ok = $true
        $res.Message = "Sauvegarde faite et vérifiée, gardée dans Docker ($chemin). Pour en avoir une copie sur l'ordinateur, réglez un dossier des sauvegardes."
        return $res
    }
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    $copie = Join-CheminJed $d (Split-Path -Leaf $chemin)
    if (-not (Test-Path -LiteralPath $copie)) {
        # J-ed copie déjà lui-même chaque sauvegarde dans ce dossier (« Copie externe ») : copie seulement si absente.
        $cp = Invoke-DockerJed $Installation.Dossier @('compose', 'cp', "web:$chemin", $copie) -SurAttente $SurAttente
        if ($cp.Code -ne 0 -or -not (Test-Path -LiteralPath $copie)) {
            $res.Message = "Sauvegarde faite, mais sa copie sur l'ordinateur a échoué.`n$($cp.Texte)"
            return $res
        }
    }
    $sha = Invoke-DockerJed $Installation.Dossier @('compose', 'exec', '-T', 'web', 'sha256sum', $chemin) -SurAttente $SurAttente
    $local = (Get-FileHash -LiteralPath $copie -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sha.Code -ne 0 -or (($sha.Texte -split '\s+')[0]).ToLowerInvariant() -ne $local) {
        $res.Message = "La copie de la sauvegarde ($copie) ne correspond pas à l'original."
        return $res
    }
    $res.Ok = $true
    $res.Copie = $copie
    $res.Message = "Vérifiée, et copiée sur l'ordinateur : $copie"
    return $res
}

function Get-ScriptVerificationJed {
    <# verifier-j-ed.ps1 de l'installation (celui de sa version), sinon celui du dossier de l'assistant. #>
    param($Installation, [string]$DossierAssistant)
    $propre = Join-CheminJed $Installation.Dossier 'verifier-j-ed.ps1'
    if (Test-Path -LiteralPath $propre) { return $propre }
    return Join-CheminJed $DossierAssistant 'verifier-j-ed.ps1'
}

function Get-RapportVerificationJed([string[]]$Lignes) {
    <# Chemin du rapport écrit par verifier-j-ed.ps1 (ligne « Rapport enregistré : … » du contrat). #>
    foreach ($l in $Lignes) { if ($l -match '^Rapport enregistr.{1,3} : (.+)$') { return $Matches[1].Trim() } }
    return $null
}

# --- Raccourcis ------------------------------------------------------------------------------------------

function Get-NomRaccourciJed($Installation) {
    $nom = "J-ed - $($Installation.Nom)"
    return ($nom -replace '[\\/:*?"<>|]', '-')
}

function Send-AvisRaccourcisJed($Fichiers) {
    <# 2.0.2-rc6 (N8) : prévient l'Explorateur de Windows de l'ajout des raccourcis, pour qu'ils apparaissent tout
       de suite sur le Bureau (sinon, il fallait appuyer sur F5). Sans effet hors de Windows. #>
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { return }
    try {
        Add-Type -Namespace JedAssistant -Name Explorateur -MemberDefinition '[DllImport("shell32.dll", CharSet = CharSet.Unicode)] public static extern void SHChangeNotify(int eventId, uint flags, string item1, IntPtr item2);' -ErrorAction Stop
        foreach ($f in $Fichiers) {
            [JedAssistant.Explorateur]::SHChangeNotify(0x00000002, 0x0005, $f, [IntPtr]::Zero)              # SHCNE_CREATE, SHCNF_PATHW
            [JedAssistant.Explorateur]::SHChangeNotify(0x00001000, 0x0005, (Split-Path -Parent $f), [IntPtr]::Zero)  # SHCNE_UPDATEDIR
        }
    } catch { }
}

function New-RaccourcisJed {
    <# Raccourci « J-ed - <nom> » (ouvre J-ed dans le navigateur) et « Assistant J-ed » (ouvre l'assistant), sur
       le Bureau et dans le menu Démarrer. Remplace seulement des raccourcis de ces mêmes noms. Renvoie les
       fichiers écrits. #>
    param($Installation, [string]$DossierAssistant, [string[]]$Dossiers)
    if (-not $Dossiers) {
        $Dossiers = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
    }
    $ecrits = New-Object System.Collections.Generic.List[string]
    foreach ($d in $Dossiers) {
        if (-not $d) { continue }
        New-Item -ItemType Directory -Force -Path $d | Out-Null
        $url = Join-CheminJed $d ((Get-NomRaccourciJed $Installation) + '.url')
        $texte = "[InternetShortcut]`r`nURL=$(Get-AdresseJed $Installation)`r`n"
        [System.IO.File]::WriteAllText($url, $texte, [System.Text.Encoding]::ASCII)
        $ecrits.Add($url)
        $cmd = Join-CheminJed $DossierAssistant 'J-ed.cmd'
        if ((Test-Path -LiteralPath $cmd) -and ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT)) {
            $lnk = Join-CheminJed $d 'Assistant J-ed.lnk'
            $shell = New-Object -ComObject WScript.Shell
            $r = $shell.CreateShortcut($lnk)
            $r.TargetPath = $cmd
            $r.WorkingDirectory = $DossierAssistant
            $r.WindowStyle = 7
            $r.Description = 'Assistant J-ed : installer, mettre à jour, vérifier et sauvegarder J-ed'
            # 2.0.2-rc6 (N11) : icône de J-ed (le fichier .cmd n'en a pas de propre).
            $icone = Join-CheminJed $DossierAssistant (Join-CheminJed 'assistant' 'j-ed.ico')
            if (Test-Path -LiteralPath $icone) { $r.IconLocation = "$icone,0" }
            $r.Save()
            $ecrits.Add($lnk)
        }
    }
    Send-AvisRaccourcisJed $ecrits
    return ,$ecrits.ToArray()
}

# --- Compte rendu « Ça ne marche pas » --------------------------------------------------------------------

function Protect-TexteJed {
    <# Masque les secrets d'un texte : valeurs sensibles du .env, mots de passe et clés écrits « nom=valeur »,
       identifiants dans les adresses, adresses électroniques. #>
    param([string]$Texte, [string[]]$Secrets = @())
    if (-not $Texte) { return $Texte }
    foreach ($s in $Secrets) {
        if ($s -and $s.Length -ge 4) { $Texte = $Texte.Replace($s, '***') }
    }
    $Texte = [regex]::Replace($Texte, '(?i)\b([A-Z0-9_]*(PASSWORD|PASSWD|SECRET|TOKEN|KEY|MOT_DE_PASSE|CLE)[A-Z0-9_]*)\s*([=:])\s*("?)[^\s"]+', '$1$3$4***')
    $Texte = [regex]::Replace($Texte, '(?i)(://)[^/\s:@]+:[^/\s@]+@', '$1***:***@')
    $Texte = [regex]::Replace($Texte, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '***@***')
    return $Texte
}

function Get-SecretsEnvJed($Installation) {
    <# Valeurs à masquer : toutes celles du .env dont le nom évoque un secret. Jamais renvoyées ailleurs. #>
    $liste = New-Object System.Collections.Generic.List[string]
    if (-not $Installation -or -not $Installation.Valide) { return ,$liste.ToArray() }
    $valeurs = Read-EnvJed (Join-CheminJed $Installation.Dossier '.env')
    foreach ($k in $valeurs.Keys) {
        if ($k -match '(?i)PASSWORD|SECRET|TOKEN|KEY|DATABASE_URL|_URL$' -and $valeurs[$k]) { $liste.Add("$($valeurs[$k])") }
    }
    return ,$liste.ToArray()
}

function New-CompteRenduJed {
    <# Compte rendu pour une personne qui aide : système, prérequis, installation, état des services, dernières
       lignes des journaux, dernier journal de mise à jour. Jamais le .env ; secrets masqués ; contrôle final.
       Écrit un .zip dans -Destination et renvoie son chemin. #>
    param($Installation, [string]$Destination, [string]$VersionAssistant = '?', [scriptblock]$SurAttente)
    $l = New-Object System.Collections.Generic.List[string]
    $l.Add("Compte rendu de l'assistant J-ed $VersionAssistant — $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
    $l.Add('Sans mot de passe, sans clé, sans adresse électronique, sans le fichier .env.')
    $l.Add('')
    $l.Add('== Ordinateur')
    $faits = Get-FaitsSystemeJed -Dossier $(if ($Installation) { $Installation.Dossier } else { '' })
    foreach ($p in $faits.PSObject.Properties) { $l.Add("$($p.Name) : $($p.Value)") }
    $l.Add("Système : $([Environment]::OSVersion.VersionString)")
    $l.Add('')
    $l.Add('== Prérequis')
    foreach ($c in (Test-PrerequisJed $faits)) { $l.Add("[$($c.Niveau)] $($c.Libelle) : $($c.Detail)") }
    $v = Invoke-DockerJed '' @('version', '--format', '{{.Server.Version}}') -SurAttente $SurAttente
    $l.Add("Docker (moteur) : $($v.Texte)")
    $journal = $null
    if ($Installation) {
        $l.Add('')
        $l.Add('== Installation')
        foreach ($k in @('Nom', 'Version', 'Port', 'Etat', 'Dossier', 'DossierSauvegardes', 'Essai', 'Protegee', 'Valide', 'Probleme')) {
            $l.Add("$k : $($Installation.$k)")
        }
        if ($Installation.Valide) {
            $ps = Invoke-DockerJed $Installation.Dossier @('compose', 'ps', '-a') -SurAttente $SurAttente
            $l.Add(''); $l.Add('== Services (docker compose ps -a)'); $l.Add($ps.Texte)
            $logs = Invoke-DockerJed $Installation.Dossier @('compose', 'logs', '--tail', '150', '--no-color') -SurAttente $SurAttente
            $l.Add(''); $l.Add('== Dernières lignes des journaux (docker compose logs --tail 150)'); $l.Add($logs.Texte)
        }
        $d = $Installation.DossierSauvegardes
        if ($d -and (Test-Path -LiteralPath $d)) {
            $journal = Get-ChildItem -LiteralPath $d -Filter 'mise-a-jour-*.log' -File -ErrorAction SilentlyContinue |
                Sort-Object -Property LastWriteTime -Descending | Select-Object -First 1
        }
    }
    $secrets = Get-SecretsEnvJed $Installation
    $texte = Protect-TexteJed (($l.ToArray()) -join "`r`n") $secrets
    $journalTexte = $null
    if ($journal) { $journalTexte = Protect-TexteJed ([System.IO.File]::ReadAllText($journal.FullName)) $secrets }
    # Contrôle final : aucune valeur secrète du .env ne doit rester.
    foreach ($s in $secrets) {
        if ($s.Length -ge 4 -and ($texte.Contains($s) -or ($journalTexte -and $journalTexte.Contains($s)))) {
            throw 'Compte rendu refusé : une valeur secrète y figure encore.'
        }
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $nom = "compte-rendu-j-ed-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $temp = Join-CheminJed ([System.IO.Path]::GetTempPath()) $nom
    New-Item -ItemType Directory -Force -Path $temp | Out-Null
    try {
        [System.IO.File]::WriteAllText((Join-CheminJed $temp 'compte-rendu.txt'), $texte, $script:Utf8SansBom)
        if ($journalTexte) { [System.IO.File]::WriteAllText((Join-CheminJed $temp $journal.Name), $journalTexte, $script:Utf8SansBom) }
        $zip = Join-CheminJed $Destination "$nom.zip"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($temp, $zip)
    } finally {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
    return $zip
}

# --- Dernière version publiée sur GitHub --------------------------------------------------------------

$script:Depot = 'adupuisauteur/japon-explorateur'

function ConvertTo-VersionJed([string]$Texte) {
    <# « 2.0.1 », « v2.0.1 », « 2.0.2-rc1 » → [version] 2.0.1 / 2.0.2 ; $null si illisible. #>
    if ("$Texte" -match '^v?(\d+\.\d+(\.\d+)?)') { return [version]$Matches[1] }
    return $null
}

function Initialize-ReseauJed {
    # Windows PowerShell 5.1 : GitHub exige TLS 1.2. Le proxy du système (PAC compris) est utilisé par défaut.
    try {
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
    } catch { }
}

function Get-DerniereVersionGitHubJed {
    <# Dernière version PUBLIÉE (ni brouillon ni version de test) et ses deux fichiers : archive et .sha256. #>
    param([string]$Api = 'https://api.github.com', [string]$Depot = $script:Depot)
    Initialize-ReseauJed
    $res = [pscustomobject]@{ Ok = $false; Version = ''; Date = ''; Archive = $null; Empreinte = $null; Raison = '' }
    try {
        $r = Invoke-WebRequest -Uri "$Api/repos/$Depot/releases/latest" -UseBasicParsing -TimeoutSec 30 `
            -Headers @{ 'User-Agent' = 'assistant-j-ed'; 'Accept' = 'application/vnd.github+json' }
        # Texte lu en UTF-8 quel que soit l'en-tête (Windows PowerShell 5.1 suppose sinon ISO-8859-1).
        $info = [System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
    } catch {
        $res.Raison = "GitHub ne répond pas (Internet, proxy ?) : $($_.Exception.Message)"
        return $res
    }
    $res.Version = ("$($info.tag_name)" -replace '^v', '')
    $res.Date = "$($info.published_at)"
    $fichiers = @($info.assets | ForEach-Object { $_ })
    $archive = $fichiers | Where-Object { $_.name -match '^japon-explorateur-.+\.zip$' } | Select-Object -First 1
    if ($archive) {
        $empreinte = $fichiers | Where-Object { $_.name -eq "$($archive.name).sha256" -or $_.name -eq ([System.IO.Path]::ChangeExtension($archive.name, '.sha256')) } | Select-Object -First 1
    } else { $empreinte = $null }
    if (-not $archive -or -not $empreinte) {
        $res.Raison = "La page de la version $($res.Version) sur GitHub n'a pas l'archive et son fichier .sha256 : choisissez les fichiers à la main."
        return $res
    }
    $res.Archive = [pscustomobject]@{ Nom = $archive.name; Url = $archive.browser_download_url; Taille = [long]$archive.size }
    $res.Empreinte = [pscustomobject]@{ Nom = $empreinte.name; Url = $empreinte.browser_download_url }
    $res.Ok = $true
    return $res
}

function Compare-VersionJed([string]$A, [string]$B) {
    <# -1 si A est plus ancienne que B, 0 si égales, 1 si plus récente ; $null si l'une est illisible. #>
    $va = ConvertTo-VersionJed $A; $vb = ConvertTo-VersionJed $B
    if (-not $va -or -not $vb) { return $null }
    return $va.CompareTo($vb)
}

function Get-DossierTelechargementsJed {
    $profil = [Environment]::GetFolderPath('UserProfile')
    return Join-CheminJed (Join-CheminJed $profil 'Downloads') 'J-ed'
}

function Save-DerniereVersionJed {
    <# Télécharge l'archive et son .sha256 dans le dossier donné (par défaut Téléchargements\J-ed), puis contrôle
       l'empreinte. Un fichier du même nom dans ce dossier est remplacé par le nouveau téléchargement. #>
    param($Info, [string]$Dossier = (Get-DossierTelechargementsJed))
    Initialize-ReseauJed
    New-Item -ItemType Directory -Force -Path $Dossier | Out-Null
    $archive = Join-CheminJed $Dossier $Info.Archive.Nom
    $empreinte = Join-CheminJed $Dossier $Info.Empreinte.Nom
    $ancienne = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'   # Windows PowerShell 5.1 : la barre de progression ralentit tout
    try {
        Invoke-WebRequest -Uri $Info.Empreinte.Url -OutFile $empreinte -UseBasicParsing -TimeoutSec 60 -Headers @{ 'User-Agent' = 'assistant-j-ed' }
        Invoke-WebRequest -Uri $Info.Archive.Url -OutFile $archive -UseBasicParsing -TimeoutSec 600 -Headers @{ 'User-Agent' = 'assistant-j-ed' }
    } catch {
        return [pscustomobject]@{ Ok = $false; Archive = ''; Empreinte = ''; Raison = "Téléchargement impossible : $($_.Exception.Message)" }
    } finally {
        $ProgressPreference = $ancienne
    }
    $controle = Test-EmpreinteJed -Archive $archive -Empreinte $empreinte
    return [pscustomobject]@{ Ok = $controle.Ok; Archive = $archive; Empreinte = $empreinte; Raison = $controle.Raison }
}

# --- Proxy (2.0.2) --------------------------------------------------------------------------------------

$script:ExceptionsProxy = 'localhost,127.0.0.1,db,redis,argos,ollama,web'

function Get-ProxySystemeJed {
    <# Adresse réelle du proxy que Windows utilise pour cette adresse (un fichier PAC est appliqué), ou $null. #>
    param([string]$Url = 'https://registry-1.docker.io/')
    try {
        $uri = New-Object System.Uri($Url)
        $p = [System.Net.WebRequest]::GetSystemWebProxy().GetProxy($uri)
        if (-not $p -or $p.AbsoluteUri -eq $uri.AbsoluteUri) { return $null }
        return "$($p.Scheme)://$($p.Authority)"
    } catch { return $null }
}

function Test-AdresseProxyJed([string]$Proxy) {
    if (-not $Proxy) { return [pscustomobject]@{ Ok = $false; Raison = 'Aucune adresse de proxy.' } }
    if ($Proxy -notmatch '^https?://[^\s/]+$') {
        return [pscustomobject]@{ Ok = $false; Raison = 'Adresse attendue sous la forme http://nom-ou-adresse:port' }
    }
    if ($Proxy -match '://[^/]*@') {
        return [pscustomobject]@{ Ok = $false; Raison = "Proxy avec identifiant et mot de passe : à régler à la main (l'assistant n'écrit jamais de mot de passe)." }
    }
    return [pscustomobject]@{ Ok = $true; Raison = '' }
}

function Set-ProxyEnvJed {
    <# Écrit HTTP_PROXY, HTTPS_PROXY et NO_PROXY dans le .env (les anciennes lignes de ces trois réglages sont
       remplacées, tout le reste est gardé tel quel, encodage compris). #>
    param([string]$Fichier, [string]$Proxy)
    $t = Test-AdresseProxyJed $Proxy
    if (-not $t.Ok) { throw $t.Raison }
    $octets = [System.IO.File]::ReadAllBytes($Fichier)
    $bom = ($octets.Length -ge 3 -and $octets[0] -eq 0xEF -and $octets[1] -eq 0xBB -and $octets[2] -eq 0xBF)
    $texte = [System.Text.Encoding]::UTF8.GetString($octets)
    if ($bom) { $texte = $texte.Substring(1) }
    $fin = "`n"
    if ($texte -match "`r`n") { $fin = "`r`n" }
    $lignes = New-Object System.Collections.Generic.List[string]
    foreach ($l in ($texte -split "`r?`n")) {
        if ($l -match '^\s*(HTTP_PROXY|HTTPS_PROXY|NO_PROXY)\s*=' -or $l -match '^# Proxy \(assistant J-ed\)') { continue }
        $lignes.Add($l)
    }
    while ($lignes.Count -gt 0 -and $lignes[$lignes.Count - 1] -eq '') { $lignes.RemoveAt($lignes.Count - 1) }
    $lignes.Add('')
    $lignes.Add('# Proxy (assistant J-ed) : utilisé pour construire J-ed et par les conteneurs ; services internes exclus.')
    $lignes.Add("HTTP_PROXY=$Proxy")
    $lignes.Add("HTTPS_PROXY=$Proxy")
    $lignes.Add("NO_PROXY=$($script:ExceptionsProxy)")
    $nouveau = ($lignes -join $fin) + $fin
    # Copie de l'ancien .env à côté de lui, avant toute modification (jamais rien perdu).
    Copy-Item -LiteralPath $Fichier -Destination "$Fichier.avant-proxy-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $encodage = New-Object System.Text.UTF8Encoding($bom)
    [System.IO.File]::WriteAllText($Fichier, $nouveau, $encodage)
}

function Get-CommandeAccesRegistreJed {
    <# Docker joint-il Internet ? Télécharge l'image de base de J-ed (nécessaire à la construction, de toute façon). #>
    return ,@('pull', 'python:3.12-slim-bookworm')
}

function Get-ConseilProxyDockerJed([string]$Proxy) {
    $t = "Docker Desktop doit passer par le proxy :`n" +
        "1. ouvrez Docker Desktop, puis Settings (roue dentée) → Resources → Proxies ;`n" +
        "2. choisissez « System proxy » pour Docker Desktop et pour les conteneurs ;`n"
    if ($Proxy) { $t += "   si cela ne suffit pas : « Manual configuration », et l'adresse $Proxy pour HTTP et HTTPS ;`n" }
    $t += "3. cliquez sur « Apply & restart », attendez la baleine immobile, puis « Vérifier à nouveau »."
    return $t
}

# --- Nouvelle installation (installer-j-ed.ps1) --------------------------------------------------------

function New-ArgumentsInstallationJed {
    param([string]$Script, [string]$Archive, [string]$Empreinte, [string]$Destination, [string]$Nom, [int]$Port,
          [string]$DossierSauvegardes, [string]$Proxy, [switch]$SansArgos, [string[]]$Autres = @())
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Script, '-Archive', $Archive, '-Destination', $Destination,
           '-Nom', $Nom, '-Port', "$Port")
    if ($Empreinte) { $a += @('-Empreinte', $Empreinte) }
    if ($DossierSauvegardes) { $a += @('-DossierSauvegardes', $DossierSauvegardes) }
    if ($Proxy) { $a += @('-Proxy', $Proxy) }
    if ($SansArgos) { $a += '-SansArgos' }
    $a += $Autres
    return ,$a
}

function Get-MessageInstallationJed([int]$Code, [switch]$PourRestauration) {
    $fin = "J-ed est installé et répond. Il reste à créer le compte administrateur dans le navigateur."
    # 2.0.2-rc5 (R16) : avant une restauration, les comptes viendront de la sauvegarde.
    if ($PourRestauration) { $fin = "J-ed est installé et répond. La sauvegarde va maintenant y être restaurée : les comptes viendront de la sauvegarde (aucun compte à créer)." }
    $m = @{
        0 = @('ok', 'Installation réussie', $fin)
        1 = @('attention', 'Installation arrêtée avant de commencer', "Rien n'a été créé. Le message affiché dit pourquoi (nom, port, archive, Docker).")
        3 = @('attention', 'Construction impossible', "Le plus souvent, Docker ne joint pas Internet (ou un proxy le bloque). Le dossier a été créé, rien n'a démarré : il peut être supprimé avant de recommencer.")
        5 = @('erreur', 'J-ed ne démarre pas', "L'installation est faite mais J-ed ne répond pas. Utilisez « Ça ne marche pas » pour préparer un compte rendu.")
    }
    if ($m.ContainsKey($Code)) {
        $v = $m[$Code]
        return [pscustomobject]@{ Code = $Code; Niveau = $v[0]; Titre = $v[1]; Texte = $v[2] }
    }
    return [pscustomobject]@{ Code = $Code; Niveau = 'erreur'; Titre = "Résultat inattendu (code $Code)"; Texte = 'Gardez le journal et utilisez « Ça ne marche pas ».' }
}

function Convert-LigneInstallationJed([string]$Ligne, [switch]$PourRestauration) {
    <# 2.0.2-rc5 (R16) : avant une restauration, la consigne « Créez maintenant le compte administrateur » du script
       d'installation ne vaut pas : elle est remplacée à l'affichage (le journal garde la ligne d'origine). #>
    if ($PourRestauration -and $Ligne -match 'Cr.{1,3}ez maintenant le compte administrateur') {
        return 'La sauvegarde va maintenant être restaurée dans cette installation (les comptes viendront de la sauvegarde).'
    }
    return $Ligne
}

function Get-AdressePremierDemarrageJed($Installation) {
    return "http://localhost:$($Installation.Port)/comptes/premier-demarrage/"
}

# --- Mot de passe oublié -------------------------------------------------------------------------------

function Get-ComptesJed {
    <# Comptes de l'installation (commande « mot_de_passe_oublie --liste », J-ed 2.0.2 ou plus récent). #>
    param($Installation, [scriptblock]$SurAttente)
    $r = Invoke-DockerJed $Installation.Dossier @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'mot_de_passe_oublie', '--liste') -SurAttente $SurAttente
    $res = [pscustomobject]@{ Ok = $false; Comptes = @(); Raison = '' }
    if ($r.Code -ne 0) {
        if ($r.Texte -match 'Unknown command') { $res.Raison = 'Cette installation est trop ancienne : « Mot de passe oublié » demande J-ed 2.0.2 ou plus récent.' }
        else { $res.Raison = "Liste des comptes impossible (J-ed est-il démarré ?).`n$($r.Texte)" }
        return $res
    }
    $debut = $r.Texte.IndexOf('['); $fin = $r.Texte.LastIndexOf(']')
    try { $res.Comptes = @(($r.Texte.Substring($debut, $fin - $debut + 1) | ConvertFrom-Json) | ForEach-Object { $_ }) }
    catch { $res.Raison = 'Réponse illisible.'; return $res }
    $res.Ok = $true
    return $res
}

function Set-MotDePasseJed {
    <# Nouveau mot de passe d'un compte, transmis par l'entrée standard (jamais en argument ni dans un fichier). #>
    param($Installation, [string]$Utilisateur, [string]$MotDePasse, [scriptblock]$SurAttente)
    if (-not $MotDePasse) { return [pscustomobject]@{ Ok = $false; Message = 'Aucun mot de passe saisi.' } }
    $moteur = (Get-Command docker -ErrorAction SilentlyContinue)
    if (-not $moteur) { return [pscustomobject]@{ Ok = $false; Message = "Docker Desktop n'est pas installé." } }
    $r = Invoke-ScriptJed -Moteur $moteur.Source -Dossier $Installation.Dossier -Entree "$MotDePasse`n" -SurAttente $SurAttente `
        -Arguments @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'mot_de_passe_oublie', '--utilisateur', $Utilisateur)
    $texte = Protect-TexteJed ((@($r.Lignes) -join "`n").Trim()) @($MotDePasse)
    return [pscustomobject]@{ Ok = ($r.Code -eq 0); Message = $texte }
}

# --- Restaurer une sauvegarde ----------------------------------------------------------------------------

function Invoke-RestaurationJed {
    <# Restaure une sauvegarde (.tar) dans une installation démarrée : copie dans le conteneur, puis
       « restore_backup --yes » (l'utilisateur a tapé RESTAURER dans l'assistant) ; J-ed fait toujours sa
       sauvegarde de sécurité avant (jamais --sans-securite) ; redémarrage ensuite (la base est mise à niveau au
       démarrage si la sauvegarde vient d'une version plus ancienne). #>
    param($Installation, [string]$Fichier, [scriptblock]$SurAttente, [scriptblock]$SurLigne)
    $res = [pscustomobject]@{ Ok = $false; Message = ''; Securite = '' }
    if (-not (Test-Path -LiteralPath $Fichier -PathType Leaf) -or $Fichier -notmatch '\.tar$') {
        $res.Message = "Fichier de sauvegarde introuvable ou incorrect (un fichier .tar est attendu) : $Fichier"
        return $res
    }
    $nom = 'restauration-' + ([System.IO.Path]::GetFileName($Fichier) -replace '[^A-Za-z0-9._-]', '_')
    $d = $Installation.Dossier
    $cp = Invoke-DockerJed $d @('compose', 'cp', $Fichier, "web:/data/$nom") -SurAttente $SurAttente -SurLigne $SurLigne
    if ($cp.Code -ne 0) { $res.Message = "Copie de la sauvegarde dans J-ed impossible (J-ed est-il démarré ?).`n$($cp.Texte)"; return $res }
    # 2.0.2-rc5 (R17) : lignes techniques de restore_backup traduites pour l'affichage (nom de variable propre,
    # pour ne pas être confondu avec le -SurLigne des fonctions appelées).
    $afficherRestauration = $SurLigne
    $filtre = $null
    if ($afficherRestauration) { $filtre = { param($l) & $afficherRestauration (Convert-LigneRestaurationJed $l) } }
    $r = Invoke-DockerJed $d @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'restore_backup', "/data/$nom", '--yes') -SurAttente $SurAttente -SurLigne $filtre
    if ($r.Texte -match 'Sauvegarde de s.{1,3}curit.{1,3} cr.{1,3}.{1,3}e : (\S+)') { $res.Securite = $Matches[1] }
    if ($r.Code -ne 0) {
        $res.Message = "La restauration a échoué.`n$($r.Texte)"
        if ($res.Securite) { $res.Message += "`nSauvegarde de sécurité faite juste avant : $($res.Securite)" }
        return $res
    }
    $redemarrage = Invoke-DockerJed $d @('compose', 'restart') -SurAttente $SurAttente -SurLigne $SurLigne
    if ($redemarrage.Code -ne 0) { $res.Message = "Sauvegarde restaurée, mais le redémarrage a échoué : utilisez « Démarrer ».`n$($redemarrage.Texte)"; return $res }
    $res.Ok = $true
    $res.Message = "Sauvegarde restaurée. J-ed redémarre (une minute environ)."
    if ($res.Securite) { $res.Message += "`nSauvegarde de sécurité faite juste avant : $($res.Securite)" }
    return $res
}

function Convert-LigneRestaurationJed([string]$Ligne) {
    <# 2.0.2-rc5 (R17) : la consigne technique de restore_backup (variables du fichier .env) devient une phrase
       simple : dans la même installation il n'y a rien à faire ; depuis une autre, seules les clés d'API des IA
       sont à saisir de nouveau, et il faut se reconnecter. #>
    if ($Ligne -match 'r.{1,3}introduire DJANGO_SECRET_KEY') {
        return ("Si la sauvegarde vient d'une autre installation : reconnectez-vous, et saisissez de nouveau les clés d'API " +
            "des services d'IA (elles restent illisibles ailleurs). Rien d'autre à faire.")
    }
    return $Ligne
}

# --- Vérifier la migration, réinitialiser l'essai --------------------------------------------------------

function New-ArgumentsMigrationJed([string]$Script, [string]$Dossier) {
    return ,@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Script, '-Dossiers', $Dossier)
}

function Get-ScriptInstallationJed($Installation, [string]$Nom, [string]$DossierAssistant) {
    <# Script de l'installation elle-même (celui de sa version) ; à défaut, celui du dossier de l'assistant. #>
    $propre = Join-CheminJed $Installation.Dossier $Nom
    if (Test-Path -LiteralPath $propre) { return $propre }
    return Join-CheminJed $DossierAssistant $Nom
}

function New-ArgumentsReinitialisationJed([string]$Script, [switch]$Complet) {
    <# Toujours -SansSauvegarde : l'assistant fait lui-même la sauvegarde avant, si l'utilisateur la demande. #>
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Script, '-SansSauvegarde')
    if ($Complet) { $a += '-Complet' }
    return ,$a
}

function Format-TitreEtapeJed([string]$Titre, [int]$Minutes) {
    <# 2.0.2-rc6 (N5) : titre de l'étape en cours, avec sa durée à partir d'une minute. #>
    if ($Minutes -lt 1) { return $Titre }
    return "$Titre — en cours depuis $Minutes min"
}

function Get-MessageReinitialisationJed {
    <# 2.0.2-rc5 (R21) : message de fin de la réinitialisation d'un essai. En mode complet, le script ne redémarre
       pas l'essai : le dire, avec ce qu'il faut faire ensuite. #>
    param([int]$Code, [string[]]$Lignes = @(), [switch]$Complet, [string]$Dossier)
    if ($Code -ne 0) {
        return [pscustomobject]@{ Niveau = 'erreur'; Titre = 'Réinitialisation arrêtée'; Texte = 'Le message affiché dit pourquoi.' }
    }
    if (@($Lignes | Where-Object { $_ -match '^Annul' }).Count -gt 0) {
        return [pscustomobject]@{ Niveau = 'attention'; Titre = 'Annulée'; Texte = 'Rien n''a été effacé.' }
    }
    if ($Complet) {
        return [pscustomobject]@{ Niveau = 'ok'; Titre = 'Essai réinitialisé (réinitialisation complète)'
            Texte = ("L'essai est arrêté et vide. Pour vous en servir de nouveau : choisissez-le dans la liste et cliquez sur " +
                "« Démarrer » (J-ed se reconstruit si besoin), puis créez le compte administrateur. Si vous n'en avez plus " +
                "besoin, vous pouvez supprimer son dossier : $Dossier") }
    }
    return [pscustomobject]@{ Niveau = 'ok'; Titre = 'Essai réinitialisé'; Texte = 'L''essai redémarre avec une base vide : créez le compte administrateur dans le navigateur.' }
}

Export-ModuleMember -Function *-*Jed, Join-CheminJed
