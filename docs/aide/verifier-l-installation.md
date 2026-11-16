---
titre: Vérifier l'installation
rubrique: Installation et mises à jour
ordre: 20
public: admin
ecrans: core:argos_selftest
resume: La page « État de l'installation » et le script verifier-j-ed.ps1 : lire leurs résultats.
---
Deux outils, à utiliser après chaque installation ou mise à jour, et dès qu'un doute apparaît.

## La page « État de l'installation »

Menu à votre nom → **Administration → État de l'installation**. Une ligne par élément :

| Ligne | Ce qui est contrôlé |
| --- | --- |
| Version, base de données | La version en service et des migrations à jour |
| Redis, workers, planificateur | Les tâches de fond peuvent tourner (le planificateur passe à « Correct » dans les 5 minutes) |
| Argos | Le service répond, ses paquets japonais → français sont installés, la dernière traduction d'essai |
| IA locale | Le service répond, les modèles installés, le dernier résumé d'essai (ligne absente si l'IA locale n'est pas installée) |
| Sauvegardes | La dernière sauvegarde et sa vérification |
| Clés, disque, ressources | La clé de chiffrement, la place libre, la mémoire et les cœurs accordés par Docker |
| Profil de la machine | Le profil retenu et un conseil |

Chaque ligne est **Correct**, **À surveiller**, **Problème** ou **Non vérifiable**, avec le détail.
**Copier le diagnostic** donne un texte à transmettre, sans clé, sans nom de compte et sans aucun texte de recherche
ou de traduction.

## Le script verifier-j-ed.ps1

Il contrôle tout depuis Windows, dans le dossier de l'installation :

```
cd C:\J-ed\japon-explorateur-2.0.0
powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1
```

1. **Dossier et `.env`** : version, nom de l'installation, mots de passe renseignés, dossier des sauvegardes, lignes en
   double.
2. **Docker et conteneurs** : les conteneurs attendus sont en service (Argos, et l'IA locale si elle est prévue).
3. **Adresse** : les pages répondent.
4. **Fonctions de l'application** : chaque fonction est essayée avec des **données fictives**, sans modifier votre
   base.

| Repère | Signification |
| --- | --- |
| `[OK]` | Tout va bien |
| `[À surveiller]` | Fonctionne, mais un point mérite attention (le détail dit lequel) |
| `[Problème]` | À corriger : le détail dit quoi faire |
| `[Non vérifié]` | Contrôle non fait (option non demandée, élément facultatif absent) |

Un rapport `verification-j-ed-….txt` est enregistré dans le dossier parent. Il ne contient ni clé, ni nom de compte,
ni texte de recherche ou de traduction : vous pouvez le transmettre tel quel.

Options : `-AvecSources` (une recherche d'essai par source, sur Internet), `-AvecTests` (la suite de tests
automatiques, 3 à 10 minutes).

## Mesurer la rapidité

Si J-ed vous paraît lent, une commande mesure la recherche, la détection des doublons et les pages principales. Dans
PowerShell, depuis le dossier de J-ed :

```
docker compose exec web python manage.py mesurer_performances
```

Elle crée une **base temporaire** remplie de 50 000 notices fictives, mesure, puis supprime cette base (comptez
quelques minutes). Sur vos propres données, elle ne fait que des recherches en lecture seule. Le résultat donne,
pour chaque mesure, la durée en millisecondes et le nombre de requêtes à la base. Option `--notices 10000` pour un
essai plus court.
