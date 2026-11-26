<#
.SYNOPSIS
    Assistant J-ed en mode texte (Linux, 2.0.3) : le « jumeau » de la fenêtre de l'assistant Windows.

.DESCRIPTION
    Décision D2 du 26 novembre 2026 : sous Linux, l'assistant est un menu dans le terminal, avec les mêmes
    fonctions, les mêmes noms et le même ordre que la fenêtre de Windows. Il s'appuie sur le MÊME module
    (assistant/AssistantJed.psm1) : une seule logique, deux présentations. Il ne fait aucune opération lui-même :
    il lance les scripts de J-ed (installer-j-ed.ps1, verifier-j-ed.ps1…) et lit ce qu'ils rendent, comme le décrit
    docs/contrat-scripts.md.

    Se lance par j-ed.sh (à la racine du dossier de J-ed), qui vérifie PowerShell 7 et refuse root.
    Les réponses peuvent venir d'un autre programme (entrée standard) : c'est ainsi qu'il est testé.

    Lot 1 de la 2.0.3 : accueil, liste des installations, Nouvelle installation, Démarrer, Arrêter, Ouvrir J-ed,
    Vérifier, Ajouter une installation, Voir les prérequis, Créer une sauvegarde, Dossier des sauvegardes.
    Lot 2 : Mettre à jour une installation (mise à jour sûre, par le mettre-a-jour.ps1 de la nouvelle version).
    Lot 3 : Créer les raccourcis (menu Applications), Ça ne marche pas, et le reste des Opérations de maintenance
    (Restaurer une sauvegarde, Mot de passe oublié, Vérifier la migration, Réinitialiser l'essai). L'aide Linux
    arrive au lot 4 (le menu le dit).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
$Racine = Split-Path -Parent $PSScriptRoot
Import-Module ([System.IO.Path]::Combine($PSScriptRoot, 'AssistantJed.psm1')) -Force
$script:Liste = Get-FichierListeJed
$script:Installations = @()

# --- Affichage et réponses ---------------------------------------------------------------------------------

$script:Couleurs = @{ ok = 'Green'; attention = 'Yellow'; erreur = 'Red' }
$script:Etiquettes = @{ ok = 'OK'; attention = 'Attention'; erreur = 'Problème' }

function Write-Titre([string]$Texte) {
    Write-Host ''
    Write-Host "== $Texte" -ForegroundColor Cyan
}

function Write-Niveau([string]$Niveau, [string]$Texte) {
    $c = $script:Couleurs[$Niveau]
    if (-not $c) { $c = 'White' }
    Write-Host $Texte -ForegroundColor $c
}

function Read-Ligne([string]$Question, [string]$ParDefaut = '') {
    <# Une réponse (la valeur proposée si l'on appuie seulement sur Entrée). Fin de l'entrée : on quitte. #>
    $invite = $Question
    if ($ParDefaut) { $invite += " [$ParDefaut]" }
    Write-Host -NoNewline "$invite : "
    $l = [Console]::In.ReadLine()
    if ($null -eq $l) {
        Write-Host ''
        Write-Host 'Fin de l''assistant.'
        exit 0
    }
    if ([Console]::IsInputRedirected) { Write-Host $l }   # trace lisible quand les réponses viennent d'un programme
    $l = $l.Trim()
    if (-not $l) { return $ParDefaut }
    return $l
}

function Read-OuiNon([string]$Question, [bool]$ParDefaut = $true) {
    $d = 'o/N'
    if ($ParDefaut) { $d = 'O/n' }
    while ($true) {
        $r = (Read-Ligne "$Question ($d)").ToLowerInvariant()
        if (-not $r) { return $ParDefaut }
        if ($r -in @('o', 'oui', 'y', 'yes')) { return $true }
        if ($r -in @('n', 'non', 'no')) { return $false }
        Write-Host 'Répondez o (oui) ou n (non).'
    }
}

function Wait-Entree {
    [void](Read-Ligne 'Appuyez sur Entrée pour revenir au menu')
}

function Write-Ligne([string]$Ligne) {
    # Lignes des scripts lancés : les étapes ressortent.
    if ($Ligne -match '^== ') { Write-Host $Ligne -ForegroundColor Cyan }
    elseif ($Ligne -match '^ARR.{1,3}T : ') { Write-Host $Ligne -ForegroundColor Red }
    else { Write-Host $Ligne }
}

function Show-Resultat([string]$Niveau, [string]$Titre, [string]$Texte) {
    Write-Host ''
    Write-Niveau $Niveau "$($script:Etiquettes[$Niveau]) — $Titre"
    if ($Texte) { foreach ($l in ($Texte -split "`n")) { Write-Host "  $l" } }
}

function Show-ErreurDocker([string]$Texte) {
    $e = Convert-ErreurDockerJed $Texte
    if ($e) {
        Write-Host "  $($e.Explication)" -ForegroundColor Yellow
        Write-Host "  $($e.Solution)"
    } elseif ($Texte) {
        foreach ($l in @($Texte -split "`n" | Select-Object -Last 8)) { Write-Host "  $l" }
    }
}

function Open-AdresseJed([string]$Cible) {
    <# Ouvre une adresse ou un dossier avec le programme habituel d'Ubuntu (xdg-open), et l'affiche toujours. #>
    Write-Host "  $Cible"
    if (Get-Command xdg-open -ErrorAction SilentlyContinue) {
        try { Start-Process -FilePath 'xdg-open' -ArgumentList $Cible -ErrorAction Stop | Out-Null } catch { }
    }
}

# --- Installations -----------------------------------------------------------------------------------------

function Update-Installations {
    # Find-InstallationsJed renvoie toujours un tableau (même vide ou d'un seul élément) : pas de @() autour.
    $script:Installations = Find-InstallationsJed -Fichier $script:Liste
}

function Show-Installations {
    Write-Host ''
    Write-Host 'Vos installations :' -ForegroundColor White
    if ($script:Installations.Count -eq 0) {
        Write-Host '  (aucune pour l''instant : choisissez « 2. Nouvelle installation »)'
        return
    }
    $n = 1
    foreach ($i in $script:Installations) {
        if ($i.Valide) {
            $sauv = Get-DerniereSauvegardeJed $i
            $texteSauv = 'aucune sauvegarde copiée'
            if ($sauv) { $texteSauv = "sauvegarde : $(Format-AncienneteJed $sauv.Jours)" }
            Write-Host ("  [{0}] {1,-24} {2,-10} port {3,-6} {4,-12} {5}" -f $n, $i.Nom, $i.Version, $i.Port, $i.Etat, $texteSauv)
            Write-Host ("      {0}" -f $i.Dossier) -ForegroundColor DarkGray
        } else {
            Write-Host ("  [{0}] {1} : {2}" -f $n, $i.Dossier, $i.Probleme) -ForegroundColor DarkGray
        }
        $n++
    }
}

function Select-Installation([string]$Pour, [switch]$Facultatif) {
    <# Installation choisie (valide), ou $null. Une seule installation : elle est prise d'office.
       -Facultatif (« Ça ne marche pas ») : aucune installation n'est pas une erreur. #>
    $valides = @($script:Installations | Where-Object { $_.Valide -and -not $_.Ancien })
    if ($valides.Count -eq 0) {
        if ($Facultatif) { return $null }
        Write-Host 'Aucune installation : choisissez d''abord « 2. Nouvelle installation » ou « 8. Ajouter une installation… ».' -ForegroundColor Yellow
        return $null
    }
    if ($valides.Count -eq 1) {
        Write-Host "Installation : $($valides[0].Nom) ($($valides[0].Dossier))"
        return $valides[0]
    }
    $r = Read-Ligne "Numéro de l'installation $Pour (0 : retour)"
    $num = 0
    if (-not [int]::TryParse($r, [ref]$num) -or $num -lt 1 -or $num -gt $script:Installations.Count) { return $null }
    $i = $script:Installations[$num - 1]
    if (-not $i.Valide) { Write-Host "Ce dossier n'est pas une installation utilisable : $($i.Probleme)" -ForegroundColor Yellow; return $null }
    return $i
}

# --- Prérequis ---------------------------------------------------------------------------------------------

function Get-Prerequis {
    return @(Test-PrerequisJed (Get-FaitsSystemeJed -Dossier ([Environment]::GetFolderPath('UserProfile'))))
}

function Show-ResumePrerequis($Controles) {
    $erreurs = @($Controles | Where-Object { $_.Niveau -eq 'erreur' }).Count
    $attentions = @($Controles | Where-Object { $_.Niveau -eq 'attention' }).Count
    if ($erreurs) { Write-Niveau 'erreur' "Prérequis : $erreurs point(s) à régler avant d'installer (choix 9)." }
    elseif ($attentions) { Write-Niveau 'attention' "Prérequis : prêt, $attentions point(s) à surveiller (choix 9)." }
    else { Write-Niveau 'ok' 'Prérequis : tout est prêt.' }
}

function Show-Prerequis {
    Write-Titre 'Prérequis'
    foreach ($c in (Get-Prerequis)) {
        Write-Niveau $c.Niveau ("  [{0}] {1} : {2}" -f $script:Etiquettes[$c.Niveau], $c.Libelle, $c.Detail)
        if ($c.Conseil -and $c.Niveau -ne 'ok') { Write-Host "      → $($c.Conseil)" }
    }
    Wait-Entree
}

# --- Opérations courantes ----------------------------------------------------------------------------------

function Invoke-Action([string]$Action, [string]$Libelle, [string]$Fin) {
    $i = Select-Installation "à $($Libelle.ToLowerInvariant())"
    if (-not $i) { return }
    Write-Titre "$Libelle « $($i.Nom) »"
    $r = Invoke-DockerJed $i.Dossier (Get-CommandeActionJed $Action) -SurLigne { param($l) Write-Ligne $l }
    if ($r.Code -eq 0) { Show-Resultat 'ok' "$Libelle : fait" $Fin }
    else { Show-Resultat 'erreur' "$Libelle : impossible" ''; Show-ErreurDocker $r.Texte }
    Wait-Entree
}

function Open-Installation {
    $i = Select-Installation 'à ouvrir'
    if (-not $i) { return }
    if ($i.Etat -ne 'en marche') {
        Write-Host "« $($i.Nom) » est arrêtée : choisissez d'abord « 3. Démarrer »." -ForegroundColor Yellow
        Wait-Entree
        return
    }
    Write-Host 'Ouverture dans le navigateur :'
    Open-AdresseJed (Get-AdresseJed $i)
    Wait-Entree
}

function Start-Verification {
    $i = Select-Installation 'à vérifier'
    if (-not $i) { return }
    $tests = Read-OuiNon 'Lancer aussi les tests automatiques (3 à 10 minutes) ?' $false
    $sources = Read-OuiNon 'Tester aussi chaque source en ligne (Internet) ?' $false
    Write-Titre "Vérifier « $($i.Nom) »"
    $script = Get-ScriptVerificationJed -Installation $i -DossierAssistant $Racine
    $arguments = New-ArgumentsVerificationJed -Script $script -Dossier $i.Dossier -AvecTests:$tests -AvecSources:$sources
    $x = Invoke-ScriptJed -Arguments $arguments -SurLigne { param($l) Write-Ligne $l }
    $m = Get-MessageVerificationJed $x.Code
    Show-Resultat $m.Niveau $m.Titre $m.Texte
    $rapport = Get-RapportVerificationJed $x.Lignes
    if ($rapport) { Write-Host "  Rapport : $rapport" }
    Wait-Entree
}

function Add-Installation {
    Write-Titre 'Ajouter une installation…'
    $d = Read-Ligne 'Dossier de l''installation (celui qui contient docker-compose.yml ; 0 : retour)'
    if (-not $d -or $d -eq '0') { return }
    if ($d.StartsWith('~')) { $d = [Environment]::GetFolderPath('UserProfile') + $d.Substring(1) }
    $i = Get-InstallationJed $d
    if (-not $i.Valide) {
        Show-Resultat 'attention' 'Dossier non ajouté' $i.Probleme
    } else {
        Add-InstallationListeJed -Fichier $script:Liste -Dossier $i.Dossier
        Show-Resultat 'ok' "Installation « $($i.Nom) » ajoutée" $i.Dossier
    }
    Wait-Entree
}

function Show-PasEncore([string]$Fonction, [string]$Lot) {
    Write-Host ''
    Write-Host "« $Fonction » arrive avec le $Lot de la version 2.0.3 pour Linux." -ForegroundColor Yellow
    Write-Host 'En attendant, sous Linux, ce qui est prévu se fait avec les scripts (voir l''aide).'
    Wait-Entree
}

function Show-Aide {
    $page = [System.IO.Path]::Combine($Racine, 'AVANT-DE-COMMENCER-LINUX.html')
    if (Test-Path -LiteralPath $page) { Write-Host 'Ouverture de l''aide :'; Open-AdresseJed $page; Wait-Entree }
    else { Show-PasEncore 'Aide : avant de commencer (Linux)' 'lot 4' }
}

# --- Opérations de maintenance -----------------------------------------------------------------------------

function Show-Maintenance {
    while ($true) {
        Write-Titre 'Opérations de maintenance'
        Write-Host '   1. Créer une sauvegarde        2. Dossier des sauvegardes'
        Write-Host '   3. Restaurer une sauvegarde    4. Mot de passe oublié'
        Write-Host '   5. Vérifier la migration       6. Réinitialiser l''essai'
        Write-Host '   0. Retour'
        switch (Read-Ligne 'Votre choix') {
            '1' { New-Sauvegarde }
            '2' {
                $i = Select-Installation 'dont ouvrir le dossier des sauvegardes'
                if ($i) {
                    if ($i.DossierSauvegardes) { Write-Host 'Dossier des sauvegardes :'; Open-AdresseJed $i.DossierSauvegardes }
                    else { Write-Host 'Pas de dossier des sauvegardes réglé : les sauvegardes restent dans Docker.' -ForegroundColor Yellow }
                    Wait-Entree
                }
            }
            '3' { Restore-Sauvegarde }
            '4' { Reset-MotDePasse }
            '5' { Start-VerificationMigration }
            '6' { Reset-Essai }
            '0' { return }
            default { Write-Host 'Choix inconnu.' }
        }
    }
}

function New-Sauvegarde {
    $i = Select-Installation 'à sauvegarder'
    if (-not $i) { return }
    Write-Titre "Créer une sauvegarde de « $($i.Nom) »"
    $r = Invoke-SauvegardeJed -Installation $i -SurLigne { param($l) Write-Ligne $l }
    if ($r.Ok) { Show-Resultat 'ok' 'Sauvegarde faite' $r.Message }
    else { Show-Resultat 'erreur' 'Sauvegarde impossible' $r.Message }
    Wait-Entree
}

function Read-Confirmation([string]$Texte, [string]$Mot) {
    <# Confirmation forte, comme la fenêtre : il faut taper le mot demandé (RESTAURER, REINITIALISER), en majuscules. #>
    Write-Host ''
    foreach ($l in ($Texte -split "`n")) { Write-Host $l -ForegroundColor Yellow }
    $r = Read-Ligne "Pour confirmer, tapez $Mot (autre réponse : annuler)"
    if ($r -ceq $Mot) { return $true }
    Write-Host 'Annulé : rien n''a changé.' -ForegroundColor Yellow
    return $false
}

function Read-Secret([string]$Question) {
    <# Saisie cachée (mot de passe). Réponses venant d'un programme (tests) : lues telles quelles, jamais réaffichées. #>
    if ([Console]::IsInputRedirected) {
        Write-Host -NoNewline "$Question : "
        $l = [Console]::In.ReadLine()
        Write-Host ''
        if ($null -eq $l) { Write-Host 'Fin de l''assistant.'; exit 0 }
        return $l
    }
    $s = Read-Host -Prompt $Question -AsSecureString
    return (ConvertFrom-SecureString -SecureString $s -AsPlainText)
}

function Restore-Sauvegarde {
    <# Comme la fenêtre : sauvegarde à restaurer, puis « dans une nouvelle installation » (conseillé) ou « dans
       l'installation choisie » (sa base est remplacée, sauvegarde de sécurité avant ; il faut taper RESTAURER). #>
    Write-Titre 'Restaurer une sauvegarde'
    $choisie = Select-Installation 'dont vient la sauvegarde (son dossier des sauvegardes est proposé)' -Facultatif
    $proposee = ''
    if ($choisie -and $choisie.DossierSauvegardes -and (Test-Path -LiteralPath $choisie.DossierSauvegardes)) {
        $derniere = Get-ChildItem -LiteralPath $choisie.DossierSauvegardes -Filter '*.tar' -File -ErrorAction SilentlyContinue |
            Sort-Object -Property LastWriteTime -Descending | Select-Object -First 1
        if ($derniere) { $proposee = $derniere.FullName }
    }
    $fichier = Read-Chemin 'Fichier de sauvegarde (.tar ; 0 : retour)' $proposee
    if (-not $fichier -or $fichier -eq '0') { return }
    if (-not (Test-Path -LiteralPath $fichier -PathType Leaf) -or $fichier -notmatch '\.tar$') {
        Show-Resultat 'attention' 'Fichier introuvable' "Un fichier de sauvegarde .tar est attendu : $fichier"
        Wait-Entree
        return
    }
    Write-Host ''
    Write-Host 'Où restaurer cette sauvegarde ?'
    Write-Host '   1. Dans une nouvelle installation (conseillé : rien d''existant n''est touché)'
    if ($choisie) { Write-Host "   2. Dans « $($choisie.Nom) » : sa base actuelle sera REMPLACÉE (une sauvegarde de sécurité est faite avant)" }
    Write-Host '   0. Retour'
    Write-Host ("  Bon à savoir : dans une nouvelle installation, les clés d'API des IA enregistrées dans la sauvegarde ne sont pas " +
        "lisibles (elles restent chiffrées avec la clé de l'installation d'origine) : il faudra les saisir à nouveau. " +
        "Une sauvegarde d'une version plus ancienne est mise à niveau au redémarrage.") -ForegroundColor DarkGray
    $choix = Read-Ligne 'Votre choix' '1'
    if ($choix -eq '1') {
        $base = 'jed'
        if ($choisie -and $choisie.Nom) { $base = "$($choisie.Nom)-copie" }
        $script:InstallationCreee = $null
        New-Installation -NomPropose $base -PourRestauration
        $cible = $script:InstallationCreee
        if (-not $cible) { return }
    } elseif ($choix -eq '2' -and $choisie) {
        $cible = $choisie
        if ($cible.Etat -ne 'en marche') {
            Write-Host "« $($cible.Nom) » est arrêtée : choisissez d'abord « 3. Démarrer »." -ForegroundColor Yellow
            Wait-Entree
            return
        }
        $texte = "La base actuelle de « $($cible.Nom) » va être remplacée par celle de la sauvegarde. J-ed fait d'abord une sauvegarde de sécurité de l'état actuel."
        if ($cible.Protegee) { $texte = "ATTENTION : $(Get-TexteProtegeeJed $cible)`n" + $texte + "`nConseil : restaurez plutôt dans une nouvelle installation." }
        if (-not (Read-Confirmation $texte 'RESTAURER')) { Wait-Entree; return }
    } else {
        return
    }
    Write-Titre "Restaurer dans « $($cible.Nom) » (une à quelques minutes)"
    $x = Invoke-RestaurationJed $cible $fichier -SurLigne { param($l) Write-Ligne $l }
    if ($x.Ok) { Show-Resultat 'ok' 'Sauvegarde restaurée' $x.Message }
    else { Show-Resultat 'erreur' 'Restauration impossible' $x.Message }
    Wait-Entree
}

function Reset-MotDePasse {
    <# Comme la fenêtre : compte choisi dans la liste, nouveau mot de passe saisi deux fois (caché), transmis à J-ed
       par l'entrée standard ; il n'est écrit nulle part. #>
    $i = Select-Installation 'dont un compte a perdu son mot de passe'
    if (-not $i) { return }
    if ($i.Etat -ne 'en marche') {
        Write-Host "« $($i.Nom) » est arrêtée : choisissez d'abord « 3. Démarrer »." -ForegroundColor Yellow
        Wait-Entree
        return
    }
    Write-Titre "Mot de passe oublié — « $($i.Nom) »"
    $c = Get-ComptesJed $i
    if (-not $c.Ok) { Show-Resultat 'erreur' 'Comptes illisibles' $c.Raison; Wait-Entree; return }
    if ($c.Comptes.Count -eq 0) {
        Show-Resultat 'attention' 'Aucun compte' "Créez le compte administrateur : $(Get-AdressePremierDemarrageJed $i)"
        Wait-Entree
        return
    }
    $n = 1
    foreach ($compte in $c.Comptes) {
        $libelle = "$($compte.identifiant)"
        if ($compte.nom) { $libelle += " — $($compte.nom)" }
        Write-Host ("   {0}. {1} ({2})" -f $n, $libelle, $compte.role)
        $n++
    }
    $num = 0
    $r = Read-Ligne 'Numéro du compte (0 : retour)' '1'
    if (-not [int]::TryParse($r, [ref]$num) -or $num -lt 1 -or $num -gt $c.Comptes.Count) { return }
    $identifiant = $c.Comptes[$num - 1].identifiant
    Write-Host 'Nouveau mot de passe : 10 caractères au moins, pas trop simple. Il ne s''affiche pas pendant la saisie et n''est écrit nulle part.'
    $mot = Read-Secret 'Nouveau mot de passe'
    $mot2 = Read-Secret 'Le même, une seconde fois'
    if ($mot -cne $mot2) {
        $mot = $null; $mot2 = $null
        Show-Resultat 'attention' 'Les deux saisies sont différentes' 'Rien n''a changé.'
        Wait-Entree
        return
    }
    $x = Set-MotDePasseJed $i $identifiant $mot
    $mot = $null; $mot2 = $null
    if ($x.Ok) { Show-Resultat 'ok' "Mot de passe changé pour « $identifiant »" 'Si le compte était bloqué par trop d''essais, attendez 15 minutes.' }
    else { Show-Resultat 'erreur' 'Rien n''a changé' $x.Message }
    Wait-Entree
}

function Start-VerificationMigration {
    $i = Select-Installation 'à vérifier après une migration'
    if (-not $i) { return }
    Write-Titre "Vérifier la migration de « $($i.Nom) » (rien n'est modifié)"
    $script = Get-ScriptInstallationJed $i 'verifier-migration.ps1' $Racine
    $arguments = New-ArgumentsMigrationJed $script $i.Dossier
    $x = Invoke-ScriptJed -Arguments $arguments -Dossier $i.Dossier -SurLigne { param($l) Write-Ligne $l }
    $m = Get-MessageVerificationJed $x.Code
    Show-Resultat $m.Niveau $m.Titre $m.Texte
    Wait-Entree
}

function Reset-Essai {
    <# Comme la fenêtre : seulement une installation d'essai ; sauvegarde avant (conseillée, si l'essai est en
       marche) ; réinitialisation simple ou complète ; il faut taper REINITIALISER. #>
    $i = Select-Installation 'd''essai à réinitialiser'
    if (-not $i) { return }
    if (-not $i.Essai) {
        Show-Resultat 'attention' 'Réservé aux essais' "« $($i.Nom) » n'est pas une installation d'essai (son nom ne contient pas « essai ») : la réinitialisation est réservée aux essais."
        Wait-Entree
        return
    }
    $script = [System.IO.Path]::Combine($i.Dossier, 'reinitialiser-essai.ps1')
    if (-not (Test-Path -LiteralPath $script)) { Show-Resultat 'erreur' 'Script absent' "reinitialiser-essai.ps1 est absent du dossier de « $($i.Nom) »."; Wait-Entree; return }
    Write-Titre "Réinitialiser l'essai « $($i.Nom) »"
    Write-Host 'La réinitialisation EFFACE les données de cet essai (base, notices, journaux) puis le redémarre vide.'
    Write-Host 'Le script refuse toute installation qui n''est pas un essai.'
    $sauver = $false
    if ($i.Etat -eq 'en marche') { $sauver = Read-OuiNon 'Faire d''abord une sauvegarde de l''essai (conseillé, pour pouvoir revenir en arrière) ?' $true }
    else { Write-Host 'L''essai est arrêté : pas de sauvegarde possible avant l''effacement.' -ForegroundColor Yellow }
    Write-Host ("Réinitialisation complète : efface aussi les paquets de langues Argos de cet essai et, si aucune autre installation " +
        "ne s'en sert, les images de J-ed. L'essai reste alors arrêté : « Démarrer » le reconstruit.") -ForegroundColor DarkGray
    $complet = Read-OuiNon 'Réinitialisation complète ?' $false
    if (-not (Read-Confirmation "Les données de l'essai « $($i.Nom) » vont être effacées." 'REINITIALISER')) { Wait-Entree; return }
    if ($sauver) {
        Write-Titre 'Sauvegarde avant effacement'
        $s = Invoke-SauvegardeJed -Installation $i -SurLigne { param($l) Write-Ligne $l }
        if (-not $s.Ok) { Show-Resultat 'erreur' 'Sauvegarde impossible : rien n''a été effacé' $s.Message; Wait-Entree; return }
        Write-Host $s.Message
    }
    Write-Titre 'Réinitialisation'
    $arguments = New-ArgumentsReinitialisationJed $script -Complet:$complet
    $x = Invoke-ScriptJed -Arguments $arguments -Dossier $i.Dossier -Entree "REINITIALISER`n" -SurLigne { param($l) Write-Ligne $l }
    $m = Get-MessageReinitialisationJed -Code $x.Code -Lignes $x.Lignes -Complet:$complet -Dossier $i.Dossier
    $texte = $m.Texte.Replace('choisissez-le dans la liste et cliquez sur « Démarrer »', 'choisissez « 3. Démarrer »')
    Show-Resultat $m.Niveau $m.Titre $texte
    Wait-Entree
}

