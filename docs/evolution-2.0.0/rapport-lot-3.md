# J-ed 2.0.0 — Rapport du lot 3 : tâches, file de nuit, « Traduire maintenant », travail en parallèle

15 novembre 2026 · branche `evolution-2.0.0` · plan : `01-audit.md`, § 3.4 et 5.2 · cahier des charges : § 6

## 1. Décisions prises au début du lot (15 novembre 2026)

| Point | Décision |
| --- | --- |
| Plage de nuit par défaut | Aucune : c'est l'utilisateur qui la choisit. Sans plage, la file de nuit n'est pas proposée |
| File de nuit commencée en retard (D1) | **Toujours redemander** : si J-ed n'était pas en marche au début de la plage, les tâches de nuit attendent une confirmation |
| Confirmation de « Traduire maintenant » (D2) | Une confirmation par demande, sauf sous un seuil de coût fixé par l'utilisateur (vide par défaut) ; Argos ne demande jamais de confirmation |
| Copies de sauvegarde dans Windows | J-ed n'en supprime aucune ; l'utilisateur les gère lui-même |
| Essai d'Argos | Bouton dans Moteurs locaux ; essai automatique 2 minutes après une installation ou une mise à jour |

## 2. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| États et lancement | Nouveaux états « Planifiée », « En pause » (avec sa raison), « En retard — à confirmer ». « Terminée avec erreurs » est affiché pour une tâche terminée dont des éléments ont échoué. Lancement immédiat, « maintenant », programmé ou de nuit, choisi à la confirmation ; le coût est confirmé une seule fois | `apps/translation/models.py`, migration `translation.0003_file_et_nuit` |
| Horloge | Tâche Celery chaque minute (file des travaux courts). Une tâche programmée part si l'horloge la voit au plus 5 minutes après son heure ; au-delà (J-ed arrêté), elle passe « En retard » avec une notification et ne part jamais d'elle-même | `apps/translation/queue.py`, `tasks.py`, `config/settings.py` |
| File de nuit | Plage choisie dans Traduction → Moteurs, qui peut passer minuit. Une tâche de nuit à la fois par utilisateur, dans l'ordre de la file (monter, descendre). Une plage observée plus de 5 minutes après son début est « en retard » : tâches à confirmer, notification. À la fin de la plage : pause entre deux paquets, reprise la nuit suivante. Après la plage : compte rendu du matin (traduit, restant, erreurs, coût estimé, nuit interrompue) | `queue.py` |
| Plafonds | Plafond mensuel du moteur et budget IA vérifiés **avant chaque paquet** : pause « plafond atteint » avec alerte, jamais d'autre moteur | `queue.py` (`cap_problem`), `services.py` |
| Pause et reprise | « Mettre en pause » (après le paquet en cours) ; « Reprendre maintenant » ; « Remettre dans la file de nuit » ; « Programmer » ; « Annuler » (ce qui est traduit reste) | `services.py`, `views/jobs.py`, `_job_status.html` |
| « Traduire maintenant » | Sur la fiche, dans la Bibliothèque : titre et description (plus sujets et lieu selon les préférences), moteur par défaut. Départ direct avec Argos ou sous le seuil choisi, sauf si quelque chose bloque, si les conditions d'un fournisseur restent à lire, si une seconde confirmation est requise ou si le profil IA impose la confirmation. Résultat affiché sur la fiche (actualisé toutes les 3 s) | `services.prepare_quick`, `views/records.py`, `record_detail.html`, `library/views.py` |
| « Ajouter à la file de nuit » | Sur la fiche, dans la Bibliothèque et dans l'atelier d'un document : écran de confirmation habituel, lancement « nuit » présélectionné, avec le rappel sur la mise en veille | idem, `workbench.html` |
| Page « Tâches » | En cours, file de nuit (ordre), programmées, à décider, terminées. L'administrateur peut afficher toutes les tâches ; le titre d'un projet confidentiel d'autrui est masqué et le contenu reste réservé à l'auteur. Compte rendu sur chaque tâche : fait, échoué et pourquoi, restant, coût estimé, liens vers les résultats | `views/jobs.py`, `job_list.html`, `_job_rows.html` |
| Indicateur | « 1 traduction en cours » dans la barre de menu, actualisé avec les fenêtres de notification ; entrée « Tâches » dans le menu à son nom | `_task_indicator.html`, `context_processors.py` |
| Trois workers | `worker` (file `celery` : exports, synchronisations, sauvegardes, horloge), `worker-traduction` (longues traductions, file de nuit, paquets Argos), `worker-maintenant` (fiche et petites tâches). La page « État » signale une file sans worker ; `verifier-j-ed.ps1` attend les trois conteneurs | `docker-compose.yml`, `apps/core/health.py`, `verifier-j-ed.ps1` |
| Profils de machine | Économe, normal, puissant, calculés au démarrage d'après la mémoire et les cœurs vus par Docker ; `JED_PROFIL` dans `.env` pour l'imposer. Ils fixent les processus du serveur web, les travaux courts en parallèle et la taille des paquets Argos (petits le jour, grands la nuit : D8). Le profil apparaît sur la page « État », avec la raison du choix et la commande pour en changer. La mémoire de l'ordinateur peut être indiquée (page « État » ou assistant) pour un conseil `.wslconfig` ; rien n'est modifié d'office | `config/profil_machine.py`, `config/gunicorn.conf.py`, `docker/Dockerfile`, migration `core.0005_memoire_ordinateur` |
| Traductions effectuées (U5) | Notices traduites : filtres par état (proposée, validée, refusée, **à revoir** si l'original a changé), moteur, date et texte ; lien vers la fiche. Avancement des documents de projets visibles par l'utilisateur | `views/done.py`, `done.html` |
| Essai d'Argos | Bouton « Lancer un essai » dans Moteurs locaux. Essai automatique 2 minutes après le démarrage, seulement si Argos est prêt et n'a pas été essayé avec la version installée ; jusqu'à 5 tentatives si le service démarre encore | `argos_selftest.py`, `config/celery.py` |
| Notifications anciennes | Les notifications **lues** de plus de 90 jours sont supprimées chaque nuit ; les non lues sont toujours gardées | `apps/notifications/services.py`, `tasks.py` |

**Base de données.** Deux migrations additives :
- `translation.0003_file_et_nuit` : 4 champs sur les tâches, 5 sur les préférences ;
- `core.0005_memoire_ordinateur` : 1 champ.

Le retour en arrière de `translation.0003` transforme les états « Planifiée », « En pause » et « En retard » en
« Interrompue », un état connu de la 1.3.0 et reprenable. Aucune tâche n'est supprimée. Retour vers la 1.3.0 :
ajouter `migrate translation 0002` aux commandes (guide de mise à jour).

## 3. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète | **631 tests réussis** (603 + 28) |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration manquante |
| Migration aller-retour (base de test) | états du lot 3 → « Interrompue » au retour ; les autres inchangés ; remontée sans erreur |
| `docker compose config` réel | trois workers, environnement et volumes hérités ; une file par worker |
| `verifier-j-ed.ps1` sous PowerShell 7 (Docker simulé) | trois conteneurs de workers attendus |
| Navigateur réel (Chrome, base temporaire, service Argos réel avec traducteur factice) | plage de nuit enregistrée ; « Traduire maintenant » sur une fiche : départ direct, « Traduction prête » ; file de nuit depuis la fiche : lancement présélectionné, prochaine plage affichée ; page Tâches ; Traductions effectuées ; profil sur la page « État » ; **aucune erreur dans la console** |

**Nouveaux tests** (`tests/test_taches_300.py`, 28 tests), avec des dates fixées :
- **plage horaire** : à cheval sur minuit, dans la journée, absente ; formulaire ;
- **lancements** : immédiat ; programmé (départ à l'heure, retard après un arrêt, jamais de départ seul, « Lancer maintenant ») ; nuit sans plage refusée ;
- **file de nuit** :
  - ordre modifiable et départs successifs ;
  - compte rendu du matin ;
  - plage commencée en retard : confirmation demandée, puis remise dans la file pour la nuit suivante ;
  - fin de plage : pause sans envoi, reprise la nuit suivante ;
- **plafond atteint en cours de tâche** : pause avant le paquet suivant, alerte, reprise refusée tant que le plafond est atteint ;
- **pause et reprise** : pause, reprise et annulation par l'utilisateur ; « Terminée avec erreurs » ;
- **« Traduire maintenant »** : confirmation ou départ direct sous le seuil, résultat sur la fiche, jamais de départ direct avec des conditions à lire, file de nuit depuis la fiche, Bibliothèque, lecteur refusé, choix de la file Celery ;
- **page Tâches, indicateur, compte rendu** : sections, indicateur, vue administrateur sans titre confidentiel ;
- **infrastructure** : file sans worker signalée, horloge dans la file courte, retour de migration ;
- **profils** : choix selon les ressources, `JED_PROFIL`, serveur web et Celery, paquets Argos jour et nuit, page « État » et conseil sur la mémoire ;
- **demandes rattachées** : Traductions effectuées (filtres, « à revoir », documents) ; nettoyage des notifications.

## 4. Écarts et choix faits pendant le lot

- **Vérification d'accès des documents NDL : reportée.** La NDL n'indique pas si un document numérisé est en accès libre, réservé aux bibliothèques ou sur place. Tenter de lire son manifeste IIIF suppose une règle (« manifeste lisible = accès libre ») que je ne peux pas vérifier d'ici, faute d'accès au site de la NDL. Je propose de la traiter avec le lot 10 (documents et nouvelles sources), à partir d'exemples réels relevés sur ton poste. Les notices NDL numérisées restent « document : non vérifié ».
- **« Terminée avec erreurs »** est un état affiché (tâche terminée et éléments en échec), pas un nouvel état en base : les exports, la consommation et le retour vers la 1.3.0 restent inchangés.
- **« Maintenant » le jour, « nuit » la nuit.** Une demande depuis une fiche, ou une tâche immédiate de 20 éléments au plus, va au worker « maintenant » et passe en priorité dans Argos. Les longues tâches et la file de nuit vont au worker « traduction ».
- **Programmation.** Le délai de 5 minutes entre l'heure prévue et le passage de l'horloge vaut aussi pour le début de la plage de nuit. Il permet un passage manqué d'une minute, sans jamais lancer une tâche après un vrai arrêt de J-ed.
- **Mémoire supplémentaire.** Les deux nouveaux workers prennent chacun quelques centaines de Mo. Le profil économe réduit le serveur web et les travaux courts en conséquence.
- **Test instable connu.** La classe des tests de recherche (`test_search_sessions`) a échoué une fois en exécution parallèle, puis a réussi seule et dans deux suites complètes. C'est le problème déjà noté pour le lot 9, qui en cherchera la cause.
- **Vérification réelle** (vraie plage de nuit, vrai arrêt de Docker, trois workers sur ton poste) : V3-1 à V3-8. Statut : testé en simulation ; test réel à confirmer.

## 5. Livrables du lot

- Archive `japon-explorateur-2.0.0-lot3.zip` et son empreinte `.sha256`.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 3 » (V3-1 à V3-8).
- CHANGELOG : section 2.0.0, lot 3.
