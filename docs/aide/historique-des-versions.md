---
titre: Historique des versions
rubrique: Référence
ordre: 20
public: admin
resume: Évolutions et améliorations de J-ed, version par version.
---
## Version 2.0.2 (version candidate rc1, 23 novembre 2026)

Une version pour installer et entretenir J-ed **sans ouvrir PowerShell**. Aucun changement de vos données.

- **L'assistant J-ed** : un double-clic sur `J-ed.cmd` ouvre une fenêtre qui vérifie l'ordinateur, installe J-ed
  (même une deuxième fois, sur un autre port), le met à jour (au besoin en téléchargeant la dernière version sur
  GitHub), le vérifie, le sauvegarde et le restaure, et retrouve un **mot de passe oublié** (aide « L'assistant
  J-ed »).
- **Proxy** : l'assistant reprend le proxy de Windows et vérifie que Docker joint Internet.
- **Avant de commencer** : un guide pas à pas (fichier `AVANT-DE-COMMENCER.html` de l'archive) pour installer
  WSL, Docker Desktop puis J-ed, même sans rien connaître à Docker.
- **« Ça ne marche pas »** prépare un compte rendu à envoyer, sans aucun mot de passe.

## Version 2.0.1 (23 novembre 2026)

Une petite version, sans changement de vos données : une mise à jour plus sûre et la licence de J-ed.

- **Une mise à jour qui ne laisse plus J-ed arrêté.** Le script prépare la nouvelle version pendant que
  l'ancienne fonctionne encore. Si Docker n'arrive pas à télécharger (pas d'Internet, proxy), il s'arrête sans
  rien avoir arrêté. Si la nouvelle version ne démarre pas, il revient tout seul à l'ancienne (**retour
  automatique**). Chaque mise à jour laisse un **journal** dans le dossier des sauvegardes, et un code qui dit ce
  qui s'est passé (aide « Mettre à jour J-ed »).
- **J-ed est un logiciel libre**, sous la licence **GNU AGPL v3 ou toute version ultérieure** : page « À propos »
  et lien **Code source** en bas de chaque page.
- **Tests automatiques** : à chaque modification publiée, GitHub relance tous les tests de J-ed.

## Version 2.0.0 (19 novembre 2026)

Une version de consolidation : J-ed devient plus sûr, travaille seul la nuit, résume, et s'explique lui-même.

- **Un nouveau nom, J-ed**, et un logo. Une page « À propos » donne la version et l'origine du projet.
  Administration et Dysfonctionnements passent dans le menu à votre nom (administrateur).
- **Trois statuts par notice**, sans confusion possible : notice disponible, document consultable, IIIF. Le
  manifeste IIIF peut être vérifié d'un clic. Les statuts figurent dans les filtres, les tris et les exports.
- **Notifications** : une fenêtre et un compteur vous préviennent quand une tâche se termine, se met en pause ou
  échoue, et l'administrateur quand un dysfonctionnement apparaît.
- **Tâches et file de nuit** : chaque traduction est une tâche que l'on peut lancer tout de suite, programmer, ou
  placer dans la file de nuit ; pause, reprise sans rien renvoyer, compte rendu du matin. « Traduire maintenant »
  sur la fiche et dans la Bibliothèque. Page « Traductions effectuées ».
- **Plafonds** : un plafond atteint met la tâche en pause ; J-ed ne change jamais de moteur de lui-même.
- **Argos installé d'office**, la traduction japonais → français s'installe en un clic, avec une traduction d'essai.
- **Choix du modèle d'IA dans une liste** tirée du fournisseur, avec le tarif estimé quand il est connu.
- **Résumés IA** : résumé court, détaillé ou fiche d'analyse, toujours dans votre langue, depuis la fiche, la
  Bibliothèque ou l'atelier ; enchaînés aux traductions si vous le souhaitez.
- **IA locale** facultative : une IA gratuite qui travaille sur votre ordinateur, pour les résumés.
- **Japonais ancien** : repérage du bungo, du kanbun et du sōrōbun, et moteur choisi pour eux.
- **Documents et nouvelles sources** : **Aozora Bunko** (plus de 17 000 œuvres) dont le texte intégral se lit
  dans J-ed avec ses furigana et s'envoie vers un projet de traduction ; **Waseda** par le catalogue de la NDL ;
  **Kokusho** interrogé dans sa vraie base ; bouton **« Ouvrir le document »** vers la visionneuse de la source ;
  **visionneuse intégrée** facultative ; pour la NDL, J-ed dit si un document numérisé est en accès libre.
- **Jeu d'essai fictif** et procédure « Essayer J-ed », pour découvrir l'application ou vérifier une nouvelle
  version (Administration → Jeu d'essai).
- **Rapidité mesurée** sur l'ordinateur (commande `mesurer_performances`) ; doublons trouvés aussi dans une
  grande base.
- **Aide intégrée** : une page d'aide par écran (bouton **?**), une recherche, un lexique, cet historique, et une
  rubrique « Installation et mises à jour » (mettre à jour, vérifier, dépanner).
- **Installation** : mise à jour en une commande (`mettre-a-jour.ps1`), vérification automatique
  (`verifier-j-ed.ps1`), page « État de l'installation », sauvegardes copiées dans un dossier de Windows, réglage
  automatique selon la puissance de l'ordinateur.

## Version 1.3.0 (14 novembre 2026)

Le module de **traduction**.

- Moteurs : DeepL, Google Traduction, Argos Translate (sur l'ordinateur) et IA en ligne, choisis dans
  Traduction → Moteurs, avec le résumé des conditions de chaque service avant le premier envoi.
- Traduction des notices (titre, description, sujets, lieu), validée avant d'apparaître sur la fiche.
- Projets de traduction : documents découpés en segments, atelier à deux colonnes, versions, validation,
  projets confidentiels.
- Glossaires (import et export CSV, envoi à DeepL) et mémoire de traduction.
- Exports bilingues : texte, Markdown, CSV, Word en tableau.
- Évaluation des moteurs côte à côte et page de consommation.

## Version 1.2.0 (13 novembre 2026)

- Nouvelles sources : CiNii Research, Archives nationales par Japan Search, outil pour trouver une base Japan
  Search.
- Recherche : état clair de chaque source (résultats, aucun résultat, indisponible…), variantes de graphie libres,
  filtre « document numérisé », tri par auteur et par institution.
- Journal des dysfonctionnements : enregistrement automatique, regroupement, suivi, analyse, export.
- Installation d'essai séparée de l'installation principale.

## Version 1.1 (novembre 2026)

La première version complète : recherche dans plusieurs catalogues japonais, Bibliothèque, dossiers partagés,
fiches avec versions et provenance, fonctions IA, exports (Word, PDF, texte, JSON, CSV, site HTML), mises à jour des
sources et imports, comptes et rôles, sauvegardes.
