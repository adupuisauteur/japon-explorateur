# Recette — migrations aller-retour sur une base d'essai (test T21)

Exécutée le 14 novembre 2026 dans l'environnement de développement, sur une base PostgreSQL 16
**temporaire** (`japon_recette130`), créée pour l'occasion puis supprimée. Aucune base réelle n'a été touchée.
Données **fictives** uniquement. Scripts : `docs/evolution-1.3.0/recette/`.

## Méthode

L'empreinte de chaque ligne de chaque table est calculée en SQL (`md5` du contenu de la ligne), sans passer
par le code de l'application : la comparaison ne dépend donc ni de la 1.2.0 ni de la 1.3.0.

| Phase | Code utilisé | Opération |
|---|---|---|
| 1 | 1.2.0 (étiquette `v1.2.0-reference`, extraite par `git archive`) | Base neuve : `migrate`, `seed_sources`, données fictives (`recette/fixtures_120.py` : comptes, 5 notices, contenus éditoriaux humain et IA, tâche IA, dossier, incident, journal) → empreinte **A** |
| 2 | 1.3.0 | `migrate` → empreinte **B** |
| 3 | 1.3.0 | Usage fictif du module (`recette/fixtures_130.py`) : projet, document, traduction validée, glossaire, réglage Argos, **traduction automatique adoptée dans une notice** → empreinte **C** |
| 4 | 1.3.0 | `verifier_retour_120 --exporter …` (lecture seule) → empreinte identique à **C** |
| 5 | 1.3.0 | `migrate translation zero`, `migrate catalog 0004`, `migrate incidents 0001` → empreinte **D** |
| 6 | 1.2.0 | `check`, `migrate --check`, `showmigrations`, lecture des notices |

## Résultats

| Contrôle | Résultat |
|---|---|
| Migrations appliquées en phase 2 | `catalog.0005`, `incidents.0002`, `translation.0001`, `translation.0002` : OK |
| A → B : lignes perdues ou modifiées | **aucune** (55 tables de la 1.2.0 intactes) |
| A → B : ajouts | 13 tables du module ; lignes ajoutées seulement dans `django_migrations` (4), `django_content_type` (12) et `auth_permission` (48), créées automatiquement par Django pour les nouveaux modèles |
| `verifier_retour_120` | Base inchangée (empreinte avant = après) ; copie JSON écrite ; signale 1 proposition et 1 titre adopté d'origine « Traduction automatique » |
| C → D : tables supprimées | les 13 tables du module, et elles seules |
| C → D : autres lignes | seules les 4 lignes de `django_migrations` de la 1.3.0 ont disparu ; **toutes les autres tables sont identiques** |
| Phase 6 : la 1.2.0 sur la base revenue | `check` sans erreur ; **aucune migration en attente** ; notices, contenus éditoriaux et journal lisibles |
| A → D | Différences dues uniquement à l'usage fictif de la phase 3 (notice modifiée par l'adoption, proposition « mt », version de notice) et aux types de contenu laissés par Django (sans effet sur la 1.2.0) |

## Point d'attention confirmé

Après le retour, la 1.2.0 lit la traduction automatique adoptée avec l'origine brute « mt » (elle ne connaît
pas ce code) : la notice affiche « mt » et l'export de la 1.2.0 l'inclurait même si l'option « Inclure
traductions et contenus IA » est décochée. C'est pourquoi la procédure de retour (`retour-1.2.0.md`) demande de
lancer `verifier_retour_120` et de décider du sort de ces contenus **avant** le retour.

## Ce qui reste à vérifier sur votre poste (TR12)

Le même retour, dans l'installation d'essai sous Docker, en suivant `retour-1.2.0.md`.