# --- Raccourcis, « Ça ne marche pas » (lot 3) ---------------------------------------------------------------

function New-Raccourcis {
    $i = Select-Installation 'pour laquelle créer les raccourcis'
    if (-not $i) { return }
    Write-Titre "Créer les raccourcis de « $($i.Nom) »"
    try {
        $fichiers = New-RaccourcisLinuxJed -Installation $i -DossierAssistant $Racine
        Show-Resultat 'ok' 'Raccourcis créés' ("Dans le menu Applications d'Ubuntu (touche Super, puis tapez « J-ed ») :`n" +
            "« $(Get-NomRaccourciJed $i) » ouvre J-ed dans le navigateur ; « Assistant J-ed » ouvre ce menu.")
        foreach ($f in $fichiers) { Write-Host "  $f" -ForegroundColor DarkGray }
    } catch {
        Show-Resultat 'erreur' 'Raccourcis impossibles' $_.Exception.Message
    }
    Wait-Entree
}

function New-CompteRendu {
    <# « Ça ne marche pas » : compte rendu sans aucun secret (le module le contrôle), sur le Bureau. #>
    $i = Select-Installation 'qui pose problème' -Facultatif
    Write-Titre 'Ça ne marche pas : compte rendu'
    Write-Host 'Préparation du compte rendu (une minute environ)…'
    try {
        $zip = New-CompteRenduJed -Installation $i -Destination (Get-DossierBureauJed) -VersionAssistant (Get-VersionAssistant)
        Show-Resultat 'ok' 'Compte rendu prêt' ("Fichier : $zip`n" +
            'Il ne contient ni mot de passe, ni clé, ni adresse électronique. Envoyez-le à la personne qui vous aide.')
    } catch {
        Show-Resultat 'erreur' 'Compte rendu impossible' $_.Exception.Message
    }
    Wait-Entree
}

