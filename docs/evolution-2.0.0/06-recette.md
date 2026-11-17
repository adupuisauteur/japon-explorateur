# J-ed 2.0.0 — Recette de la version candidate rc1

*17 novembre 2026. La 2.0.0 devient définitive quand les essais ci-dessous sont faits sur le poste de
l'utilisateur. Le code est alors envoyé sur GitHub (branche `evolution-2.0.0`, puis fusion dans `main` sans
réécriture de l'historique), selon la décision du 17 novembre 2026.*

## 1. Dernière série de tests (environnement de développement)

| Essai | Résultat |
|---|---|
| Suite complète, en parallèle, ordre aléatoire (`test --parallel 4 --shuffle`), cinq passages | 758 tests, tous réussis (deux passages ont d'abord révélé deux défauts de l'aide et un défaut du jeu d'essai, corrigés avant les passages retenus) |
| Suite complète en série (`test`) | 758 tests réussis |
| Migrations : base 1.3.0-rc3 avec données fictives, créée par le code 1.3.0 (20 notices, bibliothèque, dossier, projet de traduction), puis passage à la 2.0.0 | 14 migrations appliquées ; données intactes ; statuts des notices calculés ; sources Aozora et Waseda ajoutées, source Waseda existante non modifiée |
| Sur cette base passée en 2.0.0 : `etat_installation`, `verifier_fonctionnalites`, jeu d'essai chargé puis retiré | Aucun problème ; 12 fonctions OK, les autres « non vérifiées » faute de Redis, Argos et sauvegarde hors Docker ; retrait complet, les 20 notices d'origine gardées |
| Retour à la 1.3.0 (séquence du guide de mise à jour), puis réapplication | Réussis |
| `check --deploy` avec des réglages de production | Deux avertissements seulement : HSTS pour les sous-domaines et préchargement, réglables par l'exploitant (voir `docs/deploiement.md`) |
| Captures des pages nouvelles (Jeu d'essai, aide « Essayer J-ed », fiche, recherche) | Correctes, après une correction : la source du jeu d'essai renvoyait ses notices une seconde fois dans une recherche |

Défauts trouvés pendant cette série et corrigés :

- **Doublons** : une même œuvre en graphie ancienne (國) et moderne (国) n'était jamais rapprochée. La
  présélection porte désormais sur les trois formes (test ajouté).
- **Jeu d'essai** : sa source avait le connecteur de la base locale, et ses notices sortaient deux fois. Elle n'a
  plus de connecteur propre.
- **Aide** : la nouvelle page renvoyait vers une page d'aide inexistante (lien retiré). Le test de la rubrique
  « Installation et mises à jour » a été mis à jour.

## 2. Déjà constaté sur le poste de l'utilisateur pendant les lots

- Vérification automatique du 16/11/2026 à 22 h 43 : 30 points OK, aucun problème. Le 16/11 à 18 h 39 :
  690 tests réussis avec `-AvecTests`. Le 16/11 à 18 h 42 : sources en ligne vérifiées avec `-AvecSources`.
- IA locale prête (essai automatique au démarrage) et résumés (lot 4) ; tâches et file de nuit (lot 3) ; aide
  intégrée et logo (lot 6) ; mesure des performances (lot 9).
- Lot 10 : trois passages de l'étude des sources ; liste d'Aozora Bunko importée (21 395 notices dans la base
  d'essai) ; incident des intégrations simultanées corrigé.

## 3. Grille de recette de la rc1

Notez « OK », ou ce qui s'est passé, avec une capture si possible.

### A. Mise à jour de l'installation d'essai (`japon-explorateur-essai`, port 8001)

| N° | Essai | Attendu | Résultat |
|---|---|---|---|
| R1 | `mettre-a-jour.ps1` avec `japon-explorateur-2.0.0-rc1.zip` | « Mise à jour terminée : J-ed 2.0.0 » | |
| R2 | `.\verifier-j-ed.ps1 -AvecTests -AvecSources` | Aucune ligne « Problème » ; environ 758 tests réussis | |
| R3 | Aide → Essayer J-ed, partie A (jeu d'essai) | Chaque étape donne le résultat indiqué | |
| R4 | Aide → Essayer J-ed, partie B (Internet) | Idem ; correspond aux essais V10-4 à V10-8 et V10-11 du protocole | |
| R5 | Retirer le jeu d'essai | « 38 notice(s), 1 dossier(s), 1 projet(s) » ; tes données intactes | |

### B. Installation complète, à côté de l'installation d'essai

Suivre le guide d'installation dans un dossier séparé, sous un nom et un port nouveaux (par exemple
`C:\J-ed-essai2`, `jed-essai2`, port 8010).

| N° | Essai | Attendu | Résultat |
|---|---|---|---|
| R6 | Étapes 1 à 4 du guide (Docker déjà présent : étape 1 sautée) | Assistant de première configuration, puis compte administrateur créé | |
| R7 | Étape 5 : Argos | « Argos prêt » | |
| R8 | Étape 6 : IA locale (facultatif) | « IA locale prête » | |
| R9 | Étape 7 : jeu d'essai et procédure « Essayer J-ed » | Comme R3 à R5 | |
| R10 | `verifier-j-ed.ps1` dans ce dossier | Aucune ligne « Problème » | |
| R11 | L'installation d'essai (port 8001) fonctionne toujours | Ses données sont intactes | |

### C. Décision

| | |
|---|---|
| Recette faite le | |
| Points à corriger avant la 2.0.0 | |
| Décision | 2.0.0 définitive / rc2 nécessaire |

Une fois la 2.0.0 validée : envoi sur GitHub (branche, puis fusion dans `main`), puis mise à jour de
l'installation principale, d'abord essayée sur l'installation d'essai.
