# J-ed 2.0.0 — Rapport du lot 0 : corrections et fiabilité

14 novembre 2026 · branche locale `evolution-2.0.0` · plan : `01-audit.md` (validé le 14 novembre 2026)

## 1. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Version et nommage (D3) | `VERSION` 2.0.0 ; images 2.0.0 ; `COMPOSE_PROJECT_NAME` obligatoire (Compose s'arrête avec un message, l'entrypoint aussi) ; port 8000 par défaut ; noms `japon-explorateur` et `japon-explorateur-essai` toujours protégés | `docker-compose.yml`, `docker/entrypoint.sh`, `.env.example`, `docker/argos/server.py` |
| Sauvegarde en ligne de commande | Code de sortie 1 en cas d'échec de la sauvegarde ou de la vérification ; message avec le type d'erreur réel ; incident journalisé | `apps/backups/management/commands/backup.py`, `apps/backups/services.py` |
| Restauration | Code 1 et type d'erreur en ligne de commande ; depuis l'interface, refus si la sauvegarde de sécurité échoue ; message exact sur les fichiers (D10) | `restore_backup.py`, `apps/backups/views.py`, `templates/backups/list.html` |
| Copie externe | Ne fait plus échouer la sauvegarde ; empreinte de la copie contrôlée ; avertissement et incident en cas d'échec | `apps/backups/services.py` |
| Sauvegardes visibles dans Windows | `DOSSIER_SAUVEGARDES` dans `.env` monté sur `/backups-externes` (web et worker) ; volume Docker par défaut ; dossier affiché sur la page Sauvegardes | `docker-compose.yml`, `docker/Dockerfile`, `config/settings.py` |
| Argos sans simulation silencieuse (D4) | Réglage « mode démonstration » (désactivé par défaut) ; sinon service injoignable = tâche **interrompue** et reprenable, paquets manquants = arrêt ; préparation et confirmation refusées tant que le service ne répond pas | `apps/translation/engines/argos.py`, `apps/translation/services.py`, `apps/core/models.py` |
| Listes de modèles d'IA | Pagination Anthropic (`after_id`) et Gemini (`pageToken`) ; jusqu'à 2 000 modèles ; pas de refus si la liste est tronquée | `apps/ai/providers.py`, `apps/ai/views.py`, `apps/ai/services.py` |
| Erreurs passées sous silence | Police PDF illisible, empreinte d'export, détection d'import : journalisées avec leur type | `pdf_gen.py`, `exports/services.py`, `updates/importers.py` |
| Page « État de l'installation » | 10 contrôles, diagnostic copiable, commande `etat_installation` (`--json`, code 1) ; signe de vie du planificateur toutes les 5 min | `apps/core/health.py`, `apps/core/tasks.py`, `templates/core/state.html`, `static/js/app.js` |
| Test de démarrage d'Argos | Phrase fictive traduite après une installation de paquet réussie et sur demande ; résultat sur la page « État » | `apps/translation/argos_selftest.py` |
| Mise à jour en une commande | `mettre-a-jour.ps1` (6 étapes contrôlées, arrêts clairs, marche à suivre pour revenir en arrière) | `mettre-a-jour.ps1` |
| Tests en parallèle | Dossier temporaire partagé supprimé une seule fois en fin d'exécution ; journal du service Argos écrit avant la réponse | `tests/helpers.py`, `docker/argos/server.py` |

**Base de données.** Deux migrations additives :

- `core.0002_argos_demo_mode` : un champ booléen, faux par défaut ;
- `core.0003_service_check` : une nouvelle table.