function Get-VersionAssistant {
    $f = [System.IO.Path]::Combine($Racine, 'VERSION')
    if (Test-Path -LiteralPath $f) { return "$((Get-Content -LiteralPath $f -Raw).Trim()) (Linux)" }
    return '? (Linux)'
}

# --- Nouvelle installation ---------------------------------------------------------------------------------

function Read-Chemin([string]$Question, [string]$ParDefaut = '') {
    $c = Read-Ligne $Question $ParDefaut
    if ($c -and $c.StartsWith('~')) { $c = [Environment]::GetFolderPath('UserProfile') + $c.Substring(1) }
    return $c
}

function Use-Proxy {
    <# Proxy du réseau : proposé d'après le terminal ou les réglages d'Ubuntu. Il sert au téléchargement depuis
       GitHub, à la commande docker (construction) et à J-ed (.env, par installer-j-ed.ps1 -Proxy). #>
    $detecte = Get-ProxySystemeJed
    $proxy = ''
    if ($detecte) {
        Write-Host "Proxy trouvé dans les réglages : $detecte"
        if (Read-OuiNon 'Mon réseau passe par ce proxy : l''utiliser ?' $true) { $proxy = $detecte }
    } elseif (Read-OuiNon 'Votre réseau passe-t-il par un proxy ?' $false) {
        $proxy = Read-Ligne 'Adresse du proxy (forme http://nom-ou-adresse:port)'
    }
    if ($proxy) {
        $t = Test-AdresseProxyJed $proxy
        if (-not $t.Ok) { Show-Resultat 'erreur' 'Proxy refusé' $t.Raison; return $null }
        foreach ($nom in @('HTTP_PROXY', 'HTTPS_PROXY')) {
            if (-not [Environment]::GetEnvironmentVariable($nom)) { [Environment]::SetEnvironmentVariable($nom, $proxy) }
        }
        if (-not $env:NO_PROXY) { $env:NO_PROXY = 'localhost,127.0.0.1' }
    }
    return $proxy
}

