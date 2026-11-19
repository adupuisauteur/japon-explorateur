from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée une sauvegarde (base + fichiers par défaut). Code de sortie 1 en cas d'échec."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=["full", "db", "files"], default="full")
        parser.add_argument("--verify", action="store_true", help="Vérifier l'intégrité après création.")

    def handle(self, *args, **options):
        from apps.backups.services import create_backup, verify_backup

        job = create_backup(options["kind"])
        if job.status != "done":
            # 2.0.0 : un échec se termine par un code d'erreur (jamais « Échec » avec un code 0).
            raise CommandError(f"Sauvegarde en échec : {job.message}")
        self.stdout.write(self.style.SUCCESS(f"{job.get_status_display()} : {job.path} ({job.size} octets) — "
                                             f"{job.message}"))
        if job.external_copy:
            self.stdout.write(f"Copie externe : {job.external_copy}")
        if options["verify"]:
            ok, msg = verify_backup(job)
            if not ok:
                raise CommandError(f"Vérification de la sauvegarde en échec : {msg}")
            self.stdout.write(self.style.SUCCESS(msg))
