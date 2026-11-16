"""2.0.0 — lot 10 : documents et nouvelles sources."""
import json

import httpx

from apps.catalog.models import Record
from apps.catalog.services import upsert_record
from apps.core import etude_sources as E

from .helpers import AppTestCase

WASEDA_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:openSearch="http://a9.com/-/spec/opensearchrss/1.0/">
<channel><title>t</title><openSearch:totalResults>12</openSearch:totalResults>
<item><title>源氏物語</title><link>https://ndlsearch.ndl.go.jp/books/R000000050-I000000001</link><dc:title>源氏物語</dc:title>
<rdfs:seeAlso rdf:resource="https://www.wul.waseda.ac.jp/kotenseki/html/he12/he12_00001/index.html"/></item>
</channel></rss>"""

WASEDA_PAGE = """<html><body><h1>源氏物語</h1><a href="https://archive.wul.waseda.ac.jp/kosho/he12/he12_00001/manifest.json">Manifest</a>
<a href="he12_00001.pdf">PDF</a><img src="https://archive.wul.waseda.ac.jp/kosho/he12/he12_00001/he12_00001_p0001s.jpg">
<p>画像の利用については早稲田大学図書館の許可が必要です。</p></body></html>"""

NDL_MANIFEST = {"@context": "http://iiif.io/api/presentation/2/context.json", "license": "https://example.org/pdm",
                "sequences": [{"canvases": [{"images": [{"resource": {"@id": "https://dl.ndl.go.jp/x.jpg",
                                                                      "service": {"@id": "https://dl.ndl.go.jp/api/iiif/1234567/R0000001"}}}]}]}]}


class Router:
    def __init__(self, robots_block=()):
        self.seen = []
        self.robots_block = robots_block

    def __call__(self, request):
        url = str(request.url)
        self.seen.append(url)
        if url.endswith("/robots.txt"):
            host = request.url.host
            body = "User-agent: *\nDisallow: /\n" if host in self.robots_block else "User-agent: *\nAllow: /\n"
            return httpx.Response(200, text=body)
        if "jps-cross" in url:
            return httpx.Response(200, json={"hit": 2, "list": [
                {"id": "nijl_kokusho-200015559", "database": "nijl_kokusho",
                 "common": {"title": "歌仙繪", "linkUrl": "https://kokusho.nijl.ac.jp/biblio/200015559"}},
                {"id": "x", "common": {"title": "y", "linkUrl": "https://example.org/y"}}]})
        if "api/database/search" in url:
            return httpx.Response(200, json={"hit": 1, "list": [{"id": "nijl_kokusho", "name": {"ja": "国書データベース"},
                                                                  "apiType": "ok", "contentsAccess": "open"}]})
        if "kokusho.nijl.ac.jp/biblio" in url:
            return httpx.Response(200, json={"@context": "http://iiif.io/api/presentation/3/context.json",
                                             "items": [], "rights": "http://creativecommons.org/licenses/by-sa/4.0/"})
        if "opensearch" in url:
            return httpx.Response(200, text=WASEDA_RSS, headers={"content-type": "application/rss+xml"})
        if "wul.waseda.ac.jp/kotenseki/html" in url:
            return httpx.Response(200, text=WASEDA_PAGE, headers={"content-type": "text/html; charset=utf-8"})
        if "dl.ndl.go.jp/api/iiif/1234567/manifest.json" in url:
            return httpx.Response(200, json=NDL_MANIFEST)
        if "dl.ndl.go.jp/api/iiif/1234567/R0000001" in url:
            return httpx.Response(403)
        if "aozora.gr.jp/index_pages" in url:
            return httpx.Response(200, content=b"PK", headers={"content-length": "2",
                                                               "last-modified": "Sun, 15 Nov 2026 00:00:00 GMT"})
        if "hi.u-tokyo.ac.jp" in url:
            return httpx.Response(200, text='<html><form action="/ships/search" method="get"><input name="q"></form>'
                                            '<a href="https://clioimg.hi.u-tokyo.ac.jp/iiif/x/manifest.json">IIIF</a></html>',
                                  headers={"content-type": "text/html"})
        return httpx.Response(404)


class SourceStudyTests(AppTestCase):
    def test_study_reports_structure_and_writes_nothing(self):
        cat = self.catalogue("ndl")
        upsert_record(cat, {"source_id": "N1", "original_title": "五輪書",
                            "digital_access_url": "https://dl.ndl.go.jp/pid/1234567"})
        before = Record.objects.count()
        router = Router()
        study = E.Study(transport=httpx.MockTransport(router), pause=0)
        steps = study.run(E.ndl_digital_ids())
        report = E.text_report(steps, study.requests)
        self.assertEqual(Record.objects.count(), before)
        self.assertEqual(E.ndl_digital_ids(), ["1234567"])
        self.assertIn("nijl_kokusho", report)  # base Japan Search des notices Kokusho
        self.assertIn("kokusho.nijl.ac.jp", report)
        self.assertIn("total 12", report)  # fonds Waseda dans NDL Search
        self.assertIn("manifeste IIIF : 1 lien(s)", report)
        self.assertIn("許可", report)
        self.assertIn("première image HTTP 403", report)  # numérisation non librement accessible
        self.assertIn("/ships/search", report)
        self.assertTrue(all(s.state == "ok" for s in steps), [(s.key, s.facts) for s in steps if s.state != "ok"])

    def test_robots_refusal_is_respected(self):
        router = Router(robots_block={"www.wul.waseda.ac.jp", "www.aozora.gr.jp"})
        study = E.Study(transport=httpx.MockTransport(router), pause=0)
        steps = {s.key: s for s in study.run([])}
        self.assertEqual(steps["waseda-page"].state, "non_permis")
        self.assertFalse(any("/kotenseki/html/" in u for u in router.seen))
        self.assertFalse(any("index_pages" in u for u in router.seen))
        self.assertIn("NON permise", " ".join(steps["aozora"].facts))

    def test_failing_step_does_not_stop_the_study(self):
        def transport(request):
            if "jps-cross" in str(request.url):
                raise httpx.ConnectError("coupé")
            return Router()(request)

        study = E.Study(transport=httpx.MockTransport(transport), pause=0)
        steps = study.run([])
        states = {s.title: s.state for s in steps}
        self.assertIn("erreur", states.values())
        self.assertGreaterEqual(len(steps), 9)
        json.dumps([s.__dict__ for s in steps], ensure_ascii=False)
