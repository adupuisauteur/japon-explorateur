---
titre: Les fonctions IA et vos clés
rubrique: Traduire et résumer
ordre: 100
public: editeur
ecrans: ai:providers, ai:preferences, ai:tasks, ai:task, ai:launch, ai:launch_from_session
resume: Fournisseurs, clés personnelles, fonctions proposées et historique.
---
J-ed fonctionne entièrement **sans IA**. Activer une fonction la rend seulement disponible : aucun traitement ne
part sans votre action.

## Vos clés

IA → **Fournisseurs** (menu à votre nom → Préférences IA) : saisissez votre propre **clé API** (OpenAI, Anthropic,
Gemini, ou un service compatible OpenAI). J-ed ne demande jamais le mot de passe de votre compte ChatGPT, Claude ou
Google. Les clés sont chiffrées ; elles ne sont jamais affichées en entier ni exportées.

L'IA locale n'a pas de clé : elle se gère dans [Argos et IA locale](aide:moteurs-locaux).

## Préférences IA

- **Fournisseur et modèle par défaut**, et au besoin un fournisseur différent pour une fonction.
- **Fonctions proposées dans l'interface** : résumé documentaire, classification historique, détection des
  doublons, extension de recherche (variantes), extraction d'entités, question-réponse sur le fonds local,
  comparaison de notices.
- **Plafond mensuel estimé** : voir [Consommation et plafonds](aide:consommation-et-plafonds).

Le choix du modèle se fait dans la **liste des modèles du fournisseur** (« Actualiser la liste »), ou en saisissant
son nom.

## Ce que produit une IA

Tout résultat d'une IA est **étiqueté IA** et reste une **proposition** à valider : classification, entités,
doublons, traductions, résumés. Rien ne remplace les données de la source.

IA → **Historique** : chaque appel, avec le fournisseur, le modèle, les jetons envoyés et reçus, et le coût estimé.
