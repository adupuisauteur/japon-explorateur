"""
Configuration de J-ed (anciennement « Japon — Explorateur documentaire »).

Toute la configuration sensible passe par des variables d'environnement
(fichier .env en local, secrets du serveur en production). Aucun secret
ne doit être écrit dans ce fichier.
"""
import sys
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

# Numéro de version unique : fichier VERSION à la racine (application, rapports, archive livrée).
APP_VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
# 2.0.0 : nom affiché de l'application. Les noms techniques (projet Docker, images, volumes, dépôt) ne changent pas.
APP_NAME = "J-ed"
DATA_SCHEMA_VERSION = "1.0"

TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
# Commandes autorisées sans configuration de production (ex. générer les clés au premier démarrage).
_BOOTSTRAP_COMMAND = any(cmd in sys.argv for cmd in ("generate_secrets",))

DEV_SECRET_KEY = "dev-insecure-change-me"
SECRET_KEY = env("DJANGO_SECRET_KEY", default="") or DEV_SECRET_KEY
DEBUG = env.bool("DJANGO_DEBUG", default=False)
PLACEHOLDER_MARKERS = ("à-remplacer", "a-remplacer", "change-me", "changeme", "django-insecure")


def _is_weak_secret(value, min_length):
    low = (value or "").lower()
    return (not value or value == DEV_SECRET_KEY or len(value) < min_length
            or any(marker in low for marker in PLACEHOLDER_MARKERS) or len(set(value)) < 5)


