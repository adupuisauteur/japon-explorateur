#!/bin/sh
set -e

# Isolation : refus de démarrer sous le nom de projet Docker de l'installation principale ou de l'essai
# existant, ce qui ferait utiliser leur base de données et leurs fichiers.
# Exception VOLONTAIRE : la mise à jour d'une de ces installations en gardant ses données est permise
# seulement si .env contient AUTORISER_NOM_PROJET avec exactement le même nom de projet.
if [ -z "${COMPOSE_PROJECT_CHECK:-}" ]; then
  echo "ARRÊT : COMPOSE_PROJECT_NAME n'est pas défini dans .env (voir .env.example)." >&2
  exit 1
fi
case "${COMPOSE_PROJECT_CHECK}" in
  japon-explorateur|japon-explorateur-essai)
    if [ "${AUTORISER_NOM_PROJET:-}" = "${COMPOSE_PROJECT_CHECK}" ]; then
      echo "Projet Docker « ${COMPOSE_PROJECT_CHECK} » : démarrage autorisé par AUTORISER_NOM_PROJET (mise à jour d'une installation existante)." >&2
    else
      echo "ARRÊT : le projet Docker « ${COMPOSE_PROJECT_CHECK} » appartient à une installation existante" >&2
      echo "(principale ou essai). Pour une installation séparée, choisissez un autre COMPOSE_PROJECT_NAME dans" >&2
      echo ".env. Pour mettre à jour CETTE installation en gardant ses données, ajoutez dans .env la ligne" >&2
      echo "AUTORISER_NOM_PROJET=${COMPOSE_PROJECT_CHECK} (après une sauvegarde)." >&2
      exit 1
    fi ;;
esac

# Commandes utilitaires sans base de données (ex. génération des clés) : exécution directe.
case "$*" in
  *generate_secrets*) exec "$@" ;;
esac

# Attente de PostgreSQL
python - <<'EOF'
import os, time, psycopg, environ
url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgres"):
    cfg = environ.Env.db_url_config(url)
    for i in range(60):
        try:
            psycopg.connect(host=cfg["HOST"], port=cfg["PORT"] or 5432, user=cfg["USER"],
                            password=cfg["PASSWORD"], dbname=cfg["NAME"]).close()
            break
        except Exception:
            print("En attente de PostgreSQL…", flush=True)
            time.sleep(2)
EOF

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py seed_sources
  python manage.py collectstatic --noinput -v 0
fi

exec "$@"
