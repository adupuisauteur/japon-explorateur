# J-ed 2.0.0 — Rapport du lot 1 : interface

15 novembre 2026 · branche `evolution-2.0.0` · plan : `01-audit.md`, § 3.2 · cahier des charges : § 4

## 1. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Nom J-ed | Barre de menu, titres des pages, pied de page, page de connexion, premier démarrage, application installable (PWA), en-têtes des exports et des rapports de diagnostic, gestion interne. Réglage unique `settings.APP_NAME`, disponible dans tous les gabarits | `config/settings.py`, `apps/core/context_processors.py`, `templates/base.html`, `apps/core/views.py`, `apps/exports/document.py`, `apps/translation/exports.py`, `apps/incidents/report.py` |
| Noms techniques (cahier § 4) | Inchangés : projet Docker, images, volumes, dépôt. Le champ `application` du manifeste des sauvegardes garde sa valeur, avec un commentaire | `apps/backups/services.py` |
| Nom d'instance (D13) | « J-ed » par défaut pour une nouvelle installation ; la valeur enregistrée d'une installation existante n'est pas modifiée | `apps/core/models.py`, migration `core.0004` |
| `User-Agent` (D9) | `J-ed/2.0.0 (usage de recherche personnel)` ; toujours remplaçable par `CONNECTOR_USER_AGENT` | `config/settings.py` |
| Page « À propos » | Version, format des données exportées, nom de l'installation, origine du projet, logiciels libres utilisés. Ouverte à tout compte connecté. Lien « À propos » en bas de page (demande U3, après la vérification sur le poste) | `templates/core/about.html`, `apps/core/views.py` |
| Menus | « Administration » et « Dysfonctionnements » retirés du menu du haut ; ajoutés au menu à son nom et au pied de page, pour l'administrateur seulement. Pastille des incidents nouveaux sur le bouton du menu à son nom ; elle n'est plus calculée pour les autres rôles | `templates/base.html`, `apps/core/context_processors.py` |
| Droits sur le journal | Liste, détail, analyse, export et capture réservés à l'administrateur. « Signaler un problème » reste ouvert ; après l'envoi, un chercheur revient à sa page (adresse interne seulement) avec l'identifiant du signalement. Les liens vers le journal sont cachés aux autres rôles, le message d'erreur reste affiché | `apps/incidents/views.py`, `templates/searching/_source_status.html`, `templates/connectors/detail.html`, `templates/connectors/jps_databases.html`, `templates/incidents/report_form.html` |
| Page hors ligne | Page autonome mise en cache : « J-ed ne répond pas », sans menu ni version, conseils sur Docker Desktop, bouton « Réessayer ». Aucun script | `templates/core/offline.html` |
| Contrôle de santé | Nouvelle adresse `/sante/` (réponse « ok » si le serveur répond et la base est joignable, sinon 503 avec le type d'erreur, jamais mise en cache, accessible avant le premier compte) ; le `healthcheck` de Docker l'utilise | `apps/core/views.py`, `apps/core/middleware.py`, `docker-compose.yml` |
| Bas de page des exports (U2) | Voir § 3 | `apps/exports/…`, `apps/translation/exports.py` |
| Outils de vérification | `verifier_fonctionnalites` : pages « À propos » et `/sante/`, refus du journal au chercheur, signalement toujours possible. `verifier-j-ed.ps1` : contrôle de `/sante/` (« Non vérifié » sur une installation antérieure au lot 1) | `apps/core/verification.py`, `verifier-j-ed.ps1` |

**Base de données.** Une migration, `core.0004_instance_name_default`, qui ne change que la valeur par défaut
d'un champ dans le code : `sqlmigrate` confirme qu'elle n'exécute **aucune instruction SQL**.

**Ce qui n'est pas dans ce lot.** Le cahier ajoute aussi au menu à son nom « Notifications » (lot 5) et
« Aide » (lot 6), et un compteur des notifications non lues (lot 5). Ces entrées viendront avec leurs pages. En
attendant, la pastille du menu à son nom compte les incidents nouveaux, comme le faisait celle du menu
« Dysfonctionnements ».

## 2. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète, exécution séquentielle | **503 tests réussis** (471 à la fin du lot 0 + 32 nouveaux ; 2 tests adaptés au nouveau comportement, voir § 4) |
| Suite complète, exécution parallèle (`--parallel 4`), 3 fois | **3 fois sur 3 : 503 réussis** |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration manquante |
| Migration `core.0004` sur une base temporaire | `migrate`, retour `migrate core 0003`, puis `migrate` : sans erreur ; `sqlmigrate` : aucune instruction (« no-op ») ; base supprimée ensuite |
| `verifier_fonctionnalites` sur une base temporaire | OK 9, À surveiller 3, Problème 0, Non vérifié 3. Les points à surveiller et non vérifiés tiennent à l'environnement de test : pas de Redis, d'Argos ni de sauvegarde |
| `verifier-j-ed.ps1` et `mettre-a-jour.ps1` (PowerShell 7, faux `docker`) | 29 tests réussis, dont le contrôle de `/sante/` : réponse correcte, adresse absente (404), base injoignable (503) |
| Contrôle visuel (Chrome sans interface, base temporaire, comptes fictifs) | Accueil de l'administrateur avec le menu à son nom ouvert, accueil et « À propos » du chercheur, page de connexion, page « J-ed ne répond pas », page 2 d'un export PDF : conformes |

**Nouveaux tests** (`tests/test_interface_200.py`, 31 tests) : nom affiché ; manifeste PWA ; `User-Agent` ;
rapport de diagnostic ; valeur par défaut du nom d'instance et conservation de la valeur existante ; manifeste
des sauvegardes ; « À propos » pour les trois rôles ; menus de chaque rôle ; refus du journal (6 adresses) au
lecteur et au chercheur ; signalement et retour, y compris le refus des adresses extérieures et du journal comme
page de retour ; page d'une source ; page hors ligne ; `/sante/` (réponse, base injoignable, premier
démarrage) ; bas de page Word, PDF (chaque page), HTML et texte ; case « ne pas indiquer » et régénération ;
exports des projets de traduction (Word, texte, Markdown, case). Plus 1 test dans
`tests/test_verification_200.py` pour `/sante/`.

