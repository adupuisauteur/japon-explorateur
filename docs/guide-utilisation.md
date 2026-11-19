# J-ed — Guide d'utilisation et de réglages

J-ed 2.0.0. Ce guide reprend l'aide intégrée (menu à votre nom → Aide).

# Premiers pas

## Bien démarrer avec J-ed

Ce que fait J-ed, les menus, et les trois rôles.

J-ed aide à la recherche documentaire sur le Japon. Il interroge les catalogues des institutions japonaises et
garde les notices utiles dans votre bibliothèque. Il sait aussi les traduire, les résumer et les exporter.

### Les menus

| Menu | Pour quoi faire |
| --- | --- |
| **Rechercher** | Interroger plusieurs catalogues à la fois : [Rechercher](#rechercher) |
| **Bibliothèque** | Les notices que vous avez gardées : [La Bibliothèque](#bibliotheque) |
| **Dossiers** | Regrouper des notices par sujet, les partager, les exporter : [Les dossiers](#dossiers) |
| **Traduction** | Traduire des notices et des documents, les résumer : [Choisir un moteur](#moteurs-de-traduction) |
| **Sources** | Les catalogues interrogés et leur état : [Les sources](#sources) |
| Recherche rapide | Un mot, un titre en japonais ou en rōmaji, sans passer par le formulaire |

Le menu à votre nom donne accès à votre compte, vos exports, vos tâches, vos notifications et à cette aide.
L'administrateur y trouve aussi **Administration** et **Dysfonctionnements**.

Sur chaque écran, le bouton **?** de la barre de menu ouvre la page d'aide qui le concerne.

### Les trois rôles

| Rôle | Ce qu'il peut faire |
| --- | --- |
| **Lecteur** | Chercher, lire les notices, tenir sa bibliothèque et ses dossiers, exporter |
| **Chercheur** | Tout cela, plus traduire, résumer et utiliser les fonctions IA |
| **Administrateur** | Tout, plus les comptes, les réglages, les sauvegardes et le suivi des dysfonctionnements |

### Vos données

Tout reste sur votre ordinateur. Aucun texte ne part vers un service extérieur (DeepL, une IA en ligne) sans une
action de votre part, et J-ed affiche le coût estimé avant de vous demander confirmation.

Les notices restent la propriété de leurs institutions. Vérifiez-les auprès des catalogues d'origine.

### Découvrir J-ed sans vos données

L'administrateur peut charger un **jeu d'essai** : une quarantaine de notices fictives, un dossier et un projet de
traduction, à retirer d'un clic ensuite. La page [Essayer J-ed](#essayer-j-ed) propose un parcours pas à
pas, avec le résultat attendu à chaque étape.

### Pour aller plus loin

- [Quoi de neuf dans J-ed](#quoi-de-neuf)
- [Lexique](#lexique)
- [Signaler un problème](#signaler-un-probleme)

## Quoi de neuf

Les nouveautés de la dernière version.

Voici ce qui change dans la dernière version. Les versions précédentes sont décrites dans
l'**Historique des versions** (Administration).

### Version 2.0.0 (19 novembre 2026)

Une version de consolidation : J-ed devient plus sûr, travaille seul la nuit, résume, et s'explique lui-même.

- **Un nouveau nom, J-ed**, et un logo. Une page « À propos » donne la version et l'origine du projet.
  Administration et Dysfonctionnements passent dans le menu à votre nom (administrateur).
- **Trois statuts par notice**, sans confusion possible : notice disponible, document consultable, IIIF. Le
  manifeste IIIF peut être vérifié d'un clic. Les statuts figurent dans les filtres, les tris et les exports.
- **Notifications** : une fenêtre et un compteur vous préviennent quand une tâche se termine, se met en pause ou
  échoue, et l'administrateur quand un dysfonctionnement apparaît.
- **Tâches et file de nuit** : chaque traduction est une tâche que l'on peut lancer tout de suite, programmer, ou
  placer dans la file de nuit ; pause, reprise sans rien renvoyer, compte rendu du matin. « Traduire maintenant »
  sur la fiche et dans la Bibliothèque. Page « Traductions effectuées ».
- **Plafonds** : un plafond atteint met la tâche en pause ; J-ed ne change jamais de moteur de lui-même.
- **Argos installé d'office**, la traduction japonais → français s'installe en un clic, avec une traduction d'essai.
- **Choix du modèle d'IA dans une liste** tirée du fournisseur, avec le tarif estimé quand il est connu.
- **Résumés IA** : résumé court, détaillé ou fiche d'analyse, toujours dans votre langue, depuis la fiche, la
  Bibliothèque ou l'atelier ; enchaînés aux traductions si vous le souhaitez.
- **IA locale** facultative : une IA gratuite qui travaille sur votre ordinateur, pour les résumés.
- **Japonais ancien** : repérage du bungo, du kanbun et du sōrōbun, et moteur choisi pour eux.
- **Documents et nouvelles sources** : **Aozora Bunko** (plus de 17 000 œuvres) dont le texte intégral se lit
  dans J-ed avec ses furigana et s'envoie vers un projet de traduction ; **Waseda** par le catalogue de la NDL ;
  **Kokusho** interrogé dans sa vraie base ; bouton **« Ouvrir le document »** vers la visionneuse de la source ;
  **visionneuse intégrée** facultative ; pour la NDL, J-ed dit si un document numérisé est en accès libre.
- **Jeu d'essai fictif** et procédure « Essayer J-ed », pour découvrir l'application ou vérifier une nouvelle
  version (Administration → Jeu d'essai).
- **Rapidité mesurée** sur l'ordinateur (commande `mesurer_performances`) ; doublons trouvés aussi dans une
  grande base.
- **Aide intégrée** : une page d'aide par écran (bouton **?**), une recherche, un lexique, cet historique, et une
  rubrique « Installation et mises à jour » (mettre à jour, vérifier, dépanner).
- **Installation** : mise à jour en une commande (`mettre-a-jour.ps1`), vérification automatique
  (`verifier-j-ed.ps1`), page « État de l'installation », sauvegardes copiées dans un dossier de Windows, réglage
  automatique selon la puissance de l'ordinateur.

## Les notifications

Être prévenu d'une tâche terminée, d'une pause ou d'un problème.

J-ed vous prévient quand une tâche (traduction, résumés, installation) se termine, se termine avec des erreurs ou
se met en pause. L'administrateur est aussi prévenu des dysfonctionnements.

### Où les voir

- Une **fenêtre** s'affiche en bas à droite de l'écran, une seule fois.
- Le **compteur rouge** sur le menu à votre nom indique les notifications non lues.
- Menu à votre nom → **Notifications** : la liste complète ; **Marquer comme lue** (ou « Vu » dans la petite
  fenêtre qui s'affiche à l'arrivée d'une notification) la marque comme lue.

### Choisir ce qui vous est signalé

Notifications → **Préférences** : vous activez ou désactivez chaque type (tâche terminée, terminée avec des erreurs,
en pause). L'administrateur choisit aussi la gravité minimale des fenêtres de dysfonctionnement.

Si vous n'êtes pas connecté au moment de l'événement, la fenêtre attend votre prochaine visite. Un bouton envoie
une notification d'essai, pour voir à quoi elle ressemble.

## Signaler un problème

Que faire quand quelque chose ne marche pas.

Quand une opération échoue, J-ed affiche un message qui dit ce qui s'est passé. Il ne masque jamais une erreur.

### Signaler

En bas de chaque page, le lien **Signaler un problème** ouvre un formulaire. Décrivez ce que vous faisiez et ce que
vous attendiez. L'adresse de la page est jointe automatiquement.

L'administrateur retrouve votre signalement dans **Dysfonctionnements**, avec les erreurs techniques enregistrées
au même moment. Voir [Dysfonctionnements](#dysfonctionnements).

### Avant de signaler

- Rechargez la page avec **Ctrl + F5** : après une mise à jour, le navigateur garde parfois l'ancienne version.
- Si le message dit qu'un service est injoignable (DeepL, une IA, une source), réessayez plus tard : J-ed met la
  tâche en pause et peut la reprendre sans rien perdre.

# Chercher et lire

## Rechercher dans les catalogues

Interroger la base locale et les catalogues japonais en une seule recherche.

### Lancer une recherche

1. Menu **Rechercher**. Saisissez votre requête : en japonais (書名, 人名), en rōmaji ou en français.
2. Cochez les **catalogues interrogés**. La base locale contient les notices déjà gardées dans J-ed.
3. Choisissez le **mode d'enregistrement** :
   - **Sélectif** (conseillé) : vous choisissez ce qui entre dans votre bibliothèque ;
   - **Automatique** : tout est enregistré, sans doublon ;
   - **Manuel / temporaire** : rien n'est gardé, la session sert de brouillon.
4. Lancez. Chaque catalogue répond à son rythme ; un catalogue indisponible est signalé sans bloquer les autres.

**Recherche avancée** : titre, auteur, sujet, lieu ou institution, période, type de document. Les filtres
s'appliquent pleinement à la base locale ; chaque catalogue reçoit les critères qu'il sait traiter (voir
[Les sources](#sources)).

**Variantes de graphie** : ajoutez vos propres variantes (anciennes graphies, autres lectures), séparées par « ; ».
« Proposer des variantes… » demande des hypothèses à une IA. Elles ne servent qu'après votre validation.

La **recherche rapide** de la barre de menu lance la recherche tout de suite, sur vos catalogues préférés (ceux que
vous avez demandé de mémoriser), sinon sur tous les catalogues interrogeables.

### Trier les résultats

Sur la page des résultats :

- **Sélectionner** ou **Exclure** chaque notice (avec un motif facultatif : hors sujet, doublon, mauvaise période…) ;
- filtrer par source, décision, période, type, et par comparaison avec la recherche précédente (nouveaux,
  déjà connus, modifiés) ;
- ouvrir l'aperçu d'une notice sans quitter la liste.

Puis **intégrez** la sélection : dans la Bibliothèque seule, ou directement dans un dossier. J-ed demande
confirmation avant d'intégrer.

### Retrouver une recherche

- Menu à votre nom → **Historique des recherches** : les sessions récentes. « Conserver la session » la garde au-delà du
  nettoyage automatique.
- **Enregistrer la recherche** sous un nom : vous pourrez la **relancer** plus tard. J-ed compare alors les
  résultats avec la fois précédente et signale les notices nouvelles ou modifiées.

Voir aussi : [Lire une notice](#lire-une-notice), [La Bibliothèque](#bibliotheque).

## Lire une notice

Ce que montre la fiche d'une notice, et ce qui vient de la source ou de vous.

La fiche d'une notice réunit plusieurs couches, toujours distinguées :

| Couche | Contenu |
| --- | --- |
| **Données originales de la source** | Ce que le catalogue a fourni, sans modification |
| **Données normalisées** | Les mêmes informations rangées par J-ed (titre, auteurs, dates, lieu, rōmaji) |
| **Couche éditoriale** | Traductions, résumés, classifications : chacune porte son origine (source, IA, traduction automatique, vous) |
| **Notes et annotations** | Vos notes privées ou partagées, rattachées éventuellement à une page, un folio, une image |

Un contenu produit par une IA ou un moteur de traduction est marqué comme tel. Il reste « non validé » tant que
vous ne l'avez pas validé.

### En haut de la fiche

- Les **trois statuts** de la ressource : notice, document, IIIF. Voir [Les trois statuts](#trois-statuts).
- Le **japonais ancien** : si le texte ressemble à du bungo, du kanbun ou du sōrōbun, un bandeau « probable »
  l'indique. Voir [Le japonais ancien](#japonais-ancien).
- **Ajouter au dossier**, ajouter à la Bibliothèque.

### Plus bas

- **Résumés IA** : résumer la notice, maintenant ou cette nuit. Voir [Résumés IA](#resumes-ia).
- **Traductions** : titre et description traduits, à valider. Voir [Traduire une notice](#traduire-une-notice).
- **Provenance** : d'où vient la notice, quand elle a été collectée.
- **Versions** : chaque mise à jour par la source garde l'ancienne version, consultable.
- **Œuvre** : rattacher plusieurs exemplaires d'une même œuvre. La date de composition de l'œuvre et celle de
  l'exemplaire ne sont jamais confondues.

Une erreur dans la notice ? **Proposez une correction** : l'administrateur la valide ou la refuse. Les données de la
source ne sont jamais écrasées.

### Ouvrir le document

Quand J-ed sait où lire le document lui-même, la fiche et les résultats de recherche proposent un bouton qui y
mène directement, plutôt que vers le manifeste IIIF (un fichier technique) :

- **Ouvrir dans le Kokusho** : la visionneuse du 国書データベース ;
- **Ouvrir dans la NDL Digital Collections** : la page du document numérisé (son accès peut être réservé aux
  bibliothèques ou à la NDL) ;
- **Ouvrir sur le site de Waseda** : la page de l'ouvrage. Les images restent celles du
  « 早稲田大学図書館古典籍総合データベース », qu'il faut citer. Toute réutilisation demande l'autorisation de la
  bibliothèque de Waseda ;
- **Lire le texte (Aozora Bunko)** : la page de lecture ; voir aussi [le texte intégral dans J-ed](#aozora-bunko).

### Voir les images dans J-ed (facultatif)

L'administrateur peut activer la **visionneuse intégrée** : Administration → Paramètres → « Visionneuse d'images
intégrée ». Elle est désactivée par défaut. Une fois activée, le bouton **Voir les images dans J-ed** apparaît sur
les fiches qui ont un manifeste IIIF. La visionneuse permet de passer d'une vue à l'autre (flèches du clavier) et
d'afficher la taille réelle.

Votre navigateur charge alors les images directement depuis le site de la source, et seulement depuis les sites
listés dans « Sites d'images autorisés » (par défaut `kokusho.nijl.ac.jp` et `dl.ndl.go.jp`). J-ed ne copie pas
les images. Les mentions demandées par la source (attribution, licence) s'affichent sous l'image.

## Comprendre les trois statuts

Notice disponible, document consultable, IIIF : trois questions différentes.

Une notice bibliographique n'est pas le document lui-même. J-ed pose donc trois questions séparées, et aucune
réponse ne se déduit d'une autre.

| Statut | Question | Valeurs |
| --- | --- | --- |
| **Notice disponible** | Les métadonnées sont-elles consultables ? | oui · non · non vérifié |
| **Document consultable** | Les images ou le texte sont-ils accessibles en ligne, pour tous ? | oui · non · non vérifié |
| **IIIF** | Un manifeste IIIF est-il connu, et a-t-il été contrôlé ? | absent · identifié · vérifié · vérification en échec · non vérifié |

Chaque statut indique son **origine** (déclaré par la source, vérifié par J-ed, ou déduit par J-ed quand il
construit lui-même l'adresse d'un manifeste), sa **date** et l'adresse concernée.

Les statuts sont calculés à partir des données enregistrées, sans interroger Internet.

### Cas particuliers

- **Consultation sur place** : un document numérisé mais réservé (dans les salles d'une bibliothèque) est
  « non consultable ». La fiche le mentionne, pour ne pas faire croire qu'il n'existe pas de numérisation.
- **IIIF identifié** : une adresse de manifeste figure dans les données de la source, mais J-ed ne l'a pas encore
  ouverte. **Vérifier le IIIF** (sur la fiche) l'ouvre et passe le statut à « vérifié » ou « vérification en échec ».

Dans la Bibliothèque, vous pouvez filtrer les notices selon ces statuts.

Voir aussi le [Lexique](#lexique) (IIIF, manifeste).

### Documents de la NDL : accès libre ou réservé

La NDL numérise des millions de documents, mais beaucoup ne sont consultables qu'en bibliothèque, par le service
d'envoi aux particuliers inscrits, ou sur place. Sur la fiche d'un document numérisé de la NDL,
**Vérifier le manifeste IIIF** permet de savoir s'il est en accès libre :

- **Document : oui** (vérifié par J-ed) : la NDL publie ses images sur Internet ; « Voir les images dans J-ed »
  fonctionne si la visionneuse intégrée est activée ;
- **Document : non vérifié**, avec la mention « accès réservé probable » : la NDL ne publie pas ses images ; la
  page du document (« Ouvrir dans la NDL Digital Collections ») indique les conditions exactes.

Ce n'est pas un dysfonctionnement : rien n'est ajouté au journal.

## Les sources documentaires

Les catalogues interrogés par J-ed, leurs capacités et leur état.

Menu **Sources** : la liste des catalogues que J-ed sait interroger. Les principaux :

| Source | Contenu |
| --- | --- |
| **Base locale** | Les notices déjà gardées dans J-ed |
| **NDL Search** (国立国会図書館サーチ) | Bibliothèque nationale de la Diète et bibliothèques partenaires |
| **CiNii Research** (国立情報学研究所) | Articles, livres et thèses des universités ; demande un identifiant gratuit, personnel |
| **Kokusho Database** (国書データベース) | Livres anciens japonais (Institut national de littérature japonaise) |
| **Japan Search** | Portail national ; chacune de ses bases peut être ajoutée comme source à part |
| **Archives nationales du Japon** (国立公文書館) | Archives publiques, interrogées par la base « najda » de Japan Search |
| **Waseda Kotenseki Sōgō Database** (古典籍総合データベース) | Livres anciens de l'université Waseda, interrogés par NDL Search ; « Ouvrir sur le site de Waseda » mène à l'ouvrage |
| **Aozora Bunko** (青空文庫) | Textes du domaine public : liste des œuvres importée, texte intégral téléchargé à la demande ([Aozora Bunko](#aozora-bunko)) |

### La fiche d'une source

Elle indique ce que la source sait faire (recherche par auteur, par date, IIIF…), son état et le résultat du
dernier essai. **Tester** lance une recherche d'essai. Un connecteur n'est présenté comme opérationnel qu'après un
essai réel réussi.

D'autres institutions (Nichibunken, Tōyō Bunko, Iwase Bunko, Ritsumeikan ARC, Historiographical Institute de
l'université de Tokyo…) n'offrent pas de recherche que J-ed puisse interroger : leurs fiches les présentent « à
étudier » ou « import de fichiers », et la recherche ne les interroge pas.

**Tester** interroge toujours la source elle-même, jamais une réponse gardée en mémoire : le temps affiché est
celui de la vraie réponse.

**Japan Search → bases** : la liste des bases du portail, à ajouter une par une comme sources.
Une source qui passe par Japan Search doit avoir sa base choisie : sans elle, J-ed refuse de l'interroger,
car elle renverrait tout le portail.

**Waseda, installée avant la 2.0.0.** Sa source passe encore par Japan Search et l'essai la refuse. Ouvrez sa
fiche → **Configuration** → Connecteur « Waseda Kotenseki (via NDL Search) » → **Enregistrer**, puis **Tester**.
La mise à jour ne change pas ce réglage d'elle-même : vos sources restent telles que vous les avez réglées.

### Mettre à jour les notices

L'administrateur peut resynchroniser une source, importer un fichier et décider des notices modifiées : voir
[Mises à jour et imports](#mises-a-jour-et-imports).

## Aozora Bunko et les textes intégraux

Importer la liste des œuvres d'Aozora Bunko, lire un texte avec ses furigana, l'envoyer vers un projet de traduction.

[Aozora Bunko](https://www.aozora.gr.jp/) (青空文庫) publie le texte intégral de plus de 17 000 œuvres
japonaises, surtout modernes (de l'ère Meiji à l'ère Shōwa). La plupart sont dans le domaine public.

### Importer la liste des œuvres (une fois, puis de temps en temps)

1. **Mises à jour** → ligne **Aozora Bunko** → **Synchroniser** (synchronisation complète).
2. J-ed télécharge la liste officielle des œuvres (environ 2 Mo). Il prépare une notice par œuvre, en quelques
   dizaines de secondes.
3. Ouvrez la synchronisation, vérifiez, puis **Intégrer les éléments acceptés**. Avec 17 000 notices,
   l'intégration se fait en tâche de fond (quelques minutes). Si l'ordinateur est éteint entre-temps, rien n'est
   perdu : **Reprendre** continue là où elle s'était arrêtée.

Ensuite, Aozora Bunko se cherche comme les autres sources, sans requête au site à chaque recherche.

### Lire un texte

Sur la fiche d'une œuvre : **Texte intégral** → **Télécharger le texte**. J-ed récupère un seul fichier, le
fichier texte compressé publié par Aozora Bunko, ou à défaut sa page XHTML. Rien n'est téléchargé sans ce clic.

Le texte s'affiche avec ses lectures (furigana). Un caractère absent des jeux de caractères courants est marqué
※ : survolez-le pour voir sa description. Le bas de la page reprend le texte source utilisé par Aozora Bunko
(底本), avec les noms des personnes qui ont saisi et relu le texte.

### Traduire un texte

**Envoyer au projet** ajoute le texte à un [projet de traduction](#projets-de-traduction). Le texte est envoyé
seul, sans furigana ni notes de mise en forme. Gardez la mention « texte d'Aozora Bunko » et celle du texte source
si vous diffusez la traduction.

### Droits

Le bandeau « Droits » de la page dit si l'œuvre est dans le domaine public ou protégée. Une œuvre protégée est
publiée avec l'accord des ayants droit : vous pouvez la lire librement ; pour tout autre usage, voyez les
conditions de l'œuvre. La liste des œuvres est sous licence CC BY.

# Bibliothèque et exports

## La Bibliothèque

Vos notices gardées : filtrer, étiqueter, traduire, résumer, exporter.

Menu **Bibliothèque** : toutes les notices que vous avez intégrées depuis une recherche ou un import.

### Filtrer et trier

À gauche : texte, étiquette (tag), état de vérification, période, source, favoris, **doublons potentiels à
examiner**, et les [trois statuts](#trois-statuts). Tri par ajout, titre, date, source, collecte ou statut.

### Agir sur plusieurs notices

Cochez des notices (ou **Tout cocher**), puis choisissez :

| Action | Effet |
| --- | --- |
| **Ajouter au dossier**, **Taguer** | Ranger les notices |
| **Exporter** | Préparer un export de la sélection : [Exporter](#exporter) |
| **Traduire maintenant**, **File de nuit**, **Traduire…** | Voir [Traduire une notice](#traduire-une-notice) |
| **Résumer**, **Résumer la nuit** | Voir [Résumés IA](#resumes-ia) |
| **Vérifier IIIF** | Ouvre et contrôle le manifeste IIIF de chaque notice cochée qui en a un |
| Fonctions IA : **Détecter les doublons**, **Classifier**, **Comparer**, **Extraire les entités** | Propositions de l'IA, à valider une par une ; coût affiché avant envoi |
| **Retirer** | Retire de votre bibliothèque ; la notice reste dans J-ed |

Les actions de traduction, de résumé et les fonctions IA sont réservées aux chercheurs et à l'administrateur.

**Doublons** : J-ed propose des doublons possibles, il ne fusionne jamais seul. C'est vous qui décidez.

## Les dossiers

Regrouper des notices par sujet, les organiser, les partager.

Menu **Dossiers** : un dossier réunit des notices autour d'un sujet, d'un article, d'une exposition.

### Organiser

- **Nouveau dossier** : un titre, une description.
- **Sous-sections** : découpez le dossier (par exemple par période ou par fonds). Chaque notice peut être placée
  dans une sous-section et recevoir un commentaire.
- **Notes sur le dossier** : note privée, note partagée, ou commentaire éditorial. Elles figurent dans les exports
  si l'option « Inclure les notes et annotations » est cochée.
- **Méthodologie** : décrivez vos choix ; elle figure en tête des exports du dossier.

### Partager

**Partage** : choisissez un utilisateur de J-ed ; cochez « Autoriser la modification » s'il peut aussi ajouter ou
retirer des notices. Le partage se retire à tout moment.

### Exporter

Le bouton d'export prépare un document (Word, PDF, site HTML…) à partir du dossier, sous-sections comprises : voir
[Exporter](#exporter).

## Exporter

Bibliographies, inventaires, dossiers : Word, PDF, texte, JSON, CSV, site HTML.

Un export part d'une sélection de notices, d'un dossier ou de toute la Bibliothèque.

### Préparer

1. **Modèle** : bibliographie, inventaire complet, dossier historique, synthèse, import bibliographique,
   documentation HTML.
2. **Format** : Word (DOCX), PDF, texte, JSON, CSV, site HTML autonome (ZIP), archive complète (ZIP).
3. **Options** : champs à inclure, en-têtes, table des matières, images, profil de colonnes et séparateur pour le CSV.
4. **Contenus générés** : les contenus produits par une IA ne figurent que si vous cochez la case. Les **résumés IA**
   ont leur propre case, décochée par défaut ; ils sont toujours marqués « généré par IA ».
5. **Aperçu**, puis **Exporter**.

Vous pouvez enregistrer vos choix comme **profil** pour les réutiliser.

### Retrouver ses exports

Menu à votre nom → **Mes exports** : chaque export, ses fichiers à télécharger, et **Régénérer** pour le refaire
avec les notices à jour.

Les PDF incorporent une police japonaise : les titres en japonais s'affichent sur tout ordinateur.

# Traduire et résumer

## Choisir un moteur de traduction

DeepL, Argos hors ligne, IA en ligne ou IA locale : ce qui convient à chaque cas.

Traduction → **Moteurs** : vous choisissez un **moteur par défaut** et, si vous voulez, un **deuxième moteur**.
Le deuxième moteur n'est jamais utilisé d'office : il vous est seulement proposé quand une tâche échoue.

| Moteur | Où le texte est traité | Coût | Bon pour |
| --- | --- | --- | --- |
| **Argos Translate** | Sur votre ordinateur | Gratuit | Premier jet, textes confidentiels, gros volumes la nuit ; passe par l'anglais (japonais → anglais → français) |
| **DeepL** | Service en ligne (clé personnelle) | Selon votre offre (gratuite limitée, ou payante) | Japonais moderne, bonne qualité courante |
| **Google Traduction** (Basic) | Service en ligne (clé personnelle) | Au caractère | Alternative à DeepL |
| **IA en ligne** (OpenAI, Anthropic, Gemini…) | Service en ligne (clé personnelle) | Au nombre de mots envoyés et reçus | Textes difficiles, contexte, japonais ancien |
| **IA locale** (Ollama) | Sur votre ordinateur | Gratuit | Résumés, essais ; plus lente et moins précise qu'une IA en ligne |

Argos et l'IA locale s'installent dans **Moteurs locaux** : voir [Argos et IA locale](#moteurs-locaux).

### Clés et conditions

- Chaque clé est **personnelle**, enregistrée chiffrée, jamais affichée en entier. **Tester** vérifie la clé et lit
  le quota restant quand le service le permet.
- La première fois qu'un texte part vers un service, J-ed résume ses **conditions d'utilisation des textes envoyés**
  (conservation, usage pour l'entraînement) et vous demande d'en prendre connaissance.
- **Projets confidentiels** : seuls les moteurs qui travaillent sur votre ordinateur sont permis.

### Réglages utiles sur la même page

- **Seconde confirmation** au-delà d'un nombre de caractères (20 000 par défaut).
- **File de nuit** et **« Traduire maintenant » sans confirmation** sous un montant : voir
  [Tâches et file de nuit](#taches-et-file-de-nuit).
- **Résumés IA** : voir [Résumés IA](#resumes-ia).
- **Japonais ancien** : voir [Le japonais ancien](#japonais-ancien).

### Comparer des moteurs

Traduction → **Évaluation** : faites traduire les mêmes passages par plusieurs moteurs, puis comparez et notez les
résultats côte à côte, avant de choisir votre moteur par défaut.

## Traduire une notice

Traduire le titre et la description d'une ou plusieurs notices, puis valider.

### Lancer

- Depuis une **fiche** : **Traduire maintenant**, ou la page **Traductions** de la notice.
- Depuis la **Bibliothèque**, sur plusieurs notices cochées : **Traduire maintenant**, **File de nuit**, ou
  **Traduire…** pour choisir les champs et le moteur.

J-ed prépare une **tâche** et affiche, avant tout envoi : le moteur, le nombre de caractères, le coût estimé et les
conditions du service. Rien ne part avant **Confirmer** (sauf en dessous du seuil que vous avez fixé pour
« Traduire maintenant »).

Champs traduits : titre et description ; le sujet et le lieu si vous l'avez demandé dans **Moteurs**.

### Valider

Une traduction automatique reste une **proposition**, marquée comme telle, jusqu'à sa validation. Les notices sont
communes à tous les utilisateurs : leur validation est **réservée à l'administrateur**.

- **Valider et adopter** : la proposition devient la traduction affichée sur la fiche ; la traduction validée
  précédente du même champ redevient une proposition ;
- **Rejeter**, ou **Nouvelle traduction** avec un autre moteur ;
- **Tout valider et adopter** pour toutes les propositions d'une notice.

L'administrateur peut aussi écrire ou corriger la traduction lui-même. Pour un texte à vous, utilisez plutôt un
[projet de traduction](#projets-de-traduction), que vous validez vous-même.

### Retrouver ses traductions

Traduction → **Traductions effectuées** : toutes les notices et documents traduits, filtrables par moteur, date et
état de validation.

Voir aussi [Tâches et file de nuit](#taches-et-file-de-nuit) et [Le japonais ancien](#japonais-ancien).

## Traduire un document

Projets, documents découpés en segments, atelier de traduction, export bilingue.

Pour un texte long (une préface, un chapitre, un document d'archives), créez un **projet de traduction**.

### Préparer

1. Traduction → **Projets** → **Nouveau projet**. Cochez **confidentiel** si le texte ne doit jamais quitter votre
   ordinateur : seuls Argos et l'IA locale seront permis.
2. **Ajouter un document** : collez le texte japonais, ou choisissez un fichier .txt, .docx ou .pdf (avec du texte,
   pas une image). Indiquez sa variété de langue (moderne, classique, kanbun). J-ed le découpe en **segments**
   (phrases ou paragraphes).
3. Rattachez au besoin un ou plusieurs **glossaires** au projet.

### L'atelier

L'atelier affiche l'original et la traduction, segment par segment.

- **Traduire…** : tout le document ou les segments choisis, avec le moteur choisi ; confirmation avant envoi.
- Chaque segment peut être corrigé à la main, validé (par le propriétaire du projet), ou retraduit. Les versions
  successives sont gardées.
- Les segments déjà traduits ailleurs sont retrouvés dans la **mémoire de traduction**.
- **Valider les dernières propositions** valide d'un coup ce qui vous convient.
- **Publier dans la notice** : la traduction validée devient celle de la notice d'origine.
- **Résumer** : voir [Résumés IA](#resumes-ia).

### Exporter

Traduction → **Exports** ou le projet : texte bilingue ou traduction seule, en texte, Markdown, tableau CSV ou Word
bilingue en tableau. Au choix : les versions validées seulement, ou à défaut la dernière proposition, signalée
« non validée ».

Voir aussi [Glossaires et mémoire](#glossaires-et-memoire).

## Glossaires et mémoire de traduction

Imposer vos traductions de termes, et réutiliser ce qui a déjà été traduit.

### Glossaires

Un glossaire associe un terme japonais à sa traduction (noms propres, titres d'œuvres, termes techniques).

- Traduction → **Glossaires** → **Nouveau** : ajoutez des entrées une à une, ou **importez un fichier CSV**
  (« Vérifier le fichier » montre ce qui serait importé, sans rien enregistrer).
- Rattachez le glossaire à un projet. Dans l'atelier, les termes trouvés dans l'original sont signalés.
- **DeepL** : le glossaire peut être envoyé à DeepL, qui l'applique pendant la traduction. La copie DeepL se
  renvoie après modification et se supprime à tout moment.
- Avec une IA, les termes du glossaire sont joints à la consigne.

### Mémoire de traduction

Chaque segment validé entre dans la **mémoire**. Quand le même texte revient, J-ed reprend la traduction déjà
validée comme **proposition**, sans l'envoyer à un moteur (ni coût ni attente) ; vous la validez comme les autres. Traduction → **Mémoire** : **Exclure** une entrée fausse,
**Réintégrer** une entrée exclue.

## Tâches, file de nuit et programmation

Suivre, programmer, mettre en pause et reprendre les traductions et les résumés.

Chaque traduction (même d'un seul champ) et chaque demande de résumés est une **tâche**. Menu à votre nom →
**Tâches**, ou Traduction → Tâches.

### Les états d'une tâche

| État | Signification |
| --- | --- |
| **Préparée** | Rien n'est parti : à confirmer ou à annuler |
| **Confirmée**, **En cours** | En file ou en train de travailler |
| **Planifiée** | Partira à l'heure choisie, ou dans la file de nuit |
| **En pause** | Arrêtée par vous, par un plafond atteint, ou par la fin de la plage de nuit |
| **En retard — à confirmer** | Son heure est passée pendant que J-ed était arrêté : elle attend votre accord |
| **Interrompue** | Arrêtée par une panne (service injoignable, ordinateur éteint) : **Reprendre** |
| **Terminée**, **Terminée avec erreurs**, **Échec**, **Annulée** | Fin de la tâche, avec son compte rendu |

Une tâche reprise **ne renvoie jamais** ce qui a déjà été traduit ou résumé : elle continue là où elle s'était
arrêtée. **Relancer les échecs** ne reprend que les éléments en échec.

### Quand faire partir une tâche

À la confirmation, vous choisissez :

- **Maintenant** : tout de suite ;
- **À une heure précise** : la tâche est planifiée ;
- **File de nuit** : elle partira pendant votre plage de nuit, l'une après l'autre.

Pour une traduction de notices ou de documents, la case **Résumer aussi** enchaîne les résumés, juste après chaque
traduction ou après l'ensemble des traductions. Voir [Résumés IA](#resumes-ia).

### La file de nuit

Réglez votre **plage de nuit** dans Traduction → Moteurs (par exemple de 23 h à 6 h). Il n'y a pas de plage par
défaut : sans réglage, le choix « File de nuit » reste grisé.

- L'ordinateur doit rester **allumé, sans mise en veille**, avec Docker Desktop démarré. Éteint, rien n'avance.
- À la fin de la plage, une tâche inachevée se met **en pause** ; elle reprend la nuit suivante.
- Si la plage a commencé alors que J-ed était arrêté, J-ed ne lance rien sans vous **redemander confirmation**.
- Le matin, une notification résume la nuit : ce qui est terminé, en pause, en erreur.
- Sur la page Tâches, les flèches **Monter** et **Descendre** changent l'ordre de la file.
- Une tâche en pause, en retard ou interrompue peut être **remise dans la file de nuit**.

### Coût et confirmation

Le coût estimé est affiché avant tout envoi à un service payant. Vous pouvez fixer, dans **Moteurs** :

- un montant en dessous duquel « Traduire maintenant » part sans confirmation (vide par défaut : toujours confirmer ;
  Argos ne demande jamais, il est gratuit) ;
- une **seconde confirmation** au-delà d'un nombre de caractères.

Les plafonds mensuels sont décrits dans [Consommation et plafonds](#consommation-et-plafonds).

## Résumés IA

Résumé court, détaillé ou fiche d'analyse, toujours dans votre langue.

Un résumé IA aide à savoir de quoi parle un document avant de le lire ou de le traduire. Il est toujours marqué
**« généré par IA »** : c'est une aide, pas une source.

### Trois types

| Type | Contenu |
| --- | --- |
| **Résumé court** | 3 à 5 phrases |
| **Résumé détaillé** | Plusieurs paragraphes, dans l'ordre du texte |
| **Fiche d'analyse** | Résumé, puis thèmes, personnes, lieux et dates repérés, et les limites du résumé |

Le résumé est rédigé dans **votre langue** (français par défaut ; anglais ou japonais sur demande), à partir de
l'**original japonais**. S'il est fait d'après une traduction non validée, il le signale.

### Demander un résumé

- Sur la **fiche** d'une notice : **Résumer maintenant**, ou le bouton lune pour la nuit.
- Dans la **Bibliothèque** : **Résumer**, **Résumer la nuit** sur les notices cochées.
- Dans l'**atelier** d'un document : **Résumer**.
- À la confirmation d'une traduction : **Résumer aussi**.

Comme une traduction, c'est une [tâche](#taches-et-file-de-nuit) : nombre d'appels et coût estimé affichés,
confirmation, file de nuit, pause et reprise. Un texte long est découpé en parties, chacune résumée, puis une
synthèse donne le résumé final.

**Résumer après la traduction** : « juste après chaque traduction », ou « après l'ensemble des traductions ». La
nuit, si Argos et l'IA locale devraient travailler en même temps, J-ed choisit « après l'ensemble » : ils ne
tiennent pas toujours ensemble en mémoire.

### Quelle IA

Traduction → Moteurs → **Résumés IA** : le fournisseur et le modèle, le type et la langue par défaut.

- Une **IA en ligne** donne les meilleurs résumés ; chaque appel a un coût.
- L'**IA locale** est gratuite et rien ne quitte l'ordinateur, mais elle est plus lente. C'est la seule permise
  pour un **projet confidentiel**. Voir [Argos et IA locale](#moteurs-locaux).

### Retrouver ses résumés

Traduction → **Résumés IA** : la liste de vos résumés. Chaque nouvelle demande crée une **nouvelle version** ; les
précédentes restent consultables. Dans un export, les résumés n'apparaissent que si vous cochez la case
« Inclure les résumés IA ».

## Le japonais ancien dans J-ed

Repérage du bungo, du kanbun et du sōrōbun, et moteur choisi pour eux.

Beaucoup de notices et de documents anciens sont écrits en **japonais classique** (bungo 文語), en **kanbun** (漢文,
chinois classique lu à la japonaise) ou en **sōrōbun** (候文, style épistolaire). Un moteur prévu pour le japonais
moderne les traduit mal.

### Le repérage

J-ed repère les textes **probablement** anciens, d'après des indices : signes de lecture du kanbun, texte presque
sans kana, formes classiques (けり, べし, なり, anciens kana…), style en 候.

- Sur la **fiche** d'une notice, un bandeau indique par exemple « Japonais classique (bungo) — probable », avec ses
  indices. **Confirmez**, ou corrigez la variété.
- Dans l'**atelier** d'un document, une suggestion apparaît si le document est encore noté « moderne ».

Le repérage n'est qu'une suggestion : votre choix l'emporte toujours, et un nouveau repérage ne le remplace jamais.
Le repérage se trompe parfois sur des textes courts ou mixtes : vérifiez.

### Choisir un moteur pour le japonais ancien

Traduction → Moteurs → **Japonais ancien** : le moteur à utiliser pour ces textes, par exemple une IA en ligne,
et l'IA de leurs résumés.

Quand une demande mélange textes modernes et anciens, elle est présentée **en deux parties**, chacune avec son
moteur, son nombre de caractères et son coût. Les deux parties partent ensemble, ou aucune. J-ed ne change jamais
de moteur sans l'afficher avant l'envoi.

Sans réglage, tous les textes vont au moteur habituel. La variété est quand même transmise à l'IA de traduction et
de résumé, qui sait alors à quel type de texte elle a affaire.

Conseils pour obtenir de bonnes traductions : [Japonais ancien : bonnes pratiques avec une IA](#japonais-ancien-bonnes-pratiques).

## Japonais ancien : bonnes pratiques avec une IA

Traduire du kobun ou du japonais d'Edo avec une IA, de façon fiable.

Le japonais ancien, du kobun de l'époque de Heian au japonais pré-moderne de l'époque d'Edo, pose des difficultés
majeures :

- le sujet est souvent omis ;
- les particules ont plusieurs sens ;
- le vocabulaire est désuet ;
- l'écriture peut être cursive (kuzushiji くずし字) ou utiliser des kanji historiques.

Pour obtenir un résultat fiable, suivez ces trois règles.

### 1. Ne pas traduire d'un seul coup

Ne demandez pas directement la traduction en français (ou dans une autre langue). Procédez en trois étapes :

1. **Japonais moderne d'abord.** Demandez à l'IA de transcrire le texte en japonais moderne (gendai-go yaku
   現代語訳).
2. **Analyse.** Faites-lui détailler la grammaire, les formes verbales classiques et le sens des mots rares. Par
   exemple : « Décompose ce texte phrase par phrase en indiquant les formes en ren'yōkei, les auxiliaires de
   l'époque et le sujet implicite. »
3. **Traduction.** Faites traduire enfin ce japonais moderne vers votre langue.

### 2. Une consigne rigoureuse

- Précisez l'**époque** exacte du texte : Heian, Sengoku, Edo…
- **Interdisez** explicitement de résumer ou de couper des passages.
- Demandez de **lister les doutes et les ambiguïtés** plutôt que de deviner.

### 3. Toujours vérifier

Les IA génératives n'ont pas de conscience historique. Elles peuvent inventer des sens (« hallucinations »).
Croisez leurs analyses avec des dictionnaires de japonais classique (kogo jiten 古語辞典, dictionnaires de kobun en
ligne) ou avec le Kōjien (広辞苑), qui couvre aussi la langue classique. Soumettez les passages délicats à des
spécialistes ou à des forums spécialisés.

### Dans J-ed aujourd'hui

- J-ed signale la **variété** du texte (bungo, kanbun, sōrōbun) dans la consigne envoyée à l'IA, et vous pouvez
  choisir une IA dédiée au japonais ancien : voir [Le japonais ancien dans J-ed](#japonais-ancien).
- La traduction se fait encore **en une étape**. Pour un passage important, vous pouvez suivre les trois étapes
  ci-dessus avec votre IA, puis saisir ou corriger la traduction dans l'[atelier](#projets-de-traduction).
- Toute traduction automatique reste une proposition « non validée » tant que vous ne l'avez pas relue.

## Consommation et plafonds

Ce que vous avez envoyé ce mois-ci, et les limites que J-ed ne dépasse pas.

Traduction → **Consommation** : vos envois aux moteurs, par moteur et par mois, avec le coût estimé. Les montants
sont des estimations ; la facture du fournisseur fait foi.

### Les plafonds

| Plafond | Où le régler | Ce qu'il limite |
| --- | --- | --- |
| **Plafond mensuel de caractères** | Traduction → Moteurs, pour chaque service (DeepL…) | Les caractères envoyés à ce service dans le mois |
| **Plafond mensuel estimé (USD)** | Préférences IA, dans votre profil | Le coût estimé des appels aux IA en ligne dans le mois (traductions, résumés, fonctions IA) |

- Une demande qui **dépasserait** un plafond n'est pas confirmée : J-ed dit lequel et de combien.
- Une tâche en cours qui **atteint** un plafond se met **en pause**. Elle ne passe jamais à un autre moteur toute
  seule. Vous la reprenez le mois suivant, ou après avoir relevé le plafond.
- Argos et l'IA locale sont gratuits : aucun plafond ne les concerne.

Voir aussi [Tâches et file de nuit](#taches-et-file-de-nuit).

## Les fonctions IA et vos clés

Fournisseurs, clés personnelles, fonctions proposées et historique.

J-ed fonctionne entièrement **sans IA**. Activer une fonction la rend seulement disponible : aucun traitement ne
part sans votre action.

### Vos clés

IA → **Fournisseurs** (menu à votre nom → Préférences IA) : saisissez votre propre **clé API** (OpenAI, Anthropic,
Gemini, ou un service compatible OpenAI). J-ed ne demande jamais le mot de passe de votre compte ChatGPT, Claude ou
Google. Les clés sont chiffrées ; elles ne sont jamais affichées en entier ni exportées.

L'IA locale n'a pas de clé : elle se gère dans [Argos et IA locale](#moteurs-locaux).

### Préférences IA

- **Fournisseur et modèle par défaut**, et au besoin un fournisseur différent pour une fonction.
- **Fonctions proposées dans l'interface** : résumé documentaire, classification historique, détection des
  doublons, extension de recherche (variantes), extraction d'entités, question-réponse sur le fonds local,
  comparaison de notices.
- **Plafond mensuel estimé** : voir [Consommation et plafonds](#consommation-et-plafonds).

Le choix du modèle se fait dans la **liste des modèles du fournisseur** (« Actualiser la liste »), ou en saisissant
son nom.

### Ce que produit une IA

Tout résultat d'une IA est **étiqueté IA** et reste une **proposition** à valider : classification, entités,
doublons, traductions, résumés. Rien ne remplace les données de la source.

IA → **Historique** : chaque appel, avec le fournisseur, le modèle, les jetons envoyés et reçus, et le coût estimé.

## Argos et IA locale

Les deux moteurs gratuits qui travaillent sur votre ordinateur.

Traduction → **Moteurs locaux**. Les installations sont faites par l'administrateur ; chacun peut consulter l'état.

### Argos Translate (traduction)

Argos fait partie de l'installation standard. Il traduit sans Internet, gratuitement.

#### Une traduction en deux temps, par l'anglais

Argos ne traduit **pas directement** du japonais au français. Il fait deux traductions à la suite :

1. du **japonais vers l'anglais** (paquet ja → en) ;
2. puis de **l'anglais vers le français** (paquet en → fr).

Vous ne voyez que le résultat français. Les conséquences :

- **les erreurs s'additionnent** : une ambiguïté mal résolue en anglais est reprise, parfois aggravée, en français ;
- **les noms propres et les titres anciens** sont souvent pris pour des mots ordinaires, puis traduits. Exemple
  constaté : le titre 今様源氏小倉百人一首 devient « M. Yuichi Kokura » ; un nom de collection (九曜文庫) devient un
  nombre ; un nom de lieu devient un mot courant ;
- Argos **n'utilise pas les glossaires**.

À retenir : lisez toujours l'original à côté ; rejetez les propositions manifestement fausses (bouton
**Rejeter**) ; pour un titre, un nom ou un texte important, préférez DeepL ou une IA quand vous êtes en ligne. Si
vous lisez l'anglais, l'étape anglaise est souvent plus fidèle que le français final : une traduction vers
l'anglais seul est envisagée dans une prochaine version.

- **Installer la traduction japonais → français** : récupère les paquets de langues (environ 200 Mo, une seule
  fois), après confirmation.
- **Traduction d'essai Argos** (page « État de l'installation ») : vérifie qu'Argos répond. Elle est aussi faite
  automatiquement deux minutes après une installation ou une mise à jour.
- Qualité : un bon premier jet, à relire. Conseillé pour la file de nuit et les projets confidentiels.

### IA locale (Ollama) : facultative

Une IA qui tourne sur votre ordinateur : gratuite, et rien ne quitte l'ordinateur. Elle fait les **résumés IA**
et, si vous la choisissez, des traductions par IA. Plus lente qu'une IA en ligne, et de qualité moindre.

**Installer le service** (administrateur) : dans le fichier `.env` de J-ed, la ligne `COMPOSE_PROFILES` doit
contenir `ollama` :

```
COMPOSE_PROFILES=argos,ollama
```

Une seule ligne `COMPOSE_PROFILES` dans tout le fichier : s'il y en a deux, seule la dernière compte (la
vérification `verifier-j-ed.ps1` le signale). Puis `docker compose up -d`.

**Choisir un modèle** : section « IA locale », la liste indique la taille de chaque modèle et la mémoire nécessaire.
Cochez « télécharger … depuis Internet », puis **Installer**. Le téléchargement est suivi (pourcentage) et reprend
s'il est coupé. À la fin, un **résumé d'essai** vérifie que tout marche.

Ensuite : Traduction → Moteurs → **Résumés IA** → « IA locale » et le modèle installé.

**Mémoire** : un modèle moyen occupe environ 4 Go pendant un résumé, puis quitte la mémoire après 5 minutes sans
demande. Argos et l'IA locale ne tiennent pas toujours ensemble en mémoire : J-ed évite de les faire travailler en
même temps la nuit.

# Administration

## Comptes et rôles

Créer des comptes, attribuer les rôles, supprimer les données personnelles.

Administration → **Comptes et rôles**.

- **Nouveau compte** : identifiant, nom affiché, mot de passe initial, **rôle** (lecteur, chercheur ou
  administrateur ; voir [Bien démarrer](#premiers-pas)).
- Un compte peut être **désactivé** (case « actif ») sans rien perdre. Vous ne pouvez pas retirer vos propres droits
  d'administration.
- **Supprimer les données personnelles** d'un compte : il est anonymisé et ses données privées sont supprimées ; les
  contenus communs restent. Ses projets et glossaires de traduction vous sont confiés ; ses clés de moteurs sont
  effacées. C'est refusé, sans rien modifier, s'il n'existe aucun autre administrateur actif.

**Ouvrir J-ed à d'autres personnes** : J-ed est prévu pour un usage sur votre ordinateur (adresse `127.0.0.1`).
Le rendre accessible sur un réseau suppose un hébergement sécurisé (HTTPS), à mettre en place par une personne
compétente.

Chaque clé d'IA ou de DeepL est **personnelle** : un chercheur saisit la sienne ; elle n'est jamais visible des
autres comptes, administrateur compris.

## État de l'installation et réglages

Vérifier que tout fonctionne, régler l'instance, adapter J-ed à l'ordinateur.

### La page « État de l'installation »

Administration → **État de l'installation** : un contrôle par ligne (version, base de données, Redis, workers,
planificateur, Argos, IA locale, sauvegardes…), chacun « Correct », « À surveiller », « Problème » ou
« Non vérifiable », avec le détail.

- **Traduction d'essai Argos** : vérifie Argos de bout en bout.
- **Diagnostic à transmettre** : un texte à copier pour signaler un problème. Il ne contient ni clé, ni nom de
  compte, ni texte de recherche ou de traduction ; les chemins personnels sont masqués.

Pour lire chaque ligne en détail, et pour le contrôle complet depuis Windows (`verifier-j-ed.ps1`), voir
[Vérifier l'installation](#verifier-l-installation).

### Profil de la machine

J-ed choisit au démarrage un profil selon la mémoire et les cœurs que Docker lui accorde :

| Profil | Pour |
| --- | --- |
| **Économe** | Petite machine : moins de travaux en parallèle |
| **Normal** | Cas courant |
| **Puissant** | Au moins 12 Go et 8 cœurs accordés à Docker |

La page « État » affiche le profil retenu et un conseil. Indiquez la **mémoire totale** de l'ordinateur pour que
le conseil soit juste. Pour imposer un profil : `JED_PROFIL=econome` (ou `normal`, `puissant`) dans `.env`, puis
`docker compose up -d`. Argos et l'IA locale peuvent aussi être limités (`ARGOS_COEURS`, `ARGOS_MEMOIRE_MAX`,
`OLLAMA_COEURS`, `OLLAMA_MEMOIRE_MAX`).

### Paramètres de l'instance

Administration → **Paramètres** : nom de l'installation, mode de recherche par défaut, durée de conservation des
sessions temporaires, sauvegardes automatiques, auteur et en-têtes des exports, **mode démonstration d'Argos**
(désactivé par défaut : chaque résultat porte alors la mention « Simulation »). Aucun secret n'y figure : les clés
et mots de passe restent dans `.env`.

### Journal des actions

Administration → **Journal des actions** : les actions sensibles (comptes, clés, envois aux services, sauvegardes,
téléchargements de modèles…), sans aucun secret.

## Sauvegardes et restauration

Sauvegarder, vérifier, copier hors de Docker, restaurer.

Administration → **Sauvegardes**. Une sauvegarde contient la base complète, les fichiers d'import, les archives, les
exports et un manifeste d'empreintes.

- **Créer une sauvegarde**, ou laisser faire la sauvegarde automatique (Paramètres).
- **Vérifier** : contrôle l'intégrité. Une sauvegarde non vérifiée n'est pas considérée comme fiable.
- **Copie hors de Docker** : avec `DOSSIER_SAUVEGARDES=C:\chemin\vers\sauvegardes` dans `.env`, chaque sauvegarde est
  copiée dans ce dossier de Windows. Le script de mise à jour le règle pour vous.
- J-ed ne supprime **jamais** ces copies : faites le ménage vous-même si la place manque.

### Restaurer

**Restaurer…** remplace la base actuelle par celle de la sauvegarde. Les fichiers de la sauvegarde sont ajoutés ou
remplacés ; les plus récents sont conservés. J-ed crée d'abord une **sauvegarde de sécurité**, puis demande de taper
`RESTAURER`. Tout ce qui a été saisi après la sauvegarde restaurée est perdu.

Le **guide d'installation** décrit aussi la restauration en ligne de commande, quand J-ed ne démarre plus.

## Dysfonctionnements

Le journal des problèmes rencontrés par J-ed, regroupés et suivis.

Menu à votre nom → **Dysfonctionnements**. Les problèmes sont enregistrés automatiquement : source injoignable,
réponse illisible, erreur de traitement, signalement d'un utilisateur. Une recherche sans résultat n'est pas un
dysfonctionnement.

- Les occurrences d'un **même problème** sont regroupées : une seule ligne, avec le nombre de fois et les dates.
- Chaque incident a une **gravité** (information, avertissement, erreur, critique) et un **statut** que vous faites
  évoluer : nouveau, à analyser, en cours de correction, corrigé, à vérifier, clôturé.
- Le compteur rouge du menu signale les nouveaux incidents de gravité Erreur ou Critique ; une fenêtre vous prévient,
  selon le seuil choisi dans vos [notifications](#notifications).
- **Analyse** : sur une période choisie, les erreurs récurrentes et les sources les plus instables.
- **Exporter** un incident ou la liste, pour le transmettre.

Le journal reste sur votre ordinateur : rien n'est envoyé à l'extérieur.

## Corrections proposées et corbeille

Valider les corrections des utilisateurs, restaurer une notice supprimée.

### Propositions de correction

Administration → **Propositions de correction**. Un utilisateur peut proposer de corriger une notice (un titre mal
lu, une date). Vous **acceptez** ou **rejetez**. Une correction porte sur la couche normalisée ou éditoriale : la
donnée de la source n'est jamais modifiée.

### Corbeille des notices

Administration → **Corbeille** : les notices retirées. La suppression est réversible : **Restaurer** remet la
notice en service.

## Mises à jour des sources et imports

Resynchroniser les sources, importer un fichier, décider des notices modifiées.

Sources → **Gestionnaire de mises à jour** (administrateur).

### Synchroniser une source

| Action | Effet |
| --- | --- |
| **Synchronisation incrémentale** | Ce qui a changé depuis la dernière fois |
| **Synchronisation complète** | Toute la source (long) |
| **Actualiser les notices connues** | Relit seulement les notices déjà présentes dans J-ed |
| **Tester le connecteur** | Une recherche d'essai |
| **Suspendre / Reprendre** | Arrête les synchronisations de cette source |

Une synchronisation ne remplace jamais une notice en silence. Chaque notice nouvelle ou modifiée vous est proposée :
vous **intégrez** ou vous écartez. L'ancienne version reste consultable sur la fiche.

### Importer un fichier

**Import → Nouveau** : un fichier CSV ou Excel (inventaire, liste de références). J-ed reconnaît les colonnes,
montre ce qu'il a compris, compare avec les notices existantes, puis attend votre décision. Des fichiers d'exemple
sont livrés dans `docs/exemples/`.

# Installation et mises à jour

## Mettre à jour J-ed

Passer à une nouvelle version sans rien perdre, avec le script de mise à jour.

Une mise à jour **garde toutes vos données** : notices, bibliothèque, projets, glossaires, comptes, clés, paquets
Argos et modèles de l'IA locale. Elle se fait en une commande, avec le script `mettre-a-jour.ps1`. Le **guide de
mise à jour** livré avec chaque version détaille chaque étape.

### Ce qu'il faut

- Docker Desktop démarré, et J-ed en marche (sa page s'ouvre dans le navigateur).
- Environ 5 Go d'espace disque libre.
- Les trois fichiers de la nouvelle version, dans le **dossier parent** de l'installation (par exemple `C:\J-ed`) :
  l'archive `.zip`, son empreinte `.zip.sha256`, et `mettre-a-jour.ps1`.
- Un accès Internet **pour Docker** : la nouvelle version est construite à partir d'éléments téléchargés (Docker Hub
  et bibliothèques Python).

#### Vérifier l'accès Internet de Docker avant de commencer

Le script arrête l'ancienne version **avant** de construire la nouvelle. Si Docker ne peut pas télécharger, J-ed
reste arrêté jusqu'au retour en arrière (plus bas). Vérifiez donc d'abord, dans PowerShell :

```
docker pull python:3.12-slim-bookworm
```

[Résultat attendu : l'image se télécharge, ou « Image is up to date ». Un message contenant « deadline exceeded » ou
« connecting to … » veut dire que Docker ne joint pas Internet : ne lancez pas la mise à jour.]

**Derrière un proxy** (réseau d'entreprise ou d'établissement), déclarez-le dans Docker Desktop : Settings →
Resources → Proxies → « Manual proxy configuration », la même adresse (par exemple `http://10.0.0.1:3128`) dans les
champs HTTP et HTTPS, et `localhost,127.0.0.1,db,redis,argos,ollama,web` dans le champ des exceptions, puis « Apply &
restart ». Docker Desktop ne sait pas lire un fichier de configuration automatique (PAC) : il faut l'adresse réelle du
proxy, que votre service informatique peut vous donner. Refaites ensuite la vérification ci-dessus.

### Toujours le script de la nouvelle version

Le script `mettre-a-jour.ps1` évolue avec J-ed. **À chaque mise à jour, remplacez celui du dossier parent** par celui
livré avec la nouvelle version (ou par celui du nouveau dossier, après la mise à jour). Un ancien script garde ses
anciens défauts. Par exemple, une version de novembre 2026 ajoutait une ligne `COMPOSE_PROFILES=hors-ligne` au
fichier `.env` à chaque passage.

Le script le signale lui-même : « Attention : ce script de mise à jour n'est pas celui de l'archive », puis un
rappel à la fin.

### La méthode

1. Récupérez les trois fichiers de la nouvelle version et placez-les dans le dossier parent de l'installation
   (ci-dessus).
2. Vérifiez que Docker Desktop est démarré et que J-ed s'ouvre dans le navigateur.
3. Lancez le script (commandes ci-dessous). Il vérifie l'archive, fait une **sauvegarde vérifiée** copiée dans votre
   dossier de sauvegardes, installe la nouvelle version dans un **nouveau dossier** (l'ancien n'est jamais modifié)
   et reprend votre `.env`. Il demande ensuite de taper `OUI` avant d'arrêter l'ancienne version et de démarrer la
   nouvelle.
4. Vérifiez la nouvelle version, puis gardez l'ancien dossier quelques semaines : il permet de revenir en arrière.

### Les commandes

Dans PowerShell (clic droit sur Démarrer → Terminal). L'exemple passe de la 2.0.0 à la 2.0.1 ; remplacez les
numéros et les chemins par les vôtres.

```
cd C:\J-ed
```

Puis :

```
powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.1.zip -Actuel C:\J-ed\japon-explorateur-2.0.0 -DossierSauvegardes C:\J-ed\sauvegardes
```

- `-Archive` : l'archive de la nouvelle version.
- `-Actuel` : le dossier de la version **actuellement installée** (celui qui contient `.env`). Si vous ne le
  retrouvez plus, la commande `docker compose ls` l'indique dans la colonne CONFIG FILES.
- `-DossierSauvegardes` : le dossier où copier la sauvegarde faite avant la mise à jour, en dehors des dossiers
  d'installation.
- `-Destination` (facultatif) : le nouveau dossier, si celui proposé par défaut (`C:\J-ed\japon-explorateur-2.0.1`)
  existe déjà.

[Résultat attendu, à la fin : « Mise à jour terminée : J-ed 2.0.1, http://localhost:8000 ».]

À la moindre anomalie, le script s'arrête avec un message qui commence par **ARRÊT** et dit quoi faire. Avant
l'étape `OUI`, l'installation actuelle n'a pas été touchée.

**Si l'arrêt survient après `OUI`** (par exemple « démarrage de la nouvelle version impossible »), l'ancienne version
est déjà arrêtée et J-ed ne répond plus. Vos données ne sont pas touchées. Suivez les lignes « Pour revenir en
arrière » affichées par le script : `docker compose down` dans le **nouveau** dossier, puis `docker compose up -d`
dans l'**ancien**. Gardez une copie du message d'erreur (copier-coller dans un fichier texte) avant de fermer la
fenêtre.

**Installation au nom protégé** (`japon-explorateur` ou `japon-explorateur-essai`) : son `.env` doit contenir
`AUTORISER_NOM_PROJET=` suivi du même nom, sinon le script s'arrête. Il n'ajoute jamais cette ligne de lui-même.

### Après la mise à jour

Ouvrez J-ed et rechargez la page avec **Ctrl + F5** : le pied de page indique la nouvelle version.

Vérifiez ensuite l'installation depuis le **nouveau** dossier :

```
cd C:\J-ed\japon-explorateur-2.0.1
```

Puis :

```
powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1
```

[Résultat attendu : aucune ligne « [Problème] ». Voir aussi [Vérifier l'installation](#verifier-l-installation).]

- En cas de souci : [Dépannage après une mise à jour](#depannage-apres-mise-a-jour).
- Pour essayer les nouveautés sans toucher à vos données : [Essayer J-ed](#essayer-j-ed), avec le jeu d'essai.

Gardez l'ancien dossier quelques semaines : il permet de revenir en arrière. La procédure de retour est dans le
guide de mise à jour.

## Vérifier l'installation

La page « État de l'installation » et le script verifier-j-ed.ps1 : lire leurs résultats.

Deux outils, à utiliser après chaque installation ou mise à jour, et dès qu'un doute apparaît.

### La page « État de l'installation »

Menu à votre nom → **Administration → État de l'installation**. Une ligne par élément :

| Ligne | Ce qui est contrôlé |
| --- | --- |
| Version, base de données | La version en service et des migrations à jour |
| Redis, workers, planificateur | Les tâches de fond peuvent tourner (le planificateur passe à « Correct » dans les 5 minutes) |
| Argos | Le service répond, ses paquets japonais → français sont installés, la dernière traduction d'essai |
| IA locale | Le service répond, les modèles installés, le dernier résumé d'essai (ligne absente si l'IA locale n'est pas installée) |
| Sauvegardes | La dernière sauvegarde et sa vérification |
| Clés, disque, ressources | La clé de chiffrement, la place libre, la mémoire et les cœurs accordés par Docker |
| Profil de la machine | Le profil retenu et un conseil |

Chaque ligne est **Correct**, **À surveiller**, **Problème** ou **Non vérifiable**, avec le détail.
**Copier le diagnostic** donne un texte à transmettre, sans clé, sans nom de compte et sans aucun texte de recherche
ou de traduction.

### Le script verifier-j-ed.ps1

Il contrôle tout depuis Windows, dans le dossier de l'installation :

```
cd C:\J-ed\japon-explorateur-2.0.0
```

Puis :

```
powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1
```

1. **Dossier et `.env`** : version, nom de l'installation, mots de passe renseignés, dossier des sauvegardes, lignes en
   double.
2. **Docker et conteneurs** : les conteneurs attendus sont en service (Argos, et l'IA locale si elle est prévue).
3. **Adresse** : les pages répondent.
4. **Fonctions de l'application** : chaque fonction est essayée avec des **données fictives**, sans modifier votre
   base.

| Repère | Signification |
| --- | --- |
| `[OK]` | Tout va bien |
| `[À surveiller]` | Fonctionne, mais un point mérite attention (le détail dit lequel) |
| `[Problème]` | À corriger : le détail dit quoi faire |
| `[Non vérifié]` | Contrôle non fait (option non demandée, élément facultatif absent) |

Un rapport `verification-j-ed-….txt` est enregistré dans le dossier parent. Il ne contient ni clé, ni nom de compte,
ni texte de recherche ou de traduction : vous pouvez le transmettre tel quel.

Options : `-AvecSources` (une recherche d'essai par source, sur Internet), `-AvecTests` (la suite de tests
automatiques, 3 à 10 minutes).

### Mesurer la rapidité

Si J-ed vous paraît lent, une commande mesure la recherche, la détection des doublons et les pages principales. Dans
PowerShell, depuis le dossier de J-ed :

```
docker compose exec web python manage.py mesurer_performances
```

Elle crée une **base temporaire** remplie de 50 000 notices fictives, mesure, puis supprime cette base (comptez
quelques minutes). Sur vos propres données, elle ne fait que des recherches en lecture seule. Le résultat donne,
pour chaque mesure, la durée en millisecondes et le nombre de requêtes à la base. Option `--notices 10000` pour un
essai plus court.

## Dépannage après une mise à jour

Les problèmes les plus courants après une mise à jour, et leur solution.

Commencez toujours par [Vérifier l'installation](#verifier-l-installation) : la page « État » et
`verifier-j-ed.ps1` disent le plus souvent ce qui ne va pas.

| Ce que vous voyez | Que faire |
| --- | --- |
| L'ancienne version, ou une page sans le nouveau logo | Rechargez avec **Ctrl + F5** : le navigateur garde une copie de l'interface |
| « J-ed ne répond pas » | Attendez une ou deux minutes (premier démarrage). Sinon, dans le dossier : `docker compose ps`, puis `docker compose logs --tail 200 web` |
| « Fichier .env : la ligne … figure 2 fois » | Gardez une seule ligne, mettez `#` devant les autres, puis `docker compose up -d`. Remplacez aussi votre `mettre-a-jour.ps1` par le plus récent : voir [Mettre à jour J-ed](#mettre-a-jour) |
| Argos « non démarré » | La ligne `COMPOSE_PROFILES` de `.env` doit contenir `argos` (par exemple `COMPOSE_PROFILES=argos` ou `argos,ollama`), puis `docker compose up -d` |
| IA locale « non installée » alors que vous l'utilisez | Même ligne : elle doit contenir `ollama`. Les modèles déjà téléchargés sont conservés |
| IA locale « Essai automatique en attente » | Normal dans les minutes qui suivent la mise à jour : J-ed refait l'essai environ 2 minutes après le démarrage. Rechargez la page ensuite |
| « Vérification dans l'application : réponse illisible » | Transmettez le rapport : les lignes « Cause », « Début » et « Erreur » permettent de trouver l'origine |
| Des tâches « En retard — à confirmer » | Normal : leur heure (ou la plage de nuit) est passée pendant l'arrêt. Ouvrez Tâches, puis confirmez, reprogrammez ou annulez |
| L'icône de l'application installée n'a pas changé | Désinstallez puis réinstallez l'application depuis le navigateur |
| Un message « ARRÊT » du script de mise à jour | Lisez la ligne qui suit : elle dit quoi faire. Avant l'étape 5, rien n'a été modifié |

### Revenir à la version précédente

Si la nouvelle version ne convient pas, suivez la section « Revenir à la version précédente » du **guide de mise à
jour**. L'ancien dossier n'a pas été modifié ; vos données sont dans Docker, et la sauvegarde faite avant la mise à
jour est dans votre dossier de sauvegardes.

### Demander de l'aide

Joignez le rapport de `verifier-j-ed.ps1` et le texte de **Copier le diagnostic** (page « État »). Aucun des deux ne
contient de données personnelles ni de texte de recherche.

## Essayer J-ed (jeu d'essai et procédure de test)

Un jeu de données fictives et une procédure pas à pas, pour découvrir J-ed ou vérifier une nouvelle version.

Cette procédure sert dans deux cas :

- **vous découvrez J-ed** : elle fait le tour des fonctions principales en une demi-heure environ ;
- **vous venez d'installer ou de mettre à jour J-ed** : elle vérifie que tout fonctionne, sans toucher à vos vraies
  données.

Elle s'appuie sur un **jeu d'essai** : des notices, un dossier et un projet de traduction **entièrement
inventés**. Vous les retirez en un clic à la fin.

> Pour une installation d'essai à côté de votre installation principale, utilisez un autre dossier, un autre nom
> d'installation (`COMPOSE_PROJECT_NAME`) et un autre port (`WEB_PORT`) dans le fichier `.env` : voir le guide
> d'installation, étape 3.1.

### Avant de commencer

1. Lancez la vérification automatique : dans PowerShell, depuis le dossier de J-ed,
   `powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1`.
   Attendu : un rapport dont le bilan indique **0 problème** (voir [Vérifier l'installation](#verifier-l-installation)).
2. Ouvrez **Administration → Jeu d'essai** → **Charger le jeu d'essai**.
   Attendu : le message « Jeu d'essai chargé : 38 notices fictives… ».

### Partie A — sans Internet (20 minutes)

Chaque étape indique entre crochets le **résultat attendu**. Une étape qui ne donne pas ce résultat est à signaler,
avec une capture d'écran si possible.

1. **Recherche locale.** Rechercher → tapez `架空`, source **Base locale** cochée.
   [23 notices du jeu d'essai (titre, auteur 架空太郎 ou fonds 架空文庫), dont 架空物語集 et 架空絵巻, chacune une
   seule fois ; « 4 déjà enregistré(s) » : celles qui sont déjà dans la bibliothèque. Vos propres notices contenant
   架空 s'y ajoutent, le cas échéant.]
2. **Lecture et rōmaji.** Tapez `kakuu` (en lettres latines).
   [17 notices du jeu d'essai : J-ed cherche aussi par la lecture du titre et de l'auteur. Les six notices
   trouvées à l'étape 1 seulement par leur fonds 架空文庫 n'y sont pas, car un fonds n'a pas de lecture. Vos
   propres notices dont la lecture contient « kakuu » s'y ajoutent, le cas échéant.]
3. **Fiche et trois statuts.** Dans les résultats de l'étape 1, sur la ligne de 架空旅日記 (cote 架-009), cliquez
   sur **Fiche locale** : la fiche s'ouvre dans un nouvel onglet.
   [Trois pastilles : Notice, Document, IIIF. Document indique un lien vers une numérisation (adresse fictive
   `example.org`, à ne pas ouvrir).]
4. **Doublons.** Même chose pour 架空國史略 (avec 國, caractère ancien) : **Fiche locale** sur sa ligne → bloc
   « Doublons et notices liées » (colonne de droite, sous
   « Dossiers » ; sur un écran étroit, en bas de la page) → **Chercher des doublons (règles)**.
   [架空国史略 est proposé : même œuvre, en graphie ancienne et moderne. J-ed ne fusionne jamais tout seul.]
5. **Bibliothèque et dossier.** Ma bibliothèque, puis Dossiers → « [Essai] Dossier fictif ».
   [8 notices dans la bibliothèque et dans le dossier.]
6. **Export.** Dans le dossier : Exporter → Word, puis PDF.
   [Deux fichiers téléchargés ; le PDF affiche correctement les caractères japonais.]
7. **Projet de traduction.** Traduction → Projets → « [Essai] Projet de traduction fictif ».
   [Deux documents. Le texte classique est repéré comme langue classique (bungo).]
8. **Traduction hors ligne.** Ouvrez le texte moderne → **Traduire…** → moteur **Argos**.
   [Une traduction française proposée pour chaque segment, sans connexion ; à valider avant publication.]
9. **Tâches et file de nuit.** Sur le texte classique : **Ajouter à la file de nuit**, puis Traduction → Tâches.
   [La tâche apparaît « dans la file de nuit » ; vous pouvez l'annuler.]
10. **Notifications.** Menu à votre nom (en haut à droite, avec le compteur rouge des non lues) → **Notifications**.
    [Les fins de tâche et les exports y apparaissent ; **Marquer comme lue** fait baisser le compteur. Une
    notification qui arrive pendant que vous travaillez s'affiche aussi dans une petite fenêtre en bas de l'écran,
    avec un bouton **Vu**.]
11. **Sauvegarde.** Administration → Sauvegardes → **Sauvegarder maintenant**, puis vérifiez son intégrité.
    [Sauvegarde terminée, intégrité vérifiée.]
12. **Aide.** Le bouton **?** de chaque page ouvre l'aide correspondante.

### Partie B — avec Internet (facultatif, 15 minutes)

Ces recherches interrogent les vraies sources. Les résultats peuvent varier légèrement avec le temps.

1. **Kokusho.** Rechercher, source **Kokusho** seule : `方丈記`.
   [Les 50 premières notices du 日本古典籍総合目録, avec auteur, date, imprimé (刊) ou manuscrit (写). L'état de
   la source indique « 50 résultat(s) sur … » : un peu plus d'une centaine en tout (112 en novembre 2026).]
2. **Document à images.** Pour voir aussi les images dans J-ed, activez d'abord la visionneuse intégrée (elle est
   désactivée par défaut) : Administration → **Paramètres** → cochez **Visionneuse d'images intégrée** → Enregistrer.
   La liste des sites d'images autorisés, déjà remplie, peut rester telle quelle.
   Puis Rechercher → source **Kokusho** seule cochée → tapez `10.20730/200015559` (l'identifiant DOI du 歌仙繪).
   [Un seul résultat : 歌仙繪. Son lien « Ouvrir dans le Kokusho » ouvre la visionneuse du NIJL, sur son site.]
   Sur cette ligne, cliquez sur **Retenir**, puis, en haut de la liste, sur **Intégrer la sélection (1)** → « Ma
   bibliothèque uniquement » → **Confirmer l'intégration**.
   [Retour aux résultats avec « Intégration terminée : 1 notice(s) créée(s)… » ; la ligne affiche maintenant
   **Fiche locale**. Si 歌仙繪 était déjà intégré, ce lien y est déjà.]
   Cliquez sur **Fiche locale** (nouvel onglet), puis sur **Voir les images dans J-ed**.
   [La visionneuse intégrée montre 152 vues. Sans l'activation de la visionneuse, ce bouton n'apparaît pas. La
   fiche se retrouve aussi plus tard dans la **Bibliothèque**.]
3. **Aozora Bunko.** Si la liste n'est pas encore importée : Mises à jour → Aozora Bunko → synchronisation
   complète, puis intégration (quelques minutes, voir [Aozora Bunko](#aozora-bunko)). Rechercher `羅生門`,
   source Aozora Bunko → **Fiche locale** sur la ligne de 羅生門 → **Texte intégral** → **Télécharger le texte**.
   [Le texte s'affiche avec ses furigana ; le texte source (底本) est indiqué en bas de page.]
4. **Waseda.** Source **Waseda** : `源氏物語`.
   [Environ deux cents notices ; « Ouvrir sur le site de Waseda » mène à la page de l'ouvrage. Sur une installation
   mise à jour depuis une version antérieure, choisissez d'abord le connecteur dédié : voir [Les sources](#sources).]
5. **Vérification des sources.** `powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1 -AvecSources`.
   [Chaque source en ligne répond, ou figure dans la liste « sans recherche en ligne ».]

### Pour finir

1. **Administration → Jeu d'essai → Retirer le jeu d'essai.**
   [« Jeu d'essai retiré : 38 notice(s), 1 dossier(s), 1 projet(s) ». Vos données ne sont pas touchées.]
2. Si vous avez fait la partie B, les notices réelles ajoutées à la bibliothèque y restent : retirez-les si vous le
   souhaitez.

Le jeu d'essai se charge aussi en ligne de commande, depuis le dossier de J-ed :
`docker compose exec web python manage.py jeu_essai --charger` (et `--retirer`).

# Référence

## Lexique

Les mots de J-ed, en une phrase chacun.

| Terme | Sens dans J-ed |
| --- | --- |
| **Notice** | Description bibliographique d'un document (titre, auteur, date, cote…), fournie par un catalogue. Ce n'est pas le document lui-même. |
| **Source** | Un catalogue interrogé par J-ed (NDL Search, CiNii, Kokusho, Japan Search…), ou la base locale. |
| **Session de recherche** | Une recherche lancée et ses résultats, avec vos décisions (sélectionné, exclu). |
| **Bibliothèque** | Les notices que vous avez gardées. |
| **Dossier** | Un regroupement de notices autour d'un sujet, avec sous-sections, notes et méthodologie. |
| **Œuvre** | Le texte ou l'objet dont plusieurs notices décrivent des exemplaires ou des éditions. |
| **Couche éditoriale** | Ce qui s'ajoute à la notice sans la modifier : traductions, résumés, classifications, commentaires. |
| **Origine** | Qui a produit un contenu : la source, vous, une IA, une traduction automatique, une règle. |
| **IIIF** | Norme internationale de diffusion des images de documents numérisés. |
| **Manifeste IIIF** | Fichier qui décrit les images d'un document numérisé ; J-ed peut l'ouvrir pour vérifier qu'il existe. |
| **Statuts** | Notice disponible, document consultable, IIIF : voir [Les trois statuts](#trois-statuts). |
| **Moteur** | Ce qui traduit : DeepL, Google, Argos, une IA en ligne, l'IA locale. |
| **Argos Translate** | Moteur de traduction gratuit qui travaille sur votre ordinateur, sans Internet, en passant par l'anglais (japonais → anglais → français). |
| **IA locale** | Une IA (Ollama) qui travaille sur votre ordinateur, sans Internet une fois le modèle installé. |
| **Modèle** | Le « cerveau » précis d'une IA (par exemple qwen3:4b, ou un modèle d'OpenAI). |
| **Projet de traduction** | Un ensemble de documents à traduire, avec ses glossaires ; il peut être confidentiel. |
| **Segment** | Un morceau de document (phrase ou paragraphe), traduit et validé séparément. |
| **Proposition** | Une traduction pas encore validée. |
| **Validation** | Votre accord sur une traduction ; seule une traduction validée entre dans la mémoire. |
| **Mémoire de traduction** | Les segments déjà traduits et validés, réutilisés quand le même texte revient. |
| **Glossaire** | Liste de termes avec leur traduction imposée. |
| **Tâche** | Une traduction ou une demande de résumés, suivie de la préparation au compte rendu. |
| **File de nuit** | Les tâches qui partiront, l'une après l'autre, pendant votre plage de nuit. |
| **Plafond** | Limite mensuelle de caractères ou de coût estimé ; atteinte, la tâche se met en pause. |
| **Seuil** | Montant ou nombre de caractères à partir duquel J-ed redemande confirmation. |
| **Bungo** (文語) | Japonais classique écrit. |
| **Kanbun** (漢文) | Chinois classique, lu à la japonaise avec des signes de lecture. |
| **Sōrōbun** (候文) | Style épistolaire en 候, courant jusqu'au début du XXe siècle. |
| **Rōmaji** | Transcription du japonais en alphabet latin (Hepburn, avec macrons : ō, ū). |
| **Sauvegarde** | Copie complète de la base et des fichiers de J-ed, vérifiable et restaurable. |
| **Dysfonctionnement** | Un problème enregistré par J-ed (source injoignable, erreur…), suivi par l'administrateur. |

## Historique des versions

Évolutions et améliorations de J-ed, version par version.

### Version 2.0.0 (19 novembre 2026)

Une version de consolidation : J-ed devient plus sûr, travaille seul la nuit, résume, et s'explique lui-même.

- **Un nouveau nom, J-ed**, et un logo. Une page « À propos » donne la version et l'origine du projet.
  Administration et Dysfonctionnements passent dans le menu à votre nom (administrateur).
- **Trois statuts par notice**, sans confusion possible : notice disponible, document consultable, IIIF. Le
  manifeste IIIF peut être vérifié d'un clic. Les statuts figurent dans les filtres, les tris et les exports.
- **Notifications** : une fenêtre et un compteur vous préviennent quand une tâche se termine, se met en pause ou
  échoue, et l'administrateur quand un dysfonctionnement apparaît.
- **Tâches et file de nuit** : chaque traduction est une tâche que l'on peut lancer tout de suite, programmer, ou
  placer dans la file de nuit ; pause, reprise sans rien renvoyer, compte rendu du matin. « Traduire maintenant »
  sur la fiche et dans la Bibliothèque. Page « Traductions effectuées ».
- **Plafonds** : un plafond atteint met la tâche en pause ; J-ed ne change jamais de moteur de lui-même.
- **Argos installé d'office**, la traduction japonais → français s'installe en un clic, avec une traduction d'essai.
- **Choix du modèle d'IA dans une liste** tirée du fournisseur, avec le tarif estimé quand il est connu.
- **Résumés IA** : résumé court, détaillé ou fiche d'analyse, toujours dans votre langue, depuis la fiche, la
  Bibliothèque ou l'atelier ; enchaînés aux traductions si vous le souhaitez.
- **IA locale** facultative : une IA gratuite qui travaille sur votre ordinateur, pour les résumés.
- **Japonais ancien** : repérage du bungo, du kanbun et du sōrōbun, et moteur choisi pour eux.
- **Documents et nouvelles sources** : **Aozora Bunko** (plus de 17 000 œuvres) dont le texte intégral se lit
  dans J-ed avec ses furigana et s'envoie vers un projet de traduction ; **Waseda** par le catalogue de la NDL ;
  **Kokusho** interrogé dans sa vraie base ; bouton **« Ouvrir le document »** vers la visionneuse de la source ;
  **visionneuse intégrée** facultative ; pour la NDL, J-ed dit si un document numérisé est en accès libre.
- **Jeu d'essai fictif** et procédure « Essayer J-ed », pour découvrir l'application ou vérifier une nouvelle
  version (Administration → Jeu d'essai).
- **Rapidité mesurée** sur l'ordinateur (commande `mesurer_performances`) ; doublons trouvés aussi dans une
  grande base.
- **Aide intégrée** : une page d'aide par écran (bouton **?**), une recherche, un lexique, cet historique, et une
  rubrique « Installation et mises à jour » (mettre à jour, vérifier, dépanner).
- **Installation** : mise à jour en une commande (`mettre-a-jour.ps1`), vérification automatique
  (`verifier-j-ed.ps1`), page « État de l'installation », sauvegardes copiées dans un dossier de Windows, réglage
  automatique selon la puissance de l'ordinateur.

### Version 1.3.0 (14 novembre 2026)

Le module de **traduction**.

- Moteurs : DeepL, Google Traduction, Argos Translate (sur l'ordinateur) et IA en ligne, choisis dans
  Traduction → Moteurs, avec le résumé des conditions de chaque service avant le premier envoi.
- Traduction des notices (titre, description, sujets, lieu), validée avant d'apparaître sur la fiche.
- Projets de traduction : documents découpés en segments, atelier à deux colonnes, versions, validation,
  projets confidentiels.
- Glossaires (import et export CSV, envoi à DeepL) et mémoire de traduction.
- Exports bilingues : texte, Markdown, CSV, Word en tableau.
- Évaluation des moteurs côte à côte et page de consommation.

### Version 1.2.0 (13 novembre 2026)

- Nouvelles sources : CiNii Research, Archives nationales par Japan Search, outil pour trouver une base Japan
  Search.
- Recherche : état clair de chaque source (résultats, aucun résultat, indisponible…), variantes de graphie libres,
  filtre « document numérisé », tri par auteur et par institution.
- Journal des dysfonctionnements : enregistrement automatique, regroupement, suivi, analyse, export.
- Installation d'essai séparée de l'installation principale.

### Version 1.1 (novembre 2026)

La première version complète : recherche dans plusieurs catalogues japonais, Bibliothèque, dossiers partagés,
fiches avec versions et provenance, fonctions IA, exports (Word, PDF, texte, JSON, CSV, site HTML), mises à jour des
sources et imports, comptes et rôles, sauvegardes.
