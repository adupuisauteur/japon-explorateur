from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Restaure une sauvegarde (.tar). REMPLACE la base et les fichiers actuels."

    def add_arguments(self, parser):
        parser.add_argument("archive")
        parser.add_argument("--yes", action="store_true", help="Confirmer sans question interactive.")
        parser.add_argument("--db-only", action="store_true")
        parser.add_argument("--files-only", action="store_true")
        parser.add_argument("--sans-securite", action="store_true",
                            help="Ne pas créer de sauvegarde de sécurité avant la restauration.")

    def handle(self, *args, **options):
        from apps.backups.services import restore_backup

        if not options["yes"]:
            answer = input("La base et les fichiers actuels seront remplacés. Taper RESTAURER pour confirmer : ")
            if answer.strip() != "RESTAURER":
                raise CommandError("Restauration annulée.")
        if not options["sans_securite"]:
            from apps.backups.services import create_backup

            safety = create_backup("full")
            if safety.status != "done":
                raise CommandError(f"Sauvegarde de sécurité impossible ({safety.message}) : restauration annulée.")
            self.stdout.write(f"Sauvegarde de sécurité créée : {safety.path}")
        log = restore_backup(options["archive"], restore_db=not options["files_only"],
                             restore_files=not options["db_only"])
        for line in log:
            self.stdout.write(self.style.SUCCESS(line))
        self.stdout.write("Pensez à réintroduire DJANGO_SECRET_KEY et AI_KEYS_ENCRYPTION_KEY d'origine.")
