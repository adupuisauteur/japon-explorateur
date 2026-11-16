# J-ed 2.0.0 — Rapport du lot 4 : résumés IA, IA locale et japonais ancien

16 novembre 2026 · branche `evolution-2.0.0` · cahier des charges : § 7 · demandes U8, U9, U10
(`02-demandes-utilisateur.md`)

## 1. Décisions prises au début du lot (15 novembre 2026)

| Point | Décision |
| --- | --- |
| Types de résumé | Trois : court, détaillé, fiche d'analyse (thèmes, personnes, lieux, dates) |
| Langue du résumé | Toujours celle de l'utilisateur : français par défaut, autre langue sur demande. « Il faut que ce soit compréhensible dans la langue de l'utilisateur » |
| Texte lu | L'original japonais par défaut. Un résumé fait d'après une traduction non validée le dit |
| Exports | Case « Inclure les résumés IA », décochée par défaut ; résumés toujours marqués « généré par IA » |
| Enchaînement (U9) | À la confirmation d'une traduction : « juste après chaque traduction » ou « après l'ensemble ». La nuit, « après l'ensemble » est imposé si Argos et l'IA locale travailleraient en même temps. Le coût des résumés est compris dans ce qui est confirmé |
| IA locale (U8) | Service Ollama facultatif. Modèle choisi dans une courte liste avec sa taille, téléchargé après confirmation dans une tâche suivie et reprenable, puis résumé d'essai. Le choix du modèle conseillé se fera après l'essai réel sur ton poste |
| Japonais ancien (U10) | Repérage automatique (bungo, kanbun, sōrōbun) présenté comme « probable », que tu confirmes ou corriges. Réglage « Pour le japonais ancien, utiliser… » pour les traductions et les résumés. Tâche mixte en deux parties confirmées ensemble ; jamais de changement de moteur silencieux ; plafond atteint = pause |

