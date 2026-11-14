# Guide d'installation sous Windows 11 — version 1.3.0 (installation d'essai)

Ce guide installe la version 1.3.0 **à côté** de vos installations actuelles, **sans les toucher** :

| | Installation principale | Essai 1.2.0 | **Essai 1.3.0** |
|---|---|---|---|
| Adresse | http://localhost:8000 | http://localhost:8001 | **http://localhost:8002** |
| Nom Docker (conteneurs et volumes) | `japon-explorateur` | `japon-explorateur-essai` | **`japon-explorateur-essai-130`** |
| Base de données | la vôtre | celle de l'essai 1.2.0 | une base neuve, vide |
| Image Docker | `japon-explorateur:1.0` | `japon-explorateur:1.2.0` | `japon-explorateur:1.3.0` (+ `japon-explorateur-argos:1.3.0` si vous activez Argos) |
| Dossier conseillé | — | `C:\JaponExplorateur-essai-1.2.0` | **`C:\JaponExplorateur-essai-1.3.0`** |

Les conteneurs de la 1.3.0 **refusent de démarrer** sous le nom Docker de l'installation principale ou de
l'essai 1.2.0. Aucune connaissance en programmation n'est nécessaire : il suffit de copier les commandes.

---

## Étape 0 — Sauvegarde de référence (recommandée)

Cette version ne touche pas vos autres installations. Faites tout de même une sauvegarde de l'installation
principale par sécurité : http://localhost:8000 → **Administration → Sauvegardes → Lancer une sauvegarde**, puis
vérifiez l'intégrité.

## Étape 1 — Prérequis

- **Docker Desktop** démarré (« Engine running »), moteur **WSL2** (configuration par défaut).
- Environ 4 Go d'espace disque libre ; **2 à 4 Go de plus** si vous activez Argos Translate (image PyTorch et
  paquets de langues — taille exacte à mesurer lors du protocole).

## Étape 2 — Vérifier l'archive reçue

1. Enregistrez `japon-explorateur-1.3.0.zip` et `japon-explorateur-1.3.0.zip.sha256` dans le même dossier.
2. Dans **PowerShell** :
   ```powershell
   cd $HOME\Downloads
   Get-FileHash .\japon-explorateur-1.3.0.zip -Algorithm SHA256
   ```
3. La valeur affichée doit être **identique** à celle du fichier `.sha256` (ouvrez-le avec le Bloc-notes).
   Sinon, ne continuez pas.

## Étape 3 — Décompresser dans un dossier séparé

Clic droit sur l'archive → **Extraire tout…** → `C:\JaponExplorateur-essai-1.3.0`. Le dossier doit contenir
directement `docker-compose.yml`, `VERSION`, `manage.py`… (sinon, utilisez le sous-dossier).

> ⚠️ N'extrayez **pas** l'archive dans le dossier de l'installation principale ni dans celui de l'essai 1.2.0,
> et ne copiez pas le `.env` de l'essai 1.2.0.

## Étape 4 — Créer le fichier de configuration

```powershell
cd C:\JaponExplorateur-essai-1.3.0
copy .env.example .env
docker compose run --rm --no-deps web python manage.py generate_secrets
```

La première fois, la dernière commande construit l'application (3 à 10 minutes), puis affiche quatre lignes
(`DJANGO_SECRET_KEY=…`, `AI_KEYS_ENCRYPTION_KEY=…`, `POSTGRES_PASSWORD=…`, `SETUP_TOKEN=…`).
Ouvrez `notepad .env` :

1. Remplacez les trois valeurs `à-remplacer…` par celles affichées.
2. **Ne modifiez pas** `COMPOSE_PROJECT_NAME=japon-explorateur-essai-130` ni `WEB_PORT=8002`.
3. Les clés DeepL et Google **ne se mettent pas ici** : elles se saisissent dans l'application (notices
   `notice-cle-deepl.md` et `notice-cle-google.md`).
4. Enregistrez et fermez.

## Étape 5 — Démarrer

```powershell
docker compose up -d --build
```

Après environ une minute, ouvrez **http://localhost:8002** : créez le compte administrateur dans l'assistant.
Le pied de page indique **« v1.3.0 »** et le menu contient **« Traduction »**.

### Facultatif — Argos Translate (traduction hors ligne)

```powershell
docker compose --profile hors-ligne up -d --build
```

Voir `notice-argos.md` : les paquets de langues ne sont téléchargés que si vous le décidez dans l'application.

## Étape 6 — Contrôler la séparation

```powershell
docker volume ls
```

Les volumes `japon-explorateur-essai-130_db-data`, `…_app-data`, `…_argos-depot` (et `…_argos-packages` si Argos
est activé) sont **distincts** de ceux de l'installation principale et de l'essai 1.2.0.

## Opérations courantes (dans `C:\JaponExplorateur-essai-1.3.0`)

| Action | Commande |
|---|---|
| Arrêter l'essai | `docker compose --profile hors-ligne stop` |
| Redémarrer | `docker compose restart` (ajoutez `--profile hors-ligne` si Argos est utilisé) |
| Messages techniques | `docker compose logs --tail 100 web` ; worker : `… logs --tail 100 worker` ; Argos : `docker compose --profile hors-ligne logs --tail 100 argos` |
| Tests automatiques | `docker compose exec web python manage.py test tests` |
| Réinitialiser l'essai (base vide ; paquets Argos conservés) | `powershell -ExecutionPolicy Bypass -File .\reinitialiser-essai.ps1` |
| Réinitialisation complète (paquets Argos et images compris) | `powershell -ExecutionPolicy Bypass -File .\reinitialiser-essai.ps1 -Complet` |

> ⚠️ N'utilisez `docker compose down -v` que dans le dossier de l'essai, jamais dans celui de l'installation
> principale. Préférez le script de réinitialisation, qui contrôle le nom du projet et le port avant d'effacer.

## Retour en arrière

Vos autres installations n'étant pas modifiées, il suffit d'arrêter ou de réinitialiser l'essai 1.3.0. Pour
ramener une base 1.3.0 à la 1.2.0 (test TR12), suivez `retour-1.2.0.md`.

## En cas de problème

1. **Dysfonctionnements** dans le menu : les erreurs de traduction y sont classées dans le module « traduction »
   (clé refusée, quota, paquet Argos absent…), sans aucun texte ni clé.
2. Ouvrez l'incident → **Exporter le diagnostic**, puis transmettez le fichier.
3. Si la page ne s'affiche pas, transmettez `docker compose logs --tail 200 web`.
