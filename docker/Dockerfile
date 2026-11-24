FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    STATIC_ROOT=/app/staticfiles

# Client PostgreSQL (sauvegardes pg_dump/pg_restore) et polices japonaises incorporables dans les PDF.
# 2.0.2 : derrière un proxy (argument de construction HTTP_PROXY, réglé par l'assistant), apt ne lit que les noms en
# minuscules : ils lui sont donnés pour cette commande seulement (rien n'est gardé dans l'image).
RUN if [ -n "$HTTP_PROXY" ]; then export http_proxy="$HTTP_PROXY"; fi \
 && if [ -n "$HTTPS_PROXY" ]; then export https_proxy="$HTTPS_PROXY"; fi \
 && if [ -n "$NO_PROXY" ]; then export no_proxy="$NO_PROXY"; fi \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client fonts-ipaexfont-mincho fonts-ipaexfont-gothic fonts-hanazono curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# 2.0.2-rc5 (R7) : réseau lent ou proxy : délai de 120 s et 10 nouvelles tentatives (pip : 15 s et 5 par défaut).
RUN pip install --timeout 120 --retries 10 -r requirements.txt

COPY . .
RUN chmod +x docker/entrypoint.sh \
 && useradd --create-home --uid 1000 japon \
 && mkdir -p /data /argos-depot /backups-externes \
 && chown -R japon:japon /data /app /argos-depot /backups-externes

USER japon
EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
# 2.0.0 (lot 3) : adresse, délai et nombre de processus dans config/gunicorn.conf.py (profil de machine).
CMD ["gunicorn", "config.wsgi:application", "-c", "config/gunicorn.conf.py"]
