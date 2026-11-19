"""Pages d'aide : fichiers Markdown de ``docs/aide/``, lus au démarrage puis relus s'ils changent.

En-tête de chaque fichier (entre deux lignes ``---``) :

    titre: Traduire une notice
    rubrique: Traduire et résumer
    ordre: 30
    public: tous | editeur | admin
    ecrans: translation:records_prepare, translation:record_translations
    resume: Une phrase qui présente la page.
    reprend: historique-des-versions   (facultatif : ajoute la première section « ## » de cette page)

Liens internes dans le texte : ``[texte](aide:autre-page)``, ``[texte](aide:autre-page#ancre)`` vers une autre
page d'aide, ``[texte](ecran:translation:engines)`` vers un écran de J-ed. Les liens cassés sont détectés par les
tests. Le HTML écrit dans les fichiers n'est jamais interprété : il est affiché comme du texte.
"""
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

import markdown
from django.conf import settings
from django.urls import NoReverseMatch, reverse
from markdown.treeprocessors import Treeprocessor

HELP_DIR = Path(settings.BASE_DIR) / "docs" / "aide"
AUDIENCES = ("tous", "editeur", "admin")
#: Rubriques de l'index, dans l'ordre d'affichage.
SECTIONS = ("Premiers pas", "Chercher et lire", "Bibliothèque et exports", "Traduire et résumer",
            "Administration", "Installation et mises à jour", "Référence")


@dataclass
class Page:
    slug: str
    title: str
    section: str
    order: int
    audience: str
    screens: list
    summary: str
    body: str
    mtime: float
    takes: str = ""
    html: str = ""
    headings: list = field(default_factory=list)
    links: list = field(default_factory=list)

    def visible_to(self, user):
        if self.audience == "tous":
            return True
        if not getattr(user, "is_authenticated", False):
            return False
        if self.audience == "editeur":
            return bool(getattr(user, "can_edit", False))
        return bool(getattr(user, "is_admin_role", False))


class HelpLinks(Treeprocessor):
    """Liens « aide: » et « ecran: » résolus ; liens externes ouverts à part ; liens non sûrs neutralisés."""

    def run(self, root):
        found = []
        for a in root.iter("a"):
            href = a.get("href", "")
            target, ok = resolve_link(href)
            found.append((href, ok))
            a.set("href", target if ok else "#lien-introuvable")
            if href.startswith(("http://", "https://")):
                a.set("rel", "noopener noreferrer")
                a.set("target", "_blank")
        for img in list(root.iter("img")):  # pas d'image distante dans l'aide
            if not img.get("src", "").startswith("/static/"):
                img.set("src", "")
        self.md.help_links = found


def resolve_link(href):
    """(adresse, valide) pour un lien écrit dans une page d'aide."""
    if href.startswith("aide:"):
        slug, _, anchor = href[5:].partition("#")
        if slug not in registry().pages:
            return href, False
        return reverse("help:page", args=[slug]) + (f"#{anchor}" if anchor else ""), True
    if href.startswith("ecran:"):
        try:
            return reverse(href[6:]), True
        except NoReverseMatch:
            return href, False
    if href.startswith(("http://", "https://", "#", "/", "mailto:")):
        return href, True
    return href, False


def _md():
    md = markdown.Markdown(extensions=["tables", "sane_lists", "toc"],
                           extension_configs={"toc": {"permalink": False, "toc_depth": "2-3"}})
    # HTML brut jamais interprété (le Markdown standard le laisse passer) : il est affiché comme du texte.
    md.preprocessors.deregister("html_block")
    md.inlinePatterns.deregister("html")
    md.treeprocessors.register(HelpLinks(md), "help_links", 1)
    return md


