#!/bin/sh
set -e

# Isolation (1.3.0) : refus de démarrer sous le nom de projet Docker de l'installation principale
# ou de l'installation d'essai 1.2.0, ce qui ferait utiliser leur base de données et leurs fichiers.
case "${COMPOSE_PROJECT_CHECK:-}" in
  japon-explorateur|japon-explorateur-essai)
    echo "ARRÊT : le projet Docker « ${COMPOSE_PROJECT_CHECK} » appartient à une autre installation" >&2
    echo "(principale ou essai 1.2.0). Corrigez COMPOSE_PROJECT_NAME dans .env (valeur attendue :" >&2
    echo "japon-explorateur-essai-130), puis relancez « docker compose up -d »." >&2
    exit 1 ;;
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
