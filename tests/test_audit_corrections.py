"""Tests de non-régression des anomalies relevées par l'audit (corrections 1 à 13).

Chaque test reproduit le défaut constaté et vérifie qu'il ne se produit plus.
"""
import csv
import gzip
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

import httpx
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.ai.models import AIPreferenceProfile, AIProviderCredential, AITask
from apps.ai.preferences import INITIAL_PREFERENCES, active_profile
from apps.ai.providers import OpenAICompatibleProvider, ProviderError
from apps.ai.services import PURGED_PAYLOAD, purge_payload_if_needed, purge_stale_drafts
from apps.ai.urlsafety import UnsafeProviderURL, check_provider_url
from apps.backups.services import create_backup, restore_backup
from apps.catalog.models import Catalogue, EditorialContent, Record
from apps.catalog.services import clean_source_data, record_editorial_change, upsert_record
from apps.exports.models import ExportJob
from apps.library.models import Collection, CorrectionProposal
from apps.updates.importers import _generic_xml_rows

from .helpers import TMP, AppTestCase

ROOT = Path(__file__).resolve().parent.parent


# --- Correction 1 : restauration de secours (JSON) -----------------------------------------------

@override_settings(MEDIA_ROOT=TMP + "/files-c1", BACKUP_DIR=Path(TMP) / "backups-c1")
class JsonFallbackRestoreTests(TransactionTestCase):
    def setUp(self):
        call_command("seed_sources", verbosity=0)
        self.admin = User.objects.create_user("admin", password="motdepasse-solide-1", role="admin")
        cat = Catalogue.objects.get(code="codh-pmjt")
        upsert_record(cat, {"source_id": "J1", "original_title": "方丈記"})
        upsert_record(cat, {"source_id": "J2", "original_title": "徒然草"})

    def _json_backup(self):
        with mock.patch("apps.backups.services.shutil.which", return_value=None):
            job = create_backup("full", user=self.admin)
        self.assertEqual(job.status, "done", job.message)
        self.assertIn("pg_dump introuvable", job.message, "la raison du mode de secours doit être consignée")
        with tarfile.open(job.path) as tar:
            self.assertIn("database.json.gz", tar.getnames())
        return job

    def test_json_backup_restores(self):
        job = self._json_backup()
        Record.objects.filter(source_id="J1").delete()
        restore_backup(job.path, restore_files=False)
        self.assertTrue(Record.objects.filter(source_id="J1", original_title="方丈記").exists())
        self.assertTrue(Record.objects.filter(source_id="J2").exists())

    def test_failed_loaddata_leaves_database_intact(self):
        job = self._json_backup()
        Record.objects.filter(source_id="J1").delete()
        before = Record.objects.count()
        with mock.patch("apps.backups.services.management.call_command",
                        side_effect=[None, RuntimeError("échec simulé de loaddata")]):
            with self.assertRaises(RuntimeError):
                restore_backup(job.path, restore_files=False)
        self.assertEqual(Record.objects.count(), before, "la base ne doit pas être vidée par une restauration échouée")
        self.assertTrue(User.objects.filter(username="admin").exists())

    def test_corrupted_json_is_refused_before_any_change(self):
        job = self._json_backup()
        work = Path(TMP) / "corrompu"
        work.mkdir(parents=True, exist_ok=True)
        with tarfile.open(job.path) as tar:
            tar.extractall(work, filter="data")
        (work / "database.json.gz").write_bytes(gzip.compress(b"[]"))
        manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
        import hashlib

        manifest["files"]["database.json.gz"]["sha256"] = hashlib.sha256((work / "database.json.gz").read_bytes()).hexdigest()
        (work / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        bad = Path(TMP) / "corrompu.tar"
        with tarfile.open(bad, "w") as tar:
            for p in work.iterdir():
                tar.add(p, arcname=p.name)
        before = Record.objects.count()
        with self.assertRaises(ValueError):
            restore_backup(bad, restore_files=False)
        self.assertEqual(Record.objects.count(), before)


# --- Correction 2 : clé secrète de développement ----------------------------------------------------

class SecretKeyTests(AppTestCase):
    def _check(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DATABASE_URL", "SECURE_", "SETUP_"))}
        base.update(env)
        return subprocess.run([sys.executable, "manage.py", "check"], cwd=ROOT, env=base,
                              capture_output=True, text=True, timeout=120)

    def test_production_refuses_missing_or_placeholder_key(self):
        for key in ("", "à-remplacer", "court"):
            r = self._check(DJANGO_DEBUG="false", DJANGO_SECRET_KEY=key)
            self.assertNotEqual(r.returncode, 0, key)
            self.assertIn("DJANGO_SECRET_KEY", r.stderr)

    def test_production_accepts_strong_key(self):
        r = self._check(DJANGO_DEBUG="false", DJANGO_SECRET_KEY="x7!" + "k" * 30 + "Qz9-" + "p" * 20)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])

    def test_https_requires_setup_token(self):
        strong = "x7!" + "k" * 30 + "Qz9-" + "p" * 20
        r = self._check(DJANGO_DEBUG="false", DJANGO_SECRET_KEY=strong, SECURE_HTTPS="true")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SETUP_TOKEN", r.stderr)
        r = self._check(DJANGO_DEBUG="false", DJANGO_SECRET_KEY=strong, SECURE_HTTPS="true", SETUP_TOKEN="jeton-test-123")
        self.assertEqual(r.returncode, 0, r.stderr[-800:])

    def test_generate_secrets_prints_all_values(self):
        out = io.StringIO()
        call_command("generate_secrets", stdout=out)
        text = out.getvalue()
        for name in ("DJANGO_SECRET_KEY=", "AI_KEYS_ENCRYPTION_KEY=", "POSTGRES_PASSWORD=", "SETUP_TOKEN="):
            self.assertIn(name, text)


