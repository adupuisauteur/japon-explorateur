---
titre: Tâches, file de nuit et programmation
rubrique: Traduire et résumer
ordre: 50
public: editeur
ecrans: translation:job_list, translation:job_detail
resume: Suivre, programmer, mettre en pause et reprendre les traductions et les résumés.
---
Chaque traduction (même d'un seul champ) et chaque demande de résumés est une **tâche**. Menu à votre nom →
**Tâches**, ou Traduction → Tâches.

## Les états d'une tâche

| État | Signification |
| --- | --- |
| **Préparée** | Rien n'est parti : à confirmer ou à annuler |
| **Confirmée**, **En cours** | En file ou en train de travailler |
| **Planifiée** | Partira à l'heure choisie, ou dans la file de nuit |
| **En pause** | Arrêtée par vous, par un plafond atteint, ou par la fin de la plage de nuit |
| **En retard — à confirmer** | Son heure est passée pendant que J-ed était arrêté : elle attend votre accord |
| **Interrompue** | Arrêtée par une panne (service injoignable, ordinateur éteint) : **Reprendre** |
| **Terminée**, **Terminée avec erreurs**, **Échec**, **Annulée** | Fin de la tâche, avec son compte rendu |

Une tâche reprise **ne renvoie jamais** ce qui a déjà été traduit ou résumé : elle continue là où elle s'était
arrêtée. **Relancer les échecs** ne reprend que les éléments en échec.

## Quand faire partir une tâche

À la confirmation, vous choisissez :

- **Maintenant** : tout de suite ;
- **À une heure précise** : la tâche est planifiée ;
- **File de nuit** : elle partira pendant votre plage de nuit, l'une après l'autre.

Pour une traduction de notices ou de documents, la case **Résumer aussi** enchaîne les résumés, juste après chaque
traduction ou après l'ensemble des traductions. Voir [Résumés IA](aide:resumes-ia).

## La file de nuit

Réglez votre **plage de nuit** dans Traduction → Moteurs (par exemple de 23 h à 6 h). Il n'y a pas de plage par
défaut : sans réglage, le choix « File de nuit » reste grisé.

- L'ordinateur doit rester **allumé, sans mise en veille**, avec Docker Desktop démarré. Éteint, rien n'avance.
- À la fin de la plage, une tâche inachevée se met **en pause** ; elle reprend la nuit suivante.
- Si la plage a commencé alors que J-ed était arrêté, J-ed ne lance rien sans vous **redemander confirmation**.
- Le matin, une notification résume la nuit : ce qui est terminé, en pause, en erreur.
- Sur la page Tâches, les flèches **Monter** et **Descendre** changent l'ordre de la file.
- Une tâche en pause, en retard ou interrompue peut être **remise dans la file de nuit**.

## Coût et confirmation

Le coût estimé est affiché avant tout envoi à un service payant. Vous pouvez fixer, dans **Moteurs** :

- un montant en dessous duquel « Traduire maintenant » part sans confirmation (vide par défaut : toujours confirmer ;
  Argos ne demande jamais, il est gratuit) ;
- une **seconde confirmation** au-delà d'un nombre de caractères.

Les plafonds mensuels sont décrits dans [Consommation et plafonds](aide:consommation-et-plafonds).
