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

## Lot 3 — tâches, file de nuit, « Traduire maintenant »

Sur l'essai mis à jour avec l'archive du lot 3. Recharge une fois avec Ctrl + F5.

**V3-1 — Conteneurs et profil.** `verifier-j-ed.ps1` : conteneurs `worker`, `worker-traduction` et
`worker-maintenant` en service. État de l'installation : « Workers » indique les trois files servies ; « Profil de
la machine » indique Normal (7,6 Go, 8 cœurs). Indique la mémoire de ton ordinateur dans le champ sous le tableau :
un conseil `.wslconfig` s'affiche si Docker en voit nettement moins.

**V3-2 — Essai automatique d'Argos.** Deux à trois minutes après la mise à jour : Moteurs locaux affiche « Dernier
essai (…, automatique) : Argos prêt ». Le bouton « Lancer un essai » refait l'essai.

**V3-3 — Traduire maintenant.** Sur une fiche, avec Argos comme moteur par défaut : « Traduire maintenant ».
Attendu : aucun écran de confirmation ; « Traduction en cours » puis « Traduction prête : voir et valider » sur la
fiche ; pendant ce temps, l'indicateur « 1 traduction en cours » apparaît dans la barre de menu.

**V3-4 — Plage de nuit.** Traduction → Moteurs : choisis une plage commençant dans 5 minutes (par exemple 19:30 –
19:45), enregistre. Ajoute deux traductions à la file de nuit (bouton lune d'une fiche, ou « Ajouter à la file de
nuit » dans l'atelier d'un document). Page Tâches : elles sont dans « File de nuit » ; inverse leur ordre.
Attendu : au début de la plage, la première part, puis la seconde ; après la fin de la plage, une notification
« Compte rendu de la nuit ».

**V3-5 — Retard.** Programme une traduction dans 5 minutes, puis arrête J-ed (`docker compose stop`) pendant
10 minutes et redémarre-le (`docker compose up -d`). Attendu : la tâche est « En retard — à confirmer », une
notification le dit, rien n'est parti ; « Lancer maintenant » la fait partir.

**V3-6 — Pause et reprise.** Pendant une longue traduction Argos (plus de 20 segments) : « Mettre en pause ».
Attendu : arrêt après le paquet en cours ; « Reprendre maintenant » termine sans retraduire ce qui est fait.

**V3-7 — Travail en parallèle.** Pendant cette longue traduction, lance une recherche sur plusieurs sources et
navigue dans la Bibliothèque. Attendu : pages fluides ; une « Traduire maintenant » sur une fiche aboutit sans
attendre la fin du document.

**V3-8 — Traductions effectuées.** Traduction → Traductions effectuées : tes notices traduites, filtres par état,
moteur et date ; les documents de projets avec leur avancement.

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

## Lot 4 — résumés IA, IA locale, japonais ancien

Sur l'essai mis à jour avec l'archive du lot 4. Recharge une fois avec Ctrl + F5. Les essais V4-5 à V4-7
téléchargent le programme Ollama puis un modèle (2,5 Go pour qwen3:4b) : fais-les quand tu peux laisser le
téléchargement se faire.

**V4-1 — Résumé d'une notice.** Traduction → Moteurs, section « Résumés IA » : choisis une IA en ligne déjà
configurée (fournisseur et modèle). Sur une fiche avec une description japonaise : type « Résumé court », langue
Français, « Résumer maintenant ». Attendu : écran de confirmation (appels, coût estimé, « généré par IA ») ; après
confirmation, le résumé apparaît sur la fiche avec la mention « généré par IA », le modèle et la date. Refais-le en
« Fiche d'analyse » : thèmes, personnes, lieux, dates ; « Détail » montre aussi la version précédente.

**V4-2 — Résumer après la traduction.** Prépare une traduction de deux notices (« Traduire… »). Sur l'écran de
confirmation, coche « Résumer aussi », choisis « juste après chaque traduction », confirme. Attendu : la
traduction, puis les résumés (notification « Résumés prêts »). Refais-le avec la file de nuit et « après l'ensemble
des traductions » : la page Tâches montre les résumés après toutes les traductions de la nuit.

