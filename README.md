# Japon — Explorateur documentaire

Application web progressive (PWA) de recherche, de gestion et d'exploitation de ressources documentaires japonaises, développée d'après le cahier des charges v1.2 du 12 novembre 2026.

**Version 2.0.0 — en cours de développement** (fichier `VERSION`), renommée **J-ed**, à partir de la 1.3.0-rc3 (étiquette `v1.3.0-rc3`, commit `d7296d4`) : version de consolidation. Audit et plan : `docs/evolution-2.0.0/01-audit.md` ; avancement : `CHANGELOG.md`.

> **Nom et port de l'installation (2.0.0) :** `COMPOSE_PROJECT_NAME` est **obligatoire** dans `.env` (plus de nom par défaut) ; pour mettre à jour une installation, gardez exactement le nom de son `.env` actuel, et utilisez de préférence `mettre-a-jour.ps1` (sauvegarde, empreinte, reprise du `.env`, contrôle final). Les noms `japon-explorateur` et `japon-explorateur-essai` restent protégés (`AUTORISER_NOM_PROJET`). Port par défaut : 8000 (`WEB_PORT`).

**Stack :** Django 5 · PostgreSQL · HTMX + Bootstrap 5 (sans framework front lourd) · Celery + Redis · Docker Compose · python-docx · ReportLab.

---

## 1. Installation (Windows, macOS, Linux)

Prérequis : [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ou Docker Engine sous Linux).

```bash
# 1. Décompresser l'archive, puis dans le dossier du projet :
cp .env.example .env            # sous Windows : copy .env.example .env
#    puis renseigner COMPOSE_PROJECT_NAME (obligatoire, par exemple « jed ») dans .env

# 2. Générer les secrets et les recopier dans .env
docker compose run --rm --no-deps web python manage.py generate_secrets
#    → DJANGO_SECRET_KEY=…  AI_KEYS_ENCRYPTION_KEY=…  POSTGRES_PASSWORD=…  SETUP_TOKEN=…
#    (SETUP_TOKEN n'est obligatoire qu'en accès distant HTTPS)

# 3. Démarrer
docker compose up -d --build

# 4. Ouvrir http://localhost:8000   (port réglable par WEB_PORT dans .env)
```

Au premier accès, un **assistant de première configuration** crée le compte administrateur, enregistre le mode d'enregistrement par défaut (« Sélectif » recommandé), active la sauvegarde quotidienne et répertorie toutes les sources du §5.1. Il ouvre ensuite l'assistant d'import.

Services lancés : `web` (Gunicorn), `worker` (Celery : synchronisations, exports, IA), `beat` (planification : actualisations, purge des sessions temporaires, sauvegarde quotidienne), `db` (PostgreSQL, non exposé), `redis`.

> **Sécurité au démarrage :** hors mode développement (`DJANGO_DEBUG=false`), l'application **refuse de démarrer** si `DJANGO_SECRET_KEY` est absente, trop courte ou laissée à sa valeur d'exemple, ou si le mot de passe PostgreSQL d'un serveur distant est faible. Avec `SECURE_HTTPS=true`, `SETUP_TOKEN` est exigé : l'assistant de première configuration le demande avant de créer le compte administrateur.

> **Important :** conservez `DJANGO_SECRET_KEY` et `AI_KEYS_ENCRYPTION_KEY` hors des sauvegardes. Sans la seconde, les clés API enregistrées deviennent illisibles. Il suffira alors de les ressaisir.

### Installation PWA
Dans Chrome ou Edge : icône « Installer » de la barre d'adresse. Sur iPhone : Partager → « Sur l'écran d'accueil ». L'interface est mise en cache. Les fiches marquées « Hors ligne » restent consultables sans connexion.

### Sans Docker (développement)
```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # ajouter DATABASE_URL=postgres://… (ou laisser vide pour SQLite d'essai) et DJANGO_DEBUG=true
python manage.py migrate && python manage.py seed_sources
python manage.py runserver
```
Sans Redis, les tâches s'exécutent immédiatement, de façon synchrone (mode `CELERY_EAGER`). Les actualisations planifiées exigent `celery beat`.

---

## 2. Premiers pas

1. **Importer l'inventaire CODH 2019** : *Sources → Importer un fichier*, source « CODH — PMJT (inventaire 2019) ». L'assistant détecte le format et l'encodage (UTF-8, Shift-JIS, EUC-JP) et propose la correspondance des colonnes à partir de noms japonais, français ou anglais courants. Vérifiez-la, puis cliquez sur *Comparer avec la base* : un rapport s'affiche (nouvelles, modifiées, inchangées, doublons potentiels, erreurs). Validez ensuite globalement ou sélectivement. **Rien n'est écrit avant cette validation.**
2. **Importer le classeur central** de la même façon, source « Classeur documentaire central » (XLSX : choix de la feuille).
3. **Activer Kokusho** : *Sources → Kokusho Database → Tester le connecteur*. Le test vérifie l'accès IIIF officiel et tente de **détecter l'identifiant de la base Kokusho dans Japan Search**. Cliquez ensuite sur « Enregistrer ce paramètre ».
4. **Rechercher** : depuis l'accueil ou la barre du haut. Les sources répondent une à une, et une source en panne n'empêche pas les autres d'afficher leurs résultats. Retenez ou excluez les résultats (avec motif), puis *Intégrer la sélection* en bibliothèque ou dans un dossier.
5. **Dossiers et exports** : *Dossiers → Nouveau dossier*, sous-sections et notes, puis *Préparer un export* (DOCX, PDF, TXT, JSON, CSV, site HTML autonome, ZIP) avec prévisualisation.

