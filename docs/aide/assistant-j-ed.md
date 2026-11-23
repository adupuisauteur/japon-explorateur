---
titre: L'assistant J-ed
rubrique: Installation et mises à jour
ordre: 5
public: admin
resume: Installer, mettre à jour, vérifier, sauvegarder et restaurer J-ed sous Windows, sans ouvrir PowerShell.
---
L'**assistant J-ed** est une fenêtre Windows qui fait à votre place les opérations d'installation et d'entretien :
plus besoin d'ouvrir PowerShell ni de taper des commandes. Il lance les mêmes scripts que la ligne de commande,
avec les mêmes garde-fous (sauvegarde vérifiée, empreinte de l'archive, confirmation, jamais d'effacement des
données sans votre accord).

## L'ouvrir

Double-cliquez sur **`J-ed.cmd`**, dans le dossier de J-ed (ou sur le raccourci « Assistant J-ed » du Bureau, s'il
a été créé). La première fois, Windows peut afficher « Windows a protégé votre ordinateur » : cliquez sur
**Informations complémentaires**, puis **Exécuter quand même**.

Pour une première installation, suivez d'abord le guide **Avant de commencer** (fichier `AVANT-DE-COMMENCER.html`
de l'archive) : il explique comment installer WSL et Docker Desktop.

## L'écran d'accueil

- **Mettre à jour une installation** et **Nouvelle installation**, en haut.
- **Vos installations** : nom, version, port, état (en marche ou arrêtée), date de la dernière sauvegarde (la ligne
  se colore au-delà de 7 jours) et dossier. L'assistant retrouve les installations que Docker connaît, et celles
  qu'il a déjà vues. Une installation arrêtée avec « docker compose down » n'est plus visible pour Docker :
  ajoutez-la avec **Ajouter une installation…** (choisissez son dossier, celui qui contient `.env`).
- Pour l'installation choisie : **Démarrer**, **Arrêter** (les données restent intactes), **Ouvrir J-ed**,
  **Vérifier** (avec ou sans tests et sources ; un rapport est écrit), **Créer les raccourcis**.
- **Prérequis** : vérifiés au démarrage (Windows, mémoire, virtualisation, WSL, Docker Desktop, place libre). Ce
  qui manque s'affiche en rouge, avec un bouton **Comment faire ?**.

## Mettre à jour

1. Choisissez l'installation dans la liste, puis **Mettre à jour une installation**.
2. Choisissez l'archive de la nouvelle version (**Choisir…**), ou cliquez sur **Télécharger la dernière version
   (GitHub)** : l'assistant télécharge l'archive et son empreinte dans `Téléchargements\J-ed`.
3. L'assistant contrôle l'empreinte : le bouton **Lancer la mise à jour** ne s'active que si elle est conforme.
4. Pendant la mise à jour, la fenêtre montre chaque étape. Quand la nouvelle version est prête, une question vous
   demande de confirmer l'arrêt de l'ancienne : répondez **Oui**.
5. À la fin, un message dit ce qui s'est passé (les codes sont expliqués dans
   [Mettre à jour J-ed](aide:mettre-a-jour)) ; **Ouvrir le journal** montre le détail.

## Nouvelle installation

**Nouvelle installation** installe J-ed dans un nouveau dossier, même si une installation existe déjà : vous
pouvez ainsi avoir une **deuxième instance** (par exemple un essai), sur un autre port. L'assistant propose un nom
et un port libres et les vérifie pendant que vous tapez ; il refuse un nom déjà pris, même par d'anciennes données
encore présentes dans Docker. Chaque installation reçoit ses propres secrets : rien n'est copié d'une autre.

À la fin, l'assistant propose de **créer le compte administrateur**, de **créer les raccourcis** et de **charger le
jeu d'essai** (notices fictives ; voir [Essayer J-ed](aide:essayer-j-ed)).

## Opérations de maintenance

- **Créer une sauvegarde** : sauvegarde vérifiée, copiée dans le dossier des sauvegardes.
- **Restaurer une sauvegarde** : de préférence **dans une nouvelle installation** (rien d'existant n'est touché ;
  c'est la façon sûre d'essayer une sauvegarde). Dans une installation existante, sa base est remplacée : il faut
  taper `RESTAURER`, et J-ed fait d'abord une sauvegarde de sécurité. Dans une nouvelle installation, les clés
  d'API des IA ne sont pas reprises : saisissez-les de nouveau.
- **Mot de passe oublié** : choisissez le compte, tapez deux fois le nouveau mot de passe (10 caractères au moins).
  Il n'est écrit nulle part. Si le compte était bloqué par trop d'essais, attendez 15 minutes.
- **Vérifier la migration** : après un passage sur un autre ordinateur.
- **Réinitialiser l'essai** : seulement pour une installation d'essai ; une sauvegarde est faite avant si possible,
  et il faut taper `REINITIALISER`.

## Derrière un proxy

Si Windows passe par un proxy, laissez cochée la case **« Mon réseau passe par un proxy : utiliser celui de
Windows »** (cochée d'avance quand un proxy est détecté) ; **Docker joint-il Internet ?** vérifie que Docker
Desktop est bien réglé (Settings → Resources → Proxies → « System proxy »). L'adresse du proxy est écrite dans le
fichier `.env` de l'installation (une copie de l'ancien fichier est gardée). Un proxy avec identifiant et mot de
passe se règle à la main.

## Ça ne marche pas

Le bouton **Ça ne marche pas** enregistre sur le Bureau un compte rendu (`compte-rendu-j-ed-….zip`) à envoyer à la
personne qui vous aide : état de l'ordinateur, de Docker et de l'installation choisie, dernières lignes des
journaux, dernier journal de mise à jour. Il ne contient **ni mot de passe, ni clé, ni adresse électronique**, et
jamais le fichier `.env`.

Si l'assistant lui-même ne s'ouvre pas, ouvrez un Terminal dans le dossier de J-ed et tapez la commande suivante :
le message affiché dit pourquoi.

```
powershell -ExecutionPolicy Bypass -File .\assistant\assistant-j-ed.ps1
```
