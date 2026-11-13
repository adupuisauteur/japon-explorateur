"""
Projets, documents, segments et versions (plan 1.3.0, lot 6).

Garanties :
- le texte importé (TranslationDocument.original_text) n'est jamais modifié ;
- après toute opération (création, fusion, division), la concaténation des segments redonne exactement ce
  texte ; sinon l'opération est annulée (transaction) ;
- une seule version validée par segment (contrainte en base) ; valider une version remet la précédente à
  « proposée » ; une correction crée une nouvelle version liée à celle qu'elle corrige ; rien n'est écrasé ;
- fusion et division conservent les traductions existantes, signalées « original modifié depuis la traduction ».
"""
import hashlib

from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from . import memory as tm
from .models import TranslationChapter, TranslationDocument, TranslationSegment, TranslationVersion
from .segmentation import is_translatable, split_text
from .services import RECORD_FIELDS, update_segment_state


class ProjectError(Exception):
    """Opération impossible : message présentable à l'utilisateur."""


def integrity_ok(document):
    joined = "".join(document.segments.order_by("position").values_list("source_text", flat=True))
    return joined == document.original_text


def _check(document):
    if not integrity_ok(document):
        raise ProjectError("Opération annulée : les segments ne redonneraient plus exactement le texte importé.")


@transaction.atomic
def create_document(project, *, title, text, source_kind="paste", filename="", encoding="", confidence="",
                    variety="modern", record=None):
    if not text or not text.strip():
        raise ProjectError("Le texte est vide.")
    order = (project.documents.aggregate(m=Max("order"))["m"] or 0) + 1
    document = TranslationDocument.objects.create(
        project=project, title=title[:300] or "Document sans titre", order=order, source_kind=source_kind,
        record=record, source_filename=filename[:255], original_text=text,
        original_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), encoding=encoding[:30],
        encoding_confidence=confidence, variety=variety)
    TranslationSegment.objects.bulk_create([
        TranslationSegment(document=document, position=i, source_text=s, memory_key=tm.memory_key(s))
        for i, s in enumerate(split_text(text), start=1)])
    _check(document)
    project.save(update_fields=["updated_at"])
    return document


def _following(segment):
    return (TranslationSegment.objects.filter(document=segment.document, position__gt=segment.position)
            .order_by("position").first())


@transaction.atomic
def merge_with_next(segment):
    nxt = _following(segment)
    if nxt is None:
        raise ProjectError("Ce segment est le dernier du document : rien à fusionner.")
    if segment.versions.filter(status="validated").exists() and nxt.versions.filter(status="validated").exists():
        raise ProjectError("Les deux segments ont chacun une traduction validée : retirez d'abord l'une des deux "
                           "validations.")
    had_versions = segment.versions.exists() or nxt.versions.exists()
    segment.source_text += nxt.source_text
    segment.memory_key = tm.memory_key(segment.source_text)
    segment.source_changed = segment.source_changed or had_versions
    segment.save(update_fields=["source_text", "memory_key", "source_changed", "updated_at"])
    nxt.versions.update(segment=segment)
    removed = nxt.position
    nxt.delete()
    TranslationSegment.objects.filter(document=segment.document, position__gt=removed).update(position=F("position") - 1)
    update_segment_state(segment)
    _check(segment.document)
    return segment


@transaction.atomic
def split_segment(segment, first_part):
    """Coupe `segment` après `first_part`, qui doit être un début exact et non vide de son texte."""
    text = segment.source_text
    if not first_part or not text.startswith(first_part) or len(first_part) >= len(text):
        raise ProjectError("La première partie doit être un début exact du segment, plus court que lui.")
    offset = len(first_part)
    TranslationSegment.objects.filter(document=segment.document, position__gt=segment.position).update(
        position=F("position") + 1)
    second = TranslationSegment.objects.create(
        document=segment.document, chapter=segment.chapter, position=segment.position + 1, source_text=text[offset:],
        memory_key=tm.memory_key(text[offset:]), variety=segment.variety)
    had_versions = segment.versions.exists()
    segment.source_text = text[:offset]
    segment.memory_key = tm.memory_key(segment.source_text)
    segment.source_changed = segment.source_changed or had_versions
    segment.save(update_fields=["source_text", "memory_key", "source_changed", "updated_at"])
    update_segment_state(segment)
    _check(segment.document)
    return segment, second


@transaction.atomic
def start_chapter(segment, title):
    """Crée un chapitre qui commence à `segment` et s'étend jusqu'au chapitre suivant."""
    title = (title or "").strip() or f"Chapitre à partir du segment {segment.position}"
    previous_chapter = segment.chapter_id
    chapter = TranslationChapter.objects.create(document=segment.document, title=title[:300], order=segment.position)
    following = TranslationSegment.objects.filter(document=segment.document, position__gte=segment.position)
    next_start = (TranslationChapter.objects.filter(document=segment.document, order__gt=segment.position)
                  .order_by("order").values_list("order", flat=True).first())
    if next_start is not None:
        following = following.filter(position__lt=next_start)
    following.filter(chapter_id=previous_chapter).update(chapter=chapter)
    return chapter


