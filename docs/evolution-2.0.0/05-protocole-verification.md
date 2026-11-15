# J-ed 2.0.0 — Protocole de vérification manuelle (tenu à jour au fil des lots)

À faire sur ton poste, dans une installation **d'essai** mise à jour en 2.0.0, avec des données fictives ou
une copie de travail. Inscris le résultat (« OK » ou ce que tu as constaté) dans la grille en fin de page. Ces
vérifications complètent les tests automatiques : elles portent sur ce qui ne peut pas être testé dans
l'environnement de développement (Docker, Windows, Argos réel, clés réelles).

## Vérification automatique (à faire en premier, puis après chaque mise à jour)

Dans PowerShell, depuis le dossier de l'installation :

```
powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1
```

Ce que fait le script :

- il contrôle le poste, Docker, les conteneurs, l'adresse et le `.env` ;
- il essaie ensuite chaque fonction de l'application avec des données fictives, sans modifier ta base ;
- il enregistre un rapport `verification-j-ed-<date>.txt` à côté du dossier de l'installation.

Deux options s'ajoutent à la commande :

- `-AvecSources` interroge aussi chaque source en ligne, sur Internet ;
- `-AvecTests` lance les tests automatiques dans le conteneur, en 3 à 10 minutes, sur une base de test séparée.

Attendu : aucun « Problème ». Les lignes « À surveiller » et « Non vérifié » disent pourquoi. Joins le rapport
à la grille.

Ce que le script ne remplace pas : les vérifications ci-dessous qui demandent une action de ta part, comme
arrêter un conteneur ou utiliser une vraie clé, et ton appréciation de l'affichage.

## Lot 0 — corrections et fiabilité

**V0-1 — Mise à jour par le script.**

1. Place côte à côte, dans le dossier parent de ton essai : l'archive 2.0.0 et son fichier `.sha256`.
2. Lance, dans PowerShell, en adaptant les chemins :

   ```
   powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.0-lot0.zip -Actuel D:\Exemple\japon-explorateur-1.3.0-rc3 -DossierSauvegardes D:\Exemple\sauvegardes
   ```

Attendu :

- les 6 étapes défilent, puis « Mise à jour terminée : J-ed 2.0.0 » s'affiche avec l'adresse ;
- la sauvegarde est présente dans le dossier `-DossierSauvegardes` ;
- l'ancien dossier est inchangé ;
- tes notices et tes projets sont toujours là.

**V0-2 — Arrêts du script.**

1. Modifie un caractère du fichier `.sha256`, puis relance. Attendu : « ARRÊT : empreinte de l'archive
   différente », rien n'est arrêté.
2. Remets l'empreinte correcte, puis relance alors que le nouveau dossier existe déjà. Attendu : « ARRÊT : le
   dossier de destination existe déjà ».

**V0-3 — Page « État de l'installation ».** Administration → État de l'installation. Attendu :

- Version 2.0.0, base « À jour » ;
- Redis et workers « Correct » ;
- planificateur « Correct » dans les 5 minutes qui suivent le démarrage ;
- espace disque et ressources affichés ;
- « Copier le diagnostic » place dans le presse-papiers un texte sans ton nom de compte ni tes clés.

**V0-4 — Planificateur arrêté.**

1. Dans Docker Desktop, arrête le conteneur `beat`.
2. Attends 20 minutes, puis recharge la page « État ». Attendu : planificateur « Problème », avec la date du
   dernier signe de vie.
3. Redémarre `beat`.

**V0-5 — Sauvegarde en ligne de commande.**

1. Lance, dans le dossier de l'installation : `docker compose exec web python manage.py backup --verify`, puis
   `echo $LASTEXITCODE`. Attendu : « Terminée », « Intégrité vérifiée », code `0`.
2. Avec `DOSSIER_SAUVEGARDES` dans `.env` (puis `docker compose up -d`), lance une sauvegarde depuis
   Administration → Sauvegardes. Attendu : la sauvegarde apparaît dans le dossier Windows, et la page
   Sauvegardes affiche ce dossier.

