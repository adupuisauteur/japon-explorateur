<#
.SYNOPSIS
    Fabrique les archives d'essai de la mise à jour (2.0.3, lot 2) : une archive normale, une dont la construction
    échoue exprès, une dont le démarrage échoue exprès. Outil de recette, pas une fonction de J-ed.

.DESCRIPTION
    Sert à essayer, sur une installation d'ESSAI, les trois issues de la mise à jour sûre : réussite (code 0),
    construction impossible (code 3, l'ancienne version reste en service) et démarrage impossible (retour
    automatique à l'ancienne version, code 4). Fonctionne sous Windows et sous Linux (PowerShell 7 ou 5.1).

    Chaque archive a un seul dossier à la racine, contient le fichier VERSION demandé et son fichier .sha256 à
    côté, comme une archive publiée. Le fichier .env et le dossier .git ne sont jamais copiés. Les deux archives
    ratées contiennent ESSAI-LISEZMOI.txt (pour vérifier ensuite qu'elles ne sont pas restées en service).

    - construction impossible : une dernière ligne RUN du Dockerfile échoue (après pip : le cache sert) ;
    - démarrage impossible : le serveur web (gunicorn) s'arrête dès son lancement ; les autres services démarrent.

.PARAMETER Source
    Dossier du code de J-ed (celui qui contient docker-compose.yml). Par défaut : celui de ce script.

.PARAMETER Version
    Numéro écrit dans le fichier VERSION des archives (par exemple 2.0.3).

.PARAMETER Sortie
    Dossier où écrire les archives. Par défaut : J-ed/archives-essai dans le dossier personnel.

.EXAMPLE
    pwsh -NoProfile -File tests/outils/archives-essai.ps1 -Version 2.0.3
#>
[CmdletBinding()]
param(
    [string]$Source,
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Sortie
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (-not $Source) { $Source = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$Source = (Resolve-Path -LiteralPath $Source).Path
if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Source, 'docker-compose.yml')))) {
    throw "docker-compose.yml absent de $Source : ce n'est pas le dossier du code de J-ed."
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version attendue sous la forme 2.0.3 (reçu : $Version)." }
if (-not $Sortie) { $Sortie = [System.IO.Path]::Combine([Environment]::GetFolderPath('UserProfile'), 'J-ed', 'archives-essai') }
New-Item -ItemType Directory -Force -Path $Sortie | Out-Null
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$Lisezmoi = "Archive d'ESSAI de J-ed (recette de la mise à jour). À n'utiliser que sur une installation d'essai.`n"

function Get-Fichiers {
    # Chemins relatifs (séparateur /) des fichiers à mettre dans l'archive.
    $base = $Source.TrimEnd('\', '/')
    foreach ($f in (Get-ChildItem -LiteralPath $Source -Recurse -File -Force)) {
        $rel = $f.FullName.Substring($base.Length + 1).Replace('\', '/')
        if ($rel -eq '.env' -or $rel -like '.git/*' -or $rel -like '.venv/*' -or $rel -like '*/__pycache__/*' -or $rel -like '__pycache__/*') { continue }
        $rel
    }
}

function New-ArchiveEssai([string]$Nom, [hashtable]$Remplacements) {
    $chemin = [System.IO.Path]::Combine($Sortie, "$Nom.zip")
    if (Test-Path -LiteralPath $chemin) { Remove-Item -LiteralPath $chemin -Force }   # archive d'essai refaite
    $racine = "japon-explorateur-$Version/"
    $zip = [System.IO.Compression.ZipFile]::Open($chemin, 'Create')
    try {
        foreach ($rel in (Get-Fichiers)) {
            $e = $zip.CreateEntry($racine + $rel)
            # Sous Linux : droits du fichier gardés (j-ed.sh reste exécutable), comme dans une archive publiée.
            $item = Get-Item -LiteralPath ([System.IO.Path]::Combine($Source, $rel)) -Force
            if ($item.PSObject.Properties['UnixFileMode']) { $e.ExternalAttributes = ((([int]$item.UnixFileMode) -bor 0x8000) -shl 16) }
            $flux = $e.Open()
            try {
                if ($Remplacements.ContainsKey($rel)) { $o = $Utf8.GetBytes($Remplacements[$rel]); $flux.Write($o, 0, $o.Length) }
                else { $o = [System.IO.File]::ReadAllBytes([System.IO.Path]::Combine($Source, $rel)); $flux.Write($o, 0, $o.Length) }
            } finally { $flux.Close() }
        }
        foreach ($rel in $Remplacements.Keys) {
            if (-not (Test-Path -LiteralPath ([System.IO.Path]::Combine($Source, $rel)))) {
                $e = $zip.CreateEntry($racine + $rel)
                $flux = $e.Open()
                try { $o = $Utf8.GetBytes($Remplacements[$rel]); $flux.Write($o, 0, $o.Length) } finally { $flux.Close() }
            }
        }
    } finally { $zip.Dispose() }
    $hash = (Get-FileHash -LiteralPath $chemin -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText("$chemin.sha256", "$hash  $Nom.zip`n", $Utf8)
    Write-Host "$chemin"
    Write-Host "  SHA-256 : $hash"
}

$dockerfile = [System.IO.File]::ReadAllText([System.IO.Path]::Combine($Source, 'docker', 'Dockerfile')).Replace("`r`n", "`n")
$entrypoint = [System.IO.File]::ReadAllText([System.IO.Path]::Combine($Source, 'docker', 'entrypoint.sh')).Replace("`r`n", "`n")
if (-not $entrypoint.Contains("set -e`n")) { throw 'docker/entrypoint.sh inattendu (ligne « set -e » absente).' }

$normale = @{ 'VERSION' = "$Version`n" }
$construction = @{
    'VERSION' = "$Version`n"
    'ESSAI-LISEZMOI.txt' = $Lisezmoi
    'docker/Dockerfile' = $dockerfile.TrimEnd("`n") + "`n# Archive d'essai : construction impossible volontaire.`nRUN echo ""Essai J-ed : construction impossible volontaire."" && exit 1`n"
}
$demarrage = @{
    'VERSION' = "$Version`n"
    'ESSAI-LISEZMOI.txt' = $Lisezmoi
    'docker/entrypoint.sh' = $entrypoint.Insert($entrypoint.IndexOf("set -e`n") + 7,
        "`n# Archive d'essai : démarrage impossible volontaire du serveur web.`ncase ""`$1"" in gunicorn) echo ""Essai J-ed : démarrage impossible volontaire."" >&2; exit 1 ;; esac`n")
}

Write-Host "Archives d'essai de J-ed $Version (code de $Source) :"
New-ArchiveEssai "japon-explorateur-$Version-essai" $normale
New-ArchiveEssai "japon-explorateur-$Version-essai-construction-impossible" $construction
New-ArchiveEssai "japon-explorateur-$Version-essai-demarrage-impossible" $demarrage
