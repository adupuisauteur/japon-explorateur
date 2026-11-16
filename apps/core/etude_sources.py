"""Étude des sources (2.0.0, lot 10) — à lancer sur le poste de l'utilisateur, seul endroit d'où ces sites sont joignables.

Lecture seule, une trentaine de requêtes espacées d'une seconde, uniquement quand l'utilisateur lance la commande
`manage.py etudier_sources`. Rien n'est enregistré dans la base. Le rapport décrit la structure des réponses (champs,
adresses, codes HTTP) pour construire les connecteurs du lot 10 à partir de faits et non de suppositions.

Aucune donnée personnelle : des notices NDL de la base, seuls les identifiants des numérisations sont repris.
"""
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from django.conf import settings
from lxml import etree, html

NDL_OPENSEARCH = "https://ndlsearch.ndl.go.jp/api/opensearch"
JPSEARCH = "https://jpsearch.go.jp/api/item/search/jps-cross"
JPSEARCH_DB = "https://jpsearch.go.jp/api/database/search"
KOKUSHO_MANIFEST = "https://kokusho.nijl.ac.jp/biblio/200015559/manifest"
AOZORA_LIST = "https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip"
ROBOTS = ["https://www.wul.waseda.ac.jp/robots.txt", "https://archive.wul.waseda.ac.jp/robots.txt",
          "https://www.aozora.gr.jp/robots.txt", "https://www.hi.u-tokyo.ac.jp/robots.txt",
          "https://wwwap.hi.u-tokyo.ac.jp/robots.txt", "https://kokusho.nijl.ac.jp/robots.txt",
          "https://dl.ndl.go.jp/robots.txt"]
SHIPS_PAGES = ["https://www.hi.u-tokyo.ac.jp/publication/dip", "https://wwwap.hi.u-tokyo.ac.jp/ships/"]
TITLES = {"japan_search": "Japan Search : bases et sites dans les résultats",
          "japan_search_databases": "Japan Search : bases correspondant aux sources étudiées",
          "kokusho": "Kokusho : manifeste IIIF officiel", "ndl_provider": "NDL Search, fonds",
          "waseda_page": "Waseda : liens d'une page d'ouvrage", "ndl_access": "NDL : accès des documents numérisés",
          "aozora": "Aozora Bunko : liste des œuvres", "ships": "Historiographical Institute (SHIPS)"}
URL_RE = re.compile(r"https?://[^\s\"'<>]+")


@dataclass
class Step:
    key: str
    title: str
    state: str = "ok"  # ok, erreur, non_permis
    facts: list = field(default_factory=list)
    data: dict = field(default_factory=dict)


