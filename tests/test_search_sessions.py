"""AT-03 à AT-08 : recherche multi-source, sélection/exclusion, modes, sessions, relance et comparaison."""
import json

import httpx

from apps.catalog.models import Catalogue, Record
from apps.catalog.services import upsert_record
from apps.connectors.http import ConnectorHTTP
from apps.library.models import LibraryEntry
from apps.searching import services
from apps.searching.models import SavedSearch, SearchResult

from .helpers import AppTestCase

NDL_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcndl="http://ndl.go.jp/dcndl/terms/" xmlns:openSearch="http://a9.com/-/spec/opensearchrss/1.0/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><channel><title>t</title>
<openSearch:totalResults>2</openSearch:totalResults>
<item><title>五輪書</title><link>https://ndlsearch.ndl.go.jp/books/R100000002-I000000001</link>
<dc:title>五輪書</dc:title><dcndl:titleTranscription>ゴリンノショ</dcndl:titleTranscription>
<dc:creator>宮本武蔵 著</dc:creator><dcterms:issued>1909</dcterms:issued>
<dc:identifier xsi:type="dcndl:NDLBibID">000000001</dc:identifier></item>
<item><title>五輪書講義</title><link>https://ndlsearch.ndl.go.jp/books/R100000002-I000000002</link>
<dc:title>五輪書講義</dc:title><dc:identifier xsi:type="dcndl:NDLBibID">000000002</dc:identifier></item>
</channel></rss>"""


def ndl_transport(request):
    return httpx.Response(200, text=NDL_RSS, headers={"content-type": "application/rss+xml"})


def failing_transport(request):
    return httpx.Response(503, text="maintenance")


class SearchTests(AppTestCase):
    def setUp(self):
        super().setUp()
        cat = self.catalogue("codh-pmjt")
        self.r1, _ = upsert_record(cat, {"source_id": "A1", "original_title": "五輪書", "reading": "ごりんのしょ",
                                         "creator_original": "宮本武蔵", "composition_date_text": "寛永20年"})
        self.r2, _ = upsert_record(cat, {"source_id": "A2", "original_title": "葉隠", "reading": "はがくれ"})
        Catalogue.objects.filter(code="ndl").update(enabled_for_search=True, min_interval_seconds=0)
        ConnectorHTTP.transport = httpx.MockTransport(ndl_transport)
        Catalogue.objects.filter(code="kokusho").update(min_interval_seconds=0, timeout_seconds=2)

    def tearDown(self):
        ConnectorHTTP.transport = None
        from django.core.cache import cache

        cache.clear()

    def _session(self, mode="selective", sources=("local", "ndl")):
        session = services.run_all_sources(services.create_session(self.admin, query="五輪書", sources=list(sources),
                                                                   mode=mode))
        # 2.0.0, lot 9 : ces tests échouaient parfois (« error » au lieu du statut attendu, résultats absents).
        # Une erreur inattendue est rapportée avec sa trace, pour en connaître la cause.
        unexpected = {code: s for code, s in session.source_stats.items() if s.get("status") == "error"}
        if unexpected:
            from apps.incidents.models import Incident

            traces = [(i.title, i.message, (i.context or {}).get("traceback")) for i in Incident.objects.all()]
            self.fail(f"Erreur inattendue d'une source : {unexpected} ; incidents : {traces}")
        return session

    def test_at03_provenance_and_tolerance_to_failing_connector(self):
        ConnectorHTTP.transport = httpx.MockTransport(failing_transport)
        session = self._session(sources=("local", "ndl"))
        # 1.2.0 (§2.7) : une source qui répond HTTP 503 est « indisponible », et non plus « erreur » générique.
        self.assertEqual(session.source_stats["ndl"]["status"], "unavailable")
        self.assertEqual(session.source_stats["local"]["status"], "ok")
        self.assertEqual(session.status, "partial")
        self.assertTrue(session.results.filter(catalogue__code="local").exists())
        ConnectorHTTP.transport = httpx.MockTransport(ndl_transport)
        from django.core.cache import cache

        cache.clear()
        session = self._session()
        ndl = session.results.filter(catalogue__code="ndl")
        self.assertEqual(ndl.count(), 2)
        first = ndl.get(source_id="000000001")
        self.assertEqual(first.data["source_url"], "https://ndlsearch.ndl.go.jp/books/R100000002-I000000001")
        self.assertEqual(first.data["reading"], "ゴリンノショ")
        page = self.client.get(f"/recherche/session/{session.uid}/resultats/")
        self.assertContains(page, "NDL Search")
        self.assertContains(page, "Collecté le")
        # session page tolerates the HTMX per-source flow
        self.assertEqual(self.client.post(f"/recherche/session/{session.uid}/source/ndl/").status_code, 200)

    def test_at04_select_deselect_exclude_reinstate(self):
        session = self._session()
        res = session.results.first()
        url = f"/recherche/session/{session.uid}/decision/"
        self.client.post(url, {"action": "select", "result_ids": res.pk})
        res.refresh_from_db()
        self.assertEqual(res.decision, "selected")
        self.client.post(url, {"action": "deselect", "result_ids": res.pk})
        res.refresh_from_db()
        self.assertEqual(res.decision, "pending")
        self.client.post(url, {"action": "exclude", "result_ids": res.pk, "reason": "wrong_period", "note": "XIXe"})
        res.refresh_from_db()
        self.assertEqual((res.decision, res.exclusion_reason), ("excluded", "wrong_period"))
        self.client.post(url, {"action": "reinstate", "result_ids": res.pk})
        res.refresh_from_db()
        self.assertEqual((res.decision, res.exclusion_reason), ("pending", ""))
        self.client.post(url, {"action": "select_all"})
        self.assertEqual(session.results.filter(decision="selected").count(), session.results.count())
        self.client.post(url, {"action": "deselect_all"})
        self.assertEqual(session.results.filter(decision="selected").count(), 0)
        self.assertEqual(res.decision_log.count(), 6)  # 4 décisions unitaires + 2 globales

    def test_at05_exclusion_never_deletes_library_record(self):
        LibraryEntry.objects.create(user=self.admin, record=self.r1)
        session = self._session()
        local = session.results.get(catalogue__code="local", source_id=self.r1.record_id)
        self.assertTrue(local.in_library)
        services.set_decision([local], "exclude", self.admin, reason="duplicate")
        services.integrate(session, list(session.results.all()), self.admin)
        self.assertTrue(Record.objects.filter(pk=self.r1.pk).exists())
        self.assertTrue(LibraryEntry.objects.filter(user=self.admin, record=self.r1).exists())

    def test_at06_three_modes_and_configurable_default(self):
        # automatique : tout est enregistré, dédoublonné
        auto = self._session(mode="auto")
        self.assertEqual(auto.results.filter(integrated_record__isnull=False).count(), auto.results.count())
        self.assertTrue(Record.objects.filter(catalogue__code="ndl", source_id="000000001").exists())
        n = Record.objects.count()
        self._session(mode="auto")
        self.assertEqual(Record.objects.count(), n, "pas de doublon lors d'un second enregistrement automatique")
        # sélectif : rien sans action
        before = LibraryEntry.objects.filter(user=self.researcher).count()
        sel = services.run_all_sources(services.create_session(self.researcher, query="五輪書",
                                                               sources=["local", "ndl"], mode="selective"))
        self.assertEqual(LibraryEntry.objects.filter(user=self.researcher).count(), before)
        services.set_decision(list(sel.results.filter(catalogue__code="ndl")[:1]), "select", self.researcher)
        self.client.force_login(self.researcher)
        r = self.client.post(f"/recherche/session/{sel.uid}/integrer/", {"dest": "library"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(LibraryEntry.objects.filter(user=self.researcher).count(), before + 1)
        # manuel : session temporaire avec expiration, aucune intégration
        man = self._session(mode="manual")
        self.assertFalse(man.is_saved)
        self.assertIsNotNone(man.expires_at)
        self.assertEqual(man.results.filter(integrated_record__isnull=False).count(), 0)
        # mode par défaut configurable
        from apps.core.models import AppSettings

        s = AppSettings.get()
        s.default_search_mode = "manual"
        s.save()
        self.assertEqual(self.reader.effective_search_mode(), "manual")
        self.researcher.default_search_mode = "auto"
        self.assertEqual(self.researcher.effective_search_mode(), "auto")

    def test_at07_session_keeps_query_sources_filters_results_decisions(self):
        r = self.client.post("/recherche/lancer/", {"q": "五輪書", "variants": ["ごりんのしょ"], "sources": ["local", "ndl"],
                                                   "mode": "selective", "period": ["edo"], "date_kind": "any"})
        self.assertEqual(r.status_code, 302)
        from apps.searching.models import SearchSession

        session = SearchSession.objects.latest("started_at")
        services.run_all_sources(session)
        session.refresh_from_db()
        self.assertEqual(session.query, "五輪書")
        self.assertEqual(session.variants, ["ごりんのしょ"])
        self.assertEqual(session.sources, ["local", "ndl"])
        self.assertEqual(session.filters["period"], ["edo"])
        self.assertIn("ndl", session.source_stats)
        self.assertTrue(session.duration_ms is not None)
        self.assertTrue(session.variant_details)
        res = session.results.first()
        services.set_decision([res], "exclude", self.admin, reason="off_topic")
        self.assertEqual(SearchResult.objects.get(pk=res.pk).exclusion_reason, "off_topic")
        self.assertContains(self.client.get(session.get_absolute_url()), "五輪書")

    def test_at08_replay_and_compare_without_silent_overwrite(self):
        first = self._session()
        self.client.post(f"/recherche/session/{first.uid}/enregistrer/", {"name": "Musashi"})
        saved = SavedSearch.objects.get(name="Musashi")
        services.integrate(first, list(first.results.filter(catalogue__code="ndl")), self.admin)
        rec = Record.objects.get(catalogue__code="ndl", source_id="000000001")
        old_title = rec.original_title
        changed = NDL_RSS.replace("<dc:title>五輪書</dc:title>", "<dc:title>五輪書（改訂）</dc:title>").replace(
            """<item><title>五輪書講義</title><link>https://ndlsearch.ndl.go.jp/books/R100000002-I000000002</link>
