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
    param([string]$Dossier, [string[]]$Arguments)
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Code = 127; Texte = "docker n'est pas reconnu : Docker Desktop n'est pas installé." }
    }
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
        Protegee = $false; Valide = $false; Probleme = ''; Etat = 'inconnu'
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
            $inst.Etat = 'arrêtée'
        }
        $resultat.Add($inst)
    }
    return ,@($resultat | Sort-Object -Property Nom, Dossier)
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
    } elseif ($Faits.Build -lt 19045) {
        $c.Add((New-ControleJed 'windows' 'Version de Windows' 'attention' "Windows trop ancien pour Docker Desktop (version $($Faits.Build)) : faites les mises à jour de Windows." 'configuration'))
    } else {
        $c.Add((New-ControleJed 'windows' 'Windows' 'ok' 'Windows 64 bits à jour.' 'configuration'))
    }
    if ($null -eq $Faits.MemoireGo) {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'attention' 'Mémoire inconnue : 8 Go sont conseillés.' 'configuration'))
    } elseif ($Faits.MemoireGo -lt 4) {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'erreur' "$($Faits.MemoireGo) Go : trop peu pour Docker et J-ed (8 Go conseillés)." 'configuration'))
    } elseif ($Faits.MemoireGo -lt 7.5) {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'attention' "$($Faits.MemoireGo) Go : J-ed fonctionnera, lentement ; 8 Go sont conseillés." 'configuration'))
    } else {
        $c.Add((New-ControleJed 'memoire' 'Mémoire' 'ok' "$($Faits.MemoireGo) Go." 'configuration'))
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
        $c.Add((New-ControleJed 'disque' 'Place sur le disque' 'erreur' "$($Faits.DisqueLibreGo) Go libres : trop peu (20 Go conseillés)." 'disque'))
    } elseif ($Faits.DisqueLibreGo -lt 20) {
        $c.Add((New-ControleJed 'disque' 'Place sur le disque' 'attention' "$($Faits.DisqueLibreGo) Go libres : juste (20 Go conseillés)." 'disque'))
    } else {
        $c.Add((New-ControleJed 'disque' 'Place sur le disque' 'ok' "$($Faits.DisqueLibreGo) Go libres." 'disque'))
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
          [scriptblock]$SurQuestion, [scriptblock]$SurAttente)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Moteur
    $psi.Arguments = Join-ArgumentsJed $Arguments
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $p = [System.Diagnostics.Process]::Start($psi)
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
            if (-not $journal -and $ligne -match '^Journal de la mise .{1,3} jour : (.+)$') { $journal = $Matches[1].Trim() }
            if ($SurLigne) { & $SurLigne $ligne }
            $lectures[$nom] = $flux[$nom].ReadLineAsync()
        }
        if (-not $repondu -and $journal) {
            $etat = Get-EtatJournalJed $journal
            if ($etat.QuestionEnAttente) {
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
    param($Installation)
    $res = [pscustomobject]@{ Ok = $false; Fichier = ''; Copie = ''; Message = '' }
    $r = Invoke-DockerJed $Installation.Dossier (Get-CommandeActionJed 'Sauvegarder')
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
    $cp = Invoke-DockerJed $Installation.Dossier @('compose', 'cp', "web:$chemin", $copie)
    if ($cp.Code -ne 0 -or -not (Test-Path -LiteralPath $copie)) {
        $res.Message = "Sauvegarde faite, mais sa copie sur l'ordinateur a échoué.`n$($cp.Texte)"
        return $res
    }
    $sha = Invoke-DockerJed $Installation.Dossier @('compose', 'exec', '-T', 'web', 'sha256sum', $chemin)
    $local = (Get-FileHash -LiteralPath $copie -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sha.Code -ne 0 -or (($sha.Texte -split '\s+')[0]).ToLowerInvariant() -ne $local) {
        $res.Message = "La copie de la sauvegarde ($copie) ne correspond pas à l'original."
        return $res
    }
    $res.Ok = $true
    $res.Copie = $copie
    $res.Message = "Sauvegarde faite, vérifiée et copiée : $copie"
    return $res
}

Export-ModuleMember -Function *-*Jed, Join-CheminJed
