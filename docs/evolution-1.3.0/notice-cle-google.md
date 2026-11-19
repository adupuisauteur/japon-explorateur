# Notice — Créer et configurer une clé Google Traduction (version 1.3.0)

L'application utilise **Cloud Translation — Basic (v2)** avec une **clé d'API** simple (décision A2). Étapes
vérifiées sur la documentation officielle de Google Cloud le 14 novembre 2026 ; les écrans de la console
peuvent changer.

## 1. Projet et facturation

1. Ouvrez la **console Google Cloud** (https://console.cloud.google.com) avec votre compte Google.
2. En haut, sélecteur de projet → **Nouveau projet** (par exemple « japon-traduction »). Un projet séparé
   pour les essais est recommandé par Google.
3. **Facturation** : Cloud Translation exige un compte de facturation lié au projet (menu **Facturation** →
   associer un compte, avec un moyen de paiement). Consultez la page des tarifs de Cloud Translation pour
   la franchise et le prix au caractère.

## 2. Activer l'API

Menu **API et services → Bibliothèque** → recherchez « **Cloud Translation API** » → **Activer**.

## 3. Créer une clé restreinte

1. **API et services → Identifiants → Créer des identifiants → Clé API**. Copiez la clé.
2. Ouvrez la clé (icône crayon) → **Restrictions relatives aux API** → **Restreindre la clé** → cochez
   seulement **Cloud Translation API** → **Enregistrer**. Ainsi, une clé divulguée ne donne accès à rien d'autre.

## 4. Plafond de dépenses conseillé

- **Facturation → Budgets et alertes** → créez un budget pour le projet, avec des alertes (par exemple à 50 %,
  90 % et 100 %). Une alerte prévient ; elle n'arrête pas la facturation.
- **API et services → Cloud Translation API → Quotas** : vous pouvez abaisser le quota de caractères par jour.
- Dans l'application, fixez aussi un **plafond mensuel** de caractères sur la carte Google (Traduction →
  Moteurs) : au-delà, la traduction est bloquée.

## 5. La saisir dans l'application

1. **Traduction → Moteurs** → carte **Google Traduction (Basic)** → collez la clé → **Enregistrer**.
2. **Tester** envoie la phrase d'essai fictive « これは動作確認のための架空の文です。 » et affiche le résultat.
3. Choisissez Google comme moteur par défaut ou deuxième moteur.

La clé est chiffrée, jamais réaffichée. Google ne gère pas de glossaire dans cette édition : seul le contrôle
terminologique local s'applique.

## Sources

- Cloud Translation — Configuration : https://docs.cloud.google.com/translate/docs/setup
- Cloud Translation — Utilisation des données : https://docs.cloud.google.com/translate/data-usage
