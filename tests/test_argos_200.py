"""2.0.0 — lot 7 : Argos installé par défaut, bouton unique, invitations, priorité « maintenant », mémoire.

Vrai serveur HTTP du service (docker/argos/server.py) avec un traducteur factice : aucun paquet réel, rien
n'est téléchargé, aucun texte réel.
"""
import json
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
from django.test import SimpleTestCase, override_settings

from apps.core.models import ServiceCheck
from apps.notifications.models import Notification
from apps.translation import argos_packages as A
from apps.translation.engines.argos import ArgosEngine
from apps.translation.engines.base import Segment
from apps.translation.models import EngineSetting, TranslationJob

from .helpers import AppTestCase
from .test_argos_service import ClientMixin, ServerMixin, server_mod

JA_FR = (("ja", "en", "1.1"), ("en", "fr", "1.9"))


class GateTests(SimpleTestCase):
    def test_now_requests_pass_before_waiting_background_requests(self):
        gate, order, release = server_mod.PriorityGate(), [], threading.Event()

        def work(name, priority, hold=False):
            with gate.slot(priority):
                order.append(name)
                if hold:
                    release.wait(5)

        first = threading.Thread(target=work, args=("paquet 1 (fond)", "background", True))
        first.start()
        while not gate.state()["running"]:
            time.sleep(0.01)
        second = threading.Thread(target=work, args=("paquet 2 (fond)", "background"))
        second.start()
        while gate.state()["waiting_background"] < 1:
            time.sleep(0.01)
        urgent = threading.Thread(target=work, args=("demande immédiate", "now"))
        urgent.start()
        while gate.state()["waiting_now"] < 1:
            time.sleep(0.01)
        self.assertEqual(gate.state(), {"running": True, "waiting_now": 1, "waiting_background": 1})
        release.set()
        for t in (first, second, urgent):
            t.join(5)
        # la demande immédiate a attendu la fin du paquet en cours, pas celle du paquet suivant
        self.assertEqual(order, ["paquet 1 (fond)", "demande immédiate", "paquet 2 (fond)"])
        self.assertEqual(gate.state(), {"running": False, "waiting_now": 0, "waiting_background": 0})

    def test_memory_state(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "meminfo").write_text("MemTotal:  8000000 kB\nMemFree: 1 kB\nMemAvailable:  6000000 kB\n")
        cg = tmp / "cg"
        cg.mkdir()
        (cg / "memory.max").write_text("max\n")
        self.assertEqual(server_mod.memory_state(tmp / "meminfo", (cg,)),
                         {"total_mb": 7812, "available_mb": 5859, "limit_mb": None})
        (cg / "memory.max").write_text(str(3 * 1024 ** 3))
        self.assertEqual(server_mod.memory_state(tmp / "meminfo", (cg,))["limit_mb"], 3072)
        (cg / "memory.max").write_text("9223372036854771712")  # cgroup v1 : pas de vraie limite
        self.assertIsNone(server_mod.memory_state(tmp / "meminfo", (cg,))["limit_mb"])
        self.assertEqual(server_mod.memory_state(tmp / "absent", ()),
                         {"total_mb": None, "available_mb": None, "limit_mb": None})

    def test_license_is_read_from_the_package_metadata(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "metadata.json").write_text(json.dumps({"license": "CC BY 4.0"}))
        self.assertEqual(server_mod.ArgosBackend._license(SimpleNamespace(package_path=tmp)), "CC BY 4.0")
        (tmp / "metadata.json").write_text(json.dumps({"from_code": "ja"}))
        self.assertEqual(server_mod.ArgosBackend._license(SimpleNamespace(package_path=tmp)), "")
        (tmp / "metadata.json").write_text("[1, 2]")
        self.assertEqual(server_mod.ArgosBackend._license(SimpleNamespace(package_path=tmp)), "")
        self.assertEqual(server_mod.ArgosBackend._license(SimpleNamespace()), "")


class ServerPriorityTests(ServerMixin, SimpleTestCase):
    def setUp(self):
        self.start_server(installed=JA_FR)

    def test_health_reports_memory_and_queue(self):
        status, data = self.call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(set(data["memory"]), {"total_mb", "available_mb", "limit_mb"})
        self.assertEqual(data["queue"], {"running": False, "waiting_now": 0, "waiting_background": 0})

    def test_priority_values(self):
        for priority in ("now", "background"):
            status, data = self.call("POST", "/translate", {"texts": ["文"], "source": "ja", "target": "fr",
                                                            "priority": priority})
            self.assertEqual(status, 200)
        self.assertEqual(self.call("POST", "/translate", {"texts": ["文"], "source": "ja", "target": "fr"})[0], 200)
        status, data = self.call("POST", "/translate", {"texts": ["文"], "source": "ja", "target": "fr",
                                                        "priority": "urgent"})
        self.assertEqual((status, data["code"]), (400, "requete"))


