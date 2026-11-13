# Évolution 1.3.0 — Version de départ et isolation

## Version de départ

| Élément | Valeur |
|---|---|
| Version de départ | **1.2.0** |
| Commit | `4982a3dc574b5950bf65f1fd508ecc897a584144` (`4982a3d`) |
| Branche GitHub de la 1.2.0 | `evolution-1.2.0` (`adupuisauteur/japon-explorateur`), non modifiée |
| Étiquettes locales | `v1.2.0` et `v1.2.0-reference`, toutes deux sur `4982a3d` |
| Archive de référence | `japon-explorateur-1.2.0.zip`, SHA-256 `be6bd9dcbf4475726ad0026d67bfab6f8f2dd599b65a990d45ec54ee2e1d2e55` |
| Contrôle | Contenu du commit `4982a3d` comparé fichier par fichier à l'archive : 283 fichiers, aucune différence |
| Branche de travail | `evolution-1.3.0`, créée depuis `4982a3d` |
| Branche `main` | Inchangée (version 1.1, `7cb4075`) |

## Revenir à la 1.2.0

- Code : `git switch evolution-1.2.0` (ou `git checkout v1.2.0-reference`). Rien de la 1.3.0 n'y est fusionné.
- Installation : l'essai 1.2.0 garde son dossier, son `.env`, son projet Docker (`japon-explorateur-essai`), son port (8001) et ses volumes. L'essai 1.3.0 ne les utilise jamais.

## Isolation de l'installation d'essai 1.3.0

| | Principale | Essai 1.2.0 | Essai 1.3.0 |
|---|---|---|---|
| Projet Docker (`COMPOSE_PROJECT_NAME`) | `japon-explorateur` | `japon-explorateur-essai` | `japon-explorateur-essai-130` |
| Port web (`WEB_PORT`) | 8000 | 8001 | 8002 |
| Image | `japon-explorateur:1.0` | `japon-explorateur:1.2.0` | `japon-explorateur:1.3.0` |
| Dossier conseillé | — | `C:\JaponExplorateur-essai-1.2.0` | `C:\JaponExplorateur-essai-1.3.0` |

- Les volumes PostgreSQL et fichiers sont préfixés par le nom du projet : ils sont donc distincts. Redis n'a pas de volume ; chaque projet a son propre conteneur Redis.
- **Garde-fou au démarrage** : les conteneurs `web`, `worker` et `beat` refusent de démarrer si le projet s'appelle `japon-explorateur` ou `japon-explorateur-essai` (variable `COMPOSE_PROJECT_CHECK`, contrôlée par `docker/entrypoint.sh`). Le refus intervient **avant toute migration**, donc sans écriture dans la base d'une autre installation.
- Limite connue : avec un mauvais nom de projet, Docker Compose remplace quand même les conteneurs applicatifs de l'autre installation avant que le garde-fou ne les arrête. Les données ne sont pas touchées, mais l'autre installation reste arrêtée jusqu'à ce qu'on la relance depuis son propre dossier (`docker compose up -d`).
- **Script `reinitialiser-essai.ps1`** : il refuse désormais aussi l'essai 1.2.0 (nom de projet et port 8001), en plus de l'installation principale.

## Numéro de version

Le numéro est lu dans le seul fichier `VERSION` (`1.3.0`). Il se propage automatiquement à l'interface, au journal des dysfonctionnements, aux rapports de diagnostic, aux sauvegardes, aux exports, au cache hors ligne et à l'identifiant envoyé aux sources. Les mentions « 1.2.0 » qui datent une fonction dans le code et la documentation de la 1.2.0 sont conservées.