function Select-Archive {
    <# Archive vérifiée (empreinte conforme, fichier VERSION) : objet Archive, Empreinte, Version ; ou $null.
       -VersionActuelle (mise à jour) : la dernière version publiée n'est pas proposée si elle n'est pas plus récente. #>
    param([string]$VersionActuelle = '')
    while ($true) {
        Write-Host ''
        Write-Host 'Archive de J-ed :'
        Write-Host '   1. Télécharger la dernière version (GitHub)'
        Write-Host '   2. Indiquer une archive déjà téléchargée (.zip)'
        Write-Host '   0. Retour'
        $choix = Read-Ligne 'Votre choix' '1'
        $archive = ''; $empreinte = ''
        if ($choix -eq '0') { return $null }
        if ($choix -eq '1') {
            Write-Host 'Recherche de la dernière version sur GitHub…'
            $info = Get-DerniereVersionGitHubJed
            if (-not $info.Ok) { Show-Resultat 'erreur' 'GitHub ne répond pas' $info.Raison; continue }
            if ($VersionActuelle -and (Compare-VersionJed $info.Version $VersionActuelle) -le 0) {
                Show-Resultat 'ok' "Dernière version publiée : $($info.Version)" 'Votre installation est déjà à jour.'
                continue
            }
            $dossier = Get-DossierTelechargementsJed
            $taille = Format-NombreJed ($info.Archive.Taille / 1MB)
            if (-not (Read-OuiNon "Télécharger J-ed $($info.Version) ($taille Mo) dans $dossier ?" $true)) { continue }
            Write-Host 'Téléchargement…'
            $t = Save-DerniereVersionJed $info $dossier
            if (-not $t.Archive -or -not (Test-Path -LiteralPath $t.Archive)) { Show-Resultat 'erreur' 'Téléchargement impossible' $t.Raison; continue }
            $archive = $t.Archive; $empreinte = $t.Empreinte
        } elseif ($choix -eq '2') {
            $archive = Read-Chemin 'Chemin de l''archive (.zip)'
            if (-not $archive -or -not (Test-Path -LiteralPath $archive -PathType Leaf)) { Write-Host 'Archive introuvable.' -ForegroundColor Yellow; continue }
            $archive = (Resolve-Path -LiteralPath $archive).Path
            $empreinte = Find-FichierEmpreinteJed $archive
            if (-not $empreinte) { $empreinte = Read-Chemin 'Fichier d''empreinte (.sha256) de cette archive' }
        } else { Write-Host 'Choix inconnu.'; continue }
        $e = Test-EmpreinteJed -Archive $archive -Empreinte $empreinte
        if (-not $e.Ok) { Show-Resultat 'erreur' 'Archive refusée' $e.Raison; continue }
        $v = $null
        try { $v = Get-VersionArchiveJed $archive } catch { }
        if (-not $v) { Show-Resultat 'erreur' 'Archive refusée' "Ce n'est pas une archive de J-ed (fichier VERSION absent)."; continue }
        Write-Niveau 'ok' "Archive de la version $v : empreinte conforme."
        return [pscustomobject]@{ Archive = $archive; Empreinte = $empreinte; Version = $v }
    }
}

