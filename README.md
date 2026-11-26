# J-ed

Anciennement « Japon — Explorateur documentaire ». Les noms techniques (dépôt `japon-explorateur`, projet Docker, images, volumes) restent inchangés.

Application web progressive (PWA) de recherche, de gestion et d'exploitation de ressources documentaires japonaises, développée d'après le cahier des charges v1.2 du 12 novembre 2026.

**Version 2.0.3 — version candidate rc1 du 26 novembre 2026** : **J-ed sous Linux** (Ubuntu 26.04 LTS) avec les mêmes scripts que sous Windows (PowerShell 7), assistant en menu texte (`j-ed.sh`), proxy sous Ubuntu, guide « Avant de commencer (Linux) » ; aucun changement des données. Versions précédentes : **2.0.2** du 24 novembre 2026 (**assistant graphique Windows** `J-ed.cmd`, proxy de Windows, guide « Avant de commencer »), **2.0.1** du 23 novembre 2026 (licence, mise à jour sûre, tests automatiques), **2.0.0** du 19 novembre 2026, renommée **J-ed**, à partir de la 1.3.0-rc3 (étiquette `v1.3.0-rc3`, commit `d7296d4`). Détail des évolutions : `CHANGELOG.md` ; synthèse technique de la 2.0.0 : `docs/evolution-2.0.0/rapport-technique-2.0.0.md`.

**Nouveautés de la 2.0.0.** Trois statuts par notice (notice, document, IIIF), notifications, tâches et file de nuit, plafonds de dépense, Argos installé d'office, résumés par IA (en ligne ou locale avec Ollama), repérage du japonais ancien, aide intégrée, mise à jour et vérification par script, Aozora Bunko (texte intégral), Waseda, Kokusho dans sa vraie base, « Ouvrir le document », visionneuse IIIF facultative, accès des documents numérisés de la NDL, mesure des performances.

> **Nom et port de l'installation (2.0.0) :** `COMPOSE_PROJECT_NAME` est **obligatoire** dans `.env` (plus de nom par défaut) ; pour mettre à jour une installation, gardez exactement le nom de son `.env` actuel, et utilisez de préférence `mettre-a-jour.ps1` (sauvegarde, empreinte, reprise du `.env`, contrôle final). Les noms `japon-explorateur` et `japon-explorateur-essai` restent protégés (`AUTORISER_NOM_PROJET`). Port par défaut : 8000 (`WEB_PORT`).

**Stack :** Django 5 · PostgreSQL · HTMX + Bootstrap 5 (sans framework front lourd) · Celery + Redis · Docker Compose · python-docx · ReportLab.

---

## 1. Installation (Windows, macOS, Linux)

**Sous Windows, le plus simple (2.0.2) : l'assistant graphique.** Lisez d'abord `AVANT-DE-COMMENCER.html` (ou sa
version PDF), à la racine de l'archive : prérequis (WSL, Docker Desktop), téléchargement, puis un double-clic sur
**`J-ed.cmd`**. La fenêtre « Assistant J-ed » vérifie les prérequis, installe J-ed (aussi une deuxième instance sur un
autre port), le met à jour (archive choisie ou dernière version de GitHub), le vérifie, le sauvegarde et le restaure,
règle le proxy de Windows, et prépare un compte rendu « Ça ne marche pas » sans aucun secret. Les opérations restent
possibles en ligne de commande (ci-dessous et scripts `.ps1`) ; le contrat entre l'assistant et les scripts est dans
`docs/contrat-scripts.md`.

**Sous Linux (Ubuntu), depuis la 2.0.3 : le menu de l'assistant.** Lisez d'abord `AVANT-DE-COMMENCER-LINUX.html`
(ou sa version PDF) : Terminal, proxy, Docker Engine (dépôt officiel de Docker), groupe `docker`, PowerShell 7.6,
puis `bash j-ed.sh` dans le dossier extrait. Le menu (dans le Terminal) offre les mêmes fonctions que la fenêtre de
Windows, dans le même ordre, et lance les mêmes scripts `.ps1` (avec `pwsh`). Il refuse d'être lancé avec `sudo`.

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

Services lancés : `web` (Gunicorn), `worker` (Celery : synchronisations, exports, IA), `worker-maintenant` (tâches lancées « maintenant »), `worker-traduction` (traductions et résumés), `beat` (planification : actualisations, file de nuit, purge des sessions temporaires, sauvegarde quotidienne), `db` (PostgreSQL, non exposé), `redis`. Profils facultatifs (`COMPOSE_PROFILES` dans `.env`) : `argos` (traduction hors ligne, activé par défaut) et `ollama` (IA locale pour les résumés).