def parse_file(path):
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    if text.startswith("---\n"):
        head, sep, rest = text[4:].partition("\n---\n")
        if sep:
            body = rest
            for line in head.splitlines():
                key, _, value = line.partition(":")
                if key.strip():
                    meta[key.strip()] = value.strip().strip("\"")
    audience = meta.get("public", "tous")
    if audience not in AUDIENCES:
        raise ValueError(f"{path.name} : public inconnu « {audience} »")
    return Page(slug=path.stem, title=meta.get("titre") or path.stem, section=meta.get("rubrique", "Référence"),
                order=int(meta.get("ordre", "100")), audience=audience,
                screens=[s.strip() for s in meta.get("ecrans", "").split(",") if s.strip()],
                summary=meta.get("resume", ""), body=body, mtime=path.stat().st_mtime, takes=meta.get("reprend", ""))


class Registry:
    def __init__(self, directory):
        self.directory, self.pages, self.by_screen, self.stamp = directory, {}, {}, None

    def _stamp(self):
        files = sorted(self.directory.glob("*.md"))
        return tuple((f.name, f.stat().st_mtime) for f in files)

    def load(self):
        pages = {}
        for path in sorted(self.directory.glob("*.md")):
            page = parse_file(path)
            pages[page.slug] = page
        self.pages = pages
        by_screen = {}
        for page in pages.values():
            for screen in page.screens:
                by_screen.setdefault(screen, page.slug)
        self.by_screen = by_screen
        for page in pages.values():  # « reprend: autre-page » : ajoute la première section « ## » de l'autre page
            source = pages.get(page.takes)
            if source is not None:
                page.body = page.body.rstrip() + "\n\n" + latest_section(source.body)
        for page in pages.values():  # rendu après chargement : les liens « aide: » visent toutes les pages
            md = _md()
            page.html = md.convert(page.body)
            page.links = getattr(md, "help_links", [])
            page.headings = [(t["id"], t["name"]) for t in _flat(md.toc_tokens)]
        self.stamp = self._stamp()
        return self

    def fresh(self):
        if self.stamp != self._stamp():
            self.load()
        return self


def latest_section(body):
    """Première section de niveau 2 (la version la plus récente de l'historique)."""
    parts = re.split(r"(?m)^(?=## )", body)
    sections = [s for s in parts if s.startswith("## ")]
    return sections[0].rstrip() + "\n" if sections else ""


def _flat(tokens):
    for t in tokens:
        yield t
        yield from _flat(t.get("children", []))


_lock = threading.RLock()  # réentrant : le rendu d'une page résout ses liens par le registre
_registry = None


def registry():
    global _registry
    with _lock:
        if _registry is None:
            _registry = Registry(HELP_DIR)
            _registry.load()  # les pages se référencent entre elles : d'abord toutes lues
        return _registry


def fresh_registry():
    reg = registry()
    with _lock:
        return reg.fresh()


def visible_pages(user):
    pages = [p for p in fresh_registry().pages.values() if p.visible_to(user)]
    return sorted(pages, key=lambda p: (SECTIONS.index(p.section) if p.section in SECTIONS else 99, p.order, p.title))


def page_for_screen(view_name):
    return fresh_registry().by_screen.get(view_name or "")


# --------------------------------------------------------------------------- recherche


def fold(text):
    """Minuscules sans accents (les kanji et kana restent tels quels)."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def plain(html):
    try:
        return "".join(ElementTree.fromstring(f"<div>{html}</div>").itertext())
    except ElementTree.ParseError:
        return re.sub(r"<[^>]+>", " ", html)


def search(user, query, limit=20):
    words = [w for w in fold(query).split() if len(w) > 1 or not w.isascii()]
    if not words:
        return []
    hits = []
    for page in visible_pages(user):
        text = plain(page.html)
        title, body = fold(page.title), fold(text)
        if not all(w in title or w in body for w in words):
            continue
        score = sum(5 * title.count(w) + body.count(w) for w in words)
        first = min((body.find(w) for w in words if w in body), default=0)
        start = max(0, first - 80)
        excerpt = " ".join(text[start:start + 220].split())
        hits.append((score, page, ("… " if start else "") + excerpt + " …"))
    hits.sort(key=lambda h: (-h[0], h[1].title))
    return [(page, excerpt) for _, page, excerpt in hits[:limit]]