## 2. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète, exécution séquentielle | **440 tests réussis** (389 de la 1.3.0 – 5 remplacés + 56 nouveaux) |
| Suite complète, exécution parallèle (`--parallel 4`), 7 fois | **6 fois sur 7 : 440 réussis** (5 échecs à chaque fois en 1.3.0) ; **une fois**, un échec de `test_platform.test_quick_search_from_every_page_and_session` (voir § 4) |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration manquante |
| `docker compose config` (le client Docker fonctionne sans le service) | nom obligatoire, volume ou dossier Windows des sauvegardes (`D:\…` reconnu comme dossier de l'ordinateur), port 8000 |
| `mettre-a-jour.ps1` exécuté par PowerShell 7.4 sous Linux avec un faux `docker` | 10 scénarios : mise à jour complète, Argos redémarré, empreinte fausse, archive trop ancienne, retour en arrière refusé, échec de sauvegarde d'une 1.3.0 (code 0 mais « Échec »), nom protégé sans autorisation, destination existante, Docker arrêté, démarrage impossible |
| Page « État » avec un vrai worker Celery et un vrai Redis (hors Docker) | Redis « Répond », 1 worker, signe de vie reçu |
| Aller-retour des migrations sur une base temporaire (données fictives de la recette 1.3.0) | voir ci-dessous |

**Aller-retour des migrations.** Base PostgreSQL temporaire `jed_recette200`, créée puis supprimée. Les
empreintes sont calculées colonne par colonne en SQL, sans le code de l'application :

| Étape | Résultat |
| --- | --- |
| Code 1.3.0-rc3 : `migrate`, sources, données fictives 1.2.0 et 1.3.0, une sauvegarde → empreinte A | 68 tables, 396 lignes |
| Code 2.0.0 : `migrate` → empreinte B | 2 migrations appliquées ; **aucune ligne perdue ni modifiée** ; ajouts : table `core_servicecheck`, colonne `argos_demo_mode` (faux), lignes techniques de Django (`django_migrations` 2, `django_content_type` 1, `auth_permission` 4) |
| Code 2.0.0 : `migrate core 0001` → empreinte C | table et colonne retirées ; **toutes les données de A intactes** ; restent les 5 lignes techniques des types de contenu, sans effet |
| Code 1.3.0-rc3 sur la base revenue | `check` sans erreur, aucune migration en attente ; 5 notices, 1 projet, 1 glossaire lus |

## 3. Écarts et choix faits pendant le lot

- **Noms protégés** : la décision D3 citait l'installation principale. J'ai gardé aussi la protection de
  `japon-explorateur-essai`, comme en 1.3.0, parce que ton essai contient des données. Ton `.env` contient
  déjà `AUTORISER_NOM_PROJET`, donc rien ne change pour toi.
- **`reinitialiser-essai.ps1`** : ce script, propre à l'essai 1.3.0 (nom `japon-explorateur-essai-130`), est
  conservé tel quel avec ses tests. Il ne concerne pas une installation 2.0.0 ; le guide d'installation de la
  2.0.0 (lot 6) dira comment repartir de zéro.
- **Copies externes** : la rotation (14 sauvegardes conservées) ne s'applique qu'aux sauvegardes internes. Les
  copies dans le dossier Windows ne sont jamais supprimées par J-ed : à toi de faire le ménage. Je propose
  d'afficher leur nombre et leur taille sur la page « État » au lot 3, avec les réglages adaptés à la machine.
- **Sauvegarde sans copie externe** : « Aucune sauvegarde réussie » est un point « à surveiller », pas un
  « problème », pour qu'une installation neuve ne soit pas signalée en erreur avant sa première nuit.
- **Le script `mettre-a-jour.ps1` est livré à part**, à côté de l'archive, puisqu'il sert à la décompresser.
  Il est aussi dans l'archive, pour les mises à jour suivantes.
- **Grille TR1–TR12** : pas encore reçue ; ses anomalies seront traitées dès réception.

## 4. Points ouverts et vérifications à faire sur ton poste

- **Test instable en exécution parallèle** :
  - `test_quick_search_from_every_page_and_session` (recherche rapide sur la base locale) a échoué une fois sur
    sept exécutions parallèles de la suite complète : la notice fictive n'est pas trouvée ;
  - il réussit toujours en exécution séquentielle, qui est le mode de référence du projet, et il a réussi 6 fois
    sur 6 sur un sous-ensemble de tests en parallèle ;
  - la cause n'est pas identifiée. Je n'ai pas modifié ce test. Je reprends l'enquête au lot 9, qui touche à la
    recherche.

- Le script n'a été exécuté qu'avec PowerShell 7 sous Linux et un faux `docker`. Restent à vérifier sous
  Windows PowerShell 5.1 : les chemins Windows, `docker compose cp` et `Expand-Archive`. C'est l'objet du
  protocole V0-1 et V0-2.
- Le montage d'un dossier Windows (`DOSSIER_SAUVEGARDES`) et les droits d'écriture du conteneur sur ce dossier
  sont à vérifier sur ton poste (V0-5).
- L'interruption réelle d'Argos en cours de traduction est à vérifier sur ton poste (V0-6).
- La liste complète des modèles reste à vérifier avec une vraie clé (V0-8) : statut « testé en simulation ;
  test réel à confirmer ».

- **Guides pour débutant** (documents en ligne du 14 novembre 2026, installation et mise à jour) : décision
  de l'utilisateur, **à chaque lot qui ajoute des migrations, mettre à jour la commande de retour** de la section
  « Revenir à la version précédente » du guide de mise à jour (actuellement `migrate core 0001`).

- **Constats sur le poste de l'utilisateur (15 novembre 2026)**, après la mise à jour de l'essai par
  `mettre-a-jour.ps1` (réussie) :
  - le script croyait la sauvegarde en échec : Windows PowerShell 5.1 lisait les accents de Docker abîmés.
    Corrigé (lecture en UTF-8, motifs tolérants), archive `lot0c` ;
  - Argos : « Erreur interne (KeyError) ». Le diagnostic montre `KeyError: 'feat_dropout'` au chargement des
    modèles de découpage Stanza des paquets. Corrigé par un découpage par la ponctuation (`ARGOS_DECOUPAGE`),
    archive `lot0d`. Test réel refait sur le poste : **Argos traduit** (confirmé par l'utilisateur et par
    `verifier-j-ed.ps1`) ;
  - validation groupée des traductions (demande U1), archive `lot0e` ;
  - `verifier-j-ed.ps1` sur le poste : **26 vérifications OK, 0 à surveiller, 0 problème, 2 non vérifiées**.
    Une ligne contradictoire : « Argos : non activé » alors que le conteneur `argos` tournait. Le script de mise
    à jour démarrait Argos par `--profile hors-ligne` sans écrire `COMPOSE_PROFILES=hors-ligne` dans le
    nouveau `.env` : un simple `docker compose up -d` ne l'aurait plus démarré. Corrigé dans les deux scripts
    (ajout de la ligne à la mise à jour ; avertissement « À surveiller » à la vérification), archive `lot0f`.

## 5. Livrables du lot

- Archive intermédiaire `japon-explorateur-2.0.0-lot0.zip`, son empreinte `.sha256`, et `mettre-a-jour.ps1` à
  part.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 0 ».
- CHANGELOG : section 2.0.0, lot 0.
