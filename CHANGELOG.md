# Historique des versions

## 2.0.0 — en cours de développement

Version de consolidation, renommée **J-ed**. Base : version 1.3.0-rc3, étiquette `v1.3.0-rc3` (commit
`d7296d4`). Audit et plan : `docs/evolution-2.0.0/01-audit.md`.

- **Lot 8 — choix du modèle d'IA dans une liste** (15 novembre 2026, rapport :
  `docs/evolution-2.0.0/rapport-lot-8.md`) :
  - liste déroulante des modèles du fournisseur choisi, mise à jour sans recharger la page quand on change de
    fournisseur, dans les six écrans où l'on choisit un modèle : préférences IA (modèle par défaut et par
    fonction), page « IA indisponible », Traduction → Moteurs (moteur par défaut et deuxième moteur), fiche d'un
    projet de traduction, Traduction → Évaluation ;
  - seuls les modèles de texte sont proposés : images, son, synthèse vocale, transcription, vectorisation et
    modération sont écartés (OpenAI, Gemini, services compatibles OpenAI) ; les listes déjà enregistrées sont
    filtrées à l'affichage, le test de connexion enregistre la liste filtrée ;
  - tarif estimé à côté du modèle quand l'administrateur l'a saisi ; date de la liste ; bouton « Actualiser la
    liste » qui interroge le fournisseur avec la clé de l'utilisateur, sur son action seulement (l'échec est
    affiché et la liste précédente conservée) ;
  - option « Autre modèle (saisie libre) » ; avertissement, sans changement d'office, quand le modèle enregistré
    n'apparaît pas dans la liste ;
  - aucun changement de la base de données : le champ du modèle reste la valeur enregistrée.
