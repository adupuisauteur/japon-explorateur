# J-ed 2.0.0 — Rapport du lot 2 : trois statuts indépendants par notice

15 novembre 2026 · branche `evolution-2.0.0` · plan : `01-audit.md`, § 3.3 et § 5.1 (validé le 14 novembre
2026) · cahier des charges : § 5

## 1. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Modèle de données | Table `catalog_recordstatus` : une ligne par notice et par statut (`notice`, `document`, `iiif`), avec valeur, origine, date, adresse et détail, plus le suivi d'une vérification IIIF demandée | `apps/catalog/models.py`, migration `catalog.0006` |
| Calcul des statuts | Règles par source, à partir des champs et des données brutes déjà enregistrés, sans appel réseau (§ 3). Recalcul à chaque enregistrement d'une notice ; une vérification faite par J-ed est conservée tant que l'adresse du manifeste ne change pas | `apps/catalog/statuses.py` |
| Notices existantes | Migration de données : statuts calculés pour toutes les notices, sans appel réseau ni modification des notices ; relançable sans doublon ; le retour vide la table | migration `catalog.0007` |
| Vérification IIIF | Manifeste téléchargé, conformité à l'API de présentation 2.x ou 3.0, nombre de vues, accès à l'image de la première vue (quelques kilo-octets, rien n'est conservé). Collection : le premier manifeste est contrôlé. Résultat « vérifié » ou « vérification en échec », avec la raison | `apps/catalog/iiif.py`, `apps/connectors/http.py` (`probe`) |
| Suivi et reprise | Demande inscrite en base avant tout appel réseau ; traitement une notice à la fois, délai réglable entre deux notices (`IIIF_CHECK_DELAY_SECONDS`, 2 s) en plus du délai propre à chaque source ; verrou contre deux traitements simultanés ; reprise automatique toutes les 10 minutes ; chaque échec inscrit au journal des dysfonctionnements | `apps/catalog/iiif.py`, `apps/catalog/tasks.py`, `config/settings.py` |
| Pastilles | Trois pastilles distinctes (Notice, Document, IIIF) dans les résultats de recherche, la Bibliothèque et la fiche ; au survol : origine, date et détail | `apps/core/templatetags/app_tags.py`, `templates/searching/_results.html`, `templates/library/index.html` |
| Filtres et tri | Résultats d'une recherche et Bibliothèque : un filtre par statut et un tri par statut. Recherche avancée (base locale) : trois groupes de cases. Ils remplacent « Document numérisé » et « Accès numérique » ; l'ancienne adresse `?digital=1` vaut « Document consultable : oui » | `apps/searching/views.py`, `apps/searching/forms.py`, `apps/catalog/search.py`, `apps/library/views.py`, `templates/partials/status_filters.html` |
| Fiche | Section « Disponibilité » : les trois statuts avec origine, date, adresse, détail, vérification en attente ; bouton « Vérifier le manifeste IIIF » (chercheur et administrateur) | `templates/catalog/_statuses.html`, `apps/catalog/views.py` |
| Sélection | Bouton « Vérifier IIIF » dans la barre de sélection de la Bibliothèque ; les notices sans manifeste connu sont comptées à part | `apps/library/views.py` |
| Vérification automatique | Nouveau contrôle « Statuts des notices » : trois statuts calculés pour une notice fictive, lecture d'un manifeste fictif sans appel réseau, nombre de notices sans statut, répartition IIIF et vérifications en attente | `apps/core/verification.py` |

**Base de données** : deux migrations, toutes deux additives.

- `catalog.0006_statuts_notice` crée la table `catalog_recordstatus`.
- `catalog.0007_statuts_notices_existantes` la remplit.

Les notices ne sont pas modifiées. L'ancien champ `digital_access` et sa règle de la 1.2.0 sont conservés pour
les exports au format 1.0, mais ne servent plus aux statuts.

## 2. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète, exécution séquentielle | **536 tests réussis** (503 à la fin du lot 1 + 33 nouveaux ; 1 test de la 1.2.0 adapté, voir § 4) |
| Suite complète, exécution parallèle (`--parallel 4`), 4 fois | **3 fois sur 4 : 536 réussis** ; une fois, un échec du test instable connu `test_quick_search_from_every_page_and_session` (voir § 5), qui réussit seul et en exécution séquentielle |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration manquante |
| Aller-retour 1.3.0 → 2.0.0 → 1.3.0 sur une base temporaire | voir ci-dessous |
| Contrôle visuel (Chrome sans interface, base temporaire, notices fictives) | fiche avec la section « Disponibilité », Bibliothèque triée par IIIF : conformes |

**Aller-retour des migrations.** Base PostgreSQL temporaire `jed_recette202`, créée puis supprimée. Les
empreintes sont calculées colonne par colonne en SQL.

| Étape | Résultat |
| --- | --- |
| Code 1.3.0-rc3 : `migrate`, sources, 9 notices fictives couvrant chaque cas (Japan Search avec et sans manifeste, Kokusho, NDL avec et sans numérisation, CiNii, fichier importé déclaré, consultation sur place, base locale), mises en Bibliothèque → empreinte A | 68 tables, 392 lignes |
| Code 2.0.0 : `migrate` → empreinte B | 5 migrations appliquées (`catalog.0006` et `0007`, `core.0002` à `0004`) ; **aucune ligne perdue ni modifiée** ; ajouts : tables `catalog_recordstatus` (27 lignes) et `core_servicecheck`, colonne `argos_demo_mode`, lignes techniques de Django |
| Statuts calculés | conformes aux règles du § 3 pour les 9 cas |
| Code 2.0.0 : `migrate catalog 0005` puis `migrate core 0001` → empreinte C | tables et colonne retirées ; **toutes les données de A intactes** |
| Code 1.3.0-rc3 sur la base revenue | `check` sans erreur, aucune migration en attente, 9 notices et 9 entrées de Bibliothèque lues |

**Nouveaux tests** (`tests/test_statuts_200.py`, 33 tests) :

- règles de calcul pour chaque source et chaque cas, y compris l'indépendance des statuts et le résultat d'une
  recherche non enregistré ;
- recalcul à l'enregistrement : vérification J-ed conservée, puis remplacée quand le manifeste change ;
  demande abandonnée dans ce cas ;
- migration de données : aucun appel réseau, notices inchangées, relance sans doublon, retour ;
- lecture des manifestes IIIF 2.x, 3.0 et des collections, et documents non conformes ;
- vérification réussie, image refusée (HTTP 403, avec incident), réponse qui n'est pas du JSON, image qui
  n'en est pas une, réseau coupé, collection ;
- reprise après interruption, ordre de traitement, verrou, délai entre notices, notices sans manifeste ;
- interface : fiche, droits du lecteur, bouton de la fiche, Bibliothèque (pastilles, filtre, tri, sélection),
  recherche locale, formulaire de recherche, résultats d'une session (filtre, tri, résultats antérieurs à la
  2.0.0), pastilles.

