---
titre: Essayer J-ed (jeu d'essai et procédure de test)
rubrique: Installation et mises à jour
ordre: 40
public: admin
ecrans: core:demo_dataset
resume: Un jeu de données fictives et une procédure pas à pas, pour découvrir J-ed ou vérifier une nouvelle version.
---
Cette procédure sert dans deux cas :

- **vous découvrez J-ed** : elle fait le tour des fonctions principales en une demi-heure environ ;
- **vous venez d'installer ou de mettre à jour J-ed** : elle vérifie que tout fonctionne, sans toucher à vos vraies
  données.

Elle s'appuie sur un **jeu d'essai** : des notices, un dossier et un projet de traduction **entièrement
inventés**. Vous les retirez en un clic à la fin.

> Pour une installation d'essai à côté de votre installation principale, utilisez un autre dossier, un autre nom
> d'installation (`COMPOSE_PROJECT_NAME`) et un autre port (`WEB_PORT`) dans le fichier `.env` : voir le guide
> d'installation, étape 3.1.

## Avant de commencer

1. Lancez la vérification automatique : dans PowerShell, depuis le dossier de J-ed,
   `powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1`.
   Attendu : un rapport dont le bilan indique **0 problème** (voir [Vérifier l'installation](aide:verifier-l-installation)).
2. Ouvrez **Administration → Jeu d'essai** → **Charger le jeu d'essai**.
   Attendu : le message « Jeu d'essai chargé : 38 notices fictives… ».

## Partie A — sans Internet (20 minutes)

Chaque étape indique entre crochets le **résultat attendu**. Une étape qui ne donne pas ce résultat est à signaler,
avec une capture d'écran si possible.

1. **Recherche locale.** Rechercher → tapez `架空`, source **Base locale** cochée.
   [23 notices du jeu d'essai (titre, auteur 架空太郎 ou fonds 架空文庫), dont 架空物語集 et 架空絵巻, chacune une
   seule fois ; « 4 déjà enregistré(s) » : celles qui sont déjà dans la bibliothèque. Vos propres notices contenant
   架空 s'y ajoutent, le cas échéant.]
2. **Lecture et rōmaji.** Tapez `kakuu` (en lettres latines).
   [17 notices du jeu d'essai : J-ed cherche aussi par la lecture du titre et de l'auteur. Les six notices
   trouvées à l'étape 1 seulement par leur fonds 架空文庫 n'y sont pas, car un fonds n'a pas de lecture. Vos
   propres notices dont la lecture contient « kakuu » s'y ajoutent, le cas échéant.]
3. **Fiche et trois statuts.** Dans les résultats de l'étape 1, sur la ligne de 架空旅日記 (cote 架-009), cliquez
   sur **Fiche locale** : la fiche s'ouvre dans un nouvel onglet.
   [Trois pastilles : Notice, Document, IIIF. Document indique un lien vers une numérisation (adresse fictive
   `example.org`, à ne pas ouvrir).]
4. **Doublons.** Même chose pour 架空國史略 (avec 國, caractère ancien) : **Fiche locale** sur sa ligne → bloc
   « Doublons et notices liées » (colonne de droite, sous
   « Dossiers » ; sur un écran étroit, en bas de la page) → **Chercher des doublons (règles)**.
   [架空国史略 est proposé : même œuvre, en graphie ancienne et moderne. J-ed ne fusionne jamais tout seul.]
5. **Bibliothèque et dossier.** Ma bibliothèque, puis Dossiers → « [Essai] Dossier fictif ».
   [8 notices dans la bibliothèque et dans le dossier.]
6. **Export.** Dans le dossier : Exporter → Word, puis PDF.
   [Deux fichiers téléchargés ; le PDF affiche correctement les caractères japonais.]
7. **Projet de traduction.** Traduction → Projets → « [Essai] Projet de traduction fictif ».
   [Deux documents. Le texte classique est repéré comme langue classique (bungo).]
8. **Traduction hors ligne.** Ouvrez le texte moderne → **Traduire…** → moteur **Argos**.
   [Une traduction française proposée pour chaque segment, sans connexion ; à valider avant publication.]
9. **Tâches et file de nuit.** Sur le texte classique : **Ajouter à la file de nuit**, puis Traduction → Tâches.
   [La tâche apparaît « dans la file de nuit » ; vous pouvez l'annuler.]
10. **Notifications.** Menu à votre nom (en haut à droite, avec le compteur rouge des non lues) → **Notifications**.
    [Les fins de tâche et les exports y apparaissent ; **Marquer comme lue** fait baisser le compteur. Une
    notification qui arrive pendant que vous travaillez s'affiche aussi dans une petite fenêtre en bas de l'écran,
    avec un bouton **Vu**.]
11. **Sauvegarde.** Administration → Sauvegardes → **Sauvegarder maintenant**, puis vérifiez son intégrité.
    [Sauvegarde terminée, intégrité vérifiée.]
12. **Aide.** Le bouton **?** de chaque page ouvre l'aide correspondante.

## Partie B — avec Internet (facultatif, 15 minutes)

Ces recherches interrogent les vraies sources. Les résultats peuvent varier légèrement avec le temps.

1. **Kokusho.** Rechercher, source **Kokusho** seule : `方丈記`.
   [Les 50 premières notices du 日本古典籍総合目録, avec auteur, date, imprimé (刊) ou manuscrit (写). L'état de
   la source indique « 50 résultat(s) sur … » : un peu plus d'une centaine en tout (112 en novembre 2026).]
2. **Document à images.** Pour voir aussi les images dans J-ed, activez d'abord la visionneuse intégrée (elle est
   désactivée par défaut) : Administration → **Paramètres** → cochez **Visionneuse d'images intégrée** → Enregistrer.
   La liste des sites d'images autorisés, déjà remplie, peut rester telle quelle.
   Puis source Kokusho : `10.20730/200015559` (歌仙繪) → ajoutez-le à la bibliothèque, ouvrez sa fiche (**Fiche
   locale**) → **Ouvrir dans le Kokusho**, puis **Voir les images dans J-ed**.
   [La visionneuse du NIJL s'ouvre sur son site ; dans J-ed, la visionneuse intégrée montre 152 vues. Sans
   l'activation, seul le premier bouton est proposé.]
3. **NDL.** Source **NDL Search** : `2586959` → fiche → **Vérifier le manifeste IIIF**, puis rechargez la page.
   [Document : « oui », consultable librement sur Internet.]
4. **Aozora Bunko.** Si la liste n'est pas encore importée : Mises à jour → Aozora Bunko → synchronisation
   complète, puis intégration (quelques minutes, voir [Aozora Bunko](aide:aozora-bunko)). Rechercher `羅生門`,
   source Aozora Bunko → fiche → **Texte intégral** → **Télécharger le texte**.
   [Le texte s'affiche avec ses furigana ; le texte source (底本) est indiqué en bas de page.]
5. **Waseda.** Source **Waseda** : `源氏物語`.
   [Environ deux cents notices ; « Ouvrir sur le site de Waseda » mène à la page de l'ouvrage. Sur une installation
   mise à jour depuis une version antérieure, choisissez d'abord le connecteur dédié : voir [Les sources](aide:sources).]
6. **Vérification des sources.** `powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1 -AvecSources`.
   [Chaque source en ligne répond, ou figure dans la liste « sans recherche en ligne ».]

## Pour finir

1. **Administration → Jeu d'essai → Retirer le jeu d'essai.**
   [« Jeu d'essai retiré : 38 notice(s), 1 dossier(s), 1 projet(s) ». Vos données ne sont pas touchées.]
2. Si vous avez fait la partie B, les notices réelles ajoutées à la bibliothèque y restent : retirez-les si vous le
   souhaitez.

Le jeu d'essai se charge aussi en ligne de commande, depuis le dossier de J-ed :
`docker compose exec web python manage.py jeu_essai --charger` (et `--retirer`).
