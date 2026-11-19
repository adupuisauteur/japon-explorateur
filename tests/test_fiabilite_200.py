"""2.0.0, lot 0 — fiabilité : un échec est toujours signalé comme tel, avec son type d'erreur réel."""
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.backups.models import BackupJob
from apps.backups.services import create_backup
from apps.incidents.models import Incident

from .helpers import TMP, AppTestCase


@override_settings(BACKUP_DIR=Path(TMP) / "backups-200", BACKUP_EXTERNAL_DIR="")
class BackupCommandTests(AppTestCase):
    def test_success_prints_the_archive_and_exits_normally(self):
        out = StringIO()
        call_command("backup", "--kind", "db", "--verify", stdout=out)
        self.assertIn("Terminée", out.getvalue())
        self.assertIn("Intégrité vérifiée", out.getvalue())

    def test_failure_exits_with_an_error_code_and_the_real_error_type(self):
        with mock.patch("apps.backups.services._dump_database", side_effect=PermissionError("accès refusé")):
            with self.assertRaises(CommandError) as ctx:
                call_command("backup", "--kind", "db", stdout=StringIO())
        self.assertIn("PermissionError", str(ctx.exception))
        job = BackupJob.objects.latest("created_at")
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.message, "Échec : PermissionError : accès refusé")
        self.assertTrue(Incident.objects.filter(operation="Sauvegarde", technical_code="PermissionError").exists())

    def test_failed_verification_exits_with_an_error_code(self):
        with mock.patch("apps.backups.services.verify_backup", return_value=(False, "Problèmes : test")):
            with self.assertRaises(CommandError) as ctx:
                call_command("backup", "--kind", "db", "--verify", stdout=StringIO())
        self.assertIn("Vérification de la sauvegarde en échec", str(ctx.exception))

    def test_management_command_returns_exit_code_1(self):
        """Le code de sortie réel du processus (celui que voit mettre-a-jour.ps1) vaut 1."""
        from django.core.management import ManagementUtility

        # run_from_argv ferme les connexions à la base en fin de commande : neutralisé pour la transaction de test.
        with mock.patch("apps.backups.services._dump_database", side_effect=OSError("disque plein")), \
                mock.patch("django.core.management.base.connections.close_all"), \
                mock.patch("sys.stderr", new_callable=StringIO) as err, self.assertRaises(SystemExit) as exit_ctx:
            ManagementUtility(["manage.py", "backup", "--kind", "db"]).execute()
        self.assertEqual(exit_ctx.exception.code, 1)
        self.assertIn("OSError : disque plein", err.getvalue())


@override_settings(BACKUP_DIR=Path(TMP) / "backups-200-ext")
class ExternalCopyTests(AppTestCase):
    def test_copy_lands_in_the_external_folder(self):
        ext = Path(TMP) / "externe-ok"
        with override_settings(BACKUP_EXTERNAL_DIR=str(ext)):
            job = create_backup("db")
        self.assertEqual(job.status, "done", job.message)
        self.assertTrue((ext / Path(job.path).name).exists())
        self.assertEqual(job.external_copy, str(ext / Path(job.path).name))

    def test_failed_copy_keeps_a_valid_backup_and_warns(self):
        with override_settings(BACKUP_EXTERNAL_DIR=str(Path(TMP) / "externe-ko")), \
                mock.patch("apps.backups.services.shutil.copy2", side_effect=PermissionError("lecture seule")):
            job = create_backup("db")
        self.assertEqual(job.status, "done")
        self.assertTrue(Path(job.path).exists())
        self.assertEqual(job.external_copy, "")
        self.assertIn("Attention : copie externe impossible (PermissionError : lecture seule)", job.message)
        self.assertTrue(Incident.objects.filter(operation="Copie externe d'une sauvegarde", severity="warning").exists())

    def test_backup_page_shows_the_windows_folder(self):
        with override_settings(BACKUP_EXTERNAL_DIR="/backups-externes",
                               BACKUP_EXTERNAL_HOST_DIR=r"D:\Exemple\sauvegardes"):
            r = self.client.get("/administration/sauvegardes/")
        self.assertContains(r, r"D:\Exemple\sauvegardes")


@override_settings(BACKUP_DIR=Path(TMP) / "backups-200-restore", BACKUP_EXTERNAL_DIR="")
class RestoreSafetyTests(AppTestCase):
    def test_restore_is_refused_when_the_safety_backup_fails(self):
        job = create_backup("db")
        self.assertEqual(job.status, "done", job.message)
        with mock.patch("apps.backups.services._dump_database", side_effect=OSError("disque plein")), \
                mock.patch("apps.backups.views.restore_backup") as restore:
            r = self.client.post(f"/administration/sauvegardes/{job.pk}/restaurer/", {"confirmation": "RESTAURER"}, follow=True)
        restore.assert_not_called()
        self.assertContains(r, "Sauvegarde de sécurité impossible")
        self.assertContains(r, "rien n&#x27;a été modifié")

    def test_restore_message_says_newer_files_are_kept(self):
        from apps.backups.services import restore_backup

        self.assertIn("conservés", restore_backup.__doc__)
        self.assertEqual(create_backup("db").status, "done")  # le formulaire de restauration suit chaque sauvegarde
        self.assertContains(self.client.get("/administration/sauvegardes/"), "les plus récents conservés")


