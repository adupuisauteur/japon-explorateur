"""
Détection de l'encodage des fichiers texte japonais.

- `decode_text` : fonction déplacée telle quelle depuis apps/updates/importers.py (1.2.0), où elle reste
  importable sous le même nom. Comportement inchangé, y compris le dernier recours latin-1.
- `detect_text` (1.3.0) : même ordre de détection, mais avec un indice de fiabilité, pour que le module
  de traduction AVERTISSE au lieu de produire un texte illisible sans le dire. Elle ne décode jamais
  en latin-1 sans le signaler comme « incertain ».
"""
from dataclasses import dataclass, field

JAPANESE_ENCODINGS = ("cp932", "euc_jp")


def decode_text(raw):
    for enc in ("utf-8-sig", "cp932", "euc_jp", "utf-16"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1"), "latin-1"


@dataclass
class DecodedText:
    text: str
    encoding: str
    confidence: str  # "sure", "probable" ou "uncertain"
    notes: list = field(default_factory=list)


def _plausibility(text):
    """Part des caractères attendus dans un texte japonais ou occidental (0 à 1).

    Les décodages erronés produisent surtout des katakana demi-chasse, des caractères de la zone
    privée ou des symboles rares ; un texte bien décodé se compose de kana, de kanji, de ponctuation
    japonaise et de caractères latins courants.
    """
    if not text:
        return 1.0
    good = 0
    for ch in text:
        o = ord(ch)
        if (ch.isspace() or 0x20 <= o < 0x7F or 0x3000 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF
                or 0x4E00 <= o <= 0x9FFF or 0xFF01 <= o <= 0xFF5E or 0xF900 <= o <= 0xFAFF
                or 0xC0 <= o <= 0x17F or o in (0x2026, 0x2014, 0x2015, 0x2018, 0x2019, 0x201C, 0x201D, 0x00AB, 0x00BB)):
            good += 1
    return good / len(text)


def _kana_share(text):
    """Part des kana et de la ponctuation japonaise parmi les caractères non ASCII.

    Un texte japonais réel en contient ; une suite de kanji tirée au hasard (par exemple du Shift_JIS
    lu comme de l'UTF-16) n'en contient presque pas.
    """
    wide = [ch for ch in text if ord(ch) > 0x7F and not ch.isspace()]
    if not wide:
        return 1.0
    return sum(1 for ch in wide if 0x3000 <= ord(ch) <= 0x30FF or 0xFF01 <= ord(ch) <= 0xFF5E) / len(wide)


def _has_non_ascii(raw):
    return any(b >= 0x80 for b in raw)


def detect_text(raw):
    """Décode `raw` (bytes) et indique la fiabilité de l'encodage retenu."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return DecodedText(raw[3:].decode("utf-8", errors="strict"), "utf-8", "sure", ["marque BOM UTF-8"])
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return DecodedText(raw.decode("utf-16"), "utf-16", "sure", ["marque BOM UTF-16"])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is not None:
        if _has_non_ascii(raw):
            return DecodedText(text, "utf-8", "sure")
        # Octets tous ASCII : peut aussi être du japonais en kana encodé en UTF-16 sans marque
        # (« かな » donne « K0j0 »). Un vrai texte ASCII lu en UTF-16 ne donne presque jamais de kana.
        if len(raw) % 2 == 0:
            for enc in ("utf-16-le", "utf-16-be"):
                other = raw.decode(enc, errors="replace")
                proper_kana = sum(1 for ch in other if 0x3041 <= ord(ch) <= 0x30FA)
                if proper_kana >= max(2, len(other) // 2) and _plausibility(other) > 0.98:
                    return DecodedText(other, enc, "uncertain",
                                       ["octets lisibles aussi comme du texte ASCII : vérifiez le résultat"])
        return DecodedText(text, "utf-8", "sure", ["texte ASCII : encodage sans importance"])

    # UTF-16 sans marque : nombreux octets nuls
    if raw and raw.count(0) > len(raw) // 4:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                text = raw.decode(enc)
            except UnicodeDecodeError:
                continue
            if _plausibility(text) > 0.95:
                return DecodedText(text, enc, "probable", ["UTF-16 sans marque, déduit des octets nuls"])

    candidates = []
    # UTF-16 sans marque, texte japonais (peu d'octets nuls) : mis en concurrence, départagé par la vraisemblance.
    encodings = JAPANESE_ENCODINGS + (("utf-16-le", "utf-16-be") if raw and len(raw) % 2 == 0 else ())
    for enc in encodings:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        candidates.append((_plausibility(text), _kana_share(text), enc, text))
    if candidates:
        # Vraisemblance d'abord, puis part de kana pour départager deux lectures également « propres ».
        candidates.sort(key=lambda c: (round(c[0], 2), c[1]), reverse=True)
        score, kana, enc, text = candidates[0]
        notes = []
        if len(candidates) > 1:
            other_score, other_kana, other_enc, _ = candidates[1]
            gap = score - other_score
            notes.append(f"décodable aussi en {other_enc} (écart de vraisemblance {gap:.2f})")
            distinct = gap > 0.05 or (kana - other_kana) > 0.1
            confidence = "probable" if score > 0.98 and distinct else "uncertain"
        else:
            confidence = "probable" if score > 0.98 else "uncertain"
        if score <= 0.98:
            notes.append(f"{(1 - score):.0%} de caractères inattendus")
        return DecodedText(text, enc, confidence, notes)

    return DecodedText(raw.decode("latin-1"), "latin-1", "uncertain",
                       ["aucun encodage japonais ne convient : décodage de secours, texte probablement illisible"])
