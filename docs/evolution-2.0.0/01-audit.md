# J-ed 2.0.0 — Audit de départ et plan de développement

14 novembre 2026 · audit du code 1.3.0-rc3 (`d7296d4`) au regard du cahier des charges 2.0.0

Ce document clôt l'étape « audit » de la méthode (cahier des charges, section 12). **Aucun développement n'a
commencé** : il attend la validation du plan (section 6) et des décisions (section 7).

## 1. En bref

- Le point de départ est sain : la branche `evolution-1.3.0` de GitHub est identique, fichier par fichier, à
  l'archive rc3 (empreinte vérifiée). Les **389 tests réussissent**, et `check` et `makemigrations --check`
  ne signalent rien.
- **Quatre défauts** sont à corriger en priorité dans le lot 0, en plus de ceux que le cahier relève
  déjà. Le plus important : si le service Argos devient injoignable pendant une traduction, la suite est
  produite **en simulation**, sans arrêt ni erreur (§ 3.1).
- **Trois hypothèses du cahier sont à corriger** :
  - des index trigrammes existent déjà (§ 3.10) ;
  - la liste des modèles d'IA sert déjà à refuser un modèle inconnu, mais elle est tronquée chez deux
    fournisseurs (§ 3.9) ;
  - un résumé IA des notices existe déjà en 1.3.0 (§ 3.5).
- **Deux exigences du cahier ne sont pas réalisables telles quelles** ; je propose une adaptation pour
  chacune :
  - faire varier les cœurs accordés à Argos à chaque demande (§ 3.8) ;
  - changer de profil de machine depuis l'interface (§ 3.4).
- **Mesures sur 50 000 notices fictives** : les recherches dans la Bibliothèque prennent moins de 160 ms
  ici, ce qui ne justifie aucune optimisation à ce stade. La page Consommation, en revanche, fait **903
  requêtes et prend 1,4 s** pour 300 tâches : son optimisation est justifiée.
- **Limites de l'environnement de développement** : Docker n'y fonctionne pas (le client est présent, pas
  le service), l'index PyTorch est inaccessible et PowerShell n'est pas installé. L'image Argos, les
  fichiers `docker-compose.yml` et `mettre-a-jour.ps1` seront donc vérifiés sur ton poste.

## 2. Point de départ vérifié

| Élément | Constat |
| --- | --- |
| Archive rc3 | SHA-256 `b6738552…688698a`, identique au cahier ; 486 fichiers ; `VERSION` = 1.3.0 |
| Branche GitHub `evolution-1.3.0` | `d7296d4`, 17 commits au-dessus de `4982a3d`, descend directement de `7cb4075` (avance simple de `main` possible) ; contenu identique à l'archive |
| Étiquettes | `v1.3.0-rc1` → `49bed31`, `v1.3.0-rc2` → `6f3cf65`, `v1.3.0-rc3` → `d7296d4` recréées **en local** (pas de bundle joint ; commits du cahier) |
| Branche de travail | `evolution-2.0.0` créée en local sur `d7296d4`, sans commit de code |
| Tests | 389 réussis en 92 s (PostgreSQL 16 temporaire). **En parallèle (`--parallel 4`), 5 échouent** (exports DOCX et HTML, PDF, import, journal Argos) : défaut d'isolation des tests, pas de l'application |
| Taille du code | environ 18 000 lignes Python (hors migrations), 91 gabarits, 12 applications Django |

## 3. Constats par lot

### 3.1 Lot 0 — corrections et fiabilité

**Défauts déjà relevés par le cahier, confirmés dans le code**

- `manage.py backup` (`apps/backups/management/commands/backup.py`) affiche « Échec » mais se termine avec
  le code 0. Même chose quand la vérification `--verify` échoue.
- `create_backup` (`apps/backups/services.py`, l. 113) ne conserve que le message de l'exception, **sans son
  type**.

**Nouveaux défauts trouvés**

