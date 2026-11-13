# Rapport technique final — Évolution 1.2.0

**Japon — Explorateur documentaire** · Sources documentaires et suivi des dysfonctionnements · 13 novembre 2026

| | |
|---|---|
| Version de départ | 1.1, commit `7cb40758` (affichée « 1.0.0 ») |
| Version livrée | **1.2.0**, numéro unique dans le fichier `VERSION` (application, rapports de diagnostic, sauvegardes, exports, image Docker, archive) |
| Périmètre | Module 1 (sources et recherche) et module 2 (journal) uniquement. Aucune refonte. Cartes mentales, graphe, traduction, multilingue, multi-utilisateur et IA non touchés. |
| Dépôt GitHub | **Non modifié** : rien n'a été poussé. Travail sur une branche locale `evolution-1.2.0`. |

---

## 1. Fonctions existantes conservées

Toutes : catalogue (œuvres, éditions, exemplaires, notices et versions), imports CSV/XLSX/JSON/MARC/DC avec rapport de comparaison, sessions de recherche (modes, décisions, relance et comparaison), bibliothèque, dossiers, annotations, exports (DOCX, PDF, TXT, JSON, CSV, site HTML, ZIP), sauvegardes et restaurations, module IA facultatif, PWA, sécurité (CSP, verrouillage des connexions, chiffrement des clés).

**Les 95 tests de la 1.1 passent.** Un seul a été adapté, pour refléter un changement demandé : une source qui répond HTTP 503 est désormais « indisponible », et non plus « erreur » générique (§2.7).

## 2. Fonctions ajoutées

