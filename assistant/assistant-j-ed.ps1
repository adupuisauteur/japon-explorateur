<#
.SYNOPSIS
    Fenêtre de l'assistant J-ed (2.0.2), ouverte par un double-clic sur J-ed.cmd.

.DESCRIPTION
    L'assistant évite d'ouvrir PowerShell : il retrouve les installations, vérifie les prérequis, lance les
    scripts de J-ed (mise à jour, vérification) et les commandes Docker courantes, et montre leur déroulement en
    français. Toute la logique est dans AssistantJed.psm1 (testé automatiquement) ; ce fichier ne fait que
    l'affichage. Windows PowerShell 5.1 et Windows Forms, intégrés à Windows : rien à installer.

    Règles : la confirmation « OUI » vient toujours de l'utilisateur ; jamais « down -v » ; une seule opération à
    la fois, et la fenêtre d'une opération ne se ferme pas avant sa fin.
#>
$ErrorActionPreference = 'Stop'
$Ici = $PSScriptRoot
$Racine = Split-Path -Parent $Ici

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
} catch {
    Write-Host "L'assistant J-ed fonctionne sous Windows (Windows Forms introuvable)."
    exit 1
}
[System.Windows.Forms.Application]::EnableVisualStyles()

try {
    # Fichiers téléchargés : Windows les marque « venus d'Internet ». L'assistant débloque les siens seulement.
    foreach ($f in @(Get-ChildItem -LiteralPath $Ici -File) + @(Get-ChildItem -LiteralPath $Racine -Filter '*.ps1' -File)) {
        try { Unblock-File -LiteralPath $f.FullName } catch { }
    }
    Import-Module ([System.IO.Path]::Combine($Ici, 'AssistantJed.psm1')) -Force
} catch {
    # 2.0.2 (aperçu du 23/11) : sans console, une erreur au démarrage doit s'afficher.
    [void][System.Windows.Forms.MessageBox]::Show("L'assistant J-ed ne peut pas démarrer :`n`n$($_.Exception.Message)", 'Assistant J-ed', 'OK', 'Error')
    exit 1
}

$script:Version = '?'
$fichierVersion = [System.IO.Path]::Combine($Racine, 'VERSION')
if (Test-Path -LiteralPath $fichierVersion) { $script:Version = ([System.IO.File]::ReadAllText($fichierVersion)).Trim() }
$script:PageAide = [System.IO.Path]::Combine($Racine, 'AVANT-DE-COMMENCER.html')
$script:Liste = Get-FichierListeJed
$script:Installations = @()
$script:Police = New-Object System.Drawing.Font('Segoe UI', 10)
$script:PoliceTitre = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
$script:PoliceGras = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$script:Couleurs = @{
    ok = [System.Drawing.Color]::FromArgb(30, 120, 40)
    attention = [System.Drawing.Color]::FromArgb(190, 110, 0)
    erreur = [System.Drawing.Color]::FromArgb(180, 30, 30)
}
$script:Fonds = @{
    ok = [System.Drawing.Color]::FromArgb(225, 245, 225)
    attention = [System.Drawing.Color]::FromArgb(253, 240, 215)
    erreur = [System.Drawing.Color]::FromArgb(250, 225, 225)
}

# --- Petits outils d'affichage -------------------------------------------------------------------------

function Show-InfoJed([string]$Texte, [string]$Titre = 'Assistant J-ed') {
    [void][System.Windows.Forms.MessageBox]::Show($Texte, $Titre, 'OK', 'Information')
}

function Show-ErreurJed([string]$Texte, [string]$Titre = 'Assistant J-ed') {
    [void][System.Windows.Forms.MessageBox]::Show($Texte, $Titre, 'OK', 'Error')
}

function Confirm-ChoixJed([string]$Texte, [string]$Titre = 'Assistant J-ed') {
    return ([System.Windows.Forms.MessageBox]::Show($Texte, $Titre, 'YesNo', 'Warning') -eq 'Yes')
}

function New-BoutonJed([string]$Texte, [int]$X, [int]$Y, [int]$Largeur = 170, [int]$Hauteur = 34) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Texte
    $b.Location = New-Object System.Drawing.Point($X, $Y)
    $b.Size = New-Object System.Drawing.Size($Largeur, $Hauteur)
    $b.Font = $script:Police
    return $b
}

function New-EtiquetteJed([string]$Texte, [int]$X, [int]$Y, [int]$Largeur = 600, [int]$Hauteur = 24) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $Texte
    $l.Location = New-Object System.Drawing.Point($X, $Y)
    $l.Size = New-Object System.Drawing.Size($Largeur, $Hauteur)
    $l.Font = $script:Police
    return $l
}

function Set-TailleJed($Fenetre, [int]$Largeur, [int]$Hauteur) {
    # Petit écran (portable 15 pouces, mise à l'échelle 125 ou 150 %) : la fenêtre ne dépasse jamais la partie
    # utile de l'écran ; si elle est réduite, des barres de défilement donnent accès à tout son contenu.
    $zone = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $l = [Math]::Min($Largeur, $zone.Width - 10)
    $h = [Math]::Min($Hauteur, $zone.Height - 10)
    if ($l -lt $Largeur -or $h -lt $Hauteur) { $Fenetre.AutoScroll = $true }
    $Fenetre.Size = New-Object System.Drawing.Size($l, $h)
}

function New-FenetreJed([string]$Titre, [int]$Largeur, [int]$Hauteur) {
    $f = New-Object System.Windows.Forms.Form
    $f.Text = $Titre
    Set-TailleJed $f $Largeur $Hauteur
    $f.StartPosition = 'CenterParent'
    $f.Font = $script:Police
    $f.FormBorderStyle = 'FixedDialog'
    $f.MaximizeBox = $false
    $f.MinimizeBox = $false
    return $f
}

function Open-AideJed([string]$Ancre) {
    if (-not (Test-Path -LiteralPath $script:PageAide)) {
        Show-ErreurJed "Fichier d'aide introuvable : $script:PageAide"
        return
    }
    $url = 'file:///' + ($script:PageAide -replace '\\', '/')
    if ($Ancre) { $url += '#' + $Ancre }
    try { Start-Process $url } catch { Start-Process -FilePath $script:PageAide }
}

function Open-DossierJed([string]$Chemin) {
    if ($Chemin -and (Test-Path -LiteralPath $Chemin -PathType Leaf)) {
        Start-Process -FilePath 'explorer.exe' -ArgumentList "/select,`"$Chemin`""
    } elseif ($Chemin -and (Test-Path -LiteralPath $Chemin)) {
        Start-Process -FilePath 'explorer.exe' -ArgumentList "`"$Chemin`""
    } else {
        Show-ErreurJed "Introuvable : $Chemin"
    }
}

function New-ResultatJed([string]$Niveau, [string]$Titre, [string]$Texte, [string]$Journal, [string]$Fichier) {
    return [pscustomobject]@{ Niveau = $Niveau; Titre = $Titre; Texte = $Texte; Journal = $Journal; Fichier = $Fichier }
}

function Add-ExplicationJed($Resultat, [string[]]$Lignes) {
    # Ajoute l'explication en français d'une erreur Docker reconnue dans ce qui a été affiché.
    $e = Convert-ErreurDockerJed (@($Lignes) -join "`n")
    if ($e) { $Resultat.Texte += "`n`nCause probable : $($e.Explication)`nQue faire : $($e.Solution)" }
    if ($e -and $e.Cle -eq 'internet') { $Resultat.Texte += "`n`n" + (Get-ConseilProxyDockerJed (Get-ProxySystemeJed)) }
    return $Resultat
}

# --- Fenêtre d'une opération -----------------------------------------------------------------------------