**V4-3 — Bibliothèque et atelier.** Bibliothèque : sélectionne des notices, action « Résumer maintenant ». Atelier
d'un document : bouton « Résumer ». Attendu : les mêmes écrans ; un projet confidentiel refuse une IA en ligne.

**V4-4 — Exports.** Exporte une notice résumée deux fois : sans cocher « Inclure les résumés IA » (aucun résumé),
puis en le cochant (résumé marqué « Généré par IA — Non vérifié », ligne « Résumés IA » dans la méthodologie).

**V4-5 — Installer l'IA locale.** Dans `.env`, remplace la ligne par `COMPOSE_PROFILES=argos,ollama`, puis
`docker compose up -d`. `verifier-j-ed.ps1` : ligne « IA locale : service Ollama démarré ». Moteurs locaux,
section « IA locale » : « En service », la liste des trois modèles avec leur taille.

**V4-6 — Télécharger un modèle.** Coche « télécharger 2,5 Go depuis Internet » pour qwen3:4b, « Installer ».
Attendu : « Installations récentes » montre la progression (pourcentage) ; à la fin, « Dernier essai : IA locale
prête » avec le résumé d'un texte fictif, et une notification. Note la durée du résumé d'essai.

**V4-7 — Résumé avec l'IA locale.** Traduction → Moteurs, « Résumés IA » : IA locale, qwen3:4b. Résume une notice.
Attendu : coût 0, mention « IA locale : gratuite, rien ne quitte l'ordinateur » ; note la durée et la qualité du
résumé (c'est l'essai réel qui décide du modèle conseillé).

**V4-8 — Japonais ancien.** Ouvre une notice en japonais classique (un texte avec けり, べし, 候…). Attendu : bandeau
« Japonais classique (bungo) — probable » avec ses indices ; « Confirmer » ou corrige la variété. Signale-moi
quelques notices anciennes mal repérées (ou modernes repérées à tort) pour régler le repérage.

**V4-9 — Moteur pour le japonais ancien.** Traduction → Moteurs, « Pour le japonais ancien, utiliser… » : une IA.
Prépare une traduction d'une notice moderne et d'une notice ancienne. Attendu : « Tâche en deux parties,
confirmées ensemble » avec le moteur de chaque partie ; « Confirmer » lance les deux.

## Lot 6 — aide intégrée, historique des versions, logo

Sur l'essai mis à jour avec l'archive du lot 6. Recharge une fois avec Ctrl + F5 (le logo et les icônes sont mis en
cache par le navigateur).

**V6-1 — Le bouton ?.** Sur plusieurs écrans (fiche d'une notice, Bibliothèque, Traduction → Tâches, Moteurs locaux,
Administration → Sauvegardes), clique sur le bouton **?** à gauche du menu à ton nom. Attendu : la page d'aide de
cet écran s'ouvre.

**V6-2 — L'aide.** Menu à ton nom → **Aide**. Attendu : six rubriques ; les pages « administrateur » sont marquées.
Ouvre deux ou trois pages : les liens vers d'autres pages fonctionnent. Dis-moi si un texte est faux, flou ou
incomplet.

**V6-3 — Recherche dans l'aide.** Cherche « file de nuit », puis « sorobun » (sans macron). Attendu : les pages
« Tâches, file de nuit… » et « Le japonais ancien dans J-ed ».

**V6-4 — Rôles.** Avec un compte chercheur, puis lecteur : les pages de l'administrateur n'apparaissent pas ; le
lecteur ne voit pas non plus les pages de traduction.

**V6-5 — Quoi de neuf et historique.** Bas de page → **Quoi de neuf** : la version 2.0.0 seulement. Administration →
**Historique des versions** : 2.0.0, 1.3.0, 1.2.0, 1.1, sans aucune liste de corrections.

**V6-6 — Logo.** Barre de menu (logo seul), onglet du navigateur, page de connexion, « À propos ». Si J-ed est
installé comme application, l'icône peut ne changer qu'après l'avoir désinstallée puis réinstallée.

