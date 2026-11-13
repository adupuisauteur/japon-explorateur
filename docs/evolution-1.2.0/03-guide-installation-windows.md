# Guide d'installation sous Windows 11 — version 1.2.0 (installation d'essai)

Ce guide installe la version 1.2.0 **à côté** de votre installation actuelle, **sans la toucher** :

| | Installation principale (actuelle) | Installation d'essai 1.2.0 |
|---|---|---|
| Adresse | http://localhost:8000 | **http://localhost:8001** |
| Nom Docker (conteneurs et volumes) | `japon-explorateur` | **`japon-explorateur-essai`** |
| Base de données | la vôtre | une base neuve, vide |
| Image Docker | `japon-explorateur:1.0` | `japon-explorateur:1.2.0` |

Aucune connaissance en programmation n'est nécessaire : il suffit de copier les commandes indiquées.

---

## Étape 0 — Sauvegarde de référence de l'installation principale (recommandée)

Cette version ne touche pas à votre installation principale. Faites tout de même une sauvegarde avant tout essai, par sécurité :

1. Ouvrez l'application principale (http://localhost:8000) → **Administration → Sauvegardes → Lancer une sauvegarde**.
2. Attendez le message « Sauvegarde terminée » et vérifiez l'intégrité.

## Étape 1 — Prérequis

- **Docker Desktop** installé et démarré : la baleine doit apparaître dans la barre des tâches, avec l'état « Engine running ».
- Docker Desktop utilise **WSL2** : *Paramètres → General → « Use the WSL 2 based engine »* doit être coché. C'est la configuration par défaut.
- Environ 3 Go d'espace disque libre.

## Étape 2 — Vérifier l'archive reçue

1. Enregistrez `japon-explorateur-1.2.0.zip` et `japon-explorateur-1.2.0.zip.sha256` dans le même dossier, par exemple `Téléchargements`.
2. Ouvrez **PowerShell** : menu Démarrer → tapez « PowerShell » → Entrée.
3. Tapez ces deux commandes, en adaptant le chemin si nécessaire :
   ```powershell
   cd $HOME\Downloads
   Get-FileHash .\japon-explorateur-1.2.0.zip -Algorithm SHA256
   ```
4. Comparez la valeur affichée (colonne *Hash*) avec celle du fichier `.sha256`, que vous pouvez ouvrir avec le Bloc-notes. **Elles doivent être identiques.** Sinon, ne continuez pas : l'archive est incomplète ou altérée.

## Étape 3 — Décompresser dans un dossier séparé

1. Clic droit sur l'archive → **Extraire tout…** → choisissez `C:\JaponExplorateur-essai-1.2.0`.
2. Vérifiez que ce dossier contient directement `docker-compose.yml`, `VERSION`, `manage.py`… S'il contient un sous-dossier, utilisez ce sous-dossier dans la suite.

> ⚠️ N'extrayez **pas** l'archive dans le dossier de votre installation principale.

## Étape 4 — Créer le fichier de configuration

Dans PowerShell :

```powershell
cd C:\JaponExplorateur-essai-1.2.0
copy .env.example .env
docker compose run --rm --no-deps web python manage.py generate_secrets
```

La première fois, la dernière commande construit l'application, ce qui prend 3 à 10 minutes. Elle affiche ensuite quatre lignes : `DJANGO_SECRET_KEY=…`, `AI_KEYS_ENCRYPTION_KEY=…`, `POSTGRES_PASSWORD=…`, `SETUP_TOKEN=…`.

Ouvrez le fichier de configuration : `notepad .env`

1. Remplacez les trois valeurs `à-remplacer…` (DJANGO_SECRET_KEY, AI_KEYS_ENCRYPTION_KEY, POSTGRES_PASSWORD) par celles qui viennent d'être affichées.
2. **Ne modifiez pas** les lignes `COMPOSE_PROJECT_NAME=japon-explorateur-essai` et `WEB_PORT=8001`. Ce sont elles qui séparent cette installation de la principale.
3. *Facultatif.* Si vous avez obtenu un identifiant CiNii (voir l'annexe), indiquez-le sur la ligne `CINII_APPID=`.
4. Enregistrez et fermez le Bloc-notes.

## Étape 5 — Démarrer

```powershell
docker compose up -d --build
```

Attendez environ une minute, puis ouvrez **http://localhost:8001** dans votre navigateur.

- L'**assistant de première configuration** s'affiche : créez le compte administrateur de cette installation d'essai. Vous pouvez reprendre les mêmes identifiants que l'installation principale ou en choisir d'autres.
- En bas de chaque page, le pied de page doit indiquer **« v1.2.0 »**.
- Le menu doit contenir **« Dysfonctionnements »**.

## Étape 6 — Contrôler que les deux installations sont bien séparées

```powershell
docker volume ls
```

Vous devez voir des volumes `japon-explorateur-essai_db-data` et `japon-explorateur-essai_app-data`, **distincts** de ceux de l'installation principale (`japon-explorateur_db-data`…).

## Opérations courantes

| Action | Commande (dans `C:\JaponExplorateur-essai-1.2.0`) |
|---|---|
| Arrêter l'essai | `docker compose stop` |
| Redémarrer | `docker compose restart` |
| Voir les messages techniques | `docker compose logs --tail 100 web` |
| Lancer les tests automatiques | `docker compose exec web python manage.py test tests` |
| Supprimer **uniquement** l'installation d'essai et ses données | `docker compose down -v` |

> ⚠️ Ne lancez `docker compose down -v` que **dans le dossier de l'essai**. Dans le dossier de l'installation principale, cette commande effacerait votre base réelle.

## Retour en arrière

L'installation principale n'ayant pas été modifiée, **aucun retour en arrière n'est nécessaire** : il suffit d'arrêter ou de supprimer l'installation d'essai.

Version de départ conservée : voir `docs/evolution-1.2.0/version-de-depart.md` (commit `7cb4075` de la version 1.1, et procédure de retour pour une future mise à niveau de l'installation principale).

## En cas de problème

1. Ouvrez **Dysfonctionnements** dans le menu : la plupart des problèmes y sont expliqués en langage courant (« origine probable »).
2. Ouvrez l'incident → **Exporter le diagnostic** → relisez l'aperçu → **Télécharger ce rapport**, puis transmettez le fichier.
3. Si la page ne s'affiche pas du tout, transmettez le résultat de `docker compose logs --tail 200 web`.

---

## Annexe — Obtenir l'identifiant CiNii (facultatif)

Le connecteur CiNii Research donne accès aux revues savantes, aux thèses et aux catalogues des bibliothèques universitaires. Il exige un **identifiant d'application gratuit**, délivré par NII :

1. Faites une demande sur la page « CiNii API利用登録 » (inscription aux API CiNii), accessible depuis https://support.nii.ac.jp/ja/cinii/api/api_outline. L'approbation peut prendre quelques jours.
2. Indiquez l'identifiant reçu dans `.env` (`CINII_APPID=…`), puis lancez `docker compose up -d`.
3. Dans l'application : **Sources → CiNii Research → Tester le connecteur**, puis cochez « Interrogé dans les recherches » dans la configuration.

Cet identifiant n'est jamais enregistré dans la base ni dans le journal : il est masqué partout.
