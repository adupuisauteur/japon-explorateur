---
titre: Les sources documentaires
rubrique: Chercher et lire
ordre: 40
public: tous
ecrans: connectors:list, connectors:detail, connectors:jps_databases
resume: Les catalogues interrogés par J-ed, leurs capacités et leur état.
---
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
| **Aozora Bunko** (青空文庫) | Textes du domaine public : liste des œuvres importée, texte intégral téléchargé à la demande ([Aozora Bunko](aide:aozora-bunko)) |

## La fiche d'une source

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

## Mettre à jour les notices

L'administrateur peut resynchroniser une source, importer un fichier et décider des notices modifiées : voir
[Mises à jour et imports](aide:mises-a-jour-et-imports).