**V0-6 — Argos jamais simulé en silence.**

1. Lance la traduction Argos d'un long document fictif.
2. Pendant la traduction, arrête le conteneur `argos` dans Docker Desktop. Attendu :
   - la tâche passe « Interrompue » avec un message qui parle du service Argos ;
   - les segments déjà traduits le sont réellement ;
   - aucun segment ne porte « Simulation » ;
   - un incident « Indisponibilité » est enregistré.
3. Redémarre `argos`, puis clique sur « Reprendre ». Attendu : seuls les segments restants sont traduits.

**V0-7 — Traduction d'essai d'Argos.** Page « État » → « Traduction d'essai Argos ». Après quelques secondes,
recharge la page. Attendu : « Traduction d'essai : Argos prêt — … », avec les versions des paquets.

**V0-8 — Liste des modèles d'IA** (si tu as une clé Anthropic ou Gemini). IA → Fournisseurs → Tester. Attendu :
le nombre de modèles affiché correspond à la liste complète du fournisseur, soit plus de 20 chez Anthropic si
ton compte en a davantage.

**V0-9 — Tout valider en une fois.**

1. Sur une fiche, lance « Traduire… » avec Argos sur le titre, la description et les sujets.
2. Sur la page de la tâche, clique sur « Tout valider et adopter » et confirme. Attendu :
   - le message « 3 traduction(s) validée(s) et adoptée(s) » ;
   - le titre et la description traduits apparaissent sur la fiche ;
   - le bouton disparaît.
3. Relance une traduction du seul titre, puis utilise le bouton de la fiche (couche éditoriale). Attendu : seul
   le titre change, et l'ancienne traduction redevient « proposée ».

## Lot 1 — interface

À faire sur l'essai, après la mise à jour vers l'archive du lot 1. Pour V1-3, crée un compte fictif de rôle
« Chercheur » (Administration → Utilisateurs → Nouveau), par exemple `chercheur-essai`, avec un mot de passe
d'essai.

**V1-1 — Nom J-ed.** Recharge la page avec Ctrl + F5. Attendu :

- en haut à gauche, « J-ed » ;
- l'onglet du navigateur se termine par « — J-ed » ;
- la page de connexion affiche « J-ed » ;
- le pied de page indique « J-ed · v2.0.0 ».

Si J-ed est installé comme application (PWA), son nom reste parfois l'ancien jusqu'à la réinstallation : c'est
le comportement du navigateur, pas une erreur.

**V1-2 — Menus de l'administrateur.** Connecté en administrateur :

1. Le menu du haut ne contient plus « Administration » ni « Dysfonctionnements ».
2. Le menu à ton nom, en haut à droite, contient « Administration » et « Dysfonctionnements ». S'il y a des incidents nouveaux de gravité Erreur ou Critique, une pastille rouge s'affiche sur ce
   bouton.
3. Le pied de page contient « Administration » et « Dysfonctionnements ».

**V1-3 — Ce que voit un chercheur.** Connecté avec `chercheur-essai` :

1. Ni le menu du haut, ni le menu à son nom, ni le pied de page ne montrent « Administration » ou
   « Dysfonctionnements ».
2. L'adresse `http://localhost:8001/journal/` affiche un refus d'accès.
3. « Signaler un problème », en bas de page, fonctionne. Après l'envoi, on revient à la page de départ, avec le
   message « Signalement enregistré sous l'identifiant … L'administrateur en est informé ».
4. De retour en administrateur, ce signalement figure dans « Dysfonctionnements ».

**V1-4 — À propos** (modifié après ton retour, demande U3). Lien « À propos » en bas de page ; il n'est plus
dans le menu à ton nom. Attendu : version 2.0.0, origine du projet (ancien
nom « Japon — Explorateur documentaire »), liste des logiciels libres.

