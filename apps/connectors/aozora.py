"""
Connecteur Aozora Bunko — 青空文庫 (2.0.0, lot 10).

Accès (sans lecture de pages HTML de navigation) :
  1. Liste de toutes les œuvres, publiée par Aozora Bunko en CSV compressé (licence CC BY) :
     https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip
     Une ligne par couple (œuvre, personne) ; J-ed regroupe par œuvre. Importée par « Synchroniser » (Mises à
     jour), suivie en base et reprise après interruption (curseur), avec un rapport à valider comme les autres
     sources.
  2. Texte d'une œuvre, téléchargé à la demande depuis la fiche : fichier texte compressé (zip, Shift_JIS,
     notation 《ルビ》 et ［＃注記］) ou, à défaut, page XHTML. Voir apps/catalog/texts.py.

La recherche porte sur les notices déjà importées (aucune requête au site à chaque recherche).
Les colonnes sont lues par leur nom : un changement de l'ordre ne gêne pas ; une colonne indispensable absente
arrête l'import avec la liste des colonnes reçues.
"""
import csv
import io
import time
import zipfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .base import BaseConnector, ConnectorError, ConnectorResult, HarvestBatch, SearchResponse
from .http import ConnectorHTTP, format_error
from .registry import register

LIST_URL = "https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip"
REQUIRED = ["作品ID", "作品名", "図書カードURL"]
BATCH = 500
ROLES = {"著者": "", "翻訳者": "訳", "編者": "編", "校訂者": "校訂", "その他": ""}


def _cache_path(day):
    folder = Path(settings.MEDIA_ROOT) / "aozora"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"liste-{day:%Y%m%d}.zip"


def read_list(content):
    """Archive zip → lignes (dict par nom de colonne). Lève une erreur de format si la structure a changé."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
            if not names:
                raise format_error("Liste Aozora Bunko : aucun fichier CSV dans l'archive.", code="no_csv")
            raw = archive.read(names[0])
    except zipfile.BadZipFile as exc:
        raise format_error("Liste Aozora Bunko illisible (archive zip invalide).", content[:200].decode("latin-1"),
                           code="bad_zip") from exc
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise format_error(f"Liste Aozora Bunko : colonne(s) {', '.join(missing)} absente(s). Colonnes reçues : "
                           f"{', '.join(reader.fieldnames or [])[:400]}", code="columns_changed")
    return list(reader)


def _person(row):
    name = " ".join(p for p in (row.get("姓", ""), row.get("名", "")) if p).strip()
    reading = " ".join(p for p in (row.get("姓読み", ""), row.get("名読み", "")) if p).strip()
    role = (row.get("役割フラグ") or "著者").strip()
    return name, reading, role


def group_works(rows):
    """Une notice par œuvre : les lignes d'une même œuvre (une par personne) sont réunies."""
    works = {}
    for row in rows:
        work_id = (row.get("作品ID") or "").strip()
        if not work_id:
            continue
        work = works.setdefault(work_id, {"row": row, "people": []})
        person = _person(row)
        if person[0] and person not in work["people"]:
            work["people"].append(person)
    return [to_result(work_id, w["row"], w["people"]) for work_id, w in sorted(works.items())]


def to_result(work_id, row, people):
    authors = [p for p in people if p[2] == "著者"] or people[:1]
    others = [p for p in people if p not in authors]
    creator = " ; ".join(p[0] for p in authors)
    if others:
        creator += "".join(f" ; {p[0]}（{ROLES.get(p[2], p[2]) or p[2]}）" for p in others)
    title = (row.get("作品名") or "").strip()
    subtitle = (row.get("副題") or "").strip()
    protected = (row.get("作品著作権フラグ") or "").strip() == "あり"
    base = " ; ".join(v for v in (row.get("底本名1", ""), row.get("底本出版社名1", ""),
                                  row.get("底本初版発行年1", "")) if v)
    description = " ".join(v for v in (
        f"初出：{row['初出']}" if row.get("初出") else "",
        f"底本：{base}" if base else "",
        f"文字遣い：{row['文字遣い種別']}" if row.get("文字遣い種別") else "",
        f"入力：{row['入力者']} ; 校正：{row['校正者']}" if row.get("入力者") else "") if v)
    data = {
        "source_id": work_id,
        "source_url": (row.get("図書カードURL") or "").strip(),
        "digital_access_url": (row.get("XHTML/HTMLファイルURL") or "").strip(),
        "digital_access": "fulltext" if row.get("XHTML/HTMLファイルURL") or row.get("テキストファイルURL") else "",
        "original_title": f"{title}　{subtitle}" if subtitle else title or "(sans titre)",
        "reading": (row.get("作品名読み") or "").strip(),
        "creator_original": creator,
        "creator_reading": " ; ".join(p[1] for p in authors if p[1]),
        "description_original": description,
        "copy_date_text": (row.get("底本初版発行年1") or "").strip(),
        "subjects_original": (row.get("分類番号") or "").strip(),
        "material_type_original": "電子テキスト",
        "document_type_original": "texte numérique",
        "holding_institution_text": "青空文庫",
        "rights_and_access": ("Œuvre protégée par le droit d'auteur, publiée par Aozora Bunko avec l'accord des ayants "
                              "droit : lecture libre, autre usage selon les conditions de l'œuvre."
                              if protected else "Domaine public (Aozora Bunko). Liste des œuvres : CC BY."),
        "language": "ja",
    }
    raw = {k: v for k, v in row.items() if v and k in (
        "作品ID", "作品名", "副題", "原題", "初出", "分類番号", "文字遣い種別", "作品著作権フラグ", "公開日", "最終更新日",
        "図書カードURL", "テキストファイルURL", "テキストファイル最終更新日", "テキストファイル符号化方式",
        "テキストファイル文字集合", "XHTML/HTMLファイルURL", "XHTML/HTMLファイル符号化方式", "底本名1", "底本出版社名1",
        "底本初版発行年1", "入力者", "校正者")}
    raw["personnes"] = [{"nom": p[0], "lecture": p[1], "rôle": p[2]} for p in people]
    return ConnectorResult(source_id=work_id, data=data, raw=raw, raw_format="aozora-csv")


