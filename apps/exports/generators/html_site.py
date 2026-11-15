"""
Site documentaire HTML statique et autonome, inspiré de MkDocs Material (§12.8) :
navigation latérale, pages hiérarchisées, fiches, bibliographie, méthodologie,
recherche locale fonctionnant sans serveur (index JavaScript embarqué).
Toutes les ressources (CSS, JS) sont locales ; seuls les liens vers les catalogues
restent des liens Internet.
"""
import json
import zipfile
from html import escape
from pathlib import Path

from .common import citation, fiche_rows, metadata_lines, sha256_file, write_manifest
from .text import json_payload

CSS = """
:root{--accent:#8a2b23;--ink:#1f2328;--muted:#5b6270;--line:#e6ded4;--soft:#f7f3ee;--side:280px}
*{box-sizing:border-box}html{font-size:16px}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic","Noto Sans CJK JP",Meiryo,sans-serif;color:var(--ink);line-height:1.65;background:#fff}
a{color:#1f4e79}a:hover{color:var(--accent)}
header.top{position:sticky;top:0;z-index:5;background:var(--accent);color:#fff;padding:.7rem 1.2rem;display:flex;gap:1rem;align-items:center}
header.top a{color:#fff;text-decoration:none;font-weight:600}header.top .meta{font-size:.78rem;opacity:.85;margin-left:auto;text-align:right}
#menu-toggle{display:none;background:none;border:1px solid #fff6;color:#fff;border-radius:6px;padding:.2rem .6rem}
.layout{display:flex;min-height:calc(100vh - 56px)}
nav.side{width:var(--side);flex:0 0 var(--side);border-right:1px solid var(--line);padding:1.2rem 1rem;background:var(--soft);position:sticky;top:56px;height:calc(100vh - 56px);overflow:auto}
nav.side h2{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:1rem 0 .3rem}
nav.side ul{list-style:none;padding:0;margin:0}nav.side li a{display:block;padding:.25rem .5rem;border-radius:6px;text-decoration:none;color:var(--ink);font-size:.92rem}
nav.side li a.active,nav.side li a:hover{background:#fff;color:var(--accent)}
nav.side input{width:100%;padding:.45rem .6rem;border:1px solid var(--line);border-radius:8px;font-size:.9rem}
main{flex:1;max-width:960px;padding:2rem 2.5rem 4rem}
h1{color:var(--accent);font-size:1.9rem;line-height:1.3;margin-top:0}h2{color:var(--accent);font-size:1.3rem;border-bottom:1px solid var(--line);padding-bottom:.3rem;margin-top:2rem}
.lead{color:var(--muted);font-size:1.05rem}
table.fiche{border-collapse:collapse;width:100%;margin:1rem 0}table.fiche th{width:32%;text-align:left;vertical-align:top;background:var(--soft);font-weight:500;color:var(--muted);font-size:.88rem}
table.fiche th,table.fiche td{padding:.45rem .7rem;border-bottom:1px solid var(--line)}td{word-break:break-word}
.card{border:1px solid var(--line);border-radius:10px;padding:.9rem 1.1rem;margin:.7rem 0;background:#fff}
.card h3{margin:.1rem 0 .3rem;font-size:1.08rem}.card .sub{color:var(--muted);font-size:.88rem}
.badge{display:inline-block;font-size:.72rem;padding:.08rem .45rem;border-radius:999px;background:var(--soft);border:1px solid var(--line);color:var(--muted);margin-right:.25rem}
.badge.ai{background:#fbeaea;border-color:#e9b8b3;color:var(--accent)}
.editorial{border-left:3px solid var(--line);padding:.3rem .8rem;margin:.6rem 0;background:#fcfaf7}.editorial.ai{border-color:var(--accent)}
.meta-table td,.meta-table th{padding:.3rem .6rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
footer.page{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--muted);font-size:.8rem}
.results .card{cursor:pointer}mark{background:#ffe9a8}
@media (max-width:860px){#menu-toggle{display:inline-block}nav.side{position:fixed;left:-100%;top:56px;z-index:4;transition:left .2s;width:85%}nav.side.open{left:0}main{padding:1.2rem}}
@media print{header.top,nav.side{display:none}main{max-width:none}}
"""

