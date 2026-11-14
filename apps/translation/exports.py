"""
Exports du module de traduction (plan 1.3.0, lot 8 ; décisions A4 et E4, cahier des charges § 18).

Formats : texte bilingue (.txt, Markdown), tableau bilingue (CSV), traduction seule (.txt, Markdown) et
Word bilingue en tableau à deux colonnes (.docx). Les glossaires s'exportent en CSV (glossary.export_csv).

Deux modes :
- « validated » : versions validées seulement ; un segment sans version validée apparaît « non traduit » ;
- « fallback » : version validée, à défaut la dernière proposition (jamais une version rejetée),
  alors signalée « non validée ».
Toute traduction produite par un moteur simulé porte la mention « Simulation » (décision du 13/11/2026).

Les exports sont produits à la demande, sans fichier conservé sur le serveur, et réservés au propriétaire
du projet (décision E4). L'original n'est jamais modifié : il est lu tel qu'importé (segments).
"""
import csv
import io
from collections import Counter
from dataclasses import dataclass, field

from django.conf import settings
from django.utils import timezone

from apps.ai.models import PROVIDERS as AI_PROVIDERS

from .glossary import protect_cell as _cell
from .models import ENGINES
from .segmentation import is_translatable

FORMATS = {
    "bilingual_txt": ("Texte bilingue (.txt)", "txt", "text/plain; charset=utf-8"),
    "bilingual_md": ("Texte bilingue (Markdown)", "md", "text/markdown; charset=utf-8"),
    "table_csv": ("Tableau bilingue (CSV)", "csv", "text/csv; charset=utf-8"),
    "translation_txt": ("Traduction seule (.txt)", "txt", "text/plain; charset=utf-8"),
    "translation_md": ("Traduction seule (Markdown)", "md", "text/markdown; charset=utf-8"),
    "bilingual_docx": ("Word bilingue en tableau (.docx)", "docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}
MODES = {
    "validated": "Versions validées seulement",
    "fallback": "Versions validées, à défaut dernière proposition (signalée « non validée »)",
}
STATUS_LABELS = {"validated": "validée", "proposed": "non validée", "untranslated": "non traduit", "blank": "—"}
CSV_COLUMNS = ["identifiant", "document", "chapitre", "position", "original", "traduction", "statut", "simulation",
               "moteur", "origine", "validée par", "validée le", "alertes"]


class ExportError(Exception):
    pass


@dataclass
class Row:
    segment: object
    document: object
    chapter: str
    version: object = None
    status: str = "untranslated"  # validated, proposed, untranslated, blank (rien à traduire)

    @property
    def source(self):
        return self.segment.source_text

    @property
    def text(self):
        return self.version.text if self.version else ""

    @property
    def simulated(self):
        return bool(self.version and self.version.simulated)

    @property
    def source_changed(self):
        return bool(self.version and self.version.source_text != self.segment.source_text)

    @property
    def marks(self):
        """Mentions jointes à la traduction (statut, simulation, original différent)."""
        out = []
        if self.status == "proposed":
            out.append("non validée")
        if self.simulated:
            out.append("Simulation")
        if self.source_changed:
            out.append("traduite d'un original différent")
        return out

    @property
    def identifier(self):
        return f"D{self.document.order or self.document.pk}-S{self.segment.position}"


@dataclass
class ExportData:
    project: object
    documents: list
    mode: str
    rows: list = field(default_factory=list)
    generated_at: object = None

    @property
    def translatable(self):
        return [r for r in self.rows if r.status != "blank"]

    def count(self, status):
        return sum(1 for r in self.rows if r.status == status)

    # raccourcis pour les gabarits
    count_validated = property(lambda self: self.count("validated"))
    count_proposed = property(lambda self: self.count("proposed"))
    count_untranslated = property(lambda self: self.count("untranslated"))

    @property
    def validated_share(self):
        n = len(self.translatable)
        return (self.count("validated") / n) if n else 0.0

    @property
    def simulated_count(self):
        return sum(1 for r in self.rows if r.simulated)

    def engines_used(self):
        return Counter(engine_label(r.version) for r in self.rows if r.version).most_common()

    @property
    def title(self):
        if len(self.documents) == 1:
            return f"{self.project.title} — {self.documents[0].title}"
        return self.project.title


def engine_label(version):
    if version is None:
        return ""
    if version.origin in ("human", "human_edit") and not version.engine:
        return "Saisie humaine"
    if version.engine == "ai":
        provider = dict(AI_PROVIDERS).get(version.ai_provider, version.ai_provider)
        base = f"{provider} — {version.model}" if version.model else provider
    else:
        base = dict(ENGINES).get(version.engine, version.engine or "—")
    if version.origin == "human_edit":
        base += " (modifiée à la main)"
    return base


def collect(project, *, document=None, mode="validated"):
    """Rassemble les segments à exporter. `document` : un seul document du projet (sinon tous)."""
    if mode not in MODES:
        raise ExportError("Mode d'export inconnu.")
    documents = [document] if document is not None else list(project.documents.order_by("order", "pk"))
    data = ExportData(project=project, documents=documents, mode=mode, generated_at=timezone.now())
    for doc in documents:
        segments = (doc.segments.order_by("position").select_related("chapter")
                    .prefetch_related("versions__decided_by"))
        for segment in segments:
            row = Row(segment=segment, document=doc, chapter=segment.chapter.title if segment.chapter_id else "")
            if not is_translatable(segment.source_text):
                row.status = "blank"
            else:
                versions = list(segment.versions.all())
                validated = next((v for v in versions if v.status == "validated"), None)
                if validated is not None:
                    row.version, row.status = validated, "validated"
                elif mode == "fallback":
                    proposals = [v for v in versions if v.status == "proposed"]
                    if proposals:
                        row.version, row.status = max(proposals, key=lambda v: v.created_at), "proposed"
            data.rows.append(row)
    return data


# --------------------------------------------------------------------------- en-tête commun


def header_lines(data):
    p = data.project
    n = len(data.translatable)
    lines = [
        ("Projet", p.title),
        ("Documents", ", ".join(d.title for d in data.documents) or "aucun"),
        ("Langues", f"{p.get_source_lang_display()} → {p.get_target_lang_display()}"),
        ("Exporté le", timezone.localtime(data.generated_at).strftime("%d/%m/%Y %H:%M")),
        ("Application", f"Japon — Explorateur documentaire {settings.APP_VERSION}"),
        ("Contenu", MODES[data.mode]),
        ("Segments validés", f"{data.count('validated')} sur {n} ({data.validated_share * 100:.0f} %)"),
    ]
    if data.mode == "fallback":
        lines.append(("Non validés (propositions)", str(data.count("proposed"))))
    lines.append(("Non traduits", str(data.count("untranslated"))))
    engines = data.engines_used()
    lines.append(("Moteurs utilisés", " ; ".join(f"{name} ({count})" for name, count in engines) or "aucun"))
    if data.simulated_count:
        lines.append(("Simulation", f"{data.simulated_count} traduction(s) produite(s) par un moteur SIMULÉ : "
                                    "aucune traduction réelle"))
    if p.confidential:
        lines.append(("Confidentialité", "projet confidentiel — diffusion à maîtriser"))
    return lines


def _untranslated(row):
    return f"[non traduit — segment {row.segment.position}]"


def _separator(row):
    """Séparateur après un segment : sauts de ligne de l'original conservés, sinon une espace."""
    trailing = row.source[len(row.source.rstrip()):]
    newlines = trailing.replace("\r\n", "\n").count("\n")
    return "\n" * newlines if newlines else " "


# --------------------------------------------------------------------------- texte et Markdown


def bilingual_txt(data):
    out = [data.title, "=" * min(len(data.title), 80)]
    out += [f"{label} : {value}" for label, value in header_lines(data)]
    current = (None, None)
    for row in data.rows:
        if row.status == "blank":
            continue
        if (row.document.pk, row.chapter) != current:
            if len(data.documents) > 1 and row.document.pk != current[0]:
                out += ["", f"=== {row.document.title} ==="]
            if row.chapter:
                out += ["", f"--- {row.chapter} ---"]
            current = (row.document.pk, row.chapter)
        out += ["", f"[{row.segment.position}] {row.source.strip()}"]
        if row.version:
            marks = f" [{', '.join(row.marks)}]" if row.marks else ""
            out.append(f"    → {row.text.strip()}{marks}")
        else:
            out.append(f"    → {_untranslated(row)}")
    return "\n".join(out) + "\n"


def _md_escape(text):
    return text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("#", "\\#")


def _md_quote(text):
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().splitlines())


def bilingual_md(data):
    out = [f"# {_md_escape(data.title)}", ""]
    out += [f"- **{label}** : {_md_escape(value)}" for label, value in header_lines(data)]
    current = (None, None)
    for row in data.rows:
        if row.status == "blank":
            continue
        if (row.document.pk, row.chapter) != current:
            if len(data.documents) > 1 and row.document.pk != current[0]:
                out += ["", f"## {_md_escape(row.document.title)}"]
            if row.chapter:
                out += ["", f"### {_md_escape(row.chapter)}"]
            current = (row.document.pk, row.chapter)
        out += ["", f"**{row.segment.position}.**", "", _md_quote(_md_escape(row.source)), ""]
        if row.version:
            marks = f" *({', '.join(row.marks)})*" if row.marks else ""
            out.append(_md_escape(row.text.strip()) + marks)
        else:
            out.append(f"*{_untranslated(row)}*")
    return "\n".join(out) + "\n"


def _heading(parts, line):
    """Titre précédé et suivi d'une seule ligne vide, quels que soient les sauts de ligne qui précèdent."""
    if parts:
        parts[-1] = parts[-1].rstrip()
        parts.append("\n\n")
    parts.append(line + "\n\n")


def _translation_body(data, *, markdown):
    parts, chapter, document = [], None, None
    esc = _md_escape if markdown else (lambda x: x)
    for row in data.rows:
        if len(data.documents) > 1 and row.document.pk != document:
            title = esc(row.document.title)
            _heading(parts, ("## " + title) if markdown else f"=== {title} ===")
            document = row.document.pk
        if row.chapter and row.chapter != chapter:
            _heading(parts, ("### " + esc(row.chapter)) if markdown else f"--- {row.chapter} ---")
        chapter = row.chapter
        if row.status == "blank":
            parts.append(row.source)
            continue
        if row.version:
            mark = ""
            if row.status == "proposed":
                mark += "[*]"
            if row.simulated:
                mark += "[S]"
            parts.append(esc(row.text.strip()) + (f" {mark}" if mark else "") + _separator(row))
        else:
            parts.append(_untranslated(row) + _separator(row))
    return "".join(parts).strip()


def _legend(data):
    legend = []
    if data.count("proposed"):
        legend.append("[*] traduction non validée (dernière proposition)")
    if data.simulated_count:
        legend.append("[S] Simulation : traduction produite par un moteur simulé, aucune traduction réelle")
    return legend


def translation_txt(data):
    out = [data.title, "=" * min(len(data.title), 80)]
    out += [f"{label} : {value}" for label, value in header_lines(data)]
    out += [f"Légende : {item}" for item in _legend(data)]
    out += ["", "-" * 40, "", _translation_body(data, markdown=False)]
    return "\n".join(out) + "\n"


def translation_md(data):
    out = [f"# {_md_escape(data.title)}", ""]
    out += [f"- **{label}** : {_md_escape(value)}" for label, value in header_lines(data)]
    out += [f"- *Légende* : {item}" for item in _legend(data)]
    out += ["", "---", "", _translation_body(data, markdown=True)]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- CSV


def table_csv(data):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in data.rows:
        if row.status == "blank":
            continue
        v = row.version
        writer.writerow([_cell(x) for x in (
            row.identifier, row.document.title, row.chapter, str(row.segment.position), row.source.strip(),
            row.text.strip(), STATUS_LABELS[row.status], "oui" if row.simulated else "", engine_label(v),
            v.get_origin_display() if v else "", str(v.decided_by or "") if v and v.status == "validated" else "",
            timezone.localtime(v.decided_at).strftime("%d/%m/%Y") if v and v.decided_at and v.status == "validated" else "",
            " | ".join(list(v.alerts or []) + (["traduite d'un original différent"] if row.source_changed else []))
            if v else "")])
    return "﻿" + buffer.getvalue()


# --------------------------------------------------------------------------- Word


def bilingual_docx(data):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.shared import Cm, Pt, RGBColor

    from apps.exports.generators.docx_gen import set_fonts

    muted, warn = RGBColor(0x55, 0x5B, 0x66), RGBColor(0x9A, 0x5B, 0x00)
    latin, east = "Cambria", "Yu Mincho"
    d = Document()
    section = d.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21.0)
    section.left_margin = section.right_margin = Cm(1.8)
    set_fonts(d.styles["Normal"], latin, east, 10.5)
    for name in ("Title", "Heading 1", "Heading 2"):
        set_fonts(d.styles[name], latin, east)
    d.core_properties.title = data.title
    d.core_properties.comments = f"Export du module de traduction — {settings.APP_VERSION}"
    d.add_paragraph(data.title, style="Title")
    for label, value in header_lines(data):
        p = d.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(f"{label} : ")
        r.bold = True
        r.font.color.rgb = muted
        p.add_run(value)

    table, current = None, (None, None)
    source_label, target_label = data.project.get_source_lang_display(), data.project.get_target_lang_display()
    for row in data.rows:
        if row.status == "blank":
            continue
        if table is None or (row.document.pk, row.chapter) != current:
            if len(data.documents) > 1 and row.document.pk != current[0]:
                d.add_heading(row.document.title, level=1)
            if row.chapter:
                d.add_heading(row.chapter, level=2)
            current = (row.document.pk, row.chapter)
            table = d.add_table(rows=1, cols=2)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for cell, label in zip(table.rows[0].cells, (source_label, target_label)):
                cell.text = ""
                cell.paragraphs[0].add_run(label).bold = True
        cells = table.add_row().cells
        cells[0].text = ""
        number = cells[0].paragraphs[0].add_run(f"{row.segment.position}. ")
        number.font.color.rgb = muted
        number.font.size = Pt(8)
        cells[0].paragraphs[0].add_run(row.source.strip())
        cells[1].text = ""
        if row.version:
            cells[1].paragraphs[0].add_run(row.text.strip())
            if row.marks:
                note = cells[1].add_paragraph().add_run(" · ".join(row.marks))
                note.italic, note.font.size, note.font.color.rgb = True, Pt(8), warn
        else:
            empty = cells[1].paragraphs[0].add_run(_untranslated(row))
            empty.italic, empty.font.color.rgb = True, muted
    if table is None:
        d.add_paragraph("Aucun segment à exporter.")
    buffer = io.BytesIO()
    d.save(buffer)
    return buffer.getvalue()


GENERATORS = {"bilingual_txt": bilingual_txt, "bilingual_md": bilingual_md, "table_csv": table_csv,
              "translation_txt": translation_txt, "translation_md": translation_md, "bilingual_docx": bilingual_docx}


def render(project, fmt, *, document=None, mode="validated"):
    """Retourne (contenu, type MIME, extension, données collectées)."""
    if fmt not in FORMATS:
        raise ExportError("Format d'export inconnu.")
    data = collect(project, document=document, mode=mode)
    content = GENERATORS[fmt](data)
    if isinstance(content, str):
        content = content.encode("utf-8")
    _, ext, mime = FORMATS[fmt]
    return content, mime, ext, data
