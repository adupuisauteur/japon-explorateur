from pathlib import Path

from django.core.management.base import BaseCommand

from apps.help.guide import build_html, build_markdown


class Command(BaseCommand):
    help = ("Produit le guide d'utilisation à partir de l'aide intégrée (docs/aide) : HTML autonome et Markdown. "
            "Pour un PDF : ouvrir le HTML dans le navigateur, puis Imprimer → Enregistrer au format PDF.")

    def add_arguments(self, parser):
        parser.add_argument("--dossier", default="docs", help="Dossier de sortie (par défaut : docs)")

    def handle(self, *args, **opts):
        out = Path(opts["dossier"])
        out.mkdir(parents=True, exist_ok=True)
        html, md = out / "guide-utilisation.html", out / "guide-utilisation.md"
        html.write_text(build_html(), encoding="utf-8")
        md.write_text(build_markdown(), encoding="utf-8")
        self.stdout.write(f"Guide écrit : {html} et {md}")
