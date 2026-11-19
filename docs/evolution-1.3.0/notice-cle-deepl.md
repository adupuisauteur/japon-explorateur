# Notice — Créer et configurer une clé DeepL (version 1.3.0)

Informations vérifiées sur les pages officielles de DeepL le 14 novembre 2026. Les offres et les écrans de
DeepL peuvent changer : en cas de différence, la page officielle fait foi.

## 1. Choisir l'offre

DeepL propose deux offres d'**API** (différentes des abonnements « DeepL Translator » pour le site, qui ne
donnent pas de clé d'API) :

| | DeepL API Free | DeepL API Pro |
|---|---|---|
| Coût | gratuit | abonnement + paiement au caractère (voir la page des tarifs de DeepL) |
| Volume | jusqu'à 500 000 caractères par mois | sans plafond de volume ; plafond de coût réglable chez DeepL |
| Textes envoyés | peuvent servir à améliorer les modèles de DeepL | supprimés après la traduction, jamais utilisés pour l'entraînement |
| Adresse utilisée par l'application | `api-free.deepl.com` | `api.deepl.com` |

> Pour des textes de recherche non publiés ou sensibles, préférez **API Pro**, ou Argos (hors ligne). Le résumé
> des conditions est affiché par l'application avant le premier envoi (Traduction → Moteurs → « Conditions
> d'utilisation des textes envoyés »).

## 2. Obtenir la clé

1. Créez un compte DeepL API depuis la page « DeepL API » du site de DeepL, et choisissez **API Free** ou
   **API Pro**. Confirmez votre adresse électronique.
2. Connecté à votre compte, ouvrez l'onglet **« API Keys & Limits »** (adresse :
   `https://www.deepl.com/your-account/keys`).
3. Cliquez sur **« Create key »**, donnez-lui un nom (par exemple « Japon — essai 1.3.0 ») et copiez la clé.
   Une clé de l'offre gratuite se termine en général par `:fx`.
4. *Conseillé* : sur la même page, fixez une **limite d'usage** à la clé.

## 3. La saisir dans l'application

1. http://localhost:8002 → **Traduction → Moteurs** → carte **DeepL**.
2. Collez la clé dans **Clé**, choisissez l'**Offre** (gratuite ou payante, comme votre compte DeepL : une
   erreur d'offre fait échouer le test), facultativement un **plafond mensuel** en caractères, puis
   **Enregistrer**.
3. Cliquez sur **Tester** : l'application lit votre consommation chez DeepL (aucun texte envoyé, aucun
   caractère décompté) et affiche « Connexion réussie : … caractères utilisés sur … ».
4. Dans **Moteurs choisis**, sélectionnez DeepL comme moteur par défaut ou comme deuxième moteur.

La clé est **chiffrée** et n'est plus jamais affichée ; « Effacer la clé » la retire du serveur.

## 4. Quota

- Le quota lu chez DeepL s'affiche sur l'écran de confirmation de chaque traduction.
- Quota épuisé : message « Quota DeepL épuisé pour la période en cours », la tâche s'arrête, le deuxième moteur
  vous est **proposé** (jamais utilisé d'office).
- Votre consommation par mois : **Traduction → Consommation**. Les montants restent « non disponibles » tant
  que les tarifs DeepL ne sont pas saisis dans `apps/translation/reference/tarifs-traduction.json`.

## Sources

- DeepL — Gestion des clés d'API : https://developers.deepl.com/docs/admin/managing-api-keys
- DeepL — DeepL API Free et Pro : https://support.deepl.com/hc/articles/360021200939
- DeepL — Politique de confidentialité : https://www.deepl.com/en/privacy
