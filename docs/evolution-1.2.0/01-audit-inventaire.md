# Évolution 1.2.0 — Audit préalable et inventaire des connecteurs

*Audit limité aux deux évolutions demandées (cahier des charges du 13 novembre 2026, §2.2 et §6.1).*

## 1. Version de départ

| Élément | Valeur |
|---|---|
| Dépôt | `adupuisauteur/japon-explorateur` (GitHub, privé) |
| Commit de départ | `7cb40758e54f23383559994957147c31455161c7` — « Version 1.1 : application complète et 13 corrections de l'audit » |
| Étiquette locale | `v1.1-reference` (posée sur ce commit, non poussée) |
| Numéro affiché par l'application | `1.0.0` (incohérence : le commit et la documentation parlent de 1.1) |
| Socle | Django 5.1, PostgreSQL 15, Celery + Redis, HTMX + Bootstrap 5, Docker Compose |
| Tests existants | 95 tests ; 93 réussis et 2 en erreur dans l'environnement d'essai, faute du module de test `pypdf` (dépendance de test absente de `requirements.txt`, sans lien avec le code applicatif) |

## 2. Connecteurs existants

Tous respectent le même contrat (`apps/connectors/base.py`). Un registre (`registry.py`) les rend indépendants, et une couche HTTP commune (`http.py`) gère les délais, la limite de débit, le cache et les reprises.

| Source | Accès utilisé | Recherche | Format | État constaté | Limites relevées |
|---|---|---|---|---|---|
| Base locale | PostgreSQL (index trigrammes) | Plein texte, champs, dates | Modèle interne | Opérationnel | — |
| NDL Search | API OpenSearch officielle | Plein texte, titre, auteur, sujet, dates ; variantes interrogées séparément (2 au plus) | RSS 2.0 + DC-NDL | Développé, **jamais testé en conditions réelles** | Le lien vers le document numérisé (`rdfs:seeAlso` → dl.ndl.go.jp) n'est pas lu |
| Japan Search | API web simple (`/api/item/search/jps-cross`) | Mot-clé | JSON | Partiel, **jamais testé en conditions réelles** | 1) Les variantes sont jointes par une espace, donc combinées en **ET** au lieu de **OU** (moins de résultats quand on ajoute des variantes). 2) Plusieurs noms de champs ne correspondent pas à la documentation officielle (`spatial`, `iiifManifestUrl`, `owner`, `subject`). |
| Kokusho (NIJL) | Manifeste IIIF officiel + Japan Search filtré | Mot-clé (via Japan Search), notice par identifiant | IIIF v2/v3, JSON | Partiel, **jamais testé en conditions réelles** | Dépend de l'identifiant de base Japan Search |
| CODH PMJT, Classeur | Import de fichiers | — | CSV/XLSX | Opérationnel (import) | Instantané historique |
| Archives nationales, Waseda, Kyoto, Tokyo HI/SHIPS, NIJL spécialisées, Nichibunken… | Aucun | — | — | Répertoriées « À étudier » | Aucun connecteur |

## 3. Composants réutilisables

- **Gestion des sessions de recherche** (`apps/searching`) : sources interrogées une à une, une source en panne n'empêche pas les autres, état par source, filtres, tri, dédoublonnage, intégration au catalogue **avec historisation, sans écrasement silencieux**, relance et comparaison.
- **Variantes de graphie** (`apps/catalog/search.py`, `apps/core/japanese.py`) : NFKC, shinjitai et kyūjitai, kana, rōmaji. La table `CreatorVariant` (variantes de noms attestées) existe mais n'est pas utilisée pour la recherche.
- **Champs de notice** (`Record`) : source, identifiant original, titre, auteur, dates, type, description, lien vers la notice, lien vers le document, date de collecte, données brutes. Ils couvrent déjà le §2.6, **sans modification nécessaire du modèle**.
- **Masquage des secrets** dans les journaux techniques (`apps/core/logging.py`).
- **Numéro de version** déjà centralisé dans `settings.APP_VERSION` (pied de page, sauvegardes, exports, cache PWA), mais avec une valeur erronée.

## 4. Mécanisme de sauvegarde

Commandes `backup --verify` et `restore_backup` : `pg_dump` + fichiers + manifeste SHA-256. La restauration se fait en une transaction, avec sauvegarde de sécurité automatique. Le mécanisme est réutilisable tel quel avant toute mise à niveau.

## 5. Risques directs pour les données existantes

1. **Risque majeur : partage des volumes Docker.** `docker-compose.yml` fixe `name: japon-explorateur` et l'image `japon-explorateur:1.0`. Une copie de la nouvelle version lancée sur le même PC **réutiliserait la base de l'installation principale** et y appliquerait les migrations, et la construction remplacerait son image. → Corrigé dans la 1.2.0 : nom de projet, port et image propres à l'installation d'essai.
2. Port 8000 déjà pris par l'installation principale → l'installation d'essai écoute sur le port 8001.
3. Le lancement exécute automatiquement les migrations (`entrypoint.sh`). C'est sans danger grâce au point 1, puisque seule la base d'essai est concernée.

## 6. Décisions qui en découlent

- **Aucune modification des tables existantes.** Le journal ajoute ses propres tables (application `incidents`).
- Conservation de tous les connecteurs. Corrections ciblées de Japan Search et NDL, ajout de CiNii Research et des bases institutionnelles via Japan Search.
- Le numéro de version est lu dans un fichier unique, `VERSION` (1.2.0).
