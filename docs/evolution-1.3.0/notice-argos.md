# Notice — Installer Argos Translate et ses paquets de langues (version 1.3.0)

Argos Translate est le moteur de traduction **hors ligne** du module : il traduit sur votre ordinateur, sans
envoyer de texte sur Internet. Il est **facultatif** et fonctionne dans un service Docker séparé, qui ne
concerne que l'installation d'essai 1.3.0 (projet `japon-explorateur-essai-130`, port 8002).

> Statut : service **développé et testé en simulation** (traducteur factice, bibliothèque Argos imitée).
> La construction de l'image, sa taille réelle, le téléchargement des paquets et la traduction réelle,
> y compris connexion Internet coupée (protocole TR8), sont **à vérifier sur votre poste**.

## 1. Démarrer le service

Dans le dossier de l'installation d'essai (PowerShell) :

```powershell
docker compose --profile hors-ligne up -d --build
```

- La première construction télécharge PyTorch « CPU » et Argos Translate (plusieurs centaines de Mo,
  plusieurs minutes). Elle ne touche ni l'installation principale ni l'essai 1.2.0.
- Le service n'a **aucun port publié** : seule l'application peut le joindre.
- Sans ce profil, `docker compose up -d` démarre l'application comme avant, sans Argos ; Argos est alors
  en **mode simulé** (mention « Simulation » sur chaque résultat, aucune traduction réelle).

Arrêter le seul service Argos : `docker compose --profile hors-ligne stop argos`.

## 2. Installer les paquets de langues — c'est vous qui choisissez

Ouvrez **Traduction → Moteurs → Service et paquets de langues** (page « Moteurs locaux »). Les paquets sont
communs à toute l'installation : seul un administrateur peut les gérer.

Il n'existe pas de paquet direct japonais → français : la traduction passe par l'anglais.

| Paire | Paquets nécessaires |
|---|---|
| japonais → français | ja→en et en→fr |
| anglais → français | en→fr |

### a) Depuis l'index Argos (Internet)

1. « Consulter l'index Argos » : le service lit la liste des paquets proposés. **Rien n'est téléchargé.**
2. Cochez les paquets voulus (les paquets utiles sont présélectionnés), puis la case de confirmation, et
   cliquez sur « Télécharger et installer ».
3. Suivez la progression dans « Installations récentes ». En cas d'interruption (coupure, arrêt de
   Docker), cliquez sur « Reprendre » : un paquet déjà installé n'est pas téléchargé de nouveau.

Le modèle de découpage en phrases éventuellement nécessaire (MiniSBD, quelques Mo) est récupéré pendant
cette même installation.

### b) Depuis un fichier (sans Internet)

1. Sur un ordinateur relié à Internet, téléchargez le fichier `.argosmodel` du paquet (index Argos :
   https://www.argosopentech.com/argospm/index/).
2. Dans « Installer depuis un fichier », choisissez le fichier et cliquez sur « Installer ».

Si le paquet ne contient pas son modèle de découpage en phrases, la page l'indique (« modèle de découpage
en phrases manquant ») : ce paquet ne pourra pas traduire tant que vous n'aurez pas cliqué sur
« Télécharger » à côté de lui (Internet, sur votre choix). La traduction, elle, **n'utilise jamais
Internet** : elle est refusée avec un message clair plutôt que de télécharger quoi que ce soit.

## 3. Utiliser Argos

Dans **Traduction → Moteurs**, activez Argos et choisissez-le comme moteur. Avec les paquets installés, son
état passe à « Disponible hors ligne ». La version des paquets utilisés est enregistrée avec chaque
traduction (par exemple « Argos 1.11.0 — ja→en 1.1 ; en→fr 1.9 »). Argos est le seul moteur accepté pour
un projet confidentiel.

## 4. Réinitialiser l'essai

`reinitialiser-essai.ps1` **conserve les paquets** (volume `japon-explorateur-essai-130_argos-packages`) ;
seul `-Complet` les efface, avec les images Docker de l'essai. Si le service Argos était démarré, il
redémarre avec ses paquets.

## 5. En cas de problème

| Message | Que faire |
|---|---|
| « service Argos injoignable — démarré avec le profil Docker « hors-ligne » ? » | Lancer la commande du § 1. |
| « paquets de langues nécessaires non installés » | Installer les paquets du § 2. |
| « modèle de découpage en phrases manquant » | Cliquer sur « Télécharger » à côté du paquet (Internet). |
| « Index des paquets Argos injoignable » | Vérifier la connexion, ou installer depuis un fichier. |

Journal du service : `docker compose --profile hors-ligne logs --tail 100 argos` (il ne contient jamais
de texte traduit ou original).
