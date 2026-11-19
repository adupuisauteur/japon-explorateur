# Rapport technique — J-ed 2.0.0 (version candidate rc1)

**J-ed** (anciennement « Japon — Explorateur documentaire ») · 17 novembre 2026

> **Mise à jour du 19 novembre 2026 :** après la rc2 (18 novembre) et la recette courte, la version **2.0.0** est
> déclarée définitive, puis la branche `evolution-2.0.0` est fusionnée dans `main` sans réécriture de l'historique.
> Détail des changements depuis la rc1 : `CHANGELOG.md` ; recette : `06-recette.md`. Le présent rapport décrit la rc1.

| | |
|---|---|
| Version de départ | **1.3.0-rc3**, étiquette `v1.3.0-rc3`, commit `d7296d4` |
| Version livrée | **2.0.0-rc1** (fichier `VERSION` : `2.0.0`), branche locale `evolution-2.0.0`, 49 commits depuis la 1.3.0-rc3 |
| Ampleur | 288 fichiers modifiés ou ajoutés, environ 24 500 lignes ajoutées et 500 retirées |
| Plan | Cahier des charges 2.0.0 (14 novembre 2026), audit `01-audit.md`, lots 0 à 10, demandes U1 à U12 (`02-demandes-utilisateur.md`) |
| Dépôt GitHub | **Non modifié** à ce stade. À la validation finale, décision du 17 novembre 2026 : envoi de la branche, puis fusion dans `main` sans réécriture de l'historique. Les étiquettes ne sont pas envoyées : le dépôt les refuse (HTTP 403) |

---

## 1. Contenu de la version, lot par lot