Des fichiers d'exemple **fictifs** (illustratifs, non bibliographiques) se trouvent dans `docs/exemples/`.

---

## 3. Sources et connecteurs

| Source | État (inchangé depuis la 1.2.0) | Méthode |
|---|---|---|
| Base locale | Opérationnel | Recherche PostgreSQL (index trigrammes) sur les champs normalisés |
| **NDL Search** | Développé et testé en simulation — **test réel à confirmer** | API OpenSearch officielle ; lien vers le document numérisé (dl.ndl.go.jp) |
| **Japan Search** | Développé et testé en simulation — **test réel à confirmer** | API web simple officielle (variantes en OU, période, personne) |
| **Archives nationales** | Développé et testé en simulation — **test réel à confirmer** | Japan Search, base `najda` |
| **CiNii Research** et **CiNii bibliothèques universitaires** | Développé et testé en simulation — **test réel à confirmer** | API OpenSearch officielle ; identifiant gratuit `CINII_APPID` dans `.env` |
| **Kokusho Database** (国書データベース) | Partiel — **test réel à confirmer** | Manifeste IIIF officiel + Japan Search filtré sur le fonds Kokusho |
| CODH PMJT, classeur | Import | Fichiers fournis, instantané historique signalé |
| Autres archives, universités, musées | Via « Trouver une base Japan Search » si l'institution y diffuse sa base, sinon consultation externe | Voir `docs/evolution-1.2.0/02-etude-sources.md` |

