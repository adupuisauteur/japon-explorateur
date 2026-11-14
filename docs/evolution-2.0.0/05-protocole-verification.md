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