- **Lot 5 — notifications** (15 novembre 2026, rapport : `docs/evolution-2.0.0/rapport-lot-5.md`) :
  - mécanisme unique (application `notifications`, migration `notifications.0001`, deux tables) pour les
    fins de tâches et les alertes de dysfonctionnement ; canal « dans l'application » seulement ;
  - **fenêtres** en bas à droite : fin d'une traduction (terminée, avec des erreurs, en échec, interrompue),
    export prêt ou en échec, synchronisation à valider ou en échec ; lien « Voir le compte rendu » et bouton
    « Vu ». Une fenêtre n'est montrée qu'une fois ; celles d'un utilisateur absent attendent sa prochaine visite ;
  - **administrateur** : une fenêtre par nouveau groupe d'incidents (pas une par occurrence) ou par problème
    corrigé qui revient, à partir d'un seuil de gravité réglable (« Erreur et plus » par défaut), avec un lien
    vers le dysfonctionnement ; rien n'est envoyé pour une opération annulée ;
  - **compteur** des notifications non lues sur le bouton du menu à son nom (il remplace la pastille provisoire
    des incidents du lot 1), entrée « Notifications » dans ce menu ;
  - page **« Notifications »** : historique, filtres (état, type), « Marquer comme lue », « Tout marquer comme
    lu » ; page **« Préférences »** : activation par type d'événement, seuil des alertes ;
  - **essai** : « Envoyer une notification d'essai » et, pour l'administrateur, « Envoyer une alerte de
    dysfonctionnement d'essai », sans lancer de tâche ni écrire au journal ;
  - interrogation légère toutes les 30 secondes (HTMX), **suspendue quand l'onglet est masqué** et reprise dès
    son retour ; même suspension pour les 5 pages qui s'actualisent toutes les 2 à 5 secondes ; aucun script en
    ligne (politique de sécurité inchangée) ;
  - **correctif** : le cache du navigateur (service worker) portait seulement le numéro de version, si bien
    qu'entre deux livraisons de la 2.0.0 le navigateur pouvait garder l'ancien `app.js` et l'ancien `app.css`.
    Son nom suit désormais le contenu de ces fichiers ;
  - `verifier_fonctionnalites` contrôle les notifications (fenêtre, compteur, « Vu », préférences, alertes
    réservées à l'administrateur, seuil) ; pages « Notifications » et « Préférences » ajoutées au contrôle des
    pages.
- **Correctif — tests lancés dans une installation** (15 novembre 2026, archive `lot2b`) : avec
  `verifier-j-ed.ps1 -AvecTests`, la suite de tests s'exécute dans le conteneur de l'installation. Elle aurait
  copié des sauvegardes fictives dans le dossier Windows des sauvegardes et envoyé des tâches d'essai à la file
  Redis de l'installation (constaté en simulant le conteneur, avant toute exécution sur le poste). En mode test,
  dossiers de données, copie externe, file de tâches, cache, Argos, adresses d'IA locales et clé CiNii sont
  désormais isolés ; un test le vérifie.
- **Lot 2 — trois statuts indépendants par notice** (15 novembre 2026, rapport :
  `docs/evolution-2.0.0/rapport-lot-2.md`) :
  - chaque notice porte trois statuts, sans qu'aucun ne se déduise d'un autre : **notice disponible** (oui, non,
    non vérifié), **document consultable** (oui, non, non vérifié) et **IIIF** (absent, identifié, vérifié,
    vérification en échec, non vérifié), chacun avec son origine (déclaré par la source, vérifié par J-ed,
    déduit par J-ed), sa date, l'adresse concernée et un détail ;
  - calcul à partir des métadonnées enregistrées, **sans appel réseau**, règles propres à chaque source (Japan
    Search, Kokusho, NDL, CiNii, fichiers importés, base locale). Un « oui » ou un « absent » n'est retenu que
    si la source le dit ; un lien vers une numérisation sans précision d'accès reste « non vérifié » ; une
    consultation réservée (sur place, réseau de bibliothèques) donne « non consultable », avec la mention de
    la source ;
  - nouvelle table `catalog_recordstatus` (migration `catalog.0006`) et statuts des notices existantes
    (migration `catalog.0007`, sans appel réseau ni modification des notices ; son retour vide la table).
    L'ancien champ « accès numérique » reste inchangé pour les exports au format 1.0 ;
  - **vérification du manifeste IIIF** sur demande (fiche, ou sélection de la Bibliothèque) : téléchargement,
    conformité à l'API de présentation IIIF 2.x ou 3.0, nombre de vues, accès à une image de la première vue.
    Demande enregistrée en base, reprise automatique après un arrêt (toutes les 10 minutes), délai entre deux
    notices (`IIIF_CHECK_DELAY_SECONDS`, 2 s par défaut), échecs inscrits au journal des dysfonctionnements
    avec leur raison ;
  - **interface** : trois pastilles dans les résultats de recherche, la Bibliothèque et la fiche ; filtres et
    tri par statut (résultats d'une recherche, Bibliothèque, recherche avancée dans la base locale), à la
    place du filtre « Document numérisé » ; section « Disponibilité » de la fiche avec le détail de chaque
    statut et le bouton « Vérifier le manifeste IIIF » ;
  - `verifier_fonctionnalites` contrôle les trois statuts d'une notice fictive et compte les notices sans
    statut ;
  - **statuts dans les exports** (décision du 15 novembre 2026, archive `lot5b`) : ligne « Disponibilité » des
    fiches Word, PDF, texte et site HTML (pastilles), à la place de « Accès numérique » ; colonnes
    `status_notice`, `status_document` et `status_iiif` des profils CSV bibliographie, historique et inventaire,
    décrites dans le fichier des colonnes ; clé `statuses` de chaque notice dans le JSON, avec origine, date,
    adresse et détail (ajout compatible avec le schéma 1.0, qui l'accepte et la décrit). Le profil de réimport et
    l'ancien champ `digital_access` restent inchangés ; une réimport ne signale pas ces statuts comme colonnes
    inconnues.
- **Lot 1 — interface** (15 novembre 2026, rapport : `docs/evolution-2.0.0/rapport-lot-1.md`) :
  - l'application s'affiche sous le seul nom **J-ed** : barre de menu, titres des pages, pied de page,
    application installable, page de connexion, en-têtes des exports et des rapports de diagnostic, gestion
    interne. Les noms techniques ne changent pas (projet Docker, images, volumes, dépôt) ; le manifeste des
    sauvegardes garde sa valeur technique. Nom d'instance « J-ed » par défaut pour une nouvelle installation,
    valeur existante conservée (D13, migration `core.0004`, sans effet sur la base) ; en-tête `User-Agent`
    envoyé aux catalogues : `J-ed/2.0.0 (usage de recherche personnel)` (D9) ;
  - page **« À propos »** (lien du pied de page, demande U3) : version, origine du projet, logiciels
    libres utilisés ;
  - **menus** : « Administration » et « Dysfonctionnements » quittent le menu du haut ; ils sont dans le menu à
    son nom et en pied de page, pour l'administrateur seulement. La pastille des incidents nouveaux est sur le
    bouton du menu à son nom ;
  - **journal des dysfonctionnements réservé à l'administrateur** (liste, détail, analyse, export, capture).
    « Signaler un problème » reste ouvert à tous ; après l'envoi, un chercheur revient à sa page avec
    l'identifiant du signalement. Les liens vers le journal (fiche d'une source, état d'une recherche) ne sont
    montrés qu'à l'administrateur ; le chercheur voit toujours le message d'erreur ;
  - **page « J-ed ne répond pas »** : la page mise en cache par le navigateur est autonome, sans menu ni numéro
    de version, et conseille de vérifier Docker Desktop (constat du 14 novembre 2026). Le contrôle de santé de
    Docker passe par une adresse dédiée, `/sante/` (le serveur répond et la base est joignable) ;
  - **bas de page des exports** (demande U2) : date et heure de production, J-ed et sa version, identifiant de
    connexion (case « Ne pas indiquer mon identifiant »), identifiant de l'export, numéro de page ; Word, PDF,
    HTML, texte et exports des projets de traduction ;
  - `verifier_fonctionnalites` contrôle aussi « À propos », `/sante/` et le refus du journal au chercheur ;
    `verifier-j-ed.ps1` interroge `/sante/`.
- **Lot 0 — corrections et fiabilité** (14 novembre 2026, rapport : `docs/evolution-2.0.0/rapport-lot-0.md`) :
  - numéro de version 2.0.0 ; images `japon-explorateur:2.0.0` et `japon-explorateur-argos:2.0.0` ;
    `COMPOSE_PROJECT_NAME` **obligatoire** dans `.env` (plus de nom d'essai par défaut, décision D3) ; port
    par défaut 8000 ; les noms `japon-explorateur` et `japon-explorateur-essai` restent protégés
    (`AUTORISER_NOM_PROJET` pour une mise à jour en place) ;
  - **sauvegardes** : `manage.py backup` et `restore_backup` se terminent avec le code 1 en cas d'échec (y
    compris une vérification `--verify` en échec) ; le message d'échec donne le **type d'erreur réel** et
    l'incident est journalisé ; une copie externe impossible ne fait plus échouer la sauvegarde (avertissement
    et incident) ; la copie est contrôlée par son empreinte ; la restauration depuis l'interface est refusée si
    la sauvegarde de sécurité échoue ; le message de restauration dit que les fichiers plus récents sont
    conservés (décision D10) ;
  - **sauvegardes visibles dans Windows** : `DOSSIER_SAUVEGARDES=…` dans `.env` (monté sur `/backups-externes`) ;
    sans cette ligne, la copie reste dans le volume Docker `sauvegardes-externes` ;
  - **Argos ne simule plus jamais en silence** (décision D4) : nouveau réglage « Argos : mode démonstration »
    (Administration → Paramètres, désactivé par défaut) ; sans lui, un service injoignable **interrompt** la
    tâche (reprenable, éléments non traités laissés en attente) et des paquets manquants l'arrêtent ; en 1.3.0,
    un service devenu injoignable en cours de tâche produisait des simulations pour la suite ;
  - **listes de modèles d'IA complètes** : toutes les pages sont lues chez Anthropic (20 par page) et Gemini
    (50 par page) ; liste conservée jusqu'à 2 000 modèles ; un modèle n'est plus refusé si la liste est tronquée ;
  - erreurs autrefois ignorées en silence, désormais journalisées : police PDF illisible, empreinte d'export
    incalculable, détection d'un export J-ed à l'import ;
  - **page « État de l'installation »** (Administration, administrateur seulement) : version, base et migrations,
    Redis, workers, planificateur (signe de vie toutes les 5 minutes), Argos et traduction d'essai, sauvegardes
    (alerte au-delà de 36 h, erreur au-delà de 7 jours), clés des services en ligne (comptées, jamais
    affichées), espace disque, mémoire et cœurs accordés par Docker ; bouton **« Copier le diagnostic »**
    (sans clé, nom de compte ni texte ; chemins personnels masqués) ; commande `manage.py etat_installation`
    (`--json`, code 1 en cas de problème) ;
  - **test de démarrage d'Argos** : traduction d'une phrase fictive après chaque installation de paquet réussie
    et sur demande depuis la page « État » ;
  - **`mettre-a-jour.ps1`** : mise à jour en une commande (contrôles, empreinte, sauvegarde vérifiée et copiée
    hors de Docker, nouveau dossier, reprise du `.env`, arrêt sans effacement, démarrage, contrôle final),
    arrêt avec un message clair et la marche à suivre pour revenir en arrière ;
  - tests : isolation des tests en exécution parallèle (dossier temporaire partagé supprimé trop tôt ; journal
    du service Argos écrit avant la réponse) ; tests de la 1.3.0 propres aux valeurs de l'essai 1.3.0 remplacés
    par leurs équivalents 2.0.0 ; tests qui utilisaient la simulation d'Argos passés en mode démonstration.
- **Outils de vérification** (14 novembre 2026, en complément du protocole manuel) :
  - `manage.py verifier_fonctionnalites` (`--json`, `--sources`) : exerce avec des données **fictives**, dans
    une transaction annulée, la recherche, les notices et leurs versions, les doublons, la lecture des imports, la
    Bibliothèque et les dossiers, les six formats d'export (police japonaise des PDF comprise), les projets de
    traduction (découpage, validation, mémoire, glossaire, export bilingue), Argos, un aller-retour avec un worker,
    l'intégrité de la dernière sauvegarde, 17 pages principales avec leur politique de sécurité et les droits
    d'accès ; **la base n'est pas modifiée** ; code de sortie 1 en cas de problème ;
  - `verifier-j-ed.ps1` (Windows) : contrôle le dossier, le `.env` (valeurs à remplacer, nom protégé), le dossier
    des sauvegardes, Docker (mémoire, conteneurs, port publié seulement sur l'ordinateur, volumes), les pages qui
    répondent, puis lance la vérification ci-dessus (`-AvecSources`, `-AvecTests`) ; rapport texte sans clé ni
    nom de compte.
- **Argos traduit de nouveau avec les paquets réels** (constat du 15 novembre 2026 sur le poste de
  l'utilisateur, après mise à jour) : la correction de la rc3 (`resources.json`) fonctionnait, mais les modèles
  de découpage en phrases Stanza livrés dans les paquets ja→en 1.1 et en→fr 1.9 ne se chargent pas avec
  Stanza 1.10.1 (`KeyError: 'feat_dropout'`). Le service découpe désormais lui-même par la ponctuation
  (`ARGOS_DECOUPAGE=jed`, par défaut ; les segments de J-ed sont déjà des phrases) : aucun modèle de découpage
  n'est chargé ni téléchargé ; `ARGOS_DECOUPAGE=paquet` rétablit l'ancien comportement. Les erreurs internes
  donnent la clé manquante (`KeyError : 'packages'`) et le journal du service dit où elles se produisent, sans
  aucun texte. Nouveau `docker/argos/diagnostic.py` (versions, paquets, traduction d'essai fictive pas à pas).
- **Valider en une fois les traductions de notices** (demande du 15 novembre 2026) : bouton « Tout valider et
  adopter » sur la fiche (couche éditoriale), sur la page « Traductions » d'une notice et sur la page d'une
  tâche de traduction de notices. Pour chaque notice et chaque champ, la proposition la plus récente est
  adoptée (la précédente redevient proposée) ; sont écartées, avec leur raison, les simulations, les
  traductions dont l'original a changé et les propositions plus anciennes. Réservé à l'administrateur (C2),
  avec confirmation ; tout ou rien. Corrigé au passage : deux adoptions successives sur une même notice
  pouvaient donner deux versions de même numéro ; la page « Traductions » plantait pour une proposition sans
  moteur ni modèle indiqué (saisie manuelle).
- **Argos reste démarré après une mise à jour** (constat du 15 novembre 2026, `verifier-j-ed.ps1` sur le poste
  de l'utilisateur) : quand Argos était en service, `mettre-a-jour.ps1` le redémarrait mais n'écrivait pas
  `COMPOSE_PROFILES=hors-ligne` dans le nouveau `.env` ; il ajoute désormais cette ligne, avec un commentaire.
  `verifier-j-ed.ps1` signale « À surveiller » un Argos en service sans cette ligne, au lieu de « non activé ».
  - Base de données : migrations **additives** `core.0002` (champ `argos_demo_mode`) et `core.0003` (table
    `core_servicecheck`), testées en aller-retour 1.3.0 → 2.0.0 → 1.3.0 sur une base temporaire.

## 1.3.0 — 14 novembre 2026 (candidate, en attente du protocole de vérification)

Évolution : module de traduction. Base : version 1.2.0, étiquette `v1.2.0-reference` (commit `4982a3d`). Voir `docs/evolution-1.3.0/`.

- **Socle (lot 0)** : numéro de version 1.3.0 ; installation d'essai 1.3.0 isolée de l'installation principale et de l'essai 1.2.0 (projet Docker `japon-explorateur-essai-130`, port 8002, image `japon-explorateur:1.3.0`) ; les conteneurs refusent de démarrer sous le nom de projet de l'installation principale ou de l'essai 1.2.0 ; le script `reinitialiser-essai.ps1` refuse aussi l'essai 1.2.0 (nom et port 8001).
- **Fondations du module de traduction (lot 1)** : application `apps/translation` (12 tables), rubrique « Traduction » dans le menu (administrateur et chercheur ; pas le lecteur), droits d'accès (projet à un seul propriétaire ; l'administrateur ne voit que les métadonnées d'un projet confidentiel d'autrui ; seul le propriétaire valide). Compte anonymisé ou supprimé : ses projets et glossaires de traduction sont confiés à un administrateur (celui qui anonymise), ses réglages et clés de moteurs effacés ; suppression refusée s'il n'existe aucun autre administrateur actif. Contenu des projets absent de l'interface d'administration Django.
- **Retouches transverses (lot 2)** : nouvelle origine « Traduction automatique » ; l'option d'export « Inclure traductions automatiques et contenus IA » couvre aussi cette origine, et le récapitulatif des exports parle de « contenus générés (IA, traduction automatique) » (la clé de métadonnées `contains_ai_content` garde son nom) ; les erreurs des fournisseurs IA portent le code HTTP et une nature (messages inchangés) ; `decode_text` déplacée dans `apps/core/encoding.py` (même comportement, même nom dans l'import) et nouvelle détection d'encodage avec indice de fiabilité ; module « traduction » et huit catégories dans le journal des dysfonctionnements. Constats sur l'existant : `docs/evolution-1.3.0/constats-existant.md`.
- **Moteurs de traduction (lot 3)** : contrat commun et registre ; connecteurs DeepL (offre gratuite ou payante), Google Traduction Basic v2, Argos Translate (client du service local, **mode simulé** signalé tant que le service et ses paquets ne sont pas installés) et IA en ligne (clés du module IA, consentement respecté, réponse JSON vérifiée) ; client HTTP sans aucun texte dans les diagnostics ; erreurs classées et journalisées dans le module « traduction » ; page **Traduction → Moteurs** (lieu unique du choix des moteurs, clés chiffrées jamais réaffichées, bouton « Tester » sans texte réel pour DeepL). Statut de chaque moteur : **développé et testé en simulation ; test réel à confirmer**. Tarifs DeepL et Google non renseignés (`reference/tarifs-traduction.json`, à compléter).
- **Chaîne de traitement (lot 4)** : toute traduction est une tâche — préparation (rien n'est envoyé), écran de confirmation (volume, éléments non envoyés car déjà validés ou repris de la mémoire, coût estimé, quota lu), seconde confirmation au-delà du seuil, exécution par paquets dans la file Celery « traduction » (le worker écoute désormais `celery,traduction`), suivi en direct, annulation, reprise sans renvoi après interruption, relance des échecs, deuxième moteur seulement proposé. Refus côté serveur : projet confidentiel avec moteur en ligne, plafond mensuel du moteur, plafond IA, consentement IA. Une tâche IA par appel IA. Mémoire de traduction exacte (NFKC), limitée aux projets du même compte. Contrôles à la réception (vide, identique, encore en japonais). Traductions de notices enregistrées dans la couche éditoriale (origine « Traduction automatique » ou « IA »), notice d'origine inchangée. Rubrique **Traduction → Tâches**.
- **Traduction des notices (lot 5)** : bouton « Traduire… » sur la fiche et dans la Bibliothèque (sélection), vers le module de traduction (champs titre et description, sujets et lieu en option ; moteur par défaut ou deuxième moteur ; confirmation avant envoi). Page de la notice : original, traduction adoptée et toutes les propositions avec moteur, date, alertes, mention « Simulation ». **Valider une traduction de notice l'adopte dans la fiche** (sur la fiche comme dans le module) et la traduction validée précédente du même champ redevient proposée ; validation réservée à l'administrateur. La logique « Adopter » est extraite dans `catalog/services.py` sans changement de comportement. L'ancienne traduction IA disparaît de l'interface (fiche, Bibliothèque, ligne « fournisseur pour la traduction » des préférences IA) ; son code et les valeurs enregistrées sont conservés. Reprise unique : si un utilisateur traduisait par IA en 1.2.0, cette IA devient son moteur par défaut. La case « Traduction » des préférences IA reste l'autorisation d'utiliser les IA pour traduire.
- **Projets et documents (lot 6)** : rubrique **Traduction → Projets** (création, modification, suppression par le propriétaire après recopie du titre) ; import de documents par collage, .txt (UTF-8, Shift_JIS, EUC-JP, UTF-16 ; aperçu et confirmation si l'encodage est incertain), .docx (texte) et PDF avec texte (sans OCR) ; découpage automatique en segments qui redonne toujours exactement le texte importé (fins de phrase, citations 「」『』, lectures entre parenthèses, paragraphes) ; fusion et division de segments et chapitres, traductions conservées ; écran de travail à deux colonnes (filtres par état et chapitre, traduction par sélection, chapitre ou segments non traduits, validation des dernières propositions) ; page d'un segment avec toutes ses versions, correction (nouvelle version liée), saisie libre, validation (une seule par segment, par le propriétaire). Confidentialité : moteurs en ligne refusés, l'administrateur ne voit que les métadonnées d'un projet confidentiel d'autrui ; une notice peut être copiée dans un projet sans rien publier, puis sa traduction validée publiée dans la notice par une action explicite et confirmée. Limites : `docs/evolution-1.3.0/07-limitations-connues.md`.
- **Glossaires et mémoire de traduction (lot 7)** : rubrique **Traduction → Glossaires** (création, saisie et modification des entrées avec lecture, catégorie, variantes de graphie, traductions à éviter, remarque et source de la décision ; doublons refusés, y compris entre terme et variante ; version du glossaire incrémentée à chaque modification) ; import CSV avec vérification préalable sans enregistrement (séparateur et encodage détectés, en-têtes français acceptés, doublons du fichier ou du glossaire ignorés ou mis à jour au choix, erreurs par ligne) et export CSV (UTF-8 avec BOM, cellules protégées contre l'exécution de formules). Glossaires rattachés aux projets par ordre de priorité, le premier l'emportant en cas de doublon ; contradictions entre glossaires affichées sur la page du projet ; « Ajouter un terme au glossaire » et termes présents affichés sur la page d'un segment. Application par moteur : **DeepL** — copie envoyée seulement par le bouton « Envoyer à DeepL » coché et confirmé par le propriétaire (paire vérifiée auprès de DeepL ; termes à éviter et remarques non envoyés ; refusé pour un glossaire utilisé par un projet confidentiel), utilisée tant qu'elle correspond à la version du glossaire, suppression possible de la copie distante ; **IA** — termes présents dans le paquet ajoutés à la consigne, avec les traductions à éviter ; **Google, Argos** — aucune prise en charge. Contrôle terminologique local pour tous les moteurs et pour les traductions saisies (casse, accents, macrons, pluriels simples) : il **signale sans corriger** (terme attendu absent, traduction à éviter présente). Chaque version enregistre les glossaires appliqués (version et mode d'application) ; l'écran de confirmation indique comment chaque glossaire sera appliqué. Rubrique **Traduction → Mémoire de traduction** (décision E7) : paires validées de ses propres projets, recherche, filtre par projet et par état, exclusion et réintégration ; la mémoire de chaque compte n'est visible que par lui, administrateur compris. Un glossaire servant un projet confidentiel d'autrui n'est visible de l'administrateur qu'en métadonnées. Aucune migration.
- **Exports (lot 8)** : rubrique **Traduction → Exports** et bouton « Exporter » sur la page du projet et sur l'écran de travail d'un document (décisions A4 et E4). Formats : texte bilingue (.txt ou Markdown, original et traduction alternés par segment), tableau bilingue CSV (identifiant, document, chapitre, position, original, traduction, statut, simulation, moteur, origine, validation, alertes ; UTF-8 avec BOM, cellules protégées), traduction seule (.txt ou Markdown, paragraphes de l'original conservés) et Word bilingue en tableau à deux colonnes (police japonaise Yu Mincho déclarée). Choix : versions validées seulement, ou validées à défaut de dernière proposition (jamais une version rejetée), alors signalées « non validée ». En-tête de chaque fichier : moteurs utilisés, proportion de segments validés, nombre de propositions et de segments non traduits, version de l'application, mention **Simulation** dès qu'une traduction vient d'un moteur simulé, mention du caractère confidentiel. Exports produits au téléchargement (aucun fichier conservé), par document ou pour le projet entier, **réservés au propriétaire du projet** (l'administrateur compris ne peut pas exporter le projet d'un autre) ; chaque export est consigné dans le journal d'audit (sans texte). Glossaires : export CSV du lot 7, repris dans la rubrique. Dans `apps/exports/generators/docx_gen.py`, la fonction des polices japonaises reçoit le nom public `set_fonts` ; l'ancien nom `_set_fonts` reste (exports de notices inchangés). Aucune migration.
- **Service Argos Translate facultatif (lot 9)** : service Docker `argos` (profil `hors-ligne`, image séparée `japon-explorateur-argos:1.3.0`, PyTorch « CPU », dépendances figées dans `docker/argos/requirements.txt`, **aucun port publié**, refus de démarrer sous le nom de projet de l'installation principale ou de l'essai 1.2.0) ; serveur HTTP interne en bibliothèque standard (`docker/argos/server.py`) dont le journal ne contient jamais de texte. Page **Traduction → Moteurs locaux** : état du service, paquets nécessaires (japonais → français par l'anglais) et installés avec leur version. **Téléchargement des paquets au choix de l'utilisateur** (décision F du 14 novembre 2026) : consultation de l'index sans téléchargement, puis choix des paquets et confirmation explicite ; ou installation depuis un fichier `.argosmodel` (sans Internet) ; désinstallation. Gestion réservée à l'administrateur (paquets communs à l'installation). Chaque installation est une tâche suivie en base, exécutée par le worker et reprenable ; un paquet déjà installé n'est pas retéléchargé. **Fonctionnement hors ligne garanti par le service** : Stanza appelé sans téléchargement, traduction refusée avec un message clair si le modèle de découpage en phrases (MiniSBD) manque, ce modèle étant récupéré pendant le téléchargement d'un paquet ou sur choix explicite. Volumes `argos-packages` et `argos-depot` ; `reinitialiser-essai.ps1` **conserve les paquets** lors d'une réinitialisation normale (décision E6), les efface avec `-Complet` (ainsi que l'image du service), et redémarre Argos s'il était démarré. Variables `TRANSLATION_ARGOS_INSTALL_TIMEOUT` et adresse par défaut `http://argos:5000` (`.env.example`). Notice : `docs/evolution-1.3.0/notice-argos.md`. Statut : **développé et testé en simulation ; construction de l'image et traduction réelle à confirmer sur le poste de l'utilisateur.**
- **Évaluation et consommation (lot 10)** : rubrique **Traduction → Évaluation** (cahier des charges § 15) — un projet coché « Corpus de référence » peut être traduit par plusieurs moteurs choisis (DeepL, Google, Argos, jusqu'à deux IA) ; une tâche par moteur, sur tous les segments du corpus, sans reprise de la mémoire ni exclusion des segments validés ; **rien n'est envoyé avant la confirmation** du coût estimé de chaque moteur (seconde confirmation au-delà du seuil ; moteurs en ligne écartés pour un corpus confidentiel) ; résultats datés et conservés (versions proposées), affichés côte à côte ; **notation humaine** (correcte, acceptable, fautive, contresens, avec commentaire) et répartition des notes données — aucun score automatique. Rubrique **Traduction → Consommation** (§ 14) — par moteur et par mois (12 derniers mois) : tâches, caractères envoyés, traductions reçues, coût estimé par devise (somme des coûts enregistrés avec chaque traduction ; coût des tâches IA pour les IA, avec leurs jetons), ligne à part pour les traductions de l'ancien module IA, détail des tâches du mois ; plafonds du mois en cours (caractères par moteur, budget IA) ; montants présentés comme des estimations, la facture du fournisseur faisant foi. Aucune migration.
- **Conditions des fournisseurs avant le premier envoi (complément du lot 10, cahier des charges § 13)** : résumé daté de ce que chaque fournisseur en ligne fait des textes envoyés (conservation, utilisation pour l'amélioration du service, différences entre offre gratuite et payante), avec les liens vers les conditions officielles, vérifié sur leurs pages le 14 novembre 2026 (`reference/conditions-fournisseurs.json` : DeepL, Google Cloud Translation, OpenAI, Anthropic, Gemini, service compatible OpenAI). Avant le premier envoi à un fournisseur (traduction, comparaison sur le corpus, envoi d'un glossaire à DeepL), le résumé s'affiche et l'envoi exige la case « J'ai pris connaissance » ; la prise de connaissance est enregistrée dans le journal des actions (aucune nouvelle table) et redemandée quand le résumé du fournisseur est revérifié. Argos n'est pas concerné (rien ne quitte l'ordinateur). Tous les résumés sont consultables dans Traduction → Moteurs. Aucune migration.
- **Recette (14 novembre 2026)** : migrations aller-retour testées sur une base d'essai temporaire avec données fictives (aucune perte ; `docs/evolution-1.3.0/recette-migrations.md`) ; commande en lecture seule `verifier_retour_120` (avec `--exporter`) et procédure de retour à la 1.2.0 (`retour-1.2.0.md`, correctif inverse) ; guide d'installation, guide d'utilisation, notices DeepL, Google et Argos, protocole TR1 à TR13, rapport technique. Statut de chaque moteur : **développé et testé en simulation ; test réel à confirmer**.
- **Mise à jour d'une installation existante (14 novembre 2026)** : la 1.3.0 refuse toujours de démarrer sous le nom de projet Docker de l'installation principale ou de l'essai 1.2.0, **sauf autorisation explicite** : la ligne `AUTORISER_NOM_PROJET=<même nom>` dans `.env` permet de mettre à jour cette installation en gardant ses données (conteneurs de l'application et service Argos). `reinitialiser-essai.ps1` accepte, avec la même autorisation, l'essai 1.2.0 mis à jour (jamais l'installation principale). Notice pour débutant : mettre à jour, vider ou réinstaller dans Docker, avec l'installation de Docker Desktop sous Windows 11 en annexe.
- **Correctifs du protocole TR8 (1.3.0-rc3, 14 novembre 2026)** : premier essai réel d'Argos sur le poste de l'utilisateur. (1) Les paquets ja→en 1.1 et en→fr 1.9 de l'index livrent un `resources.json` de Stanza à l'ancien format (sans rubrique « packages ») : Stanza 1.10, appelé sans téléchargement, levait `KeyError: 'packages'` et toute traduction échouait (HTTP 500). Le service lit désormais une **copie adaptée** de ce fichier, écrite dans son cache (découpage en phrases seul, modèle fourni par le paquet) ; le paquet n'est pas modifié et rien n'est téléchargé. Vérifié avec le code de résolution réel de Stanza 1.10.1 ; le chargement des modèles des paquets reste à confirmer sur le poste. (2) Une erreur interne du service n'est plus présentée comme « momentanément indisponible (HTTP 500) » : l'application affiche son type (par exemple « Service Argos : Erreur interne (KeyError). ») et le journal du service l'enregistre, toujours sans aucun texte. Relevé, non corrigé dans la 1.3.0 : la commande `backup` affiche « Échec » mais se termine sans code d'erreur (présent depuis la 1.2.0 ; prévu au lot 0 de la 2.0.0).
- Base de données : migrations `catalog.0005` et `incidents.0002`, **listes de choix uniquement, aucune instruction SQL** ; migration **additive** `translation.0001_initial` (nouvelles tables uniquement ; aucune table existante modifiée) ; `translation.0002_paquets_argos` (nouvelle nature de tâche « Installation de paquets Argos », **liste de choix uniquement, aucune instruction SQL**). Retour : `python manage.py migrate translation zero`.

## 1.2.0 — 13 novembre 2026

Évolution ciblée : sources documentaires japonaises et journal des dysfonctionnements. Voir `docs/evolution-1.2.0/`.

- **Sources** : nouveau connecteur CiNii Research (et CiNii bibliothèques universitaires) ; Archives nationales via Japan Search ; outil « Trouver une base Japan Search » ; Japan Search corrigé (variantes en OU, champs documentés, dates) ; lien vers les documents numérisés NDL.
- **Recherche** : cinq états distincts par source (résultats, aucun résultat, indisponible, erreur technique, réponse illisible) ; variantes de graphie libres, sans suffixe et attestées ; tri par auteur et institution ; filtre « document numérisé ».
- **Journal des dysfonctionnements** : enregistrement automatique et expurgé, regroupement, gravités, statuts de correction, réapparitions, signalement manuel, analyse, export de diagnostic.
- **Socle** : numéro de version unique (`VERSION`) ; installation d'essai isolée (projet Docker, volumes, port 8001, image) ; `pypdf` ajouté aux dépendances.
- **Outil** : script `reinitialiser-essai.ps1` (Windows) pour remettre l'installation d'essai à zéro, avec contrôles de sécurité qui protègent l'installation principale.
- **Correctif (13/11, incident INC-20261113-41FDF0)** : erreur 500 au clic sur « Comparer avec la base » sous Docker. Le module `packaging`, requis par kombu 5.7 (transport Redis de Celery) mais non déclaré par ce paquet, est ajouté aux dépendances. Le même problème touchait toute tâche confiée au worker (synchronisations, exports). Un test de non-régression a été ajouté, et chaque erreur de page reçoit désormais un identifiant de requête.
- **Correctif (13/11, incident INC-20261113-0AB9C5)** : « Actualiser » était proposé pour NDL Search, Japan Search et CiNii, qui ne savent pas actualiser des notices, et l'échec était enregistré comme « Erreur technique ». Le bouton n'est désormais proposé que pour les connecteurs compatibles (ex. Kokusho), le serveur refuse l'opération sinon, et le planificateur comme « Actualiser les sources compatibles » les ignorent. Une opération non proposée n'est jamais enregistrée comme dysfonctionnement.
- Base de données : une migration **additive** (`incidents.0001_initial`), aucune table existante modifiée.

## 1.1 — commit 7cb4075

Application complète et 13 corrections de l'audit (numéro affiché par erreur : 1.0.0).
