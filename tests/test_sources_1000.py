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
            import io
            import zipfile

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("list_person_all_extended_utf8.csv", "\ufeff作品ID,作品名\n000001,羅生門\n")
            return httpx.Response(200, content=buffer.getvalue(),
                                  headers={"last-modified": "Sun, 15 Nov 2026 00:00:00 GMT"})
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
        self.assertIn("1 ligne(s) ; 2 colonnes", report)
        self.assertIn("作品ID | 作品名", report)
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


# --------------------------------------------------------------------------- Aozora Bunko

import csv as _csv
import io as _io
import zipfile as _zipfile
from unittest import mock

from django.test import override_settings

from apps.connectors import aozora as AZ
from apps.connectors.http import ConnectorHTTP

HEADER = ("作品ID,作品名,作品名読み,ソート用読み,副題,副題読み,原題,初出,分類番号,文字遣い種別,作品著作権フラグ,公開日,"
          "最終更新日,図書カードURL,人物ID,姓,名,姓読み,名読み,姓読みソート用,名読みソート用,姓ローマ字,名ローマ字,"
          "役割フラグ,生年月日,没年月日,人物著作権フラグ,底本名1,底本出版社名1,底本初版発行年1,入力に使用した版1,"
          "校正に使用した版1,底本の親本名1,底本の親本出版社名1,底本の親本初版発行年1,底本名2,底本出版社名2,"
          "底本初版発行年2,入力に使用した版2,校正に使用した版2,底本の親本名2,底本の親本出版社名2,底本の親本初版発行年2,"
          "入力者,校正者,テキストファイルURL,テキストファイル最終更新日,テキストファイル符号化方式,テキストファイル文字集合,"
          "テキストファイル修正回数,XHTML/HTMLファイルURL,XHTML/HTMLファイル最終更新日,XHTML/HTMLファイル符号化方式,"
          "XHTML/HTMLファイル文字集合,XHTML/HTMLファイル修正回数").split(",")

TEXT_URL = "https://www.aozora.gr.jp/cards/000001/files/900001_ruby_1.zip"
XHTML_URL = "https://www.aozora.gr.jp/cards/000001/files/900001_1.html"


def _row(**values):
    return [values.get(h, "") for h in HEADER]


def aozora_list(extra_rows=0, header=HEADER):
    rows = [
        _row(作品ID="900001", 作品名="架空の物語", 作品名読み="かくうのものがたり", 初出="「架空雑誌」1910（明治43）年",
             分類番号="NDC 913", 文字遣い種別="旧字旧仮名", 作品著作権フラグ="なし",
             図書カードURL="https://www.aozora.gr.jp/cards/000001/card900001.html", 姓="架空", 名="太郎",
             姓読み="かくう", 名読み="たろう", 役割フラグ="著者", 底本名1="架空全集", 底本出版社名1="架空書房",
             底本初版発行年1="1950（昭和25）年", 入力者="入力者甲", 校正者="校正者乙", テキストファイルURL=TEXT_URL,
             **{"XHTML/HTMLファイルURL": XHTML_URL}),
        _row(作品ID="900001", 作品名="架空の物語", 図書カードURL="https://www.aozora.gr.jp/cards/000001/card900001.html",
             姓="架空", 名="花子", 役割フラグ="翻訳者"),
        _row(作品ID="900002", 作品名="保護作品", 作品著作権フラグ="あり",
             図書カードURL="https://www.aozora.gr.jp/cards/000002/card900002.html", 姓="架空", 名="一郎", 役割フラグ="著者"),
    ]
    rows += [_row(作品ID=f"9{n:05d}", 作品名=f"架空作品{n}", 図書カードURL=f"https://www.aozora.gr.jp/cards/x/card{n}.html",
                  姓="架空", 名="次郎", 役割フラグ="著者") for n in range(10, 10 + extra_rows)]
    out = _io.StringIO()
    writer = _csv.writer(out)
    writer.writerow(header)
    writer.writerows([r[:len(header)] for r in rows])
    buffer = _io.BytesIO()
    with _zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("list_person_all_extended_utf8.csv", "﻿" + out.getvalue())
    return buffer.getvalue()


