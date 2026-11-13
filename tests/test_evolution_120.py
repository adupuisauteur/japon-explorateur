"""Évolution 1.2.0 — sources documentaires et journal des dysfonctionnements (cahier des charges, §6.3).

Tous les connecteurs sont testés **en simulation**, sur des réponses enregistrées (tests/fixtures/reponses) :
situation normale, absence de résultat, indisponibilité (HTTP 503, délai dépassé, échec DNS) et réponse
mal formée. Aucun appel réseau n'est effectué. Les tests en conditions réelles relèvent du protocole
de vérification sous Windows (docs/evolution-1.2.0/).
"""
import json
from pathlib import Path
from unittest import mock

import httpx
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import override_settings

from apps.catalog.models import Catalogue, Creator, CreatorVariant, Record, RecordVersion
from apps.catalog.search import suggest_variants
from apps.connectors.http import ConnectorHTTP
from apps.core.logging import redact, redact_url
from apps.incidents.models import Incident, IncidentEvent, IncidentOccurrence
from apps.incidents.services import change_status, record_incident
from apps.library.models import Annotation, LibraryEntry
from apps.searching import services

from .helpers import AppTestCase

FIX = Path(__file__).resolve().parent / "fixtures" / "reponses"
APPID = "APPID-SECRET-TEST-9f3c2a"


def fixture(name):
    return (FIX / name).read_text(encoding="utf-8")


class Router:
    """Transport simulé : chaque hôte renvoie le scénario choisi par le test et mémorise les requêtes reçues."""

    HOSTS = {"ndlsearch.ndl.go.jp": "ndl", "jpsearch.go.jp": "jps", "cir.nii.ac.jp": "cinii",
             "kokusho.nijl.ac.jp": "kokusho"}

    def __init__(self, **scenarios):
        self.scenarios = {"ndl": "ok", "jps": "ok", "cinii": "ok", "kokusho": "ok", **scenarios}
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        key = self.HOSTS.get(request.url.host, "")
        scenario = self.scenarios.get(key, "ok")
        if scenario == "503":
            return httpx.Response(503, text="maintenance")
        if scenario == "timeout":
            raise httpx.ReadTimeout("simulated timeout", request=request)
        if scenario == "dns":
            raise httpx.ConnectError("[Errno -2] Name or service not known", request=request)
        if scenario == "403":
            return httpx.Response(403, text="appid invalid")
        if key == "ndl":
            name = {"ok": "ndl_ok.xml", "vide": "ndl_vide.xml", "mal": "ndl_mal_forme.html"}[scenario]
            return httpx.Response(200, text=fixture(name), headers={"content-type": "application/rss+xml"})
        if key == "jps":
            if "/api/database/search" in request.url.path:
                return httpx.Response(200, text=fixture("jps_bases.json"), headers={"content-type": "application/json"})
            name = {"ok": "jps_ok.json", "vide": "jps_vide.json", "mal": "jps_mal_forme.json"}[scenario]
            return httpx.Response(200, text=fixture(name), headers={"content-type": "application/json"})
        if key == "cinii":
            name = {"ok": "cinii_ok.json", "vide": "cinii_vide.json", "mal": "cinii_mal_forme.json"}[scenario]
            return httpx.Response(200, text=fixture(name), headers={"content-type": "application/json"})
        if key == "kokusho":
            return httpx.Response(200, text=fixture("kokusho_manifeste_mal_forme.json"))
        return httpx.Response(404)


@override_settings(CINII_APPID=APPID)
class Evolution120Base(AppTestCase):
    def setUp(self):
        super().setUp()
        Catalogue.objects.update(min_interval_seconds=0, timeout_seconds=2)
        cache.clear()
        self.sleep = mock.patch("apps.connectors.http.time.sleep")
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        ConnectorHTTP.transport = None
        cache.clear()

    def route(self, **scenarios):
        router = Router(**scenarios)
        ConnectorHTTP.transport = httpx.MockTransport(router)
        return router

    def run_search(self, sources, query="望月千代女", variants=None):
        session = services.create_session(self.admin, query=query, sources=list(sources), variants=variants or [])
        return services.run_all_sources(session)


