"""
Services du modèle documentaire : création / mise à jour versionnée des notices,
comparaison avec l'existant, détection prudente des doublons.
"""
import difflib

from django.db import transaction
from django.utils import timezone

from apps.core import japanese as jp

from .models import RECORD_SOURCE_FIELDS, TRACKED_FIELDS, Record, RecordLink, RecordVersion

INT_FIELDS = {"composition_year_start", "composition_year_end", "copy_year_start", "copy_year_end"}
CHOICE_FIELDS = {
    "composition_date_precision": {"exact", "year", "interval", "century", "period", "estimated", "unknown"},
    "copy_date_precision": {"exact", "year", "interval", "century", "period", "estimated", "unknown"},
    "digital_access": {"", "fulltext", "image", "record_only", "restricted"},
    "language": {"", "ja", "lzh", "fr", "en", "other"},
}
MAX_LENGTHS = {f.name: f.max_length for f in Record._meta.fields if getattr(f, "max_length", None)}


def clean_source_data(data, warnings=None):
    """Nettoie un dictionnaire de champs source sans réécrire le contenu.

    Aucune normalisation Unicode n'est appliquée : la graphie source (y compris les
    idéogrammes de compatibilité CJK) est conservée telle quelle (§6.5 ; audit, correction 7).
    Seuls les espaces en début et fin de valeur sont retirés. Toute valeur tronquée faute
    de place est signalée dans `warnings` (liste fournie par l'appelant) ; la valeur complète
    reste disponible dans les données brutes.
    """
    clean = {}
    for key, value in data.items():
        if key not in RECORD_SOURCE_FIELDS:
            continue
        if value is None:
            continue
        if key in INT_FIELDS:
            try:
                value = int(str(value).strip()) if str(value).strip() else None
            except ValueError:
                if warnings is not None:
                    warnings.append(f"{key} : valeur numérique invalide « {str(value)[:40]} » ignorée")
                value = None
            if value is None:
                continue
        else:
            value = str(value).strip()
            if key in CHOICE_FIELDS and value not in CHOICE_FIELDS[key]:
                continue
            limit = MAX_LENGTHS.get(key)
            if limit and len(value) > limit:
                if warnings is not None:
                    warnings.append(f"{key} : {len(value)} caractères tronqués à {limit} "
                                    "(valeur complète conservée dans les données brutes)")
                value = value[:limit]
            if key in ("source_url", "digital_access_url", "image_url") and value and not value.startswith(("http://", "https://")):
                if warnings is not None:
                    warnings.append(f"{key} : adresse non web ignorée")
                continue
        clean[key] = value
    return clean


def build_unsaved_record(catalogue, data, raw=None, raw_format=""):
    record = Record(catalogue=catalogue, raw_data=raw or {}, raw_format=raw_format)
    for key, value in clean_source_data(data).items():
        setattr(record, key, value)
    if not record.original_title:
        record.original_title = "(sans titre)"
    return record


def compare_with_existing(catalogue, data, raw=None, raw_format=""):
    """Compare des données entrantes avec la notice locale.

    Retourne (notice_existante | None, statut, champs_modifiés) où statut ∈
    {'new', 'unchanged', 'modified'}.
    """
    source_id = str(data.get("source_id") or "").strip()
    existing = Record.objects.filter(catalogue=catalogue, source_id=source_id).first() if source_id else None
    if existing is None:
        return None, "new", []
    incoming = build_unsaved_record(catalogue, data, raw, raw_format)
    # Les datations corrigées par l'utilisateur ne sont pas recalculées : on les reporte avant comparaison.
    for prefix in ("composition", "copy"):
        if getattr(existing, f"{prefix}_date_origin") == "user":
            for suffix in ("year_start", "year_end", "date_precision", "date_origin"):
                setattr(incoming, f"{prefix}_{suffix}", getattr(existing, f"{prefix}_{suffix}"))
    from .normalization import normalize_record

    normalize_record(incoming)
    if incoming.compute_hash() == existing.record_hash:
        return existing, "unchanged", []
    changed = [f for f in TRACKED_FIELDS if (getattr(incoming, f) or "") != (getattr(existing, f) or "")
               and f in clean_source_data(data)]
    if raw is not None and raw != existing.raw_data:
        changed.append("raw_data")
    return existing, ("modified" if changed else "unchanged"), changed