1. **Basculement silencieux d'Argos en simulation** (`apps/translation/engines/argos.py`, l. 95-138).
   - À chaque paquet, le moteur interroge `/health`. Si le service ne répond pas, `translate()` renvoie
     le texte original préfixé de « [Simulation Argos…] » au lieu d'une erreur.
   - Conséquence : un redémarrage du conteneur Argos ou un manque de mémoire au milieu d'une file de nuit
     produit des « traductions » simulées pour tout le reste de la file. La tâche finit « Terminée », sans
     erreur.
   - Les versions portent bien la mention « Simulation », mais rien n'arrête la tâche.
   - Avec Argos installé par défaut (lot 7), la simulation doit devenir un **choix explicite**, jamais un
     repli automatique.
2. **Liste des modèles d'IA tronquée** (`apps/ai/providers.py`). Anthropic renvoie 20 modèles par page par
   défaut et Gemini 50 ; la 1.3.0 ne lit que la première page. Or `apps/ai/services.py` (l. 157) refuse un
   modèle absent de la liste (« n'apparaît pas dans la liste du fournisseur »). Un modèle valide situé
   au-delà de la première page peut donc être refusé à tort.
3. **Copie externe des sauvegardes** : si la copie vers `BACKUP_EXTERNAL_DIR` échoue, toute la sauvegarde
   est marquée « Échec » alors que l'archive a été créée. La rotation ne supprime que les sauvegardes
   réussies, donc ces archives restent sur le disque sans jamais être supprimées.
4. **Restauration des fichiers** : elle ajoute les fichiers de la sauvegarde aux fichiers existants
   (`copytree(..., dirs_exist_ok=True)`) sans retirer ceux créés depuis. Le message « remplace » est donc
   inexact. À corriger dans le message, ou dans le comportement avec ta validation.

**Autres cas où une erreur est passée sous silence**

24 blocs `except Exception` ont été relus. La plupart sont corrects : l'erreur est journalisée avec son
type. Trois cas silencieux restent à corriger :

- une police PDF configurée mais illisible est ignorée sans avertissement (`pdf_gen.py`, l. 47 et 59) ;
- une erreur de calcul d'empreinte d'export est traitée comme une « donnée modifiée » sans être journalisée
  (`exports/services.py`, l. 89) ;
- la détection du format d'import JSON ignore toute erreur (`updates/importers.py`, l. 133) ; c'est
  mineur.

**Page « État », sauvegardes visibles dans Windows, `mettre-a-jour.ps1`**

- Rien de tout cela n'existe encore.
- Les sauvegardes sont écrites dans le volume Docker `app-data` (`/data/backups`). La ligne de copie
  externe de `docker-compose.yml` est commentée et écrite pour Linux.
  - Proposition : `DOSSIER_SAUVEGARDES=D:\…` dans `.env`, monté par Compose sur `/backups-externes`.
  - Compose accepte les chemins Windows à gauche du « : ». Reste à vérifier sur ton poste.
- `reinitialiser-essai.ps1` (270 lignes) contient le nom `japon-explorateur-essai-130` et le port 8002 en
  dur. Le nouveau script `mettre-a-jour.ps1` ne doit contenir aucun nom ni chemin propre à l'installation
  d'essai.

**Noms d'installation figés**

- `docker-compose.yml`, `.env.example`, `entrypoint.sh` et le service Argos supposent un projet nommé par
  défaut `japon-explorateur-essai-130`, avec des images étiquetées `1.3.0`.
- Pour une installation générique (cahier, § 10), il faut fixer la règle de nommage de la 2.0.0 : voir la
  décision D3.

### 3.2 Lot 1 — interface

**Nom affiché**

- « Japon — Explorateur documentaire » apparaît à **17 endroits** du code et des gabarits : titre des pages,
  barre de menu, pied de page, manifeste PWA, en-têtes des exports et du diagnostic, et la valeur
  `application` du manifeste des sauvegardes.
- Le manifeste des sauvegardes est un **champ technique** : je propose de le garder tel quel pour que la
  restauration des anciennes sauvegardes ne soit pas perturbée.
- Le réglage « Nom de l'instance » (`AppSettings.instance_name`) est **enregistré en base** avec l'ancien
  nom par défaut. Il ne s'affiche que dans les réglages. Je propose de changer la valeur par défaut pour
  les nouvelles installations, sans toucher aux valeurs existantes (décision D13).
- L'en-tête `User-Agent` envoyé aux catalogues (« JaponExplorateurDocumentaire/… ») est une identification
  technique : je propose `J-ed/2.0.0 (usage de recherche personnel)` (décision D9).

**Menus**

- `templates/base.html` : « Dysfonctionnements » est **visible par tous les comptes**, y compris le rôle
  Lecteur, et le compteur d'incidents est calculé pour tout le monde.
- `apps/incidents/views.py` : la liste, le détail, l'analyse et l'export des incidents ne demandent qu'une
  connexion. Seul le changement de statut est réservé à l'administrateur.
- Le lot 1 réserve donc ces vues à l'administrateur. « Signaler un problème » reste ouvert à tous.

**Page hors ligne**

- `templates/core/offline.html` hérite du gabarit général. Le navigateur la met en cache avec le menu et le
  numéro de version du moment, d'où l'ancienne version constatée le 14 novembre.
- Son message (« Vous êtes hors ligne ») parle d'Internet, alors que c'est le serveur qui ne répond pas.
- Correction : une page autonome, sans menu ni version, qui dit que J-ed ne répond pas et conseille de
  vérifier que Docker Desktop est démarré.
- Le contrôle de santé de Docker (`healthcheck`) interroge cette même page : il passera sur une adresse
  dédiée.

### 3.3 Lot 2 — trois statuts

**Ce qui existe**

- Un seul champ, `Record.digital_access`, qui **mélange les notions** : texte intégral, image, notice seule,
  accès restreint.
- `normalization.py` (l. 112-116) **déduit** « image disponible » de la simple présence d'une adresse. C'est
  exactement la confusion que le cahier veut supprimer.
- `Record.image_url` (« Manifeste ou image (IIIF) ») contient des choses différentes selon la source :
  - **Japan Search** y met le manifeste IIIF, ou à défaut l'adresse du contenu, ou à défaut **la vignette**
    (`japansearch.py`, l. 80) ;
  - **NDL** y met uniquement une adresse qui contient « iiif » et « manifest » ;
  - **Kokusho** y met une adresse de manifeste **construite à partir de l'identifiant**, que la source ne
    fournit pas.

**Conséquence pour les données existantes**

- Le statut IIIF ne peut pas être tiré de `image_url`.
- Il peut l'être, sans appel réseau, des **données brutes conservées** (`raw_data`) : par exemple le champ
  `iiifUrl` de Japan Search, ou le type « Manifest » d'un manifeste Kokusho déjà téléchargé.
- Pour les adresses construites (Kokusho, recherche), il faut une troisième origine : décision D5.

**Filtre « document numérisé disponible »** : il se trouve dans `apps/searching/views.py` (l. 157) et dans
le formulaire de recherche. Il sera remplacé par les trois filtres.

**Modèle proposé** : voir § 5.1.

### 3.4 Lot 3 — tâches, file de nuit, à la demande, travail en parallèle

**Ce qui sert de base**

- `TranslationJob` et `TranslationJobItem` gèrent déjà :
  - un état par élément ;
  - un signe d'activité régulier et la détection d'une interruption (10 min sans activité) ;
  - la reprise sans renvoyer ce qui est déjà traduit ;
  - l'annulation entre deux paquets.
- `run_translation_job` traite **un paquet puis se relance** (au plus 50 segments ou 20 000 caractères pour
  Argos). La pause « entre deux segments » se loge naturellement entre deux paquets.

**Ce qui manque**

- **Plafonds** : ils ne sont vérifiés qu'à la confirmation (`blocking_problems`), jamais pendant
  l'exécution (`process_next_chunk`).
- **États** : il n'existe ni « planifiée », ni « en pause », ni « terminée avec erreurs », ni ordre dans
  une file.
- **Workers** :
  - un seul worker Celery à deux places traite les files `celery` et `traduction`, ainsi que
    l'installation des paquets Argos (jusqu'à 30 min, dans la file `traduction`) ;
  - les résumés IA (`run_ai_task`) passent par la file `celery`.