function Start-OperationJed {
    <# Montre le déroulement d'une opération. $Travail reçoit trois blocs : $SurLigne (une ligne affichée),
       $SurAttente (garder la fenêtre active) et $SurEtape (titre de l'étape) ; il renvoie un résultat
       (New-ResultatJed). La fenêtre ne se ferme qu'à la fin. #>
    param([string]$Titre, [scriptblock]$Travail)
    $f = New-FenetreJed $Titre 860 600
    $etape = New-EtiquetteJed 'Préparation…' 16 12 810 26
    $etape.Font = $script:PoliceGras
    $barre = New-Object System.Windows.Forms.ProgressBar
    $barre.Location = New-Object System.Drawing.Point(16, 42)
    $barre.Size = New-Object System.Drawing.Size(810, 16)
    $barre.Style = 'Marquee'
    $texte = New-Object System.Windows.Forms.TextBox
    $texte.Multiline = $true
    $texte.ReadOnly = $true
    $texte.ScrollBars = 'Vertical'
    $texte.Font = New-Object System.Drawing.Font('Consolas', 9)
    $texte.Location = New-Object System.Drawing.Point(16, 66)
    $texte.Size = New-Object System.Drawing.Size(810, 330)
    $bandeau = New-EtiquetteJed '' 16 404 810 100
    $bandeau.Padding = New-Object System.Windows.Forms.Padding(8)
    $bJournal = New-BoutonJed 'Ouvrir le journal' 16 512 170
    $bFichier = New-BoutonJed 'Afficher le fichier' 196 512 170
    $bCopier = New-BoutonJed 'Copier le compte rendu' 376 512 200
    $bFermer = New-BoutonJed 'Fermer' 656 512 170
    foreach ($b in @($bJournal, $bFichier, $bCopier, $bFermer)) { $b.Enabled = $false }
    $f.Controls.AddRange(@($etape, $barre, $texte, $bandeau, $bJournal, $bFichier, $bCopier, $bFermer))
    $etat = @{ Fini = $false; Resultat = $null }

    $f.Add_FormClosing({
        param($s, $e)
        if (-not $etat.Fini) {
            $e.Cancel = $true
            Show-InfoJed "Une opération est en cours : attendez qu'elle se termine. Fermer maintenant pourrait laisser J-ed à moitié mis à jour."
        }
    })
    $bFermer.Add_Click({ $f.Close() })
    $bJournal.Add_Click({ Start-Process -FilePath 'notepad.exe' -ArgumentList "`"$($etat.Resultat.Journal)`"" })
    $bFichier.Add_Click({ Open-DossierJed $etat.Resultat.Fichier })
    $bCopier.Add_Click({
        $r = $etat.Resultat
        $compte = "$Titre`r`n$($r.Titre)`r`n$($r.Texte)`r`n`r`n$($texte.Text)"
        [System.Windows.Forms.Clipboard]::SetText((Protect-TexteJed $compte))
        Show-InfoJed 'Compte rendu copié (sans mot de passe ni adresse électronique) : collez-le dans un message.'
    })
    $f.Add_Shown({
        $surLigne = { param($l) $texte.AppendText("$l`r`n"); [System.Windows.Forms.Application]::DoEvents() }
        $surAttente = { [System.Windows.Forms.Application]::DoEvents() }
        $surEtape = { param($t) $etape.Text = $t; [System.Windows.Forms.Application]::DoEvents() }
        [System.Windows.Forms.Application]::DoEvents()
        try {
            $r = & $Travail $surLigne $surAttente $surEtape
        } catch {
            $r = New-ResultatJed 'erreur' 'Erreur inattendue' "$($_.Exception.Message)`n`nUtilisez « Ça ne marche pas » pour préparer un compte rendu." $null $null
        }
        if (-not $r) { $r = New-ResultatJed 'erreur' 'Erreur inattendue' 'Aucun résultat.' $null $null }
        $etat.Resultat = $r
        $etat.Fini = $true
        $barre.Style = 'Continuous'
        $barre.Value = 100
        $etape.Text = $r.Titre
        $bandeau.Text = "$($r.Titre)`n$($r.Texte)"
        $bandeau.ForeColor = $script:Couleurs[$r.Niveau]
        $bandeau.BackColor = $script:Fonds[$r.Niveau]
        $bJournal.Enabled = [bool]($r.Journal -and (Test-Path -LiteralPath $r.Journal))
        $bFichier.Enabled = [bool]$r.Fichier
        $bCopier.Enabled = $true
        $bFermer.Enabled = $true
        $bFermer.Focus()
    })
    [void]$f.ShowDialog()
    return $etat.Resultat
}

# --- Prérequis -------------------------------------------------------------------------------------------

function Get-BilanPrerequisJed {
    $controles = Test-PrerequisJed (Get-FaitsSystemeJed -Dossier "$env:SystemDrive\")
    $erreurs = @($controles | Where-Object { $_.Niveau -eq 'erreur' }).Count
    return [pscustomobject]@{ Controles = $controles; Erreurs = $erreurs }
}

function Show-PrerequisJed {
    $f = New-FenetreJed 'Avant de commencer : ce qu''il faut sur cet ordinateur' 760 560
    $panneau = New-Object System.Windows.Forms.Panel
    $panneau.Location = New-Object System.Drawing.Point(16, 16)
    $panneau.Size = New-Object System.Drawing.Size(710, 380)
    $panneau.AutoScroll = $true
    $bVerifier = New-BoutonJed 'Vérifier à nouveau' 16 412 180
    $bDocker = New-BoutonJed 'Télécharger Docker Desktop' 206 412 230
    $bGuide = New-BoutonJed 'Lire « Avant de commencer »' 446 412 230
    $bFermer = New-BoutonJed 'Fermer' 556 452 170
    $f.Controls.AddRange(@($panneau, $bVerifier, $bDocker, $bGuide, $bFermer))
    $remplir = {
        $panneau.Controls.Clear()
        $f.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        $bilan = Get-BilanPrerequisJed
        $f.Cursor = [System.Windows.Forms.Cursors]::Default
        $y = 0
        foreach ($c in $bilan.Controles) {
            $marque = @{ ok = 'OK'; attention = 'À voir'; erreur = 'À régler' }[$c.Niveau]
            $m = New-EtiquetteJed $marque 0 ($y + 4) 80 24
            $m.Font = $script:PoliceGras
            $m.ForeColor = $script:Couleurs[$c.Niveau]
            $t = New-EtiquetteJed "$($c.Libelle) : $($c.Detail)" 84 ($y + 4) 450 44
            $panneau.Controls.AddRange(@($m, $t))
            if ($c.Niveau -ne 'ok') {
                $b = New-BoutonJed 'Comment faire ?' 545 $y 150 30
                $b.Tag = ($c.Aide -replace '^.*#', '')
                $b.Add_Click({ param($s, $e) Open-AideJed $s.Tag })
                $panneau.Controls.Add($b)
            }
            $y += 52
        }
    }
    $bVerifier.Add_Click({ & $remplir })
    $bDocker.Add_Click({ Start-Process 'https://www.docker.com/products/docker-desktop/' })
    $bGuide.Add_Click({ Open-AideJed '' })
    $bFermer.Add_Click({ $f.Close() })
    $f.Add_Shown({ & $remplir })
    [void]$f.ShowDialog()
    Update-BilanJed
}

function Update-BilanJed {
    $bilan = Get-BilanPrerequisJed
    if ($bilan.Erreurs -eq 0) {
        $script:EtiquettePrerequis.Text = 'Prérequis : tout est prêt.'
        $script:EtiquettePrerequis.ForeColor = $script:Couleurs['ok']
    } else {
        $script:EtiquettePrerequis.Text = "Prérequis : $($bilan.Erreurs) point(s) à régler avant d'installer ou de mettre à jour."
        $script:EtiquettePrerequis.ForeColor = $script:Couleurs['erreur']
    }
    return $bilan
}

# --- Liste des installations ---------------------------------------------------------------------------

function Update-ListeJed {
    $script:Fenetre.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
    try {
        $script:Installations = @(Find-InstallationsJed -Fichier $script:Liste)
    } finally {
        $script:Fenetre.Cursor = [System.Windows.Forms.Cursors]::Default
    }
    $lv = $script:ListeVue
    $lv.BeginUpdate()
    $lv.Items.Clear()
    foreach ($i in $script:Installations) {
        $nom = $i.Nom
        if (-not $nom) { $nom = '(inconnue)' }
        $item = New-Object System.Windows.Forms.ListViewItem($nom)
        if ($i.Valide) {
            $s = Get-DerniereSauvegardeJed $i
            $sauvegarde = '—'
            if ($s) { $sauvegarde = $s.Texte } elseif ($i.DossierSauvegardes) { $sauvegarde = 'aucune' }
            [void]$item.SubItems.Add($i.Version)
            [void]$item.SubItems.Add("$($i.Port)")
            [void]$item.SubItems.Add($i.Etat)
            [void]$item.SubItems.Add($sauvegarde)
            if ($i.Etat -eq 'en marche') { $item.ForeColor = $script:Couleurs['ok'] }
            if ($s -and $s.Jours -gt 7) { $item.BackColor = $script:Fonds['attention'] }
        } else {
            [void]$item.SubItems.Add('?')
            [void]$item.SubItems.Add('')
            [void]$item.SubItems.Add($i.Probleme)
            [void]$item.SubItems.Add('')
            $item.ForeColor = [System.Drawing.Color]::Gray
        }
        [void]$item.SubItems.Add($i.Dossier)
        $item.Tag = $i
        [void]$lv.Items.Add($item)
    }
    $lv.EndUpdate()
    if ($lv.Items.Count -eq 1) { $lv.Items[0].Selected = $true }
}

function Get-ChoixJed {
    if ($script:ListeVue.SelectedItems.Count -eq 0) {
        Show-InfoJed "Choisissez d'abord une installation dans la liste."
        return $null
    }
    $i = $script:ListeVue.SelectedItems[0].Tag
    if (-not $i.Valide) {
        Show-ErreurJed "Cette installation n'est pas utilisable : $($i.Probleme)"
        return $null
    }
    return $i
}

# --- Opérations courantes ----------------------------------------------------------------------------

function Start-ActionDockerJed($Installation, [string]$Action, [string]$Libelle, [string]$Reussite) {
    $arguments = Get-CommandeActionJed $Action
    $r = Start-OperationJed "$Libelle « $($Installation.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        & $surEtape "$Libelle…"
        $d = Invoke-DockerJed $Installation.Dossier $arguments -SurAttente $surAttente -SurLigne $surLigne
        if ($d.Code -eq 0) { return New-ResultatJed 'ok' 'Terminé' $Reussite $null $null }
        $res = New-ResultatJed 'erreur' 'Échec' "La commande a échoué (code $($d.Code))." $null $null
        return Add-ExplicationJed $res @($d.Texte)
    }
    Update-ListeJed
    return $r
}

function Start-VerificationJed {
    $i = Get-ChoixJed
    if (-not $i) { return }
    $f = New-FenetreJed "Vérifier « $($i.Nom) »" 560 260
    $l = New-EtiquetteJed "La vérification ne modifie rien. Elle écrit un rapport à côté du dossier de l'installation." 16 16 510 44
    $cTests = New-Object System.Windows.Forms.CheckBox
    $cTests.Text = 'Avec les tests automatiques (3 à 10 minutes)'
    $cTests.Location = New-Object System.Drawing.Point(16, 70)
    $cTests.Size = New-Object System.Drawing.Size(500, 26)
    $cSources = New-Object System.Windows.Forms.CheckBox
    $cSources.Text = 'Avec les sources en ligne (demande Internet)'
    $cSources.Location = New-Object System.Drawing.Point(16, 100)
    $cSources.Size = New-Object System.Drawing.Size(500, 26)
    $bOk = New-BoutonJed 'Vérifier' 196 160 160
    $bOk.DialogResult = 'OK'
    $bNon = New-BoutonJed 'Annuler' 366 160 160
    $bNon.DialogResult = 'Cancel'
    $f.AcceptButton = $bOk
    $f.CancelButton = $bNon
    $f.Controls.AddRange(@($l, $cTests, $cSources, $bOk, $bNon))
    if ($f.ShowDialog() -ne 'OK') { return }
    $script = Get-ScriptVerificationJed $i $Racine
    $arguments = New-ArgumentsVerificationJed -Script $script -Dossier $i.Dossier -AvecTests:$cTests.Checked -AvecSources:$cSources.Checked
    [void](Start-OperationJed "Vérifier « $($i.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        & $surEtape 'Vérification en cours…'
        $r = Invoke-ScriptJed -Arguments $arguments -SurLigne $surLigne -SurAttente $surAttente -Dossier $i.Dossier
        $m = Get-MessageVerificationJed $r.Code
        $res = New-ResultatJed $m.Niveau $m.Titre $m.Texte $null (Get-RapportVerificationJed $r.Lignes)
        if ($r.Code -ne 0) { $res = Add-ExplicationJed $res $r.Lignes }
        return $res
    })
}