## 2. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Résumés | Modèle `Summary` : notice ou document, type, langue, texte lu (et son empreinte), variété, contenu, données de la fiche d'analyse, fournisseur, modèle, nombre d'appels, auteur. Une nouvelle demande crée une nouvelle version ; les précédentes sont gardées et consultables | `apps/ai/models.py`, migration `ai.0004_resumes` |
| Tâche de résumé | Un résumé est une tâche de la file du lot 3 (type « Résumés IA »), un élément par notice ou document. Un texte long est découpé en parties (6 000 caractères ; 3 000 avec l'IA locale), chaque partie est résumée, puis une synthèse donne le résumé final. Les résumés partiels sont gardés : une reprise ne renvoie rien. Avant chaque appel : fin de plage de nuit et budget IA (pause, jamais d'autre moteur). Chaque appel est tracé (tâche IA, jetons, coût) | `apps/translation/summaries.py`, `services.py` |
| Consigne | En français, réponse JSON, rédaction dans la langue choisie, mention des limites ; variété du texte signalée (bungo, kanbun, sōrōbun) ; raisonnement des modèles Qwen3 désactivé et retiré de la réponse | `summaries.py` |
| Écrans | Fiche : section « Résumés IA » (dernier résumé par type et langue, « Résumer maintenant », bouton lune pour la nuit) ; Bibliothèque : actions « Résumer maintenant » et « Résumer cette nuit » ; atelier d'un document : « Résumer » ; page « Résumés IA » (liste, détail, versions) ; rubrique sur l'accueil Traduction | `views/summaries.py`, `_summaries.html`, `summary_detail.html`, `summary_list.html` |
| Réglages | Traduction → Moteurs : IA des résumés, type et langue par défaut ; « Pour le japonais ancien, utiliser… » (traduction et résumés) | `forms.py`, `engines.html`, migration `translation.0004` |
| Enchaînement (U9) | Écran de confirmation d'une traduction : « Résumer aussi » (type, langue, chaque ou ensemble, appels et coût estimé). Problème des résumés = rien ne part (tout ou rien). Le jour : résumés lancés à la fin de la traduction ; annulés avec elle. La nuit : placés juste après la traduction, ou après toutes les traductions de la file | `summaries.chain`, `queue.py`, `views/jobs.py`, `_job_status.html` |
| Exports | Case « Inclure les résumés IA des notices », décochée ; jamais si les contenus générés sont exclus ; ligne « Résumés IA » dans la méthodologie. Les résumés de documents de projets restent dans le projet (ils peuvent être confidentiels) | `apps/exports/document.py`, `views.py`, `generators/common.py` |
| IA locale (U8) | Service `ollama` (profil du même nom, image officielle version 0.30.9 fixée, aucun port publié, un modèle chargé à la fois, déchargé après 5 minutes sans demande, limites `OLLAMA_COEURS` et `OLLAMA_MEMOIRE_MAX`). Moteurs locaux, section « IA locale » : état, trois modèles avec taille et mémoire, « Installer » après confirmation, « Essai », « Supprimer » après confirmation. Téléchargement suivi (pourcentage, battement de cœur) et reprenable ; résumé d'essai et notification à la fin. Ligne « IA locale » sur la page « État » et dans `verifier-j-ed.ps1`. L'IA locale n'a pas de clé : elle n'apparaît pas dans IA → Fournisseurs | `apps/ai/local.py`, `providers.py`, `views/local_engines.py`, `docker-compose.yml`, `.env.example`, `apps/core/health.py`, `verifier-j-ed.ps1` |
| Japonais ancien (U10) | Repérage par règles : signes de lecture du kanbun, texte presque sans kana avec mots-outils chinois, style épistolaire en 候, formes du japonais classique (けり, べし, なり, 旧仮名…). Fiche : bandeau « Japonais classique (bungo) — probable » avec les indices, « Confirmer » ou corriger ; atelier : suggestion pour un document encore « moderne ». Une confirmation n'est jamais remplacée par un nouveau repérage | `apps/translation/variety.py`, `_variety.html`, modèle `RecordVariety` |
| Tâches mixtes | Avec un moteur choisi pour le japonais ancien : les textes anciens partent dans une tâche sœur vers ce moteur ; l'écran de confirmation montre les deux parties (éléments, caractères, moteur, coût) ; elles partent ensemble ou aucune (problème, conditions à lire, seconde confirmation vérifiés pour les deux) ; annuler l'une annule l'autre. La variété est aussi transmise à l'IA de traduction | `services._prepare_routed`, `confirm`, `_job_status.html` |
| Confidentialité | Projet confidentiel : résumés seulement par l'IA locale, comme pour la traduction ; résumé d'un document confidentiel invisible des autres utilisateurs | `summaries.problems`, `views/summaries.py` |

**Base de données.** Trois migrations additives :
- `ai.0004_resumes` : table des résumés ; fournisseur « IA locale » ;
- `translation.0004_resumes_et_textes_anciens` : options des tâches, document et données des éléments, 9 réglages,
  table des variétés de notices ;