### Module 1 — Sources et recherche
- **Cinq états distincts par source** : résultats, *aucun résultat* (jamais traité comme une erreur), *source indisponible*, *erreur technique* et *réponse impossible à interpréter*, plus *configuration incomplète*.
- **Nouveau connecteur CiNii Research** (API OpenSearch JSON-LD officielle), avec deux sources : CiNii Research et CiNii bibliothèques universitaires (type `books`). L'identifiant d'application est lu dans `.env` uniquement.
- **Archives nationales** préconfigurées via Japan Search (base `najda`).
- **« Trouver une base Japan Search »** : recherche des bases connectées (archives, universités, musées) par l'API officielle `/api/database/search`, puis création d'une source limitée à une base, désactivée tant qu'elle n'a pas été testée.
- **Japan Search corrigé** : variantes combinées en **OU** (`keyword=+A&keyword=+B`) au lieu de ET, champs conformes à la documentation (`titleYomi`, `location`, `iiifUrl`, `provider`…), filtre de dates `r-tempo`, personne `q-contributor`.
- **NDL amélioré** : lien vers le **document numérisé** (`rdfs:seeAlso` → dl.ndl.go.jp) ; l'échec d'une variante n'annule plus les résultats principaux.
- **Variantes de graphie** : saisie libre (« Mes variantes de graphie »), règle « nom sans suffixe » (女, 女房, 尼, 丸…), variantes **attestées** du référentiel des noms (`CreatorVariant`, existant mais inutilisé jusqu'ici).
- **Tri** par auteur et par institution détentrice ; **filtre** « document numérisé disponible » ; lien « Document numérisé / Images » sur chaque résultat.
- Un résultat dont les métadonnées ne peuvent pas être converties est **ignoré seul** : les autres sont conservés et l'incident est journalisé.

### Module 2 — Journal des dysfonctionnements
- Nouvelle application `apps/incidents`, transversale, appelée par un point d'entrée unique (`record_incident`, `record_connector_error`, `record_exception`, `record_database_error`).
- **Journalisation automatique** : recherche, connecteurs (tests, synchronisations), récupération des métadonnées, importation, base de données (gravité *Critique*), erreurs inattendues de page (signal Django `got_request_exception`).
- **Informations enregistrées (§3.3)** : identifiant `INC-AAAAMMJJ-XXXXXX`, dates, module, source, catégorie, gravité, opération, message, code technique, code HTTP, identifiant de requête (local, jamais transmis), version de l'application, statut, origine probable, contexte expurgé.
- **Origine probable** expliquée en langage courant : application, connecteur, source distante, réseau, traitement des données.
- **Regroupement** par empreinte, compteur d'occurrences, **réouverture automatique** d'un incident corrigé qui se reproduit, comparaison **avant / après correction**, et note « source de nouveau disponible ».
- **Pages** : journal filtrable (date, module, source, gravité, statut, type, recherche par identifiant d'incident ou de requête), détail, suivi des statuts (administrateur), **signalement manuel** avec capture d'écran, **analyse** (récurrences, sources instables, connecteurs en échec, incidents par version, réapparitions, pannes simultanées), **export de diagnostic** (Markdown ou JSON) avec aperçu contrôlé et masquage optionnel des termes de recherche.
- Accès : menu **Dysfonctionnements** (pastille des nouveaux incidents graves), lien **Signaler un problème** en pied de page, bloc d'historique sur chaque fiche de source.
- **Confidentialité** : expurgation avant écriture et à l'export (paramètres sensibles des adresses, dont `appid` ; en-têtes d'authentification ; chaînes de connexion ; clés de type `sk-…` ; adresses e-mail ; dossiers personnels Windows, macOS et Linux). Aucune télémétrie. Le journal reste dans la base locale.

### Socle
- Fichier `VERSION` unique. Correction de l'affichage « 1.0.0 ».
- **Isolation de l'installation d'essai** : nom de projet Docker `japon-explorateur-essai` (volumes séparés), port 8001, image `japon-explorateur:1.2.0`. Dans la 1.1, le nom de projet fixe aurait fait réutiliser la base de l'installation principale.
- `pypdf` ajouté aux dépendances : il était requis par deux tests de la 1.1 mais absent.

## 3. État des connecteurs

| Connecteur / source | Statut |
|---|---|
| Base locale | **Opérationnel** (local, pas de service externe) |
| NDL Search | **Développé et testé en simulation — test réel à confirmer** |
| Japan Search (toutes bases) | **Développé et testé en simulation — test réel à confirmer** |
| Archives nationales (Japan Search, `najda`) | **Développé et testé en simulation — test réel à confirmer** |
| Bases créées via « Trouver une base Japan Search » | **Développé et testé en simulation — test réel à confirmer** (par base) |
| CiNii Research | **Développé et testé en simulation — test réel à confirmer** (identifiant CiNii requis) |
| CiNii bibliothèques universitaires | **Développé et testé en simulation — test réel à confirmer** (même identifiant) |
| Kokusho (NIJL) | Existant ; gestion des erreurs **testée en simulation — test réel à confirmer** |
| Testé en conditions réelles | **Aucun** (réseau japonais inaccessible depuis l'environnement de développement) |
| Non intégrés (consultation externe ou import) | Waseda, Kyoto, Tokyo HI/SHIPS, NIJL bases spécialisées, Nichibunken, presse ancienne, CODH (import existant), NDL Digital Collections (liens via NDL Search). Archives préfectorales et municipales selon leur présence dans Japan Search. |

Lors du test de bout en bout réalisé ici, de vrais appels vers NDL et Japan Search ont été refusés par le filtre réseau de l'environnement. L'application a correctement affiché « Source indisponible » et journalisé deux incidents d'Avertissement. **Cela valide la chaîne de traitement des échecs, pas les connecteurs eux-mêmes.**

## 4. Tests exécutés

Environnement : Python 3.13, Django 5.2, PostgreSQL 16, sous Linux. **Résultat : 128 tests, tous réussis**, avec `DJANGO_DEBUG=true` puis `false`.

| Exigence §6.3 | Test exécuté | Résultat |
|---|---|---|
| Un test par connecteur développé | Réponse normale enregistrée pour NDL, Japan Search, Archives nationales, CiNii, CiNii bibliothèques ; manifeste illisible pour Kokusho | Réussi (simulation) |
| Absence de résultat | Les 5 sources : état « aucun résultat », aucun incident | Réussi |
| Indisponibilité | HTTP 503 (5 sources), délai dépassé, échec DNS (origine « réseau ») ; sources indépendantes les unes des autres | Réussi |
| Réponse mal formée | Les 5 sources + Kokusho : état « réponse illisible », extrait conservé | Réussi |
| Journalisation | Regroupement, réapparition après correction, avant/après, retour de la source, erreur de conversion, erreur de base (critique), erreur de page, requête vide (pas d'incident), secret CiNii jamais écrit | Réussi |
| Consultation et export | Filtres, recherche par identifiant d'incident ou de requête, fiche de source, export Markdown et JSON, masquage des termes, signalement manuel avec capture, droits (lecteur : 403 sur le statut) | Réussi |
| Conservation du catalogue | Note personnelle et favori intacts après intégration d'une version modifiée ; versionnement de l'ancien titre ; aucune notice créée par une erreur | Réussi |
| Migration sur base d'essai | Base 1.1 avec données fictives → sauvegarde de référence vérifiée → migration 1.2.0 → données identiques ; retour en 1.1 (`migrate incidents zero`) puis remontée | Réussi |
| Démarrage et redémarrage | Gunicorn en mode production : 13 pages contrôlées (HTTP 200, pied de page v1.2.0), recherche réelle, signalement manuel et export via le navigateur ; arrêt puis relance : incidents, notices et notes persistants | Réussi (hors Docker) |
| Version unique | `VERSION` = `settings.APP_VERSION` = étiquette d'image = pied de page | Réussi |
| Configuration Docker | `docker compose config` : projet `japon-explorateur-essai`, port 8001, image 1.2.0 | Réussi (validation hors ligne) |
| Script `reinitialiser-essai.ps1` | PowerShell 7.4 sous Linux, avec de vrais volumes Docker de test pour l'essai et pour une « installation principale » simulée : annulation, 4 refus de sécurité (nom principal, nom sans « essai », port 8000, `.env` absent), Docker arrêté, effacement en mode normal et en mode `-Complet` (image de l'essai supprimée, image et volumes de l'installation principale intacts) | Réussi. Non testés : la sauvegarde avant effacement et le redémarrage final (aucun conteneur ne peut tourner ici), et l'exécution sous Windows PowerShell 5.1 |

## 5. Tests non exécutés

| Test | Raison | Où le faire |
|---|---|---|
| Tests réels des connecteurs (NDL, Japan Search, Archives nationales, Kokusho, CiNii ×2) | Serveurs japonais inaccessibles depuis l'environnement de développement (choix de ne pas modifier ses autorisations) | Protocole, C1 à C8 |
| Construction et démarrage Docker | Registre Docker Hub inaccessible depuis l'environnement de développement | Guide d'installation ; protocole V1, V2, V12 |
| Fonctionnement sous Windows 11 / Docker Desktop / WSL2 | Pas de poste Windows dans l'environnement de développement | Guide d'installation |
| CiNii avec un véritable identifiant | Aucun identifiant fourni (et aucune clé réelle ne doit être intégrée) | Protocole C5, C6, V9 |

## 6. Problèmes connus

**Corrigé le 13/11/2026 : incident INC-20261113-41FDF0, signalé lors de l'installation sous Windows.** Le clic sur « Comparer avec la base et produire le rapport » provoquait une erreur 500.
- **Cause** : kombu 5.7.0, installé automatiquement avec Celery (versions non figées), importe le module `packaging` sans le déclarer comme dépendance. Sous Docker, la tâche est confiée au worker par Redis, et l'import échoue. Les tests exécutaient les tâches sans worker (mode « eager ») et ne pouvaient donc pas voir le problème. Toute reconstruction récente de la 1.1 aurait le même défaut.
- **Correction** : `packaging>=23.0` est ajouté à `requirements.txt`. Un test de non-régression importe le transport Redis. Le scénario a été reproduit, puis vérifié corrigé, avec Redis et un vrai worker Celery (comparaison puis intégration des deux fichiers d'exemple).
- **Amélioration associée** : chaque erreur de page reçoit désormais un identifiant de requête.

Le journal des dysfonctionnements a joué son rôle : le rapport exporté indiquait le module manquant et le fichier en cause.

Aucun autre test ne révèle d'anomalie dans le code livré. Les points d'incertitude sur les formats réels sont listés dans `02-etude-sources.md` §3, et les limitations dans `07-limitations-connues.md`.

## 7. Fichiers principaux modifiés ou ajoutés

- **Ajoutés** : `VERSION`, `reinitialiser-essai.ps1`, `apps/incidents/` (modèles, services, rapport, vues, formulaires, administration, migration), `apps/connectors/cinii.py`, `templates/incidents/*`, `templates/connectors/jps_databases.html`, `tests/test_evolution_120.py`, `tests/fixtures/reponses/*`, `docs/evolution-1.2.0/*`, `CHANGELOG.md`.
- **Modifiés** : `apps/connectors/{base,http,ndl,japansearch,kokusho,registry,views,urls}.py`, `apps/searching/{services,views}.py`, `apps/updates/{services,views}.py`, `apps/catalog/search.py`, `apps/core/{logging,context_processors}.py`, `apps/core/templatetags/app_tags.py`, `apps/core/management/commands/seed_sources.py`, `config/{settings,urls}.py`, `docker-compose.yml`, `.env.example`, `requirements.txt`, quelques gabarits et la feuille de style.
- Le détail ligne à ligne figure dans `docs/evolution-1.2.0/retour-1.1/evolution-1.1-vers-1.2.0.patch`.