| Lot | Objet | Rapport |
|---|---|---|
| 0 | Corrections et fiabilité : nom d'installation obligatoire et noms protégés, sauvegardes (codes de sortie, copie dans un dossier de Windows, contrôle d'empreinte), Argos sans simulation silencieuse, listes de modèles d'IA complètes, page « État de l'installation », `mettre-a-jour.ps1`, `verifier-j-ed.ps1` | `rapport-lot-0.md` |
| 1 | Interface : validation des traductions en une fois, bas de page des exports, « À propos », menu administrateur | `rapport-lot-1.md` |
| 2 | Trois statuts indépendants par notice (notice, document, IIIF), vérification du manifeste en file d'attente | `rapport-lot-2.md` |
| 3 | Tâches, file de nuit, « Traduire maintenant », plafonds, travail en parallèle (files Celery `maintenant` et `traduction`), compte rendu du matin | `rapport-lot-3.md` |
| 4 | Résumés IA, IA locale (Ollama, essai automatique au démarrage), japonais ancien (bungo, kanbun, sōrōbun) | `rapport-lot-4.md` |
| 5 | Notifications (fenêtre, compteur, préférences, alertes de l'administrateur) | `rapport-lot-5.md` |
| 6 | Aide intégrée (33 pages, recherche, lexique), historique des versions, logo, guide d'utilisation exporté | `rapport-lot-6.md` |
| 7 | Argos installé par défaut (profil `argos`) | `rapport-lot-7.md` |
| 8 | Choix du modèle d'IA dans une liste tirée du fournisseur, avec tarif estimé | `rapport-lot-8.md` |
| 9 | Performances : `mesurer_performances`, page Consommation à requêtes fixes, doublons choisis par ressemblance | `rapport-lot-9.md` |
| 10 | Documents et nouvelles sources : Aozora Bunko, Kokusho (`nij16`), Waseda, « Ouvrir le document », visionneuse IIIF facultative, accès des documents NDL, `etudier_sources` | `rapport-lot-10.md` |
| rc1 | Jeu d'essai fictif et procédure « Essayer J-ed », doublons en graphie ancienne et moderne, documentation | `CHANGELOG.md` |

## 2. Statut des sources

Méthode suivie au lot 10 : une commande d'étude en lecture seule, `etudier_sources`, lancée trois fois sur le poste
de l'utilisateur, a relevé la structure réelle des réponses. Les connecteurs ont été construits sur ces faits, puis
testés sur des simulations qui les reproduisent.

| Source | Statut | Constaté sur le poste |
|---|---|---|
| NDL Search | Testé en simulation ; utilisé | Recherches ; fonds `waseda` et `aozora` ; manifeste publié (200) pour une numérisation libre, absent (404) pour une numérisation réservée |
| Japan Search | Testé en simulation ; utilisé | Bases des résultats ; `nij16` pour le NIJL ; `arc_books` pour une partie du fonds Waseda |
| Kokusho | Testé en simulation | Manifeste IIIF 2 (152 vues, Public Domain Mark) ; recherche à essayer (V10-5) |
| Aozora Bunko | Testé en simulation ; liste importée | Liste de 19 502 lignes et 55 colonnes, importée (21 395 notices dans la base d'essai) ; texte à essayer (V10-4) |
| Waseda | Testé en simulation | NDL Search `dpid=waseda` : 223 notices pour 源氏物語 ; le site refuse les requêtes automatiques |
| CiNii, Archives nationales | Testé en simulation | — |
| SHIPS | Consultation externe | Aucune API, IIIF ni OpenSearch |

Règles communes : API officielles, manifestes et fichiers publiés seulement ; aucune page HTML de navigation lue ;
robots.txt respecté (401/403 = refus, 5xx = abstention) ; requêtes espacées ; badge « Non vérifié en conditions
réelles » tant qu'aucun « Tester le connecteur » n'a réussi.

## 3. Architecture

Ajouts au socle de la 1.3.0 :

- **Applications nouvelles** : `apps/notifications` (lot 5) et `apps/help` (lot 6 ; aide en Markdown dans
  `docs/aide/`, Python-Markdown, HTML brut désactivé, registre protégé par un verrou réentrant).
- **Services Docker** : `worker-maintenant` et `worker-traduction` (lot 3), `ollama` (profil `ollama`, lot 4),
  `argos` (profil `argos`, standard depuis le lot 7 ; l'ancien profil `hors-ligne` reste accepté), volumes
  `ollama-models` et `sauvegardes-externes`.
- **Connecteurs** : `aozora` (liste CSV, moisson reprenable par curseur) et `waseda` (NDL Search, fournisseur
  `waseda`) ; Kokusho interroge `nij16` ; le registre retient qu'il est chargé et inscrit lui-même les classes de
  chaque module. C'était la cause des tests de recherche instables : un module importé seul remplissait le
  registre à moitié.
- **Documents** : `apps/catalog/documents.py` (« Ouvrir le document », sans réseau), `texts.py` (texte intégral,
  notation Aozora, furigana en HTML échappé), visionneuse (`record_viewer`, script statique, en-tête CSP propre à
  la page, `img-src` limité aux sites autorisés).
- **Intégrations** : une seule à la fois par source (verrou consultatif PostgreSQL entre processus) ; au-delà de
  1 000 notices, intégration en tâche de fond, reprenable ; création concurrente d'une même notice reprise en
  mise à jour.
- **Outils** : `etat_installation`, `verifier_fonctionnalites` (sortie JSON entre marqueurs), `mesurer_performances`
  (base temporaire supprimée même en cas d'erreur), `etudier_sources`, `exporter_guide`, `jeu_essai`.
- **Scripts Windows** (PowerShell 5.1, BOM et CRLF) : `mettre-a-jour.ps1`, `verifier-j-ed.ps1`,
  `reinitialiser-essai.ps1`.

## 4. Modèle de données et migrations

Toutes les migrations sont additives. Chaque migration comportant des données a sa migration de retour,
séparée.

| Application | Migrations 2.0.0 | Objet |
|---|---|---|
| core | 0002 à 0006 | Mode démonstration d'Argos, `ServiceCheck`, nom d'instance, mémoire de l'ordinateur, visionneuse |
| catalog | 0006 à 0008 | Statuts des notices (et calcul pour les notices existantes), `RecordText` (textes intégraux) |
| translation | 0003 à 0006 | File et nuit, résumés et textes anciens, retour arrière des résumés (séparé), provenance Aozora |
| ai | 0004 | Résumés |
| notifications | 0001 | Nouvelle application |

**Retour à la 1.3.0 essayé le 17 novembre 2026** sur une base temporaire. Séquence `notifications zero`,
`translation 0002`, `catalog 0005`, `core 0001`, `ai 0003` : chaque migration est défaite sans erreur, l'état
obtenu est celui de la 1.3.0-rc3, et la réapplication réussit. La séquence est reprise dans le guide de mise à jour.

## 5. Confidentialité et sécurité

- Aucun texte envoyé à un service en ligne sans confirmation ; plafonds ; projets confidentiels refusés aux
  moteurs en ligne ; IA locale sans clé, sur l'ordinateur.
- Rapports (`Copier le diagnostic`, `verifier-j-ed.ps1`, `etudier_sources`) sans clé, nom de compte, texte de
  recherche ou de traduction ; chemins personnels masqués ; de la base, l'étude ne reprend que des numéros de
  numérisation.
- Politique de sécurité (CSP) stricte inchangée : aucun script en ligne. Seule exception, la page de la
  visionneuse, facultative et désactivée par défaut : `img-src` y est élargi aux sites listés par
  l'administrateur.
- Noms d'installation protégés (`japon-explorateur`, `japon-explorateur-essai`) ; `COMPOSE_PROJECT_NAME`
  obligatoire.
- Jeu d'essai : uniquement des données inventées, rangées à part ; son retrait ne touche que ses éléments.

## 6. Dépendances

| Dépendance | Où | Statut |
|---|---|---|
| Markdown ≥ 3.6 (BSD) | Application | Seule dépendance Python nouvelle (aide intégrée) |
| ollama/ollama 0.30.9 | Image officielle, profil `ollama` | Facultative ; modèles téléchargés seulement sur choix de l'utilisateur (`qwen3:4b` conseillé) |
| Argos Translate et ses dépendances | Image `japon-explorateur-argos:2.0.0` | Inchangées depuis la 1.3.0 |

## 7. Tests

| Ensemble | Résultat |
|---|---|
| Suite complète (`manage.py test`, PostgreSQL), en parallèle et en ordre aléatoire (5 passages) puis en série | **758 tests réussis** (détail : `06-recette.md`, § 1) |
| Scripts PowerShell (PowerShell 7) | inclus dans la suite |
| Migrations : base 1.3.0 avec données fictives passée en 2.0.0 ; retour à la 1.3.0 ; réapplication | réussis (§ 4) |
| Simulations des sources | structures relevées sur le poste (lot 10) |

Non exécutés dans l'environnement de développement, faute d'accès : appels réels aux sources et aux
fournisseurs, construction des images Docker, scripts sous Windows PowerShell 5.1, Ollama réel. Ce sont les
essais de la recette (`06-recette.md`), et une partie a déjà été constatée sur le poste pendant les lots.

## 8. Limites connues

- Accès des documents NDL : le niveau exact de réservation (bibliothèques et particuliers inscrits, ou NDL
  seulement) n'est pas lu ; J-ed dit « accès réservé probable ».
- Kokusho : la base `nij16` est un catalogue figé en 2021, sans images. Ses identifiants ne sont pas rapprochés
  des numéros des notices à images.
- Waseda : pas d'images dans J-ed (autorisation de Waseda nécessaire) ; les manifestes de l'ARC ne sont pas
  utilisés.
- Doublons : la présélection couvre la graphie reçue, la forme moderne et la forme ancienne. Un titre qui mêle
  les deux formes peut encore échapper.
- Visionneuse : affichage vue par vue, sans tuilage IIIF ; une très grande image se charge en entier.
- Linux : installation décrite, non testée.
- Traduction du japonais ancien en trois étapes : reportée après la 2.0.0 (U12).

## 9. Livrables

| Livrable | Emplacement |
|---|---|
| Code 2.0.0-rc1 | Branche locale `evolution-2.0.0` ; étiquette locale `v2.0.0-rc1` |
| Archive et empreinte | `japon-explorateur-2.0.0-rc1.zip` et `.sha256` ; `mettre-a-jour.ps1` livré à part |
| Guides | Guide d'installation et guide de mise à jour (documents partagés) ; aide intégrée ; `docs/guide-utilisation.html` et sa version PDF |
| Recette | `06-recette.md` (grille), `05-protocole-verification.md` (protocole par lot), aide « Essayer J-ed » et jeu d'essai |
| Rapports | `rapport-lot-0.md` à `rapport-lot-10.md`, ce document |
| Journal des modifications | `CHANGELOG.md` |
