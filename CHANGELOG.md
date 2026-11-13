# Historique des versions

## 1.3.0 — en cours de développement

Évolution : module de traduction. Base : version 1.2.0, étiquette `v1.2.0-reference` (commit `4982a3d`). Voir `docs/evolution-1.3.0/`.

- **Socle (lot 0)** : numéro de version 1.3.0 ; installation d'essai 1.3.0 isolée de l'installation principale et de l'essai 1.2.0 (projet Docker `japon-explorateur-essai-130`, port 8002, image `japon-explorateur:1.3.0`) ; les conteneurs refusent de démarrer sous le nom de projet de l'installation principale ou de l'essai 1.2.0 ; le script `reinitialiser-essai.ps1` refuse aussi l'essai 1.2.0 (nom et port 8001).
- Base de données : aucune migration dans ce lot.

## 1.2.0 — 13 novembre 2026

Évolution ciblée : sources documentaires japonaises et journal des dysfonctionnements. Voir `docs/evolution-1.2.0/`.

- **Sources** : nouveau connecteur CiNii Research (et CiNii bibliothèques universitaires) ; Archives nationales via Japan Search ; outil « Trouver une base Japan Search » ; Japan Search corrigé (variantes en OU, champs documentés, dates) ; lien vers les documents numérisés NDL.
- **Recherche** : cinq états distincts par source (résultats, aucun résultat, indisponible, erreur technique, réponse illisible) ; variantes de graphie libres, sans suffixe et attestées ; tri par auteur et institution ; filtre « document numérisé ».
- **Journal des dysfonctionnements** : enregistrement automatique et expurgé, regroupement, gravités, statuts de correction, réapparitions, signalement manuel, analyse, export de diagnostic.
- **Socle** : numéro de version unique (`VERSION`) ; installation d'essai isolée (projet Docker, volumes, port 8001, image) ; `pypdf` ajouté aux dépendances.
- **Outil** : script `reinitialiser-essai.ps1` (Windows) pour remettre l'installation d'essai à zéro, avec contrôles de sécurité qui protègent l'installation principale.
- **Correctif (13/11, incident INC-20261113-41FDF0)** : erreur 500 au clic sur « Comparer avec la base » sous Docker. Le module `packaging`, requis par kombu 5.7 (transport Redis de Celery) mais non déclaré par ce paquet, est ajouté aux dépendances. Le même problème touchait toute tâche confiée au worker (synchronisations, exports). Un test de non-régression a été ajouté, et chaque erreur de page reçoit désormais un identifiant de requête.
- **Correctif (13/11, incident INC-20261113-0AB9C5)** : « Actualiser » était proposé pour NDL Search, Japan Search et CiNii, qui ne savent pas actualiser des notices, et l'échec était enregistré comme « Erreur technique ». Le bouton n'est désormais proposé que pour les connecteurs compatibles (ex. Kokusho), le serveur refuse l'opération sinon, et le planificateur comme « Actualiser les sources compatibles » les ignorent. Une opération non proposée n'est jamais enregistrée comme dysfonctionnement.
- Base de données : une migration **additive** (`incidents.0001_initial`), aucune table existante modifiée.

## 1.1 — commit 7cb4075

Application complète et 13 corrections de l'audit (numéro affiché par erreur : 1.0.0).
