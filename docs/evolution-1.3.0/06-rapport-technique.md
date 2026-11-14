# Rapport technique — Évolution 1.3.0 (module de traduction)

**Japon — Explorateur documentaire** · 14 novembre 2026

| | |
|---|---|
| Version de départ | **1.2.0**, commit `4982a3d` (étiquettes locales `v1.2.0` et `v1.2.0-reference`) |
| Version livrée | **1.3.0** (fichier `VERSION`), branche locale `evolution-1.3.0` |
| Périmètre | Nouveau module de traduction ; retouches limitées et justifiées des modules catalogue, exports, IA, journal (lot 2) |
| Dépôt GitHub | **Non modifié** pour la 1.3.0 : ni branche ni étiquette envoyée. `main` et `evolution-1.2.0` inchangées |
| Plan et décisions | Document « Plan de développement — Version 1.3.0 » (décisions A1 à F validées les 13 et 14 novembre 2026) |

---

## 1. Statut exact de chaque moteur

Aucun service en ligne, ni l'index des paquets Argos, n'est joignable depuis l'environnement de développement.
**Aucun moteur n'a été testé en conditions réelles.**

| Moteur | Statut | Testé ici | À vérifier sur votre poste |
|---|---|---|---|
| DeepL (API Free et Pro) | **Développé et testé en simulation ; test réel à confirmer** | Réponses enregistrées : traduction, clé refusée (403), quota épuisé (456), 429/5xx, réponse mal formée, lecture de la consommation, glossaires v3 (création, vérification des langues, utilisation, suppression, 404) | TR2, TR4, TR7, TR10 |
| Google Cloud Translation Basic v2 | **Développé et testé en simulation ; test réel à confirmer** | Traduction, clé refusée, quota, indisponibilité, réponse mal formée, test par phrase fictive | TR3, TR4 |
| IA en ligne (OpenAI, Anthropic, Gemini, compatible OpenAI) | **Développé et testé en simulation ; test réel à confirmer** | Consignes (glossaire, classique, kanbun, contexte), réponse JSON vérifiée, commentaire signalé, consentement, tâche IA par appel, plafond | TR4, TR13 |
| Argos Translate (service local) | **Développé et testé en simulation ; test réel à confirmer** | Serveur réel avec traducteur factice ; bibliothèque Argos imitée d'après son code source ; client (service absent, paquet absent, modèle de découpage absent, passage par l'anglais) ; Compose résolu avec et sans profil | TR8 (dont hors ligne), construction de l'image |

Tarifs DeepL et Google : non renseignés (`reference/tarifs-traduction.json`) ; leur coût s'affiche « non disponible ».

## 2. Architecture

- **Application Django `apps/translation`** (isolée ; aucune modification des modules hors périmètre en dehors
  du lot 2) : `models.py` (12 modèles), `engines/` (contrat commun `base.py`, `deepl.py`, `google_basic.py`,
  `argos.py`, `ai.py`, `registry.py`), `http.py` (client sans texte dans les diagnostics, réseau bloqué en test),
  `services.py` (préparation, confirmation, exécution par paquets, reprise), `tasks.py` (Celery, file
  « traduction »), `segmentation.py`, `importers.py`, `projects.py`, `glossary.py`, `memory.py`, `checks.py`,
  `exports.py`, `evaluation.py`, `usage.py`, `pricing.py`, `terms.py`, `argos_packages.py`, `journal.py`,
  `permissions.py`, `ownership.py`, vues dans `views/` (12 fichiers), gabarits `templates/translation/`.
- **Références datées et modifiables** : `reference/consignes-ia.json` (consignes IA versionnées),
  `reference/tarifs-traduction.json` (tarifs), `reference/conditions-fournisseurs.json` (résumés des conditions).
- **Ajout d'un moteur** (Ollama plus tard) : une classe héritant de `TranslationEngine` et une ligne dans
  `engines/registry.py` ; le reste du module ne connaît que ce contrat.
- **Service Argos** : `docker/argos/` (image séparée, serveur HTTP en bibliothèque standard, profil Docker
  `hors-ligne`, aucun port publié), volumes `argos-packages` et `argos-depot`.
- **Exécution** : toute traduction est une `TranslationJob` suivie en base (préparée → confirmée → en cours →
  terminée/échec/annulée), exécutée par paquets courts dans la file Celery « traduction » (le worker écoute
  `celery,traduction`), reprenable sans renvoi. Les installations de paquets Argos sont des tâches de nature
  « package ».

## 3. Modèle de données

| Table | Rôle |
|---|---|
| `EngineSetting` | Réglage d'un moteur par utilisateur : clé chiffrée, offre DeepL, état du dernier test, quota lu, plafond mensuel |
| `TranslationPreference` | Moteur par défaut et deuxième moteur, seuil de seconde confirmation, contexte IA, champs de notices |
| `Glossary`, `GlossaryEntry` | Glossaires versionnés (copies DeepL par compte), entrées avec variantes et traductions à éviter |
| `TranslationProject`, `ProjectGlossary` | Projets (confidentiel, corpus de référence, moteurs propres) et glossaires par priorité ; table de liaison projets ↔ notices |
| `TranslationDocument`, `TranslationChapter`, `TranslationSegment` | Texte importé intact (empreinte SHA-256), chapitres, segments dont la concaténation redonne l'original |
| `TranslationVersion` | Versions jamais écrasées : moteur, modèle, version, simulation, glossaires appliqués, alertes, coût, validation, note humaine, exclusion de la mémoire |
| `TranslationJob`, `TranslationJobItem` | Tâches et éléments : statut, caractères, coût, lien vers la tâche IA, reprise |