function New-Installation {
    <# -PourRestauration (lot 3) : installation neuve pour y restaurer une sauvegarde ; pas de fin guidée (les comptes
       viendront de la sauvegarde). L'installation créée est rangée dans $script:InstallationCreee. #>
    param([string]$NomPropose = 'jed', [switch]$PourRestauration)
    $script:InstallationCreee = $null
    if ($PourRestauration) { Write-Titre 'Nouvelle installation pour y restaurer la sauvegarde' }
    else { Write-Titre 'Nouvelle installation' }
    $erreurs = @(Get-Prerequis | Where-Object { $_.Niveau -eq 'erreur' })
    if ($erreurs.Count) {
        Write-Niveau 'erreur' 'Des prérequis ne sont pas remplis :'
        foreach ($c in $erreurs) { Write-Host "  - $($c.Libelle) : $($c.Detail)"; if ($c.Conseil) { Write-Host "    → $($c.Conseil)" } }
        Wait-Entree
        return
    }
    $proxy = Use-Proxy
    if ($null -eq $proxy) { Wait-Entree; return }
    $a = Select-Archive
    if (-not $a) { return }
    $volumes = Get-VolumesDockerJed
    $nom = ''
    while ($true) {
        $nom = Read-Ligne 'Nom de l''installation (lettres minuscules, chiffres, tirets)' (Get-NomProposeJed $NomPropose $script:Installations $volumes)
        $n = Test-NomProjetJed $nom $script:Installations $volumes
        if ($n.Ok) { break }
        Write-Host $n.Raison -ForegroundColor Yellow
    }
    $port = 0
    while ($true) {
        $r = Read-Ligne 'Port' "$(Get-PortLibreJed $script:Installations)"
        if ([int]::TryParse($r, [ref]$port) -and (Test-PortJed $port $script:Installations).Ok) { break }
        if ($port) { Write-Host (Test-PortJed $port $script:Installations).Raison -ForegroundColor Yellow } else { Write-Host 'Un nombre, par exemple 8001.' }
    }
    $destination = ''
    while ($true) {
        $destination = Read-Chemin 'Emplacement (un dossier neuf)' (Get-EmplacementParDefautJed $script:Installations $nom $a.Version)
        if ($destination -and -not (Test-Path -LiteralPath $destination)) { break }
        Write-Host "Le dossier $destination existe déjà : choisissez-en un autre." -ForegroundColor Yellow
    }
    $parent = Split-Path -Parent $destination
    $sauvegardes = Read-Chemin 'Dossier des sauvegardes de cette installation' ([System.IO.Path]::Combine($parent, "sauvegardes-$nom"))
    $argos = Read-OuiNon 'Traduction hors ligne Argos (conseillée ; environ 2 Go de plus) ?' $true
    if (Read-OuiNon 'Vérifier d''abord que Docker joint Internet (téléchargement de l''image de base) ?' $true) {
        Write-Titre 'Docker joint-il Internet ?'
        $d = Invoke-DockerJed '' (Get-CommandeAccesRegistreJed) -SurLigne { param($l) Write-Ligne $l }
        if ($d.Code -eq 0) { Show-Resultat 'ok' 'Docker joint Internet' 'L''installation pourra télécharger ce dont elle a besoin.' }
        else {
            Show-Resultat 'erreur' 'Docker ne joint pas Internet' (Get-ConseilProxyDockerJed $proxy)
            if (-not (Read-OuiNon 'Installer quand même ?' $false)) { return }
        }
    }
    Write-Titre 'Récapitulatif'
    Write-Host "  Archive : $($a.Archive) (version $($a.Version))"
    Write-Host "  Nom : $nom ; port : $port"
    Write-Host "  Emplacement : $destination"
    Write-Host "  Sauvegardes : $sauvegardes"
    $texteArgos = 'non'
    if ($argos) { $texteArgos = 'oui' }
    $texteProxy = 'aucun'
    if ($proxy) { $texteProxy = $proxy }
    Write-Host "  Argos : $texteArgos ; proxy : $texteProxy"
    if (-not (Read-OuiNon 'Installer ?' $true)) { return }

    # Le script de l'archive s'il existe (2.0.2 et suivantes), sinon celui de l'assistant (comme la fenêtre).
    $temp = Get-DossierTemporaireJed "installation-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $scriptInst = Export-ScriptArchiveJed -Archive $a.Archive -Nom 'installer-j-ed.ps1' -Dossier $temp
    if (-not $scriptInst) { $scriptInst = [System.IO.Path]::Combine($Racine, 'installer-j-ed.ps1') }
    $arguments = New-ArgumentsInstallationJed -Script $scriptInst -Archive $a.Archive -Empreinte $a.Empreinte `
        -Destination $destination -Nom $nom -Port $port -DossierSauvegardes $sauvegardes -Proxy $proxy -SansArgos:(-not $argos)
    Write-Titre "Installer « $nom » (la construction prend 15 à 30 minutes la première fois)"
    $restauration = [bool]$PourRestauration
    $x = Invoke-ScriptJed -Arguments $arguments -SurLigne { param($l) Write-Ligne (Convert-LigneInstallationJed $l -PourRestauration:$restauration) }
    $m = Get-MessageInstallationJed $x.Code -PourRestauration:$restauration
    Show-Resultat $m.Niveau $m.Titre $m.Texte
    if ($x.Code -ne 0) {
        if ($x.Code -in @(1, 3, 5)) { Show-ErreurDocker (@($x.Lignes) -join "`n") }
        $conseil = Get-ConseilDossierInstallationJed $x.Code $x.Lignes
        if ($conseil) { Write-Host ''; foreach ($l in ($conseil -split "`n")) { Write-Host "  $l" } }
        if ($x.Journal) { Write-Host "  Journal : $($x.Journal)" }
        Wait-Entree
        return
    }
    Add-InstallationListeJed -Fichier $script:Liste -Dossier $destination
    $nouvelle = Get-InstallationJed $destination
    $nouvelle.Etat = 'en marche'
    $script:InstallationCreee = $nouvelle
    if (-not $PourRestauration) { Show-FinInstallation $nouvelle }
}

