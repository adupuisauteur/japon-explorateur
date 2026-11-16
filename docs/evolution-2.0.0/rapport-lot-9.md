# Rapport du lot 9 — performances (2.0.0)

*État : étapes 1 (mesure) et 2 (corrections issues de la mesure) livrées.*

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

## 3. Étape 2 (16 novembre 2026) : résultats de la mesure sur le poste de l'utilisateur

### 3.1 Mesure

| Mesure (50 000 notices fictives, médiane de 5) | Durée | Requêtes |
| --- | --- | --- |
| Recherche libre, 2 caractères | 111 ms | 2 |
| Recherche libre, 4 caractères | 120 ms | 2 |
| Critère Titre | 137 ms | 2 |
| Critère Auteur | 132 ms | 2 |
| Détection des doublons d'une notice | 75 ms | 2 (**0 candidat**) |
| Calcul de la consommation (300 tâches) | 25 ms | 4 |
| Page Bibliothèque (2 000 notices) | 57 ms | 14 |
| Page d'une fiche | 43 ms | 26 |
| Page Consommation | 94 ms | 12 |
| Page Rechercher | 23 ms | 11 |

Sur les 3 555 notices réelles : 5 à 17 ms. **Conclusion : aucune lenteur.** Toutes les mesures restent sous
140 ms à 50 000 notices, soit quatorze fois le volume actuel. Aucun index ni cache supplémentaire n'est justifié :
ils compliqueraient le code sans gain perceptible. La recherche libre de 4 caractères renvoie plus de réponses que
celle de 2 caractères parce que les titres fictifs contiennent souvent 藤原定家 : c'est un effet des données
fictives, pas une erreur.

### 3.2 Défaut révélé : doublons non trouvés au-delà de quelques milliers de notices

« 0 candidat » n'était pas normal. Reproduit avec les mêmes 50 000 notices : 4 180 notices partagent le début du
titre de la notice mesurée, dont 206 ont un titre assez semblable pour être des doublons possibles. La détection
n'en examinait que 200, **les premières par ordre alphabétique**, et aucune des 206 n'en faisait partie. Avec
3 555 notices le défaut ne se voyait pas ; il serait apparu avec la croissance de la base.

Correction : les 200 notices examinées sont choisies par ressemblance du titre (similarité trigramme de
PostgreSQL, extension pg_trgm et index déjà en place depuis la 1.x). Sur les mêmes données : 168 des 200 notices
examinées sont de vrais candidats, en 30 ms. Un test place 400 notices au début de titre identique avant le vrai
doublon : il échoue avec l'ancien code et réussit avec le nouveau.

### 3.3 IA locale : « Résumé d'essai en échec » juste après une mise à jour

Rapport de vérification de 20 h 26, une minute après la mise à jour de 20 h 25. Au démarrage, J-ed refait l'essai
environ 2 minutes plus tard. La vérification a donc lu l'essai précédent, qui datait d'avant le correctif 3 et
avait échoué. L'IA locale fonctionnait (constat de l'utilisateur). La page « État de l'installation » distingue
maintenant trois cas :
- l'essai en échec date d'avant le démarrage du conteneur, et l'essai automatique n'a pas encore eu lieu :
  « Essai automatique en attente », avec l'heure prévue (à surveiller, pas un problème) ;
- un vrai résumé par l'IA locale a réussi depuis l'essai en échec : « Prête » ;
- sinon : « Résumé d'essai en échec », comme avant.

L'heure de démarrage est celle du processus n° 1 du conteneur (lue dans `/proc`) ; si elle est illisible, rien ne
change. `verifier-j-ed.ps1` affiche aussi la cause et la date de l'essai en échec, pour Argos et l'IA locale.
Les chemins de dossiers ne sont pas repris, car ils peuvent contenir un nom de compte Windows.

### 3.4 Tests de recherche instables

Lors de cette étape, 8 tests de `test_search_sessions` ont échoué ensemble, deux fois, dans des suites complètes
lancées juste après un redémarrage de PostgreSQL. Les sources y étaient en « error » et les résultats absents.
Isolés, ces tests réussissent. 12 autres suites complètes, dont 8 après un redémarrage, ont toutes réussi. La cause
n'est pas encore établie. En cas de nouvel échec, ces tests affichent désormais l'état de chaque source et les
incidents enregistrés, trace comprise. Ce défaut touche les tests, pas l'application installée : aucun
signalement de l'utilisateur ne s'en approche.

### 3.5 Tests

Suite complète : **707 tests réussis**.

## 4. Suite du lot

Les mesures ne justifient pas d'autre optimisation. Reste du lot : la cause des tests instables, quand le
diagnostic l'aura donnée.

## 5. Livrables


- Étape 1 : `japon-explorateur-2.0.0-lot9-etape1.zip` et son empreinte `.sha256`.
- Étape 2 : `japon-explorateur-2.0.0-lot9-etape2.zip` et son empreinte `.sha256`.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 9 » (V9-1 à V9-5).