# --- Mise à jour ---------------------------------------------------------------------------------------

function Show-MiseAJourJed {
    $i = Get-ChoixJed
    if (-not $i) { return }
    if ($i.Etat -ne 'en marche') {
        if (-not (Confirm-ChoixJed "« $($i.Nom) » est arrêtée. Elle doit être en marche pour que sa sauvegarde soit faite avant la mise à jour.`n`nLa démarrer maintenant ?")) { return }
        $r = Start-ActionDockerJed $i 'Demarrer' 'Démarrer' 'J-ed démarre.'
        if ($r.Niveau -ne 'ok') { return }
    }
    $f = New-FenetreJed "Mettre à jour « $($i.Nom) » (version $($i.Version))" 760 590
    $f.Controls.Add((New-EtiquetteJed "Installation : $($i.Dossier)" 16 14 720 24))
    $f.Controls.Add((New-EtiquetteJed 'Archive de la nouvelle version (.zip) :' 16 50 720 22))
    $tArchive = New-Object System.Windows.Forms.TextBox
    $tArchive.Location = New-Object System.Drawing.Point(16, 74); $tArchive.Size = New-Object System.Drawing.Size(560, 26)
    $bArchive = New-BoutonJed 'Choisir…' 586 72 140 30
    $bGitHub = New-BoutonJed 'Télécharger la dernière version (GitHub)' 16 106 330 32
    $infoGitHub = New-EtiquetteJed '' 356 110 370 44
    $f.Controls.Add((New-EtiquetteJed 'Empreinte de l''archive (.sha256), téléchargée avec elle :' 16 158 720 22))
    $tEmpreinte = New-Object System.Windows.Forms.TextBox
    $tEmpreinte.Location = New-Object System.Drawing.Point(16, 182); $tEmpreinte.Size = New-Object System.Drawing.Size(560, 26)
    $bEmpreinte = New-BoutonJed 'Choisir…' 586 180 140 30
    $f.Controls.Add((New-EtiquetteJed 'Dossier des sauvegardes (une sauvegarde vérifiée y est copiée avant la mise à jour) :' 16 218 720 22))
    $tSauv = New-Object System.Windows.Forms.TextBox
    $tSauv.Location = New-Object System.Drawing.Point(16, 242); $tSauv.Size = New-Object System.Drawing.Size(560, 26)
    $tSauv.Text = $i.DossierSauvegardes
    if (-not $tSauv.Text) { $tSauv.Text = [System.IO.Path]::Combine((Split-Path -Parent $i.Dossier), 'sauvegardes') }
    $bSauv = New-BoutonJed 'Choisir…' 586 240 140 30
    $cProxy = New-Object System.Windows.Forms.CheckBox
    $cProxy.Text = 'Mon réseau passe par un proxy : utiliser celui de Windows'
    $cProxy.Location = New-Object System.Drawing.Point(16, 282); $cProxy.Size = New-Object System.Drawing.Size(500, 26)
    $tProxy = New-Object System.Windows.Forms.TextBox
    $tProxy.Location = New-Object System.Drawing.Point(36, 312); $tProxy.Size = New-Object System.Drawing.Size(320, 26)
    $bInternet = New-BoutonJed 'Docker joint-il Internet ?' 366 310 220 30
    $proxyDetecte = Get-ProxySystemeJed
    if ($proxyDetecte) { $cProxy.Checked = $true; $tProxy.Text = $proxyDetecte }
    $tProxy.Enabled = $cProxy.Checked
    $cProxy.Add_CheckedChanged({ $tProxy.Enabled = $cProxy.Checked })
    $controle = New-EtiquetteJed 'Choisissez l''archive, ou téléchargez la dernière version.' 16 352 710 48
    $bLancer = New-BoutonJed 'Lancer la mise à jour' 376 500 200
    $bLancer.Enabled = $false
    $bLancer.DialogResult = 'OK'
    $bAnnuler = New-BoutonJed 'Annuler' 586 500 140
    $bAnnuler.DialogResult = 'Cancel'
    $f.CancelButton = $bAnnuler
    $f.Controls.AddRange(@($tArchive, $bArchive, $bGitHub, $infoGitHub, $tEmpreinte, $bEmpreinte, $tSauv, $bSauv,
        $cProxy, $tProxy, $bInternet, $controle, $bLancer, $bAnnuler))
    $verifier = {
        $bLancer.Enabled = $false
        if (-not $tArchive.Text) { return }
        $f.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        $e = Test-EmpreinteJed -Archive $tArchive.Text -Empreinte $tEmpreinte.Text
        $v = $null
        if ($e.Ok) { try { $v = Get-VersionArchiveJed $tArchive.Text } catch { } }
        $f.Cursor = [System.Windows.Forms.Cursors]::Default
        if (-not $e.Ok) {
            $controle.Text = $e.Raison; $controle.ForeColor = $script:Couleurs['erreur']
        } elseif (-not $v) {
            $controle.Text = "Ce n'est pas une archive de J-ed (fichier VERSION absent)."; $controle.ForeColor = $script:Couleurs['erreur']
        } else {
            $controle.Text = "Archive de la version $v : empreinte conforme. Prêt à lancer."
            $controle.ForeColor = $script:Couleurs['ok']
            $bLancer.Enabled = $true
        }
    }
    $bArchive.Add_Click({
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Filter = 'Archive de J-ed (*.zip)|*.zip'
        $d.Title = 'Archive de la nouvelle version'
        if ($d.ShowDialog() -eq 'OK') {
            $tArchive.Text = $d.FileName
            $trouvee = Find-FichierEmpreinteJed $d.FileName
            if ($trouvee) { $tEmpreinte.Text = $trouvee } else { $tEmpreinte.Text = '' }
            & $verifier
        }
    })
    $bEmpreinte.Add_Click({
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Filter = 'Empreinte (*.sha256)|*.sha256|Tous les fichiers (*.*)|*.*'
        $d.Title = 'Empreinte de l''archive'
        if ($d.ShowDialog() -eq 'OK') { $tEmpreinte.Text = $d.FileName; & $verifier }
    })
    $bSauv.Add_Click({
        $d = New-Object System.Windows.Forms.FolderBrowserDialog
        $d.Description = 'Dossier des sauvegardes'
        if ($d.ShowDialog() -eq 'OK') { $tSauv.Text = $d.SelectedPath }
    })
    $bGitHub.Add_Click({
        $f.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        $info = Get-DerniereVersionGitHubJed
        $f.Cursor = [System.Windows.Forms.Cursors]::Default
        if (-not $info.Ok) { $infoGitHub.Text = $info.Raison; $infoGitHub.ForeColor = $script:Couleurs['erreur']; return }
        $date = $info.Date
        try { $date = ([datetime]$info.Date).ToString('d MMMM yyyy', [System.Globalization.CultureInfo]::GetCultureInfo('fr-FR')) } catch { }
        if ((Compare-VersionJed $info.Version $i.Version) -le 0) {
            $infoGitHub.Text = "Dernière version publiée : $($info.Version) ($date). Votre installation est déjà à jour."
            $infoGitHub.ForeColor = $script:Couleurs['ok']
            return
        }
        $taille = Format-NombreJed ($info.Archive.Taille / 1MB)
        $dossier = Get-DossierTelechargementsJed
        if (-not (Confirm-ChoixJed "Télécharger J-ed $($info.Version), publiée le $date ($taille Mo), dans $dossier ?")) { return }
        $f.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        $infoGitHub.Text = 'Téléchargement…'
        [System.Windows.Forms.Application]::DoEvents()
        $t = Save-DerniereVersionJed $info $dossier
        $f.Cursor = [System.Windows.Forms.Cursors]::Default
        if (-not $t.Archive -or -not (Test-Path -LiteralPath $t.Archive)) { $infoGitHub.Text = $t.Raison; $infoGitHub.ForeColor = $script:Couleurs['erreur']; return }
        $infoGitHub.Text = "Version $($info.Version) téléchargée."
        $infoGitHub.ForeColor = $script:Couleurs['ok']
        $tArchive.Text = $t.Archive
        $tEmpreinte.Text = $t.Empreinte
        & $verifier
    })
    $bInternet.Add_Click({
        [void](Start-OperationJed 'Docker joint-il Internet ?' {
            param($surLigne, $surAttente, $surEtape)
            & $surEtape 'Téléchargement de l''image de base de J-ed (python:3.12-slim-bookworm)…'
            $d = Invoke-DockerJed $i.Dossier (Get-CommandeAccesRegistreJed) -SurAttente $surAttente -SurLigne $surLigne
            if ($d.Code -eq 0) { return New-ResultatJed 'ok' 'Docker joint Internet' 'La construction de la nouvelle version pourra télécharger ce dont elle a besoin.' $null $null }
            $res = New-ResultatJed 'erreur' 'Docker ne joint pas Internet' (Get-ConseilProxyDockerJed $tProxy.Text) $null $null
            return $res
        })
    })
    if ($f.ShowDialog() -ne 'OK') { return }
    if ($cProxy.Checked) {
        $tp = Test-AdresseProxyJed $tProxy.Text
        if (-not $tp.Ok) { Show-ErreurJed "Proxy : $($tp.Raison)"; return }
        if (-not (Confirm-ChoixJed "Le proxy $($tProxy.Text) va être écrit dans le fichier .env de « $($i.Nom) » (une copie de l'ancien fichier est gardée à côté). La nouvelle version le reprendra.`n`nContinuer ?")) { return }
        Set-ProxyEnvJed -Fichier ([System.IO.Path]::Combine($i.Dossier, '.env')) -Proxy $tProxy.Text
    }

    if ($i.Protegee -and -not (Confirm-ChoixJed "« $($i.Nom) » est une installation protégée (sans doute votre installation principale).`n`nConseil : essayez d'abord la mise à jour sur une copie. Continuer quand même ?")) { return }

    $archive = $tArchive.Text
    $empreinte = $tEmpreinte.Text
    $sauvegardes = $tSauv.Text
    $temp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), 'J-ed', "mise-a-jour-$(Get-Date -Format 'yyyyMMdd-HHmmss')")
    $scriptMaj = Export-ScriptArchiveJed -Archive $archive -Dossier $temp
    if (-not $scriptMaj) {
        Show-ErreurJed "mettre-a-jour.ps1 est absent de l'archive : ce n'est pas une archive de J-ed 2.0 ou plus récente."
        return
    }
    $arguments = New-ArgumentsMiseAJourJed -Script $scriptMaj -Archive $archive -Actuel $i.Dossier -DossierSauvegardes $sauvegardes -Empreinte $empreinte
    $r = Start-OperationJed "Mettre à jour « $($i.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        $ligneEtEtape = { param($l) & $surLigne $l; if ($l -match '^== (.+)$') { & $surEtape $Matches[1] } }
        $question = {
            param($q)
            Confirm-ChoixJed ("La nouvelle version est prête.`n`nL'ancienne version va maintenant être arrêtée, puis la nouvelle démarrée. " +
                "Aucune donnée n'est effacée ; si la nouvelle version ne démarre pas, l'assistant revient tout seul à l'ancienne.`n`nContinuer ?") 'Confirmation'
        }
        $x = Invoke-ScriptJed -Arguments $arguments -SurLigne $ligneEtEtape -SurAttente $surAttente -SurQuestion $question
        $m = Get-MessageMiseAJourJed $x.Code
        $res = New-ResultatJed $m.Niveau $m.Titre $m.Texte $x.Journal $null
        if ($x.Code -in @(1, 3, 5)) { $res = Add-ExplicationJed $res $x.Lignes }
        return $res
    }
    Update-ListeJed
    if ($r -and $r.Niveau -eq 'ok' -and (Confirm-ChoixJed 'Mise à jour réussie. Mettre à jour les raccourcis « J-ed » du Bureau et du menu Démarrer ?')) {
        $nouvelle = $script:Installations | Where-Object { $_.Nom -eq $i.Nom -and $_.Version -ne $i.Version } | Select-Object -First 1
        if ($nouvelle) { [void](New-RaccourcisJed $nouvelle $nouvelle.Dossier) }
    }
}

