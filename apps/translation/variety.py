"""
Repérage du japonais ancien (2.0.0, lot 4, demande U10 du 15 novembre 2026).

Le repérage est une SUGGESTION : « japonais ancien probable », que l'utilisateur confirme ou corrige. Il
n'est jamais présenté comme sûr. Indices recherchés (règles simples, sans dictionnaire) :

- kanbun : signes de lecture (kaeriten, bloc Unicode 3190–319F, ou レ一二三上下 en petits caractères), ou texte
  presque sans kana avec des mots-outils du chinois classique (之 者 也 矣 焉 乎 哉 於 而 則) ;
- sōrōbun (style épistolaire) : 候 répété, souvent avec 被・可・致・申 ;
- bungo (japonais classique) : terminaisons et auxiliaires classiques (けり, なり。, たり。, べし, ざる, ぬ。, らむ,
  けむ, 侍り, 給ふ…) et kana historiques (ゐ, ゑ ; ふ en fin de verbe : いふ, 思ふ).

Seuils prudents : sous le seuil, le texte reste « moderne ». Un texte court (titre seul) n'est jamais classé.
"""
import hashlib
import re

ANCIENT = ("classical", "kanbun")
KAERITEN = re.compile(r"[㆐-㆟]")
KANA = re.compile(r"[ぁ-ゟ゠-ヿ]")
KANJI = re.compile(r"[一-鿿]")
KANBUN_WORDS = re.compile(r"[之者也矣焉乎哉於而則]")
SORO = re.compile(r"候")
SORO_HELPERS = re.compile(r"[被可致申]")
BUNGO = [
    (re.compile(r"けり[。、\s]|けり$"), "けり"), (re.compile(r"なり[。、]"), "なり"), (re.compile(r"たり[。、]"), "たり"),
    (re.compile(r"べ[しきくけ]|べからず"), "べし"), (re.compile(r"ざる|ざり|ざれ"), "ざる"), (re.compile(r"[^ぁ-ゟ]ぬ[。、]"), "ぬ"),
    (re.compile(r"らむ|けむ|なむ"), "む"), (re.compile(r"侍[りる]|給[ふへ]|たまふ"), "敬語古形"),
    (re.compile(r"[ゐゑ]"), "旧仮名"), (re.compile(r"(?:いふ|思ふ|言ふ|云ふ|候ふ|給ふ)"), "ふ"),
    (re.compile(r"(?:思|言|云|給|候|行|書|問|会|逢|向)ひ"), "旧仮名（ひ）"),
    (re.compile(r"ければ|けれど|しかば|ども[、。]"), "已然形"), (re.compile(r"[^ぁ-ゟ]き[。、]"), "き"),
]
MIN_CHARS = 20


def detect(text):
    """(variété, indices) : « kanbun », « classical » ou « modern ». Les indices expliquent la suggestion."""
    text = (text or "").strip()
    if len(text) < MIN_CHARS:
        return "modern", []
    kana = len(KANA.findall(text))
    kanji = len(KANJI.findall(text))
    reasons = []
    if KAERITEN.search(text):
        return "kanbun", ["signes de lecture du kanbun (kaeriten)"]
    if kanji >= 15 and kana <= kanji * 0.05 and len(KANBUN_WORDS.findall(text)) >= 3:
        return "kanbun", ["texte presque sans kana", "mots-outils du chinois classique (之・者・也…)"]
    soro = len(SORO.findall(text))
    if soro >= 2 and SORO_HELPERS.search(text):
        reasons.append(f"style épistolaire en 候 ({soro} occurrences)")
    found = [label for pattern, label in BUNGO if pattern.search(text)]
    if len(found) >= 2:
        reasons.append("formes du japonais classique : " + "、".join(found[:6]))
    if reasons:
        return "classical", reasons
    return "modern", []


def is_ancient(variety):
    return variety in ANCIENT


def sha(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def variety_of_record(record):
    """Variété d'une notice : langue déclarée kanbun, annotation (confirmée ou repérée), sinon repérage à la volée."""
    if getattr(record, "language", "") == "lzh":
        return "kanbun"
    annotation = getattr(record, "language_variety", None) if record.pk else None
    try:
        if annotation is not None:
            return annotation.variety
    except Exception:  # noqa: BLE001 — relation absente
        pass
    return detect(_record_text(record))[0]


def _record_text(record):
    return "\n".join(v for v in (record.original_title, record.description_original) if v)


def annotate_record(record, *, force=False):
    """Repère la variété d'une notice et l'enregistre comme « probable », sans toucher une confirmation."""
    from .models import RecordVariety

    text = _record_text(record)
    existing = RecordVariety.objects.filter(record=record).first()
    if existing is not None and existing.origin == "user" and not force:
        return existing
    variety, reasons = detect(text)
    if existing is None and variety == "modern":
        return None
    obj, _ = RecordVariety.objects.update_or_create(
        record=record, defaults={"variety": variety, "origin": "detected", "reasons": reasons, "source_sha256": sha(text)})
    return obj


def confirm_record(record, variety, user):
    from .models import VARIETIES, RecordVariety

    if variety not in dict(VARIETIES):
        raise ValueError("Variété inconnue.")
    obj, _ = RecordVariety.objects.update_or_create(
        record=record, defaults={"variety": variety, "origin": "user", "reasons": [], "updated_by": user,
                                 "source_sha256": sha(_record_text(record))})
    return obj


def variety_of_document(document):
    """Variété d'un document : celle choisie (« moderne » par défaut) ; le repérage n'est qu'une suggestion."""
    return document.variety or "modern"


def suggest_for_document(document):
    """Suggestion pour un document encore marqué « moderne » : (variété, indices) ou None."""
    if document.variety != "modern":
        return None
    variety, reasons = detect(document.original_text[:20000])
    return (variety, reasons) if variety != "modern" else None
