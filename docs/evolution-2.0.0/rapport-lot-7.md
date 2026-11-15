# J-ed 2.0.0 — Rapport du lot 7 : Argos installé par défaut

15 novembre 2026 · branche `evolution-2.0.0` · plan : `01-audit.md`, § 3.8 · cahier des charges : § 9 bis

## 1. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Démarrage par défaut | Le service `argos` porte les profils `argos` et `hors-ligne`. La ligne `COMPOSE_PROFILES=argos` de `.env.example` le démarre avec J-ed, sans option à taper. Laissée vide (`COMPOSE_PROFILES=`), elle le désactive. L'ancienne valeur `hors-ligne` reste acceptée | `docker-compose.yml`, `.env.example` |
| Mise à jour | `mettre-a-jour.ps1` ajoute `COMPOSE_PROFILES=argos` seulement si la ligne manque. Une ligne existante n'est jamais modifiée ni doublée ; vide, elle est respectée (message). Le démarrage n'utilise plus `--profile` : le `.env` décide | `mettre-a-jour.ps1` |
| Vérification | `verifier-j-ed.ps1` : profil `argos` ou `hors-ligne` = conteneur attendu ; ligne absente = « À surveiller » ; ligne vide = « désactivé volontairement » | `verifier-j-ed.ps1` |
| Bouton unique | « Installer la traduction japonais → français » : taille annoncée (environ 200 Mo), case de confirmation, puis une seule tâche suivie en base avec les paquets manquants (ja→en, en→fr). La tâche est reprenable ; un paquet déjà installé n'est pas retéléchargé. Argos est activé dans les moteurs de l'utilisateur. Une installation en cours bloque un second lancement | `apps/translation/argos_packages.py`, `views/local_engines.py` |
| Fin d'installation | Traduction d'essai d'une phrase fictive : « Argos prêt » ou le message d'erreur précis, affiché dans « Service » et sur la page « État ». Fenêtre de notification « Terminé », « Échec » ou « l'essai a échoué » | `argos_packages.py` |
| Invitations | Encadré commun : Traduction → Moteurs (carte Argos), Moteurs locaux, préparation d'une traduction de notices, atelier d'un document et écran de confirmation d'une tâche quand Argos est le moteur choisi. L'administrateur a le bouton ; un chercheur lit « demandez à l'administrateur ». Si le service ne répond pas, l'encadré en donne la raison | `templates/translation/_argos_invite.html` |
| Première configuration | Case « Installer maintenant la traduction hors ligne japonais → français », **décochée** par défaut (« plus tard »). Si le service n'est pas encore prêt, un avertissement s'affiche ; la configuration n'est pas bloquée | `apps/accounts/forms.py`, `views.py` |
| Priorité « maintenant » | Le service fait une traduction à la fin d'un paquet ; il traite une demande `now` avant les demandes `background` en attente. L'application envoie `now` pour une tâche de 20 éléments au plus (`TRANSLATION_ARGOS_NOW_MAX_ITEMS`) | `docker/argos/server.py`, `engines/argos.py`, `services.py` |
| Cœurs et mémoire | `ARGOS_COEURS` (limite de cœurs et fils de calcul d'Argos) et `ARGOS_MEMOIRE_MAX` dans `.env`. Par défaut, 0 = sans limite (vérifié avec `docker compose config`) | `docker-compose.yml` |
| Mémoire affichée | `/health` donne la mémoire vue par le service (totale, disponible, limite du conteneur). Moteurs locaux l'affiche. Un avertissement apparaît en dessous de 4 Go (8 Go conseillés), aussi sur la page « État » | `server.py`, `argos_packages.py`, `apps/core/health.py` |
| Licences | Section « Licences » : Argos Translate (MIT ou CC0, d'après le dépôt du projet), paquets entraînés principalement sur les corpus OPUS, lien vers l'index. Pour chaque paquet installé, la licence qu'il déclare dans ses métadonnées, sinon « non déclarée » | `local_engines.html`, `server.py` |

**Base de données.** Aucun changement. La commande de retour vers la 1.3.0 ne change pas.

**Guides.** Mis à jour :
- **guide d'installation**, étape 5 : le service tourne déjà, il reste un clic ;
- **guide de mise à jour** : ligne ajoutée par le script, durée de construction, vérification d'Argos, mise à jour manuelle.

## 2. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète, exécution séquentielle | **599 tests réussis** (575 + 24) |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration |
| `docker compose config` réel (Compose 5.7) | Argos démarré avec le `.env.example`, absent avec `COMPOSE_PROFILES=`, présent avec `hors-ligne` ; limites 0 = aucune, 4 cœurs / 4g appliqués |
| `mettre-a-jour.ps1` et `verifier-j-ed.ps1` sous PowerShell 7 (Docker simulé) | ligne ajoutée si absente, respectée si présente ou vide, plus de `--profile` ; contrôles Argos du vérificateur |
| Navigateur réel (Chrome, base temporaire, service Argos réel avec traducteur factice) | encadré avec 200 Mo ; case puis bouton ; tâche « Terminée » (2 paquets) ; « Dernier essai : Argos prêt » ; fenêtre « Terminé » ; mémoire affichée ; licences ; **aucune erreur dans la console** |

**Nouveaux tests** (`tests/test_argos_200.py`, 21 tests, plus 3 tests Compose et scripts) :

- priorité : une demande `now` passe avant un paquet `background` en attente, après le paquet en cours (threads réels) ;
- mémoire (cgroup v2, limite réelle, cgroup v1 sans limite, fichiers absents) ; licence lue dans `metadata.json` ;
- `/health` (mémoire, file) et valeurs de priorité ; priorité envoyée par le moteur ; petite ou grande tâche ;
- bouton unique :
  - confirmation obligatoire ;
  - deux paquets, essai et notification ;
  - seuls les paquets manquants sont téléchargés ;
  - échec notifié puis reprise ;
  - refus pendant une installation ou si le service est arrêté ;
  - droits d'accès ;
- invitations : Moteurs (administrateur et chercheur), rien quand Argos est prêt, préparation d'une traduction (encadré hors du formulaire), écran de confirmation, page « État » ;
- assistant de première configuration : « plus tard » par défaut, installation immédiate, service non prêt sans blocage.

## 3. Écarts et choix faits pendant le lot

- **« Sans profil à activer ».** Argos garde un profil Compose, mais la ligne livrée dans `.env.example` l'active. C'est le mécanisme standard de Docker pour un service désactivable. L'utilisateur n'a donc rien à taper.
- **Taille annoncée.** « Environ 200 Mo » est affiché **avant** tout appel à Internet. Connaître la taille exacte demanderait de consulter l'index Argos en ligne avant la confirmation.
- **Licences.** La licence d'Argos Translate est vérifiée sur son dépôt. Je n'ai pas pu lire celle des paquets ja→en 1.1 et en→fr 1.9 ici (il faudrait les télécharger). L'application affiche donc ce que chaque paquet déclare, ou renvoie à l'index.
- **Priorité.** Le service fait désormais une traduction à la fois. Le calcul occupe déjà tous les cœurs : deux traductions simultanées n'allaient pas plus vite. Une demande « maintenant » attend au plus la fin du paquet en cours (50 segments au plus). La taille des paquets selon le moment (petits le jour, grands la nuit) et le bouton « Traduire maintenant » relèvent du lot 3 (file de nuit). Le rechargement du traducteur la nuit (D8) reste à décider après les mesures V7-7.
- **Seuil mémoire.** L'avertissement à 4 Go est une estimation prudente, pas une mesure. La mesure V7-7 permettra de l'ajuster.
- **`reinitialiser-essai.ps1`** est inchangé : il continue de fonctionner, et le `.env` décide désormais d'Argos au redémarrage.
- **Vérification réelle** (vrai service, vrais paquets, durée, taille de l'image) : à faire sur ton poste (V7-1 à V7-7). Statut : testé en simulation ; test réel à confirmer.

## 4. Livrables du lot

- Archive `japon-explorateur-2.0.0-lot7.zip` et son empreinte `.sha256` (contient aussi le lot 8).
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 7 » (V7-1 à V7-7).
- CHANGELOG : section 2.0.0, lot 7.
