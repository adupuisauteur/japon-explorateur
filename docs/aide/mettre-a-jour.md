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

## Lancer la mise à jour

Dans PowerShell (clic droit sur Démarrer → Terminal), en adaptant les chemins :

```
cd C:\J-ed
powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.0.zip -Actuel C:\J-ed\japon-explorateur-1.3.0 -DossierSauvegardes C:\J-ed\sauvegardes
```

- `-Actuel` : le dossier de la version **actuellement installée** (celui qui contient `.env`).
- Le script vérifie l'archive, fait une **sauvegarde vérifiée** copiée dans `-DossierSauvegardes`, installe la
  nouvelle version dans un **nouveau dossier** (l'ancien n'est jamais modifié), reprend votre `.env`, puis demande de
  taper `OUI` avant d'arrêter l'ancienne version et de démarrer la nouvelle.
- À la moindre anomalie, il s'arrête avec un message qui commence par **ARRÊT** et dit quoi faire.

## Après la mise à jour

1. Ouvrez J-ed et rechargez la page avec **Ctrl + F5**.
2. Vérifiez l'installation : voir [Vérifier l'installation](aide:verifier-l-installation).
3. En cas de souci : [Dépannage après une mise à jour](aide:depannage-apres-mise-a-jour).
4. Pour essayer les nouveautés sans toucher à vos données : [Essayer J-ed](aide:essayer-j-ed), avec le jeu
   d'essai.

Gardez l'ancien dossier quelques semaines : il permet de revenir en arrière. La procédure de retour est dans le
guide de mise à jour.