**V6-7 — Logo dans les exports.** Exporte une notice en PDF, en Word et en site HTML. Attendu : le logo sur la page
de titre et dans l'en-tête des pages (PDF, Word), et dans l'en-tête de chaque page du site HTML.

**V6-9 — Correctifs du 16 novembre 2026.**
- **Script de mise à jour.** Avant la mise à jour, remplace `C:\J-ed\mettre-a-jour.ps1` par celui joint à
  l'archive.
- **Fichier `.env`.** Dans le `.env` actuel, ne garde qu'une ligne active `COMPOSE_PROFILES=argos,ollama` : mets un
  `#` devant les lignes `hors-ligne`.

Après la mise à jour :
- `.env` n'a pas de nouvelle ligne `hors-ligne` ;
- `verifier-j-ed.ps1` passe la section 4 ;
- la fiche « HANKYO TAISAKU… » garde ses boutons à droite du titre ;
- l'aide a la rubrique « Installation et mises à jour ».

**V6-8 — Guide d'utilisation.** Ouvre `docs/guide-utilisation.html` dans le navigateur : sommaire, toutes les pages
de l'aide. Imprimer → Enregistrer au format PDF donne le guide en PDF.

## Lot 9 — performances (étape 1 : mesure)

Sur l'essai mis à jour avec l'archive `lot9-etape1`.

**V9-1 — Mesure.** Dans PowerShell, depuis `C:\J-ed` :
`docker compose exec web python manage.py mesurer_performances`. Attendu : quelques minutes, puis deux tableaux
(« Base temporaire : 50000 notices fictives » et « Vos données (lecture seule) »), et la ligne « Base temporaire …
supprimée ». Copie le résultat complet dans ta réponse.

**V9-2 — Rien n'a changé.** Après la mesure : même nombre de notices dans la Bibliothèque et dans Sources, aucune
nouvelle notice « fictif », aucun utilisateur « mesure-fictif » dans Administration → Utilisateurs.

**V9-3 — Page Consommation.** Traduction → Consommation : mêmes totaux qu'avant la mise à jour pour le mois en cours.

**V9-4 — Étape 2 : IA locale juste après la mise à jour.** Lance `verifier-j-ed.ps1` dans la minute qui suit la
mise à jour. Attendu : la ligne IA locale n'est plus « Problème ». Elle est soit « OK », soit « à surveiller » avec
« Essai automatique en attente » et une heure. Trois minutes plus tard, la page « État de l'installation » indique
« Prête ».

**V9-5 — Étape 2 : doublons.** Ouvre une fiche dont tu sais qu'elle a un doublon (même œuvre dans deux sources).
Attendu : le doublon est proposé, comme avant.

## Lot 10 — documents et nouvelles sources

**V10-1 — Étude des sources (étape 1).** Dans PowerShell, depuis le dossier de J-ed :
`docker compose exec web python manage.py etudier_sources`, puis
`docker compose cp web:/tmp/etude-sources.txt etude-sources.txt`. Attendu : 1 à 2 minutes, dix rubriques, aucune
erreur Python. Joins le fichier `etude-sources.txt` à ta réponse.

**V10-2 — Étude des sources, second passage (étape 2).** Même commande qu'en V10-1 :
`docker compose exec web python manage.py etudier_sources`, puis
`docker compose cp web:/tmp/etude-sources.txt etude-sources-2.txt`. Joins `etude-sources-2.txt`.

**V10-3 — Aozora Bunko : import.** Mises à jour → Aozora Bunko → Synchronisation complète. Attendu : environ
17 000 nouvelles notices à valider. « Intégrer les éléments acceptés » : message « tâche de fond » ; quelques
minutes plus tard, la synchronisation est « Intégré ». Une recherche 羅生門 avec la source Aozora Bunko trouve
l'œuvre d'Akutagawa.

