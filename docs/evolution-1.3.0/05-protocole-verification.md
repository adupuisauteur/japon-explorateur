# Protocole de vérification utilisateur — version 1.3.0 (Windows 11)

**Objectif :** confirmer en conditions réelles ce qui n'a pu être testé qu'en simulation (DeepL, Google, IA,
Argos, Docker, script PowerShell). Durée : 1 h 30 à 2 h (TR8 dépend du téléchargement des paquets).
Prérequis : l'essai 1.3.0 est installé (`03-guide-installation-windows.md`) et ouvert sur
**http://localhost:8002** avec le compte administrateur.

**Textes à utiliser :** uniquement des textes fictifs ou libres de droits, jamais un texte confidentiel (par
exemple : 「江戸の町は賑やかであった。徳川家康は幕府を開いた。」).

Pour chaque test, notez **OK**, **KO** ou **non testé** (avec la raison) dans la grille finale. En cas de KO,
notez l'identifiant d'incident (`INC-…`) et exportez le diagnostic (Dysfonctionnements → incident → Exporter).

---

**TR1 — Installation et version.** Pied de page « v1.3.0 », menu « Traduction ». L'installation principale
(port 8000) et l'essai 1.2.0 (port 8001) s'ouvrent toujours avec leurs données. `docker volume ls` montre des
volumes `japon-explorateur-essai-130_…` distincts. *Facultatif :* `docker compose exec web python manage.py test
tests` → « OK » (382 tests ou plus).

**TR2 — Clé DeepL.** Suivez `notice-cle-deepl.md`. Attendu : « Tester » affiche « Connexion réussie » avec votre
consommation ; la clé n'est plus jamais affichée ; une offre erronée (gratuite au lieu de payante) donne un
message clair.

**TR3 — Clé Google.** Suivez `notice-cle-google.md`. Attendu : « Tester » affiche la traduction de la phrase
d'essai fictive.

**TR4 — Traduction d'une notice.** Importez ou créez une notice fictive (titre et description en japonais).
Fiche → **Traduire…** avec chaque moteur configuré tour à tour (DeepL, Google, IA si configurée, Argos).
Attendu : au premier envoi à chaque fournisseur, le résumé de ses conditions et la case à cocher ; l'écran de
confirmation (volume, coût estimé ou « non disponible ») ; les propositions sur la page « Traductions de la
notice » ; **Valider** (administrateur) adopte la traduction dans la fiche, le titre original est inchangé.

**TR5 — Projet fictif.** Traduction → Projets → Nouveau projet. Ajoutez un document (collez quelques
paragraphes, puis importez un .txt en Shift_JIS et un .docx). Attendu : découpage en segments, original exact.
Créez un chapitre, traduisez-le avec le moteur par défaut, puis un segment avec le deuxième moteur ; comparez
les versions sur la page du segment ; corrigez une version ; validez.

**TR6 — Glossaire.** Créez un glossaire (ex. 幕府 → bakufu, à éviter : shogunat), rattachez-le au projet,
traduisez avec Google ou Argos un segment contenant 幕府. Attendu : alerte « glossaire : … devrait être traduit
par « bakufu » » si le moteur ne l'a pas respecté, sans correction automatique. Testez l'import et l'export CSV.

**TR7 — Glossaire DeepL.** Sur le glossaire : cochez la confirmation → **Envoyer à DeepL**. Attendu : « Glossaire
envoyé à DeepL (n entrée(s)…) ». Traduisez avec DeepL un segment contenant le terme : la version indique le
glossaire appliqué « native », et le terme est respecté. Puis **Supprimer la copie DeepL** : message de
suppression ; vérifiez sur votre compte DeepL qu'il n'y a plus de glossaire.

**TR8 — Argos Translate hors ligne.** Suivez `notice-argos.md` :
1. `docker compose --profile hors-ligne up -d --build` (notez la durée et la taille : `docker image ls`).
2. Moteurs locaux → **Consulter l'index Argos** (aucun téléchargement), cochez ja→en et en→fr, confirmez.
   Attendu : installations « Terminée », paquets « installé, v… ».
3. Traduisez un segment avec Argos : état « Disponible hors ligne », pas de mention Simulation, version des
   paquets enregistrée.
4. **Coupez Internet** (mode Avion), redémarrez Argos (`docker compose --profile hors-ligne restart argos`), puis
   traduisez un autre segment. Attendu : la traduction fonctionne. Notez la durée pour un chapitre d'environ
   20 phrases.

**TR9 — Projet confidentiel.** Créez un projet coché « Confidentiel ». Attendu : DeepL, Google et IA refusés
(« Projet confidentiel : moteurs en ligne refusés ») ; Argos accepté. Connecté avec un autre compte
administrateur : seuls le titre, le propriétaire et la taille sont visibles.

**TR10 — Erreur volontaire.** Remplacez la clé DeepL par une clé fausse, puis traduisez. Attendu : message
« Clé DeepL refusée… » ; un incident « traduction / Clé refusée » dans Dysfonctionnements ; le diagnostic exporté
ne contient **ni la clé ni le texte**. Remettez la bonne clé.

**TR11 — Exports.** Traduction → Exports → votre projet : téléchargez chaque format (texte bilingue .txt et
Markdown, CSV, traduction seule, Word). Attendu : fichiers lisibles (Word et Excel/LibreOffice), japonais
correct, mention « non validée » en mode « à défaut dernière proposition », mention « Simulation » si un
résultat simulé est présent. Glossaire : export CSV.

**TR12 — Retour à la 1.2.0.** Suivez `retour-1.2.0.md` sur l'essai 1.3.0 (après les autres tests). Attendu :
`verifier_retour_120` liste vos données ; les trois commandes de migration réussissent ; après passage au code
1.2.0, le pied de page indique « v1.2.0 », les notices et le journal sont intacts, aucune migration en attente.
Puis réinstallez la 1.3.0 si vous voulez poursuivre (`reinitialiser-essai.ps1 -Complet`, puis le guide).

**TR13 — Comparaison des moteurs (facultatif).** Créez un corpus de référence (projet coché « Corpus de
référence ») avec vos phrases d'évaluation non confidentielles. Évaluation → préparez une comparaison avec 2 ou 3
moteurs, confirmez le coût, notez les traductions. Attendu : résultats datés côte à côte, répartition de vos
notes, aucun score automatique.

**Réinitialisation (script PowerShell).** Lancez `reinitialiser-essai.ps1` une fois Argos installé. Attendu :
le script annonce que le volume `…_argos-packages` est **conservé**, demande `REINITIALISER`, redémarre avec une
base vide ; les paquets Argos sont toujours installés.

---

## Grille de résultats (à renvoyer)

| Test | Résultat | Remarques (durées, tailles, incident…) |
|---|---|---|
| TR1 Installation, version, séparation | | |
| TR2 Clé DeepL | | offre : gratuite / payante |
| TR3 Clé Google | | |
| TR4 Traduction de notice (par moteur) | | DeepL : · Google : · IA : · Argos : |
| TR5 Projet fictif | | |
| TR6 Glossaire, contrôle local | | |
| TR7 Glossaire DeepL | | |
| TR8 Argos hors ligne | | durée de construction : · taille de l'image : · durée d'un chapitre : |
| TR9 Projet confidentiel | | |
| TR10 Erreur volontaire | | n° d'incident : |
| TR11 Exports | | |
| TR12 Retour à la 1.2.0 | | |
| TR13 Comparaison (facultatif) | | |
| Script de réinitialisation | | |
