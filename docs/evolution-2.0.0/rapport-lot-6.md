# J-ed 2.0.0 — Rapport du lot 6 : aide intégrée, historique des versions, logo

16 novembre 2026 · branche `evolution-2.0.0` · cahier des charges : § 9 · demandes U4 et logo
(`02-demandes-utilisateur.md`)

## 1. Demandes prises en compte

| Demande | Origine | Décision |
| --- | --- | --- |
| Aide intégrée | Cahier § 9, décision D11 de l'audit (validé le 14 novembre 2026) | Markdown dans `docs/aide/`, rendu côté serveur par la bibliothèque Python-Markdown (licence BSD), contenu filtré |
| Historique des versions (U4) | 15 novembre 2026 | Administration → Historique des versions : évolutions et améliorations, sans les corrections ; « Quoi de neuf » reprend la dernière version |
| Logo | 16 novembre 2026 | Barre de menu (logo seul, sans le nom écrit), onglet, application installée, connexion, « À propos », en-têtes des exports PDF, Word et HTML. PNG fourni ; le SVG viendra plus tard |
| Bonnes pratiques pour le japonais ancien | Texte fourni le 16 novembre 2026 | Page d'aide dédiée, reprise presque telle quelle (voir § 4) |

## 2. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Moteur de l'aide | Application `help` : pages lues dans `docs/aide/*.md` (en-tête : titre, rubrique, ordre, public, écrans, résumé), relues quand un fichier change. Liens `aide:page#ancre` et `ecran:nom` résolus. HTML écrit dans une page affiché comme du texte. Liens non sûrs neutralisés, liens externes ouverts à part. Aucune image distante | `apps/help/pages.py`, `views.py`, `urls.py`, `templates/help/` |
| Accès | Bouton **?** dans la barre de menu, vers la page de l'écran affiché (sinon l'index de l'aide). « Aide » dans le menu à son nom ; « Aide » et « Quoi de neuf » en bas de page ; deux cartes dans Administration | `context_processors.py`, `base.html`, `admin_hub.html` |
| Publics | Chaque page est pour tous, pour les chercheurs, ou pour l'administrateur. Une page non permise répond « introuvable » et n'apparaît ni dans l'index ni dans la recherche | `pages.Page.visible_to` |
| Recherche | Tous les mots demandés doivent figurer dans la page ; le titre compte davantage. Accents et macrons ignorés (« sorobun » trouve « sōrōbun »). Un extrait est affiché pour chaque résultat | `pages.search`, `search.html` |
| Contenu | 30 pages en six rubriques. **Premiers pas** (4 pages) : démarrer, Quoi de neuf, notifications, signaler un problème. **Chercher et lire** (4) : rechercher, lire une notice, trois statuts, sources. **Bibliothèque et exports** (3) : Bibliothèque, dossiers, exporter. **Traduire et résumer** (11) : moteurs, notice, document, glossaires et mémoire, tâches et file de nuit, résumés IA, japonais ancien, bonnes pratiques, consommation et plafonds, fonctions IA, Argos et IA locale. **Administration** (6) : comptes, état et réglages, sauvegardes, dysfonctionnements, corrections et corbeille, mises à jour et imports. **Référence** (2) : lexique, historique | `docs/aide/*.md` |
| Historique (U4) | Une page rédigée pour l'utilisateur, distincte du `CHANGELOG.md` technique. « Quoi de neuf » ajoute automatiquement sa première section (la dernière version) | `historique-des-versions.md`, `quoi-de-neuf.md` (`reprend:`), `history.html` |
| Guide d'utilisation | `manage.py exporter_guide` met les pages bout à bout dans l'ordre de l'index : HTML autonome (logo, sommaire, liens internes) et Markdown. Le PDF s'obtient en imprimant le HTML. Produits dans `docs/guide-utilisation.html` et `.md` | `apps/help/guide.py`, commande `exporter_guide` |
| Guide d'installation | Nouvelle étape 6, « Installer l'IA locale (facultatif) » : une seule ligne `COMPOSE_PROFILES`, démarrage, choix du modèle, essai | Document « J-ed — Guide d'installation (débutant) » |
| Logo | PNG fourni, rogné et décliné : logo de barre de menu, grand logo, favicon 32 px, icônes 192 et 512 px (ordinaires et « maskable » sur fond blanc), icône Apple 180 px. Il est mis en cache par le navigateur avec le reste de l'interface. Un export ne s'arrête jamais si le logo manque | `static/img/`, `static/icons/`, `base.html`, `login.html`, `first_run.html`, `about.html`, `offline.html`, `core/views.py`, `exports/generators/common.py`, `pdf_gen.py`, `docx_gen.py`, `html_site.py` |
| Libellés | La page d'une demande de résumés ne parle plus de traduction. Remarque faite sur la tâche n° 15 | `TranslationJob.title_label`, `done_word`, `sent_word`, `_job_status.html` |
| « À propos » | Ollama et les modèles Qwen3, et Python-Markdown, ajoutés aux logiciels libres cités, avec leur licence | `core/views.py` |
| Vérification | `verifier_fonctionnalites` ouvre aussi l'aide, sa recherche, « Quoi de neuf », l'historique et les résumés IA | `apps/core/verification.py` |

