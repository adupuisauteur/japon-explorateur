"""Vérification des fonctionnalités avec des données fictives (2.0.0) — voir apps/core/verification.py.

La base n'est pas modifiée (transaction annulée). Code de sortie 1 si une vérification est en « Problème ».
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Exerce les fonctions principales avec des données fictives, sans modifier la base."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Sortie JSON (pour verifier-j-ed.ps1).")
        parser.add_argument("--sources", action="store_true",
                            help="Tester aussi chaque source en ligne (une requête d'essai par source, Internet).")

    def handle(self, *args, **options):
        from django.conf import settings

        from apps.core import verification as V

        from django.db import OperationalError

        try:
            results = V.run(with_sources=options["sources"])
        except OperationalError as exc:  # base injoignable : message clair, pas de trace Python
            raise CommandError(f"Problème : base de données injoignable ({' '.join(str(exc).split())[:300]}). "
                               "Vérifiez le conteneur « db » dans Docker Desktop.") from None
        if options["json"]:
            self.stdout.write(json.dumps({
                "version": settings.APP_VERSION, "etat": V.overall(results),
                "verifications": [{"cle": r.key, "libelle": r.label, "niveau": r.level, "resume": r.summary,
                                   "details": r.details} for r in results],
            }, ensure_ascii=False, indent=1))
        else:
            self.stdout.write(V.report_text(results))
        errors = [r for r in results if r.level == V.ERROR]
        if errors:
            raise CommandError("Problème : " + " ; ".join(f"{r.label} — {r.summary}" for r in errors))
