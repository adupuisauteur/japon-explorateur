---
titre: Mettre à jour J-ed
rubrique: Installation et mises à jour
ordre: 10
public: admin
resume: Passer à une nouvelle version sans rien perdre, avec le script de mise à jour.
---
Une mise à jour **garde toutes vos données** : notices, bibliothèque, projets, glossaires, comptes, clés, paquets
Argos et modèles de l'IA locale. Elle se fait en une commande, avec le script `mettre-a-jour.ps1`. Le **guide de
mise à jour** livré avec chaque version détaille chaque étape.

## Ce qu'il faut

- Docker Desktop démarré, et J-ed en marche (sa page s'ouvre dans le navigateur).
- Environ 5 Go d'espace disque libre.
- Les trois fichiers de la nouvelle version, dans le **dossier parent** de l'installation (par exemple `C:\J-ed`) :
  l'archive `.zip`, son empreinte `.zip.sha256`, et `mettre-a-jour.ps1`.

## Toujours le script de la nouvelle version

Le script `mettre-a-jour.ps1` évolue avec J-ed. **À chaque mise à jour, remplacez celui du dossier parent** par celui
livré avec la nouvelle version (ou par celui du nouveau dossier, après la mise à jour). Un ancien script garde ses
anciens défauts. Par exemple, une version de novembre 2026 ajoutait une ligne `COMPOSE_PROFILES=hors-ligne` au
fichier `.env` à chaque passage.

Le script le signale lui-même : « Attention : ce script de mise à jour n'est pas celui de l'archive », puis un
rappel à la fin.

## La méthode

1. Récupérez les trois fichiers de la nouvelle version et placez-les dans le dossier parent de l'installation
   (ci-dessus).
2. Vérifiez que Docker Desktop est démarré et que J-ed s'ouvre dans le navigateur.
3. Lancez le script (commandes ci-dessous). Il vérifie l'archive, fait une **sauvegarde vérifiée** copiée dans votre
   dossier de sauvegardes, installe la nouvelle version dans un **nouveau dossier** (l'ancien n'est jamais modifié)
   et reprend votre `.env`. Il demande ensuite de taper `OUI` avant d'arrêter l'ancienne version et de démarrer la
   nouvelle.
4. Vérifiez la nouvelle version, puis gardez l'ancien dossier quelques semaines : il permet de revenir en arrière.

## Les commandes

Dans PowerShell (clic droit sur Démarrer → Terminal). L'exemple passe de la 2.0.0 à la 2.0.1 ; remplacez les
numéros et les chemins par les vôtres.

```
cd C:\J-ed
```

Puis :

```
powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.1.zip -Actuel C:\J-ed\japon-explorateur-2.0.0 -DossierSauvegardes C:\J-ed\sauvegardes
```

- `-Archive` : l'archive de la nouvelle version.
- `-Actuel` : le dossier de la version **actuellement installée** (celui qui contient `.env`). Si vous ne le
  retrouvez plus, la commande `docker compose ls` l'indique dans la colonne CONFIG FILES.
- `-DossierSauvegardes` : le dossier où copier la sauvegarde faite avant la mise à jour, en dehors des dossiers
  d'installation.
- `-Destination` (facultatif) : le nouveau dossier, si celui proposé par défaut (`C:\J-ed\japon-explorateur-2.0.1`)
  existe déjà.

[Résultat attendu, à la fin : « Mise à jour terminée : J-ed 2.0.1, http://localhost:8000 ».]

À la moindre anomalie, le script s'arrête avec un message qui commence par **ARRÊT** et dit quoi faire. Avant
l'étape `OUI`, l'installation actuelle n'a pas été touchée.

**Installation au nom protégé** (`japon-explorateur` ou `japon-explorateur-essai`) : son `.env` doit contenir
`AUTORISER_NOM_PROJET=` suivi du même nom, sinon le script s'arrête. Il n'ajoute jamais cette ligne de lui-même.

## Après la mise à jour

Ouvrez J-ed et rechargez la page avec **Ctrl + F5** : le pied de page indique la nouvelle version.

Vérifiez ensuite l'installation depuis le **nouveau** dossier :

```
cd C:\J-ed\japon-explorateur-2.0.1
```

Puis :

```
powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1
```

[Résultat attendu : aucune ligne « [Problème] ». Voir aussi [Vérifier l'installation](aide:verifier-l-installation).]

- En cas de souci : [Dépannage après une mise à jour](aide:depannage-apres-mise-a-jour).
- Pour essayer les nouveautés sans toucher à vos données : [Essayer J-ed](aide:essayer-j-ed), avec le jeu d'essai.

Gardez l'ancien dossier quelques semaines : il permet de revenir en arrière. La procédure de retour est dans le
guide de mise à jour.