class ConnectorScenarioTests(Evolution120Base):
    """§6.3 : un test par connecteur, absence de résultat, indisponibilité, réponse mal formée."""

    CASES = [("ndl", "ndl"), ("japansearch", "jps"), ("nat-archives", "jps"), ("cinii", "cinii"),
             ("cinii-books", "cinii")]

    def test_normal_response_each_connector(self):
        for code, host in self.CASES:
            with self.subTest(source=code):
                cache.clear()
                self.route(**{host: "ok"})
                session = self.run_search([code])
                stats = session.source_stats[code]
                self.assertEqual(stats["status"], "ok", stats)
                self.assertEqual(stats["count"], 2)
                result = session.results.filter(catalogue__code=code).first()
                self.assertTrue(result.data["source_url"].startswith("https://"))
                self.assertTrue(result.data["original_title"].startswith("架空"))
        self.assertFalse(Incident.objects.exists(), "une recherche réussie ne crée aucun incident")

    def test_empty_result_is_not_an_error(self):
        for code, host in self.CASES:
            with self.subTest(source=code):
                cache.clear()
                self.route(**{host: "vide"})
                session = self.run_search([code], query="存在しない語")
                self.assertEqual(session.source_stats[code]["status"], "empty")
                self.assertEqual(session.status, "done")
        self.assertFalse(Incident.objects.exists(), "une absence de résultat n'est jamais un incident")

    def test_unavailable_source_is_a_warning_not_a_connector_defect(self):
        for code, host in self.CASES:
            with self.subTest(source=code):
                cache.clear()
                self.route(**{host: "503"})
                session = self.run_search([code])
                self.assertEqual(session.source_stats[code]["status"], "unavailable")
                self.assertEqual(session.status, "partial")
                incident = Incident.objects.get(source_code=code)
                self.assertEqual((incident.category, incident.severity, incident.origin),
                                 ("indisponibilite", "warning", "source_distante"))
                self.assertEqual(incident.http_status, 503)
                self.assertTrue(incident.last_request_id)

    def test_timeout_and_dns_failure(self):
        self.route(ndl="timeout")
        session = self.run_search(["ndl"])
        self.assertEqual(session.source_stats["ndl"]["status"], "unavailable")
        self.assertEqual(Incident.objects.get(source_code="ndl").technical_code, "timeout")
        cache.clear()
        self.route(jps="dns")
        session = self.run_search(["japansearch"])
        incident = Incident.objects.get(source_code="japansearch")
        self.assertEqual(incident.origin, "reseau", "un échec DNS oriente vers la connexion du poste")
        self.assertIn("DNS", session.source_stats["japansearch"]["error"])

    def test_malformed_response_is_classified_as_unparsable(self):
        for code, host in self.CASES:
            with self.subTest(source=code):
                cache.clear()
                self.route(**{host: "mal"})
                session = self.run_search([code])
                self.assertEqual(session.source_stats[code]["status"], "unparsable", session.source_stats[code])
                incident = Incident.objects.get(source_code=code)
                self.assertEqual((incident.category, incident.severity, incident.origin),
                                 ("reponse_illisible", "error", "connecteur"))
                self.assertIn("response_excerpt", incident.context)

    def test_kokusho_unreadable_manifest(self):
        self.route(kokusho="ok")
        session = self.run_search(["kokusho"], query="https://kokusho.nijl.ac.jp/biblio/100000001")
        self.assertEqual(session.source_stats["kokusho"]["status"], "unparsable")
        self.assertEqual(Incident.objects.get(source_code="kokusho").category, "reponse_illisible")

    def test_one_failing_source_does_not_block_the_others(self):
        self.route(ndl="503", jps="mal", cinii="ok")
        session = self.run_search(["local", "ndl", "japansearch", "cinii"])
        statuses = {c: s["status"] for c, s in session.source_stats.items()}
        self.assertEqual(statuses["ndl"], "unavailable")
        self.assertEqual(statuses["japansearch"], "unparsable")
        self.assertEqual(statuses["cinii"], "ok")
        self.assertIn(statuses["local"], ("ok", "empty"))
        self.assertEqual(session.results.filter(catalogue__code="cinii").count(), 2)
        page = self.client.get(f"/recherche/session/{session.uid}/")
        self.assertContains(page, "Source indisponible")
        self.assertContains(page, "Réponse impossible à interpréter")

    def test_ndl_digitized_link_and_jps_fields(self):
        self.route()
        session = self.run_search(["ndl", "japansearch"])
        ndl = session.results.get(catalogue__code="ndl", source_id="900000001")
        self.assertEqual(ndl.data["digital_access_url"], "https://dl.ndl.go.jp/pid/9900001")
        self.assertEqual(ndl.data["norm"]["digital_access"], "image")
        jps = session.results.get(catalogue__code="japansearch", source_id="najda-F0000000000000000001")
        self.assertEqual(jps.data["reading"], "モチヅキケユイショガキ")
        self.assertEqual(jps.data["place_original"], "信濃国")
        self.assertEqual(jps.data["holding_institution_text"], "国立公文書館")
        self.assertTrue(jps.data["image_url"].endswith("manifest.json"))
        page = self.client.get(f"/recherche/session/{session.uid}/resultats/?digital=1&sort=author")
        self.assertContains(page, "Document numérisé")

    def test_japan_search_variants_are_combined_with_or(self):
        router = self.route()
        self.run_search(["japansearch"], variants=["望月千代", "千代女房"])
        keywords = router.requests[0].url.params.get_list("keyword")
        self.assertEqual(keywords, ["+望月千代女", "+望月千代", "+千代女房"])

    def test_nat_archives_filters_on_documented_database(self):
        router = self.route()
        self.run_search(["nat-archives"])
        self.assertEqual(router.requests[0].url.params.get("f-db"), "najda")

    def test_ndl_variant_failure_keeps_main_results(self):
        calls = {"n": 0}

        def transport(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(200, text=fixture("ndl_ok.xml"))
            return httpx.Response(503, text="busy")

        ConnectorHTTP.transport = httpx.MockTransport(transport)
        session = self.run_search(["ndl"], variants=["望月千代"])
        stats = session.source_stats["ndl"]
        self.assertEqual(stats["status"], "warning")
        self.assertEqual(stats["count"], 2)
        self.assertTrue(any("Variante" in w for w in stats["warnings"]))


class CiNiiSecretTests(Evolution120Base):
    def test_appid_is_sent_but_never_recorded(self):
        router = self.route(cinii="403")
        session = self.run_search(["cinii"])
        self.assertEqual(router.requests[0].url.params.get("appid"), APPID)
        self.assertEqual(session.source_stats["cinii"]["status"], "error")
        incident = Incident.objects.get(source_code="cinii")
        self.assertIn("identifiant d'accès", incident.message)
        dump = json.dumps(list(Incident.objects.values()), default=str) + json.dumps(
            list(IncidentOccurrence.objects.values()), default=str) + json.dumps(
            list(IncidentEvent.objects.values()), default=str)
        self.assertNotIn(APPID, dump)
        self.assertIn("appid=[secret masqué]", incident.context["url"])
        for fmt in ("md", "json"):
            export = self.client.get(f"/journal/{incident.uid}/export/?format={fmt}&download=1")
            self.assertEqual(export.status_code, 200)
            body = export.content.decode()
            self.assertNotIn(APPID, body)
            self.assertNotIn(self.admin.username + "@", body)
            self.assertIn(incident.uid, body)
            self.assertIn(settings.APP_VERSION, body)

    @override_settings(CINII_APPID="")
    def test_missing_appid_is_a_configuration_warning(self):
        router = self.route()
        session = self.run_search(["cinii"])
        self.assertEqual(session.source_stats["cinii"]["status"], "error")
        self.assertEqual(router.requests, [], "aucun appel sans identifiant")
        incident = Incident.objects.get(source_code="cinii")
        self.assertEqual((incident.category, incident.severity), ("configuration", "warning"))
        self.assertIn("CINII_APPID", incident.message)


class JournalTests(Evolution120Base):
    def test_identical_failures_are_grouped(self):
        self.route(ndl="503")
        self.run_search(["ndl"])
        cache.clear()
        self.run_search(["ndl"], query="別の語")
        self.assertEqual(Incident.objects.filter(source_code="ndl").count(), 1)
        incident = Incident.objects.get(source_code="ndl")
        self.assertEqual(incident.occurrence_count, 2)
        self.assertEqual(incident.occurrences.count(), 2)
        self.assertEqual(incident.first_seen_version, settings.APP_VERSION)

    def test_fixed_incident_that_reappears_is_reopened_and_compared(self):
        self.route(jps="mal")
        self.run_search(["japansearch"])
        incident = Incident.objects.get(source_code="japansearch")
        change_status(incident, "corrige", self.admin, "Format corrigé")
        self.assertEqual(incident.fixed_in_version, settings.APP_VERSION)
        cache.clear()
        self.run_search(["japansearch"])
        incident.refresh_from_db()
        self.assertEqual(incident.status, "a_analyser")
        self.assertEqual(incident.reappeared_count, 1)
        self.assertTrue(incident.events.filter(kind="reappeared").exists())
        self.assertEqual(incident.events.filter(kind="status").count(), 1, "l'historique de correction est conservé")
        page = self.client.get(incident.get_absolute_url())
        self.assertContains(page, "Avant / après correction")
        self.assertContains(page, "réapparu")
        analysis = self.client.get("/journal/analyse/")
        self.assertContains(analysis, incident.uid)

    def test_recovered_source_is_noted_in_history(self):
        self.route(ndl="503")
        self.run_search(["ndl"])
        cache.clear()
        self.route(ndl="ok")
        self.run_search(["ndl"])
        incident = Incident.objects.get(source_code="ndl")
        self.assertTrue(incident.events.filter(kind="recovered").exists())
        self.assertEqual(incident.status, "nouveau", "le statut n'est pas modifié automatiquement")

    def test_conversion_error_skips_result_and_keeps_others(self):
        self.route()
        original = services._store_one

        def flaky(session, catalogue, res, *args):
            if res.source_id == "900000002":
                raise ValueError("date impossible à convertir")
            return original(session, catalogue, res, *args)

        with mock.patch("apps.searching.services._store_one", side_effect=flaky):
            session = self.run_search(["ndl"])
        stats = session.source_stats["ndl"]
        self.assertEqual((stats["status"], stats["count"]), ("warning", 1))
        incident = Incident.objects.get(category="erreur_traitement")
        self.assertEqual((incident.module, incident.origin), ("metadonnees", "traitement"))
        self.assertTrue(incident.context["traceback"])

    def test_database_error_is_critical(self):
        self.route()
        with mock.patch("apps.searching.services._store_one", side_effect=DatabaseError("disk full")):
            self.run_search(["ndl"])
        incident = Incident.objects.get(category="erreur_critique")
        self.assertEqual(incident.severity, "critical")
        self.assertEqual(incident.occurrence_count, 2)

    def test_unexpected_page_error_is_captured(self):
        from django.core.signals import got_request_exception
        from django.test import RequestFactory

        request = RequestFactory().get("/notices/exemple/?token=abc")
        try:
            raise RuntimeError("panne simulée")
        except RuntimeError:
            got_request_exception.send(sender=None, request=request)
        incident = Incident.objects.get(module="application")
        self.assertEqual(incident.context["path"], "/notices/exemple/")
        self.assertEqual(len(incident.last_request_id), 12, "chaque erreur de page reçoit un identifiant de requête")
        self.assertNotIn("token", json.dumps(incident.context))

    def test_empty_query_is_not_an_incident(self):
        self.route()
        session = services.run_all_sources(services.create_session(self.admin, query="", sources=["ndl"]))
        self.assertEqual(session.source_stats["ndl"]["status"], "error")
        self.assertFalse(Incident.objects.exists())

    def test_list_filters_and_search_by_id(self):
        self.route(ndl="503", jps="mal")
        self.run_search(["ndl", "japansearch"])
        ndl = Incident.objects.get(source_code="ndl")
        jps = Incident.objects.get(source_code="japansearch")
        page = self.client.get("/journal/")
        self.assertContains(page, "Journal des dysfonctionnements")
        self.assertContains(page, ndl.uid)
        for query, present, absent in [
            ("?source=ndl", ndl, jps), ("?severity=error", jps, ndl), ("?module=recherche&severity=warning", ndl, jps),
            (f"?q={jps.uid}", jps, ndl), (f"?q={ndl.last_request_id}", ndl, jps), ("?status=ouverts", ndl, None),
            ("?date_from=2000-01-01&date_to=2999-12-31", ndl, None),
        ]:
            with self.subTest(query=query):
                page = self.client.get("/journal/" + query)
                self.assertContains(page, present.uid)
                if absent:
                    self.assertNotContains(page, absent.uid)
        self.assertNotContains(self.client.get("/journal/?date_to=2000-01-01"), ndl.uid)
        detail = self.client.get(ndl.get_absolute_url())
        self.assertContains(detail, "Source distante")
        self.assertContains(detail, ndl.last_request_id)
        source_page = self.client.get("/sources/ndl/")
        self.assertContains(source_page, "Dysfonctionnements de cette source")
        self.assertContains(source_page, ndl.uid)

    def test_export_preview_and_hidden_terms(self):
        self.route(ndl="503")
        self.run_search(["ndl"], query="望月千代女")
        incident = Incident.objects.get()
        preview = self.client.get(f"/journal/{incident.uid}/export/")
        self.assertContains(preview, "Rapport de diagnostic")
        self.assertContains(preview, "望月千代女")
        hidden = self.client.get(f"/journal/{incident.uid}/export/?format=md&hide_terms=on&download=1").content.decode()
        self.assertNotIn("望月千代女", hidden)
        self.assertIn("[termes masqués]", hidden)
        listing = self.client.get("/journal/export/?source=ndl&format=json&download=1")
        data = json.loads(listing.content)
        self.assertEqual(data["environnement"]["application_version"], settings.APP_VERSION)
        self.assertEqual(data["incidents"][0]["identifiant"], incident.uid)
        self.assertIn("etapes_pour_reproduire", data["incidents"][0])

    def test_manual_report_with_screenshot(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        response = self.client.post("/journal/signaler/", {
            "module": "recherche", "severity": "warning", "description": "Les résultats NDL n'affichent pas la lecture\n"
            "détails…", "steps": "Recherche 望月千代女, source NDL", "expected": "Lecture en kana",
            "obtained": "Champ vide ; mon mot de passe=Secret123456 est masqué ?", "source_code": "ndl",
            "screenshot": SimpleUploadedFile("capture.png", png, content_type="image/png")})
        incident = Incident.objects.get(is_manual=True)
        self.assertRedirects(response, incident.get_absolute_url())
        self.assertEqual(incident.category, "signalement")
        self.assertTrue(incident.screenshot)
        self.assertEqual(self.client.get(f"/journal/{incident.uid}/capture/").status_code, 200)
        page = self.client.get("/journal/?manual=manual")
        self.assertContains(page, "signalement manuel")
        bad = self.client.post("/journal/signaler/", {"module": "recherche", "severity": "info", "description": "x",
                                                      "screenshot": SimpleUploadedFile("x.png", b"not an image")})
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(Incident.objects.filter(is_manual=True).count(), 1)

    def test_status_change_is_reserved_to_admin(self):
        incident = record_incident(module="recherche", category="erreur_technique", severity="error", title="Essai")
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(incident.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.post(f"/journal/{incident.uid}/statut/", {"status": "cloture"}).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(f"/journal/{incident.uid}/statut/", {"status": "en_cours", "comment": "Analyse"})
        incident.refresh_from_db()
        self.assertEqual(incident.status, "en_cours")

    def test_menu_entry_and_badge(self):
        record_incident(module="recherche", category="erreur_technique", severity="error", title="Essai")
        page = self.client.get("/")
        self.assertContains(page, "Dysfonctionnements")
        self.assertContains(page, 'nav-badge')
        self.assertContains(page, f"v{settings.APP_VERSION}")


class RedactionTests(Evolution120Base):
    def test_secrets_are_masked_everywhere(self):
        self.assertEqual(redact_url("https://cir.nii.ac.jp/opensearch/all?q=望月&appid=XYZ&format=json"),
                         "https://cir.nii.ac.jp/opensearch/all?q=望月&appid=[secret masqué]&format=json")
        text = redact("postgres://japon:MotDePasseLong@db/japon token=abcd sk-ant-abcdefghijklmnop "
                      "C:\\Users\\Arnaud\\Documents arnaud@example.org")
        for secret in ("MotDePasseLong", "abcd", "sk-ant-abcdefghijklmnop", "Arnaud", "arnaud@example.org"):
            self.assertNotIn(secret, text)
        incident = record_incident(module="connecteur", category="erreur_technique", severity="error",
                                   title="Échec", message="Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
                                   context={"headers": {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz"},
                                            "password": "x", "url": "https://x.org/a?api_key=K123"})
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", incident.message + json.dumps(incident.context))
        self.assertEqual(incident.context["password"], "[secret masqué]")
        self.assertIn("api_key=[secret masqué]", incident.context["url"])


class SourcesAndVariantsTests(Evolution120Base):
    def test_japan_search_database_finder(self):
        self.route()
        page = self.client.get("/sources/japansearch/bases/?q=公文書館")
        self.assertContains(page, "najda")
        self.assertContains(page, "Déjà configurée")  # Archives nationales préconfigurées
        self.assertContains(page, "Consultation externe uniquement")  # base non diffusée par API
        Catalogue.objects.filter(code="nat-archives").delete()
        response = self.client.post("/sources/japansearch/bases/creer/", {"db_id": "najda", "name": "国立公文書館DA"})
        created = Catalogue.objects.get(config__database="najda")
        self.assertRedirects(response, created.get_absolute_url())
        self.assertFalse(created.enabled_for_search)
        self.assertTrue(created.needs_real_verification)

    def test_japan_search_database_finder_failure_is_logged(self):
        self.route(jps="503")
        page = self.client.get("/sources/japansearch/bases/?q=早稲田")
        self.assertContains(page, "n'a pas pu être obtenue")
        self.assertEqual(Incident.objects.get().module, "connecteur")

    def test_name_variants(self):
        values = [v["value"] for v in suggest_variants("望月千代女")]
        self.assertIn("望月千代", values)
        creator = Creator.objects.create(name_original="望月千代女", name_reading="もちづきちよめ")
        CreatorVariant.objects.create(creator=creator, form="千代女房", verified=True)
        CreatorVariant.objects.create(creator=creator, form="望月千代", verified=False)
        suggestions = {v["value"]: v for v in suggest_variants("望月千代女")}
        self.assertIn("千代女房", suggestions)
        self.assertEqual(suggestions["千代女房"]["verification"], "attestée")
        self.assertIn("望月千代女", [v["value"] for v in suggest_variants("千代女房")])

    def test_free_text_variants_are_sent_to_sources(self):
        self.route()
        Catalogue.objects.filter(code="ndl").update(enabled_for_search=True)
        response = self.client.post("/recherche/lancer/", {"q": "望月千代女", "sources": ["ndl"], "mode": "selective",
                                                           "custom_variants": "望月千代 ; 千代女房"})
        session = services.SearchSession.objects.latest("started_at")
        self.assertEqual(session.variants, ["望月千代", "千代女房"])
        self.assertEqual(response.status_code, 302)


class DataPreservationTests(Evolution120Base):
    def test_existing_catalogue_and_personal_data_are_preserved(self):
        self.route()
        session = self.run_search(["ndl"])
        services.integrate(session, session.results.all(), self.admin)
        record = Record.objects.get(catalogue__code="ndl", source_id="900000001")
        entry = LibraryEntry.objects.get(user=self.admin, record=record)
        entry.favorite = True
        entry.save()
        Annotation.objects.create(author=self.admin, record=record, body="Ma note personnelle")
        before = Record.objects.count()
        # La source renvoie ensuite un titre modifié : la notice est versionnée, rien n'est écrasé silencieusement.
        cache.clear()
        modified = fixture("ndl_ok.xml").replace("架空資料 甲州歩き巫女考", "架空資料 甲州歩き巫女考（改訂）")
        ConnectorHTTP.transport = httpx.MockTransport(lambda r: httpx.Response(200, text=modified))
        session2 = self.run_search(["ndl"])
        result = session2.results.get(source_id="900000001")
        self.assertEqual(result.comparison, "modified")
        services.integrate(session2, [result], self.admin)
        record.refresh_from_db()
        self.assertEqual(Record.objects.count(), before)
        last = RecordVersion.objects.filter(record=record).latest("version")
        self.assertIn("original_title", last.changed_fields)
        self.assertEqual(last.previous_values["original_title"], "架空資料 甲州歩き巫女考")
        entry.refresh_from_db()
        self.assertTrue(entry.favorite)
        self.assertEqual(record.annotations.get().body, "Ma note personnelle")
        # Les erreurs de source n'altèrent pas le catalogue.
        cache.clear()
        self.route(ndl="mal")
        self.run_search(["ndl"])
        self.assertEqual(Record.objects.count(), before)


class VersionTests(Evolution120Base):
    def test_single_version_number(self):
        root = Path(settings.BASE_DIR)
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        # 1.3.0 : la valeur exacte est vérifiée dans test_evolution_130 ; ici, la cohérence du numéro unique.
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(settings.APP_VERSION, version)
        compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn(f"image: japon-explorateur:{version}", compose)
        self.assertIn("japon-explorateur-essai", compose, "l'installation d'essai a ses propres volumes")
        self.assertIn(version, self.client.get("/").content.decode())


class DependencyTests(Evolution120Base):
    def test_celery_redis_transport_is_importable(self):
        """Régression 1.2.0 (INC-20261113-41FDF0) : kombu 5.7 importe « packaging » sans le déclarer.

        Les tests exécutent les tâches sans worker (mode « eager ») et ne chargeaient donc jamais le transport
        Redis utilisé sous Docker ; ce test l'importe explicitement.
        """
        import importlib

        importlib.import_module("kombu.transport.redis")
        from config.celery import app

        self.assertTrue(app.conf.broker_url is None or isinstance(app.conf.broker_url, str))


class RefreshScopeTests(Evolution120Base):
    """INC-20261113-0AB9C5 : « Actualiser » sur NDL créait un faux incident « Erreur technique »."""

    def test_search_only_connectors_cannot_be_refreshed(self):
        for code in ("ndl", "japansearch", "nat-archives", "cinii", "cinii-books"):
            self.assertFalse(Catalogue.objects.get(code=code).can_refresh, code)
        self.assertTrue(Catalogue.objects.get(code="kokusho").can_refresh)
        page = self.client.get("/sources/ndl/")
        self.assertNotContains(page, "/mises-a-jour/source/ndl/lancer/")
        self.assertNotContains(page, "> Actualiser</button>")
        self.assertContains(page, "Sans objet")
        self.assertContains(self.client.get("/sources/kokusho/"), "Actualiser")
        self.assertContains(self.client.get("/mises-a-jour/"), "pas d'actualisation")

    def test_refresh_request_is_refused_without_incident(self):
        from django.urls import reverse
        from apps.updates.models import SyncJob
        from apps.updates.services import due_catalogues, run_sync

        response = self.client.post(reverse("updates:sync_launch", args=["ndl"]), {"kind": "incremental"})
        self.assertRedirects(response, "/sources/ndl/")
        self.assertFalse(SyncJob.objects.filter(catalogue__code="ndl").exists())
        # Même si une actualisation est déclenchée autrement : échec expliqué, aucun incident.
        job = run_sync(SyncJob.objects.create(catalogue=Catalogue.objects.get(code="ndl"), kind="incremental"))
        self.assertEqual(job.status, "failed")
        self.assertIn("sert aux recherches", job.message)
        self.assertFalse(Incident.objects.exists())
        Catalogue.objects.filter(code="ndl").update(frequency="daily", last_attempt_at=None, status="available")
        self.assertNotIn("ndl", [c.code for c in due_catalogues()])
        self.client.post(reverse("updates:sync_all"))
        self.assertEqual(SyncJob.objects.filter(catalogue__code="ndl").count(), 1)