- **Serveur web** : il lance trois processus gunicorn synchrones. Chaque source d'une recherche est une
  requête distincte, exécutée par le serveur web, avec jusqu'à 20 s d'attente par source. Une recherche sur
  quatre sources peut donc occuper les trois processus et ralentir toutes les autres pages.

**Planification**

- Celery beat est en place, mais avec des horaires fixes.
- Proposition : une tâche « horloge » toutes les minutes, qui lit en base les tâches planifiées et la plage
  de nuit. Rien de nouveau à installer.
- Elle permet aussi d'appliquer la règle « retard au redémarrage » : une tâche dont l'heure est passée
  attend une nouvelle confirmation.

**Réglages adaptés à la machine : adaptation nécessaire**

- Le nombre de processus du serveur web et des workers est fixé **au démarrage des conteneurs**.
- L'application ne peut pas redémarrer ses propres conteneurs. Un profil choisi dans l'interface ne
  pourrait donc pas s'appliquer sans intervention.
- Proposition :
  - le profil est calculé **au démarrage**, d'après la mémoire et les cœurs que Docker accorde ;
  - il peut être imposé par une ligne du `.env` (`JED_PROFIL=econome|normal|puissant`) ;
  - la page « État » affiche le profil retenu, la raison du choix et la commande à lancer pour en changer ;
  - la mémoire totale de l'ordinateur, saisie dans l'assistant, sert à conseiller l'utilisateur, sans rien
    modifier d'office (décision D7).