- `translation.0005_retour_arriere_resumes` : migration de données seule (rien à l'aller).

## 3. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète | **664 tests réussis** (631 + 33) |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration manquante |
| Migration aller-retour (base temporaire, données fictives, supprimée ensuite) | voir § 4 : erreur trouvée et corrigée ; au retour, tâches de résumé non terminées annulées, lancement « après » devenu « immédiat », notice conservée ; remontée sans erreur |
| `docker compose config` réel | avec `COMPOSE_PROFILES=argos,ollama` : service `ollama` présent ; avec `argos` seul : absent |
| `verifier-j-ed.ps1` sous PowerShell 7 (Docker simulé) | IA locale « non installée (facultative) » par défaut ; conteneur attendu avec le profil ; signalée si elle tourne sans la ligne |
| Navigateur réel (Chrome, base temporaire, faux service Ollama) | fiche avec fiche d'analyse ; fiche d'un texte classique : bandeau « probable » et ses indices ; confirmation d'une tâche mixte en deux parties avec « Résumer aussi » ; Moteurs locaux, section IA locale ; page résumé ; aucune erreur serveur |

**Nouveaux tests** (`tests/test_resumes_400.py`, 32 tests ; 1 test ajouté dans `test_verification_200.py`) :
- **résumés** : de bout en bout sur une notice (consigne, original lu, bloc de raisonnement retiré, tâche IA et coût, notification, nouvelle version) ; fiche d'analyse en anglais ; document long en parties puis synthèse, coupure au 2e appel et reprise sans rien renvoyer ; problèmes bloquants ; budget vérifié avant chaque appel ;
- **écrans et file** : confirmation ou départ direct sous le seuil ; file de nuit ; Bibliothèque, atelier, lecteur refusé ; projet confidentiel (IA en ligne refusée, IA locale permise, résumé privé) ;
- **exports** : rien sans la case ; avec la case, mais pas si les contenus générés sont exclus ; marqué et dans la méthodologie ;
- **enchaînement** : proposition à la confirmation ; traduction puis résumé ; problème des résumés = rien ne part ; nuit « ensemble » (après toutes les traductions) et « chaque » (juste après) ; Argos + IA locale = « ensemble » ; traduction annulée = résumés annulés ;
- **IA locale** (faux service) : absente du profil ; installation suivie puis essai ; téléchargement coupé puis repris ; droits et confirmation de suppression ; liste des modèles et page Fournisseurs ; gratuite, parties plus petites ;
- **japonais ancien** : règles de repérage ; suggestion puis correction (jamais remplacée) ; résumés en deux parties ; traduction sans réglage inchangée ; tâche mixte (deux parties, tout ou rien) ; consigne « classique » transmise à l'IA ; tout ancien vers le moteur ancien ; correction de l'utilisateur prioritaire.

## 4. Écarts et choix faits pendant le lot

- **Erreur trouvée par l'aller-retour des migrations, corrigée.** Le retour arrière de `translation.0004` échouait sous PostgreSQL : la mise à jour des tâches et la modification de la table étaient dans la même transaction (« pending trigger events »). La mise à jour des données est passée dans sa propre migration, `translation.0005`, qui s'exécute d'abord au retour. Les commandes de retour du guide de mise à jour ne changent pas (`migrate translation 0002` défait aussi 0004, 0005 et `ai.0004`). **Au retour arrière, les résumés et les variétés confirmées sont effacés** (leurs tables n'existent pas avant) : la sauvegarde faite avant la mise à jour les contient.
- **Projets confidentiels.** Je n'avais pas prévu cette règle pour les résumés au départ ; je l'ai ajoutée en cours de lot, alignée sur la traduction : une IA en ligne est refusée, l'IA locale permise.
- **Repérage « probable » utilisé pour répartir une tâche mixte.** Il n'y a pas de changement silencieux : l'écran de confirmation montre les deux parties et rappelle qu'on peut corriger la variété sur la fiche avant de confirmer. Les variétés sont repérées à l'affichage, pas enregistrées pour toutes les notices ; seules tes confirmations le sont.
- **Version d'Ollama fixée à 0.30.9** (publiée le 15 juin 2026, relevé GitHub), changeable par `OLLAMA_VERSION`. Je n'ai pas pu la télécharger d'ici : à vérifier en V4-5.
- **Tailles des modèles** (2,5 / 5,2 / 1,4 Go) relevées dans la bibliothèque Ollama ; durée et qualité réelles inconnues tant que l'essai n'est pas fait sur ton poste (V4-6, V4-7). C'est cet essai qui décidera du modèle conseillé.
- **Repérage du japonais ancien** : règles testées sur des textes fictifs ou classiques courts seulement. Statut : testé en simulation ; à régler avec les notices anciennes que tu me signaleras (V4-8).
- **Retour à la ligne des parties** : un texte est coupé de préférence à une fin de ligne ou de phrase japonaise (。) ; aucune partie ne dépasse la taille fixée.
- **Test instable connu** (`test_search_sessions`) : de nouveau un échec en exécution parallèle, puis réussi seul et dans les trois suites complètes suivantes. Toujours pour le lot 9.
- **Vérification réelle** (vraie IA en ligne, vrai service Ollama et vrai modèle) : V4-1 à V4-9. Statut : testé en simulation ; test réel à confirmer.