# --------------------------------------------------------------------------- Argos (décision D4)
import httpx  # noqa: E402

from apps.translation import services as translation_services  # noqa: E402
from apps.translation.engines.argos import ArgosEngine  # noqa: E402
from apps.translation.models import EngineSetting, TranslationVersion  # noqa: E402

from .test_translation_pipeline import PipelineTestCase  # noqa: E402

HEALTH = {"argos_version": "1.11.0", "packages": [{"from": "ja", "to": "en", "version": "1.1"},
                                                  {"from": "en", "to": "fr", "version": "1.9"}]}


class ArgosService:
    """Faux service Argos ; `down` simule un conteneur arrêté (connexion refusée)."""

    def __init__(self):
        self.down = False
        self.down_after = None  # nombre de traductions réussies avant l'arrêt
        self.translated = 0

    def __call__(self, request):
        if self.down or (self.down_after is not None and self.translated >= self.down_after):
            raise httpx.ConnectError("connexion refusée")
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTH)
        import json

        texts = json.loads(request.content)["texts"]
        self.translated += 1
        return httpx.Response(200, json={"translations": [f"FR:{t}" for t in texts], "path": ["ja", "en", "fr"]})


@override_settings(TRANSLATION_ARGOS_URL="http://argos:5000")
class ArgosNeverSimulatesTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        EngineSetting.objects.create(user=self.user, engine="argos", enabled=True)
        self.service = ArgosService()
        ArgosEngine.transport = httpx.MockTransport(self.service)
        patcher = mock.patch.object(ArgosEngine, "max_items", 1)  # un segment par paquet
        patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self, n=3):
        segs = self.doc(*[f"架空の文{i}。" for i in range(n)])
        return translation_services.prepare_segments_job(self.user, segs, project=self.project,
                                                         choice=translation_services.EngineChoice("argos"))

    def test_service_lost_mid_job_interrupts_and_resume_finishes(self):
        self.service.down_after = 1
        job = self.run_job(self.prepare())
        self.assertEqual(job.status, "interrupted")
        self.assertIsNone(job.finished_at)
        self.assertIn("Interrompue", job.error_summary)
        self.assertEqual(job.items.filter(status="done").count(), 1)
        self.assertEqual(job.items.filter(status="pending").count(), 2, "non traités : restés en attente")
        self.assertEqual(job.items.filter(status="failed").count(), 0)
        self.assertFalse(TranslationVersion.objects.filter(simulated=True).exists(), "jamais de simulation")
        self.assertTrue(Incident.objects.filter(module="traduction", category="indisponibilite").exists())
        # le service revient : la reprise traduit seulement le reste
        self.service.down_after = None
        translation_services.resume(job, self.user)
        job.refresh_from_db()
        self.assertEqual((job.status, job.done_items), ("done", 3))
        self.assertEqual(self.service.translated, 3)

    def test_preparation_and_confirmation_are_refused_while_the_service_is_down(self):
        self.service.down = True
        with self.assertRaises(translation_services.TranslationUnavailable) as ctx:
            self.prepare(1)
        self.assertIn("injoignable", str(ctx.exception))
        self.service.down = False
        job = self.prepare(1)
        self.service.down = True  # arrêt entre la préparation et la confirmation
        with self.assertRaises(translation_services.TranslationUnavailable) as ctx:
            translation_services.confirm(job, self.user)
        self.assertIn("injoignable", str(ctx.exception))
        self.assertFalse(TranslationVersion.objects.exists())

    def test_demo_mode_still_simulates_on_request(self):
        from .helpers import set_argos_demo

        self.service.down = True
        set_argos_demo(True)
        job = self.run_job(self.prepare(1))
        self.assertEqual(job.status, "done")
        self.assertTrue(TranslationVersion.objects.get().simulated)


# --------------------------------------------------------------------------- listes de modèles complètes
from apps.ai.models import AIProviderCredential  # noqa: E402
from apps.ai.providers import AnthropicProvider, GeminiProvider, get_provider  # noqa: E402
from apps.ai.crypto import encrypt_secret  # noqa: E402


