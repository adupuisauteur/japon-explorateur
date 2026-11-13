# Conformité au cahier des charges v1.2

## Critères d'acceptation (§19)

| ID | Couverture | Test |
|---|---|---|
| AT-01 | Import CSV, recherche par identifiant, titre, rōmaji, katakana | `test_import_and_records.test_at01_…` |
| AT-02 | Unicode conservé à l'import, à l'affichage, en recherche et à l'export (DOCX, PDF, JSON, CSV, HTML) | `test_at02_…`, `test_library_exports` |
| AT-03 | Provenance par résultat ; source en erreur sans blocage des autres | `test_at03_…` |
| AT-04 | Sélection, désélection, exclusion avec motif, réintégration, actions globales | `test_at04_…` |
| AT-05 | L'exclusion ne supprime jamais une notice de la bibliothèque | `test_at05_…` |
| AT-06 | Modes automatique, sélectif et manuel ; mode par défaut réglable (instance et utilisateur) | `test_at06_…` |
| AT-07 | La session conserve requête, variantes, sources, filtres, statistiques, durée et décisions | `test_at07_…` |
| AT-08 | Relance avec classement nouveau, connu, modifié, indisponible, non comparable ; aucun écrasement | `test_at08_…` |
| AT-09 | Import : aperçu, correspondance, erreurs, rapport avant validation | `test_at09_…` |
| AT-10 | Versions historisées et consultables avec les valeurs précédentes | `test_at10_…` |
| AT-11 | Dossiers, sous-sections, notes de dossier, annotations avec repère | `test_at11_…` |
| AT-12 | DOCX, PDF, TXT, JSON, CSV, HTML et ZIP générés | `test_at12_*`, `test_at16_…` |
| AT-13 | Préparation : titre, sujet, en-tête, pied de page, dates, provenance, prévisualisation | `test_at13_…` |
| AT-14 | CSV sans ligne de titre, option BOM, séparateur réglable, manifeste associé | `test_at14_…` |
| AT-15 | JSON versionné, réimporté sans doublon | `test_at12_txt_and_json_and_at15_reimport` |
| AT-16 | Site HTML autonome, ressources locales, recherche locale en `file://` | `test_at16_…` |
| AT-17 | IA désactivée : toutes les fonctions documentaires restent disponibles | `test_ia03_and_at17_…` |
| AT-18 | Aucun envoi sans déclenchement ni confirmation explicites | `test_at18_and_ia06_…` |
| AT-19 | Sauvegarde puis restauration réelle de la base et des fichiers | `test_platform.BackupRestoreTests` |
| AT-20 | Écrans principaux affichés en vue ordinateur et mobile | `test_at20_…` |
| AT-IA-01 à 12 | Préférences initiales, profils, désactivation, absence de déclenchement implicite, trois fournisseurs, fournisseur par fonction, indisponibilité sans basculement, révocation, clé distincte du consentement | `tests/test_ai.py` |

## Points d'attention et limites connues