**V1-5 — Page « J-ed ne répond pas ».**

1. Ouvre J-ed une fois, puis arrête-le : `docker compose stop web`, dans le dossier de l'installation.
2. Recharge la page (F5, pas Ctrl + F5). Attendu : la page « J-ed ne répond pas », sans menu et sans numéro de
   version, qui conseille de vérifier Docker Desktop.
3. Redémarre : `docker compose start web`, attends une minute, puis clique sur « Réessayer ». Attendu : J-ed
   revient.

Après un `docker compose ps`, la colonne STATUS de `web` indique « (healthy) » : le contrôle de santé passe
désormais par l'adresse `/sante/`.

**V1-6 — Bas de page des exports (demande U2).**

1. Exporte une sélection de notices en Word, puis en PDF. Attendu, en bas de chaque page après la couverture :
   « Produit le JJ/MM/AAAA à HH:MM · J-ed 2.0.0 · par <ton identifiant> », l'identifiant de l'export
   (`EXP-…`) et le numéro de page. Le texte de la case « Pied de page » figure au-dessus.
2. Refais l'export Word en cochant « Ne pas indiquer mon identifiant en bas de page ». Attendu : la même ligne,
   sans « par … ».
3. Dans un projet de traduction, Exporter → « Word bilingue en tableau (.docx) ». Attendu : la même ligne en bas de chaque
   page, et « Exporté par » dans l'en-tête ; la case « Ne pas indiquer mon identifiant » les retire.

## Lot 2 — trois statuts

À faire sur l'essai, après la mise à jour vers l'archive du lot 2. La mise à jour calcule les statuts de toutes
tes notices, sans appel réseau ; elle prend quelques secondes de plus.

**V2-1 — Pastilles.** Ouvre la Bibliothèque. Attendu : sous chaque notice, trois pastilles distinctes
« Notice », « Document » et « IIIF ». Le survol d'une pastille affiche l'origine, la date et le détail.

**V2-2 — Fiche.** Ouvre une notice venue de Japan Search ou de Kokusho. Attendu : la section « Disponibilité »
présente les trois statuts, avec origine, date et adresse. Pour une notice Kokusho trouvée par la recherche,
IIIF « Identifié », origine « déduit par J-ed » (adresse construite à partir de l'identifiant, décision D5).

**V2-3 — Vérifier un manifeste.**

1. Sur une fiche dont le statut IIIF est « Identifié », clique sur « Vérifier le manifeste IIIF ».
2. Recharge la page après quelques secondes. Attendu : « Vérifié », origine « vérifié par J-ed », avec la
   version IIIF et le nombre de vues ; ou « Vérification en échec » avec la raison, et un incident dans
   « Dysfonctionnements ».

**V2-4 — Sélection et reprise.**

1. Dans la Bibliothèque, coche cinq notices, dont une sans manifeste, puis « Vérifier IIIF ». Attendu :
   « Vérification … lancée pour 4 notice(s) » et « 1 notice(s) sans manifeste IIIF connu ».
2. Pendant la vérification, arrête le worker : `docker compose stop worker`, puis relance-le :
   `docker compose start worker`. Attendu : au plus tard un quart d'heure après, les notices restantes sont
   vérifiées, sans refaire les premières (reprise toutes les 10 minutes, après expiration du verrou de 5 minutes).

**V2-5 — Filtres et tri.**

1. Bibliothèque : filtre « IIIF : Identifié », puis tri « IIIF ». Attendu : seules les notices concernées ;
   les vérifiées d'abord.
2. Lance une recherche sur Japan Search et la NDL ; dans les résultats, filtre « Document consultable : Oui ».
   Attendu : une notice NDL avec un lien de numérisation n'apparaît pas (la NDL ne dit pas si l'accès est
   libre : « non vérifié »).
3. Recherche avancée : les cases « Notice disponible », « Document consultable » et « IIIF » remplacent
   « Accès numérique ».

