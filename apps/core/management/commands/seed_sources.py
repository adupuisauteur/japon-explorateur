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
         access_method="Les liens vers les documents numérisés sont repris des notices NDL Search (rdfs:seeAlso → "
                       "dl.ndl.go.jp). Pas de connecteur de recherche séparé dans la 1.2.0."),
    dict(code="japansearch", name="Japan Search", name_original="ジャパンサーチ", connector="japansearch",
         status="partial", enabled_for_search=False, sort_order=30, base_url="https://jpsearch.go.jp/",
         role="Agrégateur national de métadonnées patrimoniales.",
         terms_url="https://jpsearch.go.jp/static/developer/webapi/",
         access_method="API web simple officielle, sans clé (JSON) : recherche transversale, filtre par base, période "
                       "(r-tempo), personne (q-contributor). Permet de créer des sources limitées à une base "
                       "(archives, universités…) via « Trouver une base Japan Search »."),
    dict(code="cinii", name="CiNii Research", name_original="CiNii Research（国立情報学研究所）", connector="cinii",
         status="partial", enabled_for_search=False, sort_order=35,
         institution=("National Institute of Informatics (NII)", "国立情報学研究所", "Institut de recherche",
                      "https://www.nii.ac.jp/"),
         base_url="https://cir.nii.ac.jp/", terms_url="https://support.nii.ac.jp/ja/cir/r_opensearch",
         role="Articles, revues savantes, thèses, livres des bibliothèques universitaires et données de recherche.",
         access_method="API OpenSearch officielle (JSON-LD). Identifiant d'application gratuit obligatoire "
                       "(CINII_APPID dans .env).",
         license_notes="Métadonnées CiNii : voir les conditions d'utilisation de l'API (support.nii.ac.jp).",
         min_interval_seconds=1.0),
    dict(code="cinii-books", name="CiNii — bibliothèques universitaires", name_original="CiNii Research（図書・雑誌）",
         connector="cinii", config={"search_type": "books"}, status="partial", enabled_for_search=False,
         sort_order=36, base_url="https://ci.nii.ac.jp/books/", terms_url="https://support.nii.ac.jp/ja/cir/r_opensearch",
         role="Catalogue collectif des bibliothèques universitaires japonaises (livres anciens et modernes, revues).",
         access_method="API OpenSearch de CiNii Research, type « books ». Même identifiant d'application que CiNii Research.",
         min_interval_seconds=1.0),
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
    dict(code="nat-archives", name="National Archives of Japan (via Japan Search)", name_original="国立公文書館",
         connector="japansearch", config={"database": "najda"}, status="partial", enabled_for_search=False,
         sort_order=50, base_url="https://www.digital.archives.go.jp/",
         terms_url="https://jpsearch.go.jp/static/developer/webapi/",
         institution=("National Archives of Japan", "国立公文書館", "Archives nationales", "https://www.archives.go.jp/"),
         role="Archives et documents administratifs et historiques (fonds du Cabinet, archives Tokugawa, Meiji…).",
         access_method="API officielle de Japan Search filtrée sur la base « najda » (国立公文書館デジタルアーカイブ, "
                       "diffusion par API autorisée). Pas d'API publique propre identifiée ; consultation des images "
                       "sur le site de la Digital Archive.", min_interval_seconds=1.0),
    # 2.0.0 (lot 10)
    dict(code="aozora", name="Aozora Bunko", name_original="青空文庫", connector="aozora", status="available",
         sort_order=55, base_url="https://www.aozora.gr.jp/", terms_url="https://www.aozora.gr.jp/guide/kijyunn.html",
         role="Textes intégraux d'œuvres japonaises, surtout modernes (Meiji à Shōwa), dans le domaine public pour la "
              "plupart.",
         access_method="Liste de toutes les œuvres publiée par Aozora Bunko (CSV compressé, licence CC BY), importée "
                       "par « Synchroniser » ; texte d'une œuvre téléchargé à la demande depuis sa fiche (fichier zip "
                       "ou XHTML). Aucune page de navigation n'est lue.",
         license_notes="Liste des œuvres : CC BY. Textes : domaine public, sauf œuvres signalées « protégées » "
                       "(publiées avec l'accord des ayants droit). Garder la mention du texte source (底本) et "
                       "d'Aozora Bunko.",
         min_interval_seconds=2.0, timeout_seconds=60.0),
    dict(code="waseda", name="Waseda Kotenseki Sōgō Database", name_original="古典籍総合データベース",
         status="to_study", sort_order=60, base_url="https://www.wul.waseda.ac.jp/kotenseki/",
         role="Collections de textes anciens.",
         access_method="Pas d'API publique identifiée : consultation externe. Si la base est diffusée par Japan Search, "
                       "créez une source avec « Trouver une base Japan Search » (recherche 早稲田)."),
    dict(code="kyoto", name="Kyoto University Digital Archive", name_original="京都大学貴重資料デジタルアーカイブ",
         status="to_study", sort_order=70, base_url="https://rmda.kulib.kyoto-u.ac.jp/",
         role="Collections et documents rares.",
         access_method="Manifestes IIIF par document ; pas d'API de recherche publique identifiée. Si la base est "
                       "diffusée par Japan Search, utilisez « Trouver une base Japan Search » (recherche 京都大学)."),
    dict(code="utokyo-hi", name="University of Tokyo HI / SHIPS", name_original="東京大学史料編纂所",
         status="to_study", sort_order=80, base_url="https://www.hi.u-tokyo.ac.jp/",
         role="Catalogues et bases d'histoire japonaise.",
         access_method="Bases SHIPS consultables en ligne ; aucune API publique documentée identifiée : consultation "
                       "externe uniquement dans la 1.2.0."),
    dict(code="nijl-specialized", name="NIJL et bases spécialisées", status="to_study", sort_order=90,
         role="Répertoires et bases de recherche sur les textes anciens.",
         access_method="Étude par base, sans présumer d'une API uniforme."),
    dict(code="others", name="Nichibunken, Tōyō Bunko, Iwase Bunko, Ritsumeikan ARC…", status="to_study",
         sort_order=99, role="Sources spécialisées complémentaires.",
         access_method="Ajout au cas par cas : d'abord via « Trouver une base Japan Search » (日文研, 東洋文庫, "
                       "立命館…), sinon consultation externe."),
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
