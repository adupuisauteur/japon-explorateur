# Contribuer à J-ed

Merci de votre intérêt pour J-ed, application d'aide à la recherche documentaire sur le Japon.

## Licence des contributions

J-ed est publié sous la licence **GNU AGPL v3.0 ou toute version ultérieure** (`AGPL-3.0-or-later`, fichier
[`LICENSE`](LICENSE)). En proposant une contribution (code, documentation, traduction, image…), vous acceptez
qu'elle soit publiée **sous la même licence**, et vous confirmez que vous avez le droit de la proposer (travail
personnel, ou contenu sous une licence compatible dont vous indiquez l'origine).

## Signaler un problème ou proposer une idée

- Ouvrez un ticket (onglet « Issues » du dépôt) en décrivant ce que vous avez fait, ce que vous attendiez et ce que
  vous avez obtenu, avec le numéro de version (pied de page de J-ed).
- Dans J-ed, « Signaler un problème » prépare un rapport de diagnostic que vous pouvez joindre.
- **N'y mettez jamais** de clé d'API, de mot de passe, de fichier `.env`, d'adresse personnelle ni de données
  réelles de vos recherches : le dépôt est public.

## Proposer une modification

1. Partez de la branche `main` et créez une branche à votre nom de sujet.
2. Gardez des modifications courtes, sur un seul sujet.
3. Données de test **fictives** uniquement ; aucune clé d'API réelle dans le code.
4. Migrations de base de données **seulement additives** (ajouter, jamais supprimer ni renommer), pour qu'une
   version précédente fonctionne encore sur une base migrée.
5. Lancez les tests avant de proposer (PostgreSQL avec l'extension `pg_trgm`, et Redis ; voir le README,
   sections 1 et 8) :
   `python manage.py test tests --noinput --parallel 4`, puis `python manage.py makemigrations --check --dry-run`.
6. Mettez à jour l'aide intégrée (`docs/aide/`) si ce que voit l'utilisateur change, et `CHANGELOG.md`.
7. Ouvrez une demande de fusion (« Pull request ») qui explique le pourquoi de la modification.

## Conventions

- Textes de l'interface et de l'aide **en français**, simples, pour des utilisateurs qui débutent avec Docker et
  PowerShell : une commande par cadre, avec le résultat attendu.
- Scripts PowerShell compatibles avec **Windows PowerShell 5.1** : fichiers en UTF-8 avec BOM et fins de ligne
  CRLF ; ils sont testés avec PowerShell 7 (`tests/test_mise_a_jour_ps1.py`).
- Aucune opération ne doit effacer de données : jamais `docker compose down -v`, sauvegarde vérifiée avant toute
  opération risquée.
