from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée une sauvegarde (base + fichiers par défaut)."

    def add_arguments(self, parser):
        parser.add_argument("--kind", choices=["full", "db", "files"], default="full")
        parser.add_argument("--verify", action="store_true", help="Vérifier l'intégrité après création.")

    def handle(self, *args, **options):
        from apps.backups.services import create_backup, verify_backup

        job = create_backup(options["kind"])
        self.stdout.write(f"{job.get_status_display()} : {job.path} ({job.size} octets) — {job.message}")
        if options["verify"] and job.status == "done":
            ok, msg = verify_backup(job)
            self.stdout.write(msg)
