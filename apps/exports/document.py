"""
Modèle documentaire commun des exports (§4.3) : tous les générateurs consomment
cette structure, calculée à partir du périmètre choisi.
"""
import hashlib
import json
from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import Max, Min
from django.utils import timezone

from apps.catalog.models import (DIGITAL_ACCESS, DOCUMENT_TYPES, GENERATED_ORIGINS, MATERIAL_TYPES, PERIODS,
                                 RECORD_SOURCE_FIELDS, Record)

PERIOD_LABELS = dict(PERIODS)
DOC_LABELS = dict(DOCUMENT_TYPES)
MATERIAL_LABELS = dict(MATERIAL_TYPES)
ACCESS_LABELS = dict(DIGITAL_ACCESS)

COLUMN_PROFILES = {
    "bibliography": ["record_id", "catalogue_code", "source_id", "original_title", "reading", "translated_title",
                     "creator_original", "composition_date_text", "copy_date_text", "holding_institution_text",
                     "shelfmark", "source_url", "collected_at"],
    "historical": ["record_id", "original_title", "reading", "translated_title", "creator_original", "period",
                   "composition_date_text", "composition_year_start", "composition_year_end",
                   "composition_date_precision", "copy_date_text", "copy_year_start", "copy_year_end",
                   "copy_date_precision", "document_type", "material_type", "place_original",
                   "holding_institution_text", "source_url"],
    "generic": ["record_id", "catalogue_code", "record_version"] + RECORD_SOURCE_FIELDS + ["collected_at"],
    "inventory": ["record_id", "catalogue_code", "catalogue_name", "record_version", "record_status"]
                 + RECORD_SOURCE_FIELDS + ["period", "document_type", "material_type", "title_romaji",
                                           "translated_title_origin", "collected_at", "dataset_label"],
}

COLUMN_DOC = {
    "record_id": ("texte", "Identifiant interne stable de la notice (REC-…)."),
    "catalogue_code": ("texte", "Code technique du catalogue source."),
    "catalogue_name": ("texte", "Nom du catalogue source."),
    "record_version": ("entier", "Version de la notice exportée."),
    "record_status": ("valeur contrôlée", "active, unavailable, withdrawn, to_check."),
    "source_id": ("texte", "Identifiant attribué par le catalogue source."),
    "source_url": ("URL", "URL officielle de la notice, telle que fournie ou vérifiée."),
    "original_title": ("texte", "Titre tel qu'affiché par la source (graphie conservée)."),
    "reading": ("texte", "Lecture ou transcription fournie par la source."),
    "translated_title": ("texte", "Titre traduit ; origine indiquée dans translated_title_origin."),
    "translated_title_origin": ("valeur contrôlée", "source, rule, user, ai."),
    "creator_original": ("texte", "Auteur, compilateur ou éditeur (forme originale)."),
    "creator_reading": ("texte", "Lecture du nom de l'auteur."),
    "description_original": ("texte", "Description ou 解題 originale."),
    "description_translation": ("texte", "Traduction de la description."),
    "composition_date_text": ("texte", "Date de composition de l'œuvre telle que fournie."),
    "composition_year_start": ("entier", "Année de début (normalisée)."),
    "composition_year_end": ("entier", "Année de fin (normalisée)."),
    "composition_date_precision": ("valeur contrôlée", "exact, year, interval, century, period, estimated, unknown."),
    "copy_date_text": ("texte", "Date de copie, d'impression ou d'édition de l'exemplaire décrit."),
    "copy_year_start": ("entier", "Année de début (normalisée)."),
    "copy_year_end": ("entier", "Année de fin (normalisée)."),
    "copy_date_precision": ("valeur contrôlée", "Voir composition_date_precision."),
    "document_type_original": ("texte", "Type documentaire fourni par la source."),
    "material_type_original": ("texte", "Support fourni par la source."),
    "document_type": ("valeur contrôlée", "Type normalisé : " + ", ".join(k for k, _ in DOCUMENT_TYPES if k)),
    "material_type": ("valeur contrôlée", "Support normalisé : " + ", ".join(k for k, _ in MATERIAL_TYPES if k)),
    "period": ("valeur contrôlée", "Période : " + ", ".join(k for k, _ in PERIODS if k)),
    "holding_institution_text": ("texte", "Institution détentrice."),
    "shelfmark": ("texte", "Cote."),
    "digital_access_url": ("URL", "Lien vers la numérisation."),
    "image_url": ("URL", "Manifeste IIIF ou image."),
    "digital_access": ("valeur contrôlée", "fulltext, image, record_only, restricted."),
    "rights_and_access": ("texte", "Conditions de consultation et de réutilisation connues."),
    "language": ("valeur contrôlée", "ja, lzh, fr, en, other."),
    "subjects_original": ("texte", "Sujets fournis par la source (séparateur « ; »)."),
    "place_original": ("texte", "Lieu fourni par la source."),
    "source_updated_at": ("texte", "Date de mise à jour indiquée par la source."),
    "title_romaji": ("texte", "Rōmaji automatique (lecture non vérifiée)."),
    "collected_at": ("date ISO 8601", "Date et heure de collecte."),
    "dataset_label": ("texte", "Jeu de données d'origine (import)."),
}


