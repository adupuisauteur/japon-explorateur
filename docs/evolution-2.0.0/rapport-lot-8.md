# J-ed 2.0.0 — Rapport du lot 8 : choix du modèle d'IA dans une liste

15 novembre 2026 · branche `evolution-2.0.0` · plan : `01-audit.md`, § 3.9 · cahier des charges : § 9 ter

## 1. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Liste déroulante | Sous chaque champ « modèle », la liste des modèles du fournisseur choisi, rechargée sans recharger la page quand le fournisseur change. Le champ texte reste la valeur enregistrée : il est masqué quand un modèle de la liste est choisi, affiché pour « Autre modèle (saisie libre) » ou quand aucune liste n'existe | `templates/partials/model_picker.html`, `templates/ai/_model_picker.html`, `static/js/app.js` |
| Écrans | Préférences IA (modèle par défaut, et un modèle par fonction), page « IA indisponible », Traduction → Moteurs (moteur par défaut et deuxième moteur), fiche d'un projet de traduction, Traduction → Évaluation (deux IA) | 5 gabarits |
| Modèles de texte seulement | Écartés : images, son, synthèse vocale, transcription, temps réel, vectorisation, modération, anciens modèles de complétion (OpenAI) ; images, vidéo, voix, vectorisation (Gemini) ; vectorisation, reclassement, voix, images (services compatibles OpenAI). Anthropic : tous ses modèles sont des modèles de texte | `apps/ai/providers.py` (`text_models`) |
| Listes déjà enregistrées | Filtrées à l'affichage ; le test de connexion (IA → Fournisseurs) enregistre désormais la liste filtrée | `apps/ai/views.py` |
| Tarif | Tarif estimé (entrée / sortie, par million de jetons) à côté du modèle, quand l'administrateur l'a saisi dans IA → Tarifs (préfixe le plus long) | `apps/ai/views.py` |
| Actualiser la liste | Bouton qui interroge le fournisseur avec la clé de l'utilisateur, sur son action seulement ; date de la dernière liste affichée ; en cas d'échec, message affiché et liste précédente conservée ; action inscrite au journal d'audit | `apps/ai/views.py` (`model_refresh`) |
| Modèle absent | Avertissement quand le modèle enregistré n'apparaît pas dans la liste du fournisseur (retiré, ou nom inexact), sans le changer d'office | `templates/ai/_model_picker.html` |
| Refus à l'usage | Le message de refus d'un modèle absent (lot 0) invite à cliquer sur « Actualiser la liste » | `apps/ai/services.py` |

**Base de données.** Aucun changement : la liste est déjà conservée avec la clé du fournisseur
(`AIProviderCredential.available_models`), comme prévu par l'audit. La commande de retour vers la 1.3.0 ne
change pas.

## 2. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète, exécution séquentielle | **575 tests réussis** (560 + 15 nouveaux) |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration |
| Navigateur réel (Chrome sans interface, base temporaire, clés fictives) | liste affichée avec le tarif ; champ texte masqué puis rempli au choix d'un modèle ; saisie libre ; changement de fournisseur : liste filtrée (2 modèles d'image et de son écartés sur 3) et avertissement ; **aucune erreur dans la console** |

**Nouveaux tests** (`tests/test_modeles_200.py`, 15 tests) :

- filtrage par fournisseur ; test de connexion qui enregistre la liste filtrée ;
- liste : tarif, saisie libre, date, aucun script ; modèle absent conservé avec avertissement ; pas de
  fournisseur, pas de clé, liste vide ; anciennes listes filtrées à l'affichage ;
- actualisation : jamais d'appel au fournisseur pour afficher la liste, un appel sur demande ; échec affiché,
  liste conservée ;
- accès : lecteur refusé, visiteur renvoyé à la connexion, actualisation en POST seulement ; la clé d'un autre
  utilisateur n'est jamais utilisée ;
- écrans : préférences IA (par défaut et par fonction), moteurs, fiche projet, évaluation, page « IA
  indisponible » ; valeur enregistrée inchangée ; synchronisation côté navigateur.

## 3. Écarts et choix faits pendant le lot

- **Liste sous le champ, et non à sa place.** Le champ texte reste la valeur envoyée au serveur : sans
  JavaScript, ou pour un service compatible OpenAI sans liste, la saisie continue de fonctionner. Aucun
  formulaire ni aucune règle de validation n'a changé côté serveur.
- **Page « IA indisponible »** : le champ du modèle n'est plus marqué « obligatoire » dans le navigateur, car il
  est masqué quand un modèle est choisi. Le serveur refuse toujours une demande sans modèle.
- **Changement de fournisseur** : le modèle saisi pour l'ancien fournisseur n'est pas effacé. L'avertissement
  « n'apparaît pas dans la liste de ce fournisseur » signale l'incohérence.
- **Listes très longues** : au-delà de 2 000 modèles (limite du lot 0), la liste l'indique.
- **Vérification réelle** avec tes clés : à faire sur ton poste (V8-1 à V8-5). Statut : testé en simulation ;
  test réel à confirmer.

## 4. Livrables du lot

- Archive `japon-explorateur-2.0.0-lot8.zip` et son empreinte `.sha256` : elle contient aussi les statuts dans
  les exports (`lot5b`) et la correction de l'alerte d'essai du lot 5.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 8 » (V8-1 à V8-5).
- CHANGELOG : section 2.0.0, lot 8.
