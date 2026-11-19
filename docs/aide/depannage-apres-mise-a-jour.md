---
titre: Dépannage après une mise à jour
rubrique: Installation et mises à jour
ordre: 30
public: admin
resume: Les problèmes les plus courants après une mise à jour, et leur solution.
---
Commencez toujours par [Vérifier l'installation](aide:verifier-l-installation) : la page « État » et
`verifier-j-ed.ps1` disent le plus souvent ce qui ne va pas.

| Ce que vous voyez | Que faire |
| --- | --- |
| L'ancienne version, ou une page sans le nouveau logo | Rechargez avec **Ctrl + F5** : le navigateur garde une copie de l'interface |
| « J-ed ne répond pas » | Attendez une ou deux minutes (premier démarrage). Sinon, dans le dossier : `docker compose ps`, puis `docker compose logs --tail 200 web` |
| « Fichier .env : la ligne … figure 2 fois » | Gardez une seule ligne, mettez `#` devant les autres, puis `docker compose up -d`. Remplacez aussi votre `mettre-a-jour.ps1` par le plus récent : voir [Mettre à jour J-ed](aide:mettre-a-jour) |
| Argos « non démarré » | La ligne `COMPOSE_PROFILES` de `.env` doit contenir `argos` (par exemple `COMPOSE_PROFILES=argos` ou `argos,ollama`), puis `docker compose up -d` |
| IA locale « non installée » alors que vous l'utilisez | Même ligne : elle doit contenir `ollama`. Les modèles déjà téléchargés sont conservés |
| IA locale « Essai automatique en attente » | Normal dans les minutes qui suivent la mise à jour : J-ed refait l'essai environ 2 minutes après le démarrage. Rechargez la page ensuite |
| « Vérification dans l'application : réponse illisible » | Transmettez le rapport : les lignes « Cause », « Début » et « Erreur » permettent de trouver l'origine |
| Des tâches « En retard — à confirmer » | Normal : leur heure (ou la plage de nuit) est passée pendant l'arrêt. Ouvrez Tâches, puis confirmez, reprogrammez ou annulez |
| L'icône de l'application installée n'a pas changé | Désinstallez puis réinstallez l'application depuis le navigateur |
| Un message « ARRÊT » du script de mise à jour | Lisez la ligne qui suit : elle dit quoi faire. Avant l'étape 5, rien n'a été modifié |

## Revenir à la version précédente

Si la nouvelle version ne convient pas, suivez la section « Revenir à la version précédente » du **guide de mise à
jour**. L'ancien dossier n'a pas été modifié ; vos données sont dans Docker, et la sauvegarde faite avant la mise à
jour est dans votre dossier de sauvegardes.

## Demander de l'aide

Joignez le rapport de `verifier-j-ed.ps1` et le texte de **Copier le diagnostic** (page « État »). Aucun des deux ne
contient de données personnelles ni de texte de recherche.