@dataclass
class ExportDocument:
    metadata: dict
    sections: list = field(default_factory=list)
    records: list = field(default_factory=list)
    introduction: str = ""
    methodology: str = ""
    creators: list = field(default_factory=list)
    places: list = field(default_factory=list)
    options: dict = field(default_factory=dict)


def _record_dict(record, *, include_ai, include_notes, user, collection_item=None):
    d = {f: getattr(record, f) for f in RECORD_SOURCE_FIELDS}
    d.update({
        "record_id": record.record_id,
        "record_version": record.version,
        "record_status": record.record_status,
        "catalogue_code": record.catalogue.code,
        "catalogue_name": record.catalogue.name,
        "period": record.period,
        "period_label": PERIOD_LABELS.get(record.period, "") if record.period else "",
        "document_type": record.document_type,
        "document_type_label": DOC_LABELS.get(record.document_type, "") if record.document_type else "",
        "material_type": record.material_type,
        "material_type_label": MATERIAL_LABELS.get(record.material_type, "") if record.material_type else "",
        "digital_access_label": ACCESS_LABELS.get(record.digital_access, "") if record.digital_access else "",
        "title_romaji": record.title_romaji,
        "translated_title_origin": record.translated_title_origin,
        "description_translation_origin": record.description_translation_origin,
        "composition_display": record.composition_display,
        "copy_display": record.copy_display,
        "collected_at": record.collected_at.isoformat() if record.collected_at else "",
        "dataset_label": record.dataset_label,
        "editorial": [],
        "notes": [],
        "collection_note": collection_item.note if collection_item else "",
    })
    if not include_ai:
        if record.translated_title_origin in GENERATED_ORIGINS:
            d["translated_title"] = ""
        if record.description_translation_origin in GENERATED_ORIGINS:
            d["description_translation"] = ""
    for ed in record.editorial.exclude(status="rejected"):
        if ed.origin in GENERATED_ORIGINS and not include_ai:
            continue
        d["editorial"].append({"kind": ed.get_kind_display(), "kind_code": ed.kind, "content": ed.content,
                               "origin": ed.get_origin_display(), "origin_code": ed.origin,
                               "status": ed.get_status_display(), "target_field": ed.target_field,
                               "ai_model": f"{ed.ai_task.provider}/{ed.ai_task.model}" if ed.ai_task_id else "",
                               "created_at": ed.created_at.isoformat()})
    if include_notes:
        from apps.library.models import Annotation

        for note in Annotation.visible_to(user).filter(record=record):
            d["notes"].append({"body": note.body, "visibility": note.get_visibility_display(),
                               "locator": f"{note.get_locator_type_display()} {note.locator}".strip(" —"),
                               "author": str(note.author), "updated_at": note.updated_at.isoformat()})
    return d


def resolve_records(job):
    """Retourne (sections [(titre, description, [(record, collection_item)])], counts)."""
    from apps.library.models import Collection, LibraryEntry
    from apps.searching.models import SearchSession

    p = job.scope_params or {}
    counts = {}
    if job.scope == "collection":
        collection = Collection.objects.get(pk=p["collection_id"])
        sections = []
        items = collection.items.select_related("record__catalogue", "section")
        by_section = {}
        for item in items:
            by_section.setdefault(item.section_id, []).append((item.record, item))
        for section in collection.sections.all():
            sections.append((section.title, section.description, by_section.pop(section.pk, [])))
        if by_section.get(None):
            sections.insert(0, ("Références" if sections else "Références du dossier", "", by_section.pop(None)))
        counts["exported"] = sum(len(s[2]) for s in sections)
        return sections, counts, collection
    if job.scope == "session":
        session = SearchSession.objects.get(uid=p["session_uid"])
        qs = session.results.exclude(comparison="unavailable")
        counts.update({"found": qs.count(), "retained": qs.filter(decision="selected").count(),
                       "excluded": qs.filter(decision="excluded").count()})
        which = qs.filter(decision="selected") if p.get("only_selected", True) else qs.exclude(decision="excluded")
        records = [r.integrated_record or r.local_record for r in which if (r.integrated_record or r.local_record)]
        counts["not_integrated"] = which.count() - len(records)
    elif job.scope == "library":
        qs = LibraryEntry.objects.filter(user=job.owner).select_related("record__catalogue")
        if p.get("tag"):
            qs = qs.filter(tags__name=p["tag"])
        if p.get("favorites"):
            qs = qs.filter(favorite=True)
        records = [e.record for e in qs]
    else:
        ids = p.get("record_ids") or []
        order = {rid: i for i, rid in enumerate(ids)}
        records = sorted(Record.objects.filter(record_id__in=ids).select_related("catalogue"),
                         key=lambda r: order.get(r.record_id, 0))
    counts["exported"] = len(records)
    return [("Références", "", [(r, None) for r in records])], counts, None