class EnginePriorityTests(AppTestCase):
    def test_engine_sends_its_priority(self):
        sent = []

        def reply(request):
            body = json.loads(request.content) if request.content else {}
            if request.url.path == "/health":
                return httpx.Response(200, json={"argos_version": "1.11.0", "packages": [
                    {"from": a, "to": b, "version": v} for a, b, v in JA_FR]})
            sent.append(body.get("priority"))
            return httpx.Response(200, json={"translations": body["texts"], "path": ["ja", "en", "fr"]})

        ArgosEngine.transport = httpx.MockTransport(reply)
        self.addCleanup(setattr, ArgosEngine, "transport", None)
        setting = EngineSetting.objects.create(user=self.researcher, engine="argos", enabled=True)
        with override_settings(TRANSLATION_ARGOS_URL="http://argos:5000"):
            engine = ArgosEngine(self.researcher, setting=setting)
            engine.translate([Segment("1", "文")], "ja", "fr")
            engine.priority = "now"
            engine.translate([Segment("1", "文")], "ja", "fr")
        self.assertEqual(sent, ["background", "now"])

    def test_small_jobs_are_sent_as_now(self):
        from apps.translation import services

        class Stub:
            priority = "background"

            def translate(self, segments, source, target, **kwargs):
                return self.priority

        job = SimpleNamespace(total_items=5, project_id=None, engine="argos", kind="records")
        self.assertEqual(services._translate(job, Stub(), [], "modern"), "now")
        job.total_items = 500
        self.assertEqual(services._translate(job, Stub(), [], "modern"), "background")


class OneClickTests(ClientMixin, AppTestCase):
    URL = "/traduction/moteurs/locaux/japonais-francais/"

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_confirmation_is_required(self):
        self.connect()
        self.client.post(self.URL)
        self.assertFalse(TranslationJob.objects.filter(kind="package").exists())
        self.assertEqual(self.backend.calls, [])

    def test_one_click_installs_both_packages_tests_and_notifies(self):
        self.connect()
        response = self.client.post(self.URL, {"confirm": "1"})
        self.assertRedirects(response, "/traduction/moteurs/locaux/#argos-jobs", fetch_redirect_response=False)
        job = TranslationJob.objects.get(kind="package")
        self.assertTrue(job.scope_label.startswith("Installation de la traduction japonais → français"))
        self.assertEqual(sorted(job.items.values_list("record_field", flat=True)), ["index:en→fr", "index:ja→en"])
        self.assertEqual((job.status, job.done_items), ("done", 2))  # tâche exécutée (Celery en mode immédiat)
        self.assertEqual(self.backend.calls, ["install ja→en", "install en→fr"])
        self.assertTrue(EngineSetting.objects.get(user=self.admin, engine="argos").enabled)
        check = ServiceCheck.objects.get(name="argos_essai")
        self.assertTrue(check.ok, check.message)
        self.assertIn("Argos prêt", check.message)
        notification = Notification.objects.get(recipient=self.admin, event_type="task_done")
        self.assertEqual(notification.title, "Terminé : Installation de la traduction japonais → français")
        self.assertIn("Argos prêt", notification.body)
        page = self.client.get("/traduction/moteurs/locaux/").content.decode()
        self.assertIn("Dernier essai", page)
        self.assertNotIn('id="argos-invite"', page)  # plus d'invitation une fois prêt
        # deuxième clic : rien à télécharger, nouvel essai
        self.client.post(self.URL, {"confirm": "1"})
        self.assertEqual(TranslationJob.objects.filter(kind="package").count(), 1)
        self.assertEqual(self.backend.calls, ["install ja→en", "install en→fr"])

    def test_only_missing_packages_are_downloaded(self):
        self.connect(installed=(("en", "fr", "1.9"),))
        self.client.post(self.URL, {"confirm": "1"})
        self.assertEqual(self.backend.calls, ["install ja→en"])

    def test_failure_is_shown_and_notified_and_resumable(self):
        self.connect()
        self.backend.index_reachable = False
        self.client.post(self.URL, {"confirm": "1"})
        job = TranslationJob.objects.get(kind="package")
        self.assertEqual(job.status, "failed")
        notification = Notification.objects.get(recipient=self.admin, event_type="task_errors")
        self.assertIn("Échec : Installation de la traduction japonais → français", notification.title)
        self.backend.index_reachable = True
        A.relaunch(job)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")

    def test_refused_while_an_installation_runs_or_service_down(self):
        self.connect()
        running = A._new_job(self.admin, "Installation en cours", ["index:ja→en"])
        response = self.client.post(self.URL, {"confirm": "1"}, follow=True)
        self.assertContains(response, "Une installation est déjà en cours")
        self.assertContains(response, "Installation en cours (0 paquet(s) sur 1)")
        running.status = "done"
        running.save()
        with override_settings(TRANSLATION_ARGOS_URL="http://127.0.0.1:9"):
            response = self.client.post(self.URL, {"confirm": "1"}, follow=True)
        self.assertContains(response, "COMPOSE_PROFILES=argos")
        self.assertEqual(TranslationJob.objects.filter(kind="package").count(), 1)

    def test_access(self):
        self.connect()
        self.client.force_login(self.researcher)
        self.assertEqual(self.client.post(self.URL, {"confirm": "1"}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.URL).status_code, 405)