@transaction.atomic
def upsert_record(catalogue, data, *, raw=None, raw_format="", origin="import", user=None,
                  dataset_label="", collected_at=None, note=""):
    """Crée ou met à jour une notice en historisant toute modification.

    Retourne (notice, statut) avec statut ∈ {'created', 'updated', 'unchanged'}.
    Les données antérieures sont conservées dans RecordVersion (pas d'écrasement silencieux).
    """
    clean = clean_source_data(data)
    if not clean.get("source_id"):
        raise ValueError("Identifiant source manquant : la notice ne peut pas être tracée.")
    existing = Record.objects.select_for_update().filter(catalogue=catalogue, source_id=clean["source_id"]).first()
    now = collected_at or timezone.now()

    if existing is None:
        record = build_unsaved_record(catalogue, clean, raw, raw_format)
        record.collected_at = now
        record.dataset_label = dataset_label
        record.created_by = user
        record.record_hash = ""
        record.save()
        record.record_hash = record.compute_hash()
        record.save(update_fields=["record_hash"])
        RecordVersion.objects.create(record=record, version=1, change_type="created", origin=origin,
                                     snapshot=record.source_snapshot(), record_hash=record.record_hash,
                                     created_by=user, note=note)
        return record, "created"

    previous = existing.source_snapshot()
    for key, value in clean.items():
        setattr(existing, key, value)
    if raw is not None:
        existing.raw_data = raw
        existing.raw_format = raw_format or existing.raw_format
    # Recalcul complet de la couche normalisée à partir des nouvelles valeurs source.
    from .normalization import normalize_record

    # Recalcul complet des valeurs déduites par règles (corrections de l'utilisateur conservées).
    normalize_record(existing, recompute=True)
    new_hash = existing.compute_hash()
    if new_hash == existing.record_hash:
        Record.objects.filter(pk=existing.pk).update(collected_at=now)
        return existing, "unchanged"

    changed = [f for f in previous if previous.get(f) != existing.source_snapshot().get(f)]
    existing.version += 1
    existing.record_hash = new_hash
    existing.collected_at = now
    if existing.record_status in ("unavailable", "to_check"):
        existing.record_status = "active"
    existing.save()
    RecordVersion.objects.create(
        record=existing, version=existing.version, change_type="modified", origin=origin,
        snapshot=existing.source_snapshot(), record_hash=new_hash, changed_fields=changed,
        previous_values={f: previous.get(f) for f in changed}, created_by=user, note=note,
    )
    return existing, "updated"


def set_record_status(record, status, *, origin="user", user=None, note=""):
    if record.record_status == status:
        return record
    record.record_status = status
    record.version += 1
    record.save(update_fields=["record_status", "version", "updated_at", "search_text", "title_romaji",
                               "period", "document_type", "material_type", "digital_access"])
    change = {"unavailable": "unavailable", "withdrawn": "withdrawn", "deleted": "deleted"}.get(status, "restored")
    RecordVersion.objects.create(record=record, version=record.version, change_type=change, origin=origin,
                                 snapshot=record.source_snapshot(), record_hash=record.record_hash,
                                 created_by=user, note=note)
    return record


#: champ source → champ de la notice qui reçoit la traduction adoptée
ADOPTABLE_TRANSLATION_FIELDS = {"original_title": "translated_title", "description_original": "description_translation"}


def adopt_translation(ed, user):
    """Recopie une traduction proposée dans la notice (couche éditoriale), avec son origine, et la valide.

    Logique extraite de la vue editorial_decide (1.2.0), comportement inchangé. Retourne le champ adopté,
    ou None si la traduction ne porte pas sur un champ adoptable (sujets, lieu…).
    """
    record = ed.record
    field = ADOPTABLE_TRANSLATION_FIELDS.get(ed.target_field)
    if field:
        old = getattr(record, field)
        setattr(record, field, ed.content)
        setattr(record, f"{field}_origin", ed.origin)
        record_editorial_change(record, field, old, ed.content, user,
                                note=f"Traduction adoptée ({ed.get_origin_display()})")
        ed.status = "validated"
        ed.save(update_fields=["status", "updated_at"])
    return field


def validate_translation(ed, user):
    """1.3.0 (décision du 13 novembre 2026) : valider une traduction de notice = l'adopter dans la notice.

    Une seule traduction validée par notice et par champ : la précédente redevient « proposée ».
    """
    from .models import EditorialContent

    (EditorialContent.objects.filter(record=ed.record, kind="translation", target_field=ed.target_field,
                                     status="validated").exclude(pk=ed.pk).update(status="proposed"))
    field = adopt_translation(ed, user)
    if not field:
        ed.status = "validated"
        ed.save(update_fields=["status", "updated_at"])
    return field


def plan_bulk_validation(editorials):
    """2.0.0 (demande du 15 novembre 2026) : traductions à valider en une fois, et celles écartées avec la raison.

    Pour chaque notice et chaque champ, la proposition la plus récente est retenue. Sont écartées : les
    traductions simulées (mode démonstration), celles dont l'original a changé depuis, et les propositions plus
    anciennes du même champ. Les traductions déjà validées ou rejetées ne sont pas concernées.
    Retourne (retenues, écartées) ; écartées = [(traduction, raison)].
    """
    chosen, skipped, seen = [], [], set()
    for ed in sorted(editorials, key=lambda e: e.created_at, reverse=True):
        if ed.kind != "translation" or ed.status != "proposed" or not ed.record_id:
            continue
        key = (ed.record_id, ed.target_field)
        current = (getattr(ed.record, ed.target_field, "") or "").strip() if ed.target_field else ""
        if (ed.data or {}).get("simulated"):
            skipped.append((ed, "simulation (aucune traduction réelle)"))
        elif ed.source_text and current and ed.source_text.strip() != current:
            skipped.append((ed, "l'original a changé depuis cette traduction"))
        elif key in seen:
            skipped.append((ed, "une proposition plus récente du même champ est retenue"))
        else:
            seen.add(key)
            chosen.append(ed)
    return chosen, skipped


