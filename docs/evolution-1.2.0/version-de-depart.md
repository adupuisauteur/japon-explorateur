# Version de départ et possibilité de retour

## Identification précise de la version de départ

| Élément | Valeur |
|---|---|
| Dépôt | `github.com/adupuisauteur/japon-explorateur` (privé) |
| Commit | `7cb40758e54f23383559994957147c31455161c7` |
| Message | « Version 1.1 : application complète et 13 corrections de l'audit » |
| Numéro affiché par la 1.1 | 1.0.0 (incohérence corrigée dans la 1.2.0) |
| Migrations de la 1.1 | toutes les applications existantes ; **aucune n'est modifiée par la 1.2.0** |

Le dépôt GitHub **n'a pas été modifié** : rien n'y a été poussé. La 1.1 y reste disponible telle quelle (bouton *Code → Download ZIP* sur ce commit).

L'archive livrée contient `docs/evolution-1.2.0/retour-1.1/evolution-1.1-vers-1.2.0.patch`, la liste exacte de toutes les modifications par rapport à ce commit.

## Ce que la 1.2.0 change dans la base de données

Une seule migration : `incidents.0001_initial`. Elle **ajoute** trois tables (incidents, occurrences, historique) et ne modifie aucune table existante. La commande `seed_sources` ajoute deux sources (CiNii Research, CiNii bibliothèques universitaires) **uniquement si elles n'existent pas**. Les sources déjà configurées ne sont jamais modifiées.

## Retour à la 1.1

**Installation d'essai.** Aucun retour n'est nécessaire : supprimez-la (`docker compose down -v` dans *son* dossier). L'installation principale n'a jamais été touchée.

**Plus tard, si l'installation principale est mise à niveau en 1.2.0** (hors du périmètre de cette livraison), le retour se fait ainsi, testé sur une base d'essai le 13/11/2026 :
1. Avant la mise à niveau : **Administration → Sauvegardes → Lancer une sauvegarde**, puis vérification de l'intégrité.
2. Pour revenir en arrière : `docker compose exec web python manage.py migrate incidents zero`. Cette commande supprime uniquement les tables du journal.
3. Remettez en place le code de la 1.1, puis `docker compose up -d --build`.
4. En cas de doute, restaurez plutôt la sauvegarde de l'étape 1 avec la commande `restore_backup` de la 1.1.

Résultat du test de retour : la base 1.1 avec des données fictives (5 notices, 1 note, 1 favori) a été migrée en 1.2.0, ramenée en 1.1 avec `migrate incidents zero`, puis remontée en 1.2.0. Le code 1.1 démarre sans migration en attente, et les données sont restées identiques à chaque étape.