class InvitationTests(ClientMixin, AppTestCase):
    def test_engines_page(self):
        self.connect()
        self.client.force_login(self.admin)
        page = self.client.get("/traduction/moteurs/").content.decode()
        self.assertIn("Installer la traduction japonais → français", page)
        self.assertIn("environ 200 Mo", page)
        self.assertIn('action="/traduction/moteurs/locaux/japonais-francais/"', page)
        self.client.force_login(self.researcher)
        page = self.client.get("/traduction/moteurs/").content.decode()
        self.assertIn("demandez à l'administrateur", page)
        self.assertNotIn('action="/traduction/moteurs/locaux/japonais-francais/"', page)

    def test_no_invitation_when_ready(self):
        self.connect(installed=JA_FR)
        self.client.force_login(self.admin)
        self.assertNotIn('id="argos-invite"', self.client.get("/traduction/moteurs/").content.decode())
        self.assertNotIn('id="argos-invite"', self.client.get("/traduction/moteurs/locaux/").content.decode())

    def test_first_translation_with_argos(self):
        from apps.translation import services
        from apps.translation.models import TranslationPreference

        self.connect()
        self.client.force_login(self.admin)
        EngineSetting.objects.create(user=self.admin, engine="argos", enabled=True)
        TranslationPreference.objects.create(user=self.admin, default_engine="argos", migrated_from_ai=True)
        from apps.catalog.models import Record

        record = Record.objects.create(catalogue=self.catalogue("codh-pmjt"), source_id="essai-lot7",
                                       original_title="試験の書名")
        # écran de préparation : invitation au-dessus du formulaire (jamais un formulaire dans un autre)
        page = self.client.get(f"/traduction/notices/preparer/?records={record.record_id}").content.decode()
        self.assertIn("Installer la traduction japonais → français", page)
        self.assertLess(page.index('id="argos-invite"'), page.index('name="records"'))
        # une tâche préparée plus tôt (paquets désinstallés depuis) : invitation sur l'écran de confirmation
        self.backend.packages.update({("ja", "en"): "1.1", ("en", "fr"): "1.9"})
        job = services.prepare_records_job(self.admin, [record], choice=services.EngineChoice("argos"))
        self.backend.packages.clear()
        page = self.client.get(f"/traduction/taches/{job.pk}/").content.decode()
        self.assertIn("Envoi impossible", page)
        self.assertIn("Installer la traduction japonais → français", page)

    def test_state_page_points_to_the_button(self):
        from apps.core.health import check_argos

        self.connect()
        check = check_argos()
        self.assertIn("Bouton « Installer la traduction japonais → français »", " ".join(check.details))

    def test_memory_warning(self):
        self.assertEqual(A.memory_warning({"memory": {"total_mb": 7800, "limit_mb": None}}), "")
        self.assertIn("2.0 Go", A.memory_warning({"memory": {"total_mb": 7800, "limit_mb": 2048}}))
        self.assertIn("8 Go sont conseillés", A.memory_warning({"memory": {"total_mb": 3000}}))
        self.assertEqual(A.memory_warning({}), "")
        self.assertEqual(A.memory_warning(None), "")