@register
class AozoraConnector(BaseConnector):
    key = "aozora"
    label = "Aozora Bunko (青空文庫)"
    description = ("Textes intégraux d'œuvres japonaises, surtout modernes (ère Meiji à Shōwa). Liste des œuvres "
                   "importée par « Synchroniser » ; texte d'une œuvre téléchargé à la demande depuis sa fiche.")
    supports_search = True
    supports_harvest = True
    unsupported_fields = ["translated_title", "composition_date_text", "shelfmark", "image_url"]
    config_help = {"list_url": "Adresse de la liste des œuvres (zip CSV UTF-8), par défaut celle d'Aozora Bunko."}

    def _list_url(self):
        return self.config.get("list_url") or LIST_URL

    def download_list(self):
        """Liste du jour, gardée en fichier : une reprise le même jour ne la télécharge pas de nouveau."""
        path = _cache_path(timezone.localdate())
        if path.exists() and path.stat().st_size:
            return path.read_bytes()
        response = ConnectorHTTP(self.catalogue).get_bytes(self._list_url(), max_bytes=80 * 1024 * 1024,
                                                           accept="application/zip")
        path.write_bytes(response["content"])
        return response["content"]

    def harvest(self, since=None, cursor=None):
        works = group_works(read_list(self.download_list()))
        start = int(cursor) if (cursor or "").isdigit() else 0
        if start >= len(works):
            yield HarvestBatch(results=[], cursor=str(len(works)), done=True)
            return
        for index in range(start, len(works), BATCH):
            end = min(index + BATCH, len(works))
            yield HarvestBatch(results=works[index:end], cursor=str(end), done=end >= len(works))

    def search(self, query):
        """Recherche dans les notices Aozora déjà importées (aucun appel au site)."""
        from apps.catalog.models import Record
        from apps.catalog.search import local_search

        started = time.monotonic()
        base = Record.objects.filter(catalogue=self.catalogue)
        if not base.exists():
            raise ConnectorError("La liste des œuvres d'Aozora Bunko n'est pas encore importée : Mises à jour → "
                                 "Aozora Bunko → « Synchroniser » (environ 17 000 œuvres, une fois).",
                                 kind="config", code="not_imported")
        qs = local_search(query, base_qs=base)
        total = qs.count()
        page = list(qs[(query.page - 1) * query.page_size: query.page * query.page_size])
        results = [ConnectorResult(source_id=r.source_id, data={f: getattr(r, f) for f in (
            "source_url", "digital_access_url", "original_title", "reading", "creator_original", "creator_reading",
            "description_original", "copy_date_text", "subjects_original", "material_type_original",
            "holding_institution_text", "rights_and_access", "language")} | {"source_id": r.source_id},
            raw=r.raw_data or {}, raw_format="aozora-csv") for r in page]
        return SearchResponse(results=results, total=total, page=query.page,
                              has_more=query.page * query.page_size < total,
                              elapsed_ms=int((time.monotonic() - started) * 1000))

    def test(self):
        try:
            probe = ConnectorHTTP(self.catalogue).probe(self._list_url(), max_bytes=4096)
        except ConnectorError as exc:
            return False, f"Liste des œuvres injoignable : {exc}", {"error_kind": exc.kind, "error_code": exc.code}
        if probe["status"] != 200:
            return False, f"Liste des œuvres : HTTP {probe['status']}.", {"error_code": f"http_{probe['status']}"}
        return True, "Liste des œuvres d'Aozora Bunko accessible.", {}