**V10-4 — Aozora Bunko : texte.** Fiche de 羅生門 → Texte intégral → Télécharger le texte. Attendu : texte avec
furigana, bas de page « 底本： ». Envoyer au projet (un projet d'essai) : le document apparaît dans le projet,
sans furigana.

**V10-5 — Kokusho (étape 3).** Rechercher 方丈記 avec la seule source Kokusho. Attendu : environ 112 notices, avec
titre, auteur (ex. 山岡元隣), date (明暦４), 刊 ou 写, établissement dans la description ; aucun avertissement
« filtrage approximatif ». Sources → Kokusho → Tester le connecteur : « Japan Search (base nij16) : OK ».

**V10-6 — Waseda (étape 3).** Sources → Waseda : suivre le bandeau (Configuration → Connecteur « Waseda Kotenseki
(via NDL Search) » → Enregistrer), puis Tester le connecteur. Rechercher 源氏物語 avec la seule source Waseda :
environ 223 notices ; sur une notice, « Ouvrir sur le site de Waseda » mène à la page de l'ouvrage, avec la mention
早稲田大学図書館古典籍総合データベース.

**V10-7 — Ouvrir le document.** Fiche d'une notice Kokusho à images (par exemple une recherche
`10.20730/200015559` dans Kokusho) : bouton « Ouvrir dans le Kokusho ». Fiche d'une notice NDL numérisée :
« Ouvrir dans la NDL Digital Collections ».

**V10-8 — Visionneuse intégrée.** Administration → Paramètres → cocher « Visionneuse d'images intégrée »,
Enregistrer. Sur la fiche Kokusho de V10-7 : « Voir les images dans J-ed » ; 152 vues, flèches du clavier,
« Taille réelle », mention 国文学研究資料館. Décocher ensuite si tu ne veux pas la garder.

**V10-9 — Étude, accès NDL.** `docker compose exec web python manage.py etudier_sources` (plan 3, par défaut),
puis `docker compose cp web:/tmp/etude-sources.txt etude-sources-3.txt`. Joins le fichier.

**V10-10 — Correctif 1 : intégrations simultanées.** Mises à jour → la synchronisation Aozora Bunko. Si elle
indique « En cours » sans avancer, ou s'il reste des éléments « À intégrer » : « Reprendre » (ou « Intégrer les
éléments acceptés »). Un double clic ne lance qu'une intégration ; le second clic affiche « déjà en cours ».
Journal des dysfonctionnements : l'incident INC-20261116-5D1D5E peut être marqué « Résolu » ; aucune nouvelle
occurrence.

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
| V3-1 Conteneurs et profil | | |
| V3-2 Essai automatique d'Argos | | |
| V3-3 Traduire maintenant | | |
| V3-4 Plage de nuit | | |
| V3-5 Retard | | |
| V3-6 Pause et reprise | | |
| V3-7 Travail en parallèle | | |
| V3-8 Traductions effectuées | | |
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
| V4-1 Résumé d'une notice | | |
| V4-2 Résumer après la traduction | | |
| V4-3 Bibliothèque et atelier | | |
| V4-4 Exports | | |
| V4-5 Installer l'IA locale | | |
| V4-6 Télécharger un modèle | | |
| V4-7 Résumé avec l'IA locale | | |
| V4-8 Japonais ancien | | |
| V4-9 Moteur pour le japonais ancien | | |
| V6-1 Le bouton ? | | |
| V6-2 L'aide | | |
| V6-3 Recherche dans l'aide | | |
| V6-4 Rôles | | |
| V6-5 Quoi de neuf et historique | | |
| V6-6 Logo | | |
| V6-7 Logo dans les exports | | |
| V6-8 Guide d'utilisation | | |
| V9-1 Mesure des performances | | résultat joint |
| V9-2 Rien n'a changé | | |
| V9-3 Page Consommation | | |
| V9-4 IA locale après mise à jour | | |
| V9-5 Doublons | | |
| V10-1 Étude des sources | | fichier joint |
| V10-2 Étude des sources (2) | | fichier joint |
| V10-3 Aozora : import | | |
| V10-4 Aozora : texte | | |
| V10-5 Kokusho | | |
| V10-6 Waseda | | |
| V10-7 Ouvrir le document | | |
| V10-8 Visionneuse intégrée | | |
| V10-9 Étude, accès NDL | | fichier joint |
| V10-10 Intégrations simultanées | | |