**Base de données** : aucune migration. **Nouvelle dépendance** : `Markdown>=3.6` (version 3.9 essayée), prévue
par la décision D11 du plan validé.

## 3. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète | **686 tests réussis** (671 + 15) |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration |
| Liens de l'aide | aucun lien, ancre ou écran inconnu ; tous les écrans principaux (53) ont leur page |
| Guide produit | 30 pages, 31 liens internes, aucun cassé ; PDF imprimé par Chrome sans défaut visible (couverture, sommaire, tableaux) |
| Navigateur réel (Chrome, base temporaire supprimée ensuite) | accueil avec le logo et le bouton ?, index de l'aide, page « Tâches, file de nuit… » avec son sommaire et sa rubrique, recherche, historique, « À propos », page des bonnes pratiques ; aucune erreur serveur |

**Nouveaux tests** : `tests/test_aide_600.py` (14) et 1 dans `test_resumes_400.py`.
- **Contenu** : chaque écran principal a sa page ; aucun lien, ancre ou écran inconnu ; chaque page a une rubrique et
  un résumé ; HTML jamais interprété (script, balises, `javascript:`, image distante).
- **Écrans** : pages selon le rôle, et redirection si l'on n'est pas connecté ; le bouton ? vise la page de l'écran ;
  menu et bas de page ; recherche (rôles, sans macron) ; Quoi de neuf (dernière version seulement) ; historique
  réservé à l'administrateur, sans corrections ; rechargement d'une page modifiée.