AOZORA_TEXT = """架空の物語
架空太郎

-------------------------------------------------------
【テキスト中に現れる記号について】
《》：ルビ
-------------------------------------------------------

［＃３字下げ］一［＃「一」は中見出し］
　昔、｜東の国《ひがしのくに》に一人の男が住んでゐた。男は毎朝《まいあさ》川へ行き、※［＃「土＋向」、第3水準1-15-48］を眺めた。

底本：「架空全集」架空書房
　　　1950（昭和25）年
入力：入力者甲
"""


def text_zip():
    buffer = _io.BytesIO()
    with _zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("kakuu.txt", AOZORA_TEXT.replace("\n", "\r\n").encode("cp932"))
    return buffer.getvalue()


class AozoraTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.requests = []
        self.list_bytes = aozora_list()

        def transport(request):
            url = str(request.url)
            self.requests.append(url)
            if url.endswith(".zip") and "index_pages" in url:
                return httpx.Response(200, content=self.list_bytes)
            if url == TEXT_URL:
                return httpx.Response(200, content=text_zip())
            if url == XHTML_URL:
                page = ('<html><head><meta charset="Shift_JIS"></head><body><h1 class="title">架空の物語</h1>'
                        '<div class="main_text">昔、<ruby><rb>東</rb><rp>（</rp><rt>ひがし</rt><rp>）</rp></ruby>の国。<br>'
                        '二行目。</div><div class="bibliographical_information">底本：「架空全集」</div></body></html>')
                return httpx.Response(200, content=page.encode("cp932"))
            return httpx.Response(404)

        ConnectorHTTP.transport = httpx.MockTransport(transport)
        self.addCleanup(setattr, ConnectorHTTP, "transport", None)
        from django.conf import settings
        import tempfile
        media = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        media.enable()
        self.addCleanup(media.disable)
        from apps.catalog.models import Catalogue
        self.aozora = Catalogue.objects.get(code="aozora")
        Catalogue.objects.filter(pk=self.aozora.pk).update(min_interval_seconds=0)
        self.aozora.refresh_from_db()
        self.client.force_login(self.admin)

    def _import(self):
        from apps.updates.models import SyncJob
        from apps.updates.services import apply_sync, run_sync

        job = run_sync(SyncJob.objects.create(catalogue=self.aozora, kind="full"))
        self.assertEqual(job.status, "review", job.message)
        apply_sync(job, self.admin)
        return job

    def test_list_grouped_by_work_with_roles_and_rights(self):
        works = AZ.group_works(AZ.read_list(self.list_bytes))
        self.assertEqual([w.source_id for w in works], ["900001", "900002"])
        first = works[0].data
        self.assertEqual(first["creator_original"], "架空 太郎 ; 架空 花子（訳）")
        self.assertEqual(first["digital_access_url"], XHTML_URL)
        self.assertIn("Domaine public", first["rights_and_access"])
        self.assertIn("底本：架空全集", first["description_original"])
        self.assertEqual(works[0].raw["テキストファイルURL"], TEXT_URL)
        self.assertIn("protégée", works[1].data["rights_and_access"])

    def test_changed_columns_stop_the_import_with_the_received_header(self):
        from apps.connectors.base import ConnectorError

        with self.assertRaises(ConnectorError) as ctx:
            AZ.read_list(aozora_list(header=["作品ID", "題名"]))
        self.assertIn("作品名", str(ctx.exception))
        self.assertIn("Colonnes reçues : 作品ID, 題名", str(ctx.exception))

    def test_search_before_import_explains_what_to_do(self):
        from apps.connectors.base import ConnectorError, SearchQuery

        with self.assertRaisesMessage(ConnectorError, "pas encore importée"):
            AZ.AozoraConnector(self.aozora).search(SearchQuery(text="物語"))

    def test_import_then_search_without_new_request(self):
        from apps.connectors.base import SearchQuery

        self._import()
        record = Record.objects.get(catalogue=self.aozora, source_id="900001")
        self.assertEqual(record.raw_data["テキストファイルURL"], TEXT_URL)
        count = len(self.requests)
        response = AZ.AozoraConnector(self.aozora).search(SearchQuery(text="架空の物語"))
        self.assertEqual(response.total, 1)
        self.assertEqual(len(self.requests), count)  # recherche locale : aucun appel au site

    def test_interrupted_import_resumes_from_its_cursor_without_downloading_again(self):
        self.list_bytes = aozora_list(extra_rows=30)
        connector = AZ.AozoraConnector(self.aozora)
        with mock.patch.object(AZ, "BATCH", 10):
            batches = list(connector.harvest())
            self.assertEqual([b.cursor for b in batches], ["10", "20", "30", "32"])
            downloads = sum(1 for u in self.requests if "index_pages" in u)
            resumed = list(connector.harvest(cursor="20"))
        self.assertEqual([b.cursor for b in resumed], ["30", "32"])
        self.assertEqual(sum(1 for u in self.requests if "index_pages" in u), downloads)  # liste du jour réutilisée

    def test_text_downloaded_on_click_shown_with_ruby_and_sent_to_a_project(self):
        from apps.catalog import texts
        from apps.translation.models import TranslationDocument, TranslationProject

        self._import()
        record = Record.objects.get(catalogue=self.aozora, source_id="900001")
        page = self.client.get(f"/notices/{record.record_id}/texte/").content.decode()
        self.assertIn("Télécharger le texte", page)
        self.assertNotIn(TEXT_URL, self.requests)  # rien sans clic
        self.client.post(f"/notices/{record.record_id}/texte/telecharger/")
        stored = record.texts.get()
        self.assertEqual((stored.file_format, stored.encoding), ("zip", "cp932"))
        page = self.client.get(f"/notices/{record.record_id}/texte/").content.decode()
        self.assertIn("<ruby>東の国<rt>ひがしのくに</rt></ruby>", page)
        self.assertIn("<ruby>毎朝<rt>まいあさ</rt></ruby>", page)
        self.assertNotIn("［＃", page.split('class="aozora-text')[1].split("</div>")[0])
        self.assertIn("底本：「架空全集」", page)
        head, body, colophon = texts.split(stored.text)
        self.assertIn("架空太郎", head)
        self.assertNotIn("記号について", body)
        plain = texts.plain(body)
        self.assertIn("昔、東の国に一人の男が住んでゐた。男は毎朝川へ行き、※〔土＋向〕を眺めた。", plain)
        project = TranslationProject.objects.create(owner=self.admin, title="Essai Aozora")
        self.client.post(f"/notices/{record.record_id}/texte/projet/", {"project": project.pk})
        document = TranslationDocument.objects.get(project=project)
        self.assertEqual((document.source_kind, document.record_id), ("aozora", record.pk))
        self.assertEqual(document.original_text, plain)

    def test_reader_cannot_download_and_html_is_escaped(self):
        from apps.catalog import texts

        self.assertEqual(str(texts.ruby_html("<script>x</script>漢字《かんじ》")),
                         "&lt;script&gt;x&lt;/script&gt;<ruby>漢字<rt>かんじ</rt></ruby>")
        self._import()
        record = Record.objects.get(catalogue=self.aozora, source_id="900001")
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(f"/notices/{record.record_id}/texte/telecharger/").status_code, 403)
        self.assertFalse(record.texts.exists())

    def test_xhtml_fallback(self):
        from apps.catalog import texts

        with httpx.Client(transport=ConnectorHTTP.transport) as client:
            text, encoding = texts.from_xhtml(client.get(XHTML_URL).content)
        self.assertEqual(encoding, "cp932")
        self.assertIn("昔、｜東《ひがし》の国。\n二行目。", text)
        self.assertIn("底本：「架空全集」", text)


class RegistryTests(AppTestCase):
    def test_registry_complete_even_if_one_connector_module_was_imported_first(self):
        """Cause des tests de recherche instables : un module importé seul remplissait le registre à moitié."""
        from apps.connectors import registry

        saved = dict(registry._REGISTRY), registry._LOADED
        try:
            registry._REGISTRY.clear()
            registry._LOADED = False
            registry.register(AZ.AozoraConnector)  # comme un « import apps.connectors.aozora » fait ailleurs
            self.assertIn("ndl", registry.available_connectors())
            self.assertIn("local", registry.available_connectors())
        finally:
            registry._REGISTRY.clear()
            registry._REGISTRY.update(saved[0])
            registry._LOADED = saved[1]
