"""Export PDF (ReportLab) : police japonaise incorporée, sommaire, signets, liens, en-têtes/pieds paginés."""
import os
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from .common import citation, fiche_rows, metadata_lines

ACCENT = colors.HexColor("#8A2B23")
MUTED = colors.HexColor("#555B66")
SOFT = colors.HexColor("#F4EFE9")

_FONTS = None
REPLACEMENT = "〓"  # 下駄記号 : signe typographique japonais des caractères indisponibles


def _cmap(font):
    return getattr(font.face, "charToGlyph", {}) or {}


def font_set():
    """Police principale incorporée + polices de secours TrueType, avec leur couverture de caractères."""
    global _FONTS
    if _FONTS:
        return _FONTS
    primary, primary_cmap, embedded = None, None, False
    candidates = ([settings.PDF_JAPANESE_FONT] if settings.PDF_JAPANESE_FONT else []) + settings.PDF_JAPANESE_FONT_CANDIDATES
    for path in candidates:
        if path and os.path.exists(path):
            try:
                font = TTFont("JaponText", path)
                pdfmetrics.registerFont(font)
                primary, primary_cmap, embedded = "JaponText", _cmap(font), True
                break
            except Exception:
                continue
    if primary is None:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        primary, primary_cmap = "HeiseiMin-W3", None
    fallbacks = []
    for i, path in enumerate(settings.PDF_FALLBACK_FONTS):
        if path and os.path.exists(path):
            try:
                font = TTFont(f"JaponSecours{i}", path)
                pdfmetrics.registerFont(font)
                fallbacks.append((f"JaponSecours{i}", _cmap(font)))
            except Exception:
                continue
    _FONTS = (primary, primary_cmap, fallbacks, embedded)
    return _FONTS


class GlyphMapper:
    """Balise chaque caractère avec une police qui le contient ; signale ceux qu'aucune police ne contient."""

    def __init__(self):
        self.primary, self.cmap, self.fallbacks, self.embedded = font_set()
        self.missing = {}

    def _font_for(self, ch):
        if self.cmap is None or ch in "\n\t " or ord(ch) in self.cmap:
            return self.primary
        for name, cmap in self.fallbacks:
            if ord(ch) in cmap:
                return name
        return None

    def runs(self, text):
        """Découpe le texte en segments [(police, texte)] ; l'indisponible devient 〓 et est consigné."""
        result, run, run_font = [], [], self.primary
        for ch in str(text):
            font = self._font_for(ch)
            if font is None:
                self.missing[ch] = f"U+{ord(ch):04X}"
                font, ch = self.primary, REPLACEMENT
            if font != run_font and run:
                result.append((run_font, "".join(run)))
                run = []
            run_font = font
            run.append(ch)
        if run:
            result.append((run_font, "".join(run)))
        return result

    def markup(self, text):
        return "".join(escape(chunk) if font == self.primary else f'<font name="{font}">{escape(chunk)}</font>'
                       for font, chunk in self.runs(text))

    def draw(self, canvas, x, y, text, size, align="left"):
        """Texte d'en-tête / pied de page dessiné directement sur la page, avec les mêmes polices de secours."""
        parts = self.runs(text)
        if align == "right":
            x -= sum(pdfmetrics.stringWidth(chunk, font, size) for font, chunk in parts)
        for font, chunk in parts:
            canvas.setFont(font, size)
            canvas.drawString(x, y, chunk)
            x += pdfmetrics.stringWidth(chunk, font, size)


def japanese_font():
    primary, _, _, embedded = font_set()
    return primary, embedded


