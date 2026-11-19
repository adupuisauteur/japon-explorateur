"""2.0.0 — lot 2 : trois statuts indépendants par notice, vérification du manifeste IIIF, interface.

Données fictives ; aucun appel réseau (transport HTTP simulé)."""
import importlib
import json
from unittest import mock

import httpx
from django.apps import apps as django_apps
from django.db import connection
from django.test import override_settings

from apps.catalog import iiif, statuses
from apps.catalog.models import Record, RecordStatus
from apps.catalog.services import build_unsaved_record, upsert_record
from apps.connectors.http import ConnectorHTTP
from apps.incidents.models import Incident
from apps.library.models import LibraryEntry

from .helpers import AppTestCase

MANIFEST_V3 = "https://iiif.example.org/fictif/v3/manifest.json"
MANIFEST_V2 = "https://iiif.example.org/fictif/v2/manifest.json"
IMAGE_SERVICE = "https://iiif.example.org/image/fictif-1"


def manifest_v3(views=3):
    return {
        "@context": "http://iiif.io/api/presentation/3/context.json", "id": MANIFEST_V3, "type": "Manifest",
        "label": {"ja": ["架空の書"]},
        "items": [{"id": f"{MANIFEST_V3}/canvas/{i}", "type": "Canvas", "items": [{
            "type": "AnnotationPage", "items": [{"type": "Annotation", "body": {
                "id": f"{IMAGE_SERVICE}/full/max/0/default.jpg", "type": "Image",
                "service": [{"id": IMAGE_SERVICE, "type": "ImageService3"}]}}]}]} for i in range(views)],
    }


def manifest_v2(views=2):
    return {
        "@context": "http://iiif.io/api/presentation/2/context.json", "@id": MANIFEST_V2, "@type": "sc:Manifest",
        "sequences": [{"canvases": [{"@id": f"{MANIFEST_V2}/c{i}", "images": [{"resource": {
            "@id": f"{IMAGE_SERVICE}/full/full/0/default.jpg", "service": {"@id": IMAGE_SERVICE}}}]}
            for i in range(views)]}],
    }


class FakeSite:
    """Site IIIF simulé : manifeste et image, avec des réponses réglables."""

    def __init__(self, manifest=None, image_status=200, image_type="image/jpeg", manifest_status=200, text=None):
        self.manifest, self.image_status, self.image_type = manifest, image_status, image_type
        self.manifest_status, self.text, self.requests = manifest_status, text, []

    def __call__(self, request):
        self.requests.append(str(request.url))
        url = str(request.url)
        if url.startswith(IMAGE_SERVICE):
            return httpx.Response(self.image_status, content=b"\xff\xd8" + b"0" * 2000,
                                  headers={"content-type": self.image_type})
        if self.text is not None:
            return httpx.Response(self.manifest_status, text=self.text, headers={"content-type": "text/html"})
        return httpx.Response(self.manifest_status, json=self.manifest)


class StatusTestCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(setattr, ConnectorHTTP, "transport", None)

    def jps(self, common, source_id="najda-FICTIF-1", catalogue="japansearch"):
        item = {"id": source_id, "common": {"title": "架空文書", "linkUrl": "https://jpsearch.example/item/1",
                                            **common}}
        from apps.connectors.japansearch import parse_item

        parsed = parse_item(item)
        record, _ = upsert_record(self.catalogue(catalogue), parsed.data, raw=parsed.raw,
                                  raw_format=parsed.raw_format)
        return record

    def status(self, record, kind):
        return RecordStatus.objects.get(record=record, kind=kind)

    def with_manifest(self, url=MANIFEST_V3, catalogue="codh-pmjt"):
        record, _ = upsert_record(self.catalogue(catalogue), {
            "source_id": f"IIIF-{url.split('/')[-2]}", "original_title": "架空の書", "image_url": url,
            "source_url": "https://example.org/notice/iiif"}, raw_format="csv")
        return record


