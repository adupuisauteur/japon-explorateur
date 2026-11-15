"""2.0.0 — lot 5 : notifications (fenêtres, compteur, historique, préférences, alertes, essai). Données fictives."""
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import Client

from apps.catalog.services import upsert_record
from apps.exports.models import ExportJob
from apps.incidents.services import change_status, record_incident
from apps.notifications import services
from apps.notifications.models import Notification, NotificationPreference
from apps.translation.models import TranslationJob
from apps.translation.services import _touch
from apps.updates.models import SyncJob

from .helpers import AppTestCase

ROOT = Path(settings.BASE_DIR)


class RulesTests(AppTestCase):
    def test_preferences_are_respected(self):
        self.assertIsNotNone(services.notify(self.researcher, "task_done", "A"))
        services.save_preferences(self.researcher, {"task_errors", "task_paused"})
        self.assertIsNone(services.notify(self.researcher, "task_done", "B"))
        self.assertIsNotNone(services.notify(self.researcher, "task_errors", "C"))
        self.assertFalse(NotificationPreference.objects.get(user=self.researcher, event_type="task_done").enabled)

    def test_one_unread_notification_per_group(self):
        first = services.notify(self.researcher, "task_done", "A", group_key="tache:1")
        self.assertIsNone(services.notify(self.researcher, "task_done", "A bis", group_key="tache:1"))
        services.mark_read(self.researcher, [first.pk])
        self.assertIsNotNone(services.notify(self.researcher, "task_done", "A ter", group_key="tache:1"))

    def test_incident_alerts_are_for_admins_above_their_threshold(self):
        self.assertIsNone(services.notify(self.researcher, "incident", "X", incident_severity="critical"))
        self.assertIsNone(services.notify(self.admin, "incident", "X", incident_severity="warning"))  # seuil : erreur
        self.assertIsNotNone(services.notify(self.admin, "incident", "X", incident_severity="error"))
        services.save_preferences(self.admin, {"incident"}, incident_threshold="warning")
        self.assertIsNotNone(services.notify(self.admin, "incident", "Y", incident_severity="warning"))

    def test_a_failing_notification_never_breaks_the_operation(self):
        with mock.patch.object(Notification.objects, "create", side_effect=RuntimeError("base")), \
                self.assertLogs("apps.notifications.services", level="ERROR"):
            self.assertIsNone(services.notify(self.researcher, "task_done", "A"))


