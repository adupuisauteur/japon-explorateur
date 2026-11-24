---
titre: Mettre à jour J-ed
rubrique: Installation et mises à jour
ordre: 10
public: admin
resume: Passer à une nouvelle version sans rien perdre, avec le script de mise à jour.
---
Une mise à jour **garde toutes vos données** : notices, bibliothèque, projets, glossaires, comptes, clés, paquets
Argos et modèles de l'IA locale. Le **guide de mise à jour** livré avec chaque version détaille chaque étape.

**Le plus simple (depuis la 2.0.2) : l'assistant J-ed.** Double-cliquez sur `J-ed.cmd` (ou sur le raccourci
« Assistant J-ed »), choisissez votre installation, puis **Mettre à jour une installation** : l'assistant fait tout
ce qui est décrit ci-dessous, et vous demande de confirmer au bon moment (aide [L'assistant J-ed](aide:assistant-j-ed)).
La suite de cette page décrit la même mise à jour en ligne de commande, avec le script `mettre-a-jour.ps1`.

## Ce qu'il faut

- Docker Desktop démarré, et J-ed en marche (sa page s'ouvre dans le navigateur).
- Environ 5 Go d'espace disque libre.
- Les trois fichiers de la nouvelle version, dans le **dossier parent** de l'installation (par exemple `C:\J-ed`) :
  l'archive `.zip`, son empreinte `.zip.sha256`, et `mettre-a-jour.ps1`.
- Un accès Internet **pour Docker** : la nouvelle version est construite à partir d'éléments téléchargés (Docker Hub
  et bibliothèques Python).

### Vérifier l'accès Internet de Docker avant de commencer

Depuis la 2.0.1, le script construit la nouvelle version **pendant que l'ancienne reste en service**. Si Docker ne
peut pas télécharger, le script s'arrête sans avoir rien arrêté : J-ed continue de fonctionner. La vérification
reste utile pour savoir avant de commencer si la mise à jour pourra aboutir. Dans PowerShell :

```
docker pull python:3.12-slim-bookworm
```

[Résultat attendu : l'image se télécharge, ou « Image is up to date ». Un message contenant « deadline exceeded » ou
« connecting to … » veut dire que Docker ne joint pas Internet : réglez d'abord ce point (proxy, ci-dessous).]

**Derrière un proxy** (réseau d'entreprise ou d'établissement), déclarez-le dans Docker Desktop : Settings →
Resources → Proxies → « Manual proxy configuration », la même adresse (par exemple `http://10.0.0.1:3128`) dans les
champs HTTP et HTTPS, et `localhost,127.0.0.1,db,redis,argos,ollama,web` dans le champ des exceptions, puis « Apply &
restart ». Docker Desktop ne sait pas lire un fichier de configuration automatique (PAC) : il faut l'adresse réelle du
proxy, que votre service informatique peut vous donner. Refaites ensuite la vérification ci-dessus.

## Toujours le script de la nouvelle version

Le script `mettre-a-jour.ps1` évolue avec J-ed. **À chaque mise à jour, remplacez celui du dossier parent** par celui
livré avec la nouvelle version (ou par celui du nouveau dossier, après la mise à jour). Un ancien script garde ses
anciens défauts. Par exemple, une version de novembre 2026 ajoutait une ligne `COMPOSE_PROFILES=hors-ligne` au
fichier `.env` à chaque passage.

Le script le signale lui-même : « Attention : ce script de mise à jour n'est pas celui de l'archive », puis un
rappel à la fin.

## La méthode

1. Récupérez les trois fichiers de la nouvelle version et placez-les dans le dossier parent de l'installation
   (ci-dessus).
2. Vérifiez que Docker Desktop est démarré et que J-ed s'ouvre dans le navigateur.
3. Lancez le script (commandes ci-dessous). Il vérifie l'archive, fait une **sauvegarde vérifiée** copiée dans votre
   dossier de sauvegardes, installe la nouvelle version dans un **nouveau dossier** (l'ancien n'est jamais modifié)
   et reprend votre `.env`. Il **construit** ensuite la nouvelle version pendant que l'ancienne reste en service
   (plusieurs minutes la première fois). Il demande enfin de taper `OUI` avant d'arrêter l'ancienne version et de
   démarrer la nouvelle.
4. Vérifiez la nouvelle version, puis gardez l'ancien dossier quelques semaines : il permet de revenir en arrière.

## Les commandes

Dans PowerShell (clic droit sur Démarrer → Terminal). L'exemple passe de la 2.0.0 à la 2.0.1 ; remplacez les
numéros et les chemins par les vôtres.

```
cd C:\J-ed
```

Puis :

```
powershell -ExecutionPolicy Bypass -File .\mettre-a-jour.ps1 -Archive .\japon-explorateur-2.0.1.zip -Actuel C:\J-ed\japon-explorateur-2.0.0 -DossierSauvegardes C:\J-ed\sauvegardes
```

- `-Archive` : l'archive de la nouvelle version.
- `-Actuel` : le dossier de la version **actuellement installée** (celui qui contient `.env`). Si vous ne le
  retrouvez plus, la commande `docker compose ls` l'indique dans la colonne CONFIG FILES.
- `-DossierSauvegardes` : le dossier où copier la sauvegarde faite avant la mise à jour, en dehors des dossiers
  d'installation.
- `-Destination` (facultatif) : le nouveau dossier, si celui proposé par défaut (`C:\J-ed\japon-explorateur-2.0.1`)
  existe déjà.
- `-Empreinte` (facultatif, depuis la 2.0.2) : le fichier `.sha256` de l'archive, s'il n'est pas rangé à côté
  d'elle.

[Résultat attendu, à la fin : « Mise à jour terminée : J-ed 2.0.1, http://localhost:8000 ».]

À la moindre anomalie, le script s'arrête avec un message qui commence par **ARRÊT** et dit quoi faire. Avant
l'étape `OUI`, l'installation actuelle n'a pas été touchée.

## Si la nouvelle version ne démarre pas : retour automatique

Depuis la 2.0.1, si la nouvelle version ne démarre pas ou ne répond pas au contrôle final, le script **revient tout
seul à l'ancienne version**. Le contrôle final vérifie la version, la base de données, puis que le serveur web
répond vraiment : deux fois de suite, à quelques secondes d'intervalle. Le retour automatique : il arrête la nouvelle, puis redémarre l'ancienne depuis l'ancien dossier. Vos données
ne sont pas touchées. Il affiche alors « Retour réussi : l'ancienne version … est de nouveau en service ».

Le retour vérifie que l'ancienne version répond de nouveau. Quand l'ancienne et la nouvelle version portent le même
numéro (réinstallation), le script a mis de côté les images de l'ancienne sous un nom de réserve qui se termine par
`-avant-maj`, pour pouvoir les remettre : ce nom reste ensuite dans la liste des images de Docker, c'est normal.

Si ce retour échoue lui aussi (cas rare), le script affiche les lignes « Pour remettre l'ancienne version en
service » : `docker compose down` dans le **nouveau** dossier, puis `docker compose up -d` dans l'**ancien**.

Ce comportement est celui du script **de la 2.0.1 ou plus récent** : c'est une raison de plus pour toujours
utiliser le script de la nouvelle version (plus haut).

## Le journal de la mise à jour

Chaque mise à jour écrit un journal dans le dossier des sauvegardes, par exemple
`C:\J-ed\sauvegardes\mise-a-jour-20261120-143000.log`. Son chemin est affiché au début et à la fin. Il contient
chaque étape, chaque commande Docker et sa réponse. Il ne contient jamais vos mots de passe ni vos clés. En cas de
problème, gardez-le : il permet de comprendre ce qui s'est passé.

Le script se termine par un **code de sortie**, écrit aussi à la dernière ligne du journal (`FIN code=…`) :

| Code | Ce qui s'est passé | État de J-ed |
| --- | --- | --- |
| 0 | Mise à jour réussie | Nouvelle version en service |
| 1 | Arrêt pendant les contrôles, la sauvegarde, la décompression ou la reprise du `.env` | Ancienne version en service, rien de modifié |
| 2 | Mise à jour annulée (réponse autre que `OUI`) | Ancienne version en service |
| 3 | Construction de la nouvelle version impossible (le plus souvent : pas d'accès Internet pour Docker) | Ancienne version en service |
| 4 | La nouvelle version n'a pas démarré correctement ; retour automatique réussi | Ancienne version en service |
| 5 | La nouvelle version n'a pas démarré correctement et le retour a échoué | Arrêtée : suivez les lignes affichées |

Après un code 1, 2, 3 ou 4, le nouveau dossier (par exemple `C:\J-ed\japon-explorateur-2.0.1`) peut être supprimé
avant de relancer le script : celui-ci refuse d'écrire dans un dossier qui existe déjà.

**Installation au nom protégé** (`japon-explorateur` ou `japon-explorateur-essai`) : son `.env` doit contenir
`AUTORISER_NOM_PROJET=` suivi du même nom, sinon le script s'arrête. Il n'ajoute jamais cette ligne de lui-même.

## Après la mise à jour

Ouvrez J-ed et rechargez la page avec **Ctrl + F5** : le pied de page indique la nouvelle version.

Vérifiez ensuite l'installation depuis le **nouveau** dossier :

```
cd C:\J-ed\japon-explorateur-2.0.1
```

Puis :

```
powershell -ExecutionPolicy Bypass -File .\verifier-j-ed.ps1
```

[Résultat attendu : aucune ligne « [Problème] ». Voir aussi [Vérifier l'installation](aide:verifier-l-installation).]

- En cas de souci : [Dépannage après une mise à jour](aide:depannage-apres-mise-a-jour).
- Pour essayer les nouveautés sans toucher à vos données : [Essayer J-ed](aide:essayer-j-ed), avec le jeu d'essai.

Gardez l'ancien dossier quelques semaines : il permet de revenir en arrière. La procédure de retour est dans le
guide de mise à jour.