class DerivationTests(StatusTestCase):
    """Règles de calcul, sans appel réseau : un « oui » ou un « absent » seulement si la source le dit."""

    def test_japan_search_with_manifest_and_content(self):
        record = self.jps({"iiifUrl": MANIFEST_V3, "contentsUrl": "https://jpsearch.example/contents/1"})
        self.assertEqual((self.status(record, "notice").value, self.status(record, "notice").origin), ("oui", "source"))
        self.assertEqual(self.status(record, "document").value, "oui")
        iiif_row = self.status(record, "iiif")
        self.assertEqual((iiif_row.value, iiif_row.origin, iiif_row.url), ("identifie", "source", MANIFEST_V3))

    def test_japan_search_without_digital_content(self):
        record = self.jps({"thumbnailUrl": "https://jpsearch.example/thumb.jpg"})
        self.assertEqual(self.status(record, "document").value, "non_verifie")  # une vignette ne suffit pas
        self.assertEqual((self.status(record, "iiif").value, self.status(record, "iiif").origin), ("absent", "source"))

    def test_kokusho_manifest_address_built_by_jed_is_deduced(self):
        """Décision D5 : adresse construite à partir de l'identifiant → « identifié », origine « déduit »."""
        record = self.jps({}, source_id="100001234", catalogue="kokusho")
        record.image_url = "https://kokusho.nijl.ac.jp/biblio/100001234/manifest"
        record.save()
        row = self.status(record, "iiif")
        self.assertEqual((row.value, row.origin), ("identifie", "deduit"))
        self.assertEqual(self.status(record, "document").value, "non_verifie")  # aucun statut déduit d'un autre

    def test_kokusho_official_manifest(self):
        from apps.connectors.kokusho import parse_manifest

        parsed = parse_manifest("100005678", manifest_v2())
        record, _ = upsert_record(self.catalogue("kokusho"), parsed.data, raw=parsed.raw,
                                  raw_format=parsed.raw_format)
        self.assertEqual(self.status(record, "document").value, "oui")
        self.assertEqual((self.status(record, "iiif").value, self.status(record, "iiif").origin),
                         ("identifie", "source"))

    def test_ndl_digitization_link_is_not_proof_of_open_access(self):
        record, _ = upsert_record(self.catalogue("ndl"), {
            "source_id": "NDL-FICTIF", "original_title": "架空の本", "source_url": "https://ndlsearch.example/1",
            "digital_access_url": "https://dl.ndl.go.jp/pid/0000001"}, raw={"title": "架空の本"},
            raw_format="ndl-opensearch")
        document = self.status(record, "document")
        self.assertEqual((document.value, document.url), ("non_verifie", "https://dl.ndl.go.jp/pid/0000001"))
        self.assertIn("non précisé", document.detail)
        # 2.0.0 (lot 10) : adresse du manifeste construite par J-ed, vérifiable ; l'accès reste « non vérifié »
        iiif = self.status(record, "iiif")
        self.assertEqual((iiif.value, iiif.origin, iiif.url),
                         ("identifie", "deduit", "https://dl.ndl.go.jp/api/iiif/0000001/manifest.json"))
        self.assertEqual(record.digital_access, "image")  # ancien champ inchangé (exports 1.0)

    def test_ndl_without_anything_has_no_manifest(self):
        record, _ = upsert_record(self.catalogue("ndl"), {
            "source_id": "NDL-FICTIF-2", "original_title": "架空の本", "source_url": "https://ndlsearch.example/2"},
            raw={}, raw_format="ndl-opensearch")
        self.assertEqual(self.status(record, "iiif").value, "absent")

    def test_cinii_full_text_is_not_verified(self):
        record, _ = upsert_record(self.catalogue("cinii"), {
            "source_id": "CRID-FICTIF", "original_title": "架空論文", "source_url": "https://cir.example/crid/1",
            "digital_access_url": "https://publisher.example/full.pdf"}, raw={}, raw_format="cinii-jsonld")
        self.assertEqual(self.status(record, "document").value, "non_verifie")

    def test_import_file_declared_values(self):
        cat = self.catalogue("codh-pmjt")
        declared, _ = upsert_record(cat, {"source_id": "IMP-1", "original_title": "架空", "digital_access": "image",
                                          "digital_access_url": "https://example.org/v/1"},
                                    raw={"titre": "架空", "acces": "image"}, raw_format="csv")
        self.assertEqual((self.status(declared, "document").value, self.status(declared, "document").origin),
                         ("oui", "source"))
        guessed, _ = upsert_record(cat, {"source_id": "IMP-2", "original_title": "架空",
                                         "digital_access_url": "https://example.org/v/2"},
                                   raw={"titre": "架空"}, raw_format="csv")
        self.assertEqual(guessed.digital_access, "image")  # complété par la règle de la 1.2.0…
        self.assertEqual(self.status(guessed, "document").value, "non_verifie")  # … qui ne fait pas un statut

    def test_on_site_consultation_is_not_consultable_but_mentioned(self):
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {
            "source_id": "IMP-3", "original_title": "架空", "digital_access_url": "https://example.org/v/3",
            "rights_and_access": "デジタル化済み・館内限定公開"}, raw={}, raw_format="csv")
        document = self.status(record, "document")
        self.assertEqual((document.value, document.origin), ("non", "source"))
        self.assertIn("consultation réservée", document.detail)
        self.assertIn("館内限定", document.detail)

    def test_local_withdrawn_and_constructed_addresses(self):
        local, _ = upsert_record(self.catalogue("local"), {"source_id": "LOC-1", "original_title": "架空"})
        self.assertEqual(self.status(local, "notice").value, "non")
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {
            "source_id": "IMP-4", "original_title": "架空", "source_url": "https://example.org/n/4"}, raw_format="csv")
        record.record_status = "withdrawn"
        record.save()
        self.assertEqual((self.status(record, "notice").value, self.status(record, "notice").origin), ("non", "jed"))
        record.record_status, record.source_url_verified = "active", False
        record.save()
        self.assertEqual((self.status(record, "notice").value, self.status(record, "notice").origin),
                         ("non_verifie", "deduit"))

    def test_unsaved_search_result(self):
        unsaved = build_unsaved_record(self.catalogue("japansearch"), {"source_id": "x", "original_title": "架空"},
                                       {"common": {"iiifUrl": MANIFEST_V3}}, "jpsearch-json")
        data = statuses.derive_dict(unsaved)
        self.assertEqual(data["iiif"]["value"], "identifie")
        self.assertEqual(set(data), {"notice", "document", "iiif"})


