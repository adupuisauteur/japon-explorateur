---
titre: Comprendre les trois statuts
rubrique: Chercher et lire
ordre: 30
public: tous
ecrans: catalog:record_status
resume: Notice disponible, document consultable, IIIF : trois questions différentes.
---
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

## Cas particuliers

- **Consultation sur place** : un document numérisé mais réservé (dans les salles d'une bibliothèque) est
  « non consultable ». La fiche le mentionne, pour ne pas faire croire qu'il n'existe pas de numérisation.
- **IIIF identifié** : une adresse de manifeste figure dans les données de la source, mais J-ed ne l'a pas encore
  ouverte. **Vérifier le IIIF** (sur la fiche) l'ouvre et passe le statut à « vérifié » ou « vérification en échec ».

Dans la Bibliothèque, vous pouvez filtrer les notices selon ces statuts.

Voir aussi le [Lexique](aide:lexique) (IIIF, manifeste).
