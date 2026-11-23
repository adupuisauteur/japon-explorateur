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

# Fichiers téléchargés : Windows les marque « venus d'Internet ». L'assistant débloque les siens seulement.
foreach ($f in @(Get-ChildItem -LiteralPath $Ici -File) + @(Get-ChildItem -LiteralPath $Racine -Filter '*.ps1' -File)) {
    try { Unblock-File -LiteralPath $f.FullName } catch { }
}
Import-Module ([System.IO.Path]::Combine($Ici, 'AssistantJed.psm1')) -Force

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

function New-FenetreJed([string]$Titre, [int]$Largeur, [int]$Hauteur) {
    $f = New-Object System.Windows.Forms.Form
    $f.Text = $Titre
    $f.Size = New-Object System.Drawing.Size($Largeur, $Hauteur)
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
    $f = New-FenetreJed 'Avant de commencer : ce qu''il faut sur cet ordinateur' 760 520
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
    $f = New-FenetreJed "Mettre à jour « $($i.Nom) » (version $($i.Version))" 760 420
    $f.Controls.Add((New-EtiquetteJed "Installation : $($i.Dossier)" 16 14 720 24))
    $f.Controls.Add((New-EtiquetteJed 'Archive de la nouvelle version (.zip) :' 16 50 720 22))
    $tArchive = New-Object System.Windows.Forms.TextBox
    $tArchive.Location = New-Object System.Drawing.Point(16, 74); $tArchive.Size = New-Object System.Drawing.Size(560, 26)
    $bArchive = New-BoutonJed 'Choisir…' 586 72 140 30
    $f.Controls.Add((New-EtiquetteJed 'Empreinte de l''archive (.sha256), téléchargée avec elle :' 16 110 720 22))
    $tEmpreinte = New-Object System.Windows.Forms.TextBox
    $tEmpreinte.Location = New-Object System.Drawing.Point(16, 134); $tEmpreinte.Size = New-Object System.Drawing.Size(560, 26)
    $bEmpreinte = New-BoutonJed 'Choisir…' 586 132 140 30
    $f.Controls.Add((New-EtiquetteJed 'Dossier des sauvegardes (une sauvegarde vérifiée y est copiée avant la mise à jour) :' 16 170 720 22))
    $tSauv = New-Object System.Windows.Forms.TextBox
    $tSauv.Location = New-Object System.Drawing.Point(16, 194); $tSauv.Size = New-Object System.Drawing.Size(560, 26)
    $tSauv.Text = $i.DossierSauvegardes
    if (-not $tSauv.Text) { $tSauv.Text = [System.IO.Path]::Combine((Split-Path -Parent $i.Dossier), 'sauvegardes') }
    $bSauv = New-BoutonJed 'Choisir…' 586 192 140 30
    $controle = New-EtiquetteJed 'Choisissez l''archive.' 16 236 710 48
    $bLancer = New-BoutonJed 'Lancer la mise à jour' 376 320 200
    $bLancer.Enabled = $false
    $bLancer.DialogResult = 'OK'
    $bAnnuler = New-BoutonJed 'Annuler' 586 320 140
    $bAnnuler.DialogResult = 'Cancel'
    $f.CancelButton = $bAnnuler
    $f.Controls.AddRange(@($tArchive, $bArchive, $tEmpreinte, $bEmpreinte, $tSauv, $bSauv, $controle, $bLancer, $bAnnuler))
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
    if ($f.ShowDialog() -ne 'OK') { return }

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

# --- Maintenance -------------------------------------------------------------------------------------

function Start-SauvegardeJed {
    $i = Get-ChoixJed
    if (-not $i) { return }
    if ($i.Etat -ne 'en marche') { Show-InfoJed "« $($i.Nom) » est arrêtée : démarrez-la d'abord."; return }
    [void](Start-OperationJed "Sauvegarder « $($i.Nom) »" {
        param($surLigne, $surAttente, $surEtape)
        & $surEtape 'Sauvegarde en cours (une à quelques minutes)…'
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
    $bDossier = New-BoutonJed 'Ouvrir le dossier des sauvegardes et des journaux' 296 46 290 36
    $bRestaurer = New-BoutonJed 'Restaurer une sauvegarde' 16 92 270 36
    $bMotDePasse = New-BoutonJed 'Mot de passe oublié' 296 92 290 36
    $bMigration = New-BoutonJed 'Vérifier la migration' 16 138 270 36
    $bEssai = New-BoutonJed 'Réinitialiser l''essai' 296 138 290 36
    foreach ($b in @($bRestaurer, $bMotDePasse, $bMigration, $bEssai)) { $b.Enabled = $false }
    $note = New-EtiquetteJed 'Restaurer, mot de passe oublié, vérifier la migration et réinitialiser l''essai arrivent à l''étape suivante du développement (version candidate 2.0.2-rc1).' 16 190 570 60
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
    $f.Size = New-Object System.Drawing.Size(1000, 680)
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
    $bNouvelle.Add_Click({ Show-InfoJed 'La nouvelle installation guidée arrive à l''étape suivante du développement (version candidate 2.0.2-rc1). En attendant, suivez le guide d''installation.' })
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
