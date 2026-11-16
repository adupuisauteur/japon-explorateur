"""Éléments partagés par les générateurs d'export."""
import hashlib
import json
from pathlib import Path

FICHE_FIELDS = [
    ("Titre original", "original_title"),
    ("Lecture", "reading"),
    ("Rōmaji (automatique, non vérifié)", "title_romaji"),
    ("Titre traduit", "translated_title"),
    ("Auteur (forme originale)", "creator_original"),
    ("Lecture du nom", "creator_reading"),
    ("Date de composition de l'œuvre", "composition_display"),
    ("Date de copie / impression de l'exemplaire", "copy_display"),
    ("Période", "period_label"),
    ("Type documentaire", "document_type_display"),
    ("Support", "material_type_display"),
    ("Institution détentrice", "holding_institution_text"),
    ("Cote", "shelfmark"),
    ("Disponibilité", "availability_label"),  # 2.0.0 (lot 2) : trois statuts, à la place de « Accès numérique »
    ("Droits et conditions", "rights_and_access"),
    ("Sujets", "subjects_original"),
    ("Lieu", "place_original"),
    ("Description originale", "description_original"),
    ("Traduction de la description", "description_translation"),
    ("Catalogue source", "catalogue_name"),
    ("Identifiant source", "source_id"),
    ("Notice officielle", "source_url"),
    ("Numérisation", "digital_access_url"),
    ("Date de collecte", "collected_at"),
    ("Identifiant interne (version)", "record_ref"),
]

ORIGIN_LABELS = {"ai": "traduction générée par IA", "user": "traduction de l'utilisateur", "rule": "règle automatique",
                 "source": "fournie par la source"}


#: 2.0.0 (lot 6) : logo de J-ed dans les en-têtes des exports (décision du 16 novembre 2026)
LOGO_RATIO = 507 / 611  # hauteur / largeur du logo


def logo_file():
    """Chemin du logo (PNG), ou None s'il manque : un export ne doit jamais échouer pour un logo."""
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "static" / "img" / "logo-j-ed-grand.png"
    return path if path.is_file() else None


def fiche_rows(rec):
    """Paires (libellé, valeur) non vides d'une fiche, avec signalement des contenus générés."""
    view = dict(rec)
    view["document_type_display"] = " / ".join(filter(None, [rec.get("document_type_original"),
                                                             rec.get("document_type_label")]))
    view["material_type_display"] = " / ".join(filter(None, [rec.get("material_type_original"),
                                                             rec.get("material_type_label")]))
    view["record_ref"] = f"{rec['record_id']} (v{rec['record_version']})"
    view["collected_at"] = (rec.get("collected_at") or "")[:19].replace("T", " ")
    rows = []
    for label, key in FICHE_FIELDS:
        value = view.get(key)
        if value in (None, ""):
            continue
        if key == "translated_title" and rec.get("translated_title_origin"):
            value = f"{value} [{ORIGIN_LABELS.get(rec['translated_title_origin'], rec['translated_title_origin'])}]"
        if key == "description_translation" and rec.get("description_translation_origin"):
            value = f"{value} [{ORIGIN_LABELS.get(rec['description_translation_origin'], '')}]"
        rows.append((label, str(value)))
    return rows


def citation(rec):
    """Référence bibliographique courte (une ligne)."""
    parts = [rec.get("creator_original"), rec.get("original_title")]
    if rec.get("reading"):
        parts[-1] = f"{rec['original_title']} ({rec['reading']})"
    if rec.get("translated_title"):
        parts.append(f"« {rec['translated_title']} »")
    for key in ("composition_display", "copy_display", "holding_institution_text", "shelfmark"):
        if rec.get(key):
            parts.append(rec[key])
    parts.append(f"{rec['catalogue_name']}, {rec['source_id']}")
    if rec.get("source_url"):
        parts.append(rec["source_url"])
    return ". ".join(p for p in parts if p) + "."


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(path, doc, files, extra=None):
    manifest = {
        "manifest_version": "1.0",
        "export_metadata": doc.metadata,
        "files": [{"path": str(Path(f).name) if not isinstance(f, tuple) else f[1], "role": role,
                   "sha256": sha256_file(f if not isinstance(f, tuple) else f[0]),
                   "size": Path(f if not isinstance(f, tuple) else f[0]).stat().st_size}
                  for role, f in files],
    }
    if extra:
        manifest.update(extra)
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def metadata_lines(doc):
    m = doc.metadata
    lines = [
        ("Titre", m["title"]), ("Sous-titre", m.get("subtitle")), ("Sujet", m.get("subject")),
        ("Préparateur", m.get("author")), ("Date d'export", m["generated_at_display"]),
        ("Exporté par", m.get("produced_by")),
        ("Identifiant de l'export", m["export_id"]), ("Périmètre", m["scope_label"]),
        ("Nombre de références exportées", str(m["counts"].get("exported", 0))),
    ]
    c = m["counts"]
    if "found" in c:
        lines.append(("Résultats trouvés / retenus / exclus", f"{c['found']} / {c['retained']} / {c['excluded']}"))
    for s in m["sources"]:
        when = (f"dernière vérification de la source le {s['last_verified'][:10]}" if s["last_verified"]
                else "source non vérifiée en ligne")
        collected = f", collecte du {s['collected_from'][:10]} au {s['collected_to'][:10]}" if s.get("collected_from") else ""
        snap = f" — jeu historique (instantané {s['snapshot_date'][:4]})" if s.get("is_snapshot") and s.get("snapshot_date") else ""
        lines.append((f"Source : {s['name']}", f"{s['records']} notice(s), {when}{collected}{snap}"))
    lines.append(("Contenus générés (IA, traduction automatique)", "inclus et signalés" if m["contains_ai_content"] and m["ai_content_included"]
                  else ("exclus" if not m["ai_content_included"] else "aucun")))
    if m.get("ai_summaries_included"):  # 2.0.0 (lot 4)
        lines.append(("Résumés IA", "inclus, marqués « généré par IA », non vérifiés"))
    lines.append(("Application", f"{m['application']} {m['application_version']} — schéma {m['schema_version']}"))
    return [(k, v) for k, v in lines if v]