# --- Nouvelle installation -------------------------------------------------------------------------------

function New-ZoneTexteJed([int]$X, [int]$Y, [int]$Largeur = 560) {
    $t = New-Object System.Windows.Forms.TextBox
    $t.Location = New-Object System.Drawing.Point($X, $Y)
    $t.Size = New-Object System.Drawing.Size($Largeur, 26)
    return $t
}

function Get-NomLibreJed([string]$Base) {
    $volumes = Get-VolumesDockerJed
    if ((Test-NomProjetJed $Base $script:Installations $volumes).Ok) { return $Base }
    for ($n = 2; $n -lt 100; $n++) {
        if ((Test-NomProjetJed "$Base-$n" $script:Installations $volumes).Ok) { return "$Base-$n" }
    }
    return ''
}

function Show-FinInstallationJed($Installation) {
    # Fin guidée (fonction pour un pur débutant) : compte administrateur, raccourcis, jeu d'essai.
    $f = New-FenetreJed "« $($Installation.Nom) » est installée" 640 360
    $f.Controls.Add((New-EtiquetteJed ("J-ed répond à l'adresse $(Get-AdresseJed $Installation)`n`n" +
        "1. Créez le compte administrateur (une seule fois).`n2. Si vous voulez, créez les raccourcis et chargez le jeu d'essai " +
        "pour découvrir J-ed avec des notices fictives (après l'étape 1).") 16 14 600 110))
    $bCompte = New-BoutonJed '1. Créer le compte administrateur' 16 132 600 36
    $bRaccourcis = New-BoutonJed 'Créer les raccourcis (Bureau, menu Démarrer)' 16 176 600 36
    $bEssai = New-BoutonJed 'Charger le jeu d''essai (notices fictives)' 16 220 600 36
    $bFermer = New-BoutonJed 'Fermer' 446 272 170
    $bCompte.Add_Click({ Start-Process (Get-AdressePremierDemarrageJed $Installation) })
    $bRaccourcis.Add_Click({
        $faits = New-RaccourcisJed $Installation $Installation.Dossier
        Show-InfoJed ("Raccourcis créés :`n" + ($faits -join "`n"))
    })
    $bEssai.Add_Click({
        [void](Start-OperationJed 'Charger le jeu d''essai' {
            param($surLigne, $surAttente, $surEtape)
            & $surEtape 'Chargement des notices fictives…'
            $d = Invoke-DockerJed $Installation.Dossier @('compose', 'exec', '-T', 'web', 'python', 'manage.py', 'jeu_essai', '--charger') -SurAttente $surAttente -SurLigne $surLigne
            if ($d.Code -eq 0) { return New-ResultatJed 'ok' 'Jeu d''essai chargé' 'Ouvrez J-ed : l''aide « Essayer J-ed » guide la découverte.' $null $null }
            return New-ResultatJed 'attention' 'Jeu d''essai non chargé' 'Créez d''abord le compte administrateur (étape 1), puis recommencez.' $null $null
        })
    })
    $bFermer.Add_Click({ $f.Close() })
    $f.Controls.AddRange(@($bCompte, $bRaccourcis, $bEssai, $bFermer))
    [void]$f.ShowDialog()
}