## 5. Correctif du 16 novembre 2026 (après installation)

Signalé sur ton poste : dans Traduction → Moteurs, « Résumés : fournisseur IA » = IA locale, « Actualiser la liste »
ne faisait rien de visible. Cause : pour l'IA locale, l'actualisation relisait les modèles installés sans afficher
l'état du service ; sans service (profil `ollama` absent de `COMPOSE_PROFILES`) ou sans modèle, la liste restait
vide et « Liste jamais actualisée » ne changeait pas. Correction : le sélecteur affiche la raison (IA locale non
installée et la ligne à ajouter, service injoignable, ou aucun modèle installé) avec le lien vers Moteurs locaux,
et l'actualisation est datée. Deux tests ajoutés (666 tests réussis). Archive : `japon-explorateur-2.0.0-lot4-correctif1.zip`.

**Deuxième point du même jour** : ton `.env` contenait deux lignes `COMPOSE_PROFILES` (`argos,ollama`, puis plus bas
`hors-ligne`). Docker ne retient que la dernière : Ollama ne pouvait pas démarrer. Rien ne le signalait, et
`verifier-j-ed.ps1` lisait la première ligne, donc le contraire de Docker. Correction : les deux scripts lisent la
dernière ligne, comme Docker, et signalent toute variable présente plusieurs fois (test ajouté). Archive :
`japon-explorateur-2.0.0-lot4-correctif2.zip`, qui contient aussi le premier correctif.

**Troisième point du même jour** : un résumé en cours était annoncé « 1 traduction en cours » dans la barre de menu.
L'indicateur dit maintenant « 1 résumé en cours », ou « 1 traduction et 1 résumé en cours » (test ajouté, 668 tests
réussis). Archive : `japon-explorateur-2.0.0-lot4-correctif3.zip`, qui contient aussi les deux premiers correctifs.

**Quatrième point du même jour** : premier résumé réel avec qwen3:4b (tâche n° 15) en échec, « La réponse de l'IA
n'est pas au format JSON attendu ». La réponse reçue n'était pas conservée, la cause exacte n'est donc pas prouvée.
Causes probables, toutes traitées :
- le modèle Qwen3 raisonne avant de répondre ; l'API compatible OpenAI d'Ollama ne permet pas de le désactiver de façon
  sûre, et ce raisonnement pouvait épuiser la limite de longueur (800 jetons pour un résumé court) avant la réponse ;
- rien n'imposait une sortie JSON ;
- la fenêtre de contexte par défaut d'Ollama peut tronquer sans avertissement un passage long et sa consigne.

Correction : appel par l'API native (`/api/chat`) avec `think: false`, `format: "json"` et `num_ctx` 8 192
(réglable par `OLLAMA_NUM_CTX`). Toute réponse illisible montre désormais son début dans l'erreur ; une réponse vide ou
réduite au raisonnement est nommée comme telle. Trois tests ajoutés (671 tests réussis). Statut : testé en
simulation ; test réel = « Relancer les échecs » sur la tâche n° 15. Archive : `japon-explorateur-2.0.0-lot4-correctif4.zip`,
qui contient aussi les correctifs 1 à 3.

## 6. Livrables du lot

- Archive `japon-explorateur-2.0.0-lot4.zip` et son empreinte `.sha256`.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 4 » (V4-1 à V4-9).
- CHANGELOG : section 2.0.0, lot 4.