function Show-FinInstallation($Installation) {
    <# Fin guidée, comme la fenêtre Windows : compte administrateur, puis jeu d'essai. #>
    while ($true) {
        Write-Titre "« $($Installation.Nom) » est installée : encore deux étapes"
        Write-Host '   1. Créer le compte administrateur (ouvre le navigateur)'
        Write-Host '   2. Charger le jeu d''essai (notices fictives)'
        Write-Host '   0. Terminé'
        switch (Read-Ligne 'Votre choix') {
            '1' { Write-Host 'Créez le compte dans le navigateur (un seul clic sur le bouton) :'; Open-AdresseJed (Get-AdressePremierDemarrageJed $Installation) }
            '2' {
                Write-Host 'Chargement des notices fictives…'
                $d = Invoke-DockerJed $Installation.Dossier @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'jeu_essai', '--charger') -SurLigne { param($l) Write-Ligne $l }
                if ($d.Code -eq 0) { Show-Resultat 'ok' 'Jeu d''essai chargé' 'Ouvrez J-ed : l''aide « Essayer J-ed » guide la découverte.' }
                else { Show-Resultat 'attention' 'Jeu d''essai non chargé' 'Créez d''abord le compte administrateur (choix 1), puis recommencez.' }
            }
            '0' { return }
            default { Write-Host 'Choix inconnu.' }
        }
    }
}

