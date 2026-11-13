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
