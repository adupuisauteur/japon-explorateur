# Historique des versions

## 2.0.3 — version candidate rc1 (26 novembre 2026)

**J-ed sous Linux (Ubuntu 26.04 LTS).** Les **mêmes scripts** `.ps1` servent sous Windows (Windows PowerShell 5.1) et
sous Linux (PowerShell 7) : une seule logique (décision D1 du 26 novembre 2026). Sous Linux, l'assistant est un
**menu dans le Terminal** (`j-ed.sh`, `assistant/menu-j-ed.ps1`), jumeau de la fenêtre de Windows et appuyé sur le
même module (`assistant/AssistantJed.psm1`). Aucun changement des données ; Windows inchangé.

- Lot 0 : contrat des scripts commun aux deux systèmes (`docs/contrat-scripts.md`) ; sous Linux, le proxy du `.env`
  est donné à la commande `docker` pendant une construction (sinon « failed to authorize: DeadlineExceeded »,
  constaté sur une machine virtuelle derrière un proxy) ; messages Linux (Docker Engine, l'application Fichiers).
- Lot 1 : menu texte (accueil, liste des installations, prérequis Linux, nouvelle installation, démarrer, arrêter,
  ouvrir, vérifier, ajouter, sauvegarde) ; proxy des réglages d'Ubuntu ; refus de `root` ; avertissement quand le
  conteneur (utilisateur 1000) ne peut pas écrire dans le dossier des sauvegardes.
- Lot 2 : mise à jour sûre depuis le menu (script de la nouvelle version, question avant l'arrêt de l'ancienne,
  retour automatique) ; dossier temporaire propre à chaque compte ; outil de recette
  `tests/outils/archives-essai.ps1` (archives « construction impossible » et « démarrage impossible »).
- Lot 3 : restauration (nouvelle installation ou installation choisie), mot de passe oublié, vérifier la migration,
  réinitialiser l'essai, raccourcis du menu Applications, « Ça ne marche pas » ; tous les scripts refusent `root`.
- Lot 4 : guide **« Avant de commencer (Linux) »** (`AVANT-DE-COMMENCER-LINUX.html` et `.pdf` : Terminal, proxy,
  Docker Engine, groupe `docker`, PowerShell 7.6, puis J-ed) ; lien « Comment faire ? » de chaque prérequis ;
  raccourcis rattachés à l'installation et mis à jour après une mise à jour ; aide « L'assistant J-ed » (partie
  « Sous Linux ») ; `VERSION` 2.0.3.
- 1027 tests, aussi sous un compte non `root` (comme sur GitHub). Essais réels sur une machine virtuelle
  Ubuntu 26.04 : installation de la 2.0.2 par les scripts tels quels (26 novembre 2026) ; recette de la rc1 à venir.

### Après la rc1 (26 novembre 2026, avant la recette)

- **Journaux de Docker limités** : 3 fichiers de 10 Mo au plus par service (sans limite, ils pouvaient remplir le
  disque au fil des mois) ; appliqué quand les conteneurs sont recréés, par exemple à la mise à jour.
- **Sous Linux, le fichier `.env` est réservé au compte de l'utilisateur** (il contient les secrets de
  l'installation) ; « Vérifier » signale un `.env` lisible par d'autres comptes.
- **Essais Docker sur GitHub** (outil de recette) : installation, mises à jour réussie et ratées, sauvegarde,
  restauration, réinitialisation et menu, avec le vrai Docker sous Linux, lancés à la main.
- README : macOS indiqué comme non essayé.

## 2.0.2 — 24 novembre 2026

**L'assistant graphique Windows.** Un double-clic sur `J-ed.cmd` ouvre une fenêtre qui vérifie l'ordinateur,
installe J-ed (même une deuxième fois, sur un autre port), le met à jour (au besoin en téléchargeant la dernière
version sur GitHub), le vérifie, le sauvegarde et le restaure (aussi dans une nouvelle installation), retrouve un
mot de passe oublié, réinitialise une installation d'essai et prépare un compte rendu sans aucun secret. Il reprend
le proxy de Windows. Le guide « Avant de commencer » (HTML et PDF) mène d'un Windows neuf à J-ed installé. Aucun
changement des données. Recette des versions candidates rc1 à rc6 les 23 et 24 novembre 2026, dont une
installation complète sur un Windows 11 neuf (1 h 39, en suivant seulement le guide et l'assistant).

Dernières corrections (recette de la rc6, remarques N13 à N16) :

- la mise à jour ne demande plus d'écrire le proxy quand le fichier `.env` le contient déjà ;
- après une mise à jour qui garde le même numéro de version, les raccourcis sont bien mis à jour (la nouvelle
  installation est retrouvée par son dossier), et la liste des raccourcis écrits est affichée ;
- après une installation qui n'a pas abouti, le message nomme le dossier à supprimer avant de recommencer ;
- guide : « 10 à 30 minutes (en fonction de la vitesse de téléchargement) ».
- 950 tests.

### Version candidate rc6 (24 novembre 2026)

Remarques N1 à N12 de la recette de la rc5 (installation complète sur un Windows 11 neuf
réussie en 1 h 39 ; vérification courte de la rc5 réussie, sans défaut bloquant ; aucun changement des données) :

- **« Avant de commencer »** (HTML et PDF) : fermer le Terminal puis redémarrer après WSL ; que faire si Docker
  Desktop affiche « Virtual Machine Platform is not enabled » ; attendre l'assistant jusqu'à une demi-minute, sans
  double-cliquer de nouveau ; **le réglage du proxy passe avant l'installation** (étape 7), avec « Manual proxy
  configuration » si « System proxy » ne suffit pas et une vérification par `docker pull` ; les deux réglages du
  proxy (Docker Desktop et `.env`) expliqués ; clés secrètes créées par l'assistant et conseil de garder une copie
  du `.env` en lieu sûr. Mêmes précisions dans l'aide « L'assistant J-ed ».
- **Assistant** : bouton « Docker joint-il Internet ? » aussi dans « Nouvelle installation » ; le titre d'une
  opération indique depuis combien de minutes l'étape en cours dure ; après un échec, la nouvelle fenêtre reprend
  les choix de la tentative précédente (Argos compris) ; fin guidée : rappel du fichier `.env` à garder ; Bureau
  prévenu de l'ajout des raccourcis (et conseil F5) ; **icône de J-ed** sur les fenêtres, dans la barre des
  tâches et sur le raccourci « Assistant J-ed » (faite à partir du logo vectoriel, `static/img/logo-j-ed.svg`,
  fourni par l'auteur le 24/11) ; choix de restauration lisible sur deux lignes.
- **Première configuration** : la case « Installer maintenant la traduction hors ligne » n'est plus proposée quand
  l'installation a été faite sans Argos (lu dans `COMPOSE_PROFILES`).
- Nouveaux tests (`tests/test_recette_202_rc6.py` et compléments) ; 943 tests.

### Version candidate rc5 (24 novembre 2026)

Corrections des remarques notées pendant la recette des rc1 à rc4 (essais T0 à T14
réussis ; aucun changement des données) :

- **Assistant, fenêtre principale** : bouton **Fermer** ; libellé « Aide : avant de commencer » ; liste relue dès
  que les prérequis sont vérifiés de nouveau, et état « ? (Docker arrêté) » au lieu de « arrêtée » tant que Docker
  Desktop ne répond pas ; l'installation choisie reste choisie quand la liste est relue (on pouvait la perdre
  depuis « Opérations de maintenance ») ; après une mise à jour, l'**ancien dossier** gardé apparaît en gris
  (« ancien dossier ») et l'assistant prévient avant d'agir dessus.
- **Lancement** (`J-ed.cmd`) : PowerShell est lancé caché dès le départ, pour que Windows 11 ne laisse plus de
  fenêtre vide derrière l'assistant (à vérifier à la recette ; le guide dit quoi faire si elle apparaît encore).
- **Mise à jour** : l'avertissement « installation protégée » distingue l'installation principale de l'essai et
  vient avant l'écriture du proxy dans le `.env` ; après un échec, le message nomme le **dossier de la nouvelle
  version à supprimer** (il ne contient aucune donnée) ; la question de confirmation s'affiche avec la bonne étape
  (6/7) ; le script n'affiche plus « Taper OUI » quand la réponse vient de l'assistant ; `pip` attend plus
  longtemps et réessaie (réseau lent, proxy).
- **Nouvelle installation, restauration** : le message « Version … téléchargée » s'efface quand on choisit une
  autre archive ; bouton « Choisir… » de l'emplacement lisible ; avant une restauration, plus de consigne « créez le
  compte administrateur » ; la ligne technique « Pensez à réintroduire DJANGO_SECRET_KEY… » devient une phrase
  simple.
- **Réinitialiser l'essai** : options présentées comme indépendantes (on peut cocher les deux) ; message juste
  après une réinitialisation complète (l'essai reste arrêté) ; script : lettres accentuées lisibles dans
  l'assistant (sortie UTF-8), nom J-ed, plus de « tapez REINITIALISER » quand la réponse vient de l'assistant,
  annonce « images gardées si d'autres installations s'en servent ».
- **Première configuration** : un double clic sur « Terminer la configuration » (page lente) ne provoque plus
  d'erreur 500 ni de dysfonctionnement « critique » : bouton désactivé après le premier clic, création protégée
  par un verrou, second envoi renvoyé vers la connexion avec un message clair.
- Nouveaux tests (`tests/test_recette_202_rc5.py` et compléments) ; 924 tests.

### Version candidate rc4 (23 novembre 2026)

Correction d'un défaut trouvé à la recette de la rc3 (essai T9, « Mot de passe oublié »
sur une installation en 2.0.1) :

- **l'assistant s'arrêtait sur une « exception non gérée »** au lieu d'afficher « demande J-ed 2.0.2 ou plus
  récent » : sous Windows PowerShell 5.1, avec le réglage « Stop » de la fenêtre, une ligne écrite par docker sur
  sa sortie d'erreur (ici « Unknown command ») devenait une exception. Le même risque touchait la liste des
  installations et le contrôle « Docker démarré ? » lorsque Docker Desktop est arrêté. Ces messages sont
  désormais lus comme du texte ; la liste des comptes passe par un processus à part, comme le changement du mot
  de passe. Nouveaux tests (PowerShell 7, celui des tests, ne réagit pas ainsi : le code lui-même est vérifié).
- 894 tests.

### Version candidate rc3 (23 novembre 2026)

Correction d'un défaut bloquant trouvé à la recette de la rc2 (après la première mise à
jour réussie par l'assistant, essai T2) :

- **la liste des installations plantait dès qu'il y en avait deux** (erreur « System.Object[] » de Windows Forms,
  ici l'ancien et le nouveau dossier de l'essai) : la fenêtre entourait d'un second tableau la liste déjà rendue
  sous forme de tableau. Nouveaux tests : la liste telle que la fenêtre l'utilise, avec deux installations et
  sans aucune.
- 892 tests.

### Version candidate rc2 (23 novembre 2026)

Correction d'un défaut bloquant trouvé à la recette de la rc1 (essai T2, mise à jour de
l'installation d'essai depuis l'assistant) :

- **la mise à jour vers la rc1 s'arrêtait à l'étape 4/7** (« nom de projet inattendu », code 1 ; rien n'était
  modifié) : `docker-compose.yml` déclarait les arguments de construction du proxy en majuscules et en minuscules
  (`HTTP_PROXY` et `http_proxy`…), et Windows PowerShell refuse de lire une configuration dont deux noms ne
  diffèrent que par la casse. Seuls les noms en majuscules restent ; le Dockerfile donne les minuscules à `apt`,
  pour sa seule commande. Nouveaux tests : configuration simulée avec les vrais arguments de construction, et
  aucune clé en double (casse) dans `docker-compose.yml`.
- 890 tests.

### Version candidate rc1 (23 novembre 2026)

Première version candidate de la 2.0.2 : l'**assistant graphique Windows**. Même application : **aucune migration de
base, aucun changement des données** (seul ajout à l'application : la commande `mot_de_passe_oublie`).

**Ordre des versions modifié le 23 novembre 2026** (décision de l'utilisateur) : l'assistant graphique, d'abord
prévu en 2.0.3 après Linux, devient la **2.0.2** ; **Linux** devient la **2.0.3** (avec le proxy sous Ubuntu) ; le
**proxy sous Windows** passe de la 2.0.4 à la 2.0.2. La 2.0.4 garde le réseau local, la migration et la NDL.

- **Assistant J-ed** (`J-ed.cmd`, `assistant/`, Windows PowerShell 5.1 et Windows Forms : rien à installer). Il ne
  contient aucune logique d'installation : il lance les scripts (contrat `docs/contrat-scripts.md`, testé) et
  montre leur déroulement en français.
  - Écran d'accueil : « Mettre à jour une installation », « Nouvelle installation », liste des installations
    (retrouvées par Docker et par une liste gardée ; « Ajouter une installation… »), dernière sauvegarde.
  - Prérequis vérifiés (Windows, mémoire, virtualisation, WSL, Docker Desktop installé et démarré, place libre),
    avec « Comment faire ? » vers `AVANT-DE-COMMENCER.html`.
  - Mise à jour : archive choisie ou **dernière version publiée sur GitHub** (archive et `.sha256` téléchargés,
    empreinte contrôlée), confirmation OUI dans une boîte de dialogue au moment où le script la pose, message
    de chaque code de sortie, cause probable des erreurs Docker courantes.
  - **Nouvelle installation** (`installer-j-ed.ps1`), aussi une deuxième instance : nom et port neufs contrôlés,
    secrets neufs, fin guidée (compte administrateur, raccourcis, jeu d'essai).
  - Opérations de maintenance : créer et **restaurer une sauvegarde** (dans une nouvelle installation, ou dans
    l'installation choisie après saisie de `RESTAURER`), **mot de passe oublié**, vérifier la migration,
    réinitialiser l'essai.
  - **Proxy de Windows** (PAC compris) : case à cocher, vérification de l'accès de Docker à Internet, `HTTP_PROXY`,
    `HTTPS_PROXY`, `NO_PROXY` écrits dans le `.env` et transmis par `docker-compose.yml` (vides par défaut).
  - Raccourcis « J-ed » et « Assistant J-ed » ; compte rendu « Ça ne marche pas » sans aucun secret ; fenêtres
    adaptées aux petits écrans.
- `mettre-a-jour.ps1` : paramètre facultatif `-Empreinte` ; confirmation pilotable (repères `QUESTION` et `REPONSE`
  du journal). `reinitialiser-essai.ps1` : réponses lues sur l'entrée standard quand un programme les fournit ;
  avec `-Complet`, images gardées si une autre installation de J-ed existe.
- Commande `mot_de_passe_oublie` (liste des comptes ; nouveau mot de passe lu sur l'entrée standard, vérifié, noté
  dans le journal des actions sensibles).
- **`AVANT-DE-COMMENCER.html` et `.pdf`** à la racine de l'archive : guide pas à pas pour un débutant complet.
- Aide intégrée : nouvelle page « L'assistant J-ed » ; « Mettre à jour J-ed » présente d'abord l'assistant.
- 887 tests.

## 2.0.1 — 23 novembre 2026

**Version définitive**, déclarée par l'utilisateur le 23 novembre 2026 après la recette des versions candidates rc1,
rc2 et rc3 sur l'installation d'essai (Docker 29) : mise à jour normale, vérification complète, construction
impossible, démarrage impossible avec retour automatique. Même code que la rc3. Détail des versions candidates
ci-dessous, de la plus récente à la plus ancienne.

### Version candidate rc3 (23 novembre 2026)

- **Version candidate rc3**, corrections issues de la recette courte de la rc2 (Docker 29, stockage d'images
  containerd) :
  - **retour à l'ancienne version avec le même numéro de version** (versions candidates) : avec ce stockage, une
    image qui perd son étiquette n'est plus retrouvable par son identifiant (« No such image »). Avant la
    construction, les images qui vont être remplacées reçoivent un **nom de réserve** (`…-avant-maj`), d'où elles
    sont remises en cas d'arrêt ou de retour ; ce nom reste ensuite sur l'ordinateur (la mise à jour suivante le
    remplace). Si la remise échoue malgré tout, le retour **reconstruit l'ancienne version** depuis son dossier ;
  - **le retour vérifie que l'ancienne version répond** : pour une ancienne version 2.0.0 ou plus récente, sa page
    de santé doit répondre deux fois, comme au contrôle final (versions 1.x : service web en marche).

### Version candidate rc2 (20 novembre 2026)

- **Version candidate rc2** (20 novembre 2026), corrections issues de la recette de la rc1 sur l'installation
  d'essai (mise à jour normale, vérification complète, construction impossible, démarrage impossible) :
  - **contrôle final de la mise à jour** : il interroge désormais le serveur web lui-même (page de santé
    `/sante/`), deux fois à 15 secondes d'intervalle (paramètre `-DelaiStabilite`), après la version et la base.
    Pendant la recette, un service web qui s'arrêtait juste après son démarrage avait été pris pour un succès : le
    contrôle (`etat_installation`) avait répondu pendant les secondes où le conteneur préparait la base ;
  - **messages de Docker** : les lignes vides de la sortie d'erreur s'affichaient « System.Management.Automation.
    RemoteException » sous Windows PowerShell 5.1 ; elles s'affichent désormais telles quelles ;
  - **étiquettes d'images** : quand la construction échoue (code 3) ou que la mise à jour est annulée (code 2), les
    images de l'ancienne version reprennent leur étiquette (une construction qui échoue peut en avoir ré-étiqueté
    une avant l'échec, avec le même numéro de version).

### Version candidate rc1 (20 novembre 2026)

Première des versions courtes décidées le 20 novembre 2026 (2.0.1 → 2.0.2 Linux → 2.0.3 assistant graphique
Windows → 2.0.4 réseau local, proxy, migration, NDL). Même application que la 2.0.0 : **aucune migration de
base, aucun changement des données**. Note de version validée par l'utilisateur le 20 novembre 2026.

- **Licence dans l'application** (lot 0) : J-ed est publié sous la GNU AGPL v3.0 **ou toute version ultérieure**
  (`AGPL-3.0-or-later`, fichier `LICENSE`). Page « À propos » : section « Licence et code source » (ce que la
  licence permet, absence de garantie, lien « Code source », lien vers la licence) ; pykakasi (GPL v3 ou
  ultérieure) ajouté aux composants. Lien « Code source » en bas de chaque page, y compris la page de connexion
  (article 13 de l'AGPL). Réglage `CODE_SOURCE_URL` (`.env`) pour qu'une version modifiée indique son propre
  dépôt. README : section « Licence » ; nouveau `CONTRIBUTING.md` ; aide « Bien démarrer » : « Un logiciel libre ».
- **Mise à jour sûre** (lot 1, `mettre-a-jour.ps1`) : la nouvelle version est **construite pendant que l'ancienne
  reste en service** ; les images manquantes sont téléchargées avant tout arrêt. Si Docker ne joint pas Internet,
  le script s'arrête et l'ancienne version continue de fonctionner (constat du 19 novembre 2026 sur une machine
  derrière un proxy : J-ed restait arrêté). La nouvelle version démarre ensuite sans reconstruire ; si elle ne
  démarre pas ou ne répond pas au contrôle final, **retour automatique** à l'ancienne version. Même numéro de
  version (versions candidates) : l'image d'avant la mise à jour est remise lors du retour. **Journal**
  `mise-a-jour-AAAAMMJJ-HHMMSS.log` dans le dossier des sauvegardes (jamais de mot de passe) ; **codes de sortie**
  0 à 5 ; paramètre `-DelaiControle`. Aide « Mettre à jour J-ed » complétée (retour automatique, journal, codes).
- **Tests automatiques sur GitHub** (lot 2) : `.github/workflows/tests.yml` lance tous les tests à chaque envoi sur
  `main` ou une branche `evolution-…` (Ubuntu, Python 3.12, PostgreSQL 15, polices japonaises de l'image Docker) ;
  échec si un test est ignoré. Première exécution réussie le 20 novembre 2026 (781 tests).
- Tests : 796 en 2.0.1 (759 en 2.0.0 ; 784 en rc1 ; 791 en rc2) ; `LICENSE` inclus dans l'archive de la version.

## 2.0.0 — 19 novembre 2026

Version de consolidation, renommée **J-ed**. Base : version 1.3.0-rc3, étiquette `v1.3.0-rc3` (commit
`d7296d4`). Audit et plan : `docs/evolution-2.0.0/01-audit.md` ; synthèse technique :
`docs/evolution-2.0.0/rapport-technique-2.0.0.md` ; recette : `docs/evolution-2.0.0/06-recette.md`. La version
a été déclarée définitive le 19 novembre 2026, après la recette des versions candidates rc1 et rc2 sur le poste de
l'utilisateur.

- **Version définitive** (19 novembre 2026), après la recette courte de la rc2 (mise à jour, vérification
  complète avec 759 tests et les sources interrogées en direct, jeu d'essai, Argos, retrait : tout est conforme).
  Seule l'aide change par rapport à la rc2 ; ni le code de l'application ni la base ne changent :
  - **« Mettre à jour J-ed »** : la méthode pas à pas et les commandes une par une ; vérifier d'abord que Docker
    joint Internet (`docker pull python:3.12-slim-bookworm`), car la nouvelle version est construite après l'arrêt
    de l'ancienne ; déclarer un proxy dans Docker Desktop (un fichier de configuration automatique PAC n'est pas
    lu) ; que faire si le script s'arrête après « OUI » ;
  - **« Essayer J-ed », partie B** : chemin exact pour le document à images (Retenir, Intégrer la sélection,
    Fiche locale, Voir les images dans J-ed) ; « Fiche locale » pour Aozora Bunko ; l'étape NDL est retirée : la
    recherche du numéro proposé renvoyait des articles qui contiennent ce nombre, pas le document numérisé
    (recherche fiable d'un document numérisé de la NDL : 2.0.1).
  - **Argos** (« Argos et IA locale », « Moteurs de traduction », lexique) : la traduction se fait en deux temps,
    japonais → anglais puis anglais → français ; conséquences (erreurs qui s'additionnent, noms propres et titres
    anciens traduits comme des mots ordinaires, pas de glossaire) et conduite à tenir.

- **Version candidate rc2** (18 novembre 2026), corrections issues de la recette de la rc1 sur le poste de
  l'utilisateur (mise à jour de l'installation d'essai, procédure « Essayer J-ed », installation complète) :
  - **essai des sources sans cache** : « Tester le connecteur », la vérification `-AvecSources` et l'essai réel
    enregistré pour une source interrogent toujours la source elle-même ; ils lisaient la réponse gardée en
    mémoire (« répond, 0 ms ») et pouvaient déclarer joignable une source qui ne l'était plus ;
  - **Waseda** : une source Waseda installée avant la 2.0.0 et encore reliée à Japan Search reçoit un message qui
    propose le connecteur dédié (Waseda Kotenseki, via NDL Search) ; l'explication d'un échec n'est plus coupée
    dans le rapport de vérification ;
  - **jeu d'essai** : la procédure « Essayer J-ed » s'ouvre dans un nouvel onglet (lien, et bouton une fois le jeu
    chargé) ; le journal des actions donne les nombres de notices, dossiers et projets chargés ou retirés ;
  - **traduction** : pour Argos, « caractère(s) traité(s) sur cet ordinateur » au lieu de « envoyé(s) » ;
  - **mesure des performances** : sur les données réelles, aussi une recherche par auteur moderne, une recherche
    en rōmaji et la détection des doublons (lecture seule) ;
  - **aide** : une commande par cadre, sous la forme `powershell -ExecutionPolicy Bypass -File …` ; sources
    complétées (Archives nationales, Waseda, Aozora, institutions « à étudier ») ; jeu d'essai dans « Bien
    démarrer » ; « Essayer J-ed » : résultats attendus exacts (23 et 17 notices, 50 premières notices Kokusho sur
    une centaine), fiches ouvertes par « Fiche locale », emplacement du bloc Doublons, notifications dans le menu à
    votre nom, visionneuse intégrée à activer avant l'essai du document à images ;
  - **`verifier-migration.ps1`** (nouveau, lecture seule) : après le passage de J-ed sur un autre ordinateur,
    inventaire des installations présentes dans Docker (volumes, conteneurs, dossier et `.env`, sauvegardes,
    nombres de notices, de dossiers et de projets, dernières migrations, adresse), à comparer avec l'ancien
    ordinateur ;
  - guides en ligne (installation, mise à jour) corrigés en même temps : une commande par cadre, restauration
    d'une sauvegarde sur une installation neuve (copie dans `/data/`), IA locale après une mise à jour, message
    « IA locale prête ».

- **Version candidate rc1** (17 novembre 2026) :
  - **jeu d'essai fictif** : 38 notices inventées (dont un doublon volontaire en graphie ancienne et moderne), un
    dossier et un projet de traduction de deux textes inventés ; chargé ou retiré depuis Administration → Jeu
    d'essai ou par `manage.py jeu_essai --charger|--retirer` ; le retrait ne touche que ses éléments et garde une
    notice encore utilisée ailleurs ; page d'aide **« Essayer J-ed »** : procédure pas à pas avec le résultat
    attendu de chaque étape, sans Internet puis avec ;
  - **doublons en graphie ancienne et moderne** (révélé par le jeu d'essai) : la présélection portait sur la
    graphie exacte du début du titre ; 架空國史略 et 架空国史略 ne se rencontraient jamais. Elle cherche maintenant
    la forme reçue, moderne (shinjitai) et ancienne (kyūjitai) ;
  - documentation : README réécrit pour la 2.0.0 ; rapport technique 2.0.0 ; grille de recette ; guides
    d'installation (installation d'essai à côté de la principale, jeu d'essai, Aozora) et de mise à jour (retour à
    la 1.3.0 pour la 2.0.0 complète, séquence essayée) ; descriptions des sources SHIPS et NIJL mises à jour ;
    bandeau « en cours de développement » retiré de l'accueil Traduction.

- **Lot 10 — étape 4, fin du lot** (16 novembre 2026, d'après le troisième passage de l'étude) : **accès des
  documents numérisés de la NDL** (reporté du lot 3). L'adresse du manifeste est construite à partir du numéro de
  numérisation (`https://dl.ndl.go.jp/api/iiif/<numéro>/manifest.json`, forme vérifiée sur le poste) ; « Vérifier le
  manifeste IIIF » conclut : manifeste et première image servis → « Document : oui, consultable librement sur
  Internet » ; manifeste absent (HTTP 404) → « pas en accès libre, accès réservé probable », sans incident (le
  niveau exact de réservation n'est pas publié dans le manifeste) ; conclusion conservée lors des actualisations ;
  la visionneuse intégrée sert aussi les documents NDL en accès libre ; aide (trois statuts) et historique des
  versions complétés.
- **Lot 10 — étape 3, correctif 1** (16 novembre 2026, incident INC-20261116-5D1D5E) : deux intégrations de la
  liste Aozora ont tourné en même temps (double clic ou « Reprendre » pendant que la première tournait) ; 8 561
  créations refusées par la contrainte d'unicité, aucune donnée abîmée. Une seule intégration à la fois par
  source (verrou PostgreSQL entre processus, libéré même si le processus s'arrête) ; une seconde demande est
  refusée avec un message, sans rien relancer ; « Reprendre » n'apparaît que si l'intégration ne tourne plus, avec
  le nombre de notices intégrées et restantes ; une notice créée entre-temps par une autre opération devient une
  mise à jour au lieu d'une erreur.
- **Lot 10 — étape 3** (16 novembre 2026, d'après le second passage de l'étude) :
  - **Kokusho** : recherche dans Japan Search sur la base `nij16` (日本古典籍総合目録 du NIJL, constatée sur le
    poste) sans réglage ; notices lues dans leur structure propre (titres, auteur, sujet, date, 刊/写, format,
    établissement et cote, autres titres) ; « Tester le connecteur » interroge cette base. L'ancien filtrage sur les
    liens kokusho.nijl.ac.jp ne trouvait rien ;
  - **Waseda**, connecteur dédié : fonds `waseda` de l'API officielle de NDL Search, lien vers la page de l'ouvrage
    sur le site de Waseda (jamais lu par J-ed), mention « 早稲田大学図書館古典籍総合データベース » ; nouvelle
    installation : réglé d'office ; installation existante : bandeau qui explique comment le choisir ;
  - **« Ouvrir le document »** dans les fiches et les résultats : visionneuse du Kokusho, NDL Digital Collections,
    page de Waseda, lecture Aozora, à la place du manifeste IIIF ;
  - **visionneuse intégrée**, désactivée par défaut (Administration → Paramètres) : vues d'un manifeste IIIF, une
    à une (flèches, numéro de vue, taille réelle), mentions de la source ; le navigateur charge les images des
    seuls sites autorisés (par défaut kokusho.nijl.ac.jp et dl.ndl.go.jp), et l'en-tête de sécurité n'est élargi
    que sur cette page (migration additive des paramètres) ;
  - `etudier_sources` : chaque requête de l'étape NDL est indépendante (un délai dépassé l'arrêtait toute
    entière) ; `--plan 3` (défaut) ne refait que cette étape.
- **Lot 10 — étape 2** (16 novembre 2026) :
  - **Aozora Bunko**, source à part entière : liste officielle des œuvres (CSV compressé, CC BY) importée par
    « Synchroniser », une notice par œuvre (auteurs, traducteurs, texte source, droits), colonnes lues par leur nom ;
    recherche dans les notices importées, sans requête au site ; **texte intégral** téléchargé au clic depuis la
    fiche (fichier zip Shift_JIS ou page XHTML), conservé (nouvelle table `RecordText`, migration additive),
    affiché avec ses furigana, envoyé seul vers un projet de traduction (provenance « Texte d'Aozora Bunko ») ;
    page d'aide ;
  - synchronisations de plus de 1 000 notices : intégration en tâche de fond (le délai d'une page est de 180 s),
    avec reprise après interruption ;
  - **registre des connecteurs toujours complet** : il ne chargeait ses modules que s'il était vide ; un connecteur
    importé seul ailleurs le remplissait à moitié et les autres sources devenaient « sans connecteur » dans ce
    processus. C'était la cause des tests de recherche instables ; le défaut pouvait aussi toucher l'application ;
  - étude des sources, second passage (`etudier_sources`) : notices Kokusho de Japan Search (base `nij16`),
    contrôle positif des numérisations NDL, colonnes de la liste Aozora ; un robots.txt en 401/403 ou 5xx vaut
    désormais refus.
- **Lot 10 — documents et nouvelles sources, étape 1** (16 novembre 2026, rapport :
  `docs/evolution-2.0.0/rapport-lot-10.md`) : commande `manage.py etudier_sources`, à lancer sur le poste
  (l'environnement de développement ne joint pas ces sites). Lecture seule, une trentaine de requêtes espacées d'une
  seconde, robots.txt respecté : bases et sites réellement présents dans Japan Search (cause de « aucune notice
  Kokusho reconnue »), fonds Waseda et Aozora dans NDL Search, structure d'une page d'ouvrage Waseda, accès réel des
  numérisations NDL de la base (manifeste, première image), liste des œuvres d'Aozora Bunko, pages d'accès de
  l'Historiographical Institute.
- **Lot 9 — performances, étape 1** (16 novembre 2026, rapport : `docs/evolution-2.0.0/rapport-lot-9.md`) :
  - commande `manage.py mesurer_performances` : recherche (libre, titre, auteur), doublons, calcul de la
    consommation et pages principales, mesurés sur 50 000 notices fictives dans une base temporaire supprimée
    ensuite, puis recherches en lecture seule sur les données réelles (transaction annulée) ; durée médiane et
    nombre de requêtes ; sortie texte ou `--json` ; section « Mesurer la rapidité » dans l'aide ;
  - page **Consommation** : nombre de requêtes fixe (six au plus), quel que soit le nombre de tâches du mois (avant :
    deux à trois par tâche) ; résultats identiques, vérifiés par un test qui compare avec l'ancien calcul ;
  - test parfois instable (recherche rapide) : diagnostic complet en cas d'échec, pour en trouver la cause.
- **Lot 9 — étape 2** (16 novembre 2026, d'après la mesure faite sur le poste de l'utilisateur) :
  - **détection des doublons** : les 200 notices examinées étaient les 200 premières par ordre alphabétique parmi
    celles qui partagent le début du titre ; à 50 000 notices, les vrais doublons n'y figuraient pas (mesure :
    0 candidat, alors que 206 notices avaient un titre semblable). Elles sont désormais prises par ressemblance du
    titre (extension pg_trgm, déjà installée), les plus proches d'abord ;
  - **IA locale** : un essai en échec enregistré avant un redémarrage n'est plus signalé comme un problème tant que
    l'essai automatique n'a pas eu lieu (« Essai automatique en attente », avec l'heure prévue) ; il n'est plus
    signalé non plus si un vrai résumé par l'IA locale a réussi depuis ;
  - `verifier-j-ed.ps1` : pour Argos et l'IA locale, le rapport donne la cause et la date de l'essai en échec ;
  - tests de recherche multi-source parfois en échec : diagnostic complet en cas d'erreur d'une source.
- **Lot 6 — aide intégrée, historique des versions, logo** (16 novembre 2026, rapport :
  `docs/evolution-2.0.0/rapport-lot-6.md`) :
  - aide intégrée : 30 pages courtes orientées tâches dans `docs/aide/*.md` (une seule source), en six rubriques ;
    pages réservées aux chercheurs ou à l'administrateur cachées aux autres ; rendu Markdown côté serveur
    (bibliothèque Python-Markdown, licence BSD), HTML écrit dans les pages jamais interprété, liens internes
    « aide: » et « ecran: » vérifiés par les tests ;
  - bouton **?** dans la barre de menu : page d'aide de l'écran affiché (chaque écran principal en a une) ;
    entrée « Aide » dans le menu à son nom, « Aide » et « Quoi de neuf » en bas de page ; recherche dans l'aide
    (sans accents ni macrons) ;
  - lexique, page « Japonais ancien : bonnes pratiques avec une IA » (texte fourni par l'utilisateur) ;
  - « Quoi de neuf » et **Administration → Historique des versions** (demande U4) : évolutions et améliorations
    version par version, sans les corrections, tirées d'une même page ;
  - guide d'utilisation produit à partir de l'aide : `manage.py exporter_guide` (HTML autonome et Markdown,
    `docs/guide-utilisation.*`) ; guide d'installation complété (étape 6 : IA locale, facultative) ;
  - **logo de J-ed** : barre de menu (logo seul), icône d'onglet, application installée (icônes ordinaires et
    « maskable »), connexion, premier démarrage, « À propos », page « J-ed ne répond pas », en-têtes des exports PDF,
    Word et site HTML ; logo provisoire en PNG, en attendant le SVG ;
  - libellés : la page d'une demande de résumés ne parle plus de traduction (« Demande de résumés », « 1 résumé(s) »,
    « caractère(s) lu(s) par l'IA », élément « Résumé ») ;
  - `verifier_fonctionnalites` ouvre aussi l'aide, sa recherche, « Quoi de neuf », l'historique et les résumés IA ;
  - aucune migration.
  - correctif du 16 novembre 2026 : sur la fiche, un titre long ne rejette plus les boutons sous le titre ;
  - correctif du 16 novembre 2026 : `verifier_fonctionnalites --json` encadre sa réponse de repères, que
    `verifier-j-ed.ps1` lit en séparant la sortie des erreurs ; une réponse illisible est expliquée (cause, début,
    fin, premières erreurs) au lieu de « impossible à lancer » ;
  - correctif du 16 novembre 2026 : `mettre-a-jour.ps1` signale quand le script lancé n'est pas celui de l'archive
    (un ancien script, gardé à côté des archives, ajoutait `COMPOSE_PROFILES=hors-ligne` à chaque mise à jour) ;
  - aide : nouvelle rubrique « Installation et mises à jour » (mettre à jour, vérifier l'installation, dépannage
    après une mise à jour), demandée le 16 novembre 2026.
  - correctif du 16 novembre 2026 : un résumé d'essai de l'IA locale en échec est refait automatiquement deux minutes
    après le démarrage de J-ed (comme pour Argos) ; la page « État » dit comment le relancer à la main.
  - correctif du 16 novembre 2026 (`-AvecSources`) : une source sans interrogation en ligne (import de fichiers,
    « à étudier ») n'est plus comptée comme une source qui ne répond pas ; une source reliée à Japan Search sans
    identifiant de base est refusée avec un message clair (elle renvoyait tout le portail).
  - correctif du 16 novembre 2026 : le résumé d'essai de l'IA locale reprend exactement la consigne d'un vrai résumé
    (qwen3:4b répondait « No input text provided » à l'ancienne consigne d'essai, plus courte).
- **Lot 4 — résumés IA, IA locale, japonais ancien** (16 novembre 2026, rapport :
  `docs/evolution-2.0.0/rapport-lot-4.md`) :
  - trois types de résumé (court, détaillé, fiche d'analyse avec thèmes, personnes, lieux et dates), toujours
    rédigés dans la langue choisie (français par défaut) à partir de l'original japonais ; versions successives
    gardées ; mention « généré par IA » partout ;
  - un résumé est une tâche de la file : confirmation avec coût estimé, file de nuit, plafonds, pause et reprise
    (un texte long est découpé en parties puis synthétisé ; une reprise ne renvoie rien) ;
  - boutons sur la fiche, dans la Bibliothèque et dans l'atelier d'un document ; page « Résumés IA » ;
  - à la confirmation d'une traduction : « Résumer aussi », juste après chaque traduction ou après l'ensemble
    (imposé la nuit quand Argos et l'IA locale travailleraient en même temps) ;
  - exports : case « Inclure les résumés IA », décochée par défaut ;
  - IA locale facultative (Ollama, profil `ollama` de `COMPOSE_PROFILES`) : modèle choisi dans une courte liste
    avec sa taille, téléchargé après confirmation dans une tâche suivie et reprenable, résumé d'essai, ligne dans la
    page « État » et dans `verifier-j-ed.ps1` ;
  - japonais ancien : repérage « probable » (bungo, kanbun, sōrōbun) sur la fiche, à confirmer ou corriger ;
    réglage « Pour le japonais ancien, utiliser… » pour les traductions et les résumés ; une tâche mixte est
    présentée en deux parties confirmées ensemble ;
  - projets confidentiels : résumés seulement par l'IA locale ;
  - migrations : retour arrière vérifié sur une base temporaire (la mise à jour des données passe dans sa propre
    migration, `translation 0005`).
  - correctif du 16 novembre 2026 : avec « IA locale » comme fournisseur, « Actualiser la liste » des modèles
    semblait ne rien faire ; le sélecteur dit maintenant pourquoi la liste est vide (service non installé,
    injoignable, ou aucun modèle installé), avec le lien vers Moteurs locaux, et date l'actualisation.
  - correctif du 16 novembre 2026 : une variable présente plusieurs fois dans `.env` (par exemple deux lignes
    `COMPOSE_PROFILES`) est signalée par `verifier-j-ed.ps1` et `mettre-a-jour.ps1` ; comme Docker, les deux
    scripts retiennent désormais la dernière ligne (ils lisaient la première).
  - correctif du 16 novembre 2026 : l'indicateur de la barre de menu distingue les résumés des traductions
    (« 1 résumé en cours », « 1 traduction et 1 résumé en cours »).
  - correctif du 16 novembre 2026 : l'IA locale est appelée par l'API native d'Ollama, raisonnement des modèles
    Qwen3 désactivé, sortie JSON imposée et fenêtre de contexte de 8 192 jetons (`OLLAMA_NUM_CTX`) ; une réponse
    illisible est expliquée avec son début (« Début de la réponse : … ») au lieu d'un simple « format attendu ».
- **Lot 3 — tâches, file de nuit, « Traduire maintenant », travail en parallèle** (15 novembre 2026, rapport :
  `docs/evolution-2.0.0/rapport-lot-3.md`) :
  - lancement au choix à la confirmation : immédiat, programmé (date et heure) ou file de nuit ; le coût est
    confirmé une seule fois ;
  - file de nuit : plage horaire choisie par l'utilisateur (Traduction → Moteurs), ordre modifiable, une tâche à la
    fois, pause entre deux paquets à la fin de la plage et reprise la nuit suivante, compte rendu du matin ;
  - retard : une tâche programmée dont l'heure est passée pendant un arrêt de J-ed, ou une file de nuit qui n'a pas
    pu commencer à l'heure, ne part jamais d'elle-même ; une notification demande une confirmation ;
  - plafonds mensuels vérifiés avant chaque envoi : plafond atteint = pause avec alerte, jamais d'autre moteur ;
  - pause et reprise par l'utilisateur ; états « Planifiée », « En pause », « En retard », « Terminée avec erreurs » ;
  - « Traduire maintenant » et « File de nuit » sur la fiche, dans la Bibliothèque et dans l'atelier d'un document ;
    départ sans confirmation avec Argos, ou sous un seuil de coût choisi par l'utilisateur ; résultat sur la fiche ;
  - page « Tâches » (en cours, file de nuit, programmées, à décider, terminées ; vue de toutes les tâches pour
    l'administrateur, sans titre de projet confidentiel d'autrui), indicateur « 1 traduction en cours » dans la
    barre de menu, compte rendu de fin de tâche ;
  - trois workers séparés : travaux courts, longues traductions et file de nuit, demandes « maintenant » ; la page
    « État » signale une file sans worker ;
  - profils de machine (économe, normal, puissant) calculés au démarrage, `JED_PROFIL` dans `.env` pour l'imposer ;
    processus du serveur web, travaux courts en parallèle, taille des paquets Argos le jour et la nuit ; mémoire de
    l'ordinateur indiquée pour un conseil (`.wslconfig`), rien n'est modifié d'office ;
  - « Traductions effectuées » : notices traduites (filtres par état, moteur, date ; « à revoir » si l'original a
    changé) et avancement des documents de projets (demande U5) ;
  - essai d'Argos : bouton dans Moteurs locaux et essai automatique 2 minutes après une installation ou une mise à
    jour ;
  - notifications lues supprimées après 90 jours (les non lues sont gardées).
- **Lot 7 — Argos installé par défaut** (15 novembre 2026, rapport : `docs/evolution-2.0.0/rapport-lot-7.md`) :
  - le service Argos démarre avec J-ed (ligne `COMPOSE_PROFILES=argos` de `.env.example`, ajoutée par
    `mettre-a-jour.ps1` si elle manque) ; laissée vide, la ligne le désactive (poste à mémoire limitée) ; l'ancien
    profil `hors-ligne` reste accepté ; `verifier-j-ed.ps1` signale une ligne manquante ;
  - bouton unique « Installer la traduction japonais → français » : paquets ja→en et en→fr (environ 200 Mo)
    après confirmation, dans une seule tâche suivie et reprenable ; Argos activé dans les moteurs ; traduction
    d'essai à la fin (« Argos prêt » ou l'erreur précise) et fenêtre de notification ;
  - invitations là où on en a besoin : Traduction → Moteurs, Moteurs locaux, préparation d'une traduction
    (notices, atelier d'un document) et écran de confirmation quand Argos est choisi, assistant de première
    configuration (case décochée : « plus tard » par défaut) ;
  - priorité dans le service : une petite tâche (20 éléments au plus) passe avant les paquets d'un long document
    en attente ; elle attend au plus la fin du paquet en cours ;
  - limites facultatives de cœurs et de mémoire (`ARGOS_COEURS`, `ARGOS_MEMOIRE_MAX`) ; mémoire vue par le
    service affichée, avec un avertissement en dessous de 4 Go ;
  - licences citées (Argos Translate, paquets de langues ; licence déclarée par chaque paquet quand il en a une).
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