# --- Mettre à jour une installation (lot 2) ----------------------------------------------------------------

function Update-InstallationJed {
    <# Comme la fenêtre Windows : installation en marche, archive et empreinte, dossier des sauvegardes, proxy,
       « Docker joint-il Internet ? », installation protégée, puis le mettre-a-jour.ps1 de la NOUVELLE version ;
       la confirmation OUI est demandée ici quand la nouvelle version est prête (jamais -Oui). #>
    $i = Select-Installation 'à mettre à jour'
    if (-not $i) { return }
    Write-Titre "Mettre à jour « $($i.Nom) » (version $($i.Version))"
    Write-Host "  Installation : $($i.Dossier)"
    if ($i.Etat -ne 'en marche') {
        if (-not (Read-OuiNon "« $($i.Nom) » est arrêtée. Elle doit être en marche pour que sa sauvegarde soit faite avant la mise à jour. La démarrer maintenant ?" $true)) { return }
        $d = Invoke-DockerJed $i.Dossier (Get-CommandeActionJed 'Demarrer') -SurLigne { param($l) Write-Ligne $l }
        if ($d.Code -ne 0) { Show-Resultat 'erreur' 'Démarrage impossible' ''; Show-ErreurDocker $d.Texte; Wait-Entree; return }
    }
    $proxy = Use-Proxy
    if ($null -eq $proxy) { Wait-Entree; return }
    $a = Select-Archive -VersionActuelle $i.Version
    if (-not $a) { return }
    $defaut = $i.DossierSauvegardes
    if (-not $defaut) { $defaut = [System.IO.Path]::Combine((Split-Path -Parent $i.Dossier), 'sauvegardes') }
    $sauvegardes = Read-Chemin 'Dossier des sauvegardes (une sauvegarde vérifiée y est copiée avant la mise à jour)' $defaut
    if (Read-OuiNon 'Vérifier d''abord que Docker joint Internet (téléchargement de l''image de base) ?' $true) {
        Write-Titre 'Docker joint-il Internet ?'
        $d = Invoke-DockerJed $i.Dossier (Get-CommandeAccesRegistreJed) -SurLigne { param($l) Write-Ligne $l }
        if ($d.Code -eq 0) { Show-Resultat 'ok' 'Docker joint Internet' 'La construction de la nouvelle version pourra télécharger ce dont elle a besoin.' }
        else {
            Show-Resultat 'erreur' 'Docker ne joint pas Internet' (Get-ConseilProxyDockerJed $proxy)
            if (-not (Read-OuiNon 'Lancer la mise à jour quand même ?' $false)) { return }
        }
    }
    # Comme la fenêtre (2.0.2-rc5, R4) : l'avertissement « installation protégée » vient AVANT toute écriture du .env.
    if ($i.Protegee) {
        Write-Host (Get-TexteProtegeeJed $i) -ForegroundColor Yellow
        if (-not (Read-OuiNon 'Conseil : essayez d''abord la mise à jour sur une copie. Continuer quand même ?' $false)) { return }
    }
    $fichierEnv = [System.IO.Path]::Combine($i.Dossier, '.env')
    if ($proxy -and -not (Test-ProxyEnvJed -Fichier $fichierEnv -Proxy $proxy)) {
        if (-not (Read-OuiNon "Le proxy $proxy va être écrit dans le fichier .env de « $($i.Nom) » (une copie de l'ancien fichier est gardée à côté). La nouvelle version le reprendra. Continuer ?" $true)) { return }
        Set-ProxyEnvJed -Fichier $fichierEnv -Proxy $proxy
    }
    $temp = Get-DossierTemporaireJed "mise-a-jour-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $scriptMaj = Export-ScriptArchiveJed -Archive $a.Archive -Dossier $temp
    if (-not $scriptMaj) {
        Show-Resultat 'erreur' 'Archive refusée' "mettre-a-jour.ps1 est absent de l'archive : ce n'est pas une archive de J-ed 2.0 ou plus récente."
        Wait-Entree
        return
    }
    $arguments = New-ArgumentsMiseAJourJed -Script $scriptMaj -Archive $a.Archive -Actuel $i.Dossier -DossierSauvegardes $sauvegardes -Empreinte $a.Empreinte
    Write-Titre "Mettre à jour « $($i.Nom) » vers la version $($a.Version) (la construction prend plusieurs minutes)"
    $question = {
        param($q)
        Write-Host ''
        Write-Host 'La nouvelle version est prête.' -ForegroundColor Green
        Write-Host 'L''ancienne version va maintenant être arrêtée, puis la nouvelle démarrée. Aucune donnée n''est effacée ;'
        Write-Host 'si la nouvelle version ne démarre pas, l''assistant revient tout seul à l''ancienne.'
        Read-OuiNon 'Continuer ?' $false
    }
    $x = Invoke-ScriptJed -Arguments $arguments -SurLigne { param($l) Write-Ligne $l } -SurQuestion $question
    $m = Get-MessageMiseAJourJed $x.Code
    Show-Resultat $m.Niveau $m.Titre $m.Texte
    if ($x.Code -in @(1, 3, 5)) { Show-ErreurDocker (@($x.Lignes) -join "`n") }
    $conseil = Get-ConseilDossierMiseAJourJed $x.Code $x.Lignes
    if ($conseil) { Write-Host ''; foreach ($l in ($conseil -split "`n")) { Write-Host "  $l" } }
    $nouveau = Get-DossierNouvelleVersionJed $x.Lignes
    if ($x.Code -eq 0 -and $nouveau) {
        Add-InstallationListeJed -Fichier $script:Liste -Dossier $nouveau
        Write-Host "  Nouvelle version dans : $nouveau"
        Write-Host '  L''ancien dossier est gardé (il apparaît comme « ancien dossier » dans la liste).'
    }
    if ($x.Journal) { Write-Host "  Journal : $($x.Journal)" }
    Wait-Entree
}

