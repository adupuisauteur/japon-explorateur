# Déploiement sur un serveur Linux

Les images, le schéma de données et les sauvegardes sont les mêmes qu'en local (§4.4).

1. Installer Docker Engine et le plugin Compose sur le serveur.
2. Copier le projet, créer `.env` (voir `.env.example`) et ajouter :
   ```
   DJANGO_ALLOWED_HOSTS=japon.example.org
   DJANGO_CSRF_TRUSTED_ORIGINS=https://japon.example.org
   SECURE_HTTPS=true
   SETUP_TOKEN=…            # obligatoire avec SECURE_HTTPS (generate_secrets en fournit un)
   BACKUP_EXTERNAL_DIR=/backups-externes
   ```
   Sans `SETUP_TOKEN`, ou avec une clé secrète faible, l'application refuse de démarrer : c'est voulu.
3. Monter un emplacement de sauvegarde **distinct du serveur** (stockage réseau, disque monté) dans `docker-compose.yml` (volume `/backups-externes`).
4. `docker compose up -d --build`.
5. Placer un reverse proxy HTTPS devant le port local 8000, par exemple Caddy avec `docs/deploiement/Caddyfile.exemple` (certificat automatique). PostgreSQL et Redis ne sont jamais publiés.

> Derrière un reverse proxy, toutes les connexions semblent venir de la même adresse : le verrouillage après 5 échecs vaut alors, en pratique, par identifiant. Un tiers peut ainsi bloquer un compte pendant 15 minutes en tapant de mauvais mots de passe. Ce compromis est accepté pour une petite équipe. Réglage : `LOGIN_MAX_FAILURES`, `LOGIN_LOCKOUT_SECONDS`.

## Migration du local vers le serveur

1. En local : *Administration → Sauvegardes → Sauvegarder maintenant*, puis télécharger l'archive.
2. Sur le serveur, après le premier démarrage :
   `docker compose cp sauvegarde-….tar web:/data/` puis
   `docker compose exec web python manage.py restore_backup /data/sauvegarde-….tar --yes`
3. Reprendre dans `.env` **les mêmes** `DJANGO_SECRET_KEY` et `AI_KEYS_ENCRYPTION_KEY` (sinon, ressaisir les clés API).

## Mises à jour de l'application

```
docker compose exec web python manage.py backup --verify
docker compose pull            # ou rebuild
docker compose up -d --build   # les migrations s'appliquent au démarrage
```
Retour arrière : relancer l'image précédente et restaurer la sauvegarde prise juste avant la mise à jour.

## Environnements

Prévoir une instance de test (autre dossier, autre `.env`, autre base) pour essayer imports, connecteurs et restaurations sans toucher à la production (§17.3).

## RGPD (ouverture à d'autres utilisateurs)

Documenter finalités, données (comptes, notes, journaux), durées de conservation, sous-traitants (hébergeur, fournisseurs d'IA éventuels) et transferts hors EEE. L'anonymisation d'un compte est disponible dans *Administration → Comptes*.