# --- Corrections 3 et 4 : IA (adresses, confidentialité, permissions) ------------------------------

class AISecurityTests(AppTestCase):
    def test_store_inputs_defaults_to_false(self):
        self.assertFalse(INITIAL_PREFERENCES["store_inputs"])
        self.assertFalse(AIPreferenceProfile._meta.get_field("store_inputs").default)
        self.assertFalse(active_profile(self.researcher).store_inputs)

    def test_ssrf_urls_refused(self):
        for url in ("http://api.example.org/v1", "https://127.0.0.1/v1", "https://10.0.0.5/v1",
                    "https://169.254.169.254/latest", "https://[::1]/v1", "https://[::ffff:192.168.1.1]/v1",
                    "https://user:pass@api.example.org/v1", "file:///etc/passwd"):
            with self.assertRaises(UnsafeProviderURL, msg=url):
                check_provider_url(url)
        self.assertEqual(check_provider_url("https://93.184.215.14/v1/"), "https://93.184.215.14/v1")

    def test_resolved_private_host_refused(self):
        with mock.patch("apps.ai.urlsafety.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.0.10", 443))]):
            with self.assertRaises(UnsafeProviderURL):
                check_provider_url("https://interne.example.org/v1")

    @override_settings(AI_ALLOWED_LOCAL_URLS=["http://host.docker.internal:11434/v1"])
    def test_operator_allowlist(self):
        self.assertEqual(check_provider_url("http://host.docker.internal:11434/v1/"), "http://host.docker.internal:11434/v1")

    def test_only_admin_sets_base_url_and_it_is_checked(self):
        self.client.force_login(self.researcher)
        self.client.post("/ia/fournisseurs/openai_compatible/", {"action": "save", "api_key": "sk-test-0123456789",
                                                                 "base_url": "https://api.example.org/v1"})
        cred = AIProviderCredential.objects.filter(user=self.researcher, provider="openai_compatible").first()
        self.assertTrue(cred is None or cred.base_url == "")
        self.client.force_login(self.admin)
        self.client.post("/ia/fournisseurs/openai_compatible/", {"action": "save", "api_key": "sk-test-0123456789",
                                                                 "base_url": "https://169.254.169.254/latest"})
        cred = AIProviderCredential.objects.filter(user=self.admin, provider="openai_compatible").first()
        self.assertTrue(cred is None or cred.base_url == "")

    def test_official_providers_ignore_custom_url(self):
        from apps.ai.providers import OpenAIProvider

        cred = AIProviderCredential(user=self.admin, provider="openai", base_url="https://evil.example.org/v1")
        self.assertEqual(OpenAIProvider(cred).base_url, "https://api.openai.com/v1")

    def test_compatible_provider_never_echoes_body_nor_follows_redirects(self):
        cred = AIProviderCredential(user=self.admin, provider="openai_compatible", base_url="https://93.184.215.14/v1")
        provider = OpenAICompatibleProvider(cred)
        secret_body = "SECRET-INTERNE root:x:0:0"
        try:
            OpenAICompatibleProvider.transport = httpx.MockTransport(lambda r: httpx.Response(500, text=secret_body))
            with self.assertRaises(ProviderError) as ctx:
                provider._request("GET", f"{provider.base_url}/models")
            self.assertNotIn("SECRET", str(ctx.exception))
            OpenAICompatibleProvider.transport = httpx.MockTransport(
                lambda r: httpx.Response(302, headers={"Location": "http://169.254.169.254/"}))
            with self.assertRaises(ProviderError) as ctx:
                provider._request("GET", f"{provider.base_url}/models")
            self.assertIn("Redirection", str(ctx.exception))
        finally:
            OpenAICompatibleProvider.transport = None

    def test_payload_purged_unless_user_opted_in(self):
        task = AITask.objects.create(user=self.admin, function="translation", input_payload={"records": ["五輪書"]})
        purge_payload_if_needed(task)
        task.refresh_from_db()
        self.assertEqual(task.input_payload, PURGED_PAYLOAD)
        profile = active_profile(self.admin)
        profile.store_inputs = True
        profile.save()
        task2 = AITask.objects.create(user=self.admin, function="translation", input_payload={"records": ["葉隠"]})
        purge_payload_if_needed(task2)
        task2.refresh_from_db()
        self.assertEqual(task2.input_payload, {"records": ["葉隠"]})

    def test_stale_drafts_purged(self):
        old = AITask.objects.create(user=self.admin, function="translation", input_payload={"records": ["x"]})
        AITask.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=30))
        fresh = AITask.objects.create(user=self.admin, function="translation", input_payload={"records": ["y"]})
        self.assertEqual(purge_stale_drafts(), 1)
        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual((old.status, old.input_payload), ("cancelled", PURGED_PAYLOAD))
        self.assertEqual(fresh.status, "draft")

    def test_reader_has_no_access_to_ai(self):
        self.client.force_login(self.reader)
        for url in ("/ia/preferences/", "/ia/fournisseurs/", "/ia/taches/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)


# --- Correction 5 : redirections ouvertes --------------------------------------------------------

class OpenRedirectTests(AppTestCase):
    def test_next_parameter_cannot_leave_the_site(self):
        rec, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "R1", "original_title": "竹取物語"})
        for evil in ("https://evil.example.org/", "//evil.example.org/", "/\\evil.example.org"):
            r = self.client.post("/bibliotheque/ajouter/", {"record_ids": rec.record_id, "next": evil})
            self.assertEqual(r.status_code, 302)
            self.assertNotIn("evil", r["Location"], evil)
        r = self.client.post("/bibliotheque/ajouter/", {"record_ids": rec.record_id, "next": "/bibliotheque/"})
        self.assertEqual(r["Location"], "/bibliotheque/")