<dc:title>五輪書講義</dc:title><dc:identifier xsi:type="dcndl:NDLBibID">000000002</dc:identifier></item>""",
            """<item><title>新五輪</title><link>https://ndlsearch.ndl.go.jp/books/R100000002-I000000003</link>
<dc:title>新五輪</dc:title><dc:identifier xsi:type="dcndl:NDLBibID">000000003</dc:identifier></item>""")
        ConnectorHTTP.transport = httpx.MockTransport(lambda req: httpx.Response(200, text=changed))
        from django.core.cache import cache

        cache.clear()
        r = self.client.post(f"/recherche/enregistrees/{saved.pk}/relancer/")
        replay = saved.sessions.order_by("-started_at").first()
        self.assertEqual(r.status_code, 302)
        services.run_all_sources(replay)
        comp = dict(replay.results.filter(catalogue__code="ndl").values_list("source_id", "comparison"))
        self.assertEqual(comp["000000001"], "modified")
        self.assertEqual(comp["000000003"], "new")
        self.assertEqual(comp["000000002"], "unavailable")
        rec.refresh_from_db()
        self.assertEqual(rec.original_title, old_title, "la relance n'écrase rien silencieusement")

    def test_variants_are_suggestions_with_origin(self):
        r = self.client.get("/recherche/variantes/", {"q": "國史"})
        self.assertContains(r, "国史")
        self.assertContains(r, "à vérifier")
        r = self.client.get("/recherche/variantes/", {"q": "Hagakure"})
        self.assertContains(r, "はがくれ")

    def test_kokusho_iiif_lookup_by_doi(self):
        manifest = {"@context": "http://iiif.io/api/presentation/2/context.json", "@type": "sc:Manifest",
                    "label": "方丈記", "license": "https://creativecommons.org/publicdomain/mark/1.0/",
                    "attribution": "国文学研究資料館",
                    "metadata": [{"label": "著者", "value": "鴨長明"}, {"label": "刊写年", "value": "江戸前期"},
                                 {"label": "請求記号", "value": "ﾀ1-23"}],
                    "sequences": [{"canvases": []}]}
        ConnectorHTTP.transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=manifest) if req.url.path.endswith("/manifest") else httpx.Response(404))
        Catalogue.objects.filter(code="ndl").update(enabled_for_search=False)
        session = services.run_all_sources(services.create_session(self.admin, query="10.20730/200016993",
                                                                   sources=["kokusho"]))
        res = session.results.get()
        self.assertEqual(res.source_id, "200016993")
        self.assertEqual(res.data["original_title"], "方丈記")
        self.assertEqual(res.data["creator_original"], "鴨長明")
        self.assertEqual(res.data["holding_institution_text"], "国文学研究資料館")
        self.assertEqual(res.data["source_url"], "https://kokusho.nijl.ac.jp/biblio/200016993")
        self.assertEqual(res.data["digital_access"], "image")

    def test_kokusho_search_via_japansearch_filters_kokusho_links(self):
        payload = {"hit": 2, "list": [
            {"id": "nijl-1", "database": "kokusho-db", "common": {"title": "徒然草", "linkUrl": "https://kokusho.nijl.ac.jp/biblio/100000001",
                                                            "contributor": ["兼好"], "provider": "国文学研究資料館"}},
            {"id": "other-1", "common": {"title": "徒然草図", "linkUrl": "https://example.org/item/1"}}]}
        ConnectorHTTP.transport = httpx.MockTransport(lambda req: httpx.Response(200, text=json.dumps(payload)))
        session = services.run_all_sources(services.create_session(self.admin, query="徒然草", sources=["kokusho"]))
        self.assertEqual(session.results.count(), 1)
        res = session.results.get()
        self.assertEqual(res.source_id, "100000001")
        self.assertTrue(session.source_stats["kokusho"]["warnings"])
        from apps.updates.models import SyncJob
        from apps.updates.services import run_sync

        job = run_sync(SyncJob.objects.create(catalogue=self.catalogue("kokusho"), kind="test"))
        self.assertEqual(job.report["details"].get("detected_japansearch_db"), "kokusho-db")

    def test_purge_expired_sessions_keeps_records(self):
        from datetime import timedelta

        from django.utils import timezone

        session = self._session(mode="auto")
        session.is_saved = False
        session.expires_at = timezone.now() - timedelta(days=1)
        session.save()
        n_records = Record.objects.count()
        self.assertGreaterEqual(services.purge_expired(), 1)
        self.assertEqual(Record.objects.count(), n_records)
