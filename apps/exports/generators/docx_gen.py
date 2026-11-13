"""Export Word (DOCX) : styles, titres hiérarchisés, tableaux, en-têtes/pieds de page paginés, japonais."""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .common import citation, fiche_rows, metadata_lines

ACCENT = RGBColor(0x8A, 0x2B, 0x23)
MUTED = RGBColor(0x55, 0x5B, 0x66)


def _set_fonts(style, latin, east_asian, size=None):
    style.font.name = latin
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attr), latin)
    fonts.set(qn("w:eastAsia"), east_asian)
    if size:
        style.font.size = Pt(size)


def _field(paragraph, instruction, placeholder=""):
    run = paragraph.add_run()
    for tag, attrs in (("w:fldChar", {"w:fldCharType": "begin"}), ("w:instrText", None),
                       ("w:fldChar", {"w:fldCharType": "separate"})):
        el = OxmlElement(tag)
        if attrs:
            for k, v in attrs.items():
                el.set(qn(k), v)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = instruction
        run._r.append(el)
    paragraph.add_run(placeholder)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    paragraph.add_run()._r.append(end)


def _hyperlink(paragraph, url, text):
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                          is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "1F4E79")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(color)
    rpr.append(underline)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _shade(cell, hex_color):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcpr.append(shd)


def generate_docx(doc, out_dir, basename):
    opts = doc.options
    meta = doc.metadata
    east = opts.get("east_asian_font") or "Yu Mincho"
    latin = opts.get("latin_font") or "Cambria"
    d = Document()
    section = d.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21.0)
    section.left_margin = section.right_margin = Cm(2.2)
    section.top_margin = section.bottom_margin = Cm(2.2)

    _set_fonts(d.styles["Normal"], latin, east, 10.5)
    for name, size in (("Title", 26), ("Subtitle", 14), ("Heading 1", 16), ("Heading 2", 12.5), ("Heading 3", 11)):
        _set_fonts(d.styles[name], latin, east, size)
        if name.startswith("Heading") or name == "Title":
            d.styles[name].font.color.rgb = ACCENT
    d.core_properties.title = meta["title"]
    d.core_properties.subject = meta.get("subject") or ""
    d.core_properties.author = meta.get("author") or ""
    d.core_properties.comments = f"Export {meta['export_id']}"

    # Page de titre
    for _ in range(5):
        d.add_paragraph()
    d.add_paragraph(meta["title"], style="Title")
    if meta.get("subtitle"):
        d.add_paragraph(meta["subtitle"], style="Subtitle")
    if meta.get("subject"):
        p = d.add_paragraph(meta["subject"])
        p.runs[0].italic = True
    d.add_paragraph()
    for label, value in metadata_lines(doc):
        p = d.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(f"{label} : ")
        r.bold = True
        r.font.color.rgb = MUTED
        p.add_run(value)
    d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # En-tête et pied de page (toutes pages après la couverture)
    body = d.add_section(WD_SECTION.CONTINUOUS)
    body.different_first_page_header_footer = False
    header_p = body.header.paragraphs[0]
    header_p.text = meta.get("header") or meta["title"]
    header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_p.runs[0].font.size = Pt(8.5)
    header_p.runs[0].font.color.rgb = MUTED
    footer_p = body.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_p.add_run(f"{meta.get('footer') or ''}  —  {meta['export_id']}  —  page ")
    footer_run.font.size = Pt(8.5)
    if opts.get("pagination", True):
        _field(footer_p, "PAGE", "1")

    if opts.get("toc", True):
        d.add_heading("Sommaire", level=1)
        p = d.add_paragraph()
        _field(p, 'TOC \\o "1-2" \\h \\z \\u', "Clic droit → « Mettre à jour les champs » pour afficher le sommaire.")
        d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    if doc.introduction:
        d.add_heading("Introduction", level=1)
        for para in doc.introduction.split("\n"):
            if para.strip():
                d.add_paragraph(para.strip())

    for sec in doc.sections:
        d.add_heading(sec["title"], level=1)
        if sec["description"]:
            d.add_paragraph(sec["description"])
        for rec in sec["records"]:
            d.add_heading(rec["original_title"], level=2)
            rows = fiche_rows(rec)
            table = d.add_table(rows=0, cols=2)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for label, value in rows:
                cells = table.add_row().cells
                cells[0].width, cells[1].width = Cm(5), Cm(11.6)
                cells[0].text = label
                cells[0].paragraphs[0].runs[0].bold = True
                cells[0].paragraphs[0].runs[0].font.size = Pt(9)
                _shade(cells[0], "F4EFE9")
                if value.startswith("http"):
                    _hyperlink(cells[1].paragraphs[0], value, value)
                else:
                    cells[1].text = value
            for ed in rec["editorial"]:
                p = d.add_paragraph()
                r = p.add_run(f"{ed['kind']} — {ed['origin']} ({ed['status']}) : ")
                r.bold = True
                r.font.color.rgb = ACCENT if ed["origin_code"] in ("ai", "mt") else MUTED
                p.add_run(ed["content"])
            if rec["collection_note"]:
                p = d.add_paragraph()
                p.add_run("Note de dossier : ").bold = True
                p.add_run(rec["collection_note"])
            for note in rec["notes"]:
                p = d.add_paragraph()
                p.add_run(f"Note ({note['visibility']}{' — ' + note['locator'] if note['locator'] else ''}) : ").italic = True
                p.add_run(note["body"])

    d.add_heading("Bibliographie", level=1)
    for rec in doc.records:
        d.add_paragraph(citation(rec), style="List Bullet")

    if doc.creators or doc.places:
        d.add_heading("Personnes et lieux", level=1)
        if doc.creators:
            d.add_heading("Auteurs et compilateurs", level=2)
            d.add_paragraph(" ・ ".join(doc.creators))
        if doc.places:
            d.add_heading("Lieux et institutions", level=2)
            d.add_paragraph(" ・ ".join(doc.places))

    d.add_heading("Méthodologie et provenance", level=1)
    if doc.methodology:
        d.add_paragraph(doc.methodology)
    d.add_paragraph("Les données originales des catalogues sont reproduites sans réécriture. Les traductions, "
                    "résumés et contenus générés par IA sont signalés comme tels et ne constituent pas des données "
                    "de catalogue. Les dates de composition et de copie/impression sont distinguées.")
    table = d.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for i, h in enumerate(("Source", "Notices", "Dernière vérification", "Collecte")):
        table.rows[0].cells[i].text = h
        _shade(table.rows[0].cells[i], "EDE6DD")
    for s in meta["sources"]:
        cells = table.add_row().cells
        cells[0].text = s["name"] + (f" (instantané {s['snapshot_date']})" if s.get("is_snapshot") and s.get("snapshot_date") else "")
        cells[1].text = str(s["records"])
        cells[2].text = (s["last_verified"] or "non vérifiée")[:10]
        cells[3].text = f"{(s['collected_from'] or '')[:10]} → {(s['collected_to'] or '')[:10]}"
    if meta["restrictions"]:
        d.add_heading("Restrictions et conditions de réutilisation connues", level=2)
        for r in meta["restrictions"]:
            d.add_paragraph(r, style="List Bullet")

    path = Path(out_dir) / f"{basename}.docx"
    d.save(path)
    return [("main", path)]
