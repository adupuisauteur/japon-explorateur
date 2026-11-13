"""
Import de textes à traduire (décision A3) : texte collé, .txt, .docx (texte seul), PDF avec couche texte.

- .txt : encodage détecté par apps.core.encoding.detect_text (UTF-8, Shift_JIS/cp932, EUC-JP, UTF-16),
  avec un indice de fiabilité ; « incertain » → l'utilisateur doit confirmer après aperçu (E3).
- .docx : texte des paragraphes, puis des tableaux, dans l'ordre du document (python-docx, déjà présent).
  La mise en forme n'est pas conservée (hors périmètre).
- .pdf : texte page par page (pypdf, déjà présent). Un PDF sans texte (image numérisée) est refusé :
  la reconnaissance de caractères (OCR) est hors périmètre. L'ordre du texte extrait d'un PDF peut être
  imparfait (colonnes, texte vertical) : l'aperçu permet de le vérifier avant import.
Fins de ligne : conservées telles quelles pour .txt ; « \n » pour .docx et .pdf.
"""
import io
from dataclasses import dataclass, field

from apps.core.encoding import detect_text

MAX_BYTES = 10 * 1024 * 1024
KINDS = {".txt": "txt", ".text": "txt", ".docx": "docx", ".pdf": "pdf"}


class ImportRefused(Exception):
    """Fichier non importable : message présentable à l'utilisateur."""


@dataclass
class ImportedText:
    text: str
    kind: str
    filename: str = ""
    encoding: str = ""
    confidence: str = "sure"
    notes: list = field(default_factory=list)


def _kind(filename):
    name = (filename or "").lower()
    for ext, kind in KINDS.items():
        if name.endswith(ext):
            return kind
    raise ImportRefused("Format non pris en charge : importez un fichier .txt, .docx ou .pdf (avec texte).")


def import_file(uploaded):
    """`uploaded` : fichier Django (UploadedFile). Retourne un ImportedText ; lève ImportRefused."""
    if uploaded.size > MAX_BYTES:
        raise ImportRefused(f"Fichier trop volumineux ({uploaded.size // 1024} Ko ; maximum {MAX_BYTES // 1048576} Mo).")
    kind = _kind(uploaded.name)
    raw = uploaded.read()
    if kind == "txt":
        decoded = detect_text(raw)
        return ImportedText(decoded.text, "txt", uploaded.name, decoded.encoding, decoded.confidence, decoded.notes)
    if kind == "docx":
        return ImportedText(_docx_text(raw), "docx", uploaded.name, "utf-8", "sure")
    text, notes = _pdf_text(raw)
    return ImportedText(text, "pdf", uploaded.name, "", "sure", notes)


def _docx_text(raw):
    from docx import Document

    try:
        document = Document(io.BytesIO(raw))
    except Exception:  # noqa: BLE001 — fichier corrompu ou non Word
        raise ImportRefused("Fichier Word illisible (.docx attendu ; les anciens .doc ne sont pas pris en charge).") from None
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append("\t".join(cell.text for cell in row.cells))
    text = "\n".join(parts).strip("\n")
    if not text.strip():
        raise ImportRefused("Ce fichier Word ne contient pas de texte.")
    return text


def _pdf_text(raw):
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception:  # noqa: BLE001
        raise ImportRefused("PDF illisible ou protégé.") from None
    text = "\n".join(p.strip("\n") for p in pages).strip("\n")
    if not text.strip():
        raise ImportRefused("Ce PDF ne contient pas de texte exploitable (document numérisé en image ?). "
                            "La reconnaissance de caractères (OCR) n'est pas prise en charge.")
    notes = [f"{len(pages)} page(s) ; vérifiez l'ordre du texte dans l'aperçu (colonnes, texte vertical)."]
    return text, notes
