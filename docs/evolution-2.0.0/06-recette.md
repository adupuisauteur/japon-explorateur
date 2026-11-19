# J-ed 2.0.0 — Recette des versions candidates (rc1, rc2)

*17 et 18 novembre 2026. La recette de la rc1 a été faite sur le poste de l'utilisateur ; ses remarques ont
donné la rc2 (décision du 18 novembre : rc2, puis recette courte). La 2.0.0 devient définitive après la recette
courte de la rc2 (section 4) ; le code est alors fusionné dans `main` sans réécriture de l'historique. La branche
`evolution-2.0.0` est sur GitHub depuis le 17 novembre.*

## 1. Dernière série de tests (environnement de développement)

| Essai | Résultat |
|---|---|
| Suite complète, en parallèle, ordre aléatoire (`test --parallel 4 --shuffle`), cinq passages | 758 tests, tous réussis (deux passages ont d'abord révélé deux défauts de l'aide et un défaut du jeu d'essai, corrigés avant les passages retenus) |
| Suite complète en série (`test`) | 758 tests réussis |
| **rc2 (18/11)** : suite complète, cinq passages en parallèle et ordre aléatoire, puis un passage en série | 759 tests, tous réussis à chaque passage |
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
| R1 | `powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1` avec `japon-explorateur-2.0.0-rc1.zip` | « Mise à jour terminée : J-ed 2.0.0 » | OK (17/11) |
| R2 | `powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1 -AvecTests -AvecSources` | Aucune ligne « Problème » ; environ 758 tests réussis | OK (17/11 : 758 tests, 28 pages, 21 399 notices intactes ; Waseda à régler par le connecteur dédié, puis 31 OK) |
| R3 | Aide → Essayer J-ed, partie A (jeu d'essai) | Chaque étape donne le résultat indiqué | OK (17/11) ; résultats attendus de l'aide corrigés (rc2) |
| R4 | Aide → Essayer J-ed, partie B (Internet) | Idem ; correspond aux essais V10-4 à V10-8 et V10-11 du protocole | OK (18/11, nouvelle installation) ; aide corrigée (Kokusho : 50 premières notices ; visionneuse à activer) |
| R5 | Retirer le jeu d'essai | « 38 notice(s), 1 dossier(s), 1 projet(s) » ; tes données intactes | OK (17/11 : 21 399 notices) |

### B. Installation complète, à côté de l'installation d'essai

Suivre le guide d'installation dans un dossier séparé, sous un nom et un port nouveaux (par exemple
`C:\J-ed-essai2`, `jed-essai2`, port 8010).

| N° | Essai | Attendu | Résultat |
|---|---|---|---|
| R6 | Étapes 1 à 4 du guide | Assistant de première configuration, puis compte administrateur créé | OK (18/11, PC sans proxy, Docker installé par l'étape 1) ; un premier essai derrière un proxy a échoué (Docker Hub injoignable) : section proxy reportée à la 2.0.1 |
| R7 | Étape 5 : Argos | « Argos prêt » | OK (18/11) |
| R8 | Étape 6 : IA locale (facultatif) | « IA locale prête » | OK (18/11) ; le guide précise où s'affiche le message |
| R9 | Étape 7 : jeu d'essai et procédure « Essayer J-ed » | Comme R3 à R5 | OK (18/11) |
| R10 | `powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1` dans ce dossier | Aucune ligne « Problème » | OK (18/11, selon l'utilisateur) |
| R11 | L'installation d'essai (port 8001) fonctionne toujours | Ses données sont intactes | OK : installation d'essai passée le 18/11 sur un autre ordinateur (images et volumes Argos et IA locale repris de l'exportation, base restaurée depuis la sauvegarde J-ed du 18/11 à 6 h 31), contrôlée par `verifier-migration.ps1` |

### C. Décision (18 novembre 2026)

| | |
|---|---|
| Recette faite les | 17 et 18 novembre 2026 |
| Points corrigés avant la 2.0.0 | Voir l'entrée « rc2 » du CHANGELOG (aide, messages, essai des sources sans cache, jeu d'essai) |
| Décision | rc2, puis recette courte (section 4) |

### D. Mesure des performances (17/11, installation d'essai)

`mesurer_performances` : 50 000 notices fictives, toutes les mesures ≤ 199 ms ; doublons d'une notice 44 ms et
10 candidats ; sur les 21 399 notices réelles, recherches de 4 à 83 ms. Aucune lenteur.

## 4. Recette courte de la rc2

Sur l'installation d'essai (port 8001), à jour avec `japon-explorateur-2.0.0-rc2.zip`.

| N° | Essai | Attendu | Résultat |
|---|---|---|---|
| S1 | `powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.0-rc2.zip …` | « Mise à jour terminée : J-ed 2.0.0 » | OK le 19/11 sur l'installation d'essai (machine des premiers essais) : code rc2 confirmé. Sur la VM de migration, derrière un proxy à fichier PAC : construction impossible (Docker Hub injoignable) après l'arrêt de l'ancienne version ; J-ed remis en service, données intactes ; suite en 2.0.1 |
| S2 | `powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1 -AvecTests -AvecSources` | Aucune ligne « Problème » ; environ 760 tests ; temps de réponse des sources réels (plus de « 0 ms ») | OK (rapport du 19/11, 15 h 12) : 32 OK, 0 problème, 759 tests ; 8 sources en ligne de 312 ms à 6,5 s ; Waseda répond (223 résultats) ; Kokugakuin répond avec 0 résultat (à surveiller) |
| S3 | Administration → Jeu d'essai → Charger | Bouton « Ouvrir la procédure « Essayer J-ed » » ; l'aide s'ouvre dans un nouvel onglet ; journal : « Jeu d'essai chargé : 38 notice(s)… » | OK : lien et bouton dans un nouvel onglet ; journal « Jeu d'essai chargé : 38 notice(s), dont 38 nouvelle(s) » (un second clic : « dont 0 nouvelle(s) », sans doublon) |
| S4 | Une traduction Argos (étape 8 de la partie A) | « caractère(s) traité(s) sur cet ordinateur » | OK : tâche 26, « 80 caractère(s) traité(s) sur cet ordinateur », coût : aucun, connexion coupée |
| S5 | Retirer le jeu d'essai | Journal : « Jeu d'essai retiré : 38 notice(s), 1 dossier(s), 1 projet(s). » ; données intactes | OK : journal « Jeu d'essai retiré : 38 notice(s), 1 dossier(s), 1 projet(s). » |

Constats de la partie B de « Essayer J-ed » (19/11) et corrections de l'aide, livrées dans la 2.0.0 :

- document à images (Kokusho, 歌仙繪) : l'aide disait « ajoutez-le à la bibliothèque », sans bouton de ce nom ;
  chemin exact écrit (Retenir, Intégrer la sélection, Confirmer l'intégration, Fiche locale, Voir les images dans
  J-ed) et validé : 152 vues ;
- NDL : la recherche de `2586959` renvoie deux articles qui contiennent ce nombre (R000000004-I2586959,
  R100000002-I025933528), pas le document numérisé ; un titre (`吾輩ハ猫デアル`, `徒然草`) renvoie d'abord des
  notices récentes ou des revues numérisées réservées ; **étape retirée de l'aide**, recherche fiable d'un document
  numérisé librement consultable étudiée en 2.0.1 ;
- Aozora Bunko (17 840 notices) : 羅生門 téléchargé avec ses furigana et son 底本 ; l'aide précise « Fiche locale » ;
- Waseda : recherche et lien vers la page de l'ouvrage corrects (site de Waseda en maintenance programmée le
  19/11 au soir) ;
- aide « Mettre à jour J-ed » : méthode pas à pas, une commande par cadre ; vérifier l'accès de Docker à Internet
  (`docker pull python:3.12-slim-bookworm`) avant de lancer le script, proxy de Docker Desktop, conduite à tenir
  si l'arrêt survient après « OUI ». Le changement d'ordre du script (construire avant d'arrêter, journal, retour
  automatique) est reporté à la 2.0.1 (décision de l'utilisateur).

**Décision (19 novembre 2026) : recette rc2 validée, J-ed 2.0.0 déclarée définitive.**

Ensuite : 2.0.0 définitive, fusion dans `main`, puis passage de l'installation principale (1.x) vers la 2.0,
d'abord essayé sur une copie ; puis 2.0.1 (Linux, accès en réseau local, section proxy).
