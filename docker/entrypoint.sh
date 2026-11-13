#!/bin/sh
set -e

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