SEARCH_JS = """
(function(){
  function norm(s){return (s||'').normalize('NFKC').toLowerCase().replace(/[\\u30a1-\\u30f6]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-0x60)}).replace(/[āâ]/g,'a').replace(/[īî]/g,'i').replace(/[ūû]/g,'u').replace(/[ēê]/g,'e').replace(/[ōô]/g,'o');}
  var input=document.getElementById('q'), out=document.getElementById('results');
  if(!input||!out||!window.SEARCH_INDEX){return;}
  var params=new URLSearchParams(location.search); if(params.get('q')){input.value=params.get('q');}
  function run(){
    var q=norm(input.value).trim(); out.innerHTML='';
    if(!q){return;}
    var words=q.split(/\\s+/), n=0;
    window.SEARCH_INDEX.forEach(function(d){
      var t=norm(d.text); if(words.every(function(w){return t.indexOf(w)>-1;})){
        n++; var a=document.createElement('a'); a.href=d.url; a.className='card'; a.style.display='block'; a.style.textDecoration='none';
        a.innerHTML='<h3></h3><div class="sub"></div>'; a.querySelector('h3').textContent=d.title; a.querySelector('.sub').textContent=d.sub; out.appendChild(a);
      }});
    var p=document.createElement('p'); p.textContent=n+' résultat(s)'; out.prepend(p);
  }
  input.addEventListener('input',run); run();
})();
document.addEventListener('DOMContentLoaded',function(){var b=document.getElementById('menu-toggle'),n=document.querySelector('nav.side');if(b&&n){b.addEventListener('click',function(){n.classList.toggle('open')})}});
"""


def _e(value):
    return escape(str(value or ""))


def _slug(i):
    return f"section-{i + 1}"


class SiteBuilder:
    def __init__(self, doc, root):
        self.doc = doc
        self.root = Path(root)
        self.meta = doc.metadata

    def write(self, rel, title, body, active=""):
        depth = rel.count("/")
        up = "../" * depth
        nav = self._nav(up, active)
        header_meta = f"{_e(self.meta['export_id'])} — {_e(self.meta['generated_at_display'])}"
        html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} — {_e(self.meta['title'])}</title>
<meta name="description" content="{_e(self.meta.get('subject'))}"><meta name="author" content="{_e(self.meta.get('author'))}">
<meta name="generator" content="{_e(self.meta['application'])} {_e(self.meta['application_version'])}">
<meta name="export-id" content="{_e(self.meta['export_id'])}"><meta name="dcterms.created" content="{_e(self.meta['generated_at'])}">
<link rel="stylesheet" href="{up}assets/style.css"></head>
<body><header class="top"><button id="menu-toggle" aria-label="Menu">☰</button><a href="{up}index.html">{_e(self.meta['title'])}</a>
<div class="meta">{_e(self.meta.get('header') or '')}<br>{header_meta}</div></header>
<div class="layout"><nav class="side" aria-label="Navigation">{nav}</nav>
<main>{body}<footer class="page">{_e(self.meta.get('footer') or '')}<br>{_e(self.meta.get('production_line') or '')} — export {_e(self.meta['export_id'])}</footer></main></div>
<script src="{up}assets/search-index.js"></script><script src="{up}assets/search.js"></script></body></html>"""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def _nav(self, up, active):
        def item(href, label, key):
            cls = ' class="active"' if key == active else ""
            return f'<li><a href="{up}{href}"{cls}>{_e(label)}</a></li>'

        parts = [f'<form action="{up}recherche.html"><input name="q" placeholder="Rechercher…" aria-label="Rechercher"></form>',
                 "<h2>Dossier</h2><ul>", item("index.html", "Accueil", "index"), item("contexte.html", "Contexte", "contexte")]
        parts.append("</ul><h2>Sources</h2><ul>")
        for i, sec in enumerate(self.doc.sections):
            parts.append(item(f"sections/{_slug(i)}.html", f"{sec['title']} ({len(sec['records'])})", _slug(i)))
        parts.append("</ul><h2>Outils</h2><ul>")
        parts += [item("personnes-lieux.html", "Personnes et lieux", "pl"), item("bibliographie.html", "Bibliographie", "biblio"),
                  item("methodologie.html", "Méthodologie et provenance", "methodo"), item("recherche.html", "Recherche", "search"),
                  item("donnees/references.json", "Données (JSON)", "data"), "</ul>"]
        return "".join(parts)

    def card(self, rec, up):
        sub = " · ".join(filter(None, [rec.get("reading"), rec.get("creator_original"), rec.get("composition_display"),
                                       rec.get("copy_display"), rec.get("catalogue_name")]))
        badges = ""
        if rec.get("translated_title"):
            ai = rec.get("translated_title_origin") == "ai"
            badges += f'<span class="badge{" ai" if ai else ""}">{"traduction IA" if ai else "traduit"}</span>'
        if rec.get("availability_label"):  # 2.0.0 (lot 2) : trois statuts distincts
            for part in rec["availability_label"].split(" · "):
                badges += f'<span class="badge">{_e(part)}</span>'
        elif rec.get("digital_access_label"):  # export antérieur à la 2.0.0
            badges += f'<span class="badge">{_e(rec["digital_access_label"])}</span>'
        trans = f'<div>{_e(rec["translated_title"])}</div>' if rec.get("translated_title") else ""
        return (f'<div class="card"><h3><a href="{up}fiches/{_e(rec["record_id"])}.html">{_e(rec["original_title"])}</a></h3>'
                f'{trans}<div class="sub">{_e(sub)}</div>{badges}</div>')

    def build(self):
        doc, meta = self.doc, self.meta
        (self.root / "assets").mkdir(parents=True, exist_ok=True)
        (self.root / "assets" / "style.css").write_text(CSS, encoding="utf-8")
        (self.root / "assets" / "search.js").write_text(SEARCH_JS, encoding="utf-8")

        stats = "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in metadata_lines(doc))
        sections = "".join(f'<li><a href="sections/{_slug(i)}.html">{_e(s["title"])}</a> — {len(s["records"])} référence(s)</li>'
                           for i, s in enumerate(doc.sections))
        self.write("index.html", "Accueil", f"""<h1>{_e(meta['title'])}</h1>