function Show-NouvelleInstallationJed {
    <# Nouvelle installation, aussi à côté d'installations existantes (deuxième instance, autre port). Renvoie la
       nouvelle installation, ou $null. -PourRestauration : pas de fin guidée (la sauvegarde apporte les comptes). #>
    param([string]$NomPropose = 'jed', [switch]$PourRestauration)
    $titre = 'Nouvelle installation'
    if ($PourRestauration) { $titre = 'Nouvelle installation pour y restaurer la sauvegarde' }
    $f = New-FenetreJed $titre 760 700
    $volumes = Get-VolumesDockerJed
    $f.Controls.Add((New-EtiquetteJed 'Archive de J-ed (.zip) :' 16 12 720 22))
    $tArchive = New-ZoneTexteJed 16 36
    $bArchive = New-BoutonJed 'Choisir…' 586 34 140 30
    $bGitHub = New-BoutonJed 'Télécharger la dernière version (GitHub)' 16 68 330 32
    $infoGitHub = New-EtiquetteJed '' 356 72 370 44
    $f.Controls.Add((New-EtiquetteJed 'Empreinte de l''archive (.sha256) :' 16 118 720 22))
    $tEmpreinte = New-ZoneTexteJed 16 142
    $bEmpreinte = New-BoutonJed 'Choisir…' 586 140 140 30
    $f.Controls.Add((New-EtiquetteJed 'Nom de l''installation (lettres minuscules, chiffres, tirets) :' 16 180 470 22))
    $tNom = New-ZoneTexteJed 16 204 300
    $tNom.Text = Get-NomLibreJed $NomPropose
    $f.Controls.Add((New-EtiquetteJed 'Port :' 340 180 100 22))
    $tPort = New-ZoneTexteJed 340 204 100
    $tPort.Text = "$(Get-PortLibreJed $script:Installations)"
    $infoNom = New-EtiquetteJed '' 456 196 280 44
    $f.Controls.Add((New-EtiquetteJed 'Emplacement (un dossier neuf) :' 16 244 720 22))
    $tDossier = New-ZoneTexteJed 16 268
    $bDossier = New-BoutonJed 'Choisir l''emplacement…' 586 266 140 30
    $f.Controls.Add((New-EtiquetteJed 'Dossier des sauvegardes de cette installation :' 16 306 720 22))
    $tSauv = New-ZoneTexteJed 16 330
    $bSauv = New-BoutonJed 'Choisir…' 586 328 140 30
    $cArgos = New-Object System.Windows.Forms.CheckBox
    $cArgos.Text = 'Traduction hors ligne Argos (conseillée ; environ 2 Go de plus)'
    $cArgos.Location = New-Object System.Drawing.Point(16, 368); $cArgos.Size = New-Object System.Drawing.Size(700, 26)
    $cArgos.Checked = $true
    $cProxy = New-Object System.Windows.Forms.CheckBox
    $cProxy.Text = 'Mon réseau passe par un proxy : utiliser celui de Windows'
    $cProxy.Location = New-Object System.Drawing.Point(16, 398); $cProxy.Size = New-Object System.Drawing.Size(500, 26)
    $tProxy = New-ZoneTexteJed 36 428 320
    $proxyDetecte = Get-ProxySystemeJed
    if ($proxyDetecte) { $cProxy.Checked = $true; $tProxy.Text = $proxyDetecte }
    $tProxy.Enabled = $cProxy.Checked
    $cProxy.Add_CheckedChanged({ $tProxy.Enabled = $cProxy.Checked })
    $controle = New-EtiquetteJed 'Choisissez l''archive, ou téléchargez la dernière version.' 16 468 710 66
    $bInstaller = New-BoutonJed 'Installer' 376 600 200
    $bInstaller.Enabled = $false
    $bInstaller.DialogResult = 'OK'
    $bAnnuler = New-BoutonJed 'Annuler' 586 600 140
    $bAnnuler.DialogResult = 'Cancel'
    $f.CancelButton = $bAnnuler
    $f.Controls.AddRange(@($tArchive, $bArchive, $bGitHub, $infoGitHub, $tEmpreinte, $bEmpreinte, $tNom, $tPort, $infoNom,
        $tDossier, $bDossier, $tSauv, $bSauv, $cArgos, $cProxy, $tProxy, $controle, $bInstaller, $bAnnuler))
    $etat = @{ Version = ''; ArchiveOk = $false; DossierChoisi = $false; Parent = '' }

    $proposer = {
        # Emplacement et dossier des sauvegardes proposés d'après le nom et la version (sauf choix de l'utilisateur).
        if (-not $etat.DossierChoisi) { $tDossier.Text = Get-EmplacementParDefautJed $script:Installations $tNom.Text $etat.Version }
        elseif ($etat.Parent) { $tDossier.Text = [System.IO.Path]::Combine($etat.Parent, "$($tNom.Text)-$($etat.Version)") }
        $parent = Split-Path -Parent $tDossier.Text
        $tSauv.Text = [System.IO.Path]::Combine($parent, "sauvegardes-$($tNom.Text)")
    }
    $valider = {
        $bInstaller.Enabled = $false
        $n = Test-NomProjetJed $tNom.Text $script:Installations $volumes
        $port = 0
        [void][int]::TryParse($tPort.Text, [ref]$port)
        $p = Test-PortJed $port $script:Installations
        if (-not $n.Ok) { $infoNom.Text = $n.Raison; $infoNom.ForeColor = $script:Couleurs['erreur'] }
        elseif (-not $p.Ok) { $infoNom.Text = $p.Raison; $infoNom.ForeColor = $script:Couleurs['erreur'] }
        else { $infoNom.Text = 'Nom et port libres.'; $infoNom.ForeColor = $script:Couleurs['ok'] }
        $dossierOk = $tDossier.Text -and -not (Test-Path -LiteralPath $tDossier.Text)
        if (-not $dossierOk -and $tDossier.Text) { $controle.Text = "Le dossier $($tDossier.Text) existe déjà : choisissez un autre nom ou un autre emplacement."; $controle.ForeColor = $script:Couleurs['erreur'] }
        $bInstaller.Enabled = ($etat.ArchiveOk -and $n.Ok -and $p.Ok -and $dossierOk)
    }
    $verifierArchive = {
        $etat.ArchiveOk = $false
        if ($tArchive.Text) {
            $f.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
            $e = Test-EmpreinteJed -Archive $tArchive.Text -Empreinte $tEmpreinte.Text
            $v = $null
            if ($e.Ok) { try { $v = Get-VersionArchiveJed $tArchive.Text } catch { } }
            $f.Cursor = [System.Windows.Forms.Cursors]::Default
            if (-not $e.Ok) { $controle.Text = $e.Raison; $controle.ForeColor = $script:Couleurs['erreur'] }
            elseif (-not $v) { $controle.Text = "Ce n'est pas une archive de J-ed (fichier VERSION absent)."; $controle.ForeColor = $script:Couleurs['erreur'] }
            else {
                $etat.Version = $v
                $etat.ArchiveOk = $true
                $controle.Text = "Archive de la version $v : empreinte conforme."
                $controle.ForeColor = $script:Couleurs['ok']
                & $proposer
            }
        }
        & $valider
    }
    $tNom.Add_TextChanged({ & $proposer; & $valider })
    $tPort.Add_TextChanged({ & $valider })
    $bArchive.Add_Click({
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Filter = 'Archive de J-ed (*.zip)|*.zip'
        if ($d.ShowDialog() -eq 'OK') {
            $tArchive.Text = $d.FileName
            $trouvee = Find-FichierEmpreinteJed $d.FileName
            if ($trouvee) { $tEmpreinte.Text = $trouvee } else { $tEmpreinte.Text = '' }
            & $verifierArchive
        }
    })
    $bEmpreinte.Add_Click({
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Filter = 'Empreinte (*.sha256)|*.sha256|Tous les fichiers (*.*)|*.*'
        if ($d.ShowDialog() -eq 'OK') { $tEmpreinte.Text = $d.FileName; & $verifierArchive }
    })
    $bGitHub.Add_Click({
        $f.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        $info = Get-DerniereVersionGitHubJed
        $f.Cursor = [System.Windows.Forms.Cursors]::Default
        if (-not $info.Ok) { $infoGitHub.Text = $info.Raison; $infoGitHub.ForeColor = $script:Couleurs['erreur']; return }
        $taille = Format-NombreJed ($info.Archive.Taille / 1MB)
        $dossier = Get-DossierTelechargementsJed
        if (-not (Confirm-ChoixJed "Télécharger J-ed $($info.Version) ($taille Mo) dans $dossier ?")) { return }
        $f.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        $infoGitHub.Text = 'Téléchargement…'
        [System.Windows.Forms.Application]::DoEvents()
        $t = Save-DerniereVersionJed $info $dossier
        $f.Cursor = [System.Windows.Forms.Cursors]::Default
        if (-not $t.Archive -or -not (Test-Path -LiteralPath $t.Archive)) { $infoGitHub.Text = $t.Raison; $infoGitHub.ForeColor = $script:Couleurs['erreur']; return }
        $infoGitHub.Text = "Version $($info.Version) téléchargée."
        $infoGitHub.ForeColor = $script:Couleurs['ok']
        $tArchive.Text = $t.Archive
        $tEmpreinte.Text = $t.Empreinte
        & $verifierArchive
    })
    $bDossier.Add_Click({
        $d = New-Object System.Windows.Forms.FolderBrowserDialog
        $d.Description = 'Dossier dans lequel créer l''installation (un sous-dossier « nom-version » y sera créé)'
        if ($d.ShowDialog() -eq 'OK') { $etat.DossierChoisi = $true; $etat.Parent = $d.SelectedPath; & $proposer; & $valider }
    })
    $bSauv.Add_Click({
        $d = New-Object System.Windows.Forms.FolderBrowserDialog
        $d.Description = 'Dossier des sauvegardes de cette installation'
        if ($d.ShowDialog() -eq 'OK') { $tSauv.Text = $d.SelectedPath }
    })
    $f.Add_Shown({ & $proposer; & $valider })
    if ($f.ShowDialog() -ne 'OK') { return $null }

    $proxy = ''
    if ($cProxy.Checked) {
        $tp = Test-AdresseProxyJed $tProxy.Text
        if (-not $tp.Ok) { Show-ErreurJed "Proxy : $($tp.Raison)"; return $null }
        $proxy = $tProxy.Text
    }
    # Le script de l'archive s'il existe (2.0.2 et suivantes), sinon celui de l'assistant.
    $temp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), 'J-ed', "installation-$(Get-Date -Format 'yyyyMMdd-HHmmss')")
    $scriptInst = Export-ScriptArchiveJed -Archive $tArchive.Text -Nom 'installer-j-ed.ps1' -Dossier $temp
    if (-not $scriptInst) { $scriptInst = [System.IO.Path]::Combine($Racine, 'installer-j-ed.ps1') }
    $port = [int]$tPort.Text
    $arguments = New-ArgumentsInstallationJed -Script $scriptInst -Archive $tArchive.Text -Empreinte $tEmpreinte.Text `
        -Destination $tDossier.Text -Nom $tNom.Text -Port $port -DossierSauvegardes $tSauv.Text -Proxy $proxy -SansArgos:(-not $cArgos.Checked)
    $destination = $tDossier.Text
    $r = Start-OperationJed "Installer « $($tNom.Text) »" {
        param($surLigne, $surAttente, $surEtape)
        $ligneEtEtape = { param($l) & $surLigne $l; if ($l -match '^== (.+)$') { & $surEtape $Matches[1] } }
        $x = Invoke-ScriptJed -Arguments $arguments -SurLigne $ligneEtEtape -SurAttente $surAttente
        $m = Get-MessageInstallationJed $x.Code
        $res = New-ResultatJed $m.Niveau $m.Titre $m.Texte $x.Journal $null
        if ($x.Code -in @(1, 3, 5)) { $res = Add-ExplicationJed $res $x.Lignes }
        return $res
    }
    if (-not $r -or $r.Niveau -ne 'ok') { return $null }
    Add-InstallationListeJed -Fichier $script:Liste -Dossier $destination
    Update-ListeJed
    $nouvelle = Get-InstallationJed $destination
    $nouvelle.Etat = 'en marche'
    if (-not $PourRestauration) { Show-FinInstallationJed $nouvelle }
    return $nouvelle
}

# --- Opérations de maintenance --------------------------------------------------------------------------

function Read-ConfirmationJed([string]$Texte, [string]$Mot, [string]$Titre = 'Confirmation') {
    # Confirmation forte : il faut taper le mot demandé (RESTAURER, REINITIALISER).
    $f = New-FenetreJed $Titre 620 330
    $f.Controls.Add((New-EtiquetteJed $Texte 16 14 580 150))
    $f.Controls.Add((New-EtiquetteJed "Pour confirmer, tapez $Mot :" 16 172 580 24))
    $t = New-ZoneTexteJed 16 198 300
    $bOk = New-BoutonJed 'Confirmer' 266 240 160
    $bOk.Enabled = $false
    $bOk.DialogResult = 'OK'
    $bNon = New-BoutonJed 'Annuler' 436 240 160
    $bNon.DialogResult = 'Cancel'
    $f.CancelButton = $bNon
    $t.Add_TextChanged({ $bOk.Enabled = ($t.Text -ceq $Mot) })
    $f.Controls.AddRange(@($t, $bOk, $bNon))
    return ($f.ShowDialog() -eq 'OK' -and $t.Text -ceq $Mot)
}

function Show-RestaurationJed {
    $choisie = $null
    if ($script:ListeVue.SelectedItems.Count -gt 0) { $choisie = $script:ListeVue.SelectedItems[0].Tag }
    $d = New-Object System.Windows.Forms.OpenFileDialog
    $d.Filter = 'Sauvegarde de J-ed (*.tar)|*.tar'
    $d.Title = 'Sauvegarde à restaurer'
    if ($choisie -and $choisie.DossierSauvegardes -and (Test-Path -LiteralPath $choisie.DossierSauvegardes)) { $d.InitialDirectory = $choisie.DossierSauvegardes }
    if ($d.ShowDialog() -ne 'OK') { return }
    $fichier = $d.FileName

    $f = New-FenetreJed 'Restaurer une sauvegarde' 680 380
    $f.Controls.Add((New-EtiquetteJed "Sauvegarde : $fichier" 16 14 640 44))
    $rNouvelle = New-Object System.Windows.Forms.RadioButton
    $rNouvelle.Text = 'Dans une nouvelle installation (conseillé : rien d''existant n''est touché)'
    $rNouvelle.Location = New-Object System.Drawing.Point(16, 66); $rNouvelle.Size = New-Object System.Drawing.Size(640, 26)
    $rNouvelle.Checked = $true
    $rExistante = New-Object System.Windows.Forms.RadioButton
    $rExistante.Location = New-Object System.Drawing.Point(16, 96); $rExistante.Size = New-Object System.Drawing.Size(640, 26)
    if ($choisie -and $choisie.Valide) {
        $rExistante.Text = "Dans « $($choisie.Nom) » : sa base actuelle sera REMPLACÉE (sauvegarde de sécurité faite avant)"
    } else {
        $rExistante.Text = 'Dans une installation existante (choisissez-la d''abord dans la liste)'
        $rExistante.Enabled = $false
    }
    $note = New-EtiquetteJed ("Bon à savoir : dans une nouvelle installation, les clés d'API des IA enregistrées dans la sauvegarde ne sont pas " +
        "lisibles (elles restent chiffrées avec la clé de l'installation d'origine) : il faudra les saisir à nouveau. " +
        "Une sauvegarde d'une version plus ancienne est mise à niveau au redémarrage.") 16 132 640 90
    $bOk = New-BoutonJed 'Continuer' 316 280 160
    $bOk.DialogResult = 'OK'
    $bNon = New-BoutonJed 'Annuler' 496 280 160
    $bNon.DialogResult = 'Cancel'
    $f.CancelButton = $bNon
    $f.Controls.AddRange(@($rNouvelle, $rExistante, $note, $bOk, $bNon))
    if ($f.ShowDialog() -ne 'OK') { return }

    if ($rNouvelle.Checked) {
        $base = 'jed'
        if ($choisie -and $choisie.Nom) { $base = "$($choisie.Nom)-copie" }
        $cible = Show-NouvelleInstallationJed -NomPropose $base -PourRestauration
        if (-not $cible) { return }
    } else {
        $cible = $choisie
        if ($cible.Etat -ne 'en marche') { Show-InfoJed "« $($cible.Nom) » est arrêtée : démarrez-la d'abord."; return }
        $texte = "La base actuelle de « $($cible.Nom) » va être remplacée par celle de la sauvegarde. J-ed fait d'abord une sauvegarde de sécurité de l'état actuel."
        if ($cible.Protegee) { $texte = "ATTENTION : « $($cible.Nom) » est une installation protégée (sans doute votre installation principale).`n`n" + $texte + "`n`nConseil : restaurez plutôt dans une nouvelle installation." }
        if (-not (Read-ConfirmationJed $texte 'RESTAURER' 'Restaurer une sauvegarde')) { return }
    }
    [void](Start-OperationJed "Restaurer dans « $($cible.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        & $surEtape 'Restauration en cours (une à quelques minutes)…'
        $x = Invoke-RestaurationJed $cible $fichier -SurAttente $surAttente -SurLigne $surLigne
        if ($x.Ok) { return New-ResultatJed 'ok' 'Sauvegarde restaurée' $x.Message $null $null }
        return Add-ExplicationJed (New-ResultatJed 'erreur' 'Restauration impossible' $x.Message $null $null) @($x.Message)
    })
    Update-ListeJed
}

function Show-MotDePasseJed {
    $i = Get-ChoixJed
    if (-not $i) { return }
    if ($i.Etat -ne 'en marche') { Show-InfoJed "« $($i.Nom) » est arrêtée : démarrez-la d'abord."; return }
    $script:Fenetre.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
    $c = Get-ComptesJed $i
    $script:Fenetre.Cursor = [System.Windows.Forms.Cursors]::Default
    if (-not $c.Ok) { Show-ErreurJed $c.Raison; return }
    if ($c.Comptes.Count -eq 0) { Show-InfoJed "Aucun compte : ouvrez $(Get-AdressePremierDemarrageJed $i) pour créer le compte administrateur."; return }
    $f = New-FenetreJed "Mot de passe oublié — « $($i.Nom) »" 600 380
    $f.Controls.Add((New-EtiquetteJed 'Compte :' 16 16 560 22))
    $liste = New-Object System.Windows.Forms.ComboBox
    $liste.DropDownStyle = 'DropDownList'
    $liste.Location = New-Object System.Drawing.Point(16, 40); $liste.Size = New-Object System.Drawing.Size(560, 26)
    foreach ($compte in $c.Comptes) {
        $libelle = "$($compte.identifiant)"
        if ($compte.nom) { $libelle += " — $($compte.nom)" }
        $libelle += " ($($compte.role))"
        [void]$liste.Items.Add($libelle)
    }
    $liste.SelectedIndex = 0
    $f.Controls.Add((New-EtiquetteJed 'Nouveau mot de passe (10 caractères au moins, pas trop simple) :' 16 80 560 22))
    $t1 = New-ZoneTexteJed 16 104 360
    $t1.UseSystemPasswordChar = $true
    $f.Controls.Add((New-EtiquetteJed 'Le même, une seconde fois :' 16 140 560 22))
    $t2 = New-ZoneTexteJed 16 164 360
    $t2.UseSystemPasswordChar = $true
    $info = New-EtiquetteJed 'Le mot de passe n''est écrit nulle part : ni dans un fichier, ni dans un journal.' 16 204 560 44
    $bOk = New-BoutonJed 'Changer le mot de passe' 196 280 220
    $bOk.DialogResult = 'OK'
    $bNon = New-BoutonJed 'Annuler' 426 280 150
    $bNon.DialogResult = 'Cancel'
    $f.CancelButton = $bNon
    $f.Controls.AddRange(@($liste, $t1, $t2, $info, $bOk, $bNon))
    if ($f.ShowDialog() -ne 'OK') { return }
    if ($t1.Text -cne $t2.Text) { Show-ErreurJed 'Les deux saisies sont différentes : rien n''a changé.'; return }
    $compte = $c.Comptes[$liste.SelectedIndex].identifiant
    $mot = $t1.Text
    $t1.Text = ''; $t2.Text = ''
    $script:Fenetre.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
    $x = Set-MotDePasseJed $i $compte $mot -SurAttente { [System.Windows.Forms.Application]::DoEvents() }
    $mot = $null
    $script:Fenetre.Cursor = [System.Windows.Forms.Cursors]::Default
    if ($x.Ok) { Show-InfoJed "Mot de passe changé pour « $compte ». Si le compte était bloqué par trop d'essais, attendez 15 minutes." }
    else { Show-ErreurJed "Rien n'a changé.`n`n$($x.Message)" }
}

function Start-VerificationMigrationJed {
    $i = Get-ChoixJed
    if (-not $i) { return }
    $script = Get-ScriptInstallationJed $i 'verifier-migration.ps1' $Racine
    $arguments = New-ArgumentsMigrationJed $script $i.Dossier
    [void](Start-OperationJed "Vérifier la migration de « $($i.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        & $surEtape 'Vérification de la migration…'
        $x = Invoke-ScriptJed -Arguments $arguments -SurLigne $surLigne -SurAttente $surAttente -Dossier $i.Dossier
        $m = Get-MessageVerificationJed $x.Code
        return New-ResultatJed $m.Niveau $m.Titre $m.Texte $null $null
    })
}

function Start-ReinitialisationJed {
    $i = Get-ChoixJed
    if (-not $i) { return }
    if (-not $i.Essai) { Show-InfoJed "« $($i.Nom) » n'est pas une installation d'essai (son nom ne contient pas « essai ») : la réinitialisation est réservée aux essais."; return }
    $script = [System.IO.Path]::Combine($i.Dossier, 'reinitialiser-essai.ps1')
    if (-not (Test-Path -LiteralPath $script)) { Show-ErreurJed "reinitialiser-essai.ps1 est absent du dossier de « $($i.Nom) »."; return }
    $f = New-FenetreJed "Réinitialiser l'essai « $($i.Nom) »" 640 340
    $f.Controls.Add((New-EtiquetteJed ("La réinitialisation EFFACE les données de cet essai (base, notices, journaux) puis le redémarre vide. " +
        "Le script refuse toute installation qui n'est pas un essai.") 16 14 600 66))
    $cSauver = New-Object System.Windows.Forms.CheckBox
    $cSauver.Text = 'Faire d''abord une sauvegarde de l''essai (conseillé)'
    $cSauver.Location = New-Object System.Drawing.Point(16, 90); $cSauver.Size = New-Object System.Drawing.Size(600, 26)
    $cSauver.Checked = ($i.Etat -eq 'en marche')
    $cSauver.Enabled = ($i.Etat -eq 'en marche')
    $cComplet = New-Object System.Windows.Forms.CheckBox
    $cComplet.Text = 'Réinitialisation complète (paquets de langues Argos et images aussi)'
    $cComplet.Location = New-Object System.Drawing.Point(16, 120); $cComplet.Size = New-Object System.Drawing.Size(600, 26)
    $bOk = New-BoutonJed 'Continuer' 296 240 160
    $bOk.DialogResult = 'OK'
    $bNon = New-BoutonJed 'Annuler' 466 240 150
    $bNon.DialogResult = 'Cancel'
    $f.CancelButton = $bNon
    $f.Controls.AddRange(@($cSauver, $cComplet, $bOk, $bNon))
    if ($f.ShowDialog() -ne 'OK') { return }
    if (-not (Read-ConfirmationJed "Les données de l'essai « $($i.Nom) » vont être effacées." 'REINITIALISER' 'Réinitialiser l''essai')) { return }
    $sauver = $cSauver.Checked
    $arguments = New-ArgumentsReinitialisationJed $script -Complet:$cComplet.Checked
    [void](Start-OperationJed "Réinitialiser l'essai « $($i.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        if ($sauver) {
            & $surEtape 'Sauvegarde avant effacement…'
            $s = Invoke-SauvegardeJed $i -SurAttente $surAttente -SurLigne $surLigne
            if (-not $s.Ok) { return New-ResultatJed 'erreur' 'Sauvegarde impossible : rien n''a été effacé' $s.Message $null $null }
            & $surLigne $s.Message
        }
        & $surEtape 'Réinitialisation…'
        $ligneEtEtape = { param($l) & $surLigne $l; if ($l -match '^== (.+)$') { & $surEtape $Matches[1] } }
        $x = Invoke-ScriptJed -Arguments $arguments -Dossier $i.Dossier -Entree "REINITIALISER`n" -SurLigne $ligneEtEtape -SurAttente $surAttente
        if ($x.Code -ne 0) { return Add-ExplicationJed (New-ResultatJed 'erreur' 'Réinitialisation arrêtée' 'Le message affiché dit pourquoi.' $null $null) $x.Lignes }
        if (@($x.Lignes | Where-Object { $_ -match '^Annul' }).Count -gt 0) { return New-ResultatJed 'attention' 'Annulée' 'Rien n''a été effacé.' $null $null }
        return New-ResultatJed 'ok' 'Essai réinitialisé' 'L''essai redémarre avec une base vide.' $null $null
    })
    Update-ListeJed
}

