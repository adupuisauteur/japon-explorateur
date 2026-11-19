---
titre: État de l'installation et réglages
rubrique: Administration
ordre: 20
public: admin
ecrans: core:state, core:settings, core:audit_log, core:machine_memory
resume: Vérifier que tout fonctionne, régler l'instance, adapter J-ed à l'ordinateur.
---
## La page « État de l'installation »

Administration → **État de l'installation** : un contrôle par ligne (version, base de données, Redis, workers,
planificateur, Argos, IA locale, sauvegardes…), chacun « Correct », « À surveiller », « Problème » ou
« Non vérifiable », avec le détail.

- **Traduction d'essai Argos** : vérifie Argos de bout en bout.
- **Diagnostic à transmettre** : un texte à copier pour signaler un problème. Il ne contient ni clé, ni nom de
  compte, ni texte de recherche ou de traduction ; les chemins personnels sont masqués.

Pour lire chaque ligne en détail, et pour le contrôle complet depuis Windows (`verifier-j-ed.ps1`), voir
[Vérifier l'installation](aide:verifier-l-installation).

## Profil de la machine

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

## Paramètres de l'instance

Administration → **Paramètres** : nom de l'installation, mode de recherche par défaut, durée de conservation des
sessions temporaires, sauvegardes automatiques, auteur et en-têtes des exports, **mode démonstration d'Argos**
(désactivé par défaut : chaque résultat porte alors la mention « Simulation »). Aucun secret n'y figure : les clés
et mots de passe restent dans `.env`.

## Journal des actions

Administration → **Journal des actions** : les actions sensibles (comptes, clés, envois aux services, sauvegardes,
téléchargements de modèles…), sans aucun secret.