class RefreshTests(StatusTestCase):
    def test_three_rows_per_record_and_record_untouched(self):
        record = self.with_manifest()
        self.assertEqual(RecordStatus.objects.filter(record=record).count(), 3)
        before = (record.version, record.record_hash, record.digital_access)
        record.refresh_from_db()
        statuses.refresh(record)
        record.refresh_from_db()
        self.assertEqual((record.version, record.record_hash, record.digital_access), before)

    def test_jed_verification_survives_a_resave_with_the_same_manifest(self):
        record = self.with_manifest()
        RecordStatus.objects.filter(record=record, kind="iiif").update(value="verifie", origin="jed",
                                                                         detail="IIIF 3.0 · 3 vue(s)")
        record.save()
        self.assertEqual(self.status(record, "iiif").value, "verifie")
        record.image_url = MANIFEST_V2
        record.save()
        row = self.status(record, "iiif")
        self.assertEqual((row.value, row.origin, row.url), ("identifie", "source", MANIFEST_V2))

    def test_pending_check_is_dropped_when_the_manifest_changes(self):
        record = self.with_manifest()
        iiif.request_checks([record], self.researcher)
        record.image_url = MANIFEST_V2
        record.save()
        self.assertIsNone(self.status(record, "iiif").check_requested_at)