class Study:
    def __init__(self, transport=None, pause=1.0):
        self.pause = pause
        kwargs = {"timeout": 25, "follow_redirects": True,
                  "headers": {"User-Agent": settings.CONNECTOR_USER_AGENT, "Accept-Language": "ja,fr;q=0.8"}}
        if transport is not None:
            kwargs["transport"] = transport
        self.client = httpx.Client(**kwargs)
        self.robots = {}
        self.requests = 0

    # ------------------------------------------------------------------ outils

    def get(self, url, params=None, *, stream_head=False):
        if self.requests:
            time.sleep(self.pause)
        self.requests += 1
        if stream_head:
            with self.client.stream("GET", url, params=params) as response:  # en-têtes seulement, corps non lu
                return response
        return self.client.get(url, params=params)

    def allowed(self, url):
        """robots.txt du site (lu une fois) ; en cas de doute, on s'abstient."""
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self.robots:
            parser = RobotFileParser()
            try:
                response = self.get(root + "/robots.txt")
                parser.parse(response.text.splitlines() if response.status_code == 200 else [])
            except httpx.HTTPError:
                parser.parse([])
            self.robots[root] = parser
        return self.robots[root].can_fetch(settings.CONNECTOR_USER_AGENT, url)

    # ------------------------------------------------------------------ étapes

    def run(self, ndl_ids=()):
        steps = []
        for method, args in ((self.robots_files, ()), (self.japan_search, ()), (self.japan_search_databases, ()),
                             (self.kokusho, ()), (self.ndl_provider, ("waseda", "源氏物語")),
                             (self.ndl_provider, ("aozora", "夏目漱石")), (self.waseda_page, ()),
                             (self.ndl_access, (ndl_ids,)), (self.aozora, ()), (self.ships, ())):
            try:
                steps.append(method(*args))
            except Exception as exc:  # noqa: BLE001 — une étape en échec n'arrête pas l'étude
                title = TITLES.get(method.__name__, method.__name__) + (f" « {args[0]} »" if args and
                                                                         isinstance(args[0], str) else "")
                steps.append(Step(method.__name__, title, "erreur", [f"{exc.__class__.__name__} : {str(exc)[:300]}"]))
        self.client.close()
        return steps

    def robots_files(self):
        step = Step("robots", "Fichiers robots.txt (règles d'accès automatique des sites)")
        for url in ROBOTS:
            try:
                response = self.get(url)
                text = response.text if response.status_code == 200 else ""
                rules = [line.strip() for line in text.splitlines()
                         if line.strip() and not line.startswith("#")][:12]
                step.facts.append(f"{url} → HTTP {response.status_code}" + (f" ; {' | '.join(rules)}" if rules else ""))
            except httpx.HTTPError as exc:
                step.facts.append(f"{url} → injoignable ({exc.__class__.__name__})")
        return step

    def japan_search(self):
        """Bases et sites réellement présents dans les résultats (cause de « aucune notice Kokusho reconnue »)."""
        step = Step("japansearch", "Japan Search : bases et sites dans les résultats")
        for keyword in ("源氏物語", "歌仙", "方丈記"):
            response = self.get(JPSEARCH, {"keyword": keyword, "size": 100})
            step.facts.append(f"« {keyword} » → HTTP {response.status_code}")
            if response.status_code != 200:
                continue
            payload = response.json()
            items = payload.get("list") or []
            databases, hosts, keys = Counter(), Counter(), Counter()
            for item in items:
                keys.update(item.keys())
                common = item.get("common") or {}
                databases[str(item.get("database") or common.get("database") or "?")] += 1
                for url in set(URL_RE.findall(json.dumps(item, ensure_ascii=False))):
                    hosts[urlparse(url).netloc] += 1
            step.facts.append(f"  total {payload.get('hit')} ; {len(items)} lus ; clés : {', '.join(sorted(keys))}")
            step.facts.append(f"  bases : {dict(databases.most_common(15))}")
            step.facts.append(f"  sites cités : {dict(hosts.most_common(20))}")
            for target in ("kokusho.nijl.ac.jp", "kotenseki.nijl.ac.jp", "wul.waseda.ac.jp", "hi.u-tokyo.ac.jp",
                           "aozora.gr.jp"):
                sample = next((i for i in items if target in json.dumps(i, ensure_ascii=False)), None)
                if sample:
                    common = sample.get("common") or {}
                    step.data.setdefault(target, {"base": sample.get("database") or common.get("database"),
                                                  "id": sample.get("id"),
                                                  "champs_common": sorted(common.keys()),
                                                  "liens": sorted({u for u in URL_RE.findall(
                                                      json.dumps(sample, ensure_ascii=False)) if target in u})[:5]})
        for target, info in step.data.items():
            step.facts.append(f"Exemple {target} : base « {info['base']} », id {info['id']}, liens {info['liens']}")
        return step

    def japan_search_databases(self):
        step = Step("japansearch-bases", "Japan Search : bases correspondant aux sources étudiées")
        for keyword in ("国書", "国文学研究資料館", "早稲田", "史料編纂所", "青空文庫"):
            response = self.get(JPSEARCH_DB, {"keyword": keyword, "size": 50})
            if response.status_code != 200:
                step.facts.append(f"« {keyword} » → HTTP {response.status_code}")
                continue
            found = []
            for db in response.json().get("list") or []:
                name = db.get("name") or {}
                label = name.get("ja") if isinstance(name, dict) else str(name)
                found.append(f"{db.get('id')} ({label}, api {db.get('apiType')}, accès {db.get('contentsAccess')})")
            step.facts.append(f"« {keyword} » → {response.json().get('hit')} base(s) : {' ; '.join(found[:10]) or '—'}")
        return step

    def kokusho(self):
        step = Step("kokusho", "Kokusho : manifeste IIIF officiel d'une notice d'essai")
        response = self.get(KOKUSHO_MANIFEST)
        step.facts.append(f"{KOKUSHO_MANIFEST} → HTTP {response.status_code}")
        if response.status_code == 200:
            manifest = response.json()
            step.facts.append(f"  version : {manifest.get('@context')} ; clés : {', '.join(sorted(manifest.keys()))}")
            for key in ("license", "rights", "attribution", "requiredStatement", "seeAlso", "related", "homepage"):
                if key in manifest:
                    step.facts.append(f"  {key} : {json.dumps(manifest[key], ensure_ascii=False)[:300]}")
            canvases = _canvases(manifest)
            step.facts.append(f"  vues : {len(canvases)} ; première image : {canvases[0] if canvases else '—'}")
        return step

    def ndl_provider(self, dpid, keyword):
        """Fonds d'une autre bibliothèque dans NDL Search (dpid), sans analyse de pages HTML."""
        step = Step(f"ndl-{dpid}", f"NDL Search, fonds « {dpid} »")
        response = self.get(NDL_OPENSEARCH, {"dpid": dpid, "any": keyword, "cnt": 5})
        step.facts.append(f"OpenSearch dpid={dpid} « {keyword} » → HTTP {response.status_code}")
        if response.status_code != 200:
            return step
        root = etree.fromstring(response.content, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        channel = root.find("channel")
        total = channel.findtext("{http://a9.com/-/spec/opensearchrss/1.0/}totalResults") if channel is not None else None
        items = channel.findall("item") if channel is not None else []
        step.facts.append(f"  total {total} ; {len(items)} lus")
        links = []
        for n, item in enumerate(items[:3]):
            tags = Counter(etree.QName(child).localname + (f"[{child.get('{http://www.w3.org/2001/XMLSchema-instance}type')}]"
                                                           if child.get("{http://www.w3.org/2001/XMLSchema-instance}type") else "")
                           for child in item)
            urls = sorted({u for u in URL_RE.findall(etree.tostring(item, encoding="unicode"))
                           if not any(n in u for n in ("purl.org", "w3.org", "ndl.go.jp/dcndl", "a9.com"))})
            links.extend(urls)
            step.facts.append(f"  notice {n + 1} : champs {dict(tags)}")
            step.facts.append(f"    liens : {urls[:8]}")
            for tag in ("rights", "accessRights", "license"):
                values = [e.text for e in item.iter() if etree.QName(e).localname == tag and e.text]
                if values:
                    step.facts.append(f"    {tag} : {values[:2]}")
        step.data["links"] = links
        return step

    def waseda_page(self):
        """Structure d'une page d'ouvrage de Waseda (une seule page, si robots.txt le permet) : liens vers le manifeste
        IIIF, la visionneuse, les PDF et les images."""
        step = Step("waseda-page", "Waseda : liens d'une page d'ouvrage")
        response = self.get(NDL_OPENSEARCH, {"dpid": "waseda", "any": "源氏物語", "cnt": 5})
        candidates = sorted({u for u in URL_RE.findall(response.text) if "wul.waseda.ac.jp/kotenseki/html/" in u})
        if not candidates:
            step.state = "erreur"
            step.facts.append("Aucune adresse de page Waseda dans les notices de NDL Search.")
            return step
        page_url = candidates[0]
        if not self.allowed(page_url):
            step.state = "non_permis"
            step.facts.append(f"{page_url} : robots.txt n'autorise pas la lecture automatique ; page non lue.")
            return step
        page = self.get(page_url)
        step.facts.append(f"{page_url} → HTTP {page.status_code} ({len(page.content)} octets, "
                          f"encodage {page.encoding})")
        if page.status_code != 200:
            return step
        tree = html.fromstring(page.text)
        hrefs = [urljoin(page_url, a.get("href")) for a in tree.iter("a") if a.get("href")]
        hrefs += [urljoin(page_url, i.get("src")) for i in tree.iter("img") if i.get("src")]
        for label, needle in (("manifeste IIIF", "manifest"), ("visionneuse", "viewer"), ("PDF", ".pdf"),
                              ("image", ".jpg")):
            found = [h for h in hrefs if needle in h.lower()]
            step.facts.append(f"  {label} : {len(found)} lien(s) ; {found[:3]}")
        text = " ".join(tree.text_content().split())
        for word in ("利用", "許可", "著作権", "ライセンス"):
            at = text.find(word)
            if at >= 0:
                step.facts.append(f"  mention « {word} » : …{text[max(0, at - 60):at + 120]}…")
                break
        return step

    def ndl_access(self, ndl_ids):
        """Accès réel des numérisations NDL de la base : manifeste lisible ? première image servie ? (lot 3, reporté)"""
        step = Step("ndl-acces", "NDL : accès des documents numérisés de la base (manifeste et première image)")
        if not ndl_ids:
            step.facts.append("Aucune notice NDL numérisée dans la base.")
            return step
        for pid in ndl_ids:
            manifest_url = f"https://dl.ndl.go.jp/api/iiif/{pid}/manifest.json"
            response = self.get(manifest_url)
            line = f"{pid} : manifeste HTTP {response.status_code}"
            if response.status_code == 200:
                try:
                    manifest = response.json()
                except ValueError:
                    step.facts.append(line + " (illisible)")
                    continue
                rights = {k: manifest.get(k) for k in ("license", "rights", "attribution", "requiredStatement")
                          if manifest.get(k)}
                meta = {str(m.get("label")): str(m.get("value"))[:80] for m in (manifest.get("metadata") or [])
                        if any(w in str(m.get("label")) for w in ("公開", "範囲", "Access", "access", "提供", "権利"))}
                canvases = _canvases(manifest)
                line += f" ; {len(canvases)} vue(s) ; droits {json.dumps(rights, ensure_ascii=False)[:200]}"
                if meta:
                    line += f" ; {json.dumps(meta, ensure_ascii=False)[:200]}"
                if canvases:
                    image = _thumbnail(canvases[0])
                    try:
                        status = self.get(image, stream_head=True).status_code
                    except httpx.HTTPError as exc:
                        status = exc.__class__.__name__
                    line += f" ; première image HTTP {status}"
            step.facts.append(line)
        return step

    def aozora(self):
        step = Step("aozora", "Aozora Bunko : liste de toutes les œuvres")
        allowed = self.allowed(AOZORA_LIST)
        step.facts.append(f"robots.txt : {'lecture permise' if allowed else 'lecture NON permise'} pour {AOZORA_LIST}")
        if not allowed:
            return step
        response = self.get(AOZORA_LIST)  # quelques Mo, une fois : il faut l'en-tête exact des colonnes
        step.facts.append(f"  HTTP {response.status_code} ; {len(response.content)} octets ; "
                          f"modifié {response.headers.get('last-modified')}")
        if response.status_code != 200:
            return step
        import csv
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            step.facts.append(f"  fichiers : {names}")
            with archive.open(names[0]) as handle:
                text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
                rows = csv.reader(text)
                header = next(rows)
                first = next(rows, [])
                count = 1 + sum(1 for _ in rows) if first else 0
        step.facts.append(f"  {count} ligne(s) ; {len(header)} colonnes :")
        step.facts.append("  " + " | ".join(header))
        step.data["header"] = header
        if first:
            step.facts.append("  première ligne : " + " | ".join(v[:40] for v in first))
        return step

    def ships(self):
        step = Step("ships", "Historiographical Institute (SHIPS) : pages d'accès aux bases")
        for url in SHIPS_PAGES:
            if not self.allowed(url):
                step.facts.append(f"{url} : robots.txt n'autorise pas la lecture automatique ; page non lue.")
                continue
            response = self.get(url)
            step.facts.append(f"{url} → HTTP {response.status_code}")
            if response.status_code == 200 and "html" in response.headers.get("content-type", ""):
                tree = html.fromstring(response.text)
                forms = [(f.get("action"), f.get("method"), [i.get("name") for i in f.iter("input") if i.get("name")])
                         for f in tree.iter("form")]
                apis = sorted({h for h in (urljoin(url, a.get("href") or "") for a in tree.iter("a"))
                               if any(w in h.lower() for w in ("api", "iiif", "opensearch", "sru", "oai"))})
                step.facts.append(f"  formulaires : {forms[:5]}")
                step.facts.append(f"  liens API/IIIF : {apis[:8] or '—'}")
        return step


def _canvases(manifest):
    if "sequences" in manifest:  # IIIF 2
        return [c for s in manifest.get("sequences") or [] for c in s.get("canvases") or []]
    return manifest.get("items") or []  # IIIF 3


def _thumbnail(canvas):
    """Adresse d'une petite image (200 px) de la vue, pour un essai d'accès léger."""
    service = None
    for image in canvas.get("images") or []:  # IIIF 2
        resource = image.get("resource") or {}
        service = (resource.get("service") or {}).get("@id") or resource.get("@id")
    for page in canvas.get("items") or []:  # IIIF 3
        for anno in page.get("items") or []:
            body = anno.get("body") or {}
            services = body.get("service") or []
            first = services[0] if isinstance(services, list) and services else services
            service = (first or {}).get("id") or (first or {}).get("@id") or body.get("id")
    if service and not service.lower().endswith((".jpg", ".png", ".jpeg")):
        return service.rstrip("/") + "/full/200,/0/default.jpg"
    return service or ""


def ndl_digital_ids(limit=8):
    """Identifiants des numérisations NDL de la base (lecture seule) : dl.ndl.go.jp/pid/NNN ou /info:ndljp/pid/NNN."""
    from django.db.models import Q

    from apps.catalog.models import Record

    pattern = re.compile(r"(?:pid/|ndljp/pid/|/iiif/)(\d{5,})")
    ids = []
    for url, image in (Record.objects.filter(catalogue__code="ndl")
                       .filter(Q(digital_access_url__contains="ndl") | Q(image_url__contains="ndl"))
                       .values_list("digital_access_url", "image_url")[:200]):
        m = pattern.search(f"{url} {image}")
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
        if len(ids) >= limit:
            break
    return ids


def text_report(steps, requests):
    lines = ["Étude des sources — J-ed 2.0.0 (lot 10)", f"{requests} requête(s), lecture seule ; rien n'est enregistré.", ""]
    marks = {"ok": "[OK]", "erreur": "[Erreur]", "non_permis": "[Non lu : robots.txt]"}
    for step in steps:
        lines.append(f"== {step.title} {marks.get(step.state, '')}")
        lines.extend(step.facts)
        lines.append("")
    return "\n".join(lines)
