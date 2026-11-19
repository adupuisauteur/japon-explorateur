"""Étude des sources du lot 10 (lecture seule) — voir apps/core/etude_sources.py."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.core import etude_sources as E

REPORT = Path("/tmp/etude-sources.txt")


class Command(BaseCommand):
    help = ("Interroge une seule fois NDL Search, Japan Search, Kokusho, Waseda, Aozora Bunko et l'Historiographical "
            "Institute pour décrire leurs réponses (lecture seule, rien n'est enregistré). À lancer sur le poste.")

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Sortie JSON.")
        parser.add_argument("--plan", type=int, default=3, choices=[1, 2, 3],
                            help="1 : première étude ; 2 : second passage ; 3 (défaut) : accès des numérisations NDL.")
        parser.add_argument("--pause", type=float, default=1.0, help="Secondes entre deux requêtes (défaut 1).")

    def handle(self, *args, **opts):
        self.stderr.write("Étude des sources : au plus une trentaine de requêtes espacées d'une seconde…")
        study = E.Study(pause=max(0.5, opts["pause"]))
        steps = study.run(E.ndl_digital_ids(), plan=opts["plan"])
        report = f"Plan {opts['plan']}\n" + E.text_report(steps, study.requests)
        try:
            REPORT.write_text(report, encoding="utf-8")
            where = f"\nRapport enregistré dans le conteneur. Pour le copier dans le dossier courant :\n" \
                    f"  docker compose cp web:{REPORT} etude-sources.txt"
        except OSError:
            where = ""
        if opts["json"]:
            self.stdout.write(json.dumps([s.__dict__ for s in steps], ensure_ascii=False, indent=1))
        else:
            self.stdout.write(report + where)