# --- Maintenance -------------------------------------------------------------------------------------

function Start-SauvegardeJed {
    $i = Get-ChoixJed
    if (-not $i) { return }
    if ($i.Etat -ne 'en marche') { Show-InfoJed "« $($i.Nom) » est arrêtée : démarrez-la d'abord."; return }
    [void](Start-OperationJed "Sauvegarder « $($i.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        & $surEtape 'Sauvegarde en cours (une à quelques minutes)…'
        & $surLigne 'Sauvegarde en cours, patientez : J-ed affiche son résultat à la fin.'
        $s = Invoke-SauvegardeJed $i -SurAttente $surAttente -SurLigne $surLigne
        if ($s.Ok) { return New-ResultatJed 'ok' 'Sauvegarde faite' $s.Message $null $s.Copie }
        return Add-ExplicationJed (New-ResultatJed 'erreur' 'Sauvegarde impossible' $s.Message $null $null) @($s.Message)
    })
    Update-ListeJed
}

function Show-MaintenanceJed {
    $f = New-FenetreJed 'Opérations de maintenance' 620 420
    $f.Controls.Add((New-EtiquetteJed 'Pour l''installation choisie dans la liste :' 16 14 570 24))
    $bSauver = New-BoutonJed 'Créer une sauvegarde' 16 46 270 36
    $bDossier = New-BoutonJed 'Dossier des sauvegardes' 296 46 290 36
    $bRestaurer = New-BoutonJed 'Restaurer une sauvegarde' 16 92 270 36
    $bMotDePasse = New-BoutonJed 'Mot de passe oublié' 296 92 290 36
    $bMigration = New-BoutonJed 'Vérifier la migration' 16 138 270 36
    $bEssai = New-BoutonJed 'Réinitialiser l''essai' 296 138 290 36
    $note = New-EtiquetteJed 'Restaurer : choisissez d''abord, dans la liste, l''installation dont vient la sauvegarde (son dossier des sauvegardes s''ouvre). Réinitialiser l''essai : seulement une installation d''essai.' 16 190 570 60
    $bRestaurer.Add_Click({ Show-RestaurationJed })
    $bMotDePasse.Add_Click({ Show-MotDePasseJed })
    $bMigration.Add_Click({ Start-VerificationMigrationJed })
    $bEssai.Add_Click({ Start-ReinitialisationJed })
    $bFermer = New-BoutonJed 'Fermer' 416 320 170
    $bFermer.Add_Click({ $f.Close() })
    $bSauver.Add_Click({ Start-SauvegardeJed })
    $bDossier.Add_Click({
        $i = Get-ChoixJed
        if (-not $i) { return }
        if (-not $i.DossierSauvegardes) {
            Show-InfoJed "Aucun dossier des sauvegardes n'est réglé pour « $($i.Nom) » (ligne DOSSIER_SAUVEGARDES du fichier .env) : ses sauvegardes restent dans Docker."
            return
        }
        Open-DossierJed $i.DossierSauvegardes
    })
    $f.Controls.AddRange(@($bSauver, $bDossier, $bRestaurer, $bMotDePasse, $bMigration, $bEssai, $note, $bFermer))
    [void]$f.ShowDialog()
}

