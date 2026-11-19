"""Guide d'utilisation tiré de l'aide intégrée : une seule source (docs/aide), pas de double rédaction.

Les pages sont mises bout à bout dans l'ordre de l'index (rubriques, puis ordre). Les liens « aide:page » deviennent
des liens internes au document, les liens « ecran: » le nom de l'écran (le guide se lit sans J-ed).
"""
import re
from datetime import date

from django.conf import settings
from django.utils.html import escape

from . import pages as P


class _Everyone:
    is_authenticated = True
    can_edit = True
    is_admin_role = True


def ordered_pages():
    return P.visible_pages(_Everyone())


def _rewrite(html):
    def repl(match):
        href = match.group(1)
        if href.startswith("/aide/"):
            slug, _, anchor = href[len("/aide/"):].partition("/")
            anchor = anchor.lstrip("#")
            return f'href="#{slug}{"--" + anchor if anchor else ""}"'
        if href.startswith("/"):
            return 'href="#" data-ecran="1"'
        return match.group(0)

    html = re.sub(r'href="([^"]+)"', repl, html)
    return re.sub(r'<a href="#" data-ecran="1"[^>]*>(.*?)</a>', r"<em>\1</em>", html)


def build_html():
    reg = P.fresh_registry()
    pages = ordered_pages()
    toc, body, section = [], [], None
    for page in pages:
        if page.section != section:
            section = page.section
            toc.append(f"<li class='rubrique'>{escape(section)}</li>")
            body.append(f"<h1 class='rubrique'>{escape(section)}</h1>")
        badge = " <span class='badge'>administrateur</span>" if page.audience == "admin" else ""
        toc.append(f"<li><a href='#{page.slug}'>{escape(page.title)}</a>{badge}</li>")
        html = _rewrite(page.html)
        # les sections d'une page passent sous son titre : h2 → h3, h3 → h4
        html = re.sub(r"<(/?)h([23])\b", lambda m: f"<{m.group(1)}h{int(m.group(2)) + 1}", html)
        html = re.sub(r'id="([^"]+)"', lambda m: f'id="{page.slug}--{m.group(1)}"', html)
        body.append(f"<section id='{page.slug}'><h2>{escape(page.title)}{badge}</h2>"
                    f"{'<p class=lead>' + escape(page.summary) + '</p>' if page.summary else ''}{html}</section>")
    version = getattr(settings, "APP_VERSION", "")
    css = """body{font-family:system-ui,'Segoe UI',sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;line-height:1.55;color:#222}
h1.rubrique{color:#8a2b23;border-bottom:2px solid #8a2b23;padding-bottom:.2rem;margin-top:3rem;page-break-before:always}
h2{margin-top:2.2rem}h3{margin-top:1.4rem}table{border-collapse:collapse;width:100%;margin:.6rem 0}
th,td{border:1px solid #ddd;padding:.3rem .5rem;vertical-align:top;text-align:left}code{background:#f4f4f4;padding:0 .2rem}
pre{background:#f4f4f4;padding:.6rem;overflow:auto}.lead{font-size:1.1rem;color:#555}.badge{font-size:.7rem;background:#666;color:#fff;
padding:.1rem .35rem;border-radius:.3rem;vertical-align:middle}li.rubrique{font-weight:600;margin-top:.6rem;list-style:none}
.couverture{text-align:center;margin:3rem 0}.couverture img{height:120px}@media print{a{color:inherit}}"""
    logo = (settings.BASE_DIR / "static" / "img" / "logo-j-ed-grand.png")
    logo_tag = ""
    if logo.is_file():
        import base64

        logo_tag = f"<img alt='J-ed' src='data:image/png;base64,{base64.b64encode(logo.read_bytes()).decode()}'>"
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>J-ed — Guide d'utilisation</title>
<style>{css}</style></head><body>
<div class="couverture">{logo_tag}<h1>Guide d'utilisation et de réglages</h1><p>J-ed {escape(version)} · {date.today():%d/%m/%Y}</p>
<p>Ce guide reprend l'aide intégrée de J-ed (menu à votre nom → Aide). Il est produit à partir des mêmes pages.</p></div>
<h2>Sommaire</h2><ul>{''.join(toc)}</ul>
{''.join(body)}
</body></html>"""


def build_markdown():
    pages = ordered_pages()
    out, section = [f"# J-ed — Guide d'utilisation et de réglages\n\nJ-ed {getattr(settings, 'APP_VERSION', '')}. "
                    "Ce guide reprend l'aide intégrée (menu à votre nom → Aide).\n"], None
    for page in pages:
        if page.section != section:
            section = page.section
            out.append(f"\n# {section}\n")
        body = re.sub(r"(?m)^(#{2,5}) ", lambda m: "#" + m.group(1) + " ", page.body)
        body = re.sub(r"\]\(aide:([a-z0-9-]+)(#[^)]*)?\)", r"](#\1)", body)
        body = re.sub(r"\]\(ecran:[^)]*\)", "]", body)
        out.append(f"\n## {page.title}\n\n{page.summary}\n\n{body.strip()}\n")
    return "".join(out)
