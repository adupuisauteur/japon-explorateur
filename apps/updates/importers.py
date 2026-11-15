"""
Lecture des fichiers d'import (CSV, TSV, XLSX, JSON, XML, MARCXML, Dublin Core)
et correspondance automatique des colonnes vers les champs de notice (§9.4, §9.6).
"""
import csv
import hashlib
import io
import json
import logging
import re
from collections import Counter

from lxml import etree

from apps.core import japanese as jp
from apps.core.encoding import decode_text  # noqa: F401  (déplacée en 1.3.0 ; nom conservé ici)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- synonymes de colonnes

FIELD_LABELS = {
    "source_id": "Identifiant source",
    "source_url": "URL officielle de la notice",
    "original_title": "Titre original",
    "reading": "Lecture du titre",
    "translated_title": "Titre traduit",
    "creator_original": "Auteur (forme originale)",
    "creator_reading": "Auteur (lecture)",
    "description_original": "Description originale",
    "description_translation": "Traduction de la description",
    "composition_date_text": "Date de composition",
    "copy_date_text": "Date de copie / impression / édition",
    "document_type_original": "Type documentaire",
    "material_type_original": "Support (manuscrit, imprimé…)",
    "holding_institution_text": "Institution détentrice",
    "shelfmark": "Cote",
    "digital_access_url": "Lien vers la numérisation",
    "image_url": "Manifeste IIIF / image",
    "rights_and_access": "Droits et conditions",
    "language": "Langue",
    "subjects_original": "Sujets",
    "place_original": "Lieu",
    "source_updated_at": "Mise à jour à la source",
}

SYNONYMS = {
    "source_id": ["source_id", "国文研書誌id", "書誌id", "国書id", "識別子", "identifiant", "identifier", "id", "bibid",
                  "record id", "レコードid", "資料id", "登録番号", "dc:identifier", "001", "doi", "source.source_id"],
    "source_url": ["source_url", "url", "uri", "link", "リンク", "書誌url", "詳細url", "856u", "source.url"],
    "original_title": ["original_title", "書名（統一書名）", "書名", "統一書名", "タイトル", "題名", "資料名", "作品名", "title",
                       "titre", "dc:title", "245a"],
    "reading": ["reading", "書名よみ", "書名ヨミ", "よみ", "読み", "タイトルよみ", "yomi", "title_reading",
                "dcndl:titletranscription"],
    "translated_title": ["translated_title", "titre traduit", "titre français", "titre_fr", "english title", "英文タイトル"],
    "creator_original": ["creator_original", "著者", "作者", "編者", "著者名", "編著者", "著編者", "author", "auteur", "creator",
                         "dc:creator", "100a", "110a"],
    "creator_reading": ["creator_reading", "著者よみ", "著者ヨミ", "author reading", "auteur_lecture"],
    "description_original": ["description_original", "解題", "注記", "備考", "内容", "description", "note", "notes",
                             "dc:description", "520a"],
    "description_translation": ["description_translation", "description traduite"],
    "composition_date_text": ["composition_date_text", "composition_date", "成立年", "成立", "date de composition",
                              "date_composition"],
    "copy_date_text": ["copy_date_text", "copy_or_publication_date", "刊写年", "書写年", "刊年", "出版年", "年代", "date",
                       "dc:date", "issued", "260c", "264c", "date de copie"],
    "document_type_original": ["document_type_original", "document_type", "種別", "ジャンル", "分類", "genre", "type",
                               "dc:type", "type documentaire"],
    "material_type_original": ["material_type_original", "material_type", "刊写の別", "刊写", "写刊", "形態", "support",
                               "material", "dcndl:materialtype"],
    "holding_institution_text": ["holding_institution_text", "holding_institution", "所蔵機関", "所蔵者", "所蔵館", "所蔵",
                                 "institution", "holder", "library", "provider", "852a"],
    "shelfmark": ["shelfmark", "請求記号", "函架番号", "cote", "call number", "callnumber", "852h"],
    "digital_access_url": ["digital_access_url", "画像url", "画像", "viewer", "numérisation", "digital url"],
    "image_url": ["image_url", "iiif", "manifest", "manifest_url", "iiif_manifest"],
    "rights_and_access": ["rights_and_access", "rights", "license", "licence", "ライセンス", "利用条件", "droits", "dc:rights"],
    "language": ["language", "langue", "言語", "dc:language"],
    "subjects_original": ["subjects_original", "subjects", "subject", "sujets", "主題", "件名", "キーワード", "keywords",
                          "dc:subject", "650a"],
    "place_original": ["place_original", "place", "lieu", "出版地", "書写地", "spatial", "dc:coverage", "260a", "264a"],
    "source_updated_at": ["source_updated_at", "updated", "modified", "last_modified", "更新日"],
}

