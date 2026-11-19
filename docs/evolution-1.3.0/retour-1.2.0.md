# Retour à la version 1.2.0

## Rappel : votre installation principale n'est pas concernée

La 1.3.0 s'installe dans un **essai séparé** (projet Docker `japon-explorateur-essai-130`, port 8002). Votre
installation principale (port 8000) et l'essai 1.2.0 (port 8001) ne sont jamais touchés. Pour abandonner
l'essai 1.3.0, il suffit donc de l'arrêter (`docker compose stop` dans son dossier) ou de le réinitialiser
(`reinitialiser-essai.ps1 -Complet`).

La procédure ci-dessous sert à **revenir à la 1.2.0 sur une base qui a fonctionné en 1.3.0** : c'est le test
TR12 du protocole, et ce sera la procédure à suivre si, plus tard, l'installation principale passe en 1.3.0 puis
doit revenir en arrière. Elle a été testée sur une base d'essai (voir `recette-migrations.md`).

## Ce que le retour supprime et ce qu'il garde

| Élément | Après le retour |
|---|---|
| Projets, documents, segments, traductions, glossaires, mémoire, tâches et réglages de traduction | **Supprimés** (tables du module). Exportez d'abord ce que vous voulez garder (étape 2). |
| Notices, dossiers, annotations, sources, journal des dysfonctionnements, comptes | **Conservés**, inchangés |
| Propositions de traduction de notices (couche éditoriale) et traductions adoptées dans les notices | **Conservées**. Celles d'origine « Traduction automatique » apparaîtront avec le code brut « mt » en 1.2.0, qui les **inclurait dans les exports** même si l'option « Inclure traductions et contenus IA » est décochée. |
| Copies de glossaires envoyées à DeepL | Restent sur votre compte DeepL : supprimez-les avant (Traduction → Glossaires → « Supprimer la copie DeepL »). |
| Paquets Argos (volume `argos-packages`) | Inutilisés par la 1.2.0 ; effacés seulement par `reinitialiser-essai.ps1 -Complet`. |

## Procédure (installation d'essai, PowerShell, dans `C:\JaponExplorateur-essai-1.3.0`)

1. **Sauvegarde complète** : Administration → Sauvegardes → Lancer une sauvegarde, puis vérifier l'intégrité.
   Copiez-la hors du conteneur si vous voulez la garder (le script de réinitialisation le propose aussi).
2. **Vérification et copie des données de traduction** (lecture seule, rien n'est modifié) :
   ```powershell
   docker compose exec web python manage.py verifier_retour_120 --exporter /data/sauvegarde-traduction.json
   docker compose cp web:/data/sauvegarde-traduction.json .\sauvegarde-traduction.json
   ```
   Lisez le compte rendu : nombre de projets, de traductions, de contenus « Traduction automatique », de
   copies DeepL. Décidez de ce que vous faites des contenus « Traduction automatique » : les garder (en sachant
   qu'ils seront traités comme ci-dessus), ou les retirer vous-même dans la fiche des notices **avant** le retour.
   Supprimez les copies DeepL des glossaires si nécessaire. Exportez les projets utiles (Traduction → Exports).
3. **Arrêt de l'application** (la base reste démarrée) :
   ```powershell
   docker compose --profile hors-ligne stop web worker beat argos
   ```
4. **Annulation des migrations de la 1.3.0**, avec le code de la 1.3.0 (conteneur ponctuel) :
   ```powershell
   docker compose run --rm -e RUN_MIGRATIONS=0 web python manage.py migrate translation zero
   docker compose run --rm -e RUN_MIGRATIONS=0 web python manage.py migrate catalog 0004
   docker compose run --rm -e RUN_MIGRATIONS=0 web python manage.py migrate incidents 0001
   ```
   **`-e RUN_MIGRATIONS=0` est indispensable** : sans lui, le conteneur réappliquerait d'abord toutes les
   migrations de la 1.3.0 à son démarrage.
   `catalog.0005` et `incidents.0002` ne contiennent aucune instruction SQL (listes de choix seulement) ;
   `translation zero` supprime les tables du module.
5. **Code de la 1.2.0** : remplacez le contenu du dossier par l'archive `japon-explorateur-1.2.0.zip`, en
   **gardant votre `.env`** (ou, dans un dépôt Git : `git checkout v1.2.0-reference`). Ne changez pas
   `COMPOSE_PROJECT_NAME=japon-explorateur-essai-130` ni `WEB_PORT=8002` : la 1.2.0 utilisera ainsi la base qui
   vient d'être ramenée, sur le port 8002, sans toucher l'essai 1.2.0 (port 8001) ni l'installation principale.
   Le correctif inverse `retour-1.2.0/evolution-1.2.0-vers-1.3.0.patch` contient toutes les modifications de la
   1.3.0 : `git apply -R` le retire d'une copie de la 1.3.0.
6. **Redémarrage en 1.2.0** : `docker compose up -d --build`, puis vérifiez le pied de page (« v1.2.0 ») et
   `docker compose exec web python manage.py migrate --check` (aucune migration en attente).

## En cas de problème

Restaurez la sauvegarde de l'étape 1 (Administration → Sauvegardes), avec le code de la 1.3.0, puis signalez
le problème (Dysfonctionnements → Exporter le diagnostic).