## 3. Règles de calcul (à relire)

Principe : un « oui » ou un « absent » n'est retenu que si la source le dit. Sinon : « non vérifié ».

| Source | Notice disponible | Document consultable | IIIF |
| --- | --- | --- | --- |
| Japan Search | oui (adresse de la notice fournie) | **oui** si la source publie une adresse de contenu numérique ou un manifeste ; sinon non vérifié (une vignette ne suffit pas) | identifié (manifeste indiqué) ; sinon **absent** |
| Kokusho, notice lue sur son manifeste officiel | oui | **oui** si le manifeste décrit des images | identifié, origine source |
| Kokusho, notice trouvée par la recherche | oui | non vérifié | identifié, **origine « déduit »** (adresse construite, D5) |
| NDL | oui | **non vérifié** même avec un lien de numérisation : la NDL ne précise pas si l'accès est libre, réservé aux bibliothèques ou sur place | identifié (manifeste indiqué) ; non vérifié si numérisée sans manifeste ; sinon absent |
| CiNii | oui | non vérifié (texte intégral signalé, accès libre non garanti) | non vérifié |
| Fichier importé | oui si l'adresse de la notice est fournie | oui ou non si le fichier contient la valeur ; non vérifié si J-ed l'avait complétée | identifié si l'adresse contient « manifest » ; sinon non vérifié |
| Base locale | non (pas de notice en ligne) | non vérifié | non vérifié |
| Toutes | non, origine J-ed, si la notice a été retirée par la source ; non vérifié si l'adresse a été construite par J-ed | **non**, avec la mention de la source, si les conditions d'accès signalent une consultation réservée (館内, 図書館送信, sur place…) | — |