<p class="lead">{_e(meta.get('subtitle'))}</p><p>{_e(meta.get('subject'))}</p>
<h2>Sommaire</h2><ul>{sections}<li><a href="bibliographie.html">Bibliographie</a></li><li><a href="methodologie.html">Méthodologie et provenance</a></li></ul>
<h2>Informations sur l'export</h2><table class="meta-table">{stats}</table>""", "index")

        intro = "".join(f"<p>{_e(p)}</p>" for p in (doc.introduction or "").split("\n") if p.strip())
        overview = "".join(f'<h2>{_e(s["title"])}</h2><p>{_e(s["description"])}</p>' for s in doc.sections)
        self.write("contexte.html", "Contexte", f"<h1>Contexte</h1>{intro or '<p>—</p>'}{overview}", "contexte")

        for i, sec in enumerate(doc.sections):
            cards = "".join(self.card(r, "../") for r in sec["records"]) or "<p>Aucune référence.</p>"
            self.write(f"sections/{_slug(i)}.html", sec["title"],
                       f"<h1>{_e(sec['title'])}</h1><p>{_e(sec['description'])}</p>{cards}", _slug(i))

        for rec in doc.records:
            rows = ""
            for label, value in fiche_rows(rec):
                cell = f'<a href="{_e(value)}" rel="noopener">{_e(value)}</a>' if value.startswith("http") else _e(value).replace("\n", "<br>")
                rows += f"<tr><th>{_e(label)}</th><td>{cell}</td></tr>"
            extras = ""
            for ed in rec["editorial"]:
                ai = ed["origin_code"] in ("ai", "mt")  # contenu généré : IA ou traduction automatique
                extras += (f'<div class="editorial{" ai" if ai else ""}"><span class="badge{" ai" if ai else ""}">{_e(ed["kind"])} — '
                           f'{_e(ed["origin"])}</span> <small>{_e(ed["status"])}</small><div>{_e(ed["content"])}</div></div>')
            if rec["collection_note"]:
                extras += f'<div class="editorial"><span class="badge">Note de dossier</span><div>{_e(rec["collection_note"])}</div></div>'
            for note in rec["notes"]:
                extras += f'<div class="editorial"><span class="badge">{_e(note["visibility"])}</span> <small>{_e(note["locator"])}</small><div>{_e(note["body"])}</div></div>'
            self.write(f"fiches/{rec['record_id']}.html", rec["original_title"],
                       f"<h1>{_e(rec['original_title'])}</h1><p class='lead'>{_e(rec.get('reading'))}</p>"
                       f"<table class='fiche'>{rows}</table>{extras}")

        creators = "".join(f"<li>{_e(c)}</li>" for c in doc.creators) or "<li>—</li>"
        places = "".join(f"<li>{_e(p)}</li>" for p in doc.places) or "<li>—</li>"
        self.write("personnes-lieux.html", "Personnes et lieux",
                   f"<h1>Personnes et lieux</h1><h2>Auteurs et compilateurs</h2><ul>{creators}</ul>"
                   f"<h2>Lieux et institutions</h2><ul>{places}</ul>", "pl")

        biblio = "".join(f'<li><a href="fiches/{_e(r["record_id"])}.html">{_e(citation(r))}</a></li>' for r in doc.records)
        self.write("bibliographie.html", "Bibliographie", f"<h1>Bibliographie</h1><ol>{biblio}</ol>", "biblio")

        src_rows = "".join(
            f"<tr><td>{_e(s['name'])}{' (instantané ' + _e(s['snapshot_date']) + ')' if s.get('is_snapshot') and s.get('snapshot_date') else ''}</td>"
            f"<td>{s['records']}</td><td>{_e((s['last_verified'] or 'non vérifiée')[:10])}</td>"
            f"<td>{_e((s['collected_from'] or '')[:10])} → {_e((s['collected_to'] or '')[:10])}</td></tr>" for s in meta["sources"])
        restr = "".join(f"<li>{_e(r)}</li>" for r in meta["restrictions"]) or "<li>Aucune restriction renseignée.</li>"
        self.write("methodologie.html", "Méthodologie et provenance", f"""<h1>Méthodologie et provenance</h1>
<p>{_e(doc.methodology)}</p>
<p>Les données originales des catalogues sont reproduites sans réécriture. Les traductions, résumés et contenus générés par IA
sont signalés comme tels et ne constituent pas des données de catalogue. Les dates de composition des œuvres et de
copie/impression des exemplaires sont distinguées.</p>
<h2>Sources</h2><table class="meta-table"><tr><th>Source</th><th>Notices</th><th>Dernière vérification</th><th>Collecte</th></tr>{src_rows}</table>
<h2>Restrictions et conditions de réutilisation</h2><ul>{restr}</ul>
<h2>Métadonnées</h2><table class="meta-table">{stats}</table>""", "methodo")

        self.write("recherche.html", "Recherche", '<h1>Recherche</h1><p><input id="q" placeholder="Titre, auteur, lecture, rōmaji…" '
                   'style="width:100%;padding:.6rem;border:1px solid #e6ded4;border-radius:8px"></p><div id="results" class="results"></div>',
                   "search")

        index = [{"url": f"fiches/{r['record_id']}.html", "title": r["original_title"],
                  "sub": " · ".join(filter(None, [r.get("reading"), r.get("creator_original"), r.get("catalogue_name")])),
                  "text": " ".join(str(r.get(k) or "") for k in ("original_title", "reading", "title_romaji", "translated_title",
                                                                 "creator_original", "creator_reading", "description_original",
                                                                 "holding_institution_text", "subjects_original", "source_id"))}
                 for r in doc.records]
        # Index JavaScript (et non JSON chargé par fetch) : fonctionne en ouverture locale file://
        (self.root / "assets" / "search-index.js").write_text(
            "window.SEARCH_INDEX=" + json.dumps(index, ensure_ascii=False) + ";\n"
            "if(document.currentScript){var d=document.currentScript.src.replace(/assets\\/search-index\\.js.*$/,'');"
            "window.SEARCH_INDEX.forEach(function(x){x.url=d+x.url;});}", encoding="utf-8")
        (self.root / "donnees").mkdir(exist_ok=True)
        (self.root / "donnees" / "references.json").write_text(
            json.dumps(json_payload(doc), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return self.root


def zip_dir(src, zip_path, prefix):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(Path(src).rglob("*")):
            if path.is_file():
                zf.write(path, f"{prefix}/{path.relative_to(src).as_posix()}")
    return zip_path


def generate_html(doc, out_dir, basename, extra_generators=()):
    out_dir = Path(out_dir)
    site = out_dir / "site"
    SiteBuilder(doc, site).build()
    files = [("main", (p, p.relative_to(site).as_posix())) for p in sorted(site.rglob("*")) if p.is_file()]
    for gen in extra_generators:
        for role, path in gen(doc, site / "donnees", basename):
            files.append((role, (path, path.relative_to(site).as_posix())))
    manifest_path = site / "manifest.json"
    write_manifest(manifest_path, doc, files, extra={"entry_point": "index.html",
                                                     "note": "Ouvrir index.html dans un navigateur ; aucun serveur requis."})
    zip_path = out_dir / f"{basename}.zip"
    zip_dir(site, zip_path, basename)
    manifest_copy = out_dir / f"{basename}.manifest.json"
    manifest_copy.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
    return [("main", zip_path), ("manifest", manifest_copy)]


def generate_zip(doc, out_dir, basename):
    from .text import generate_csv, generate_json, generate_txt

    return generate_html(doc, out_dir, basename, extra_generators=(generate_json, generate_csv, generate_txt))


__all__ = ["generate_html", "generate_zip", "sha256_file"]