class _Doc(SimpleDocTemplate):
    def __init__(self, *args, meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta = meta
        self._heading_seq = 0

    def beforeDocument(self):
        self._heading_seq = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and getattr(flowable, "_toc_level", None) is not None:
            text = flowable.getPlainText()
            self._heading_seq += 1
            key = f"h{self._heading_seq}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text[:120], key, level=flowable._toc_level, closed=flowable._toc_level > 0)
            self.notify("TOCEntry", (flowable._toc_level, flowable._toc_markup, self.page, key))


def _heading(text, style, level, mapper):
    markup = mapper.markup(text)
    p = Paragraph(markup, style)
    p._toc_level = level
    p._toc_markup = markup
    return p


def generate_pdf(doc, out_dir, basename):
    font, embedded = japanese_font()
    gm = GlyphMapper()
    meta = doc.metadata
    opts = doc.options
    base = getSampleStyleSheet()
    s = {
        "body": ParagraphStyle("body", parent=base["Normal"], fontName=font, fontSize=9.5, leading=14, wordWrap="CJK"),
        "small": ParagraphStyle("small", parent=base["Normal"], fontName=font, fontSize=8, leading=11,
                                textColor=MUTED, wordWrap="CJK"),
        "title": ParagraphStyle("title", parent=base["Title"], fontName=font, fontSize=24, leading=32,
                                textColor=ACCENT, alignment=TA_CENTER, wordWrap="CJK"),
        "subtitle": ParagraphStyle("subtitle", fontName=font, fontSize=13, leading=18, alignment=TA_CENTER,
                                   textColor=MUTED, wordWrap="CJK"),
        "h1": ParagraphStyle("h1", fontName=font, fontSize=15, leading=20, textColor=ACCENT, spaceBefore=10,
                             spaceAfter=8, wordWrap="CJK"),
        "h2": ParagraphStyle("h2", fontName=font, fontSize=11.5, leading=16, textColor=ACCENT, spaceBefore=10,
                             spaceAfter=4, wordWrap="CJK"),
        "label": ParagraphStyle("label", fontName=font, fontSize=8.5, leading=11.5, textColor=MUTED, wordWrap="CJK"),
        "cell": ParagraphStyle("cell", fontName=font, fontSize=9, leading=12.5, wordWrap="CJK"),
        "toc1": ParagraphStyle("toc1", fontName=font, fontSize=10, leading=15, leftIndent=0),
        "toc2": ParagraphStyle("toc2", fontName=font, fontSize=8.5, leading=12, leftIndent=14, textColor=MUTED),
    }

    def para(text, style="body"):
        return Paragraph(gm.markup(text).replace("\n", "<br/>"), s[style])

    def link(url):
        return Paragraph(f'<a href="{escape(url)}" color="#1F4E79">{gm.markup(url)}</a>', s["cell"])

    story = [Spacer(1, 5 * cm), para(meta["title"], "title")]
    if meta.get("subtitle"):
        story.append(para(meta["subtitle"], "subtitle"))
    if meta.get("subject"):
        story += [Spacer(1, 0.4 * cm), para(meta["subject"], "subtitle")]
    story.append(Spacer(1, 1.5 * cm))
    rows = [[para(k, "label"), para(v, "cell")] for k, v in metadata_lines(doc)]
    t = Table(rows, colWidths=[5.5 * cm, 10.5 * cm])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, SOFT)]))
    story += [t, PageBreak()]

    if opts.get("toc", True):
        toc = TableOfContents(tableStyle=TableStyle([("FONTNAME", (0, 0), (-1, -1), font),
                                                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                                     ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                                     ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        toc.levelStyles = [s["toc1"], s["toc2"]]
        story += [para("Sommaire", "h1"), toc, PageBreak()]

    if doc.introduction:
        story.append(_heading("Introduction", s["h1"], 0, gm))
        story.append(para(doc.introduction))

    for sec in doc.sections:
        story.append(_heading(sec["title"], s["h1"], 0, gm))
        if sec["description"]:
            story.append(para(sec["description"]))
        for rec in sec["records"]:
            block = [_heading(rec["original_title"], s["h2"], 1, gm)]
            rows = []
            for label, value in fiche_rows(rec):
                rows.append([para(label, "label"), link(value) if value.startswith("http") else para(value, "cell")])
            if rows:
                table = Table(rows, colWidths=[4.6 * cm, 11.9 * cm])
                table.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, -1), SOFT),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2D8CC")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]))
                block.append(table)
            for ed in rec["editorial"]:
                block.append(Spacer(1, 3))
                block.append(Paragraph(f'<font color="#8A2B23"><b>{gm.markup(ed["kind"])} — {gm.markup(ed["origin"])} '
                                       f'({gm.markup(ed["status"])})</b></font> : {gm.markup(ed["content"])}', s["body"]))
            if rec["collection_note"]:
                block.append(para(f"Note de dossier : {rec['collection_note']}"))
            for note in rec["notes"]:
                block.append(para(f"Note ({note['visibility']}) : {note['body']}", "small"))
            block.append(Spacer(1, 6))
            story.append(KeepTogether(block[:2]))
            story.extend(block[2:])

    story += [PageBreak(), _heading("Bibliographie", s["h1"], 0, gm)]
    for rec in doc.records:
        story.append(Paragraph("• " + gm.markup(citation(rec)), s["body"]))

    story.append(_heading("Méthodologie et provenance", s["h1"], 0, gm))
    if doc.methodology:
        story.append(para(doc.methodology))
    story.append(para("Les données originales des catalogues sont reproduites sans réécriture. Les traductions, résumés "
                      "et contenus générés par IA sont signalés comme tels. Les dates de composition et de "
                      "copie/impression sont distinguées."))
    src_rows = [[para("Source", "label"), para("Notices", "label"), para("Dernière vérification", "label")]]
    for src in meta["sources"]:
        src_rows.append([para(src["name"], "cell"), para(str(src["records"]), "cell"),
                         para((src["last_verified"] or "non vérifiée")[:10], "cell")])
    st = Table(src_rows, colWidths=[9 * cm, 2.5 * cm, 5 * cm])
    st.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font), ("BACKGROUND", (0, 0), (-1, 0), SOFT), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8CCBE"))]))
    story.append(st)
    if meta["restrictions"]:
        story.append(para("Restrictions connues :", "h2"))
        for r in meta["restrictions"]:
            story.append(para(f"• {r}"))
    if not embedded:
        story.append(para("Note technique : police CID standard utilisée (non incorporée).", "small"))

    missing_note = Paragraph("", s["small"])
    story.append(missing_note)

    def on_page(canvas, document):
        if document.page == 1:
            return
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(MUTED)
        gm.draw(canvas, A4[0] - 2 * cm, A4[1] - 1.2 * cm, (meta.get("header") or meta["title"])[:110], 7.5, "right")
        canvas.setStrokeColor(SOFT)
        canvas.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
        footer = f"{meta.get('footer') or ''}   {meta['export_id']}"
        gm.draw(canvas, 2 * cm, 1.1 * cm, footer[:130], 7.5)
        canvas.setFont(font, 7.5)
        if opts.get("pagination", True):
            canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"page {document.page}")
        canvas.restoreState()

    path = Path(out_dir) / f"{basename}.pdf"
    pdf = _Doc(str(path), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm,
               bottomMargin=2 * cm, title=meta["title"], author=meta.get("author") or "",
               subject=meta.get("subject") or "", meta=meta, initialFontName=font)
    # Le corps a déjà été balisé ; on ajoute l'en-tête et le pied de page, puis la note explicite.
    gm.runs(meta.get("header") or meta["title"])
    gm.runs(meta.get("footer") or "")
    if gm.missing:
        listing = ", ".join(sorted(gm.missing.values()))
        missing_note.__init__(escape(f"Caractères absents des polices disponibles, remplacés par {REPLACEMENT} : {listing}."),
                              s["small"])
    pdf.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)
    doc.options["_warnings"] = ([f"PDF : {len(gm.missing)} caractère(s) absent(s) des polices, remplacé(s) par "
                                 f"{REPLACEMENT} : " + ", ".join(sorted(gm.missing.values()))]
                                if gm.missing else [])
    return [("main", path)]
