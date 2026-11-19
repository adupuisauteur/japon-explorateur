"""État de l'installation (2.0.0) : mêmes contrôles que la page « État », pour le terminal et mettre-a-jour.ps1.

Code de sortie 1 si un contrôle est en erreur (« Problème »), 0 sinon. --json pour une sortie lisible par un script.
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Affiche l'état de l'installation ; code de sortie 1 si un contrôle est en erreur."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Sortie JSON (version, état général, contrôles).")

    def handle(self, *args, **options):
        from django.conf import settings

        from apps.core import health

        results = health.collect()
        state = health.overall(results)
        if options["json"]:
            self.stdout.write(json.dumps({
                "version": settings.APP_VERSION, "etat": state,
                "controles": [{"cle": r.key, "libelle": r.label, "niveau": r.level, "resume": r.summary,
                               "details": r.details} for r in results],
            }, ensure_ascii=False, indent=1))
        else:
            self.stdout.write(health.diagnostic_text(results))
        errors = [r for r in results if r.level == health.ERROR]
        if errors:
            raise CommandError("Problème : " + " ; ".join(f"{r.label} — {r.summary}" for r in errors))
