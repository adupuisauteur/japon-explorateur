# Guide d'utilisation des nouvelles fonctions — version 1.2.0

## 1. Rechercher dans les sources japonaises

### Choisir les sources
**Rechercher** → cochez les sources à interroger. Une source n'apparaît que si elle est activée dans **Sources → (la source) → Configuration → « Interrogé dans les recherches »**. Activez une nouvelle source seulement après un **« Tester le connecteur »** réussi.

Sources disponibles dans la 1.2.0 :

| Source | Contenu | À savoir |
|---|---|---|
| NDL Search | Catalogue de la Bibliothèque nationale de la Diète | Lien « Document numérisé » quand la NDL l'a numérisé |
| Japan Search | Agrégateur national (bibliothèques, archives, musées) | Toutes bases confondues |
| Archives nationales (via Japan Search) | Fonds des Archives nationales du Japon | Préconfigurée, à activer après test |
| CiNii Research | Articles, revues savantes, thèses, données | Nécessite l'identifiant CiNii (guide d'installation, annexe) |
| CiNii — bibliothèques universitaires | Livres et revues des bibliothèques universitaires | Même identifiant |
| Kokusho | Livres anciens et manuscrits (NIJL) | Inchangé |

### Ajouter une base d'archives, d'université ou de musée
**Sources → Japan Search → « Trouver une base Japan Search »**. Tapez le nom de l'institution, de préférence en japonais : 国立公文書館, 早稲田, 京都大学, 日文研, 県立公文書館… Pour chaque base trouvée :
- **diffusée** : vous pouvez cliquer sur **Créer une source**. La source est créée **désactivée** : testez-la, puis activez-la ;
- **non diffusée** : l'institution n'autorise pas l'accès par API. La base reste consultable sur son site, mais pas depuis l'application.

### Variantes de graphie des noms propres
- Les **suggestions automatiques** s'affichent sous la requête : formes anciennes et nouvelles des kanji, kana, rōmaji, et désormais **nom sans suffixe**. Par exemple, 望月千代女 suggère 望月千代. Cochez celles à inclure.
- Le champ **« Mes variantes de graphie »** accepte vos propres formes, séparées par « ; ». Par exemple : `望月千代 ; 千代女房`.
- Si un nom et ses variantes sont enregistrés dans le **référentiel des noms** (fiche auteur), ces variantes sont proposées automatiquement, avec leur statut « attestée » ou « non vérifiée ».
- Les variantes sont interrogées **en plus** du terme principal, et non à sa place. Pour Japan Search, elles sont combinées en « OU » : l'ajout de variantes élargit les résultats au lieu de les restreindre.

### Lire l'état de chaque source
En haut de la page de résultats, chaque source affiche l'un de ces états :

| Pastille | Signification | Que faire ? |
|---|---|---|
| Verte : « N résultat(s) » | Recherche réussie | — |
| Grise : « Recherche réussie, aucun résultat » | La source a répondu, mais ne contient rien pour cette requête. **Ce n'est pas une erreur.** | Essayer des variantes |
| Orange : « Source indisponible » | Le site de l'institution ne répond pas, ou ce poste n'a pas pu le joindre | Réessayer plus tard (bouton ↻) |
| Rouge : « Réponse impossible à interpréter » | La source a répondu dans un format inattendu (elle a peut-être changé son interface) | Exporter le diagnostic |
| Rouge : « Erreur technique » / « Configuration incomplète » | Requête refusée, identifiant manquant… | Lire le message ; exporter le diagnostic |

Une source en échec **n'empêche jamais** les autres d'afficher leurs résultats. Le lien « Voir l'incident » mène directement au journal.

### Trier, filtrer, ouvrir, enregistrer
- **Tri** : pertinence, titre, date, **auteur**, source interrogée, **institution détentrice**, date de collecte.
- **Filtres** : source, décision, période, type, **document numérisé disponible**…
- Sur chaque résultat : **Notice officielle** (site de l'institution), **Document numérisé** ou **Images** quand ils existent.
- **Retenir**, puis **Intégrer la sélection** : la référence entre dans votre catalogue. Si elle existait déjà, l'ancienne version est **historisée** : vos notes, favoris et étiquettes ne sont jamais écrasés.

## 2. Journal des dysfonctionnements

Menu **Dysfonctionnements**. La pastille rouge indique le nombre de nouveaux incidents de gravité Erreur ou Critique.

### Ce qui est enregistré automatiquement
Échecs des sources (indisponibilité, réponse illisible, erreur technique, configuration), erreurs de conversion des métadonnées, erreurs d'importation, erreurs de base de données (gravité **Critique**) et erreurs inattendues de l'application. Une **recherche sans résultat n'est jamais enregistrée**.

### Lire un incident
- **Gravité** : Information, Avertissement, Erreur, Critique.
- **Origine probable**, expliquée en langage courant : source distante, réseau de ce poste, connecteur, traitement des données, application.
- **Fois** : les problèmes identiques sont regroupés. Un même incident peut s'être produit 12 fois.
- **Détail technique** : code HTTP, identifiant de requête, durée, adresse appelée (expurgée), extrait de la réponse quand elle était illisible.
- **Historique** : création, changements de statut, réapparitions, retour de la source.

### Filtrer et rechercher
Par date, module, source, gravité, statut (« Non résolus »), type (automatique ou signalement manuel). Le champ de recherche accepte un identifiant d'incident (`INC-…`) ou un **identifiant de requête**.

Depuis la fiche d'une source (**Sources → …**), le bloc **« Dysfonctionnements de cette source »** donne son historique.

### Suivre la correction (administrateur)
Les statuts possibles sont Nouveau → À analyser → En cours de correction → Corrigé → À vérifier → Clôturé. Le passage à **Corrigé** enregistre la version de correction. Si le problème se reproduit ensuite, l'incident est **rouvert automatiquement** (« réapparu »). La fiche compare alors les occurrences **avant et après** la correction.

### Signaler un problème soi-même
Utilisez le bouton **Signaler un problème** (dans le journal ou en bas de chaque page) quand quelque chose ne va pas sans message d'erreur. Indiquez le module, la description, les opérations réalisées, le résultat attendu et le résultat obtenu, et joignez si besoin une capture d'écran (PNG, JPEG, WebP ou GIF, 5 Mo au plus). Le signalement porte la mention « signalement manuel ».

### Analyse
**Dysfonctionnements → Analyse** présente les erreurs récurrentes, les sources les plus instables, les connecteurs qui échouent régulièrement, les incidents apparus avec la version actuelle et les incidents corrigés qui sont réapparus. Elle signale aussi les moments où **plusieurs sources ont échoué en même temps** : la cause est alors presque toujours la connexion de ce poste.

### Exporter un diagnostic (pour Claude ou un développeur)
Depuis un incident (**Exporter le diagnostic**) ou depuis le journal filtré (**Exporter un diagnostic**) :
1. Un **aperçu** montre exactement le contenu du fichier.
2. Choisissez *Texte lisible (Markdown)* ou *JSON*, et cochez si besoin **« Masquer les termes de recherche »**.
3. **Télécharger ce rapport**.

Le rapport contient la version, le module, l'identifiant, les messages techniques, le contexte et les étapes pour reproduire. Les mots de passe, clés API (dont l'identifiant CiNii), jetons, adresses e-mail, noms d'utilisateur et chemins personnels sont **masqués automatiquement**. Le journal reste sur ce poste : rien n'est envoyé à l'extérieur.