- **Connecteurs non vérifiés en conditions réelles** (Kokusho, NDL Search, Japan Search) : signalés comme tels dans l'interface jusqu'au premier test réel réussi. L'accès IIIF et l'API Japan Search n'ont pas pu être appelés depuis l'environnement de développement (réseau restreint). La lecture des réponses est testée sur des réponses simulées conformes aux formats publics. Lors de la mise en service, lancez « Tester le connecteur » et ajustez si besoin `endpoint`, `db_param` et `japansearch_db`.
- **Colonnes CODH** : le CSV réel n'a pas été fourni. La correspondance automatique reconnaît les intitulés usuels (国文研書誌ID, 書名, 書名よみ, 著者, 刊写年…), mais doit être vérifiée lors du premier import. L'écran de correspondance permet tout ajustement.
- **Image Docker** : le fichier Compose est validé, mais l'image n'a pas pu être construite dans l'environnement de développement (pas de démon Docker). L'application, elle, a été testée sur PostgreSQL, Redis et Celery réels.
- **Conversion des ères (元号)** : règle « an 1 = année de début de l'ère », sans gestion des changements d'ère en cours d'année. Le résultat est marqué « règle automatique » et reste corrigeable.
- **Variantes de kanji** : table de correspondances courantes (~230 paires), proposées comme suggestions et jamais appliquées d'office.
- **Hors périmètre V1** (conformément au §2.2) : reconnaissance du kuzushiji, collaboration en temps réel, publication publique.
- **Synchronisation complète ou incrémentale** : le contrat (`harvest`) et le traitement (comparaison, notices « non retrouvées » jamais supprimées) sont en place. Aucun connecteur livré ne moissonne encore (Kokusho, faute d'API, procède par actualisation des notices connues). L'OAI-PMH de NDL pourra s'y brancher.

## Corrections issues de l'audit

Chaque correction est couverte par `tests/test_audit_corrections.py`.

| # | Anomalie | Correction |
|---|---|---|
| 1 | Restauration de secours (JSON) en échec ; base vidée en cas d'erreur | Fixture renommée, JSON validé avant toute suppression, `flush` + `loaddata` en transaction, `pg_restore --single-transaction --exit-on-error`, sauvegarde de sécurité préalable |
| 2 | Clé secrète de développement utilisable en production | Démarrage refusé si clé absente, courte ou d'exemple (hors `DEBUG`) ; idem mot de passe PostgreSQL distant |
| 3 | Adresse de fournisseur IA libre (SSRF) | Administrateur seul, HTTPS, IP publiques uniquement, liste blanche `AI_ALLOWED_LOCAL_URLS`, pas de redirection, pas d'écho du corps de réponse |
| 4 | `store_inputs` vrai par défaut | Faux par défaut (migration), purge après exécution, annulation, blocage, et des brouillons de plus de 24 h |
| 5 | Redirections ouvertes (`next`) | `safe_url` / `safe_next` sur toutes les vues concernées |
| 6 | Chercheur modifiant le fonds commun ; Lecteur accédant à l'IA | Propositions de correction pour le Chercheur ; validation, adoption, liens et œuvres réservés à l'administrateur ; IA fermée au Lecteur |
| 7 | Normalisation NFC altérant la graphie source ; troncatures silencieuses | Aucune normalisation Unicode ; avertissements à l'import (troncature, nombre invalide, adresse non web) |
| 8 | Champs normalisés figés après mise à jour de la source | Recalcul des valeurs déduites par règle ; corrections utilisateur conservées (`manual_fields`) |
| 9 | Connecteurs non vérifiés présentés comme opérationnels | Badge « Non vérifié en conditions réelles » jusqu'au premier test réel réussi |
| 10 | XML générique à notice unique ignoré | Détection structurelle du conteneur de notices |
| 11 | Injection de formules CSV ; caractères rares absents du PDF sans signalement | Neutralisation par défaut (`'` en préfixe, notée au manifeste) ; polices de secours caractère par caractère (Hanazono), 〓 et liste des caractères absents dans le PDF et l'écran d'export ; plus aucune police non incorporée |
| 12 | Pas de limitation des tentatives de connexion ; premier démarrage non protégé | Verrouillage après 5 échecs (15 min), cache Redis ; `SETUP_TOKEN` exigé en HTTPS |
| 13 | Pas de CSP ; gestionnaires JavaScript en ligne | CSP stricte, `X-Frame-Options: DENY`, gestionnaires déplacés dans `app.js` |

## Arbitrages du §21.2 retenus par défaut

| Question | Choix par défaut (modifiable) |
|---|---|
| Hébergement initial | Local via Docker Compose, port publié sur 127.0.0.1 uniquement |
| Premier connecteur | Kokusho (IIIF + Japan Search), NDL Search en complément |
| Mode d'enregistrement | Sélectif |
| Conservation des sessions temporaires | 30 jours, puis purge nocturne |
| Fichiers numérisés | Liens seulement ; aucun téléchargement d'image |
| Génération PDF | ReportLab + police IPAex incorporée, polices de secours Hanazono pour les idéogrammes rares |
| HTML autonome | Recherche locale par index JavaScript embarqué (compatible `file://`) ; liens vers les images, sans copie |
| Sauvegardes | Quotidienne, 14 conservées, copie externe via `BACKUP_EXTERNAL_DIR` |
