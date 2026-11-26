# Contrat des scripts (Windows depuis la 2.0.2, Windows et Linux depuis la 2.0.3)

L'assistant J-ed (`J-ed.cmd`, version 2.0.2) ne refait aucune opération lui-même : il lance les scripts
PowerShell ci-dessous et lit ce qu'ils rendent. Ce document fixe ce dont il dépend. **Une version suivante ne doit
rien retirer ni renommer de cette liste** : elle peut ajouter des paramètres facultatifs, des codes ou des
repères, à condition de mettre ce document à jour.

**Depuis la 2.0.3 (décision D1 du 26 novembre 2026), ce contrat est commun à Windows et à Linux** : ce sont les
**mêmes fichiers `.ps1`** qui servent sur les deux systèmes (un seul programme à entretenir), et non deux
programmes. Sous Linux, ils sont lancés par PowerShell 7 ; le menu texte de Linux (2.0.3) s'appuie, comme la
fenêtre Windows, sur le module `assistant/AssistantJed.psm1`. L'idée de la note du 19/11 (logique déplacée dans
des commandes J-ed, dans le conteneur) est abandonnée : la mise à jour se fait hors du conteneur, qui devrait
sinon recevoir le socket de Docker, c'est-à-dire tous les droits sur la machine.

Les tests `tests/test_contrat_scripts.py` vérifient que les scripts et ce document restent d'accord.

## Règles communes

- Fichiers à la racine du dossier de J-ed, encodés en UTF-8 avec BOM et fins de ligne CRLF (PowerShell 7 les
  lit aussi sous Linux).
- **Windows** : lancés par `powershell -ExecutionPolicy Bypass -File <script> …` (Windows PowerShell 5.1).
- **Linux** (depuis la 2.0.3) : lancés par `pwsh -NoProfile -File <script> …` (PowerShell 7 ; essai réel avec
  la 7.6.10 sur Ubuntu 26.04 LTS, le 26/11/2026), avec le passage des arguments par défaut de PowerShell 7 sous
  Linux. Les formats `docker … --format` restent écrits sans guillemets imbriqués, ce qui convient aux deux.
