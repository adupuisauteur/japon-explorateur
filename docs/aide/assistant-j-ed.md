---
titre: L'assistant J-ed
rubrique: Installation et mises à jour
ordre: 5
public: admin
resume: Installer, mettre à jour, vérifier, sauvegarder et restaurer J-ed sous Windows (fenêtre) ou sous Linux (menu dans le Terminal).
---
L'**assistant J-ed** est une fenêtre Windows qui fait à votre place les opérations d'installation et d'entretien :
plus besoin d'ouvrir PowerShell ni de taper des commandes. Il lance les mêmes scripts que la ligne de commande,
avec les mêmes garde-fous (sauvegarde vérifiée, empreinte de l'archive, confirmation, jamais d'effacement des
données sans votre accord).

## L'ouvrir

Double-cliquez sur **`J-ed.cmd`**, dans le dossier de J-ed (ou sur le raccourci « Assistant J-ed » du Bureau, s'il
a été créé). La première fois, Windows peut afficher « Windows a protégé votre ordinateur » : cliquez sur
**Informations complémentaires**, puis **Exécuter quand même**.

Une fenêtre noire s'ouvre une seconde, puis se referme : c'est normal. L'assistant apparaît ensuite **au bout de
quelques secondes** (jusqu'à une demi-minute la première fois) : patientez, sans double-cliquer une seconde fois.

Pour une première installation, suivez d'abord le guide **Avant de commencer** (fichier `AVANT-DE-COMMENCER.html`
de l'archive) : il explique comment installer WSL et Docker Desktop.

## L'écran d'accueil

- **Mettre à jour une installation** et **Nouvelle installation**, en haut.
- **Vos installations** : nom, version, port, état (en marche ou arrêtée), date de la dernière sauvegarde (la ligne
  se colore au-delà de 7 jours) et dossier. L'assistant retrouve les installations que Docker connaît, et celles
  qu'il a déjà vues. Une installation arrêtée avec « docker compose down » n'est plus visible pour Docker :
  ajoutez-la avec **Ajouter une installation…** (choisissez son dossier, celui qui contient `.env`).
- Après une mise à jour, l'ancien dossier est gardé : il apparaît en gris, avec l'état **« ancien dossier »**. Il
  utilise les mêmes données que la version en service : n'agissez pas dessus (l'assistant le rappelle). Quand la
  nouvelle version vous convient, vous pouvez le supprimer.
- Si Docker Desktop n'est pas encore démarré, l'état des installations est inconnu (« ? (Docker arrêté) ») ; la liste
  est relue dès que les prérequis sont de nouveau vérifiés.
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
6. Si la mise à jour n'a pas abouti, le message indique le **dossier de la nouvelle version à supprimer** avant de
   recommencer : il ne contient aucune de vos données. L'assistant ne le supprime pas lui-même.

## Nouvelle installation

**Nouvelle installation** installe J-ed dans un nouveau dossier, même si une installation existe déjà : vous
pouvez ainsi avoir une **deuxième instance** (par exemple un essai), sur un autre port. L'assistant propose un nom
et un port libres et les vérifie pendant que vous tapez ; il refuse un nom déjà pris, même par d'anciennes données
encore présentes dans Docker. Chaque installation reçoit ses propres secrets : rien n'est copié d'une autre.

Aucune clé ni aucun mot de passe technique à inventer : l'assistant crée lui-même les clés secrètes de
l'installation et les écrit dans le fichier `.env` de son dossier. **Gardez une copie de ce fichier en lieu sûr**
(clé USB rangée, gestionnaire de mots de passe) : elle sera nécessaire pour passer J-ed sur un autre ordinateur, et
elle ne figure pas dans les sauvegardes de J-ed. Ne l'envoyez à personne.