### 3.5 Lot 4 — résumés IA

**Ce qui existe déjà en 1.3.0**

- La fonction IA « Résumé documentaire » (bouton sur la fiche, si le profil IA l'active).
- Elle produit un `EditorialContent` de type « résumé », d'origine « IA », rattaché à la notice et
  construit **à partir des métadonnées**.

**Ce qui manque**

- Le résumé d'un **document de projet** ou d'une **traduction validée**.
- Le **rattachement au projet** : `EditorialContent.record` est obligatoire, donc un résumé de document de
  projet ne peut pas y être rangé.
- Les types de résumé, le découpage des documents longs et l'historique des versions.

**Proposition** : une table dédiée (§ 5.3). Les résumés 1.3.0 existants restent visibles sur la fiche.

### 3.6 Lot 5 — notifications

**Ce qui existe**

- Aucun mécanisme de notification.
- Les incidents sont déjà regroupés : un `Incident` réunit les occurrences d'un même problème (empreinte).
  La règle « une fenêtre par nouveau groupe » s'y appuie directement.

**Contraintes techniques**

- La politique de sécurité du contenu (CSP) interdit les scripts en ligne et `eval`. Les filtres d'HTMX du
  type `every 2s [document.visibilityState…]` ne fonctionneraient donc pas.
- La suspension des actualisations quand l'onglet est masqué passera par `static/js/app.js`. Elle concerne
  5 gabarits qui s'actualisent toutes les 2 à 5 s.

### 3.7 Lot 6 — aide intégrée

**Ce qui existe**

- Aucune aide dans l'application.
- La documentation vit dans `docs/evolution-1.2.0/` et `docs/evolution-1.3.0/` : guides d'installation et
  d'utilisation par version.

**Proposition**

- `docs/aide/*.md`, affichée par l'application et réutilisée pour le guide d'utilisation.
- Le rendu Markdown demande une bibliothèque de plus (`markdown`, sous licence BSD). Le contenu est
  contrôlé (fichiers du dépôt), mais le rendu sera tout de même filtré.
- Le guide d'installation au format document et PDF sera produit à partir du même texte.

### 3.8 Lot 7 — Argos par défaut

**Mettre le service par défaut**

- Il suffit de retirer le profil `hors-ligne` du service.
- Pour qu'il reste désactivable, je propose `COMPOSE_PROFILES=argos` dans `.env.example`. Supprimer cette
  ligne désactive le service. C'est le mécanisme standard de Compose ; je n'ai pas pu le vérifier ici.

**Bouton unique** : les quatre opérations existent déjà côté service (`/install`, `/install-sbd`) et côté
application (`argos_packages.py`, avec suivi en base ; un téléchargement interrompu reprend au début du
paquet concerné). Il reste à les enchaîner pour ja→en puis en→fr,
après confirmation de la taille.

**Cœurs « selon le moment » : adaptation nécessaire**

- argostranslate 1.11 fixe le nombre de fils de calcul (`ARGOS_INTER_THREADS`, `ARGOS_INTRA_THREADS`) **à
  la création du traducteur**, une fois par processus. On ne peut pas le changer à chaque demande.
- Proposition :
  - une limite de cœurs et de mémoire du conteneur, fixée par le profil (`.env`) ;
  - une **priorité** dans le service : une demande « maintenant » passe avant le paquet suivant d'un long
    document, donc elle attend au plus la fin d'un paquet en cours ;
  - de petits paquets en journée (par exemple 10 segments) et de grands paquets la nuit.
- Recréer le traducteur avec davantage de fils au début de la plage de nuit est possible, mais coûte un
  rechargement des modèles. À décider après mesure sur ton poste (décision D8).

**À vérifier sur ton poste**

- La taille réelle de l'image (PyTorch CPU, spaCy, Stanza, onnxruntime) : estimée entre 1,5 et 2 Go, sans
  mesure possible ici.
- La durée de construction et la mémoire au repos et pendant une traduction.

### 3.9 Lot 8 — choix du modèle dans une liste

**Le constat du cahier est à nuancer**

- La liste n'est pas inutilisée : elle sert à **refuser** un modèle absent (`ai/services.py`, l. 157) et
  son nombre s'affiche dans Traduction → Moteurs.
- Elle est tronquée chez Anthropic et Gemini (§ 3.1, défaut 2).
- Elle n'est pas filtrée chez OpenAI : les modèles d'image, de son, de vectorisation et de modération y
  figurent. Gemini est déjà filtré sur `generateContent`.

**Écrans où le modèle se tape à la main** :

- préférences IA : modèle par défaut et modèle par fonction ;
- page « IA indisponible » ;
- Traduction → Moteurs : modèle par défaut et deuxième moteur ;
- fiche d'un projet de traduction : mêmes champs, oubliés dans la liste du cahier ;
- Traduction → Évaluation.

Aucune modification de modèle de données n'est nécessaire.

### 3.10 Lot 9 — performances

**Mesures** : 50 000 notices fictives, PostgreSQL 16, médiane de 5 essais (détail en annexe).

| Opération | Temps | Commentaire |
| --- | --- | --- |
| Recherche libre, terme de 2 caractères fréquent (物語, 18 196 réponses) | 131 ms | lecture complète de la table (normal : 36 % des notices) |
| Recherche libre, terme de 4 caractères (藤原定家) | 48 ms | **index trigramme utilisé** |
| Critère Titre (源氏) | 136 ms | lecture complète : index présent mais **non utilisé** |
| Critère Auteur | 158 ms | lecture complète, plusieurs colonnes |
| Détection des doublons d'une notice | 87 ms | 200 notices comparées par le programme |
| Page Consommation, 300 tâches du mois | **1 444 ms, 903 requêtes** | 3 requêtes par tâche |

**Correction du cahier : les index existent déjà**

- La migration `catalog/0002_search_indexes.py` crée déjà l'extension pg_trgm et deux index trigrammes, sur
  `search_text` et `original_title`.
- Deux limites :
  - un trigramme compte **3 caractères**, donc l'index ne sert à rien pour un terme japonais de 2
    caractères (très fréquent) ;
  - les critères par champ utilisent `icontains`, que Django traduit par `UPPER(colonne) LIKE …`, si bien
    que l'index de `original_title` n'est jamais utilisé.

**Conclusion**

- Aucune optimisation de la recherche n'est justifiée **ici**.
- Ton poste (Windows, WSL 2, mémoire partagée) sera plus lent : je propose une commande de mesure
  (`manage.py mesurer_performances`, données fictives dans une base temporaire) à lancer chez toi avant de
  décider.
- La page **Consommation** est à optimiser : une requête groupée par moteur.
- La **réactivité pendant une traduction** dépend surtout des processus web et des workers (§ 3.4). Elle ne
  peut être mesurée qu'avec Docker et Argos réels, donc sur ton poste.

## 4. Écarts avec le cahier des charges

| Cahier | Constat | Proposition |
| --- | --- | --- |
| « `search_text` n'a pas d'index » (§ 9 quater) | Faux : index trigrammes depuis `catalog/0002` | Mesurer sur ton poste ; corriger `icontains` seulement si utile |
| « La liste des modèles n'est utilisée nulle part » (§ 9 ter) | Elle sert à refuser un modèle ; elle est tronquée chez Anthropic et Gemini | Correction en lot 0, listes déroulantes en lot 8 |
| Résumé IA « ajout » (lot 4) | Résumé de notices déjà présent (métadonnées) | Extension, table dédiée |
| Argos : cœurs selon le moment (§ 6) | Impossible par demande avec argostranslate 1.11 | Priorité et taille de paquet ; limite de cœurs fixée par le profil |
| Profils modifiables (§ 6) | Pas d'effet sans redémarrage des conteneurs | Profil calculé au démarrage, choix dans `.env`, commande affichée |
| Écrans du lot 8 | La fiche projet manque à la liste | Ajoutée |

## 5. Choix de modèle de données (à valider avant développement)

Toutes les modifications sont des **ajouts** : nouvelles tables ou nouveaux champs facultatifs. Aucune
donnée existante n'est modifiée ni supprimée. Chaque migration est testée en aller-retour 1.3.0 → 2.0.0 →
1.3.0 sur une base temporaire, avec les outils de recette de la 1.3.0 (`docs/evolution-1.3.0/recette/`).

### 5.1 Trois statuts (lot 2) : table `catalog.RecordStatus`

Une ligne par notice et par statut (proposition par défaut du cahier).

| Champ | Contenu |
| --- | --- |
| `record` | notice (suppression en cascade) |
| `kind` | `notice`, `document` ou `iiif` (unique par notice) |
| `value` | notice et document : `oui`, `non`, `non_verifie` ; IIIF : `absent`, `identifie`, `verifie`, `echec`, `non_verifie` |
| `origin` | `source` (déclaré par la source), `jed` (vérifié par J-ed), `deduit` (adresse construite, décision D5) |
| `checked_at`, `url`, `detail` | date, adresse concernée, détail (nombre de vues, raison d'un échec, mention « consultation sur place ») |

- La vérification IIIF crée une tâche suivie en base : elle peut reprendre, attend un délai entre les
  requêtes et journalise ses échecs.
- Une migration de données calcule les statuts des notices existantes à partir de `raw_data` et des champs
  déjà stockés, **sans appel réseau et sans modifier les notices**. Son retour en arrière vide la table.
- La règle de `normalization.py` qui déduit « image disponible » d'une adresse est conservée pour
  l'ancien champ, qui reste utilisé par les exports 1.0. Elle ne sert plus aux nouveaux statuts.

### 5.2 Tâches et file de nuit (lots 3 et 4) : extension de `TranslationJob`

Je propose d'**étendre** `TranslationJob` plutôt que de créer une table générique : la reprise, le signe
d'activité, les éléments, les plafonds et les pages existent déjà.

| Ajout | Rôle |
| --- | --- |
| `launch` | `immediate`, `scheduled`, `night`, `now` (demande « maintenant » d'une fiche) |
| `scheduled_for`, `queue_position` | heure prévue ; ordre dans la file |
| nouveaux états | `scheduled` (planifiée), `paused` (en pause), `late` (en retard, à confirmer), `done_errors` (terminée avec erreurs) |
| `pause_reason` | plafond, fin de plage, demande de l'utilisateur, service indisponible |
| nouveau type `summary` | tâche de résumé IA (lot 4) |

Les réglages de la plage de nuit vont dans `TranslationPreference`, avec deux champs `night_start` et
`night_end`. La page « Tâches » liste ces tâches pour tous les modules.

Variante possible : une table « file » séparée qui regroupe des tâches. Elle est plus souple, mais c'est
une seconde mécanique à maintenir. Je ne la recommande pas.

### 5.3 Résumés IA (lot 4) : table `ai.Summary`

| Champ | Contenu |
| --- | --- |
| `record`, `project`, `document` | facultatifs, au moins un renseigné : rattachement à la notice et au projet (décision du 14 novembre) |
| `kind` | `court`, `detaille`, `analyse` |
| `language`, `source_kind` | langue du résumé ; texte utilisé (description de notice, document, traduction validée) |
| `content`, `provider`, `model`, `created_at`, `ai_task` | résultat marqué « généré par IA » |
| `previous` | version précédente (historique) |

Le résumé n'entre ni dans la mémoire de traduction ni dans les exports de traduction validée.

### 5.4 Notifications (lot 5) : application `notifications`

- `Notification` : destinataire, type d'événement, gravité, titre, texte, lien, `group_key` (incident),
  canal (`app` seulement en 2.0.0), date de création, date de lecture, date d'affichage de la fenêtre.
- `NotificationPreference` : utilisateur, type d'événement, canal, activé.

## 6. Plan de développement par lots

Pour chaque lot :

- je fais un commit local et je relance la suite complète, `check` et `makemigrations --check` ;
- je produis une archive intermédiaire avec son empreinte et un rapport de lot ;
- j'attends ton accord avant de passer au lot suivant.

L'ordre tient compte des dépendances : les notifications et la liste des modèles servent aux tâches et aux
résumés, et Argos doit être prêt avant la file de nuit.

| Ordre | Lot | Contenu principal | Tests ajoutés (simulés) |
| --- | --- | --- | --- |
| 1 | **0 — Corrections, fiabilité** | `VERSION` = 2.0.0 ; code d'erreur de `backup` et `restore` ; type d'erreur réel ; plus de repli silencieux d'Argos en simulation ; pagination des listes de modèles ; copie externe non bloquante ; 3 erreurs silencieuses ; page « État » avec « Copier le diagnostic » ; `DOSSIER_SAUVEGARDES` ; `mettre-a-jour.ps1` ; test de démarrage d'Argos ; isolation des tests en parallèle ; anomalies de la grille TR1–TR12 dès réception | codes de sortie, Argos injoignable en cours de tâche, pagination simulée, diagnostic sans donnée personnelle |
| 2 | **1 — Interface J-ed** | nom affiché partout (17 endroits), page « À propos », menus (pied de page, menu utilisateur), droits sur les incidents, page hors ligne autonome | droits par rôle, absence de l'ancien nom à l'écran, page hors ligne |
| 3 | **5 — Notifications** | modèle, compteur, fenêtres (actualisation légère avec HTMX), page « Notifications », préférences, fenêtres d'incident par nouveau groupe, suspension des actualisations quand l'onglet est masqué | création, lecture, préférences, seuil de gravité, conformité CSP |
| 4 | **8 — Modèles en liste** | listes déroulantes sur 5 écrans, « Actualiser la liste », filtrage texte, tarif affiché, saisie libre, alerte si un modèle a disparu | réponses simulées par fournisseur, pagination |
| 5 | **2 — Trois statuts** | table, migration de données, pastilles, filtres et tri, détail sur la fiche, vérification IIIF (2.x et 3.0) en tâche reprenable | calcul depuis les données de chaque connecteur, manifestes simulés, aller-retour des migrations |
| 6 | **7 — Argos par défaut** | service sans profil (`COMPOSE_PROFILES`), bouton « Installer la traduction japonais → français », traduction d'essai, invitations, limites de cœurs et de mémoire, priorité « maintenant » | serveur réel avec un traducteur factice, enchaînement de l'installation |
| 7 | **3 — Tâches** | états et ordre, horloge, file de nuit, pause et reprise, retard au redémarrage, plafonds vérifiés à chaque envoi, « Traduire maintenant », 3 workers séparés, profils de machine, indicateur dans la barre de menu, page « Tâches », compte rendu | plage horaire (y compris à cheval sur minuit), plafond atteint en cours de tâche, redémarrage en retard, priorité |
| 8 | **4 — Résumés IA** | table, 3 types, documents longs (découpage puis synthèse), « Résumer maintenant », résumés par lot et dans la file de nuit | estimation, découpage, rattachements, exclusion des exports |
| 9 | **9 — Performances** | Consommation en une requête par moteur ; doublons par pg_trgm si la mesure le justifie ; commande `mesurer_performances` ; serveur web réorganisé si la mesure sur ton poste le justifie | nombre de requêtes plafonné, résultats identiques avant et après |
| 10 | **6 — Aide et guides** | `docs/aide/`, lien « ? » sur chaque écran, recherche, lexique, « Quoi de neuf », guide d'installation (document et PDF), guide d'utilisation | chaque écran principal a sa page d'aide, aucun lien cassé |
| — | **Recette** | aller-retour 1.3.0 → 2.0.0 → 1.3.0, archive et empreinte, CHANGELOG, protocole de vérification, procédure de retour, rapport technique | suite complète |

## 7. Décisions à prendre

Les décisions déjà prises le 14 novembre (cahier, § 12) ne sont pas reprises ici.

| N° | Point | Proposition par défaut |
| --- | --- | --- |
| D1 | File de nuit commencée en retard | Démarre tant que l'on est dans la plage ; hors plage, nouvelle confirmation (proposition du cahier) |
| D2 | Confirmation du coût à la demande | Une confirmation par demande ; seuil facultatif fixé par l'utilisateur (proposition du cahier) |
| D3 | **Nom de projet Docker de la 2.0.0** | Plus de nom d'essai par défaut : `COMPOSE_PROJECT_NAME` obligatoire dans `.env`, repris tel quel par `mettre-a-jour.ps1`. La garde continue de refuser `japon-explorateur` (installation principale) sans `AUTORISER_NOM_PROJET`. Images `japon-explorateur:2.0.0` et `japon-explorateur-argos:2.0.0` |
| D4 | Mode simulé d'Argos | Réglage explicite de l'administrateur (« mode démonstration »), désactivé par défaut ; un service injoignable met la tâche **en pause** avec une notification, sans jamais simuler |
| D5 | Adresse IIIF construite par J-ed (Kokusho) | Statut « identifié », origine « déduite par J-ed » (troisième origine) |
| D6 | Modèle des tâches | Extension de `TranslationJob` (§ 5.2) |
| D7 | Profils de machine | Calcul au démarrage, choix dans `.env`, affichage et conseil sur la page « État » (§ 3.4) |
| D8 | Puissance d'Argos | Priorité et taille de paquet selon le moment ; rechargement du traducteur la nuit à décider après mesure sur ton poste |
| D9 | Identification envoyée aux catalogues | `J-ed/2.0.0 (usage de recherche personnel)` ; le manifeste des sauvegardes garde son ancien nom technique |
| D10 | Restauration des fichiers | Corriger le message (« fichiers de la sauvegarde ajoutés ou remplacés ») plutôt que supprimer les fichiers récents |
| D11 | Rendu de l'aide | Bibliothèque `markdown` (BSD), rendu côté serveur, contenu filtré |
| D12 | Types de résumé | Court, détaillé, fiche d'analyse (proposition du cahier) |
| D13 | Nom de l'instance enregistré en base | « J-ed » par défaut pour les nouvelles installations ; valeurs existantes inchangées (modifiables dans Administration → Réglages) |

## 8. Limites de l'environnement de développement

- **Docker** : le client est présent, mais aucun service Docker ne tourne. Je ne peux donc construire ni
  démarrer aucune image ; la configuration Compose sera relue, sans `docker compose config`.
- **Index PyTorch** inaccessible : la vraie bibliothèque Argos ne peut pas être exécutée ici. La série de
  tests « avec les vraies bibliothèques » prévue par le cahier se lancera dans l'image Argos, sur ton poste.
- **PowerShell** absent : `mettre-a-jour.ps1` sera relu, mais pas exécuté. Si l'installation de PowerShell
  depuis GitHub est permise, j'en vérifierai au moins la syntaxe.
- **Moteurs et sources réels** : DeepL, Google, les IA et les catalogues ne sont testés qu'en simulation.
  Leur statut reste « testé en simulation ; test réel à confirmer ».
- **Mesures** : elles sont faites sur un serveur Linux, plus rapide que Windows avec WSL 2. Seules les
  mesures faites sur ton poste comptent pour décider d'une optimisation.

## Annexe — Méthode des mesures

- Base PostgreSQL 16 temporaire, migrée en 1.3.0.
- 50 000 notices **fictives**, générées par un script hors dépôt : titres faits de kanji et de kana tirés au
  hasard, 9 auteurs, 4 institutions fictives, descriptions de 3 à 15 « mots ».
- Médiane de 5 exécutions de `local_search` (comptage, puis première page de 20) et de
  `duplicate_candidates`.
- Page Consommation : 300 tâches fictives de 10 éléments, nombre de requêtes compté par
  `CaptureQueriesContext`.
- Plans d'exécution relevés par `EXPLAIN ANALYZE`. La table des notices occupe 121 Mo et l'index
  trigramme de `search_text` environ 42 Mo.
- Aucune donnée réelle, aucune clé, aucun appel réseau.