# --------------------------------------------------------------------------- versions


@transaction.atomic
def add_human_version(segment, user, text, *, parent=None):
    text = (text or "").strip("\n")
    if not text.strip():
        raise ProjectError("La traduction saisie est vide.")
    version = TranslationVersion.objects.create(
        segment=segment, text=text, source_text=segment.source_text, origin="human_edit" if parent else "human",
        parent=parent, author=user, variety=segment.variety or segment.document.variety,
        engine=parent.engine if parent else "", model=parent.model if parent else "",
        simulated=False)
    update_segment_state(segment)
    return version


@transaction.atomic
def validate_version(version, user):
    (TranslationVersion.objects.filter(segment=version.segment, status="validated").exclude(pk=version.pk)
     .update(status="proposed"))
    version.status, version.decided_by, version.decided_at = "validated", user, timezone.now()
    version.save(update_fields=["status", "decided_by", "decided_at"])
    update_segment_state(version.segment)
    return version


@transaction.atomic
def reject_version(version, user):
    version.status, version.decided_by, version.decided_at = "rejected", user, timezone.now()
    version.save(update_fields=["status", "decided_by", "decided_at"])
    update_segment_state(version.segment)
    return version


def validate_latest_proposals(segments, user):
    """Valide, pour chaque segment, sa dernière version proposée (s'il n'a pas déjà une version validée)."""
    n = 0
    for segment in segments:
        if segment.versions.filter(status="validated").exists():
            continue
        latest = segment.versions.filter(status="proposed").order_by("-created_at").first()
        if latest is not None:
            validate_version(latest, user)
            n += 1
    return n


# --------------------------------------------------------------------------- notices et projets (décision D2)


NOTICE_PREFIX = "notice:"


@transaction.atomic
def copy_record_to_project(record, project, fields=("original_title", "description_original")):
    """Copie le texte d'une notice dans un projet : un document par champ. La notice n'est pas modifiée."""
    documents = []
    for field in fields:
        text = (getattr(record, field, "") or "").strip()
        if field not in RECORD_FIELDS or not text:
            continue
        documents.append(create_document(
            project, title=f"{RECORD_FIELDS[field]} — {record.original_title[:200]}", text=text, source_kind="record",
            filename=f"{NOTICE_PREFIX}{field}", record=record,
            variety="kanbun" if record.language == "lzh" else "modern"))
    if not documents:
        raise ProjectError("Cette notice n'a aucun texte à copier pour les champs choisis.")
    project.records.add(record)
    return documents


def notice_field(document):
    name = document.source_filename or ""
    return name[len(NOTICE_PREFIX):] if document.source_kind == "record" and name.startswith(NOTICE_PREFIX) else ""


def assembled_translation(document):
    """Traduction complète du document à partir des versions VALIDÉES ; lève ProjectError s'il en manque."""
    parts, origins, simulated = [], set(), False
    for segment in document.segments.order_by("position").prefetch_related("versions"):
        if not is_translatable(segment.source_text):
            parts.append(segment.source_text)
            continue
        validated = next((v for v in segment.versions.all() if v.status == "validated"), None)
        if validated is None:
            raise ProjectError(f"Le segment {segment.position} n'a pas de traduction validée.")
        # Séparateur : les sauts de ligne de l'original (paragraphes) sont conservés ; sinon une espace, car deux
        # phrases japonaises se suivent sans espace alors que leurs traductions françaises en demandent une.
        trailing = segment.source_text[len(segment.source_text.rstrip()):]
        newlines = trailing.replace("\r\n", "\n").count("\n")
        parts.append(validated.text.strip() + ("\n" * newlines if newlines else " "))
        origins.add(validated.origin)
        simulated = simulated or validated.simulated
    return "".join(parts).strip(), origins, simulated


@transaction.atomic
def publish_to_record(document, user):
    """Publie la traduction validée d'un document copié d'une notice : proposition dans la couche éditoriale.

    La proposition devient visible par tous les comptes (la couche éditoriale est commune) : l'interface
    demande une confirmation explicite, surtout pour un projet confidentiel (décision D2).
    """
    from apps.catalog.models import EditorialContent

    field = notice_field(document)
    if not (field and document.record_id):
        raise ProjectError("Ce document ne provient pas d'une notice : rien à publier.")
    text, origins, simulated = assembled_translation(document)
    origin = "ai" if "ai" in origins else ("mt" if "machine" in origins else "user")
    return EditorialContent.objects.create(
        record=document.record, kind="translation", target_field=field, source_text=document.original_text,
        content=text, origin=origin, status="proposed", author=user,
        data={"published_from_project": document.project_id, "document": document.pk,
              "confidential_project": document.project.confidential, "simulated": simulated,
              "engine": "projet de traduction"})