Chaque source affiche dans une session : résultats, *aucun résultat* (ce n'est pas une erreur), *source indisponible*, *erreur technique* ou *réponse impossible à interpréter*. Les échecs sont enregistrés dans le **journal des dysfonctionnements** (menu « Dysfonctionnements »).

Kokusho ne publie pas, à ma connaissance, d'API de recherche documentée. Le connecteur n'aspire donc aucune page HTML : il utilise le manifeste IIIF officiel de chaque notice et l'agrégateur national Japan Search. **À vérifier lors de la première mise en service**, car ces services n'étaient pas joignables depuis l'environnement de développement : l'adresse et les noms de paramètres de l'API Japan Search (modifiables dans *Sources → Japan Search / Kokusho → Paramètres du connecteur*), ainsi que les libellés de métadonnées des manifestes IIIF Kokusho. Le code de lecture est tolérant (IIIF v2 et v3, libellés japonais et anglais), et les tests le valident sur des réponses simulées.

Tant qu'aucun test réel n'a réussi, chaque connecteur porte le badge **« Non vérifié en conditions réelles »** (fiche de la source, formulaire de recherche, état des sources d'une session). Le badge disparaît après un « Tester le connecteur » réussi ; la date est conservée.

**Ajouter un connecteur** : créer une classe dérivée de `apps/connectors/base.py:BaseConnector` (méthodes `search`, `fetch_record`, éventuellement `harvest`), la décorer par `@register`, puis l'ajouter à `registry._load()`. Le reste de l'application (recherche, sessions, mises à jour, exports) n'a pas à être modifié.

---

## 4. Intelligence artificielle (facultative)

- Valeurs initiales (AT-IA-01) : mode **À la demande**, traduction, résumé et détection des doublons proposés, classification désactivée.
- *Préférences IA* : profils multiples (créer, dupliquer, activer, supprimer), mode Désactivée / À la demande / Confirmation systématique, fournisseur et modèle par défaut **ou par fonction**, plafond mensuel estimé.
- *Fournisseurs et clés API* : OpenAI, Anthropic (Claude), Google (Gemini), ainsi que tout service compatible OpenAI. Seul l'administrateur peut saisir l'adresse d'un service compatible : HTTPS obligatoire, adresses internes, privées ou réservées refusées, redirections refusées, contrôle refait à chaque appel. Un modèle local (Ollama…) s'autorise uniquement par l'exploitant, dans `.env` : `AI_ALLOWED_LOCAL_URLS=http://host.docker.internal:11434/v1`. Les adresses des fournisseurs officiels sont fixes. Les clés sont **chiffrées (Fernet) côté serveur** et jamais renvoyées au navigateur. Elles sont masquées dans les journaux et absentes des exports.
- Chaque traitement passe par un écran de confirmation : fonction, périmètre, fournisseur, modèle, catégories de données transmises (et contenu exact en mode « Confirmation systématique »). **Aucun appel** n'est déclenché par un import, une synchronisation, l'ouverture d'un dossier, un changement de profil ou l'enregistrement d'une clé.
- Les productions de l'IA vont dans la couche éditoriale, étiquetées « IA » avec le fournisseur, le modèle et la date. Vous pouvez les valider, les rejeter, les adopter ou les supprimer. Les doublons proposés par l'IA ne sont **jamais fusionnés**.
- Confidentialité : par défaut, le contenu transmis n'est **pas conservé** (`store_inputs` désactivé) ; il est effacé après exécution, annulation ou blocage, et les brouillons non confirmés sont purgés après 24 h. Le rôle Lecteur n'a pas accès aux fonctions IA.
- Coûts : les jetons déclarés par le fournisseur sont multipliés par les tarifs saisis par l'administrateur (*Administration → IA : tarifs*). Le résultat est toujours présenté comme une estimation.

---

## 5. Sauvegardes et restauration

- Automatique : chaque nuit (planificateur), avec rotation selon *Administration → Paramètres*.
- Manuelle : *Administration → Sauvegardes*, ou `docker compose exec web python manage.py backup --verify`.
- Contenu : archive `.tar` contenant la base (`pg_dump`, ou export JSON Django en secours), les fichiers et un manifeste d'empreintes SHA-256. Une copie externe est réalisée si `BACKUP_EXTERNAL_DIR` est défini (prévoir un volume dans `docker-compose.yml`).
- Vérification d'intégrité depuis l'interface. **Testez périodiquement une restauration**, sur une instance de test de préférence :
  `docker compose exec web python manage.py restore_backup /data/backups/sauvegarde-….tar`
  Une sauvegarde de sécurité est créée automatiquement avant toute restauration (option `--sans-securite` pour s'en passer). La restauration est tout ou rien : intégrité vérifiée d'abord, base restaurée en une seule transaction (`pg_restore --single-transaction` ou export JSON de secours), fichiers copiés seulement ensuite.
- Portabilité : les exports JSON (schéma versionné) et CSV (profil « Import générique ») sont réimportables sans créer de doublons.

---

## 6. Déploiement distant

Voir `docs/deploiement.md` : serveur Linux, mêmes images Docker, reverse proxy HTTPS (exemple Caddy fourni), `SECURE_HTTPS=true` avec `SETUP_TOKEN`, base non exposée, sauvegardes hors serveur. Protections actives : verrouillage de 15 minutes après 5 échecs de connexion (identifiant + adresse IP, cache Redis partagé), politique CSP stricte (aucun script en ligne), `X-Frame-Options: DENY`, HSTS (sous-domaines et préchargement réglables). L'ouverture à d'autres utilisateurs (rôles Chercheur et Lecteur, partage de dossiers) est déjà en place ; elle suppose HTTPS et une politique RGPD (§14.1).

---

## 7. Tests

```bash
python manage.py test tests            # 130 tests ; PostgreSQL recommandé (DATABASE_URL)
```
Ils couvrent les critères d'acceptation AT-01 à AT-20 et AT-IA-01 à AT-IA-12 (correspondance détaillée dans `docs/conformite.md`). Les connecteurs et fournisseurs d'IA y sont testés sur des réponses simulées, sans appel réseau. `tests/test_audit_corrections.py` reproduit chacune des anomalies relevées par l'audit et vérifie qu'elle ne se produit plus. `tests/test_evolution_120.py` couvre la 1.2.0 sur des réponses enregistrées (`tests/fixtures/reponses/`) : réponse normale, aucun résultat, indisponibilité, réponse mal formée, journal, export, conservation des données.

---

## 8. Organisation du code

```
config/            réglages, URLs, Celery
apps/core          accueil, PWA, permissions, journal, normalisation japonaise (japanese.py)
apps/accounts      comptes, rôles, premier démarrage
apps/catalog       modèle documentaire (œuvre / édition / exemplaire / notice / versions / couche éditoriale)
apps/connectors    contrat commun + connecteurs (local, kokusho, ndl, japansearch)
apps/searching     sessions, résultats, décisions, recherches enregistrées, comparaison
apps/updates       imports (CSV/TSV/XLSX/JSON/XML/MARCXML/DC), synchronisations, zone de validation
apps/library       bibliothèque, dossiers, annotations, partage, corrections
apps/exports       modèle documentaire d'export + générateurs DOCX/PDF/TXT/JSON/CSV/HTML/ZIP
apps/ai            fournisseurs, clés chiffrées, préférences, tâches tracées
apps/backups       sauvegarde, vérification, restauration
templates/ static/ interface (Bootstrap, HTMX, icônes et polices servis localement)
docs/              conformité, déploiement, schéma JSON, exemples
tests/             tests d'acceptation
```

Licences des composants front embarqués : Bootstrap, Bootstrap Icons et htmx (MIT) ; fichiers `LICENSE` dans `static/vendor/`.
