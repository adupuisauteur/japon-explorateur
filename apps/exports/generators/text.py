"""Exports TXT, JSON et CSV."""
import csv
import json
from pathlib import Path

from ..document import COLUMN_DOC, COLUMN_PROFILES
from .common import citation, fiche_rows, metadata_lines, write_manifest

SEP = "=" * 78
SUB = "-" * 78


def generate_txt(doc, out_dir, basename):
    path = Path(out_dir) / f"{basename}.txt"
    lines = [SEP, "MÉTADONNÉES DE L'EXPORT", SEP]
    lines += [f"{k} : {v}" for k, v in metadata_lines(doc)]
    if doc.metadata.get("header"):
        lines.append(f"En-tête : {doc.metadata['header']}")
    lines += [SEP, ""]
    if doc.introduction:
        lines += ["INTRODUCTION", SUB, doc.introduction, ""]
    for section in doc.sections:
        lines += [SEP, section["title"].upper(), SEP]
        if section["description"]:
            lines += [section["description"], ""]
        for i, rec in enumerate(section["records"], 1):
            lines += [SUB, f"[{i}] {rec['original_title']}", SUB]
            lines += [f"{label} : {value}" for label, value in fiche_rows(rec)]
            for ed in rec["editorial"]:
                lines.append(f"{ed['kind']} ({ed['origin']}, {ed['status']}) : {ed['content']}")
            if rec["collection_note"]:
                lines.append(f"Note de dossier : {rec['collection_note']}")
            for note in rec["notes"]:
                lines.append(f"Note ({note['visibility']}{', ' + note['locator'] if note['locator'] else ''}) : {note['body']}")
            lines.append("")
    lines += [SEP, "BIBLIOGRAPHIE", SEP]
    lines += [f"- {citation(r)}" for r in doc.records]
    if doc.methodology:
        lines += ["", SEP, "MÉTHODOLOGIE", SEP, doc.methodology]
    lines += ["", SEP, f"Fin de l'export {doc.metadata['export_id']} — {doc.metadata.get('production_line') or doc.metadata['generated_at_display']}"]
    if doc.metadata.get("footer"):
        lines.append(doc.metadata["footer"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [("main", path)]


def json_payload(doc):
    records = []
    for rec in doc.records:
        item = {k: v for k, v in rec.items() if k not in ("catalogue_code", "catalogue_name", "source_id", "source_url",
                                                          "status_notice", "status_document", "status_iiif",
                                                          "availability_label")}
        item["catalogue"] = {"code": rec["catalogue_code"], "name": rec["catalogue_name"]}
        item["source"] = {"name": rec["catalogue_name"], "source_id": rec["source_id"], "url": rec["source_url"]}
        records.append(item)
    return {
        "schema_version": doc.metadata["schema_version"],
        "export_metadata": doc.metadata,
        "introduction": doc.introduction,
        "methodology": doc.methodology,
        "sections": [{"title": s["title"], "description": s["description"],
                      "record_ids": [r["record_id"] for r in s["records"]]} for s in doc.sections],
        "records": records,
    }


JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "japon-explorateur/export/1.0",
    "title": "Export J-ed (anciennement Japon — Explorateur documentaire)",
    "type": "object",
    "required": ["schema_version", "export_metadata", "records"],
    "properties": {
        "schema_version": {"type": "string"},
        "export_metadata": {"type": "object", "required": ["export_id", "generated_at", "sources"]},
        "sections": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "record_ids": {"type": "array", "items": {"type": "string"}}}}},
        "records": {"type": "array", "items": {"type": "object", "required": ["record_id", "source", "original_title"],
                                               "properties": {
                                                   "record_id": {"type": "string"},
                                                   "record_version": {"type": "integer"},
                                                   "catalogue": {"type": "object"},
                                                   "source": {"type": "object", "required": ["name", "source_id"]},
                                                   "original_title": {"type": "string"},
                                                   "composition_year_start": {"type": ["integer", "null"]},
                                                   "copy_year_start": {"type": ["integer", "null"]},
                                                   "editorial": {"type": "array"},
                                                   "notes": {"type": "array"},
                                                   "statuses": {"type": "object", "description": (
                                                       "2.0.0 : notice, document, iiif — value, label, origin, "
                                                       "origin_label, checked_at, url, detail")},
                                                   "collected_at": {"type": "string"}}}},
    },
}


def generate_json(doc, out_dir, basename):
    path = Path(out_dir) / f"{basename}.json"
    path.write_text(json.dumps(json_payload(doc), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    schema = Path(out_dir) / f"{basename}.schema.json"
    schema.write_text(json.dumps(JSON_SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")
    return [("main", path), ("schema", schema)]


FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def neutralize_cell(value):
    """Empêche un tableur d'interpréter une cellule comme formule (injection CSV / DDE)."""
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGERS):
        return "'" + value
    return value


def generate_csv(doc, out_dir, basename):
    opts = doc.options
    profile = opts.get("column_profile") or "bibliography"
    columns = COLUMN_PROFILES.get(profile, COLUMN_PROFILES["bibliography"])
    delimiter = {"semicolon": ";", "comma": ",", "tab": "\t"}.get(opts.get("csv_separator", "semicolon"), ";")
    encoding = "utf-8-sig" if opts.get("csv_bom") else "utf-8"
    neutralize = opts.get("csv_neutralize", True) is not False
    path = Path(out_dir) / f"{basename}.csv"
    with open(path, "w", encoding=encoding, newline="") as fh:
        writer = csv.writer(fh, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow(columns)  # aucune ligne de titre avant l'en-tête (§12.4)
        for rec in doc.records:
            row = ["" if rec.get(c) is None else rec.get(c) for c in columns]
            writer.writerow([neutralize_cell(v) for v in row] if neutralize else row)
    columns_doc = Path(out_dir) / f"{basename}.colonnes.csv"
    with open(columns_doc, "w", encoding=encoding, newline="") as fh:
        writer = csv.writer(fh, delimiter=delimiter, lineterminator="\r\n")
        writer.writerow(["colonne", "type", "definition"])
        for c in columns:
            t, d = COLUMN_DOC.get(c, ("texte", ""))
            writer.writerow([c, t, d])
    manifest = Path(out_dir) / f"{basename}.manifest.json"
    write_manifest(manifest, doc, [("main", path), ("schema", columns_doc)], extra={
        "csv": {"encoding": encoding, "delimiter": delimiter, "column_profile": profile,
                "multi_value_separator": " ; ", "dates": "ISO 8601 pour collected_at ; années en entiers",
                "formulas_neutralized": neutralize,
                "formulas_note": ("Les cellules commençant par = + - @ tabulation ou retour chariot sont préfixées "
                                  "d'une apostrophe ; la retirer avant réimportation si nécessaire.") if neutralize
                else "Aucune neutralisation : ne pas ouvrir ce fichier dans un tableur sans précaution."}})
    return [("main", path), ("manifest", manifest), ("schema", columns_doc)]