class IncidentTests(AppTestCase):
    def record(self, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return record_incident(module="recherche", category="erreur_technique", title="Panne fictive", **kwargs)

    def test_one_popup_per_new_group_not_per_occurrence(self):
        incident = self.record(severity="error")
        self.assertEqual(Notification.objects.filter(recipient=self.admin, event_type="incident").count(), 1)
        self.record(severity="error")  # même groupe : nouvelle occurrence
        self.assertEqual(Notification.objects.filter(event_type="incident").count(), 1)
        notification = Notification.objects.get(event_type="incident")
        self.assertIn(incident.uid, notification.body)
        self.assertEqual(notification.link, f"/journal/{incident.uid}/")
        self.assertFalse(Notification.objects.filter(recipient__in=[self.researcher, self.reader]).exists())

    def test_below_threshold_and_reappearance(self):
        self.record(severity="warning", message="faible")
        self.assertFalse(Notification.objects.filter(event_type="incident").exists())
        incident = self.record(severity="error", message="forte")
        services.mark_read(self.admin)
        change_status(incident, "corrige", self.admin)
        self.record(severity="error", message="forte")
        latest = Notification.objects.filter(event_type="incident").first()
        self.assertTrue(latest.title.startswith("Problème revenu après correction"))

    def test_no_alert_for_a_cancelled_operation(self):
        record_incident(module="recherche", category="erreur_technique", severity="critical", title="Annulé")
        self.assertFalse(Notification.objects.filter(event_type="incident").exists())  # transaction non validée


class JobEndTests(AppTestCase):
    def job(self, **kwargs):
        return TranslationJob.objects.create(user=self.researcher, kind="records", engine="deepl", status="running",
                                             scope_label="Notices fictives", **kwargs)

    def test_translation_done_errors_and_interrupted(self):
        job = self.job()
        _touch(job, status="done", done_items=3)
        n = Notification.objects.get(recipient=self.researcher)
        self.assertEqual((n.event_type, n.severity), ("task_done", "success"))
        self.assertEqual(n.title, "Traduction terminée : Notices fictives")
        self.assertEqual(n.link, f"/traduction/taches/{job.pk}/")
        job = self.job()
        _touch(job, status="done", done_items=2, failed_items=1)
        self.assertEqual(Notification.objects.filter(event_type="task_errors").count(), 1)
        job = self.job(error_summary="Service Argos injoignable.")
        _touch(job, status="interrupted")
        paused = Notification.objects.get(event_type="task_paused")
        self.assertIn("Argos injoignable", paused.body)
        _touch(self.job(), status="running")  # étape intermédiaire : rien
        self.assertEqual(Notification.objects.count(), 3)

    def test_export_end(self):
        self.client.force_login(self.researcher)
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "N5", "original_title": "架空"})
        self.client.post("/exports/preparer/", {"scope": "selection", "records": record.record_id,
                                                "preset": "bibliography", "format": "txt", "title": "Essai lot 5",
                                                "column_profile": "generic", "csv_separator": "semicolon"})
        job = ExportJob.objects.latest("pk")
        n = Notification.objects.get(recipient=self.researcher, event_type="task_done")
        self.assertEqual((n.title, n.link), ("Export prêt : Essai lot 5", job.get_absolute_url()))

    def test_sync_end_goes_to_its_author_or_to_admins(self):
        from apps.notifications.services import sync_ended

        cat = self.catalogue("local")
        mine = SyncJob.objects.create(catalogue=cat, kind="test", status="review", triggered_by=self.researcher)
        sync_ended(mine)
        self.assertTrue(Notification.objects.filter(recipient=self.researcher, title__startswith="Synchronisation "
                                                    "à valider").exists())
        planned = SyncJob.objects.create(catalogue=cat, kind="test", status="failed")
        sync_ended(planned)
        self.assertTrue(Notification.objects.filter(recipient=self.admin, event_type="task_errors").exists())
        quiet = SyncJob.objects.create(catalogue=cat, kind="test", status="done")
        self.assertEqual(sync_ended(quiet), [])


class InterfaceTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.researcher)

    def test_popups_shown_once_with_counter(self):
        services.notify(self.researcher, "task_done", "Traduction terminée : essai", link="/traduction/taches/")
        page = self.client.get("/notifications/fenetres/")
        html = page.content.decode()
        self.assertIn("Traduction terminée : essai", html)
        self.assertIn('id="notif-count" hx-swap-oob="true"', html)
        self.assertIn("Voir le compte rendu", html)
        self.assertIn(">Vu</button>", html)
        self.assertNotIn("<script", html)
        self.assertIn("no-cache", page["Cache-Control"])
        self.assertNotIn("Traduction terminée : essai", self.client.get("/notifications/fenetres/").content.decode())
        self.assertEqual(services.unread_count(self.researcher), 1)  # affichée, pas encore lue

    def test_waiting_popups_appear_at_next_visit(self):
        self.client.logout()
        services.notify(self.researcher, "task_done", "Pendant votre absence")
        self.assertEqual(self.client.get("/notifications/fenetres/").status_code, 302)
        self.client.force_login(self.researcher)
        self.assertContains(self.client.get("/notifications/fenetres/"), "Pendant votre absence")

    def test_mark_read_open_and_ownership(self):
        n = services.notify(self.researcher, "task_done", "A", link="/bibliotheque/")
        response = self.client.post(f"/notifications/{n.pk}/lue/", HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="notif-count" hx-swap-oob="true"')
        self.assertEqual(services.unread_count(self.researcher), 0)
        other = services.notify(self.admin, "task_done", "B")
        self.assertEqual(self.client.post(f"/notifications/{other.pk}/lue/").status_code, 404)
        self.assertEqual(self.client.get(f"/notifications/{other.pk}/ouvrir/").status_code, 404)
        self.assertRedirects(self.client.get(f"/notifications/{n.pk}/ouvrir/"), "/bibliotheque/",
                             fetch_redirect_response=False)
        outside = Notification.objects.create(recipient=self.researcher, event_type="test", title="C",
                                              link="https://example.org/")
        self.assertRedirects(self.client.get(f"/notifications/{outside.pk}/ouvrir/"), "/notifications/",
                             fetch_redirect_response=False)

    def test_history_filters_and_mark_all(self):
        services.notify(self.researcher, "task_done", "Fini")
        read = services.notify(self.researcher, "task_errors", "Erreur")
        services.mark_read(self.researcher, [read.pk])
        page = self.client.get("/notifications/?etat=non-lues")
        self.assertContains(page, "Fini")
        self.assertNotContains(page, ">Erreur<")
        page = self.client.get("/notifications/?type=task_errors")
        self.assertContains(page, "Erreur")
        self.assertNotContains(page, "Dysfonctionnement (administrateur)")  # type réservé, caché au chercheur
        self.client.post("/notifications/", {"action": "all_read"})
        self.assertEqual(services.unread_count(self.researcher), 0)

    def test_preferences_page_and_test_buttons(self):
        page = self.client.get("/notifications/preferences/")
        self.assertContains(page, "Envoyer une notification d'essai")
        self.assertNotContains(page, "alerte de dysfonctionnement d'essai")
        self.assertNotContains(page, 'name="incident_threshold"')
        self.client.post("/notifications/preferences/", {"types": ["task_errors"]})
        self.assertFalse(services.wants(self.researcher, "task_done"))
        response = self.client.post("/notifications/essai/", {"kind": "incident"}, follow=True)
        self.assertContains(response, "Notification d&#x27;essai envoyée")
        sent = Notification.objects.get(recipient=self.researcher)
        self.assertTrue(sent.title.startswith("[Essai] Tâche terminée"))  # pas d'alerte pour un chercheur
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/notifications/preferences/"), 'name="incident_threshold"')
        self.client.post("/notifications/essai/", {"kind": "incident"})
        self.assertTrue(Notification.objects.filter(recipient=self.admin, title__contains="dysfonctionnement").exists())
        self.client.post("/notifications/preferences/", {"types": ["incident"], "incident_threshold": "critical"})
        self.assertEqual(services.preference(self.admin, "incident").min_severity, "critical")

    def test_menu_counter_entry_and_popup_container(self):
        services.notify(self.researcher, "task_done", "A")
        page = self.client.get("/").content.decode()
        self.assertIn('<span id="notif-count"><span class="badge rounded-pill text-bg-danger nav-badge"', page)
        self.assertIn('href="/notifications/"', page)
        self.assertIn('hx-get="/notifications/fenetres/"', page)
        self.assertIn('hx-trigger="load, every 30s, jed:visible from:body"', page)
        self.assertIn("data-pause-hidden", page)
        self.assertNotIn('id="notif-popups"', Client().get("/comptes/connexion/").content.decode())

    def test_reader_has_notifications_too(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get("/notifications/").status_code, 200)
        self.assertEqual(self.client.get("/notifications/preferences/").status_code, 200)


class FrontEndTests(AppTestCase):
    def test_periodic_refreshes_pause_when_the_tab_is_hidden(self):
        for name in ("ai/task.html", "translation/_job_status.html", "translation/local_engines.html",
                     "translation/comparison.html", "exports/detail.html"):
            text = (ROOT / "templates" / name).read_text(encoding="utf-8")
            self.assertIn("data-pause-hidden", text, name)
        js = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
        self.assertIn('closest("[data-pause-hidden]")', js)
        self.assertIn('new CustomEvent("jed:visible")', js)
        self.assertIn("bootstrap.Toast.getOrCreateInstance", js)

    def test_service_worker_cache_follows_interface_files(self):
        from apps.core import views

        name = self.client.get("/sw.js").content.decode().split('const SHELL = "')[1].split('"')[0]
        self.assertTrue(name.startswith(f"shell-v{settings.APP_VERSION}-"))
        views._shell_fingerprint = None
        real_open = open

        def changed(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            if str(path).endswith("app.js"):
                import io
                return io.BytesIO(handle.read() + b"// modification")
            return handle

        with mock.patch("builtins.open", side_effect=changed):
            other = views.shell_fingerprint()
        views._shell_fingerprint = None
        self.assertNotEqual(name.rsplit("-", 1)[1], other)