class DataMigrationTests(StatusTestCase):
    """La migration calcule les statuts existants sans appel réseau et sans modifier les notices."""

    def test_fill_and_empty(self):
        module = importlib.import_module("apps.catalog.migrations.0007_statuts_notices_existantes")
        record = self.jps({"iiifUrl": MANIFEST_V3})
        RecordStatus.objects.all().delete()
        snapshot = list(Record.objects.order_by("pk").values_list("pk", "version", "record_hash", "updated_at"))
        with mock.patch("httpx.Client.send", side_effect=AssertionError("aucun appel réseau")):
            module.fill(django_apps, mock.Mock(connection=connection))
        self.assertEqual(RecordStatus.objects.count(), 3 * Record.objects.count())
        self.assertEqual(self.status(record, "iiif").value, "identifie")
        self.assertEqual(snapshot, list(Record.objects.order_by("pk").values_list("pk", "version", "record_hash",
                                                                                   "updated_at")))
        module.fill(django_apps, mock.Mock(connection=connection))  # relançable sans doublon
        self.assertEqual(RecordStatus.objects.count(), 3 * Record.objects.count())
        module.empty(django_apps, mock.Mock(connection=connection))
        self.assertEqual(RecordStatus.objects.count(), 0)
        self.assertEqual(Record.objects.count(), len(snapshot))


class InspectTests(AppTestCase):
    def test_v3_v2_and_collection(self):
        info = iiif.inspect(manifest_v3(4))
        self.assertEqual((info["version"], info["views"], info["image"]),
                         ("3.0", 4, f"{IMAGE_SERVICE}/full/200,/0/default.jpg"))
        info = iiif.inspect(manifest_v2(2))
        self.assertEqual((info["version"], info["views"]), ("2.x", 2))
        info = iiif.inspect({"@context": "http://iiif.io/api/presentation/2/context.json", "@type": "sc:Collection",
                             "manifests": [{"@id": MANIFEST_V2}]})
        self.assertEqual((info["type"], info["members"]), ("collection", [MANIFEST_V2]))

    def test_non_conforming_documents(self):
        for bad, message in (([], "objet JSON"), ({"title": "x"}, "ni l'API de présentation"),
                             ({"@context": "http://iiif.io/api/presentation/3/context.json", "type": "Canvas"},
                              "Type IIIF inattendu"),
                             (manifest_v3(0), "aucune vue")):
            with self.assertRaisesMessage(iiif.ManifestError, message):
                iiif.inspect(bad)


