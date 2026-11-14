"""
Vérification AVANT un retour à la version 1.2.0 (procédure : docs/evolution-1.3.0/retour-1.2.0.md).

Commande en LECTURE SEULE : elle ne modifie ni ne supprime rien. Elle indique :
- les données du module de traduction, qui disparaîtront avec « migrate translation zero » ;
- les contenus d'origine « Traduction automatique » (couche éditoriale et champs de notices adoptés), qui
  RESTENT en base après le retour : la 1.2.0 ne connaît pas cette origine et les exporterait même quand
  l'option « Inclure traductions et contenus IA » est décochée ;
- les copies de glossaires envoyées à DeepL, qui restent sur les comptes DeepL.

Option --exporter FICHIER.json : copie de sauvegarde de ces données (lecture seule de la base).
"""
import json

from django.core import serializers
from django.core.management.base import BaseCommand

MIGRATIONS_RETOUR = [
    "docker compose run --rm -e RUN_MIGRATIONS=0 web python manage.py migrate translation zero",
    "docker compose run --rm -e RUN_MIGRATIONS=0 web python manage.py migrate catalog 0004",
    "docker compose run --rm -e RUN_MIGRATIONS=0 web python manage.py migrate incidents 0001",
]


class Command(BaseCommand):
    help = "Vérifie (sans rien modifier) ce qu'implique un retour à la 1.2.0 ; --exporter pour en garder une copie."

    def add_arguments(self, parser):
        parser.add_argument("--exporter", metavar="FICHIER", help="Fichier JSON de sauvegarde à écrire.")

    def handle(self, *args, **options):
        from apps.catalog.models import EditorialContent, Record

        from ...models import (EngineSetting, Glossary, GlossaryEntry, TranslationDocument, TranslationJob,
                               TranslationProject, TranslationSegment, TranslationVersion)

        out = self.stdout
        out.write("Vérification avant retour à la 1.2.0 — aucune donnée n'est modifiée.\n")
        out.write("\n1. Données du module de traduction (supprimées par « migrate translation zero ») :\n")
        counts = [("projets", TranslationProject), ("documents", TranslationDocument), ("segments", TranslationSegment),
                  ("traductions (versions)", TranslationVersion), ("glossaires", Glossary),
                  ("entrées de glossaire", GlossaryEntry), ("tâches", TranslationJob),
                  ("réglages de moteurs (clés chiffrées)", EngineSetting)]
        for label, model in counts:
            out.write(f"   - {label} : {model.objects.count()}\n")

        mt_editorial = EditorialContent.objects.filter(origin="mt")
        mt_title = Record.objects.filter(translated_title_origin="mt")
        mt_desc = Record.objects.filter(description_translation_origin="mt")
        out.write("\n2. Contenus d'origine « Traduction automatique » (CONSERVÉS en base après le retour) :\n")
        out.write(f"   - propositions dans la couche éditoriale : {mt_editorial.count()}\n")
        out.write(f"   - titres traduits adoptés dans des notices : {mt_title.count()}\n")
        out.write(f"   - descriptions traduites adoptées dans des notices : {mt_desc.count()}\n")
        if mt_editorial.exists() or mt_title.exists() or mt_desc.exists():
            out.write("   ATTENTION : la 1.2.0 ne connaît pas cette origine ; elle afficherait le code « mt » et\n"
                      "   inclurait ces contenus dans les exports même si « Inclure traductions et contenus IA »\n"
                      "   est décoché. Décidez avant le retour : les garder, ou les retirer vous-même.\n")

        remote = [g for g in Glossary.objects.all() if g.remote_copies]
        out.write(f"\n3. Glossaires ayant une copie chez DeepL : {len(remote)}"
                  + (" (supprimez-les d'abord dans Traduction → Glossaires, sinon elles restent sur DeepL)" if remote
                     else "") + "\n")

        out.write("\n4. Commandes de retour (après une sauvegarde complète, application arrêtée sauf la base ;\n"
                  "   procédure complète : docs/evolution-1.3.0/retour-1.2.0.md) :\n")
        for cmd in MIGRATIONS_RETOUR:
            out.write(f"   {cmd}\n")

        if options.get("exporter"):
            data = {
                "module_traduction": json.loads(serializers.serialize("json", [
                    *TranslationProject.objects.all(), *TranslationDocument.objects.all(),
                    *TranslationSegment.objects.all(), *TranslationVersion.objects.all(), *Glossary.objects.all(),
                    *GlossaryEntry.objects.all()])),
                "couche_editoriale_mt": json.loads(serializers.serialize("json", mt_editorial)),
                "notices_champs_mt": [
                    {"record_id": r.record_id, "champ": field, "valeur": getattr(r, field)}
                    for qs, field in ((mt_title, "translated_title"), (mt_desc, "description_translation"))
                    for r in qs],
            }
            with open(options["exporter"], "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            out.write(f"\nCopie écrite : {options['exporter']} (les clés des moteurs n'y figurent pas).\n")