class ModelListPaginationTests(AppTestCase):
    """Anthropic renvoie 20 modèles par page par défaut, Gemini 50 : la 1.3.0 ne lisait que la première."""

    def credential(self, provider, key):
        return AIProviderCredential.objects.create(user=self.admin, provider=provider, status="ok",
                                                   encrypted_key=encrypt_secret(key))

    def tearDown(self):
        AnthropicProvider.transport = GeminiProvider.transport = None
        super().tearDown()

    def test_anthropic_reads_every_page(self):
        pages = {None: (["claude-a", "claude-b"], True, "claude-b"), "claude-b": (["claude-c"], False, "claude-c")}
        seen = []

        def reply(request):
            after = request.url.params.get("after_id")
            seen.append(dict(request.url.params))
            ids, more, last = pages[after]
            return httpx.Response(200, json={"data": [{"id": i} for i in ids], "has_more": more, "last_id": last})

        AnthropicProvider.transport = httpx.MockTransport(reply)
        models = get_provider(self.credential("anthropic", "sk-ant-fictif-0123456789")).list_models()
        self.assertEqual(models, ["claude-a", "claude-b", "claude-c"])
        self.assertEqual(seen[0]["limit"], "1000")
        self.assertEqual(seen[1]["after_id"], "claude-b")

    def test_gemini_reads_every_page_and_keeps_text_models_only(self):
        def reply(request):
            token = request.url.params.get("pageToken")
            if token is None:
                return httpx.Response(200, json={"nextPageToken": "p2", "models": [
                    {"name": "models/gemini-a", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/embedding-x", "supportedGenerationMethods": ["embedContent"]}]})
            return httpx.Response(200, json={"models": [
                {"name": "models/gemini-b", "supportedGenerationMethods": ["generateContent", "countTokens"]}]})

        GeminiProvider.transport = httpx.MockTransport(reply)
        models = get_provider(self.credential("gemini", "AIzaFictif0123456789012345")).list_models()
        self.assertEqual(models, ["gemini-a", "gemini-b"])

    def test_a_truncated_list_never_refuses_a_model(self):
        from apps.ai import services as ai_services
        from apps.ai.providers import MAX_STORED_MODELS

        cred = self.credential("anthropic", "sk-ant-fictif-0123456789")
        cred.available_models = [f"m{i}" for i in range(MAX_STORED_MODELS)]
        cred.save()
        task = ai_services.prepare_task(self.admin, "summary", provider="anthropic", model="modele-absent")
        self.assertEqual((task.model, task.status), ("modele-absent", "draft"), "rien n'est envoyé à la préparation")
        cred.available_models = ["claude-a", "claude-b"]  # liste complète : le refus reste justifié
        cred.save()
        with self.assertRaises(ai_services.AIUnavailable) as ctx:
            ai_services.prepare_task(self.admin, "summary", provider="anthropic", model="modele-absent")
        self.assertIn("n'apparaît pas dans la liste", str(ctx.exception))


# --------------------------------------------------------------------------- erreurs jamais passées sous silence
class SilentErrorsTests(AppTestCase):
    def test_unreadable_pdf_font_is_logged(self):
        from apps.exports.generators import pdf_gen

        bad = Path(TMP) / "police-illisible.ttf"
        bad.write_bytes(b"ceci n'est pas une police")
        saved = pdf_gen._FONTS
        pdf_gen._FONTS = None
        self.addCleanup(setattr, pdf_gen, "_FONTS", saved)
        with override_settings(PDF_JAPANESE_FONT=str(bad)), self.assertLogs(pdf_gen.logger, "WARNING") as logs:
            pdf_gen.font_set()
        self.assertIn("police-illisible.ttf illisible", logs.output[0])

    def test_unreadable_export_fingerprint_is_logged(self):
        from apps.exports import services as export_services

        job = mock.Mock(data_fingerprint="abc", export_uid="EXP-FICTIF")
        with mock.patch.object(export_services, "fingerprint", side_effect=ValueError("données illisibles")), \
                self.assertLogs(export_services.logger, "WARNING") as logs:
            self.assertTrue(export_services.data_changed_since(job))
        self.assertIn("ValueError : données illisibles", logs.output[0])


# --------------------------------------------------------------------------- page « État de l'installation »
from apps.core import health  # noqa: E402
from apps.core.models import ServiceCheck  # noqa: E402


class InstallationStateTests(AppTestCase):
    def test_page_is_reserved_to_the_administrator(self):
        self.assertEqual(self.client.get("/administration/etat/").status_code, 200)
        for user in (self.researcher, self.reader):
            self.client.force_login(user)
            self.assertIn(self.client.get("/administration/etat/").status_code, (302, 403))

    def test_page_lists_every_check_and_a_copyable_diagnostic(self):
        r = self.client.get("/administration/etat/")
        for label in ("Version", "Base de données et migrations", "Workers", "Planificateur", "Argos",
                      "Sauvegardes", "Clés des services en ligne", "Espace disque", "Ressources accordées par Docker"):
            self.assertContains(r, label)
        self.assertContains(r, 'data-copy-target="#diagnostic"')
        self.assertContains(r, "J-ed 2.0.0")
        self.assertNotContains(r, "onclick")  # CSP : aucun gestionnaire en ligne

    def test_diagnostic_has_no_personal_data(self):
        from apps.ai.crypto import encrypt_secret
        from apps.translation.models import EngineSetting

        EngineSetting.objects.create(user=self.researcher, engine="deepl", plan="free", status="ok",
                                     encrypted_key=encrypt_secret("cle-deepl-fictive-0000000000"))
        with override_settings(BACKUP_EXTERNAL_HOST_DIR=r"C:\Users\Arnaud\Documents\sauvegardes"):
            text = health.diagnostic_text()
        self.assertIn("deepl : 1 clé(s), test réussi", text)
        for secret in ("cle-deepl-fictive", "chercheur", "Arnaud"):
            self.assertNotIn(secret, text)
        self.assertIn(r"C:\Users\…\Documents\sauvegardes", text)

    def test_pending_migrations_are_an_error_and_the_command_exits_1(self):
        from types import SimpleNamespace

        fake_plan = [(SimpleNamespace(app_label="catalog", name="0099_fictive"), False)]
        with mock.patch("django.db.migrations.executor.MigrationExecutor.migration_plan", return_value=fake_plan):
            check = health.check_database()
            with self.assertRaises(CommandError) as ctx:
                call_command("etat_installation", "--json", stdout=StringIO())
        self.assertEqual(check.level, health.ERROR)
        self.assertIn("catalog.0099_fictive", check.summary)
        self.assertIn("Base de données", str(ctx.exception))

    def test_scheduler_heartbeat(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.core.tasks import heartbeat

        self.assertEqual(health.check_scheduler().level, health.UNKNOWN)
        heartbeat()
        self.assertEqual(health.check_scheduler().level, health.OK)
        ServiceCheck.objects.filter(name="planificateur").update(checked_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(health.check_scheduler().level, health.ERROR)

    def test_backup_age_levels(self):
        from datetime import timedelta

        from django.utils import timezone

        self.assertEqual(health.check_backups().level, health.WARNING)  # aucune sauvegarde : à surveiller
        job = BackupJob.objects.create(kind="full", status="done", size=10)
        with override_settings(BACKUP_EXTERNAL_DIR=""):
            self.assertEqual(health.check_backups().level, health.OK)
            BackupJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=3))
            self.assertEqual(health.check_backups().level, health.WARNING)
            BackupJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(days=8))
            self.assertEqual(health.check_backups().level, health.ERROR)

    def test_a_failing_check_is_shown_not_hidden(self):
        with mock.patch.object(health, "CHECKS", (health.check_version, mock.Mock(
                __name__="check_disk", side_effect=OSError("lecture impossible")))):
            results = health.collect()
        self.assertEqual(results[1].label, "Espace disque")
        self.assertIn("OSError : lecture impossible", results[1].summary)


@override_settings(TRANSLATION_ARGOS_URL="http://argos:5000")
class ArgosSelfTestTests(AppTestCase):
    def tearDown(self):
        ArgosEngine.transport = None
        super().tearDown()

    def test_ready_after_a_successful_test_sentence(self):
        from apps.translation.argos_selftest import TEST_SENTENCE, run_selftest

        service = ArgosService()
        ArgosEngine.transport = httpx.MockTransport(service)
        check = run_selftest()
        self.assertTrue(check.ok)
        self.assertIn("Argos prêt", check.message)
        self.assertEqual(check.data["translation"], f"FR:{TEST_SENTENCE}")
        self.assertEqual(health.check_argos().level, health.OK)

    def test_precise_error_when_the_test_fails(self):
        from apps.translation.argos_selftest import run_selftest

        def reply(request):
            if request.url.path == "/health":
                return httpx.Response(200, json=HEALTH)
            return httpx.Response(500, json={"code": "erreur_interne", "message": "Erreur interne (KeyError)"})

        ArgosEngine.transport = httpx.MockTransport(reply)
        check = run_selftest()
        self.assertFalse(check.ok)
        self.assertIn("KeyError", check.message)
        self.assertEqual(health.check_argos().level, health.ERROR)

    def test_button_launches_the_test(self):
        ArgosEngine.transport = httpx.MockTransport(ArgosService())
        r = self.client.post("/administration/etat/test-argos/", follow=True)
        self.assertContains(r, "Traduction d&#x27;essai d&#x27;Argos lancée")
        self.assertTrue(ServiceCheck.objects.get(name="argos_essai").ok)
