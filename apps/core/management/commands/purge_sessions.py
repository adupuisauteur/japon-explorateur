from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Supprime les sessions de recherche temporaires expirées (jamais les notices intégrées)."

    def handle(self, *args, **options):
        from apps.searching.services import purge_expired

        self.stdout.write(f"{purge_expired()} session(s) supprimée(s).")
