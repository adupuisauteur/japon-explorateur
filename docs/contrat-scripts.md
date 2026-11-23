# Contrat des scripts Windows (depuis la 2.0.2)

L'assistant J-ed (`J-ed.cmd`, version 2.0.2) ne refait aucune opération lui-même : il lance les scripts
PowerShell ci-dessous et lit ce qu'ils rendent. Ce document fixe ce dont il dépend. **Une version suivante ne doit
rien retirer ni renommer de cette liste** : elle peut ajouter des paramètres facultatifs, des codes ou des
repères, à condition de mettre ce document à jour. C'est le cas de la version Linux (2.0.3), qui déplacera la
logique des scripts dans des commandes J-ed en gardant des lanceurs `.ps1` aux mêmes noms.

Les tests `tests/test_contrat_scripts.py` vérifient que les scripts et ce document restent d'accord.

## Règles communes

- Fichiers à la racine du dossier de J-ed, encodés en UTF-8 avec BOM et fins de ligne CRLF, lancés par
  `powershell -ExecutionPolicy Bypass -File <script> …` (Windows PowerShell 5.1).
- Aucun script ne supprime de volume Docker (`down -v` interdit).

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
construction de la nouvelle version (étape 6).

**Empreinte** : sans `-Empreinte`, le fichier est cherché à côté de l'archive (`<archive>.sha256`, puis
`<nom sans .zip>.sha256`).

## `verifier-j-ed.ps1`

Paramètres : `-Dossier`, `-AvecSources`, `-AvecTests`. Codes de sortie : 0 tout va bien (avertissements
possibles), 1 au moins une erreur. Aucune question. Le chemin du rapport est écrit sur la sortie, dans une ligne qui commence par
`Rapport enregistré : ` (l'assistant propose de l'ouvrir).

## `verifier-migration.ps1`

Paramètre : `-Dossiers`. Codes de sortie : 0 tout va bien, 1 au moins une erreur. Aucune question.

## `reinitialiser-essai.ps1`

Paramètres : `-Complet`, `-SansSauvegarde`. Codes de sortie : 0 terminé ou abandonné sans rien effacer, 1 refus
ou erreur. Questions à l'écran (sauvegarde `O/N`, puis saisie de `REINITIALISER`) : leur pilotage par l'assistant
est prévu avec les opérations de maintenance de la 2.0.2. Refuse de s'exécuter hors d'une installation d'essai.