PRESETS = {
    "auto": "Détection automatique",
    "codh": "CODH — inventaire PMJT (instantané 2019)",
    "classeur": "Classeur documentaire central",
    "json_export": "JSON exporté par l'application",
    "marcxml": "MARCXML",
    "dc": "Dublin Core",
}

LANGUAGE_MAP = {"jpn": "ja", "ja": "ja", "japanese": "ja", "japonais": "ja", "日本語": "ja", "lzh": "lzh", "chi": "lzh",
                "zho": "lzh", "漢文": "lzh", "chinois classique": "lzh", "fre": "fr", "fra": "fr", "fr": "fr",
                "french": "fr", "français": "fr", "eng": "en", "en": "en", "english": "en", "anglais": "en"}


def _key(name):
    return jp.nfkc(str(name)).strip().lower()


def auto_mapping(columns):
    """Propose une correspondance champ → colonne (à vérifier par l'utilisateur)."""
    by_key = {_key(c): c for c in columns}
    mapping, used = {}, set()
    for field, names in SYNONYMS.items():
        for name in names:
            col = by_key.get(_key(name))
            if col and col not in used:
                mapping[field] = col
                used.add(col)
                break
    return mapping


def unknown_columns(columns, mapping):
    used = set()
    for v in mapping.values():
        used.update(v if isinstance(v, list) else [v])
    # 2.0.0 (lot 2) : les statuts d'un export J-ed sont recalculés à l'import, ce ne sont pas des colonnes perdues.
    return [c for c in columns if c not in used and not c.startswith("statuses.")]


# --------------------------------------------------------------------------- détection et lecture


def detect_format(filename, head):
    name = filename.lower()
    if name.endswith(".xlsx"):
        return "xlsx"
    if name.endswith(".tsv"):
        return "tsv"
    if name.endswith(".json"):
        try:
            text = head.decode("utf-8-sig", errors="ignore")
            if '"schema_version"' in text and '"export_metadata"' in text:
                return "json_export"
        except Exception as exc:  # 2.0.0 : journalisé ; le fichier est alors traité comme du JSON ordinaire
            logger.warning("Détection d'un export J-ed impossible (%s : %s) : lecture comme JSON ordinaire.",
                           exc.__class__.__name__, exc)
        return "json"
    if name.endswith((".xml", ".marcxml")):
        text = head.decode("utf-8", errors="ignore")
        if "marc" in text.lower() and ("<record" in text or ":record" in text):
            return "marcxml"
        if "purl.org/dc/elements" in text:
            return "dc"
        return "xml"
    return "csv"


# decode_text : déplacée dans apps/core/encoding.py (1.3.0), importée ci-dessus sous le même nom.