## 3. Bas de page des exports (demande U2)

Décisions de l'utilisateur au début du lot : identifiant de connexion ; case pour le retirer ; même bas de page
pour les projets de traduction.

| Export | Où | Contenu |
| --- | --- | --- |
| Word, PDF (notices) | chaque page après la couverture | texte libre « Pied de page » s'il existe, puis « Produit le 15/11/2026 à 12:17 · J-ed 2.0.0 · par chercheur », identifiant `EXP-…`, numéro de page |
| Couverture Word et PDF | métadonnées | ligne « Exporté par » ajoutée |
| Site HTML | bas de chaque page | même ligne, puis l'identifiant de l'export |
| Texte (.txt) | dernière ligne | même ligne |
| JSON | métadonnées | clés `produced_by` et `production_line` ajoutées à `export_metadata` (le schéma 1.0 ne les interdit pas) |
| CSV | — | aucun bas de page (fichier de données) |
| Projet de traduction, Word bilingue | chaque page | même ligne et numéro de page ; « Exporté par » dans l'en-tête |
| Projet de traduction, texte et Markdown | dernière ligne | même ligne ; « Exporté par » dans l'en-tête |

- La case « Ne pas indiquer mon identifiant » retire « par … » et la ligne « Exporté par ». Le champ « Auteur /
  préparateur » reste celui que l'utilisateur a saisi ; il est prérempli avec son nom, à vider au besoin.
- Les exports produits avant le lot 1 ne sont pas modifiés.

## 4. Écarts et choix faits pendant le lot

- **Tests adaptés** :
  - `test_status_change_is_reserved_to_admin` (1.2.0) vérifiait qu'un lecteur ouvrait le détail d'un incident :
    il vérifie désormais le refus ;
  - `test_translation_only_keeps_paragraph_breaks` (1.3.0) vérifiait que l'export « Traduction seule » se
    terminait par le texte : la ligne de production le suit maintenant, séparée par un trait. Les paragraphes
    sont toujours conservés.
- **Couverture des exports** : comme en 1.3.0, la page de couverture n'a pas de bas de page ; elle porte déjà la
  date, l'application et « Exporté par ».
- **Le logo 日本** devant le nom a été retiré : le cahier demande le seul nom « J-ed ». L'icône de
  l'application est inchangée.
- **Ancienne page hors ligne déjà en cache** : le navigateur la remplace par la nouvelle au premier chargement
  de J-ed 2.0.0 (le service worker change de version). Un Ctrl + F5 suffit si l'ancienne apparaît encore.
- **Retour à la version précédente** : la commande du guide de mise à jour reste `migrate core 0001` ; le
  résultat attendu mentionne désormais `core.0004`. Guides mis à jour, voir § 6.

## 5. Points ouverts

- **Test instable `test_quick_search_from_every_page_and_session`** : il n'a pas échoué pendant ce lot (3
  exécutions parallèles). L'enquête reste prévue au lot 9.
- **Grille TR1–TR12** : toujours pas reçue.
- **Copies de sauvegarde dans Windows** : jamais supprimées par J-ed ; à traiter au lot 3, comme prévu.

## 6. Retour de l'utilisateur (15 novembre 2026)

- `verifier-j-ed.ps1` sur l'essai mis à jour : **27 OK, 0 à surveiller, 0 problème**, 1 non vérifié (sources en
  ligne, facultatif). Vérifications V1-1 à V1-6 : **conformes**.
- **U3, faite** (archive `lot1b`) : lien « À propos » dans le bas de page, retiré du menu utilisateur.
- **U4**, prévue au lot 6 : historique des versions dans l'Administration, limité aux évolutions et
  améliorations, sans les bugs rencontrés.
- **U5**, prévue au lot 3 : vue d'ensemble des traductions déjà effectuées.

## 7. Livrables du lot

- Archives `japon-explorateur-2.0.0-lot1.zip`, puis `lot1b` (demande U3), avec leur empreinte `.sha256` ; `mettre-a-jour.ps1` et
  `verifier-j-ed.ps1` à part.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 1 » (V1-1 à V1-6).
- Registre des demandes : U2 et U3 faites ; U4 (lot 6) et U5 (lot 3) inscrites.
- CHANGELOG : section 2.0.0, lot 1.
- Guides en ligne :
  - mise à jour : le chemin vers « État de l'installation », la page « J-ed ne répond pas », le stade (lot 1)
    et le résultat attendu de la commande de retour ;
  - installation : un encadré qui dit où trouver « Administration ».
