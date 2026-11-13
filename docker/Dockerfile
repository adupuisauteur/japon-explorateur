FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    STATIC_ROOT=/app/staticfiles

# Client PostgreSQL (sauvegardes pg_dump/pg_restore) et polices japonaises incorporables dans les PDF
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client fonts-ipaexfont-mincho fonts-ipaexfont-gothic fonts-hanazono curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x docker/entrypoint.sh \
 && useradd --create-home --uid 1000 japon \
 && mkdir -p /data && chown -R japon:japon /data /app

USER japon
EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "180", "--access-logfile", "-"]
