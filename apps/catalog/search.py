"""Moteur de recherche locale (notices collectées et importées)."""
from django.db.models import Case, IntegerField, Q, Value, When

from apps.core import japanese as jp

from .models import Record

SORTS = {
    "relevance": "Pertinence",
    "title": "Titre",
    "date": "Date (composition, puis exemplaire)",
    "source": "Source",
    "collected": "Date de collecte",
}


def _term_q(term):
    """Une requête = tous les mots (ET) ; une variante = une autre requête (OU)."""
    norm = jp.search_normalize(term)
    words = [w for w in norm.split(" ") if w]
    q = Q()
    for w in words:
        q &= Q(search_text__contains=w)
    return q


def local_search(query, base_qs=None, sort="relevance"):
    qs = base_qs if base_qs is not None else Record.objects.all()
    qs = qs.select_related("catalogue")
    filters = query.filters or {}

    statuses = filters.get("record_status") or ["active", "to_check", "unavailable"]
    qs = qs.filter(record_status__in=statuses)

    terms = query.all_terms()
    if terms:
        combined = Q()
        for term in terms:
            combined |= _term_q(term)
        qs = qs.filter(combined)
    if query.title:
        qs = qs.filter(Q(original_title__icontains=query.title) | Q(reading__icontains=query.title)
                       | Q(translated_title__icontains=query.title) | Q(title_romaji__icontains=query.title))
    if query.creator:
        qs = qs.filter(Q(creator_original__icontains=query.creator) | Q(creator_reading__icontains=query.creator)
                       | Q(search_text__contains=jp.search_normalize(query.creator)))
    if query.subject:
        qs = qs.filter(Q(subjects_original__icontains=query.subject)
                       | Q(record_subjects__subject__label__icontains=query.subject)).distinct()
    if query.place:
        qs = qs.filter(Q(place_original__icontains=query.place) | Q(holding_institution_text__icontains=query.place))

    for key in ("period", "document_type", "material_type", "digital_access", "language"):
        values = [v for v in (filters.get(key) or []) if v]
        if values:
            qs = qs.filter(**{f"{key}__in": values})
    catalogues = [c for c in (filters.get("catalogues") or []) if c]
    if catalogues:
        qs = qs.filter(catalogue__code__in=catalogues)
    if filters.get("institution"):
        qs = qs.filter(holding_institution_text__icontains=filters["institution"])

    # Dates : composition et exemplaire restent distinctes (§7.2).
    date_kind = filters.get("date_kind") or "any"
    date_from, date_to = query.date_from, query.date_to
    if date_from or date_to:
        prefixes = {"composition": ["composition"], "copy": ["copy"]}.get(date_kind, ["composition", "copy"])
        dq = Q()
        for p in prefixes:
            part = Q(**{f"{p}_year_start__isnull": False})
            if date_to:
                part &= Q(**{f"{p}_year_start__lte": date_to})
            if date_from:
                part &= (Q(**{f"{p}_year_end__gte": date_from}) |
                         Q(**{f"{p}_year_end__isnull": True, f"{p}_year_start__gte": date_from}))
            dq |= part
        qs = qs.filter(dq)

    if sort == "title":
        qs = qs.order_by("original_title")
    elif sort == "date":
        qs = qs.order_by("composition_year_start", "copy_year_start", "original_title")
    elif sort == "source":
        qs = qs.order_by("catalogue__name", "original_title")
    elif sort == "collected":
        qs = qs.order_by("-collected_at")
    elif terms:
        main = jp.search_normalize(terms[0])
        qs = qs.annotate(score=Case(
            When(original_title__iexact=terms[0], then=Value(0)),
            When(original_title__icontains=terms[0], then=Value(1)),
            When(reading__icontains=terms[0], then=Value(2)),
            When(title_romaji__icontains=main, then=Value(2)),
            When(creator_original__icontains=terms[0], then=Value(3)),
            default=Value(5), output_field=IntegerField(),
        )).order_by("score", "original_title")
    return qs


def suggest_variants(text):
    """Variantes déterministes, présentées comme suggestions avec leur origine (§7.3).

    Retourne une liste de dicts {value, kind, origin, verification}.
    """
    text = (text or "").strip()
    if not text:
        return []
    out, seen = [], {text}

    def add(value, kind, verification):
        value = (value or "").strip()
        if value and value not in seen:
            seen.add(value)
            out.append({"value": value, "kind": kind, "origin": "règle automatique", "verification": verification})

    nf = jp.nfkc(text)
    add(nf, "Normalisation Unicode (NFKC)", "équivalence technique")
    if jp.has_kanji(text):
        add(jp.to_shinjitai(text), "Forme nouvelle des kanji (shinjitai)", "correspondance de table, à vérifier")
        add(jp.to_kyujitai(text), "Forme ancienne des kanji (kyūjitai)", "correspondance de table, à vérifier")
        reading = jp.to_hiragana_reading(text)
        add(reading, "Lecture automatique (hiragana)", "lecture non vérifiée")
        add(jp.to_romaji(text), "Rōmaji automatique", "lecture non vérifiée")
    elif jp.has_japanese(text):
        add(jp.kata_to_hira(text), "Hiragana", "équivalence d'écriture")
        add(jp.hira_to_kata(text), "Katakana", "équivalence d'écriture")
        add(jp.to_romaji(text), "Rōmaji (Hepburn)", "translittération de kana")
    elif jp.looks_like_romaji(text):
        hira = jp.romaji_to_hiragana(text)
        add(hira, "Kana depuis le rōmaji", "translittération, à vérifier")
        add(jp.fold_macrons(text), "Rōmaji sans macrons", "équivalence de graphie")
        if any(c in text for c in "ōū"):
            add(text.replace("ō", "ou").replace("ū", "uu"), "Rōmaji (voyelles longues doublées)", "équivalence de graphie")
            add(text.replace("ō", "oh").replace("ū", "u"), "Rōmaji (voyelles longues en -oh)", "équivalence de graphie")
    return out
