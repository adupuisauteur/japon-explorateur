"""« Ouvrir le document » (2.0.0, lot 10) : le meilleur lien vers le document lui-même — visionneuse ou page de
lecture de la source — plutôt que le manifeste IIIF, fichier technique.

Fonctionne sur une notice (Record) comme sur un résultat de recherche (dictionnaire `data`), sans appel réseau.
"""
import re
from urllib.parse import urlparse

KOKUSHO = re.compile(r"(?:kokusho\.nijl\.ac\.jp/biblio/|10\.20730/)(\d{6,})")
NDL_PID = re.compile(r"(?:dl\.ndl\.go\.jp/(?:info:ndljp/)?pid/|/iiif/)(\d{5,})")
WASEDA = re.compile(r"wul\.waseda\.ac\.jp/kotenseki/html/([a-z0-9]+)/([a-z0-9_]+)")

#: Mention exigée par Waseda pour tout lien vers ses images (conditions d'utilisation de la bibliothèque).
WASEDA_MENTION = "早稲田大学図書館古典籍総合データベース (Waseda University Library, Kotenseki Sōgō Database)"


def _get(obj, name):
    if isinstance(obj, dict):
        return str(obj.get(name) or "")
    return str(getattr(obj, name, "") or "")


def document_link(obj, catalogue_code=""):
    """{"url", "label", "mention"} ou None. `obj` : notice ou données d'un résultat."""
    urls = " ".join(_get(obj, f) for f in ("digital_access_url", "image_url", "source_url"))
    m = KOKUSHO.search(urls)
    if m:
        return {"url": f"https://kokusho.nijl.ac.jp/biblio/{m.group(1)}", "label": "Ouvrir dans le Kokusho",
                "mention": ""}
    m = WASEDA.search(urls)
    if m:
        return {"url": f"https://www.wul.waseda.ac.jp/kotenseki/html/{m.group(1)}/{m.group(2)}/",
                "label": "Ouvrir sur le site de Waseda", "mention": WASEDA_MENTION}
    m = NDL_PID.search(urls)
    if m and "ndl.go.jp" in urls:
        return {"url": f"https://dl.ndl.go.jp/pid/{m.group(1)}", "label": "Ouvrir dans la NDL Digital Collections",
                "mention": ""}
    digital = _get(obj, "digital_access_url")
    if digital.startswith("http"):
        host = urlparse(digital).netloc
        label = "Lire le texte (Aozora Bunko)" if "aozora.gr.jp" in host else f"Ouvrir le document ({host})"
        return {"url": digital, "label": label, "mention": ""}
    return None