# --- Accueil -----------------------------------------------------------------------------------------------

if (-not (Test-LinuxJed)) {
    Write-Host 'Ce menu sert sous Linux. Sous Windows, ouvrez J-ed.cmd (assistant en fenêtre).' -ForegroundColor Yellow
    exit 1
}
if ((Get-UidJed) -eq 0) {
    Write-Host 'Ne lancez pas l''assistant en administrateur (sudo ou root) : relancez j-ed.sh depuis votre compte, sans sudo.' -ForegroundColor Red
    exit 1
}

while ($true) {
    Update-Installations
    Write-Host ''
    Write-Host 'J-ed — Assistant (Linux)' -ForegroundColor White
    Write-Host 'Installer, mettre à jour, vérifier et sauvegarder J-ed.'
    Show-Installations
    Write-Host ''
    Show-ResumePrerequis (Get-Prerequis)
    Write-Host ''
    Write-Host '   1. Mettre à jour une installation'
    Write-Host '   2. Nouvelle installation'
    Write-Host '   3. Démarrer            4. Arrêter            5. Ouvrir J-ed'
    Write-Host '   6. Vérifier            7. Créer les raccourcis'
    Write-Host '   8. Ajouter une installation…'
    Write-Host '   9. Voir les prérequis'
    Write-Host '  10. Opérations de maintenance'
    Write-Host '  11. Ça ne marche pas'
    Write-Host '  12. Aide : avant de commencer'
    Write-Host '   0. Fermer'
    switch (Read-Ligne 'Votre choix') {
        '1' { Update-InstallationJed }
        '2' { New-Installation }
        '3' { Invoke-Action 'Demarrer' 'Démarrer' 'J-ed démarre : il répond en général au bout d''une minute.' }
        '4' { Invoke-Action 'Arreter' 'Arrêter' 'J-ed est arrêté. Ses données sont intactes.' }
        '5' { Open-Installation }
        '6' { Start-Verification }
        '7' { New-Raccourcis }
        '8' { Add-Installation }
        '9' { Show-Prerequis }
        '10' { Show-Maintenance }
        '11' { New-CompteRendu }
        '12' { Show-Aide }
        '0' { Write-Host 'Au revoir.'; exit 0 }
        default { Write-Host 'Choix inconnu : tapez un numéro du menu.' }
    }
}
