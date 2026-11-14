# Limitations connues — version 1.3.0 (document tenu à jour au fil des lots)

## Moteurs (lot 3)

- **Aucun test réel** de DeepL, Google Traduction ou des IA n'a été possible depuis l'environnement de
  développement : statut « développé et testé en simulation ; test réel à confirmer ».
- Google Basic : le classement des erreurs repose sur le code HTTP et le champ `status` de l'erreur ; la forme
  exacte des messages n'a pas pu être vérifiée.
- Tarifs DeepL et Google non renseignés (`apps/translation/reference/tarifs-traduction.json`) : l'estimation
  de coût de ces moteurs s'affiche « non disponible » tant qu'ils ne sont pas complétés.
- Argos : mode simulé tant que le service Docker (lot 9) et ses paquets ne sont pas installés.

## Chaîne de traitement (lot 4)

- Estimation du coût IA : le nombre de jetons est approché à partir du nombre de caractères.
- Fonctionnement avec un vrai worker Celery et Redis sous Docker : à vérifier lors de la recette.

## Projets et documents (lot 6)

- **Découpage** : une abréviation suivie d'une majuscule (« Mr. Yamamoto ») est coupée en deux segments ;
  la fusion manuelle corrige. Le japonais n'est pas concerné.
- **PDF** : l'ordre du texte extrait peut être imparfait (colonnes, texte vertical) ; l'OCR n'est pas pris en
  charge (un PDF sans texte est refusé).
- **Word** : seuls les fichiers .docx sont lus (pas les anciens .doc) ; la mise en forme n'est pas conservée.
- Le texte d'un segment ne peut pas être corrigé directement (le texte importé reste la référence exacte) :
  seules la fusion et la division sont proposées.
- Un projet n'a qu'un propriétaire (pas de partage en 1.3.0). Les projets confidentiels ne sont pas
  chiffrés : la base de données et les sauvegardes les contiennent en clair.

## Glossaires et mémoire (lot 7)

- **Glossaires DeepL non testés en conditions réelles** : création (`POST /v3/glossaries`), vérification des
  langues (`GET /v3/languages?resource=glossary`), utilisation (`glossary_id` dans `/v2/translate`) et suppression
  (`DELETE /v3/glossaries/{id}`) sont conformes à la documentation officielle consultée le 14 novembre 2026, mais
  testées uniquement avec un DeepL simulé. La forme exacte de la réponse de `/v3/languages?resource=glossary`
  n'est pas illustrée dans la documentation : si elle diffère, l'envoi est annulé avec un message explicite
  (jamais d'envoi « à l'aveugle »).
- **Un seul glossaire par requête DeepL** (limite du service) : lorsque plusieurs glossaires d'un projet ont une
  copie à jour, seul le plus prioritaire est appliqué par DeepL ; les autres font l'objet du contrôle local, et
  l'alerte jointe aux segments concernés le dit.
- Une copie DeepL est liée au compte et à l'offre (gratuite ou payante) utilisés pour l'envoi ; après un
  changement d'offre, elle est considérée comme périmée et doit être renvoyée. Si un compte est supprimé ou
  anonymisé, ses copies DeepL restent sur son compte DeepL (la clé est effacée) : à supprimer depuis DeepL.
- L'offre gratuite de DeepL limite le nombre de glossaires et d'entrées (selon le compte) : un refus de DeepL est
  affiché et journalisé (catégorie « glossaire refusé »).
- **Contrôle terminologique** : comparaison exacte après normalisation (casse, accents, macrons, pluriels en
  « s » ou « x »). Les formes fléchies plus complexes (« cheval/chevaux », féminins, élisions) et les conjugaisons
  japonaises ne sont pas reconnues : le contrôle peut signaler un écart qui n'en est pas un. Il ne corrige jamais.
- Les glossaires s'appliquent aux projets ; la traduction directe des notices (lot 5) ne les utilise pas.
- La mémoire de traduction reste une correspondance exacte (décision A5) : pas de correspondance approchée.
