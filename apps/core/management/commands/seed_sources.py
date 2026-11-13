"""Répertorie les sources documentaires du §5.1 (idempotent : ne modifie pas une source déjà configurée)."""
import datetime

from django.core.management.base import BaseCommand

from apps.catalog.models import Catalogue, Institution

SOURCES = [
    dict(code="local", name="Base locale", connector="local", status="available", enabled_for_search=True,
         sort_order=1, role="Notices déjà importées ou enregistrées dans l'application.",
         access_method="Interrogation directe de la base PostgreSQL de l'application."),
    dict(code="kokusho", name="Kokusho Database", name_original="国書データベース", connector="kokusho",
         status="partial", enabled_for_search=True, sort_order=10, frequency="weekly",
         institution=("National Institute of Japanese Literature (NIJL)", "国文学研究資料館", "Institut de recherche",
                      "https://www.nijl.ac.jp/"),
         base_url="https://kokusho.nijl.ac.jp/", terms_url="https://kokusho.nijl.ac.jp/page/en/about.html",
         role="Notices et images de manuscrits et imprimés anciens (catalogue collectif des textes japonais).",
         access_method="1) Notice par identifiant ou DOI via le manifeste IIIF officiel ; 2) recherche plein texte via "
                       "l'API de Japan Search filtrée sur le fonds Kokusho ; 3) import de fichiers. Aucune API de "
                       "recherche propre documentée à la date de l'étude : statut « Partiel ».",
         license_notes="Images du NIJL : statut « Public Domain » annoncé pour les collections du NIJL ; les autres "
                       "institutions ont leurs propres conditions. Vérifier chaque notice avant téléchargement.",
         unsupported_fields="Traductions, lecture du nom d'auteur selon les notices.",
         min_interval_seconds=1.5),
    dict(code="ndl", name="NDL Search", name_original="国立国会図書館サーチ", connector="ndl", status="available",
         enabled_for_search=False, sort_order=20,
         institution=("National Diet Library", "国立国会図書館", "Bibliothèque nationale", "https://www.ndl.go.jp/"),
         base_url="https://ndlsearch.ndl.go.jp/", terms_url="https://ndlsearch.ndl.go.jp/help/api",
         license_notes="Seules les données dont la diffusion est autorisée sont servies par l'API ; une demande d'utilisation peut être requise selon l'usage et le fournisseur de données (voir les conditions).",
         role="Catalogue de la Bibliothèque nationale de la Diète.",
         access_method="API OpenSearch officielle (RSS 2.0 + DC-NDL).", min_interval_seconds=1.0),
    dict(code="ndl-digital", name="NDL Digital Collections", name_original="国立国会図書館デジタルコレクション",
         status="to_study", sort_order=25, base_url="https://dl.ndl.go.jp/",
         role="Consultation de collections numérisées.",
         access_method="Liens vers documents ; téléchargement seulement si autorisé (à étudier : IIIF, API)."),
    dict(code="japansearch", name="Japan Search", name_original="ジャパンサーチ", connector="japansearch",
         status="partial", enabled_for_search=False, sort_order=30, base_url="https://jpsearch.go.jp/",
         terms_url="https://jpsearch.go.jp/", role="Agrégateur national de métadonnées patrimoniales.",
         access_method="API web simple de recherche transversale (JSON). Adresse et paramètres configurables : à confirmer avec « Tester le connecteur » et la documentation officielle avant usage intensif."),
    dict(code="codh-pmjt", name="CODH — PMJT (inventaire 2019)", name_original="日本古典籍データセット",
         status="available", sort_order=40, is_snapshot=True, snapshot_date=datetime.date(2019, 1, 1),
         institution=("ROIS-DS Center for Open Data in the Humanities", "人文学オープンデータ共同利用センター",
                      "Centre de recherche", "http://codh.rois.ac.jp/"),
         base_url="http://codh.rois.ac.jp/pmjt/",
         role="Inventaire de livres anciens et notices déjà collectées (instantané CSV de 2019, 3 126 notices).",
         access_method="Import du CSV fourni, conservé comme jeu de données historique ; vérifier les possibilités de "
                       "mise à jour.", notes="Instantané daté de 2019 : ni actuel ni exhaustif."),
    dict(code="classeur", name="Classeur documentaire central", status="available", sort_order=45,
         role="Classeur de travail existant et notices sélectionnées.",
         access_method="Import de fichier (XLSX/CSV) avec conservation des identifiants et de la provenance."),
    dict(code="nat-archives", name="National Archives of Japan", name_original="国立公文書館", status="to_study",
         sort_order=50, base_url="https://www.archives.go.jp/",
         role="Archives et documents administratifs et historiques.",
         access_method="Connecteur selon interfaces et possibilités d'export (à étudier)."),
    dict(code="waseda", name="Waseda Kotenseki Sōgō Database", name_original="古典籍総合データベース",
         status="to_study", sort_order=60, base_url="https://www.wul.waseda.ac.jp/kotenseki/",
         role="Collections de textes anciens.", access_method="Recherche et liens vers notices/images selon conditions."),
    dict(code="kyoto", name="Kyoto University Digital Archive", name_original="京都大学貴重資料デジタルアーカイブ",
         status="to_study", sort_order=70, base_url="https://rmda.kulib.kyoto-u.ac.jp/",
         role="Collections et documents rares.", access_method="Connecteur selon API, exports et finding aids."),
    dict(code="utokyo-hi", name="University of Tokyo HI / SHIPS", name_original="東京大学史料編纂所",
         status="to_study", sort_order=80, base_url="https://www.hi.u-tokyo.ac.jp/",
         role="Catalogues et bases d'histoire japonaise.",
         access_method="Connecteurs distincts selon sous-bases et restrictions (à étudier)."),
    dict(code="nijl-specialized", name="NIJL et bases spécialisées", status="to_study", sort_order=90,
         role="Répertoires et bases de recherche sur les textes anciens.",
         access_method="Étude par base, sans présumer d'une API uniforme."),
    dict(code="others", name="Nichibunken, Tōyō Bunko, Iwase Bunko, Ritsumeikan ARC…", status="to_study",
         sort_order=99, role="Sources spécialisées complémentaires.",
         access_method="Ajout progressif après étude technique et juridique."),
]


class Command(BaseCommand):
    help = "Répertorie les sources documentaires prévues (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for spec in SOURCES:
            spec = dict(spec)
            inst = spec.pop("institution", None)
            if Catalogue.objects.filter(code=spec["code"]).exists():
                continue
            if inst:
                spec["institution"], _ = Institution.objects.get_or_create(
                    name=inst[0], defaults={"name_original": inst[1], "kind": inst[2], "url": inst[3]})
            Catalogue.objects.create(**spec)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"{created} source(s) ajoutée(s)."))
