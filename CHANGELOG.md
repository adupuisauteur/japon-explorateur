# Historique des versions

## 1.2.0 — 13 novembre 2026

Évolution ciblée : sources documentaires japonaises et journal des dysfonctionnements. Voir `docs/evolution-1.2.0/`.

- **Sources** : nouveau connecteur CiNii Research (et CiNii bibliothèques universitaires) ; Archives nationales via Japan Search ; outil « Trouver une base Japan Search » ; Japan Search corrigé (variantes en OU, champs documentés, dates) ; lien vers les documents numérisés NDL.
- **Recherche** : cinq états distincts par source (résultats, aucun résultat, indisponible, erreur technique, réponse illisible) ; variantes de graphie libres, sans suffixe et attestées ; tri par auteur et institution ; filtre « document numérisé ».
- **Journal des dysfonctionnements** : enregistrement automatique et expurgé, regroupement, gravités, statuts de correction, réapparitions, signalement manuel, analyse, export de diagnostic.
- **Socle** : numéro de version unique (`VERSION`) ; installation d'essai isolée (projet Docker, volumes, port 8001, image) ; `pypdf` ajouté aux dépendances.
- Base de données : une migration **additive** (`incidents.0001_initial`), aucune table existante modifiée.

## 1.1 — commit 7cb4075

Application complète et 13 corrections de l'audit (numéro affiché par erreur : 1.0.0).