- **Logo** : PDF (page de titre et en-têtes), Word (image dans l'en-tête), site HTML (fichier et balise), tailles des
  icônes, connexion, « À propos », favicon.
- **Guide** : toutes les pages, aucun lien cassé, aucun lien vers l'application.
- **Libellés** : la demande de résumés ne parle pas de traduction.

## 4. Écarts et choix faits pendant le lot

- **Ton texte sur le japonais ancien.** Repris dans sa structure (trois règles), avec trois retouches :
  - « transrire » corrigé en « transcrire » ;
  - « ren'youkei » écrit « ren'yōkei » (macron, comme dans le reste de J-ed) ;
  - le Kōjien (広辞苑) est un dictionnaire général, qui couvre aussi la langue classique. La page cite donc d'abord
    les dictionnaires de japonais classique (kogo jiten 古語辞典), puis le Kōjien. À corriger si tu préfères ta
    formulation.
  J'ai ajouté une courte partie « Dans J-ed aujourd'hui ». Elle dit honnêtement que la traduction se fait encore en
  une étape : les trois étapes (japonais moderne, analyse, traduction) ne sont pas automatisées. Voir § 6.
- **Logo provisoire.** PNG de 611 × 507 px, fond transparent. Les icônes sont calculées à partir de lui. Quand le SVG
  arrivera, je remplacerai les fichiers et regénérerai les icônes ; les emplacements ne changent pas. Sur fond foncé
  (en-tête rouge du site HTML exporté), le logo est posé sur une pastille blanche, sinon son cadre noir disparaît.
- **Pages « chercheur ».** Les pages de traduction sont cachées au lecteur, qui n'a pas accès à ces écrans.
- **Validation des traductions de notices.** L'aide rappelle qu'elle est réservée à l'administrateur, comme depuis
  la 1.3.0. Le chercheur valide ses propres projets de traduction.
- **Guide d'utilisation au format document.** Il est produit en HTML autonome et en Markdown. Le PDF s'obtient en
  imprimant le HTML. Je n'en ai pas fait un document éditable à part : il y aurait alors deux textes à tenir à jour.
- **Historique des versions 1.1.** Sa date précise n'est pas connue des documents du dépôt : « novembre 2026 ».

## 4 bis. Correctifs et ajouts du 16 novembre 2026 (après installation)

| Constat sur ton poste | Cause | Correction |
| --- | --- | --- |
| Fiche : un titre long rejette les boutons sous le titre, à gauche | L'en-tête de la fiche donnait au titre sa largeur naturelle ; un titre long prenait toute la ligne | Titre et boutons restent côte à côte (le titre se replie). Vérifié dans Chrome avec un titre fictif de 110 caractères ; test ajouté |
| Une ligne `COMPOSE_PROFILES=hors-ligne` ajoutée à `.env` à chaque mise à jour | Le `mettre-a-jour.ps1` lancé est celui du lot 0, gardé dans `C:\J-ed`. Il ajoutait cette ligne quand Argos tournait et que la première ligne ne contenait pas « hors-ligne ». Le script actuel ne le fait plus, mais il n'était pas utilisé | Remplacer le script du dossier parent par le dernier, joint à part. Désormais, le script signale s'il n'est pas celui de l'archive. L'aide explique pourquoi le remplacer à chaque mise à jour |
| `verifier-j-ed.ps1` : « Vérification dans l'application : impossible à lancer », alors que la réponse JSON semblait complète | Cause exacte **non trouvée** ici : la même vérification est lisible par Python et par PowerShell 7 ; ton poste utilise Windows PowerShell 5.1, avec la sortie et les erreurs mélangées | La réponse est encadrée de repères, la sortie est séparée des erreurs, et un échec affiche la cause exacte avec le début et la fin de la sortie. Si le problème revient, le rapport dira pourquoi |
| Aide : prévoir mise à jour, vérification, dépannage | Demande | Rubrique « Installation et mises à jour », réservée à l'administrateur : « Mettre à jour J-ed », « Vérifier l'installation » (page « État » et `verifier-j-ed.ps1`, signification de chaque repère) et « Dépannage après une mise à jour » |

Archive : `japon-explorateur-2.0.0-lot6-correctif1.zip`. Suite : 690 tests réussis.

**Correctif 2 (rapports `verifier-j-ed.ps1` de 18 h 28 et 18 h 39).** La section 4 est désormais lue. Les 690 tests
passent aussi sur ton poste (`-AvecTests`). Un seul problème restait : « IA locale : Résumé d'essai en échec ».
Cause : le dernier résumé d'essai datait de l'installation du modèle, avant le correctif 4 du lot 4 (ancienne
façon d'appeler Ollama). Rien ne le refaisait, alors que l'IA locale fonctionnait (tâche n° 15 réussie).
Correction : comme pour Argos, l'essai est refait automatiquement deux minutes après le démarrage de J-ed. Il l'est
s'il a échoué, ou si son modèle n'est plus installé ; sinon rien n'est fait. La page « État » dit aussi comment le
relancer à la main. Deux tests ajoutés.

**Rapport `-AvecSources` de 18 h 42**, traité dans le même correctif :
- **« Nichibunken, Tōyō Bunko… : ÉCHEC — ConnectorNotConfigured ».** Cette source n'a pas de connecteur en ligne
  (import de fichiers). Elle est désormais citée à part, sans compter comme échec.
- **« Waseda Kotenseki Sōgō Database : répond (4 ms, 87 797 résultats) ».** C'est le même total que Japan Search,
  servi par le cache. Waseda est relié à Japan Search sur ton installation, mais sans identifiant de base : chaque
  recherche « dans Waseda » renvoyait en fait tout le portail. J-ed refuse maintenant d'interroger une telle source
  et dit comment choisir sa base.
- **« Université Kokugakuin : 0 résultat ».** Normal : la question d'essai (源氏物語) n'existe pas dans cette base.
- **Kokusho : « aucune notice Kokusho reconnue dans l'échantillon » de Japan Search.** Constat à reprendre au lot 10
  (documents et sources).

Deux tests ajoutés (694 tests réussis). Archive : `japon-explorateur-2.0.0-lot6-correctif2.zip`.

**Correctif 3 (essai automatique de 18 h 59, sur ton poste).** L'essai automatique a bien été relancé après la
mise à jour, mais il a échoué de nouveau. Le message, désormais complet, donne la cause : qwen3:4b a répondu
`{"error": "No input text provided. Please provide the text to summarize."}`. La consigne d'essai, plus courte que
celle des vrais résumés, collait le texte japonais à l'exemple de format sans l'annoncer. Le modèle ne l'a pas
reconnu comme le texte à résumer. Les vrais résumés, eux, annoncent le texte par « TEXTE : » ; c'est pourquoi la
tâche n° 15 a réussi. L'essai reprend maintenant exactement la consigne d'un vrai résumé court. Un test ajouté
(695 tests réussis). Archive : `japon-explorateur-2.0.0-lot6-correctif3.zip`.

## 5. Livrables du lot

- Archive `japon-explorateur-2.0.0-lot6.zip` et son empreinte `.sha256`.
- Guide d'utilisation : `docs/guide-utilisation.html` (et `.md`), plus un PDF livré à côté de l'archive.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 6 » (V6-1 à V6-8).
- CHANGELOG : section 2.0.0, lot 6.

## 6. Proposition pour plus tard (non faite, à décider)

**Traduction du japonais ancien en trois étapes.** Pour une tâche dont le texte est ancien, et avec une IA :
1. demander d'abord une version en japonais moderne (現代語訳) ;
2. puis la traduction à partir de cette version ;
3. garder la version moderne et la liste des doutes avec la traduction, pour relecture.

Cela double à peu près le nombre d'appels et le coût, toujours affichés avant confirmation. C'est un changement de
périmètre : à valider avant tout développement (lot 10 ou version suivante).