# --- Correction 6 : rôle Chercheur ---------------------------------------------------------------

class ResearcherPermissionTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.rec, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "P1", "original_title": "源氏物語"})

    def test_researcher_translation_becomes_a_proposal(self):
        self.client.force_login(self.researcher)
        self.client.post(f"/notices/{self.rec.record_id}/traduction/",
                         {"translated_title": "Le Dit du Genji", "justification": "Titre usuel"})
        self.rec.refresh_from_db()
        self.assertEqual(self.rec.translated_title, "", "le fonds commun ne doit pas être modifié directement")
        prop = CorrectionProposal.objects.get(record=self.rec)
        self.assertEqual((prop.field, prop.proposed_value, prop.status), ("translated_title", "Le Dit du Genji", "proposed"))

    def test_admin_translation_is_direct(self):
        self.client.post(f"/notices/{self.rec.record_id}/traduction/", {"translated_title": "Le Dit du Genji"})
        self.rec.refresh_from_db()
        self.assertEqual((self.rec.translated_title, self.rec.translated_title_origin), ("Le Dit du Genji", "user"))

    def test_researcher_cannot_validate_or_adopt(self):
        ed = EditorialContent.objects.create(record=self.rec, kind="translation", content="Le Dit du Genji", origin="ai")
        self.client.force_login(self.researcher)
        for action in ("validate", "reject", "adopt"):
            r = self.client.post(f"/notices/editorial/{ed.pk}/decision/", {"action": action})
            self.assertEqual(r.status_code, 403, action)
        ed.refresh_from_db()
        self.assertEqual(ed.status, "proposed")

    def test_researcher_cannot_decide_links_or_attach_works(self):
        self.client.force_login(self.researcher)
        self.assertEqual(self.client.post(f"/notices/{self.rec.record_id}/oeuvre/", {"title": "x"}).status_code, 403)