- Ce qui diffère selon le système est choisi **dans le même fichier**, par la variable `$SousLinux`, lue sans
  erreur sous Windows PowerShell 5.1 (où `$IsLinux` n'existe pas) :
  `$SousLinux = ((Get-Variable -Name IsLinux -ValueOnly -ErrorAction SilentlyContinue) -eq $true)`. Seuls des
  textes (messages, conseils) et des réglages propres à Linux en dépendent ; noms, paramètres, codes de sortie,
  repères du journal et questions sont les mêmes.
- **Proxy de la commande `docker` (Linux, 2.0.3)** : pendant une construction, la commande `docker` elle-même
  demande un jeton d'accès à Docker Hub et ne lit pas le proxy du service Docker (`/etc/docker/daemon.json`).
  `installer-j-ed.ps1` (paramètre `-Proxy`) et `mettre-a-jour.ps1` (`HTTPS_PROXY`, sinon `HTTP_PROXY`, du `.env`
  de l'installation actuelle) le donnent alors aux commandes qu'ils lancent (variables `HTTP_PROXY`,
  `HTTPS_PROXY`, et `NO_PROXY=localhost,127.0.0.1` s'il est vide), pour le seul script ; un proxy déjà réglé dans
  le terminal est gardé. Rien ne change sous Windows (Docker Desktop s'en charge).
- Aucun script ne supprime de volume Docker (`down -v` interdit).

## Linux : lanceur, menu et contrôles (depuis la 2.0.3, lot 1)

- **`j-ed.sh`** (racine du dossier de J-ed, bash, fins de ligne LF, exécutable) : refuse root, vérifie que
  PowerShell 7 (`pwsh`) est installé, puis lance **`assistant/menu-j-ed.ps1`** par `pwsh -NoProfile -File`. Se lance
  par `bash <dossier de J-ed>/j-ed.sh`.
- **`assistant/menu-j-ed.ps1`** : menu texte « jumeau » de la fenêtre Windows (décision D2), mêmes fonctions, mêmes
  noms, même ordre ; il s'appuie sur le même module `assistant/AssistantJed.psm1` et lance les scripts ci-dessous
  exactement comme la fenêtre (mêmes paramètres, mêmes codes, même journal). Réponses lisibles depuis l'entrée
  standard (tests) ; fin de l'entrée : il se ferme (code 0). Refuse root (code 1) et ne sert que sous Linux.
- **Refus de root** (décision D4) : sous Linux, `installer-j-ed.ps1` s'arrête (code 1, rien n'est créé) et
  `verifier-j-ed.ps1` aussi (code 1) quand ils sont lancés en root.
- **Dossier des sauvegardes** (décision D5) : sous Linux, J-ed copie lui-même chaque sauvegarde dans ce dossier
  depuis son conteneur (utilisateur 1000). `installer-j-ed.ps1` écrit un avertissement (repère `ATTENTION`, pas un
  arrêt) et `verifier-j-ed.ps1` une ligne « À surveiller » quand cet utilisateur ne peut pas y écrire, avec la
  commande qui le permet (`chmod o+rwx <dossier>`).
- Réglages **réservés aux tests automatiques** : `JED_UID_ACTUEL` (numéro de l'utilisateur, pour simuler root ou
  non) et `JED_UID_CONTENEUR` (numéro de l'utilisateur du conteneur, 1000 par défaut).

## `mettre-a-jour.ps1`

**Paramètres**

| Paramètre | Rôle |
| --- | --- |
| `-Archive` | archive `.zip` de la nouvelle version (obligatoire) |
| `-Empreinte` | fichier `.sha256` de l'archive, s'il n'est pas à côté d'elle (facultatif, depuis 2.0.2) |
| `-Actuel` | dossier de l'installation actuelle (obligatoire) |
| `-Destination` | dossier de la nouvelle version (facultatif) |
| `-DossierSauvegardes` | dossier des sauvegardes et du journal (facultatif) |
| `-Oui` | pas de question avant l'arrêt de l'ancienne version |
| `-DelaiControle` | secondes laissées au contrôle final (300 par défaut) |
| `-DelaiStabilite` | secondes entre les deux interrogations de la page de santé (15 par défaut) |

**Codes de sortie**

| Code | Sens |
| --- | --- |
| 0 | mise à jour réussie |
| 1 | arrêt pendant les contrôles, la sauvegarde, la décompression ou la reprise du `.env` : rien n'a changé |
| 2 | annulée à la demande (pas de `OUI`) : ancienne version toujours en service |
| 3 | construction de la nouvelle version impossible : ancienne version toujours en service |
| 4 | nouvelle version en échec, retour à l'ancienne réussi |
| 5 | nouvelle version en échec et retour impossible : intervention nécessaire |

**Journal** : fichier `mise-a-jour-AAAAMMJJ-HHMMSS.log` dans le dossier des sauvegardes ; son chemin est écrit
sur la sortie, dans une ligne qui commence par `Journal de la mise à jour : `. Chaque ligne a la forme
`AAAA-MM-JJ HH:MM:SS REPERE texte` ; une ligne de suite commence par quatre espaces et `| `. Repères :

| Repère | Sens |
| --- | --- |
| `ETAPE` | début d'une étape, texte `n/7 titre` |
| `INFO` | information |
| `ATTENTION` | avertissement |
| `COMMANDE` | commande lancée |
| `RESULTAT` | résultat d'une commande, texte `code=n …` |
| `ERREUR` | erreur |
| `QUESTION` | le script attend une réponse (depuis 2.0.2) |
| `REPONSE` | réponse reçue : `OUI` ou `refus` (depuis 2.0.2) |
| `FIN` | dernière ligne, texte `code=n sens` |

**Confirmation** : sans `-Oui`, le script écrit le repère `QUESTION` puis attend une ligne. Si l'entrée standard
est fournie par un programme (l'assistant), la réponse y est lue ; sinon elle est demandée à l'écran. Seul `OUI`
continue ; toute autre réponse, ou l'absence de réponse, annule (code 2). La question vient toujours **après** la
construction de la nouvelle version (étape 6). Depuis la 2.0.2-rc5, quand la réponse vient d'un programme, la
question n'est pas affichée sur la sortie (l'assistant la pose dans sa propre fenêtre) ; le script écrit ensuite
« Confirmation donnée dans l'assistant J-ed … » ou « Confirmation refusée dans l'assistant J-ed. ». L'assistant
lit l'étape en cours dans le journal (repère `ETAPE`) au moment de la question.

**Empreinte** : sans `-Empreinte`, le fichier est cherché à côté de l'archive (`<archive>.sha256`, puis
`<nom sans .zip>.sha256`).

## `verifier-j-ed.ps1`

Paramètres : `-Dossier`, `-AvecSources`, `-AvecTests`. Codes de sortie : 0 tout va bien (avertissements
possibles), 1 au moins une erreur. Aucune question. Le chemin du rapport est écrit sur la sortie, dans une ligne qui commence par
`Rapport enregistré : ` (l'assistant propose de l'ouvrir).

## `verifier-migration.ps1`

Paramètre : `-Dossiers`. Codes de sortie : 0 tout va bien, 1 au moins une erreur. Aucune question.

## `reinitialiser-essai.ps1`

Paramètres : `-Complet`, `-SansSauvegarde`. Codes de sortie : 0 terminé ou abandonné sans rien effacer (ligne
commençant par `Annulé`), 1 refus ou erreur. Questions : sauvegarde `O/N` (seulement sans `-SansSauvegarde` et si
l'essai est démarré), puis saisie de `REINITIALISER`. Depuis la 2.0.2, quand l'entrée standard est fournie par un
programme, les réponses y sont lues ; l'assistant passe toujours `-SansSauvegarde` (il fait la sauvegarde lui-même
avant) et répond `REINITIALISER`. Refuse de s'exécuter hors d'une installation d'essai ; agit sur SON dossier
(celui du script) : l'assistant lance toujours le script du dossier de l'installation choisie. Avec `-Complet`,
les images ne sont supprimées que si aucune autre installation de J-ed n'existe sur l'ordinateur (2.0.2), et
l'essai reste arrêté. Depuis la 2.0.2-rc5 : sortie en UTF-8 comme les autres scripts ; quand les réponses viennent
d'un programme, les questions ne sont pas affichées (ligne « Réponse donnée dans l'assistant J-ed. ») et les
consignes de fin du mode complet renvoient au bouton « Démarrer » de l'assistant.

## `installer-j-ed.ps1` (depuis la 2.0.2)

Paramètres : `-Archive`, `-Empreinte`, `-Destination`, `-Nom`, `-Port`, `-DossierSauvegardes`, `-Proxy`,
`-SansArgos`, `-DelaiControle`, `-DelaiStabilite`. Codes de sortie : 0 installation réussie, 1 arrêt pendant les
contrôles (rien créé), 3 construction impossible (dossier créé, rien démarré), 5 J-ed ne démarre pas ou ne répond
pas. Journal `installation-AAAAMMJJ-HHMMSS.log` (dossier des sauvegardes, sinon à côté du nouveau dossier), mêmes
repères que la mise à jour ; son chemin est écrit dans une ligne qui commence par `Journal de l'installation : `.
Aucune question. Ne touche jamais à une autre installation : nom et port neufs contrôlés, secrets neufs.

## Commande J-ed `mot_de_passe_oublie` (depuis la 2.0.2)

Lancée par `docker compose exec -T web python manage.py mot_de_passe_oublie` : `--liste` (comptes en JSON :
`identifiant`, `nom`, `role`, `actif`) ou `--utilisateur <identifiant>` avec le nouveau mot de passe sur l'entrée
standard (jamais en argument). Code 0 : changé ; 1 : refusé (règles de mot de passe), compte introuvable.