@override_settings(IIIF_CHECK_DELAY_SECONDS=0)
class VerificationTests(StatusTestCase):
    def verify(self, site, record=None):
        ConnectorHTTP.transport = httpx.MockTransport(site)
        record = record or self.with_manifest()
        iiif.request_checks([record], self.researcher)
        iiif.run_pending()
        return self.status(record, "iiif")

    def test_verified_manifest(self):
        row = self.verify(FakeSite(manifest_v3(5)))
        self.assertEqual((row.value, row.origin), ("verifie", "jed"))
        self.assertIn("IIIF 3.0 · 5 vue(s)", row.detail)
        self.assertIsNotNone(row.checked_at)
        self.assertIsNone(row.check_requested_at)

    def test_unreachable_image(self):
        row = self.verify(FakeSite(manifest_v3(), image_status=403))
        self.assertEqual((row.value, row.origin), ("echec", "jed"))
        self.assertIn("HTTP 403", row.detail)
        incident = Incident.objects.get(technical_code="image_http_403")
        self.assertEqual(incident.module, "metadonnees")

    def test_not_a_manifest_and_not_an_image(self):
        row = self.verify(FakeSite(text="<html>page</html>"))
        self.assertEqual(row.value, "echec")
        self.assertIn("pas du JSON", row.detail)
        record = self.with_manifest(MANIFEST_V2)
        row = self.verify(FakeSite(manifest_v2(), image_type="text/html"), record)
        self.assertIn("ne renvoie pas une image", row.detail)

    def test_network_failure_is_reported_not_hidden(self):
        def down(request):
            raise httpx.ConnectError("refusé")

        row = self.verify(down)
        self.assertEqual(row.value, "echec")
        self.assertIn("Manifeste injoignable", row.detail)

    def test_collection_checks_its_first_manifest(self):
        site = FakeSite(manifest_v2())
        collection = {"@context": "http://iiif.io/api/presentation/2/context.json", "@type": "sc:Collection",
                      "manifests": [{"@id": MANIFEST_V2}]}
        ConnectorHTTP.transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json=collection) if str(r.url) == MANIFEST_V3 else site(r))
        record = self.with_manifest()
        iiif.request_checks([record], self.researcher)
        iiif.run_pending()
        self.assertIn("Collection de 1 manifeste(s)", self.status(record, "iiif").detail)

    def test_requests_are_resumable_and_ordered(self):
        site = FakeSite(manifest_v3())
        ConnectorHTTP.transport = httpx.MockTransport(site)
        first, second = self.with_manifest(), self.with_manifest(MANIFEST_V2)
        queued, skipped = iiif.request_checks([first, second], self.researcher)
        self.assertEqual((queued, skipped), (2, 0))
        self.assertEqual(iiif.run_pending(limit=1), 1)  # arrêt après une notice (Docker arrêté…)
        self.assertEqual(iiif.pending().count(), 1)
        self.assertEqual(self.status(first, "iiif").value, "verifie")
        self.assertEqual(iiif.run_pending(), 1)  # reprise : seule la seconde est traitée
        self.assertEqual(iiif.pending().count(), 0)

    def test_lock_prevents_two_runs(self):
        from django.core.cache import cache

        record = self.with_manifest()
        iiif.request_checks([record], self.researcher)
        cache.add(iiif.LOCK_KEY, "1", 60)
        self.addCleanup(cache.delete, iiif.LOCK_KEY)
        self.assertEqual(iiif.run_pending(), 0)
        self.assertEqual(iiif.pending().count(), 1)

    def test_records_without_manifest_are_skipped(self):
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "NO-IIIF", "original_title": "架空"},
                                  raw_format="csv")
        self.assertEqual(iiif.request_checks([record], self.researcher), (0, 1))

    def test_delay_between_sites(self):
        ConnectorHTTP.transport = httpx.MockTransport(FakeSite(manifest_v3()))
        iiif.request_checks([self.with_manifest(), self.with_manifest(MANIFEST_V2)], self.researcher)
        with mock.patch("apps.catalog.iiif.time.sleep") as sleep:
            iiif.run_pending(delay=2.5)
        self.assertEqual([c for c in sleep.call_args_list if c == mock.call(2.5)], [mock.call(2.5)])