def build_document(job):
    opts = job.options or {}
    include_ai = bool(opts.get("include_ai", True))
    include_notes = bool(opts.get("include_notes", True))
    sections_raw, counts, collection = resolve_records(job)
    sections, flat = [], []
    for title, description, items in sections_raw:
        recs = [_record_dict(r, include_ai=include_ai, include_notes=include_notes, user=job.owner, collection_item=i)
                for r, i in items]
        sections.append({"title": title, "description": description, "records": recs})
        flat.extend(recs)

    record_objs = Record.objects.filter(record_id__in=[r["record_id"] for r in flat])
    sources = []
    for row in (record_objs.values("catalogue__code", "catalogue__name", "catalogue__last_success_at",
                                   "catalogue__is_snapshot", "catalogue__snapshot_date")
                .annotate(first=Min("collected_at"), last=Max("collected_at")).order_by("catalogue__name")):
        count = sum(1 for r in flat if r["catalogue_code"] == row["catalogue__code"])
        sources.append({
            "code": row["catalogue__code"], "name": row["catalogue__name"], "records": count,
            "last_verified": row["catalogue__last_success_at"].isoformat() if row["catalogue__last_success_at"] else None,
            "collected_from": row["first"].isoformat() if row["first"] else None,
            "collected_to": row["last"].isoformat() if row["last"] else None,
            "snapshot_date": row["catalogue__snapshot_date"].isoformat() if row["catalogue__snapshot_date"] else None,
            "is_snapshot": row["catalogue__is_snapshot"],
        })
    # « contains_ai_content » : nom de clé inchangé (compatibilité) ; couvre aussi la traduction automatique (1.3.0).
    has_ai = any(r["translated_title_origin"] in GENERATED_ORIGINS or r["description_translation_origin"] in GENERATED_ORIGINS
                 or any(e["origin_code"] in GENERATED_ORIGINS for e in r["editorial"]) for r in flat)
    restrictions = sorted({r["rights_and_access"] for r in flat if r["rights_and_access"]})
    now = job.generated_at or timezone.now()
    metadata = {
        "export_id": job.export_uid,
        "title": job.title,
        "subtitle": job.subtitle,
        "subject": job.subject,
        "author": job.author,
        "generated_at": now.isoformat(),
        "generated_at_display": timezone.localtime(now).strftime("%d/%m/%Y %H:%M"),
        "application": "Japon — Explorateur documentaire",
        "application_version": settings.APP_VERSION,
        "schema_version": settings.DATA_SCHEMA_VERSION,
        "format": job.format,
        "preset": job.preset,
        "scope": job.scope,
        "scope_label": job.get_scope_display(),
        "counts": counts,
        "sources": sources,
        "records": [{"record_id": r["record_id"], "version": r["record_version"]} for r in flat],
        "contains_ai_content": has_ai,
        "ai_content_included": include_ai,
        "restrictions": restrictions,
        "header": job.header_text,
        "footer": job.footer_text,
    }
    creators = sorted({r["creator_original"] for r in flat if r["creator_original"]})
    places = sorted({p for r in flat for p in (r["place_original"], r["holding_institution_text"]) if p})
    return ExportDocument(
        metadata=metadata, sections=sections, records=flat,
        introduction=(collection.description if collection else job.subject),
        methodology=(collection.methodology if collection and collection.methodology else ""),
        creators=creators, places=places, options=opts,
    )


def fingerprint(job):
    """Empreinte des données exportées : sert à signaler un changement avant régénération."""
    sections, _, collection = resolve_records(job)
    parts = []
    for title, _, items in sections:
        parts.append(title)
        for record, item in items:
            parts.append(f"{record.record_id}:{record.version}:{record.updated_at.isoformat()}:{item.note if item else ''}")
    if collection:
        parts.append(f"{collection.title}|{collection.description}|{collection.updated_at.isoformat()}")
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()