class FirstRunTests(ClientMixin, AppTestCase):
    def setUp(self):
        super().setUp()
        from apps.accounts.models import User

        self.client.logout()
        User.objects.all().delete()  # aucun compte : l'assistant de première configuration est accessible

    def post(self, **extra):
        data = {"username": "premier", "display_name": "", "email": "", "password1": "Fictif-mot-de-passe-42",
                "password2": "Fictif-mot-de-passe-42", "default_search_mode": "selective", **extra}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/comptes/premier-demarrage/", data, follow=True)

    def test_later_by_default(self):
        self.connect()
        page = self.client.get("/comptes/premier-demarrage/").content.decode()
        self.assertIn("Installer maintenant la traduction hors ligne japonais → français", page)
        self.assertNotIn('name="install_argos" checked', page)
        self.post()
        self.assertFalse(TranslationJob.objects.filter(kind="package").exists())
        self.assertEqual(self.backend.calls, [])

    def test_install_now(self):
        self.connect()
        response = self.post(install_argos="on")
        self.assertContains(response, "Installation de la traduction japonais → français lancée")
        job = TranslationJob.objects.get(kind="package")
        self.assertEqual(job.status, "done")
        self.assertEqual(self.backend.calls, ["install ja→en", "install en→fr"])

    def test_service_not_ready_does_not_block_the_setup(self):
        with override_settings(TRANSLATION_ARGOS_URL="http://127.0.0.1:9"):
            response = self.post(install_argos="on")
        self.assertContains(response, "Traduction hors ligne non installée pour l&#x27;instant")
        self.assertFalse(TranslationJob.objects.filter(kind="package").exists())


class SelftestButtonAndAutoTests(ClientMixin, AppTestCase):
    """Lot 3 (demande du 15 novembre 2026) : bouton dans Moteurs locaux ; essai automatique après démarrage."""

    def test_button_in_local_engines_returns_there(self):
        self.connect(installed=JA_FR)
        self.client.force_login(self.admin)
        page = self.client.get("/traduction/moteurs/locaux/").content.decode()
        self.assertIn("Lancer un essai", page)
        response = self.client.post("/administration/etat/test-argos/", {"next": "/traduction/moteurs/locaux/"})
        self.assertRedirects(response, "/traduction/moteurs/locaux/", fetch_redirect_response=False)
        check = ServiceCheck.objects.get(name="argos_essai")
        self.assertTrue(check.ok)
        self.assertFalse(check.data["auto"])
        response = self.client.post("/administration/etat/test-argos/", {"next": "https://exemple.invalid/"})
        self.assertRedirects(response, "/administration/etat/", fetch_redirect_response=False)
        self.client.force_login(self.researcher)
        self.assertNotIn("Lancer un essai", self.client.get("/traduction/moteurs/locaux/").content.decode())

    def test_auto_selftest_once_per_version(self):
        from apps.translation.argos_selftest import auto_selftest

        self.connect(installed=JA_FR)
        self.assertEqual(auto_selftest(), "fait")
        check = ServiceCheck.objects.get(name="argos_essai")
        self.assertTrue(check.data["auto"])
        self.assertEqual(check.data["version"], "2.0.0")
        self.assertEqual(auto_selftest(), "inutile")  # redémarrage ordinaire : pas de nouvel essai
        check.data["version"] = "1.3.0"  # mise à jour : nouvel essai
        check.save()
        self.assertEqual(auto_selftest(), "fait")
        old = ServiceCheck.objects.get(name="argos_essai")
        old.data, old.ok = {}, True  # essai d'avant la 2.0.0 (sans version) : refait
        old.save()
        self.assertEqual(auto_selftest(), "fait")

    def test_auto_selftest_waits_for_the_service_and_skips_without_packages(self):
        from apps.translation.argos_selftest import AUTO_ATTEMPTS, auto_selftest
        from apps.translation.tasks import auto_argos_selftest

        self.connect()
        self.assertEqual(auto_selftest(), "inutile")  # paquets absents : rien à essayer
        self.assertFalse(ServiceCheck.objects.filter(name="argos_essai").exists())
        with override_settings(TRANSLATION_ARGOS_URL="http://127.0.0.1:9"):
            self.assertEqual(auto_selftest(1), "attente")
            self.assertEqual(auto_selftest(AUTO_ATTEMPTS), "abandon")
            # la tâche se reprogramme jusqu'à l'abandon (Celery en mode immédiat pendant les tests)
            with override_settings(ARGOS_AUTO_SELFTEST_DELAY=0):
                self.assertEqual(auto_argos_selftest.apply(args=[1]).get(), "attente")
        with override_settings(TRANSLATION_ARGOS_URL=""):
            self.assertEqual(auto_selftest(), "inutile")

    def test_beat_start_schedules_the_selftest(self):
        from unittest import mock

        from config import celery as celery_config

        with mock.patch.object(celery_config.app, "send_task") as send:
            celery_config.schedule_argos_selftest()
        send.assert_called_once_with("apps.translation.tasks.auto_argos_selftest", countdown=120)
        with mock.patch.object(celery_config.app, "send_task", side_effect=OSError("broker absent")):
            celery_config.schedule_argos_selftest()  # n'empêche jamais le planificateur de démarrer
