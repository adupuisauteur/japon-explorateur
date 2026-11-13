"""
Couche normalisée d'une notice (§6.2) : calculée à partir des champs source,
journalisée et recalculable. Ne modifie jamais les champs originaux.
"""
from apps.core import japanese as jp

DOC_TYPE_RULES = [
    ("genealogie", ["系図", "系譜", "家譜", "genealog", "généalog"]),
    ("journal", ["日記", "日録", "diary", "journal"]),
    ("traite_militaire", ["兵法", "兵書", "軍学", "軍法", "military treatise", "traité militaire"]),
    ("chronique", ["記録", "年代記", "実録", "史", "鑑", "chronicle", "chronique"]),
    ("recit", ["軍記", "物語", "記", "譚", "tale", "récit", "monogatari"]),
    ("registre", ["帳", "目録", "台帳", "register", "registre"]),
    ("carte", ["地図", "絵図", "国図", "map", "carte"]),
    ("poesie", ["歌集", "和歌", "俳諧", "句集", "詩集", "poem", "poésie"]),
    ("religieux", ["経", "仏書", "神道", "sutra", "religi"]),
    ("dictionnaire", ["辞書", "字書", "節用", "dictionar", "dictionnaire"]),
    ("lettre", ["書状", "書簡", "往来", "消息", "letter", "lettre"]),
    ("recueil", ["集", "叢書", "全書", "collection", "recueil"]),
    ("traite", ["論", "考", "treatise", "traité"]),
]

MATERIAL_RULES = [
    ("transcription", ["翻刻", "transcri"]),
    ("edition_moderne", ["活字", "影印", "modern edition", "édition moderne"]),
    ("imprime", ["刊本", "版本", "板本", "刊", "木版", "古活字", "print", "imprim"]),
    ("manuscrit", ["写本", "自筆", "manuscri", "写"]),
    ("numerique", ["digital", "numérique", "電子"]),
]


def _classify(text, rules):
    if not text:
        return ""
    low = jp.nfkc(text).lower()
    for code, words in rules:
        if any(w.lower() in low for w in words):
            return code
    return ""


# Champs de la couche normalisée dérivés par règles (recalculables).
RULE_FIELDS = ("period", "document_type", "material_type")


def reset_rule_fields(record):
    """Efface ce qui a été déduit par règles, sauf les valeurs fixées par l'utilisateur.

    Appelé quand les données source changent : la couche normalisée est alors recalculée
    à partir des nouvelles valeurs (audit, correction 8).
    """
    manual = set(record.manual_fields or [])
    for prefix in ("composition", "copy"):
        if getattr(record, f"{prefix}_date_origin") == "rule" and f"{prefix}_year_start" not in manual:
            setattr(record, f"{prefix}_year_start", None)
            setattr(record, f"{prefix}_year_end", None)
            setattr(record, f"{prefix}_date_precision", "unknown")
            setattr(record, f"{prefix}_date_origin", "source")
    for field in RULE_FIELDS:
        if field not in manual:
            setattr(record, field, "")
    record.normalization_log = []


def normalize_record(record, recompute=False):
    """Calcule les champs normalisés d'une notice et consigne les règles appliquées.

    `recompute=True` : les valeurs déduites par règles sont recalculées depuis les champs
    source actuels ; les corrections de l'utilisateur sont conservées.
    """
    if recompute:
        reset_rule_fields(record)
    log = []

    # Dates : la date de composition et la date de copie restent strictement séparées (§6.4).
    for prefix in ("composition", "copy"):
        text = getattr(record, f"{prefix}_date_text")
        start = getattr(record, f"{prefix}_year_start")
        if text and start is None:
            parsed = jp.parse_historical_date(text)
            if parsed:
                setattr(record, f"{prefix}_year_start", parsed["start"])
                setattr(record, f"{prefix}_year_end", parsed["end"])
                setattr(record, f"{prefix}_date_precision", parsed["precision"])
                if getattr(record, f"{prefix}_date_origin") == "source":
                    setattr(record, f"{prefix}_date_origin", "rule")
                log.append({"field": f"{prefix}_year", "rule": parsed["method"], "value": [parsed["start"], parsed["end"]]})
                if parsed.get("period") and prefix == "composition" and not record.period:
                    record.period = parsed["period"]
                    log.append({"field": "period", "rule": "période nommée", "value": parsed["period"]})

    if not record.period:
        start = record.composition_year_start or record.copy_year_start
        end = record.composition_year_end if record.composition_year_start else record.copy_year_end
        period = jp.period_for_years(start, end)
        if period:
            record.period = period
            log.append({"field": "period", "rule": "années → période", "value": period})

    if not record.document_type:
        dt = _classify(record.document_type_original, DOC_TYPE_RULES) or _classify(record.subjects_original, DOC_TYPE_RULES)
        if dt:
            record.document_type = dt
            log.append({"field": "document_type", "rule": "mots-clés du type source", "value": dt})

    if not record.material_type:
        mt = _classify(record.material_type_original, MATERIAL_RULES)
        if mt:
            record.material_type = mt
            log.append({"field": "material_type", "rule": "mots-clés du support source", "value": mt})

    if not record.digital_access:
        if record.digital_access_url or record.image_url:
            record.digital_access = "image"
        elif record.source_url:
            record.digital_access = "record_only"

    if record.original_title and jp.has_japanese(record.original_title):
        basis = record.reading if record.reading and jp.is_kana_only(record.reading) else record.original_title
        record.title_romaji = jp.to_romaji(basis)[:1000]
    elif not record.title_romaji:
        record.title_romaji = ""

    parts = [
        record.original_title, record.reading, record.translated_title, record.title_romaji,
        record.creator_original, record.creator_reading, jp.to_romaji(record.creator_original or "")
        if jp.has_japanese(record.creator_original) else "",
        record.description_original, record.description_translation, record.holding_institution_text,
        record.subjects_original, record.place_original, record.document_type_original,
        record.material_type_original, record.composition_date_text, record.copy_date_text,
        record.source_id, record.shelfmark,
    ]
    record.search_text = jp.search_normalize(" \n".join(p for p in parts if p))
    if log:
        record.normalization_log = log
    return record
