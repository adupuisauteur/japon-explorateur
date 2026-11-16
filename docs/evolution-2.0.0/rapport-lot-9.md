# Rapport du lot 9 — performances (2.0.0)

*État : étape 1 livrée (mesure). Les optimisations suivantes dépendent des mesures faites sur le poste de
l'utilisateur.*

## 1. Démarche

Optimiser sans mesure risque de compliquer le code pour un gain nul. Le lot commence donc par un outil de mesure
qui tourne sur le poste réel, avec le matériel et les données réels. Seules ces mesures décident des optimisations.

## 2. Étape 1 (16 novembre 2026)

### 2.1 Commande `mesurer_performances`

`docker compose exec web python manage.py mesurer_performances [--notices 50000] [--essais 5] [--json]`

1. Recherches en **lecture seule** sur la base réelle, dans une transaction annulée : recherche libre de 2 et
   4 caractères, critère Titre, critère Auteur.
2. Création d'une **base temporaire** (`<base>_mesures_<n>`, nom vérifié différent de la base réelle), migrations,
   puis 50 000 notices fictives (titres, auteurs et institutions tirés au hasard d'une graine fixe), 2 000 notices
   en bibliothèque, 300 tâches de traduction fictives du mois (aucun envoi).
3. Mesures : les quatre recherches, la détection des doublons d'une notice, le calcul de la consommation, puis les
   pages Bibliothèque, fiche, Consommation et Rechercher.
4. Suppression de la base temporaire, **même en cas d'erreur** (bloc `finally`).

Chaque mesure est répétée (5 fois par défaut) ; la médiane est retenue, avec le nombre de requêtes SQL.

Essai dans l'environnement de développement (5 000 notices fictives, 3 essais) : toutes les mesures entre 20 et
72 ms ; la fiche fait 26 requêtes, la Bibliothèque 14. Sur 50 000 notices réelles de développement : 59 à 204 ms
selon la recherche. Ces chiffres ne valent pas pour le poste de l'utilisateur.

### 2.2 Page Consommation

L'ancien calcul faisait deux à trois requêtes **par tâche** du mois (coût de la version, tâche IA, projet). Le
nouveau en fait un nombre fixe : une lecture groupée des éléments terminés (avec coût, devise, simulation, données
éditoriales) et une lecture groupée des tâches IA, dédoublonnées par couple (tâche IA, tâche de traduction).
Tests : six requêtes au plus, identiques pour 9 et 45 tâches ; résultats identiques à l'ancien calcul, conservé
dans les tests comme référence.

### 2.3 Test instable

`test_quick_search_from_every_page_and_session` a échoué une fois, sans se reproduire ensuite (7 suites complètes
en parallèle, 10 boucles). En cas de nouvel échec, le message donne désormais : codes HTTP, sources de la session,
état de chaque source, nombre de résultats en base, notices et catalogues. La cause pourra être corrigée au vu de
ce diagnostic plutôt que devinée.

### 2.4 Sécurité des données

- La base réelle n'est jamais écrite : lecture seule, transaction annulée.
- La base temporaire porte un nom distinct, vérifié ; le mode interne (`--interne`) refuse de tourner dans une base
  dont le nom ne contient pas `_mesures_`.
- Aucune donnée réelle n'est copiée ; tout est fictif.
- Aucun service externe n'est appelé.

### 2.5 Tests

8 tests ajoutés (`tests/test_performances_900.py`), dont la commande complète : base temporaire créée puis
supprimée, base courante inchangée. Suite complète : **703 tests réussis**.

## 3. Suite du lot

Selon les mesures de l'utilisateur :
- recherche par critère (Titre, Auteur) si elle dépasse quelques centaines de millisecondes : index trigramme sur
  les champs normalisés ;
- doublons : index trigramme pour le rapprochement des titres ;
- pages à beaucoup de requêtes (fiche) : regroupement des lectures.

## 4. Livrables de l'étape 1

- Archive `japon-explorateur-2.0.0-lot9-etape1.zip` et son empreinte `.sha256`.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 9 » (V9-1 à V9-3).