La première installation prend 10 à 30 minutes (en fonction de la vitesse de téléchargement). Pendant
l'installation, le titre de la fenêtre indique depuis combien de minutes l'étape en cours dure : la
construction peut rester longtemps sans nouvelle ligne. Si l'installation n'aboutit pas, la fenêtre suivante reprend
les choix de la tentative précédente.

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
- **Réinitialiser l'essai** : seulement pour une installation d'essai ; il faut taper `REINITIALISER`. Deux options,
  que l'on peut cocher toutes les deux : **faire d'abord une sauvegarde** (conseillé) et **réinitialisation
  complète** (efface aussi les paquets de langues Argos de l'essai, et ses images si aucune autre installation ne
  s'en sert ; l'essai reste alors arrêté : **Démarrer** le reconstruit).

## Derrière un proxy

Sur un réseau qui passe par un proxy, il faut **deux réglages**, qui ont chacun leur rôle :

1. **Docker Desktop** (à faire avant la première installation) : Settings → Resources → Proxies, « System proxy » ;
   si Docker ne joint toujours pas Internet, « Manual proxy configuration » avec l'adresse du proxy pour HTTP et
   HTTPS. Ce réglage sert à télécharger les images de base (Python, PostgreSQL…).
2. **La case de l'assistant** « Mon réseau passe par un proxy : utiliser celui de Windows » (cochée d'avance quand un
   proxy est détecté) : l'adresse est écrite dans le fichier `.env` de l'installation (une copie de l'ancien fichier
   est gardée). J-ed s'en sert pendant la construction (ses bibliothèques) et pendant son fonctionnement (sources en
   ligne, paquets de traduction).

Le bouton **Docker joint-il Internet ?**, dans « Nouvelle installation » comme dans « Mettre à jour », vérifie le
premier réglage. Sur un réseau **sans** proxy, décochez la case (ou videz les lignes `HTTP_PROXY` et `HTTPS_PROXY`
du `.env` d'une installation existante). Un proxy avec identifiant et mot de passe se règle à la main.

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

## Sous Linux

Sous Linux (Ubuntu), l'assistant est un **menu dans le Terminal**, avec les mêmes fonctions, les mêmes noms et le
même ordre que la fenêtre de Windows : il lance les mêmes scripts, avec les mêmes garde-fous. Pour une première
installation, suivez le guide **Avant de commencer (Linux)** (fichier `AVANT-DE-COMMENCER-LINUX.html` de
l'archive) : Terminal, proxy, Docker Engine, groupe `docker`, PowerShell 7.

Pour l'ouvrir, tapez dans le Terminal (en remplaçant le dossier par celui de votre installation), ou choisissez le
raccourci **Assistant J-ed** du menu Applications :

```
bash ~/J-ed/jed-2.0.3/j-ed.sh
```

- Tapez le **numéro** d'un choix, puis Entrée. Une valeur entre crochets, par exemple `[8001]`, est proposée :
  Entrée seule la garde. `(O/n)` : Entrée vaut oui ; `(o/N)` : Entrée vaut non.
- Ne le lancez jamais avec `sudo` : il refuse (les fichiers de J-ed appartiendraient à l'administrateur).
- Les installations sont rangées dans `~/J-ed` (par exemple `~/J-ed/jed-2.0.3`), leurs sauvegardes à côté (par
  exemple `~/J-ed/sauvegardes-jed`).
- **Mettre à jour** : la question avant l'arrêt de l'ancienne version se répond par **o** (oui).
- **Mot de passe oublié** : le mot de passe ne s'affiche pas pendant la saisie.
- **Créer les raccourcis** : deux entrées dans le menu Applications (« J-ed - » suivi du nom de l'installation, qui
  ouvre J-ed dans le navigateur, et « Assistant J-ed »).
- **Ça ne marche pas** : le compte rendu est enregistré sur le Bureau.
- **Proxy** : l'assistant propose celui des réglages d'Ubuntu (Paramètres → Réseau → Proxy réseau) ; le service
  Docker a son propre réglage (`/etc/docker/daemon.json`, voir le guide).
- Si J-ed ne peut pas écrire dans le dossier des sauvegardes (compte qui n'est pas le premier de l'ordinateur),
  l'assistant affiche la commande qui le permet, par exemple `chmod o+rwx ~/J-ed/sauvegardes-jed`.