# --- Corrections 7 et 8 : graphie source et recalcul des champs normalisés ------------------------

class SourceFidelityTests(AppTestCase):
    def test_compatibility_ideograph_preserved(self):
        title = "欄書"  # 欄 de compatibilité : NFC le remplacerait par U+6B04
        rec, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "U1", "original_title": title})
        rec.refresh_from_db()
        self.assertEqual(rec.original_title, title)
        self.assertEqual(ord(rec.original_title[0]), 0xF91D)

    def test_truncation_and_invalid_values_are_reported(self):
        warnings = []
        clean = clean_source_data({"source_id": "T1", "original_title": "あ" * 3000, "composition_year_start": "vers 1600",
                                   "source_url": "javascript:alert(1)"}, warnings)
        self.assertLess(len(clean["original_title"]), 3000)
        joined = " ".join(warnings)
        self.assertIn("original_title", joined)
        self.assertIn("composition_year_start", joined)
        self.assertIn("source_url", joined)

    def test_import_warning_visible_in_staging(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.updates.models import ImportJob

        from .helpers import EXAMPLES

        header = (EXAMPLES / "exemple_inventaire.csv").read_text(encoding="utf-8").splitlines()[0]
        body = header + "\nEX-9999," + "あ" * 3000 + ",,,,,,,,\n"
        self.client.post("/mises-a-jour/import/nouveau/", {
            "file": SimpleUploadedFile("long.csv", body.encode("utf-8")), "catalogue": "codh-pmjt", "preset": "auto",
            "dataset_label": "Essai", "archive_source": "1"})
        job = ImportJob.objects.latest("pk")
        mapping = {f"map_{k}": v for k, v in job.mapping.items()}
        self.client.post(job.get_absolute_url(), {"action": "stage", "duplicate_strategy": "version", **mapping})
        item = job.incoming.get()
        self.assertTrue(any("tronqués" in w for w in item.warnings), item.warnings)
        self.assertContains(self.client.get(job.get_absolute_url()), "tronqués")

    def test_rule_fields_recomputed_when_source_changes(self):
        cat = self.catalogue("codh-pmjt")
        rec, _ = upsert_record(cat, {"source_id": "N1", "original_title": "記録", "composition_date_text": "鎌倉時代",
                                     "document_type_original": "物語"})
        self.assertEqual((rec.period, rec.document_type, rec.composition_year_start), ("kamakura", "recit", 1185))
        rec, status = upsert_record(cat, {"source_id": "N1", "original_title": "記録", "composition_date_text": "元禄5年",
                                          "document_type_original": "日記"})
        self.assertEqual(status, "updated")
        rec.refresh_from_db()
        self.assertEqual((rec.composition_year_start, rec.period, rec.document_type), (1692, "edo", "journal"))

    def test_user_corrections_survive_recompute(self):
        cat = self.catalogue("codh-pmjt")
        rec, _ = upsert_record(cat, {"source_id": "N2", "original_title": "記録", "composition_date_text": "鎌倉時代"})
        record_editorial_change(rec, "period", rec.period, "muromachi", self.admin)
        rec.period = "muromachi"
        rec.save()
        rec, _ = upsert_record(cat, {"source_id": "N2", "original_title": "記録 改", "composition_date_text": "元禄5年"})
        rec.refresh_from_db()
        self.assertIn("period", rec.manual_fields)
        self.assertEqual(rec.period, "muromachi")
        self.assertEqual(rec.composition_year_start, 1692)


# --- Correction 9 : connecteurs non vérifiés ------------------------------------------------------

class UnverifiedConnectorTests(AppTestCase):
    def test_unverified_flag_and_badge(self):
        kokusho = self.catalogue("kokusho")
        self.assertTrue(kokusho.needs_real_verification)
        self.assertFalse(self.catalogue("local").needs_real_verification)
        page = self.client.get(f"/sources/{kokusho.code}/")
        self.assertContains(page, "Non vérifié en conditions réelles")
        form = self.client.get("/recherche/")
        self.assertContains(form, "non vérifié")

    def test_successful_real_test_sets_flag(self):
        from apps.updates.models import SyncJob
        from apps.updates.services import run_sync

        kokusho = self.catalogue("kokusho")
        from apps.connectors.registry import connector_class

        with mock.patch.object(connector_class(kokusho.connector), "test", return_value=(True, "ok", {})):
            run_sync(SyncJob.objects.create(catalogue=kokusho, kind="test"))
        kokusho.refresh_from_db()
        self.assertIsNotNone(kokusho.real_test_ok_at)
        self.assertFalse(kokusho.needs_real_verification)


# --- Correction 10 : XML générique à notice unique -------------------------------------------------

class GenericXmlTests(AppTestCase):
    def test_single_record_file(self):
        raw = "<notice><id>U1</id><titre>竹取物語</titre></notice>".encode()
        self.assertEqual(list(_generic_xml_rows(raw)), [{"id": "U1", "titre": "竹取物語"}])

    def test_wrapped_single_record(self):
        raw = "<notices><notice><id>U1</id><titre>竹取物語</titre></notice></notices>".encode()
        self.assertEqual(list(_generic_xml_rows(raw)), [{"id": "U1", "titre": "竹取物語"}])

    def test_several_records(self):
        raw = ("<notices><notice><id>A</id><titre>甲</titre></notice>"
               "<notice><id>B</id><titre>乙</titre></notice></notices>").encode()
        self.assertEqual([r["id"] for r in list(_generic_xml_rows(raw))], ["A", "B"])

    def test_external_entities_not_resolved(self):
        raw = (b'<?xml version="1.0"?><!DOCTYPE n [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
               b"<notices><notice><id>E1</id><t>&x;</t></notice></notices>")
        rows = list(_generic_xml_rows(raw))
        self.assertEqual(rows[0]["id"], "E1")
        self.assertNotIn("root:", json.dumps(rows))


# --- Correction 11 : exports CSV (formules) et PDF (caractères absents) --------------------------

class ExportHardeningTests(AppTestCase):
    def setUp(self):
        super().setUp()
        cat = self.catalogue("codh-pmjt")
        self.r1, _ = upsert_record(cat, {"source_id": "X1", "original_title": "=HYPERLINK(\"http://x\",\"clic\")",
                                         "creator_original": "@SUM(1+1)"})
        self.r2, _ = upsert_record(cat, {"source_id": "X2", "original_title": "𠮷野家文書 \U000F0001"})
        self.col = Collection.objects.create(owner=self.admin, title="Essais export")
        from apps.library.models import CollectionRecord

        for r in (self.r1, self.r2):
            CollectionRecord.objects.create(collection=self.col, record=r)

    def _export(self, fmt, **extra):
        params = {"scope": "collection", "collection": self.col.pk, "preset": "dossier", "format": fmt,
                  "title": "Essai", "column_profile": "generic", "csv_separator": "semicolon", "pagination": "on",
                  "toc": "on", **extra}
        self.client.post("/exports/preparer/", params)
        job = ExportJob.objects.latest("pk")
        self.assertEqual(job.status, "done", job.error)
        return job

    def _main(self, job):
        return Path(settings.MEDIA_ROOT) / job.files.get(role="main").path

    def test_csv_formulas_neutralized(self):
        job = self._export("csv", csv_neutralize="on")
        rows = list(csv.reader(io.StringIO(self._main(job).read_text(encoding="utf-8")), delimiter=";"))
        cells = [c for row in rows[1:] for c in row]
        self.assertIn("'=HYPERLINK(\"http://x\",\"clic\")", cells)
        self.assertIn("'@SUM(1+1)", cells)
        self.assertFalse(any(c.startswith(("=", "+", "@")) for c in cells))
        manifest = json.loads((self._main(job).parent / self._main(job).name.replace(".csv", ".manifest.json"))
                              .read_text(encoding="utf-8"))
        self.assertTrue(manifest["csv"]["formulas_neutralized"])

    def test_csv_neutralization_can_be_disabled(self):
        job = self._export("csv")
        raw = self._main(job).read_text(encoding="utf-8")
        self.assertIn(";=HYPERLINK", raw.replace('"', ""))

    def test_pdf_reports_missing_glyphs_and_embeds_all_fonts(self):
        job = self._export("pdf")
        warnings = job.metadata.get("warnings", [])
        self.assertTrue(any("U+F0001" in w for w in warnings), warnings)
        from pypdf import PdfReader

        reader = PdfReader(self._main(job))
        text = "".join(p.extract_text() or "" for p in reader.pages)
        self.assertIn("U+F0001", text, "la note des caractères absents doit figurer dans le PDF")
        fonts = set()
        for page in reader.pages:
            for f in (page.get("/Resources") or {}).get("/Font", {}).values():
                fonts.add(str(f.get_object().get("/BaseFont")))
        self.assertFalse(any("Helvetica" in f for f in fonts), fonts)
        if Path("/usr/share/fonts/truetype/hanazono/HanaMinA.ttf").exists():
            self.assertFalse(any("U+20BB7" in w for w in warnings), "𠮷 doit être couvert par la police de secours")
        page = self.client.get(job.get_absolute_url())
        self.assertContains(page, "U+F0001")


# --- Correction 12 : connexion et premier démarrage ---------------------------------------------

class LoginThrottleTests(AppTestCase):
    def setUp(self):
        cache.clear()
        self.client.logout()

    def test_lockout_after_repeated_failures(self):
        for _ in range(settings.LOGIN_MAX_FAILURES):
            r = self.client.post("/comptes/connexion/", {"username": "chercheur", "password": "mauvais"})
            self.assertEqual(r.status_code, 200)
        r = self.client.post("/comptes/connexion/", {"username": "chercheur", "password": "motdepasse-solide-2"})
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, "Trop de tentatives", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_resets_counter(self):
        for _ in range(settings.LOGIN_MAX_FAILURES - 1):
            self.client.post("/comptes/connexion/", {"username": "chercheur", "password": "mauvais"})
        r = self.client.post("/comptes/connexion/", {"username": "chercheur", "password": "motdepasse-solide-2"})
        self.assertEqual(r.status_code, 302)
        self.client.logout()
        r = self.client.post("/comptes/connexion/", {"username": "chercheur", "password": "mauvais"})
        self.assertEqual(r.status_code, 200)


class SetupTokenTests(AppTestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        from apps.core import middleware

        self._mw = middleware

    def _post(self, **extra):
        return self.client.post("/comptes/premier-demarrage/", {
            "username": "arnaud", "display_name": "Arnaud", "email": "", "password1": "Une-phrase-solide-2026",
            "password2": "Une-phrase-solide-2026", "default_search_mode": "selective", **extra})

    @override_settings(SETUP_TOKEN="jeton-secret-42")
    def test_wrong_or_missing_token_refused(self):
        r = self._post()
        self.assertFalse(User.objects.exists())
        self.assertEqual(r.status_code, 200)
        r = self._post(setup_token="mauvais")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(User.objects.exists())
        r = self._post(setup_token="jeton-secret-42")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="arnaud", role="admin").exists())

    def test_no_token_field_when_not_configured(self):
        page = self.client.get("/comptes/premier-demarrage/")
        self.assertNotContains(page, "setup_token")


# --- Correction 13 : politique de sécurité du contenu ----------------------------------------------

class ContentSecurityPolicyTests(AppTestCase):
    def test_csp_and_frame_headers(self):
        r = self.client.get("/")
        csp = r["Content-Security-Policy"]
        for directive in ("default-src 'self'", "script-src 'self'", "frame-ancestors 'none'", "object-src 'none'"):
            self.assertIn(directive, csp)
        self.assertNotIn("unsafe-eval", csp)
        self.assertNotIn("'unsafe-inline'", csp.split("script-src")[1].split(";")[0])
        self.assertEqual(r["X-Frame-Options"], "DENY")

    def test_no_inline_scripts_or_handlers_in_templates(self):
        offenders = []
        for path in (ROOT / "templates").rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"\son[a-z]+\s*=", text) or re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text) \
                    or "javascript:" in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])
