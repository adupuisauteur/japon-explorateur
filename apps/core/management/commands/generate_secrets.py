import secrets
import string

from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Génère DJANGO_SECRET_KEY, AI_KEYS_ENCRYPTION_KEY, POSTGRES_PASSWORD et SETUP_TOKEN (à copier dans .env)."

    def handle(self, *args, **options):
        # Caractères sans risque dans .env : Docker Compose interprète « $ » et « # » peut couper la ligne.
        safe = string.ascii_letters + string.digits + "-_"
        self.stdout.write(f"DJANGO_SECRET_KEY={''.join(secrets.choice(safe) for _ in range(64))}")
        self.stdout.write(f"AI_KEYS_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
        alphabet = string.ascii_letters + string.digits  # sans @ : / # qui casseraient l'adresse de la base
        self.stdout.write(f"POSTGRES_PASSWORD={''.join(secrets.choice(alphabet) for _ in range(32))}")
        self.stdout.write(f"SETUP_TOKEN={''.join(secrets.choice(alphabet) for _ in range(24))}")
        self.stdout.write(self.style.WARNING("Conservez ces valeurs hors du dépôt et hors des sauvegardes de la base."))
