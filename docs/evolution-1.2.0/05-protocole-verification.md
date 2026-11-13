# Protocole de vérification utilisateur — version 1.2.0 (Windows 11)

**Objectif :** confirmer en conditions réelles ce qui n'a pu être testé qu'en simulation. Durée : environ 45 minutes. Prérequis : l'installation d'essai fonctionne (guide d'installation, étapes 1 à 6). Elle est ouverte sur **http://localhost:8001** avec le compte administrateur.

Pour chaque test, notez **OK** ou **KO** dans la grille finale. En cas de KO, notez l'identifiant d'incident (`INC-…`) affiché, puis exportez le diagnostic (test V8).

---

## A. Démarrage et version

**V1 — Version affichée.** Le pied de page indique « v1.2.0 » et le menu contient « Dysfonctionnements ».

**V2 — Séparation des installations.** L'installation principale (http://localhost:8000) s'ouvre toujours, avec vos données habituelles. `docker volume ls` montre des volumes `japon-explorateur-essai_…` distincts.

## B. Tests réels des connecteurs (un par connecteur)

Pour chaque ligne :
1. **Sources →** la source → **Tester le connecteur**.
2. Si le test réussit : **Configuration →** cochez « Interrogé dans les recherches » → Enregistrer.
3. **Rechercher** : le terme indiqué, avec **cette source seule** cochée.

| Test | Source | Terme | Résultat attendu |
|---|---|---|---|
| **C1** | NDL Search | `源氏物語` | Résultats ; « Notice officielle » ouvre la notice NDL ; si la NDL fournit le lien, « Document numérisé » ouvre dl.ndl.go.jp (notez si ce lien apparaît) |
| **C2** | Japan Search | `方丈記` | Résultats d'institutions variées ; « Notice officielle » ouvre la notice |
| **C3** | Archives nationales (via Japan Search) | `太政類典` | Résultats du 国立公文書館 ; liens vers la Digital Archive |
| **C4** | Kokusho | `方丈記` | Résultats Kokusho ; liens kokusho.nijl.ac.jp |
| **C5** | CiNii Research *(si vous avez l'identifiant)* | `歩き巫女` | Articles ou livres ; « Notice officielle » ouvre cir.nii.ac.jp |
| **C6** | CiNii — bibliothèques universitaires *(idem)* | `甲陽軍鑑` | Livres de bibliothèques universitaires |
| **C7** | Trouver une base Japan Search | `早稲田` puis `公文書館` | Liste de bases, chacune marquée « diffusée » ou « non diffusée ». Créez-en une, testez-la, lancez une recherche. |

Sans identifiant CiNii, C5 et C6 doivent afficher « Configuration incomplète » avec un message qui explique comment obtenir l'identifiant. Dans ce cas, notez **« non testé (pas d'identifiant) »**.

**Variantes (C8).** Rechercher `望月千代女` avec NDL et Japan Search, en cochant la suggestion `望月千代` et en ajoutant `千代女房` dans « Mes variantes ». Attendu : les deux sources répondent, sans erreur. Japan Search ne doit pas donner **moins** de résultats qu'une recherche sur `望月千代女` seul.

## C. Situations d'échec

**V3 — Absence de résultat.** Rechercher `ｘｑｚ架空語９９` sur NDL et Japan Search. Attendu : « Recherche réussie, aucun résultat » (pastille grise). **Aucun** nouvel incident dans le journal.

**V4 — Indisponibilité.** Coupez la connexion Internet du PC (mode Avion ou Wi-Fi désactivé). Relancez une recherche sur NDL et Japan Search. Attendu : « Source indisponible » (orange) pour les deux, sans blocage de la page. Le journal contient des incidents d'**Avertissement** ; leur origine probable est « Réseau » ou « Source distante ». **Dysfonctionnements → Analyse** signale « Plusieurs sources ont échoué en même temps ». Rétablissez la connexion, relancez avec ↻ : les résultats reviennent. L'historique de l'incident indique « Source de nouveau disponible ».

**V5 — Indépendance des sources.** Toujours sans connexion, cochez « Base locale » en plus. Attendu : la base locale répond normalement.

## D. Journal des dysfonctionnements

**V6 — Consultation et filtres.** Dans **Dysfonctionnements**, filtrez par source (`ndl`), par gravité (Avertissement), par date (aujourd'hui), puis recherchez un identifiant `INC-…`. Attendu : la liste se réduit correctement, et la fiche d'un incident affiche origine probable, occurrences et historique.

**V7 — Signalement manuel.** **Signaler un problème** (en bas de page). Remplissez tous les champs et joignez une capture d'écran (Windows + Maj + S, puis collez-la dans Paint et enregistrez-la en PNG). Attendu : un incident « signalement manuel » est créé, et la capture s'ouvre.

**V8 — Export du diagnostic.** Sur un incident : **Exporter le diagnostic** → relisez l'aperçu → **Télécharger ce rapport**. Attendu : un fichier `.md` contenant la version 1.2.0, l'identifiant, les messages et les étapes pour reproduire. Cochez « Masquer les termes de recherche » : les termes disparaissent de l'aperçu.

**V9 — Aucun secret dans le journal.** *(Si vous avez un identifiant CiNii.)* Mettez volontairement un identifiant **faux** dans `.env` (`CINII_APPID=FAUX12345`), puis lancez `docker compose up -d` et une recherche CiNii. Attendu : une erreur dans le journal, où la valeur `FAUX12345` n'apparaît **nulle part**, ni dans la fiche ni dans l'export (`appid=[secret masqué]`). Remettez ensuite le vrai identifiant.

**V10 — Suivi de correction.** Sur un incident, choisissez le statut **Corrigé** → Enregistrer. Reproduisez le problème (par exemple V4). Attendu : l'incident repasse « À analyser », marqué « réapparu ×1 », avec un bloc « Avant / après correction ».

## E. Données et redémarrage

**V11 — Conservation du catalogue.**
1. **Sources → Importer un fichier** : `docs\exemples\exemple_inventaire.csv` (données fictives), source « CODH — PMJT ». Validez l'import.
2. Ouvrez une notice importée, ajoutez-la à la bibliothèque, mettez-la en favori et ajoutez une note.
3. Lancez une recherche NDL, puis intégrez un ou deux résultats.

Attendu : la notice importée garde sa note et son favori, et le nombre de notices augmente seulement des résultats intégrés.

**V12 — Redémarrage.** `docker compose restart`, puis attendez une minute et rechargez la page. Attendu : connexion possible, et journal, notices, notes et sources activées intacts.

**V14 — Réinitialisation (facultatif, à faire en dernier).** `powershell -ExecutionPolicy Bypass -File .\reinitialiser-essai.ps1` → répondez **O** à la sauvegarde → tapez `REINITIALISER`. Attendu : une sauvegarde `.tar` dans `sauvegardes-essai`, la base vide (l'assistant de première configuration réapparaît sur http://localhost:8001) et l'installation principale (http://localhost:8000) intacte.

**V13 — Tests automatiques (facultatif).** `docker compose exec web python manage.py test tests`. Attendu : « OK » à la fin (127 tests).

---

## Grille de résultats (à renvoyer)

| Test | OK / KO / non testé | Incident (si KO) | Remarque |
|---|---|---|---|
| V1 version | | | |
| V2 séparation | | | |
| C1 NDL | | | |
| C2 Japan Search | | | |
| C3 Archives nationales | | | |
| C4 Kokusho | | | |
| C5 CiNii Research | | | |
| C6 CiNii bibliothèques | | | |
| C7 Trouver une base | | | |
| C8 Variantes | | | |
| V3 aucun résultat | | | |
| V4 indisponibilité | | | |
| V5 indépendance | | | |
| V6 filtres | | | |
| V7 signalement | | | |
| V8 export | | | |
| V9 secrets | | | |
| V10 réapparition | | | |
| V11 conservation | | | |
| V12 redémarrage | | | |
| V13 tests auto | | | |
| V14 réinitialisation | | | |

**À joindre en cas de KO :** le rapport exporté (**Dysfonctionnements → Exporter un diagnostic**, filtré sur la date du test). Avec cette grille, ce rapport suffit pour analyser et corriger les connecteurs.

Après un test réel réussi, le badge « non vérifié » disparaît de la source, et la date du test est enregistrée (« Dernier test réel réussi »). Elle servira à faire passer le connecteur au statut **« testé en conditions réelles »**.
