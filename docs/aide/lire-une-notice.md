---
titre: Lire une notice
rubrique: Chercher et lire
ordre: 20
public: tous
ecrans: catalog:record_detail, catalog:version_detail, catalog:work_detail, catalog:record_viewer
resume: Ce que montre la fiche d'une notice, et ce qui vient de la source ou de vous.
---
La fiche d'une notice réunit plusieurs couches, toujours distinguées :

| Couche | Contenu |
| --- | --- |
| **Données originales de la source** | Ce que le catalogue a fourni, sans modification |
| **Données normalisées** | Les mêmes informations rangées par J-ed (titre, auteurs, dates, lieu, rōmaji) |
| **Couche éditoriale** | Traductions, résumés, classifications : chacune porte son origine (source, IA, traduction automatique, vous) |
| **Notes et annotations** | Vos notes privées ou partagées, rattachées éventuellement à une page, un folio, une image |

Un contenu produit par une IA ou un moteur de traduction est marqué comme tel. Il reste « non validé » tant que
vous ne l'avez pas validé.

## En haut de la fiche

- Les **trois statuts** de la ressource : notice, document, IIIF. Voir [Les trois statuts](aide:trois-statuts).
- Le **japonais ancien** : si le texte ressemble à du bungo, du kanbun ou du sōrōbun, un bandeau « probable »
  l'indique. Voir [Le japonais ancien](aide:japonais-ancien).
- **Ajouter au dossier**, ajouter à la Bibliothèque.

## Plus bas

- **Résumés IA** : résumer la notice, maintenant ou cette nuit. Voir [Résumés IA](aide:resumes-ia).
- **Traductions** : titre et description traduits, à valider. Voir [Traduire une notice](aide:traduire-une-notice).
- **Provenance** : d'où vient la notice, quand elle a été collectée.
- **Versions** : chaque mise à jour par la source garde l'ancienne version, consultable.
- **Œuvre** : rattacher plusieurs exemplaires d'une même œuvre. La date de composition de l'œuvre et celle de
  l'exemplaire ne sont jamais confondues.

Une erreur dans la notice ? **Proposez une correction** : l'administrateur la valide ou la refuse. Les données de la
source ne sont jamais écrasées.

## Ouvrir le document

Quand J-ed sait où lire le document lui-même, la fiche et les résultats de recherche proposent un bouton qui y
mène directement, plutôt que vers le manifeste IIIF (un fichier technique) :

- **Ouvrir dans le Kokusho** : la visionneuse du 国書データベース ;
- **Ouvrir dans la NDL Digital Collections** : la page du document numérisé (son accès peut être réservé aux
  bibliothèques ou à la NDL) ;
- **Ouvrir sur le site de Waseda** : la page de l'ouvrage. Les images restent celles du
  « 早稲田大学図書館古典籍総合データベース », qu'il faut citer. Toute réutilisation demande l'autorisation de la
  bibliothèque de Waseda ;
- **Lire le texte (Aozora Bunko)** : la page de lecture ; voir aussi [le texte intégral dans J-ed](aide:aozora-bunko).

## Voir les images dans J-ed (facultatif)

L'administrateur peut activer la **visionneuse intégrée** : Administration → Paramètres → « Visionneuse d'images
intégrée ». Elle est désactivée par défaut. Une fois activée, le bouton **Voir les images dans J-ed** apparaît sur
les fiches qui ont un manifeste IIIF. La visionneuse permet de passer d'une vue à l'autre (flèches du clavier) et
d'afficher la taille réelle.

Votre navigateur charge alors les images directement depuis le site de la source, et seulement depuis les sites
listés dans « Sites d'images autorisés » (par défaut `kokusho.nijl.ac.jp` et `dl.ndl.go.jp`). J-ed ne copie pas
les images. Les mentions demandées par la source (attribution, licence) s'affichent sous l'image.