Migrations : `catalog.0005` et `incidents.0002` (listes de choix, **aucune instruction SQL**),
`translation.0001_initial` (tables nouvelles), `translation.0002_paquets_argos` (liste de choix, aucune
instruction SQL). Aller-retour testé sur une base d'essai : `recette-migrations.md` (aucune perte).

## 4. Confidentialité et sécurité

- Clés chiffrées (même mécanisme que le module IA), jamais réaffichées ni journalisées ; absentes de
  l'administration Django et des exports.
- **Aucun envoi sans confirmation** ; résumé des conditions du fournisseur et prise de connaissance avant le
  premier envoi ; refus côté serveur des moteurs en ligne pour un projet confidentiel ; plafonds mensuels.
- Journal des dysfonctionnements : module « traduction », 8 catégories, aucun texte ni clé (liste blanche des
  clés de diagnostic) ; les erreurs dues à l'utilisateur ne créent pas d'incident.
- Projet confidentiel d'autrui : l'administrateur ne voit que les métadonnées ; mémoire de traduction propre à
  chaque compte ; exports réservés au propriétaire.
- Les textes des projets confidentiels ne sont **pas chiffrés** dans la base et les sauvegardes (limite écrite).
- Isolation : les conteneurs refusent de démarrer sous le nom de projet de l'installation principale ou de
  l'essai 1.2.0, sauf autorisation explicite `AUTORISER_NOM_PROJET=<même nom>` dans `.env`, prévue pour
  mettre à jour une installation existante en gardant ses données.

## 5. Dépendances

| Dépendance | Où | Statut |
|---|---|---|
| httpx, python-docx, pypdf, lxml, cryptography | Application | Déjà présentes en 1.2.0 : **aucune dépendance nouvelle pour l'application** |
| argostranslate 1.11.0, ctranslate2 4.9.0, sentencepiece 0.2.3, stanza 1.10.1, spacy 3.8.18, minisbd 0.9.5, torch 2.5.1+cpu (et leurs dépendances, 64 lignes figées) | Image `japon-explorateur-argos:1.3.0` uniquement | Résolues pour Python 3.12 / Linux x86_64 le 14 novembre 2026 ; construction à vérifier sur votre poste |
| Paquets de langues Argos (ja→en, en→fr) | Volume `argos-packages` | Téléchargés **seulement sur votre choix** dans l'application (décision F), ou installés depuis un fichier |

## 6. Tests

| Ensemble | Nombre | Résultat |
|---|---|---|
| Tests de la 1.2.0 (7 fichiers) | 130 | Tous passent ; un seul adapté : le numéro de version (`test_evolution_120`) |
| Tests de la 1.3.0 (14 fichiers) | 257 | Tous passent |
| **Total** | **387** | **OK** (`python manage.py test tests`) |

Correspondance avec le cahier des charges (§ 23.1) : T1 contrat des moteurs ; T2–T4 DeepL, glossaires DeepL et
Google sur réponses enregistrées (`tests/fixtures/traduction/`) ; T5 consignes IA ; T6 Argos ; T7 découpage ;
T8 encodages ; T9 confirmation ; T10 lots et reprise ; T11 contrôles à la réception ; T12 versions ; T13 notices ;
T14 glossaires ; T15 confidentialité ; T16 plafonds et consommation ; T17 pas de bascule automatique ; T18
journal ; T19 exports ; T20 non-régression ; **T21 migrations : test réel sur base d'essai** (`recette-migrations.md`).

Non exécutés ici (à faire selon le protocole) : appels réels aux services, construction des images Docker,
exécution du script PowerShell, traduction Argos réelle et hors ligne, retour à la 1.2.0 sous Docker.

## 7. Limites connues

Voir `07-limitations-connues.md` (tenu à jour lot par lot), notamment : découpage après certaines abréviations
latines, PDF sans OCR, contrôle terminologique sans morphologie avancée, un seul glossaire par requête DeepL,
tarifs DeepL et Google à compléter, résumé Gemini fondé sur la version archivée des conditions, comportement
hors ligne d'Argos dépendant des versions figées.

## 8. Livrables

| Livrable (§ 24) | Emplacement |
|---|---|
| Code 1.3.0, étiquette de la version de départ | Branche locale `evolution-1.3.0` ; `v1.2.0-reference` |
| Migrations additives | `apps/catalog/migrations/0005…`, `apps/incidents/migrations/0002…`, `apps/translation/migrations/` |
| Tests et réponses enregistrées fictives | `tests/`, `tests/fixtures/traduction/` |
| Archive et empreinte SHA-256 | `japon-explorateur-1.3.0.zip` et `.sha256` |
| Notices (§ 20) | `notice-cle-deepl.md`, `notice-cle-google.md`, `notice-argos.md`, `04-guide-utilisation.md` (§ 9 IA, § 10 Ollama) |
| Protocole de vérification | `05-protocole-verification.md` |
| Rapport technique | ce document |
| Journal des modifications | `CHANGELOG.md` |
| Retour à la 1.2.0 et correctif inverse | `retour-1.2.0.md`, `retour-1.2.0/evolution-1.2.0-vers-1.3.0.patch`, commande `verifier_retour_120` |