**V2-6 — Statuts dans les exports** (archive `lot5b`). Exporte quelques notices en Word, puis en CSV (profil
bibliographie). Attendu : dans le Word, une ligne « Disponibilité » (« Notice : … · Document : … · IIIF : … »)
à la place de « Accès numérique » ; dans le CSV, trois colonnes `status_notice`, `status_document` et
`status_iiif`.

## Lot 5 — notifications

À faire sur l'essai, après la mise à jour vers l'archive du lot 5. Si l'apparence n'a pas changé, recharge une
fois la page avec Ctrl + F5.

**V5-1 — Essai.** Menu à ton nom → « Notifications » → « Préférences et essai » → « Envoyer une notification
d'essai ». Attendu :

- une fenêtre en bas à droite, « [Essai] Tâche terminée… », avec « Voir le compte rendu » et « Vu » ;
- le compteur rouge sur le bouton du menu à ton nom passe à 1 ;
- « Vu » ferme la fenêtre et remet le compteur à zéro ;
- la notification figure dans l'historique, marquée « lue ».

**V5-2 — Alerte de dysfonctionnement d'essai** (administrateur). Même page, « Envoyer une alerte de
dysfonctionnement d'essai ». Attendu : une fenêtre rouge « [Essai] Nouveau dysfonctionnement… » ; le lien mène
à la page « Dysfonctionnements ». Rien n'est ajouté au journal.

**V5-3 — Fin d'une vraie tâche.** Lance une petite traduction (un champ d'une notice, avec Argos), puis va sur
une autre page. Attendu, à la fin : une fenêtre « Traduction terminée : … » ; « Voir le compte rendu » ouvre la
tâche. Même chose avec un export : « Export prêt : … ».

**V5-4 — Absence.** Lance une traduction un peu longue, déconnecte-toi avant la fin, attends, puis reconnecte-toi.
Attendu : la fenêtre s'affiche à la reconnexion.

**V5-5 — Préférences.** Décoche « Tâche terminée », enregistre, puis lance un export. Attendu : aucune fenêtre ;
recoche ensuite la case.

**V5-6 — Onglet masqué.** Ouvre J-ed, passe à un autre onglet pendant une minute, puis reviens. Attendu : aucune
anomalie ; une notification arrivée entre-temps s'affiche au retour sur l'onglet.

## Lot 7 — Argos installé par défaut

Sur l'essai mis à jour avec l'archive du lot 7. Recharge une fois avec Ctrl + F5.

**V7-1 — Ligne de démarrage.** Ouvre le `.env` du nouveau dossier (`notepad .env`). Attendu : ta ligne
`COMPOSE_PROFILES=hors-ligne` est conservée telle quelle, sans doublon (sur une installation qui n'avait pas la
ligne, le script ajoute `COMPOSE_PROFILES=argos`). `verifier-j-ed.ps1` : Argos et ses conteneurs « OK ».

**V7-2 — Bouton unique (paquets absents).** Sur un essai sans paquets (par exemple après une réinitialisation
`-Complet`, ou une désinstallation des deux paquets dans Moteurs locaux), Traduction → Moteurs locaux : l'encadré
« Traduction hors ligne japonais → français » annonce environ 200 Mo. Coche la case, clique sur « Installer la
traduction japonais → français ». Attendu : progression dans « Installations récentes » ; à la fin, une fenêtre
« Terminé » et, dans « Service », « Dernier essai : Argos prêt » avec la phrase fictive. Note la durée.

**V7-3 — Paquets déjà installés.** Clique de nouveau sur le bouton (s'il est affiché) ou vérifie qu'il ne l'est
plus. Attendu : aucun nouveau téléchargement.

**V7-4 — Invitations.** Désinstalle un paquet, puis ouvre Traduction → Moteurs (carte Argos) et prépare la
traduction d'une notice avec Argos. Attendu : l'invitation apparaît aux deux endroits. Réinstalle ensuite le
paquet avec le bouton.

**V7-5 — Priorité.** Lance la traduction d'un long document avec Argos (plus de 20 segments), puis, pendant
qu'elle tourne, la traduction d'une notice. Attendu : la notice est traduite sans attendre la fin du document.

**V7-6 — Mémoire et licences.** Moteurs locaux : la mémoire vue par le service s'affiche (environ 7,6 Go chez toi,
sans avertissement) ; la section « Licences » est présente.