@override_settings(IIIF_CHECK_DELAY_SECONDS=0)
class InterfaceTests(StatusTestCase):
    def setUp(self):
        super().setUp()
        ConnectorHTTP.transport = httpx.MockTransport(FakeSite(manifest_v3()))
        self.record = self.with_manifest()
        self.plain, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "PLAIN", "original_title": "素"},
                                      raw_format="csv")
        for record in (self.record, self.plain):
            LibraryEntry.objects.create(user=self.researcher, record=record)
        self.client.force_login(self.researcher)

    def test_record_page_shows_details_and_button(self):
        page = self.client.get(self.record.get_absolute_url())
        self.assertContains(page, "Disponibilité")
        self.assertContains(page, "IIIF : identifié")
        self.assertContains(page, MANIFEST_V3)
        self.assertContains(page, "Vérifier le manifeste IIIF")
        self.assertNotContains(self.client.get(self.plain.get_absolute_url()), "Vérifier le manifeste IIIF")
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get(self.record.get_absolute_url()), "Vérifier le manifeste IIIF")
        self.assertEqual(self.client.post(f"/notices/{self.record.record_id}/verifier-iiif/").status_code, 403)

    def test_verify_from_record_page(self):
        response = self.client.post(f"/notices/{self.record.record_id}/verifier-iiif/", follow=True)
        self.assertContains(response, "Vérification du manifeste IIIF lancée")
        self.assertEqual(self.status(self.record, "iiif").value, "verifie")  # tâche exécutée immédiatement en test
        self.assertContains(self.client.get(self.record.get_absolute_url()), "vérifié par J-ed")

    def test_library_pills_filters_sort_and_bulk_check(self):
        page = self.client.get("/bibliotheque/")
        self.assertContains(page, "status-pills", count=2)
        self.assertContains(page, 'name="status_iiif"')
        page = self.client.get("/bibliotheque/?status_iiif=identifie")
        self.assertContains(page, "架空の書")
        self.assertNotContains(page, "素</a>")
        page = self.client.get("/bibliotheque/?sort=status_iiif")
        html = page.content.decode()
        self.assertLess(html.index("架空の書"), html.index("素</a>"))
        entries = LibraryEntry.objects.filter(user=self.researcher).values_list("pk", flat=True)
        response = self.client.post("/bibliotheque/lot/", {"entry_ids": list(entries), "action": "iiif"},
                                    follow=True)
        self.assertContains(response, "Vérification du manifeste IIIF lancée pour 1 notice(s)")
        self.assertContains(response, "1 notice(s) sans manifeste IIIF connu")
        self.assertEqual(self.status(self.record, "iiif").value, "verifie")

    def test_local_search_filters_by_status(self):
        from apps.connectors.base import SearchQuery
        from apps.catalog.search import local_search

        hits = local_search(SearchQuery(text="", filters={"status_iiif": ["identifie"]}))
        ids = {r.record_id for r in hits}
        self.assertIn(self.record.record_id, ids)
        self.assertNotIn(self.plain.record_id, ids)

    def test_search_form_offers_three_status_filters(self):
        page = self.client.get("/recherche/")
        for name in ("status_notice", "status_document", "status_iiif"):
            self.assertContains(page, f'name="{name}"')
        self.assertNotContains(page, 'name="digital_access"')


class SessionResultsTests(StatusTestCase):
    def test_session_filters_and_sort(self):
        from apps.searching import services as search_services
        from apps.searching.models import SearchResult

        session = search_services.create_session(self.researcher, query="架空", sources=["japansearch"])
        cat = self.catalogue("japansearch")
        with_manifest = {"source_id": "a", "original_title": "甲", "norm": {"statuses": {
            "notice": {"value": "oui"}, "document": {"value": "oui"}, "iiif": {"value": "identifie"}}}}
        without = {"source_id": "b", "original_title": "乙", "norm": {"statuses": {
            "notice": {"value": "oui"}, "document": {"value": "non_verifie"}, "iiif": {"value": "absent"}}}}
        old = {"source_id": "c", "original_title": "丙", "norm": {}}  # résultat d'avant la 2.0.0
        for rank, data in enumerate((without, with_manifest, old)):
            SearchResult.objects.create(session=session, catalogue=cat, source_id=data["source_id"], rank=rank,
                                        data=data)
        self.client.force_login(self.researcher)
        url = f"/recherche/session/{session.uid}/resultats/"
        page = self.client.get(url, {"status_document": "oui"}).content.decode()
        self.assertIn("甲", page)
        self.assertNotIn("乙", page)
        page = self.client.get(url, {"status_document": "non_verifie"}).content.decode()
        self.assertIn("乙", page)
        self.assertIn("丙", page)  # statut non calculé = non vérifié
        page = self.client.get(url, {"sort": "status_iiif"}).content.decode()
        self.assertLess(page.index("甲"), page.index("乙"))
        self.assertIn("IIIF : identifié", page)


