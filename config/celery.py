import logging
import os

from celery import Celery
from celery.signals import beat_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("japon")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@beat_init.connect
def schedule_argos_selftest(sender=None, **kwargs):
    """2.0.0 (lot 3) : au démarrage de J-ed (installation, mise à jour, redémarrage), essai d'Argos 2 minutes plus
    tard. La tâche ne fait rien si Argos a déjà été essayé avec la version installée."""
    from django.conf import settings

    try:
        app.send_task("apps.translation.tasks.auto_argos_selftest", countdown=settings.ARGOS_AUTO_SELFTEST_DELAY)
        # 2.0.0 (lot 6) : même chose pour l'IA locale (rien si elle n'est pas installée ou déjà essayée avec succès)
        app.send_task("apps.translation.tasks.auto_local_ai_selftest", countdown=settings.ARGOS_AUTO_SELFTEST_DELAY)
    except Exception:  # noqa: BLE001 — le planificateur démarre quand même ; l'essai reste faisable à la main
        logging.getLogger(__name__).exception("Essai automatique d'Argos ou de l'IA locale non programmé")