**V7-7 — Taille et mémoire réelles (à noter).** `docker image ls japon-explorateur-argos` (taille) et
`docker stats --no-stream` pendant une traduction (mémoire du conteneur argos). Ces chiffres serviront à la
décision D8 (lot 3).

## Lot 8 — choix du modèle d'IA

Avec tes vraies clés, sur l'essai mis à jour. Recharge une fois avec Ctrl + F5.

**V8-1 — Liste.** Traduction → Moteurs : choisis « Intelligence artificielle en ligne », puis un fournisseur dont
la clé est enregistrée. Attendu : une liste déroulante de ses modèles de texte, sans modèle d'image, de son ni de
vectorisation, avec la date de la liste et, s'il est saisi dans IA → Tarifs, le tarif estimé.

**V8-2 — Actualiser.** Clique sur « Actualiser la liste ». Attendu : la date change ; la liste reflète les modèles
actuels du fournisseur.

**V8-3 — Choisir et enregistrer.** Choisis un modèle, enregistre, recharge la page. Attendu : le modèle reste
sélectionné.

**V8-4 — Saisie libre et avertissement.** Choisis « Autre modèle (saisie libre) » et tape un nom qui n'existe
pas. Attendu : un avertissement « n'apparaît pas dans la liste de ce fournisseur » ; le nom est conservé tel
quel à l'enregistrement.

**V8-5 — Autres écrans.** La même liste apparaît dans les Préférences IA (modèle par défaut et par fonction), la
fiche d'un projet de traduction et Traduction → Évaluation.

## Grille de résultats

| Vérification | Résultat | Remarque |
| --- | --- | --- |
| Vérification automatique (`verifier-j-ed.ps1`) | | rapport joint |
| V0-1 Mise à jour par le script | | |
| V0-2 Arrêts du script | | |
| V0-3 Page « État » | | |
| V0-4 Planificateur arrêté | | |
| V0-5 Sauvegarde en ligne de commande | | |
| V0-6 Argos jamais simulé | | |
| V0-7 Traduction d'essai d'Argos | | |
| V0-8 Liste des modèles d'IA | | |
| V0-9 Tout valider en une fois | | |
| V1-1 Nom J-ed | | |
| V1-2 Menus de l'administrateur | | |
| V1-3 Ce que voit un chercheur | | |
| V1-4 À propos | | |
| V1-5 Page « J-ed ne répond pas » | | |
| V1-6 Bas de page des exports | | |
| V2-1 Pastilles | | |
| V2-2 Fiche | | |
| V2-3 Vérifier un manifeste | | |
| V2-4 Sélection et reprise | | |
| V2-5 Filtres et tri | | |
| V2-6 Statuts dans les exports | | |
| V5-1 Notification d'essai | | |
| V5-2 Alerte d'essai | | |
| V5-3 Fin d'une vraie tâche | | |
| V5-4 Absence | | |
| V5-5 Préférences | | |
| V5-6 Onglet masqué | | |
| V7-1 Ligne de démarrage | | |
| V7-2 Bouton unique | | |
| V7-3 Paquets déjà installés | | |
| V7-4 Invitations | | |
| V7-5 Priorité | | |
| V7-6 Mémoire et licences | | |
| V7-7 Taille et mémoire réelles | | |
| V8-1 Liste des modèles | | |
| V8-2 Actualiser | | |
| V8-3 Choisir et enregistrer | | |
| V8-4 Saisie libre et avertissement | | |
| V8-5 Autres écrans | | |
