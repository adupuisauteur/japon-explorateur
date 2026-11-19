"""Textes intégraux téléchargés à la demande (2.0.0, lot 10 ; Aozora Bunko pour commencer).

Le texte est gardé tel que reçu (décodé, notation Aozora intacte) dans RecordText ; l'affichage avec furigana et la
version « texte seul » (pour un projet de traduction) en sont dérivés à chaque lecture. Rien n'est téléchargé sans
clic de l'utilisateur.

Notation Aozora (https://www.aozora.gr.jp/aozora-manual/) :
  ｜漢字《かんじ》 ou 漢字《かんじ》 : lecture (ruby) ;
  ［＃…］ : note de mise en forme ou de saisie ; ※［＃「…」、第3水準1-85-25］ : caractère hors JIS décrit ;
  en-tête (titre, auteur), bloc d'explication des signes entre deux lignes de tirets, colophon « 底本： ».
"""
import hashlib
import io
import re
import zipfile

from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.connectors.base import ConnectorError
from apps.connectors.http import ConnectorHTTP

MAX_BYTES = 20 * 1024 * 1024
DASHES = re.compile(r"^-{20,}\s*$", re.M)
RUBY_BAR = re.compile(r"｜([^《｜\n]+)《([^》\n]+)》")
RUBY_KANJI = re.compile(r"([㐀-鿿豈-﫿々〆ヵヶ仝〇\U00020000-\U0002ffff]+)《([^》\n]+)》")
GAIJI = re.compile(r"※［＃(?:「([^」]*)」)?[^］]*］")
NOTE = re.compile(r"［＃[^］]*］")


class TextError(Exception):
    pass


def text_url(record):
    """(adresse, format) du meilleur fichier texte connu pour la notice, ou (None, None)."""
    raw = record.raw_data or {}
    if raw.get("テキストファイルURL", "").startswith("http"):
        return raw["テキストファイルURL"], "zip"
    xhtml = raw.get("XHTML/HTMLファイルURL") or (record.digital_access_url if record.catalogue.code == "aozora" else "")
    if xhtml and xhtml.startswith("http"):
        return xhtml, "xhtml"
    return None, None


def _decode(raw):
    """Aozora : Shift_JIS (cp932) pour l'essentiel ; JIS X 0213 pour quelques fichiers ; UTF-8 rare."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), "utf-8"
    for encoding in ("cp932", "shift_jis_2004", "utf-8", "euc_jp"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace"), "cp932 (caractères illisibles remplacés)"


def from_zip(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".txt")]
            if not names:
                raise TextError("L'archive ne contient pas de fichier texte (.txt).")
            info = archive.getinfo(names[0])
            if info.file_size > MAX_BYTES:
                raise TextError("Fichier texte trop volumineux.")
            return _decode(archive.read(names[0]))
    except zipfile.BadZipFile as exc:
        raise TextError("Archive zip illisible.") from exc


def from_xhtml(content):
    """Page XHTML d'Aozora : corps du texte (div.main_text), furigana reconvertis en notation 《》."""
    from lxml import etree, html

    head = content[:2000].decode("ascii", errors="ignore").lower()
    encoding = "utf-8" if "utf-8" in head else "cp932"
    text, used = (content.decode("utf-8"), "utf-8") if encoding == "utf-8" else _decode(content)
    tree = html.fromstring(text)
    main = tree.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' main_text ')]")
    if not main:
        raise TextError("Page XHTML sans corps de texte reconnu (div.main_text) : le format a peut-être changé.")
    node = main[0]
    for ruby in node.xpath(".//ruby"):
        base = "".join(ruby.xpath("./rb//text()")) or "".join(t for t in ruby.xpath("./text()"))
        reading = "".join(ruby.xpath("./rt//text()"))
        tail = ruby.tail or ""
        replacement = etree.Element("span")
        replacement.text = f"｜{base}《{reading}》" if reading else base
        replacement.tail = tail
        ruby.getparent().replace(ruby, replacement)
    for br in node.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")
    title = " ".join(t.strip() for t in tree.xpath("//h1//text() | //h2//text()") if t.strip())
    body = node.text_content().strip()
    colophon = " ".join(" ".join(tree.xpath("//div[@class='bibliographical_information']//text()")).split())
    return "\n".join(p for p in (title, "", body, "", colophon) if p is not None), used


def split(text):
    """(en-tête, corps, colophon). Sans structure Aozora reconnue : tout est corps."""
    text = text.replace("\r\n", "\n")
    head, body = "", text
    blocks = DASHES.split(text)
    if len(blocks) >= 3:  # en-tête / explication des signes / corps
        head, body = blocks[0].strip(), DASHES.split(text, maxsplit=2)[2]
    colophon = ""
    at = body.rfind("\n底本：")
    if at >= 0:
        body, colophon = body[:at], body[at:].strip()
    return head, body.strip("\n"), colophon


def plain(text):
    """Texte seul, pour la traduction : sans lectures ni notes de mise en forme ; caractère hors JIS → ※〔description〕."""
    out = GAIJI.sub(lambda m: f"※〔{m.group(1)}〕" if m.group(1) else "※", text)
    out = RUBY_BAR.sub(r"\1", out)
    out = RUBY_KANJI.sub(r"\1", out)
    out = NOTE.sub("", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def ruby_html(text):
    """HTML sûr : tout est échappé, puis seules les lectures deviennent des balises <ruby>."""
    out = escape(text)
    out = GAIJI.sub(lambda m: f'<span class="aozora-gaiji" title="{m.group(1) or ""}">※</span>', out)
    out = RUBY_BAR.sub(r"<ruby>\1<rt>\2</rt></ruby>", out)
    out = RUBY_KANJI.sub(r"<ruby>\1<rt>\2</rt></ruby>", out)
    out = NOTE.sub("", out)
    return mark_safe(out.replace("\n", "<br>"))


def fetch(record, user):
    """Télécharge le texte de la notice (clic de l'utilisateur) et l'enregistre. Retourne le RecordText."""
    from .models import RecordText

    url, kind = text_url(record)
    if not url:
        raise TextError("Aucun fichier texte connu pour cette notice.")
    try:
        response = ConnectorHTTP(record.catalogue).get_bytes(url, max_bytes=MAX_BYTES)
    except ConnectorError as exc:
        raise TextError(f"Téléchargement impossible : {exc}") from exc
    text, encoding = from_zip(response["content"]) if kind == "zip" else from_xhtml(response["content"])
    if not text.strip():
        raise TextError("Le fichier reçu ne contient pas de texte.")
    return RecordText.objects.create(
        record=record, source_url=url, file_format=kind, encoding=encoding, text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), size=len(response["content"]),
        fetched_at=timezone.now(), fetched_by=user)
