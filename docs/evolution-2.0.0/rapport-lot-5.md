# J-ed 2.0.0 — Rapport du lot 5 : notifications

15 novembre 2026 · branche `evolution-2.0.0` · plan : `01-audit.md`, § 3.6 et § 5.4 (validé le 14 novembre
2026) · cahier des charges : § 8

## 1. Ce qui a été fait

| Sujet | Réalisation | Fichiers principaux |
| --- | --- | --- |
| Modèle de données | Application `notifications` : `Notification` (destinataire, type, gravité, titre, texte, lien, groupe, canal, dates de création, de lecture et d'affichage de la fenêtre) et `NotificationPreference` (utilisateur, type, canal, activé, seuil des alertes) | `apps/notifications/models.py`, migration `notifications.0001` |
| Règles | Préférences respectées ; une seule notification non lue par groupe ; alertes de dysfonctionnement réservées aux administrateurs, au-dessus de leur seuil ; une erreur de notification ne fait jamais échouer l'opération notifiée (elle est journalisée) | `apps/notifications/services.py` |
| Fins de tâches | Traduction : terminée, terminée avec des erreurs, en échec (y compris erreur inattendue), interrompue. Export : prêt ou en échec. Synchronisation : à valider ou en échec, pour son auteur ; une synchronisation planifiée va aux administrateurs, et seulement si elle demande une action | `apps/translation/services.py`, `apps/exports/services.py`, `apps/updates/services.py` |
| Alertes | Une fenêtre par nouveau groupe d'incidents, ou par problème corrigé qui revient ; jamais pour une nouvelle occurrence d'un groupe connu ; envoyée après la validation de l'enregistrement (rien pour une opération annulée) | `apps/incidents/services.py` |
| Fenêtres | En bas à droite, avec « Voir le compte rendu » (ou « Voir le dysfonctionnement ») et « Vu » ; fermeture automatique pour une réussite, maintien pour une erreur ou une alerte ; une seule présentation ; attente de la prochaine visite d'un utilisateur absent | `templates/notifications/_popups.html`, `static/js/app.js` |
| Compteur | Notifications non lues sur le bouton du menu à son nom, mis à jour sans recharger la page ; entrée « Notifications » dans ce menu | `templates/base.html`, `apps/core/context_processors.py` |
| Pages | « Notifications » : historique, filtres par état et par type, « Marquer comme lue », « Tout marquer comme lu ». « Préférences » : activation par type, seuil des alertes (administrateur), boutons d'essai | `apps/notifications/views.py`, `templates/notifications/` |
| Essai | « Envoyer une notification d'essai » pour tous ; « Envoyer une alerte de dysfonctionnement d'essai » pour l'administrateur. Rien n'est lancé ni écrit au journal | `apps/notifications/services.py` (`test`) |
| Actualisation | Interrogation toutes les 30 secondes et à chaque page ; suspendue quand l'onglet est masqué, reprise dès son retour ; la même suspension s'applique aux 5 pages qui s'actualisent toutes les 2 à 5 secondes. Aucun script en ligne, aucun service extérieur | `static/js/app.js`, 5 gabarits |
| Vérification automatique | Contrôle « Notifications » : fenêtre, présentation unique, compteur, « Vu », préférence, alerte refusée à un chercheur, reçue par l'administrateur, seuil ; pages ajoutées au contrôle | `apps/core/verification.py` |

**Base de données.** Une migration, `notifications.0001_initial`, qui crée deux tables. Retour en arrière :
`migrate notifications zero`.

## 2. Correctif découvert pendant le lot : cache du navigateur

Le service worker met en cache `app.js`, `app.css` et les bibliothèques de l'interface. Il les sert ensuite
**avant** le réseau, dans un cache nommé d'après le seul numéro de version (`shell-v2.0.0`). Entre deux
livraisons de la 2.0.0 (lots 0 à 5), ce nom ne changeait pas. Le navigateur pouvait donc garder l'ancien
`app.js` : sans lui, les fenêtres du lot 5 ne s'afficheraient pas, et des couleurs du lot 2 pouvaient
manquer.

Le nom du cache porte désormais une empreinte du contenu de ces fichiers. Il change dès que l'un d'eux change ;
l'ancien cache est alors supprimé par le navigateur. Un test le vérifie.

## 3. Tests exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite complète, exécution séquentielle | **556 tests réussis** (537 + 19 nouveaux ; 2 tests adaptés, § 4) |
| `manage.py check` ; `makemigrations --check` | aucune anomalie ; aucune migration manquante |
| Aller-retour 1.3.0 → 2.0.0 (lot 5) → 1.3.0, base temporaire, 9 notices fictives, 2 notifications et une préférence fictives | 6 migrations appliquées ; aucune ligne perdue ni modifiée. Retour par `migrate notifications zero`, `migrate catalog 0005`, `migrate core 0001` : toutes les données d'origine intactes ; le code 1.3.0-rc3 démarre sans erreur, aucune migration en attente |
| Navigateur réel (Chrome sans interface, base temporaire) | fenêtre d'essai affichée, compteur à 2, « Vu » ferme la fenêtre et ramène le compteur à 1, historique correct, **aucune erreur dans la console** |
| Onglet masqué (navigateur réel) | aucune requête tant que l'onglet est masqué ; une requête dès son retour |

**Nouveaux tests** (`tests/test_notifications_200.py`, 19 tests) :

- règles : préférences, une notification non lue par groupe, alertes réservées aux administrateurs et seuil,
  erreur sans effet sur l'opération ;
- incidents : une fenêtre par groupe et non par occurrence, seuil, retour d'un problème corrigé, rien pour une
  opération annulée ;
- fins de tâches : traduction (terminée, erreurs, interrompue, étape intermédiaire sans fenêtre), export,
  synchronisation (auteur ou administrateurs) ;
- interface : présentation unique, compteur mis à jour, absence puis retour, « Vu », appartenance, liens
  internes seulement, historique et filtres, préférences et essais selon le rôle, menu, lecteur ;
- interface côté navigateur : suspension des actualisations, cache du service worker.

## 4. Écarts et choix faits pendant le lot

- **Seuil des alertes** : rangé dans `NotificationPreference` (champ `min_severity`), propre à chaque
  administrateur, plutôt que dans un réglage global. Par défaut : « Erreur et plus ».
- **Compteur du menu** : il compte désormais les notifications non lues. Il remplace la pastille provisoire des
  incidents du lot 1. Le nombre d'incidents nouveaux reste affiché sur l'entrée « Dysfonctionnements » et en
  bas de page.
- **Imports de fichiers** : leur analyse est immédiate (pas de tâche de fond) ; ils ne produisent donc pas de
  notification.
- **« En pause pour plafond »** : les plafonds vérifiés à chaque envoi viennent au lot 3. Aujourd'hui, une
  traduction interrompue (service injoignable, par exemple) donne une fenêtre « Traduction interrompue ».
- **Tests adaptés** : `test_menu_entry_and_badge` (1.2.0) et `MenuTests` (lot 1) vérifiaient la pastille des
  incidents sur le bouton du menu. Ils vérifient maintenant la chaîne complète : incident → alerte de
  l'administrateur → compteur.
- **Historique** : les notifications ne sont pas encore purgées. Leur volume est faible ; une purge des
  notifications lues de plus de six mois peut venir avec les tâches planifiées du lot 3.

## 5. Points ouverts

- Vérifications V5-1 à V5-6 sur ton poste.
- Pour le lot 2 : tes réponses sur la règle Japan Search, la règle NDL et les statuts dans les exports.

## 6. Livrables du lot

- Archive `japon-explorateur-2.0.0-lot5.zip` et son empreinte `.sha256`.
- Protocole : `docs/evolution-2.0.0/05-protocole-verification.md`, section « Lot 5 » (V5-1 à V5-6).
- CHANGELOG : section 2.0.0, lot 5.
- Guide de mise à jour : retour vers la 1.3.0 en trois commandes (`migrate notifications zero`, `migrate
  catalog 0005`, `migrate core 0001`).