function Start-CompteRenduJed {
    $i = $null
    if ($script:ListeVue.SelectedItems.Count -gt 0) { $i = $script:ListeVue.SelectedItems[0].Tag }
    $bureau = [Environment]::GetFolderPath('Desktop')
    [void](Start-OperationJed 'Ça ne marche pas : compte rendu' {
        param($surLigne, $surAttente, $surEtape)
        & $surEtape 'Préparation du compte rendu…'
        $zip = New-CompteRenduJed -Installation $i -Destination $bureau -VersionAssistant $script:Version -SurAttente $surAttente
        & $surLigne "Compte rendu : $zip"
        return New-ResultatJed 'ok' 'Compte rendu prêt' ("Fichier enregistré sur le Bureau : $zip`n" +
            'Il ne contient ni mot de passe, ni clé, ni adresse électronique. Envoyez-le à la personne qui vous aide.') $null $zip
    })
}

# --- Fenêtre principale ----------------------------------------------------------------------------------

function Show-AssistantJed {
    $f = New-Object System.Windows.Forms.Form
    $f.Text = "Assistant J-ed $script:Version"
    Set-TailleJed $f 1000 680
    $f.StartPosition = 'CenterScreen'
    $f.Font = $script:Police
    $f.FormBorderStyle = 'FixedSingle'
    $f.MaximizeBox = $false
    $script:Fenetre = $f

    $titre = New-EtiquetteJed 'Assistant J-ed' 20 14 600 32
    $titre.Font = $script:PoliceTitre
    $sous = New-EtiquetteJed 'Installer, mettre à jour, vérifier et sauvegarder J-ed, sans ouvrir PowerShell.' 20 48 900 24
    $bMaj = New-BoutonJed 'Mettre à jour une installation' 20 84 450 54
    $bMaj.Font = $script:PoliceGras
    $bNouvelle = New-BoutonJed 'Nouvelle installation' 510 84 450 54
    $bNouvelle.Font = $script:PoliceGras

    $groupe = New-Object System.Windows.Forms.GroupBox
    $groupe.Text = 'Vos installations'
    $groupe.Location = New-Object System.Drawing.Point(20, 152)
    $groupe.Size = New-Object System.Drawing.Size(940, 350)
    $lv = New-Object System.Windows.Forms.ListView
    $lv.View = 'Details'
    $lv.FullRowSelect = $true
    $lv.MultiSelect = $false
    $lv.HideSelection = $false
    $lv.Location = New-Object System.Drawing.Point(12, 26)
    $lv.Size = New-Object System.Drawing.Size(914, 230)
    foreach ($c in @(@('Nom', 170), @('Version', 80), @('Port', 60), @('État', 130), @('Dernière sauvegarde', 150), @('Dossier', 300))) {
        [void]$lv.Columns.Add($c[0], $c[1])
    }
    $script:ListeVue = $lv
    $bDemarrer = New-BoutonJed 'Démarrer' 12 266 140
    $bArreter = New-BoutonJed 'Arrêter' 160 266 140
    $bOuvrir = New-BoutonJed 'Ouvrir J-ed' 308 266 140
    $bVerifier = New-BoutonJed 'Vérifier' 456 266 140
    $bRaccourcis = New-BoutonJed 'Créer les raccourcis' 604 266 170
    $bAjouter = New-BoutonJed 'Ajouter une installation…' 12 306 220
    $bActualiser = New-BoutonJed 'Actualiser' 240 306 140
    $groupe.Controls.AddRange(@($lv, $bDemarrer, $bArreter, $bOuvrir, $bVerifier, $bRaccourcis, $bAjouter, $bActualiser))

    $script:EtiquettePrerequis = New-EtiquetteJed 'Prérequis : vérification…' 20 514 640 26
    $script:EtiquettePrerequis.Font = $script:PoliceGras
    $bPrerequis = New-BoutonJed 'Voir les prérequis' 680 510 280
    $bMaintenance = New-BoutonJed 'Opérations de maintenance' 20 560 300 40
    $bPanne = New-BoutonJed 'Ça ne marche pas' 340 560 300 40
    $bAide = New-BoutonJed 'Aide : Avant de commencer' 660 560 300 40
    $f.Controls.AddRange(@($titre, $sous, $bMaj, $bNouvelle, $groupe, $script:EtiquettePrerequis, $bPrerequis, $bMaintenance, $bPanne, $bAide))

    $bMaj.Add_Click({ Show-MiseAJourJed })
    $bNouvelle.Add_Click({ [void](Show-NouvelleInstallationJed) })
    $bDemarrer.Add_Click({ $i = Get-ChoixJed; if ($i) { [void](Start-ActionDockerJed $i 'Demarrer' 'Démarrer' 'J-ed démarre : il répond en général au bout d''une minute.') } })
    $bArreter.Add_Click({ $i = Get-ChoixJed; if ($i) { [void](Start-ActionDockerJed $i 'Arreter' 'Arrêter' 'J-ed est arrêté. Ses données sont intactes.') } })
    $bOuvrir.Add_Click({
        $i = Get-ChoixJed
        if (-not $i) { return }
        if ($i.Etat -ne 'en marche') { Show-InfoJed "« $($i.Nom) » est arrêtée : cliquez d'abord sur « Démarrer »."; return }
        Start-Process (Get-AdresseJed $i)
    })
    $bVerifier.Add_Click({ Start-VerificationJed })
    $bRaccourcis.Add_Click({
        $i = Get-ChoixJed
        if (-not $i) { return }
        $faits = New-RaccourcisJed $i $i.Dossier
        Show-InfoJed ("Raccourcis créés :`n" + ($faits -join "`n"))
    })
    $bAjouter.Add_Click({
        $d = New-Object System.Windows.Forms.FolderBrowserDialog
        $d.Description = 'Dossier de l''installation de J-ed (celui qui contient docker-compose.yml et .env)'
        if ($d.ShowDialog() -ne 'OK') { return }
        $i = Get-InstallationJed $d.SelectedPath
        if (-not $i.Valide) { Show-ErreurJed "Ce dossier n'est pas une installation de J-ed : $($i.Probleme)."; return }
        Add-InstallationListeJed -Fichier $script:Liste -Dossier $i.Dossier
        Update-ListeJed
    })
    $bActualiser.Add_Click({ Update-ListeJed })
    $bPrerequis.Add_Click({ Show-PrerequisJed })
    $bMaintenance.Add_Click({ Show-MaintenanceJed })
    $bPanne.Add_Click({ Start-CompteRenduJed })
    $bAide.Add_Click({ Open-AideJed '' })
    $f.Add_Shown({
        [System.Windows.Forms.Application]::DoEvents()
        $bilan = Update-BilanJed
        Update-ListeJed
        if ($bilan.Erreurs -gt 0) { Show-PrerequisJed }
    })
    [void]$f.ShowDialog()
}

try {
    Show-AssistantJed
} catch {
    Show-ErreurJed ("L'assistant J-ed a rencontré une erreur :`n`n$($_.Exception.Message)`n`n" +
        'Vous pouvez toujours utiliser les scripts en ligne de commande (aide « Mettre à jour J-ed »).')
    exit 1
}