### Windows : scripts fournis
- `J-ed.cmd` (2.0.2) : ouvre l'**assistant J-ed** (fenêtre ; `assistant/`), qui lance les scripts ci-dessous.
- `installer-j-ed.ps1` (2.0.2) : nouvelle installation à côté des autres (nom et port neufs contrôlés, secrets neufs, construction, démarrage, contrôle ; journal `installation-*.log` ; codes 0, 1, 3, 5).
- `mettre-a-jour.ps1` : met à jour une installation existante (sauvegarde, empreinte de l'archive, reprise du `.env`, contrôle final). Il prévient si la copie lancée est plus ancienne que celle de l'archive. Depuis la 2.0.1 : construction de la nouvelle version pendant que l'ancienne reste en service, retour automatique à l'ancienne si la nouvelle ne démarre pas, journal `mise-a-jour-*.log` dans le dossier des sauvegardes, codes de sortie 0 à 5 (aide « Mettre à jour J-ed »).
- `verifier-j-ed.ps1` : produit un rapport de vérification (dossier, conteneurs, adresse, fonctions de l'application sur données fictives) ; options `-AvecTests` et `-AvecSources`.
- `reinitialiser-essai.ps1` : remet à zéro une installation **d'essai** seulement.
- `verifier-migration.ps1` : après le passage sur un autre ordinateur, inventaire en lecture seule des installations présentes dans Docker (volumes, conteneurs, `.env`, sauvegardes, nombres de notices et de dossiers) ; option `-Dossiers` pour indiquer un dossier d'installation déplacé.

Le guide d'installation et le guide de mise à jour pas à pas sont dans l'aide intégrée (rubrique « Installation et mises à jour ») et dans `docs/guide-utilisation.html`.

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

| Source | État en 2.0.0 | Méthode |
|---|---|---|
| Base locale | Opérationnel | Recherche PostgreSQL (index trigrammes) sur les champs normalisés |
| **NDL Search** | Testé en simulation ; utilisé sur le poste | API OpenSearch officielle ; accès des numérisations vérifiable (manifeste IIIF) |
| **Japan Search** | Testé en simulation ; utilisé sur le poste | API officielle (variantes en OU, période, personne) |
| **Archives nationales** | Testé en simulation | Japan Search, base `najda` |
| **CiNii Research** et **CiNii bibliothèques universitaires** | Testé en simulation | API OpenSearch officielle ; identifiant gratuit `CINII_APPID` dans `.env` |
| **Kokusho Database** (国書データベース) | Testé en simulation ; structure relevée sur le poste | Manifeste IIIF officiel par notice ; recherche dans Japan Search, base `nij16` (日本古典籍総合目録) |
| **Aozora Bunko** (青空文庫) | Testé en simulation ; liste importée sur le poste | Liste officielle des œuvres (CSV, CC BY) ; texte intégral à la demande |
| **Waseda Kotenseki** (古典籍総合データベース) | Testé en simulation | NDL Search, fournisseur `waseda` ; lien vers la page de l'ouvrage, avec la mention exigée |
| Historiographical Institute (SHIPS) | Consultation externe | Aucune interface automatique (étude du 16/11/2026) |
| CODH PMJT, classeur | Import | Fichiers fournis, instantané historique signalé |
| Autres archives, universités, musées | Via « Trouver une base Japan Search » si l'institution y diffuse sa base, sinon consultation externe | Voir `docs/evolution-1.2.0/02-etude-sources.md` et `docs/evolution-2.0.0/rapport-lot-10.md` |

Chaque source affiche dans une session : résultats, *aucun résultat* (ce n'est pas une erreur), *source indisponible*, *erreur technique* ou *réponse impossible à interpréter*. Les échecs sont enregistrés dans le **journal des dysfonctionnements**.

J-ed n'aspire aucune page HTML de navigation : il passe par les API officielles, les manifestes IIIF et les fichiers publiés par les sources, respecte leur fichier robots.txt et espace ses requêtes. Tant qu'aucun test réel n'a réussi, chaque connecteur porte le badge **« Non vérifié en conditions réelles »** ; le badge disparaît après un « Tester le connecteur » réussi.

Sur les fiches et dans les résultats, **« Ouvrir le document »** mène au document lui-même (visionneuse du Kokusho, NDL Digital Collections, page de Waseda, lecture Aozora). La **visionneuse IIIF intégrée** est facultative et désactivée par défaut (*Administration → Paramètres*). Une fois activée, le navigateur charge les images des seuls sites autorisés, et seulement sur la page de la visionneuse.

**Ajouter un connecteur** : créer une classe dérivée de `apps/connectors/base.py:BaseConnector` (méthodes `search`, `fetch_record`, éventuellement `harvest`), la décorer par `@register`, puis ajouter son module à `registry._load()`. Le reste de l'application (recherche, sessions, mises à jour, exports) n'a pas à être modifié.

---

## 4. Intelligence artificielle (facultative)

- Valeurs initiales (AT-IA-01) : mode **À la demande**, traduction, résumé et détection des doublons proposés, classification désactivée.
- *Préférences IA* : profils multiples (créer, dupliquer, activer, supprimer), mode Désactivée / À la demande / Confirmation systématique, fournisseur et modèle par défaut **ou par fonction**, plafond mensuel estimé.
- *Fournisseurs et clés API* : OpenAI, Anthropic (Claude), Google (Gemini), ainsi que tout service compatible OpenAI. Seul l'administrateur peut saisir l'adresse d'un service compatible : HTTPS obligatoire, adresses internes, privées ou réservées refusées, redirections refusées, contrôle refait à chaque appel. Un modèle local (Ollama…) s'autorise uniquement par l'exploitant, dans `.env` : `AI_ALLOWED_LOCAL_URLS=http://host.docker.internal:11434/v1`. Les adresses des fournisseurs officiels sont fixes. Les clés sont **chiffrées (Fernet) côté serveur** et jamais renvoyées au navigateur. Elles sont masquées dans les journaux et absentes des exports.
- Chaque traitement passe par un écran de confirmation : fonction, périmètre, fournisseur, modèle, catégories de données transmises (et contenu exact en mode « Confirmation systématique »). **Aucun appel** n'est déclenché par un import, une synchronisation, l'ouverture d'un dossier, un changement de profil ou l'enregistrement d'une clé.
- Les productions de l'IA vont dans la couche éditoriale, étiquetées « IA » avec le fournisseur, le modèle et la date. Vous pouvez les valider, les rejeter, les adopter ou les supprimer. Les doublons proposés par l'IA ne sont **jamais fusionnés**.
- Confidentialité : par défaut, le contenu transmis n'est **pas conservé** (`store_inputs` désactivé) ; il est effacé après exécution, annulation ou blocage, et les brouillons non confirmés sont purgés après 24 h. Le rôle Lecteur n'a pas accès aux fonctions IA.
- Coûts : les jetons déclarés par le fournisseur sont multipliés par les tarifs saisis par l'administrateur (*Administration → IA : tarifs*). Le résultat est toujours présenté comme une estimation.

### Traduction et résumés (1.3.0, complétés en 2.0.0)
- Moteurs : DeepL, Google Traduction, Argos Translate (hors ligne, installé d'office), IA en ligne ; résumés par IA en ligne ou par **IA locale** (Ollama, profil `ollama`, modèle `qwen3:4b` conseillé, essai automatique au démarrage).
- Chaque traduction ou résumé est une **tâche** : maintenant, programmée ou dans la **file de nuit** ; pause, reprise sans rien renvoyer, compte rendu du matin. Un **plafond** atteint met la tâche en pause ; J-ed ne change jamais de moteur de lui-même.
- **Projets de traduction** : découpage en segments, mémoire, glossaire, export bilingue ; un texte d'Aozora Bunko s'y ajoute en un clic.
- **Japonais ancien** : repérage du bungo, du kanbun et du sōrōbun ; moteur adapté proposé ; page d'aide « Bonnes pratiques ».

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

## 7. Commandes utiles

Dans le dossier de J-ed : `docker compose exec web python manage.py <commande>`.

| Commande | Rôle |
|---|---|
| `backup --verify` / `restore_backup <fichier>` | Sauvegarde vérifiée / restauration (sauvegarde de sécurité d'abord) |
| `etat_installation` | État de l'installation (même contenu que la page) |
| `verifier_fonctionnalites` | Vérification des fonctions sur données fictives (utilisée par `verifier-j-ed.ps1`) |
| `mesurer_performances [--notices N]` | Mesure de la rapidité dans une base temporaire de notices fictives, supprimée ensuite |
| `etudier_sources [--plan 1\|2\|3]` | Étude des sources en lecture seule (structure des réponses des sites) |
| `exporter_guide` | Régénère `docs/guide-utilisation.html` et `.md` à partir de l'aide |
| `generate_secrets` | Produit les secrets à recopier dans `.env` |
| `seed_sources` | Répertorie les sources prévues (n'écrase jamais une source existante) |
| `purge_sessions` | Purge des sessions de recherche temporaires expirées |

---

## 8. Tests

```bash
python manage.py test tests --parallel 4     # 950 tests (2.0.2) ; PostgreSQL requis (DATABASE_URL)
```
**Tests automatiques (2.0.1)** : à chaque envoi sur `main` ou sur une branche `evolution-…`, GitHub Actions lance tous les tests sur une machine Ubuntu avec PostgreSQL 15 et les polices japonaises de l'image Docker (`.github/workflows/tests.yml`). Résultats dans l'onglet « Actions » du dépôt ; l'exécution échoue si un test est ignoré.
Ils couvrent les critères d'acceptation AT-01 à AT-20 et AT-IA-01 à AT-IA-12 (correspondance détaillée dans `docs/conformite.md`), puis chaque évolution des versions 1.2.0, 1.3.0 et 2.0.0 (`tests/test_*_<lot>.py`). Les connecteurs et fournisseurs d'IA sont testés sur des réponses simulées, sans appel réseau ; pour la 2.0.0, les simulations reprennent les structures réelles relevées sur le poste de l'utilisateur. `tests/test_audit_corrections.py` reproduit chacune des anomalies relevées par l'audit et vérifie qu'elle ne se produit plus. Les scripts PowerShell sont testés avec PowerShell 7 (`tests/test_mise_a_jour_ps1.py`, `tests/test_verification_200.py`).

---

## 9. Organisation du code

```
config/              réglages, URLs, Celery
apps/core            accueil, PWA, permissions, journal, paramètres, état et vérification de l'installation,
                     mesure des performances, étude des sources, normalisation japonaise (japanese.py)
apps/accounts        comptes, rôles, premier démarrage
apps/catalog         modèle documentaire (œuvre / édition / exemplaire / notice / versions / couche éditoriale),
                     trois statuts, IIIF et visionneuse, textes intégraux, « Ouvrir le document »
apps/connectors      contrat commun + connecteurs (local, ndl, japansearch, cinii, kokusho, aozora, waseda)
apps/searching       sessions, résultats, décisions, recherches enregistrées, comparaison
apps/updates         imports (CSV/TSV/XLSX/JSON/XML/MARCXML/DC), synchronisations, zone de validation
apps/library         bibliothèque, dossiers, annotations, partage, corrections
apps/exports         modèle documentaire d'export + générateurs DOCX/PDF/TXT/JSON/CSV/HTML/ZIP
apps/ai              fournisseurs, clés chiffrées, préférences, tâches tracées, IA locale (Ollama)
apps/translation     moteurs, tâches, file de nuit, plafonds, projets, mémoire, glossaire, résumés
apps/notifications   fenêtre, compteur, préférences
apps/incidents       journal des dysfonctionnements, rapports de diagnostic
apps/help            aide intégrée (docs/aide/*.md), recherche, guide exporté
apps/backups         sauvegarde, vérification, restauration
templates/ static/   interface (Bootstrap, HTMX, icônes et polices servis localement)
docs/                aide, conformité, déploiement, schéma JSON, exemples, dossiers d'évolution
tests/               tests d'acceptation et de non-régression
```

Licences des composants front embarqués : Bootstrap, Bootstrap Icons et htmx (MIT) ; fichiers `LICENSE` dans `static/vendor/`. Liste complète des composants et de leurs licences : page « À propos » de l'application.

---

## 10. Licence

J-ed est un logiciel libre, publié sous la licence **GNU Affero General Public License, version 3 ou (à votre choix) toute version ultérieure** (identifiant SPDX `AGPL-3.0-or-later`). Le texte complet est dans le fichier [`LICENSE`](LICENSE).

- Vous pouvez utiliser J-ed, étudier son code, le modifier et le redistribuer, sous la même licence.
- Si vous mettez une **version modifiée** de J-ed à disposition d'autres personnes à travers un réseau, vous devez leur offrir son code source (article 13 de l'AGPL). L'application affiche un lien « Code source » (pied de page et page « À propos ») ; indiquez l'adresse de votre version dans la variable `CODE_SOURCE_URL` du fichier `.env`.
- J-ed est fourni **sans aucune garantie**, dans les limites prévues par la licence.

Les composants utilisés gardent leur propre licence (liste dans la page « À propos ») : des licences libres compatibles avec l'AGPL v3 (MIT, BSD, Apache 2.0, LGPL v3, GPL v3 ou ultérieure pour pykakasi). Pour proposer une contribution : [`CONTRIBUTING.md`](CONTRIBUTING.md).