Deux choix méritent ton avis :

- **Japan Search** : une adresse de contenu numérique publiée par la source vaut « document consultable : oui ».
  C'est le sens de ce champ, mais je n'ai pas pu le confirmer sur des notices réelles (pas d'accès à Internet
  ici).
- **NDL** : toute notice numérisée reste « non vérifié » côté document. C'est prudent, mais nombreux : beaucoup
  de documents de la NDL sont en accès libre sur Internet. Une vérification du document lui-même pourra venir
  au lot 3, avec les tâches.

## 4. Écarts et choix faits pendant le lot

- **Suivi de la vérification IIIF** : l'audit prévoyait « une tâche suivie en base ». J'ai ajouté à la table
  validée deux champs de suivi (`check_requested_at`, `check_requested_by`) plutôt qu'une table de tâches. Les
  tâches générales (file programmée, file de nuit) viennent au lot 3 sur `TranslationJob` (décision D6) ; la
  vérification IIIF pourra s'y brancher.
- **Échec réseau** : une source injoignable donne « vérification en échec », avec la raison (« Manifeste
  injoignable : … »), plutôt qu'une nouvelle tentative indéfinie. La vérification se relance d'un clic.
- **Test adapté** : `test_ndl_digitized_link_and_jps_fields` (1.2.0) vérifiait qu'une notice NDL avec un lien de
  numérisation passait le filtre « Document numérisé ». Ce n'est plus le cas, par conception (§ 3) : le test
  vérifie désormais « non vérifié » et l'exclusion de cette notice.
- **Exports** : les statuts ne figurent pas encore dans les exports, qui gardent l'ancien champ « accès
  numérique » (format 1.0). Les y ajouter changerait le format d'export : à décider.
- **Recherches enregistrées** avant la 2.0.0 avec le filtre « Accès numérique » : le filtre continue de
  s'appliquer, mais le formulaire ne le propose plus.

## 5. Points ouverts

- Test instable `test_quick_search_from_every_page_and_session` : un nouvel échec en exécution parallèle (1 sur
  4), comme au lot 0. Il ne touche pas les statuts. L'enquête reste prévue au lot 9.
- Vérification IIIF réelle sur des manifestes en ligne : à faire sur ton poste (protocole V2-3 et V2-4).
- Les deux choix du § 3 (Japan Search, NDL).
- Statuts dans les exports (§ 4).

## 6. Correctif après livraison (archive `lot2b`)

Avant que tu lances `verifier-j-ed.ps1 -AvecTests`, j'ai simulé ici les conditions du conteneur : vrai Redis,
dossiers de l'installation, variables de ton `.env`. Résultat : la suite de tests aurait déposé **5 sauvegardes
fictives** dans ton dossier Windows des sauvegardes, nommées comme de vraies sauvegardes, et envoyé 4 tâches
d'essai à la file Redis de l'installation. Deux tests échouaient aussi, pour des raisons d'environnement.

**Correction** (`config/settings.py`) : en mode test, les éléments suivants sont isolés, quelles que soient les
variables du conteneur :

- dossier de données et fichiers dans un dossier temporaire, supprimé à la fin ;
- copie externe des sauvegardes désactivée ;
- file de tâches en exécution immédiate et cache en mémoire ;
- Argos, adresses d'IA locales et clé CiNii vidés.

Un test vérifie cette isolation (`TestIsolationTests`). Nouvelle simulation : **537 tests réussis, aucun fichier
écrit dans les dossiers de l'installation, aucune entrée dans Redis**.

Les tests utilisent une base de données de test distincte (`test_japon`), créée puis supprimée par Django : la
base de l'installation n'est jamais touchée.

## 7. Livrables du lot

- Archives `japon-explorateur-2.0.0-lot2.zip`, puis `lot2b` (correctif du § 6), avec leur empreinte `.sha256`.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 2 » (V2-1 à V2-5).
- CHANGELOG : section 2.0.0, lot 2.
- Guide de mise à jour : retour vers la 1.3.0, désormais en deux commandes (`migrate catalog 0005`, puis
  `migrate core 0001`), avec les résultats attendus.