def read_rows(path, fmt, *, delimiter="", sheet_name=""):
    """Retourne (colonnes, itérateur de lignes dict, infos)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    info = {}
    if fmt in ("csv", "tsv"):
        text, enc = decode_text(raw)
        info["encoding"] = enc
        if fmt == "tsv":
            delimiter = "\t"
        if not delimiter:
            try:
                delimiter = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ","
        info["delimiter"] = delimiter
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        columns = [c for c in (reader.fieldnames or []) if c is not None]
        rows = ({k: (v or "") for k, v in row.items() if k is not None} for row in reader)
        return columns, rows, info
    if fmt == "xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.worksheets[0]
        info["sheet_name"] = ws.title
        info["sheets"] = wb.sheetnames
        it = ws.iter_rows(values_only=True)
        header = None
        for row in it:
            if row and any(c not in (None, "") for c in row):
                header = [str(c).strip() if c is not None else f"colonne_{i + 1}" for i, c in enumerate(row)]
                break
        header = header or []

        def gen():
            for row in it:
                if not row or all(c in (None, "") for c in row):
                    continue
                yield {header[i]: ("" if v is None else str(v)) for i, v in enumerate(row) if i < len(header)}

        return header, gen(), info
    if fmt in ("json", "json_export"):
        text, enc = decode_text(raw)
        data = json.loads(text)
        items = data.get("records") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise ValueError("JSON : liste de notices introuvable (tableau ou clé « records » attendus).")
        if isinstance(data, dict) and data.get("schema_version"):
            info["schema_version"] = data.get("schema_version")
        flat = [_flatten(i) for i in items if isinstance(i, dict)]
        columns = list(dict.fromkeys(k for row in flat for k in row))
        return columns, iter(flat), info
    if fmt == "marcxml":
        rows = list(_marc_rows(raw))
        columns = list(dict.fromkeys(k for row in rows for k in row))
        return columns, iter(rows), info
    if fmt == "dc":
        rows = list(_dc_rows(raw))
        columns = list(dict.fromkeys(k for row in rows for k in row))
        return columns, iter(rows), info
    if fmt == "xml":
        rows = list(_generic_xml_rows(raw))
        columns = list(dict.fromkeys(k for row in rows for k in row))
        return columns, iter(rows), info
    raise ValueError(f"Format non pris en charge : {fmt}")


def _flatten(obj, prefix=""):
    out = {}
    for k, v in obj.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        elif isinstance(v, list):
            out[key] = " ; ".join(json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x)
                                  for x in v)
        elif v is not None:
            out[key] = str(v)
    return out


def _parse_xml(raw):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    return etree.fromstring(raw, parser)


def _local(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def _marc_rows(raw):
    root = _parse_xml(raw)
    for rec in root.iter():
        if _local(rec.tag) != "record":
            continue
        row = {}
        for el in rec:
            name = _local(el.tag)
            if name == "controlfield":
                row[el.get("tag", "")] = (el.text or "").strip()
            elif name == "datafield":
                tag = el.get("tag", "")
                for sub in el:
                    if _local(sub.tag) != "subfield":
                        continue
                    key = f"{tag}{sub.get('code', '')}"
                    val = (sub.text or "").strip()
                    if tag == "880":  # graphie originale liée (vernaculaire)
                        link = next((s.text for s in el if s.get("code") == "6"), "") or ""
                        key = f"{link[:3]}{sub.get('code', '')}" if link else key
                        key = f"{key}_original"
                    if val:
                        row[key] = f"{row[key]} ; {val}" if key in row else val
        for base in ("245a", "100a", "260c", "264c"):
            if f"{base}_original" in row:
                row[f"{base}_romanized"] = row.get(base, "")
                row[base] = row[f"{base}_original"]
        yield row


def _dc_rows(raw):
    root = _parse_xml(raw)
    for el in root.iter():
        if _local(el.tag) != "dc":
            continue
        row = {}
        for child in el:
            key = f"dc:{_local(child.tag)}"
            val = (child.text or "").strip()
            if val:
                row[key] = f"{row[key]} ; {val}" if key in row else val
        yield row


def _is_record(element):
    """Une notice = un élément dont les enfants sont des feuilles (champs simples)."""
    children = [c for c in element if isinstance(c.tag, str)]
    return bool(children) and all(len([g for g in c if isinstance(g.tag, str)]) == 0 for c in children)


def _generic_xml_rows(raw):
    """XML générique : repère le conteneur des notices par la structure, pas par le nombre d'enfants
    (un fichier ne contenant qu'une seule notice est donc lu correctement — audit, correction 10)."""
    root = _parse_xml(raw)
    container = root
    while True:
        children = [c for c in container if isinstance(c.tag, str)]
        if len(children) == 1 and not _is_record(children[0]):
            container = children[0]
            continue
        break
    children = [c for c in container if isinstance(c.tag, str)]
    if not children:
        return
    if _is_record(container) and not any(_is_record(c) for c in children):
        children = [container]  # la racine est elle-même l'unique notice
    tag = Counter(_local(c.tag) for c in children).most_common(1)[0][0]
    for item in children:
        if _local(item.tag) != tag:
            continue
        row = dict(item.attrib)
        for child in item.iter():
            if child is item or len(child) or not isinstance(child.tag, str):
                continue  # entités et commentaires ignorés (jamais résolus)
            key = _local(child.tag)
            val = (child.text or "").strip()
            if val:
                row[key] = f"{row[key]} ; {val}" if key in row else val
        yield row


# --------------------------------------------------------------------------- construction des notices


def build_data(row, mapping, *, generate_ids=False):
    data = {}
    for field, cols in mapping.items():
        if not cols or field not in FIELD_LABELS:
            continue
        cols = cols if isinstance(cols, list) else [cols]
        values = [str(row.get(c, "")).strip() for c in cols if str(row.get(c, "")).strip()]
        if values:
            data[field] = " ; ".join(values)
    if "language" in data:
        data["language"] = LANGUAGE_MAP.get(data["language"].strip().lower(), "other")
    if data.get("source_url") and not data["source_url"].startswith(("http://", "https://")):
        if data["source_url"].startswith("10."):
            data["source_url"] = f"https://doi.org/{data['source_url']}"
        else:
            data.pop("source_url")
    if not data.get("source_id") and generate_ids:
        basis = "|".join(data.get(k, "") for k in ("original_title", "creator_original", "copy_date_text",
                                                    "holding_institution_text", "shelfmark"))
        data["source_id"] = "CONTENU-" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16].upper()
    return data


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_filename(name):
    return re.sub(r"[^\w.\-]+", "_", name)[:150] or "fichier"