# Aucune mise en service réelle avec la clé de développement ou une valeur d'exemple (audit, point 2).
if not DEBUG and not TESTING and not _BOOTSTRAP_COMMAND and _is_weak_secret(SECRET_KEY, 50):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY est absente, trop courte ou laissée à sa valeur d'exemple. "
        "Générez-la avec « python manage.py generate_secrets » et reportez-la dans .env."
    )
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.connectors",
    "apps.searching",
    "apps.updates",
    "apps.library",
    "apps.exports",
    "apps.ai",
    "apps.backups",
    "apps.incidents",
    "apps.translation",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
    "apps.core.middleware.FirstRunMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de données : PostgreSQL en référence ; SQLite toléré pour un essai rapide.
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
DATABASES["default"].setdefault("CONN_MAX_AGE", 60)
IS_POSTGRES = DATABASES["default"]["ENGINE"].endswith("postgresql")
if (IS_POSTGRES and not DEBUG and not TESTING and not _BOOTSTRAP_COMMAND
        and DATABASES["default"].get("HOST") not in ("", "localhost", "127.0.0.1")
        and _is_weak_secret(str(DATABASES["default"].get("PASSWORD") or ""), 16)):
    raise ImproperlyConfigured(
        "Le mot de passe PostgreSQL (POSTGRES_PASSWORD) est absent, trop court (16 caractères minimum) "
        "ou laissé à sa valeur d'exemple."
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = env("TZ", default="Europe/Paris")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# Stockage des fichiers (imports, archives, exports, sauvegardes).
# L'abstraction Django Storage permet de passer ultérieurement à un stockage objet.
DATA_DIR = Path(env("DATA_DIR", default=str(BASE_DIR / "data")))
MEDIA_ROOT = env("MEDIA_ROOT", default=str(DATA_DIR / "files"))
MEDIA_URL = "/fichiers/"
BACKUP_DIR = Path(env("BACKUP_DIR", default=str(DATA_DIR / "backups")))
BACKUP_EXTERNAL_DIR = env("BACKUP_EXTERNAL_DIR", default="")
# 2.0.0 : chemin du même dossier vu depuis l'ordinateur (DOSSIER_SAUVEGARDES de .env), pour l'affichage seulement.
BACKUP_EXTERNAL_HOST_DIR = env("DOSSIER_SAUVEGARDES", default="")

# Limites d'import (exigence de sécurité §14).
IMPORT_MAX_FILE_SIZE_MB = env.int("IMPORT_MAX_FILE_SIZE_MB", default=50)
IMPORT_ALLOWED_EXTENSIONS = [".csv", ".tsv", ".txt", ".xlsx", ".json", ".xml", ".mrc", ".marcxml"]
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Chiffrement des clés API des fournisseurs d'IA (clé Fernet, base64 urlsafe 32 octets).
# À générer avec : python manage.py generate_secrets
AI_KEYS_ENCRYPTION_KEY = env("AI_KEYS_ENCRYPTION_KEY", default="")
# Adresses de modèles locaux autorisées malgré le contrôle anti-SSRF (ex. http://host.docker.internal:11434/v1).
# Réglées uniquement par l'exploitant dans .env, jamais depuis l'interface.
AI_ALLOWED_LOCAL_URLS = env.list("AI_ALLOWED_LOCAL_URLS", default=[])
# 2.0.0 (lot 4) : IA locale (service Ollama facultatif, profil « ollama »). Adresse interne fixée ici, jamais depuis
# l'interface ; délai d'un résumé (calcul sur le processeur) et d'un téléchargement de modèle.
OLLAMA_URL = env.str("OLLAMA_URL", default="")
# Fenêtre de contexte demandée à l'IA locale (jetons) : consigne + passage + réponse. Plus grand = plus de mémoire.
OLLAMA_NUM_CTX = env.int("OLLAMA_NUM_CTX", default=8192)
OLLAMA_TIMEOUT = env.int("OLLAMA_TIMEOUT", default=900)

# Police japonaise pour les PDF (TrueType). Si absente, police CID intégrée à ReportLab.
PDF_JAPANESE_FONT = env("PDF_JAPANESE_FONT", default="")
PDF_JAPANESE_FONT_CANDIDATES = [
    # polices proportionnelles d'abord (meilleure lisibilité du texte latin et japonais)
    "/usr/share/fonts/opentype/ipaexfont-mincho/ipaexm.ttf",
    "/usr/share/fonts/truetype/ipaexfont-mincho/ipaexm.ttf",
    "/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf",
    "/usr/share/fonts/truetype/ipaexfont-gothic/ipaexg.ttf",
    "/usr/share/fonts/opentype/ipafont-mincho/ipamp.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]

# Polices de secours (caractère par caractère) pour les idéogrammes rares, ex. 𠮷 (U+20BB7).
# TrueType uniquement (ReportLab n'incorpore pas les contours CFF/PostScript).
PDF_FALLBACK_FONTS = env.list("PDF_FALLBACK_FONTS", default=[]) + [
    "/usr/share/fonts/truetype/hanazono/HanaMinA.ttf",
    "/usr/share/fonts/truetype/hanazono/HanaMinB.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# Connecteurs externes
# Identifiant d'application CiNii (gratuit, nominatif) : uniquement dans .env, jamais en base ni dans les journaux.
CINII_APPID = env("CINII_APPID", default="")
CONNECTOR_USER_AGENT = env(
    "CONNECTOR_USER_AGENT",
    default=f"J-ed/{APP_VERSION} (usage de recherche personnel)",  # décision D9 (2.0.0)
)
CONNECTOR_DEFAULT_TIMEOUT = env.float("CONNECTOR_DEFAULT_TIMEOUT", default=20.0)
CONNECTOR_CACHE_SECONDS = env.int("CONNECTOR_CACHE_SECONDS", default=3600)

# Module de traduction (1.3.0)
TRANSLATION_DEFAULT_TIMEOUT = env.float("TRANSLATION_DEFAULT_TIMEOUT", default=60.0)
TRANSLATION_TIMEOUTS = {
    "deepl": env.float("TRANSLATION_TIMEOUT_DEEPL", default=60.0),
    "google_basic": env.float("TRANSLATION_TIMEOUT_GOOGLE", default=60.0),
    "argos": env.float("TRANSLATION_TIMEOUT_ARGOS", default=180.0),
}
# Adresse interne du service Argos (démarré avec J-ed depuis la 2.0.0 : COMPOSE_PROFILES=argos). Vide = non activé.
TRANSLATION_ARGOS_URL = env("TRANSLATION_ARGOS_URL", default="")
# Dossier partagé avec le service Argos (volume « argos-depot ») pour installer un paquet depuis un fichier.
TRANSLATION_ARGOS_DEPOT_DIR = Path(env("TRANSLATION_ARGOS_DEPOT_DIR", default=str(DATA_DIR / "argos-depot")))
TRANSLATION_ARGOS_INSTALL_TIMEOUT = env.float("TRANSLATION_ARGOS_INSTALL_TIMEOUT", default=1800.0)
# 2.0.0 (lot 7) : une tâche Argos d'au plus ce nombre d'éléments est « prioritaire » dans le service : elle passe
# avant les paquets d'un long document en attente (elle attend au plus la fin du paquet en cours).
TRANSLATION_ARGOS_NOW_MAX_ITEMS = env.int("TRANSLATION_ARGOS_NOW_MAX_ITEMS", default=20)
# 2.0.0 (lot 3) : délai de l'essai automatique d'Argos après le démarrage (secondes), et entre deux tentatives.
ARGOS_AUTO_SELFTEST_DELAY = env.int("ARGOS_AUTO_SELFTEST_DELAY", default=120)
# 2.0.0 (lot 3) : durée de conservation des notifications LUES (les non lues sont toujours gardées).
NOTIFICATIONS_RETENTION_DAYS = env.int("NOTIFICATIONS_RETENTION_DAYS", default=90)
TRANSLATION_ARGOS_MAX_UPLOAD = env.int("TRANSLATION_ARGOS_MAX_UPLOAD", default=1024 * 1024 * 1024)
# Tâche sans signe d'activité au-delà de ce délai (minutes) : présentée comme interrompue, reprise possible.
TRANSLATION_STALE_MINUTES = env.int("TRANSLATION_STALE_MINUTES", default=10)
# Alerte « contient encore du japonais » au-delà de cette part de caractères japonais dans la traduction.
TRANSLATION_JAPANESE_ALERT_SHARE = env.float("TRANSLATION_JAPANESE_ALERT_SHARE", default=0.3)
# Pendant les tests, tout appel réseau réel d'un moteur de traduction est refusé (réponses enregistrées seulement).
TRANSLATION_BLOCK_NETWORK = env.bool("TRANSLATION_BLOCK_NETWORK", default=len(sys.argv) > 1 and sys.argv[1] == "test")

# Cache partagé : indispensable pour que la limitation des connexions vaille pour tous les processus gunicorn.
if env("CACHE_URL", default=""):
    CACHES = {"default": env.cache("CACHE_URL")}
elif env("REDIS_URL", default="") and not TESTING:
    _redis_cache = env("REDIS_URL").rsplit("/", 1)[0] + "/1"
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": _redis_cache}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Limitation des tentatives de connexion (par identifiant + adresse IP).
LOGIN_MAX_FAILURES = env.int("LOGIN_MAX_FAILURES", default=5)
LOGIN_LOCKOUT_SECONDS = env.int("LOGIN_LOCKOUT_SECONDS", default=15 * 60)

# Jeton de première configuration : obligatoire en HTTPS (serveur accessible à d'autres personnes).
SETUP_TOKEN = env("SETUP_TOKEN", default="")

# Celery : tâches asynchrones. Sans Redis, exécution immédiate (mode « eager »).
CELERY_BROKER_URL = env("REDIS_URL", default="")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_EAGER", default=not bool(CELERY_BROKER_URL))
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TIMEZONE = TIME_ZONE
# 2.0.0 (lot 3) : profil de machine calculé au démarrage (config/profil_machine.py ; JED_PROFIL dans .env)
from config.profil_machine import current as _machine_profile  # noqa: E402

MACHINE_PROFILE = _machine_profile()
CELERY_WORKER_CONCURRENCY = MACHINE_PROFILE["courts"]
# 1.3.0 : file dédiée aux traductions (le worker écoute « celery » et « traduction », docker-compose.yml)
# 2.0.0 (lot 3) : trois files, trois workers. « celery » : travaux courts (exports, synchronisations, sauvegardes,
# horloge) ; « traduction » : travaux longs et file de nuit ; « maintenant » : demandes depuis une fiche et petites
# tâches (la file est choisie par la tâche elle-même, voir apps/translation/queue.py). Les noms exacts passent
# avant le motif.
CELERY_TASK_ROUTES = {
    "apps.translation.tasks.clock": {"queue": "celery"},
    "apps.translation.tasks.auto_argos_selftest": {"queue": "celery"},
    "apps.translation.tasks.run_argos_selftest": {"queue": "celery"},
    "apps.translation.tasks.*": {"queue": "traduction"},
}
CELERY_BEAT_SCHEDULE = {
    "synchronisations-planifiees": {
        "task": "apps.updates.tasks.run_due_syncs",
        "schedule": crontab(minute=7),
    },
    "purge-sessions-temporaires": {
        "task": "apps.searching.tasks.purge_expired_sessions",
        "schedule": crontab(hour=3, minute=17),
    },
    "ia-brouillons-abandonnes": {
        "task": "apps.ai.tasks.purge_stale_drafts",
        "schedule": crontab(hour=3, minute=41),
    },
    "sauvegarde-quotidienne": {
        "task": "apps.backups.tasks.scheduled_backup",
        "schedule": crontab(hour=2, minute=23),
    },
    # 2.0.0 (lot 3) : nettoyage des notifications lues de plus de NOTIFICATIONS_RETENTION_DAYS jours.
    "notifications-anciennes": {
        "task": "apps.notifications.tasks.purge_old_notifications",
        "schedule": crontab(hour=3, minute=53),
    },
    # 2.0.0 (lot 3) : horloge des tâches de traduction (programmées, file de nuit, compte rendu du matin).
    "horloge-taches": {
        "task": "apps.translation.tasks.clock",
        "schedule": crontab(minute="*"),
    },
    # 2.0.0 : signe de vie du planificateur et d'un worker (page « État de l'installation »).
    "signe-de-vie": {
        "task": "apps.core.tasks.heartbeat",
        "schedule": crontab(minute="*/5"),
    },
    # 2.0.0 (lot 2) : reprise des vérifications IIIF demandées et interrompues (arrêt de Docker, du worker).
    "verification-iiif-reprise": {
        "task": "apps.catalog.tasks.verify_iiif_pending",
        "schedule": crontab(minute="3-59/10"),
    },
}
#: 2.0.0 (lot 2) : délai entre deux vérifications de manifeste IIIF (respect des sites interrogés).
IIIF_CHECK_DELAY_SECONDS = env.float("IIIF_CHECK_DELAY_SECONDS", default=2.0)
#: 2.0.0 : au-delà de ce délai sans signe de vie, le planificateur ou les workers sont signalés arrêtés.
HEARTBEAT_STALE_MINUTES = env.int("HEARTBEAT_STALE_MINUTES", default=15)

# Sécurité : HTTPS obligatoire hors boucle locale (§14).
SECURE_HTTPS = env.bool("SECURE_HTTPS", default=False)
if SECURE_HTTPS and not SETUP_TOKEN and not DEBUG and not TESTING and not _BOOTSTRAP_COMMAND:
    raise ImproperlyConfigured(
        "SECURE_HTTPS=true exige SETUP_TOKEN dans .env (protège l'assistant de première configuration). "
        "Générez-le avec « python manage.py generate_secrets »."
    )
if SECURE_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=60 * 60 * 12)
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact": {"()": "apps.core.logging.RedactSecretsFilter"}},
    "formatters": {"simple": {"format": "{asctime} {levelname} {name} : {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple", "filters": ["redact"]}},
    "root": {"handlers": ["console"], "level": "CRITICAL" if TESTING else env("LOG_LEVEL", default="INFO")},
    "loggers": {"httpx": {"level": "WARNING"}, "httpcore": {"level": "WARNING"}},
}

# 2.0.0 : les tests ne touchent jamais aux dossiers, à la file de tâches ni aux services de l'installation où
# ils sont lancés (« verifier-j-ed.ps1 -AvecTests » les exécute dans le conteneur web). Constat du 15 novembre
# 2026 : sans cette isolation, des sauvegardes fictives étaient copiées dans le dossier Windows des sauvegardes
# et des tâches d'essai envoyées à la file Redis de l'installation.
if TESTING:
    import atexit
    import shutil
    import tempfile

    DATA_DIR = Path(tempfile.mkdtemp(prefix="jed-tests-donnees-"))
    atexit.register(shutil.rmtree, DATA_DIR, ignore_errors=True)
    MEDIA_ROOT = str(DATA_DIR / "files")
    BACKUP_DIR = DATA_DIR / "backups"
    BACKUP_EXTERNAL_DIR = ""
    BACKUP_EXTERNAL_HOST_DIR = ""
    TRANSLATION_ARGOS_DEPOT_DIR = DATA_DIR / "argos-depot"
    TRANSLATION_ARGOS_URL = ""
    AI_ALLOWED_LOCAL_URLS = []
    OLLAMA_URL = ""
    CINII_APPID = ""
    CELERY_BROKER_URL = ""
    CELERY_TASK_ALWAYS_EAGER = True
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