class StatusPillsTagTests(AppTestCase):
    def test_three_distinct_pills_with_details_in_title(self):
        from apps.core.templatetags.app_tags import status_pills

        html = status_pills({"notice": {"value": "oui", "origin": "source", "checked_at": "2026-11-15T10:00:00+01:00"},
                             "iiif": {"value": "echec", "origin": "jed", "detail": "HTTP 403"}})
        self.assertEqual(html.count("chip-status"), 3)
        self.assertIn("Notice : oui", html)
        self.assertIn("Document : non vérifié", html)
        self.assertIn("IIIF : vérification en échec", html)
        self.assertIn("déclaré par la source — 15/11/2026", html)
        self.assertIn("vérifié par J-ed — HTTP 403", html)
        self.assertNotIn("<script", json.dumps(html))


class ExportTests(StatusTestCase):
    """Décision du 15 novembre 2026 : les trois statuts figurent dans les exports."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)
        self.record = self.with_manifest()

    def export(self, fmt, profile="bibliography"):
        from pathlib import Path

        from django.conf import settings

        from apps.exports.models import ExportJob

        self.client.post("/exports/preparer/", {"scope": "selection", "records": self.record.record_id,
                                                "preset": "bibliography", "format": fmt, "title": "Statuts",
                                                "column_profile": profile, "csv_separator": "semicolon"})
        job = ExportJob.objects.latest("pk")
        self.assertEqual(job.status, "done", job.error)
        return job, Path(settings.MEDIA_ROOT)

    def test_readable_formats_show_availability(self):
        from docx import Document

        job, media = self.export("docx")
        text = "\n".join(c.text for t in Document(media / job.files.get(role="main").path).tables
                         for row in t.rows for c in row.cells)
        text += "\n".join(p.text for p in Document(media / job.files.get(role="main").path).paragraphs)
        self.assertIn("Notice : oui · Document : non vérifié · IIIF : identifié", text)
        self.assertNotIn("Accès numérique", text)
        job, media = self.export("txt")
        self.assertIn("Disponibilité", (media / job.files.get(role="main").path).read_text(encoding="utf-8"))

    def test_csv_columns_and_their_documentation(self):
        import csv

        job, media = self.export("csv")
        with open(media / job.files.get(role="main").path, encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        header, values = rows[0], dict(zip(rows[0], rows[1]))
        for column in ("status_notice", "status_document", "status_iiif"):
            self.assertIn(column, header)
        self.assertEqual((values["status_notice"], values["status_iiif"]), ("oui", "identifie"))
        doc = (media / job.files.get(role="schema").path).read_text(encoding="utf-8-sig")
        self.assertIn("Manifeste IIIF : absent, identifie, verifie, echec, non_verifie", doc)
        job, media = self.export("csv", profile="generic")  # profil de réimport : inchangé
        with open(media / job.files.get(role="main").path, encoding="utf-8-sig") as fh:
            self.assertNotIn("status_iiif", fh.readline())

    def test_json_keeps_details_and_origin(self):
        import json as json_module

        RecordStatus.objects.filter(record=self.record, kind="iiif").update(value="verifie", origin="jed",
                                                                              detail="IIIF 3.0 · 3 vue(s)")
        job, media = self.export("json")
        data = json_module.loads((media / job.files.get(role="main").path).read_text(encoding="utf-8"))
        item = data["records"][0]
        self.assertEqual(item["statuses"]["iiif"]["value"], "verifie")
        self.assertEqual(item["statuses"]["iiif"]["origin_label"], "vérifié par J-ed")
        self.assertEqual(item["statuses"]["iiif"]["url"], MANIFEST_V3)
        self.assertNotIn("status_iiif", item)
        self.assertEqual(item["digital_access"], self.record.digital_access)  # ancien champ conservé (format 1.0)

    def test_html_site_badges(self):
        import zipfile

        job, media = self.export("html")
        with zipfile.ZipFile(media / job.files.get(role="main").path) as zf:
            section = next(n for n in zf.namelist() if n.endswith("/sections/section-1.html"))
            page = zf.read(section).decode("utf-8")
        self.assertIn('<span class="badge">IIIF : identifié</span>', page)
