---
titre: Mises à jour des sources et imports
rubrique: Administration
ordre: 60
public: admin
ecrans: updates:dashboard, updates:sync_detail, updates:import_new, updates:import_detail
resume: Resynchroniser les sources, importer un fichier, décider des notices modifiées.
---
Sources → **Gestionnaire de mises à jour** (administrateur).

## Synchroniser une source

| Action | Effet |
| --- | --- |
| **Synchronisation incrémentale** | Ce qui a changé depuis la dernière fois |
| **Synchronisation complète** | Toute la source (long) |
| **Actualiser les notices connues** | Relit seulement les notices déjà présentes dans J-ed |
| **Tester le connecteur** | Une recherche d'essai |
| **Suspendre / Reprendre** | Arrête les synchronisations de cette source |

Une synchronisation ne remplace jamais une notice en silence. Chaque notice nouvelle ou modifiée vous est proposée :
vous **intégrez** ou vous écartez. L'ancienne version reste consultable sur la fiche.

## Importer un fichier

**Import → Nouveau** : un fichier CSV ou Excel (inventaire, liste de références). J-ed reconnaît les colonnes,
montre ce qu'il a compris, compare avec les notices existantes, puis attend votre décision. Des fichiers d'exemple
sont livrés dans `docs/exemples/`.