def validate_translations(editorials, user):
    """Valide et adopte en une fois les traductions retenues par plan_bulk_validation (tout ou rien)."""
    chosen, skipped = plan_bulk_validation(editorials)
    with transaction.atomic():
        # Une seule instance (verrouillée) par notice : chaque adoption incrémente le numéro de version de la
        # notice ; avec des copies séparées, deux versions recevaient le même numéro (erreur d'intégrité).
        records = {r.pk: r for r in Record.objects.select_for_update().filter(pk__in={ed.record_id for ed in chosen})}
        for ed in chosen:
            ed.record = records[ed.record_id]
            validate_translation(ed, user)
    return chosen, skipped


def bulk_validation_message(chosen, skipped):
    parts = []
    if chosen:
        parts.append(f"{len(chosen)} traduction(s) validée(s) et adoptée(s) dans les fiches.")
    else:
        parts.append("Aucune traduction à valider.")
    reasons = {}
    for _ed, reason in skipped:
        reasons[reason] = reasons.get(reason, 0) + 1
    if reasons:
        parts.append("Écartée(s) : " + " ; ".join(f"{n} — {r}" for r, n in reasons.items()) + ".")
    return " ".join(parts)


def record_editorial_change(record, field, old, new, user, note=""):
    from .normalization import RULE_FIELDS

    if field in RULE_FIELDS or field.endswith(("_year_start", "_year_end")):
        manual = list(record.manual_fields or [])
        key = field.replace("_year_end", "_year_start")
        if key not in manual:
            manual.append(key)
        record.manual_fields = manual
    record.version += 1
    record.save()
    RecordVersion.objects.create(record=record, version=record.version, change_type="editorial", origin="user",
                                 snapshot=record.source_snapshot(), record_hash=record.record_hash,
                                 changed_fields=[field], previous_values={field: old}, created_by=user, note=note)


# --------------------------------------------------------------------------- doublons (règles déterministes)


def _title_key(text):
    return jp.search_normalize(jp.to_shinjitai(text or "")).replace(" ", "")


def similarity(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def duplicate_candidates(record, limit=10):
    """Propose des doublons potentiels : identifiants d'abord, puis titre/auteur/dates/institution.

    Ne fusionne jamais : renvoie une liste [(notice, score, raisons)].
    """
    results = {}
    # 1. Identifiants : même identifiant source dans un autre catalogue (ex. DOI, ID CODH repris)
    same_ids = Record.objects.exclude(pk=record.pk).filter(source_id=record.source_id).exclude(source_id="")
    for other in same_ids[:limit]:
        results[other.pk] = (other, 0.95, ["même identifiant source dans un autre catalogue"])

    key = _title_key(record.original_title)
    if len(key) >= 2:
        prefix = key[: max(2, min(6, len(key)))]
        qs = (Record.objects.exclude(pk=record.pk).exclude(record_status="deleted")
              .filter(search_text__contains=jp.search_normalize(record.original_title)[:max(2, len(prefix))]))
        for other in qs[:200]:
            if other.pk in results:
                continue
            score = similarity(key, _title_key(other.original_title))
            reasons = [f"titre similaire ({score:.0%})"]
            if score < 0.75:
                continue
            if record.creator_original and other.creator_original:
                cs = similarity(_title_key(record.creator_original), _title_key(other.creator_original))
                if cs > 0.8:
                    score += 0.1
                    reasons.append("auteur similaire")
                elif cs < 0.3:
                    score -= 0.2
                    reasons.append("auteurs différents")
            if record.copy_year_start and other.copy_year_start:
                if record.copy_year_start == other.copy_year_start:
                    score += 0.05
                    reasons.append("même date d'exemplaire")
            if record.institution_display and record.institution_display == other.institution_display:
                score += 0.05
                reasons.append("même institution")
                if record.shelfmark and record.shelfmark == other.shelfmark:
                    score += 0.2
                    reasons.append("même cote")
            if score >= 0.75:
                results[other.pk] = (other, min(score, 0.99), reasons)
    ranked = sorted(results.values(), key=lambda x: -x[1])
    return ranked[:limit]


def propose_duplicate_links(record, user=None):
    created = 0
    for other, score, reasons in duplicate_candidates(record):
        a, b = sorted([record, other], key=lambda r: r.pk)
        _, was_created = RecordLink.objects.get_or_create(
            record_a=a, record_b=b, link_type="possible_duplicate",
            defaults={"score": round(score, 3), "rationale": "; ".join(reasons), "origin": "rule", "created_by": user},
        )
        created += int(was_created)
    return created
