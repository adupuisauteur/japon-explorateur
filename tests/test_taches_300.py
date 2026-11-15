"""2.0.0 — lot 3 : file des tâches (immédiat, maintenant, programmé, nuit), horloge, pauses, plafonds, page Tâches.

Moteur DeepL sur réponses simulées (aucun réseau) ; Celery en mode immédiat ; dates fixées dans les tests.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.notifications.models import Notification
from apps.translation import queue as Q
from apps.translation import services
from apps.translation.engines.deepl import DeepLEngine
from apps.translation.models import EngineSetting, TranslationJob, TranslationPreference, TranslationProject

from .test_translation_pipeline import PipelineTestCase


def at(day, hour, minute=0):
    """Date locale (fuseau du projet) du 15 + `day` novembre 2026."""
    return timezone.make_aware(datetime(2026, 11, 15 + day, hour, minute), timezone.get_current_timezone())


class TickMixin:
    def tick(self, now):
        """Un passage de l'horloge ; les départs sont envoyés après la validation de la transaction."""
        with mock.patch("django.utils.timezone.now", return_value=now), \
                self.captureOnCommitCallbacks(execute=True):
            return Q.clock(now)


PipelineTestCase = type("PipelineTestCase", (TickMixin, PipelineTestCase), {})


class WindowTests(PipelineTestCase):
    def pref(self, start, end):
        pref = TranslationPreference.objects.get(user=self.user)
        pref.night_start, pref.night_end = start, end
        pref.save()
        return pref

    def test_overnight_window(self):
        pref = self.pref(time(22), time(7))
        self.assertEqual(Q.current_window(pref, at(0, 23)), (at(0, 22), at(1, 7)))
        self.assertEqual(Q.current_window(pref, at(1, 6, 59)), (at(0, 22), at(1, 7)))
        self.assertIsNone(Q.current_window(pref, at(1, 7)))
        self.assertIsNone(Q.current_window(pref, at(1, 12)))
        self.assertEqual(Q.next_window_start(pref, at(1, 12)), at(1, 22))
        self.assertEqual(Q.window_label(pref), "22:00 – 07:00")

    def test_same_day_window_and_no_window(self):
        pref = self.pref(time(1), time(5))
        self.assertEqual(Q.current_window(pref, at(1, 2)), (at(1, 1), at(1, 5)))
        self.assertIsNone(Q.current_window(pref, at(1, 6)))
        pref = self.pref(None, None)
        self.assertIsNone(Q.current_window(pref, at(1, 2)))
        self.assertFalse(Q.has_night_window(pref))

    def test_preference_form_requires_both_ends(self):
        self.client.force_login(self.user)
        self.client.post("/traduction/moteurs/choix/", {"default_engine": "deepl", "confirmation_threshold": 20000,
                                                        "night_start": "22:00"})
        self.assertIsNone(TranslationPreference.objects.get(user=self.user).night_start)
        self.client.post("/traduction/moteurs/choix/", {"default_engine": "deepl", "confirmation_threshold": 20000,
                                                        "night_start": "22:00", "night_end": "07:00",
                                                        "confirm_below": "0.05"})
        pref = TranslationPreference.objects.get(user=self.user)
        self.assertEqual((pref.night_start, pref.night_end, pref.confirm_below), (time(22), time(7), Decimal("0.05")))


class LaunchTests(PipelineTestCase):
    def job(self, *texts):
        return services.prepare_segments_job(self.user, self.doc(*(texts or ("一つ目の文。",))), project=self.project)

    def test_immediate_runs(self):
        job = self.run_job(self.job())
        self.assertEqual((job.status, job.launch), ("done", "immediate"))

    def test_scheduled_waits_for_its_time_and_never_starts_late(self):
        job = self.job()
        services.confirm(job, self.user, launch="scheduled", scheduled_for=timezone.now() + timedelta(hours=2))
        job.refresh_from_db()
        self.assertEqual(job.status, "scheduled")
        self.assertEqual(self.stub.texts, [])
        with self.assertRaises(services.TranslationUnavailable):
            services.confirm(self.job(), self.user, launch="scheduled", scheduled_for=timezone.now() - timedelta(1))
        # l'horloge passe juste après l'heure prévue : départ
        self.tick(job.scheduled_for + timedelta(minutes=1))
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        # une autre, dont l'heure est passée pendant un arrêt de J-ed : en retard, jamais lancée d'elle-même
        late = self.job("二つ目の文。")
        services.confirm(late, self.user, launch="scheduled", scheduled_for=timezone.now() + timedelta(hours=1))
        report = self.tick(timezone.now() + timedelta(hours=3))
        late.refresh_from_db()
        self.assertEqual(late.status, "late")
        self.assertEqual(report["late"], [late.pk])
        self.assertNotIn("二つ目の文。", self.stub.texts)
        notification = Notification.objects.get(recipient=self.user, group_key=f"translation:{late.pk}:late")
        self.assertIn("ne part jamais d'elle-même", notification.body)
        services.resume(late, self.user)  # « Lancer maintenant »
        late.refresh_from_db()
        self.assertEqual((late.status, late.launch), ("done", "immediate"))

    def test_night_requires_a_window(self):
        with self.assertRaisesMessage(services.TranslationUnavailable, "Choisissez d'abord la plage"):
            services.confirm(self.job(), self.user, launch="night")


class NightTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        pref = TranslationPreference.objects.get(user=self.user)
        pref.night_start, pref.night_end = time(22), time(7)
        pref.save()

    def queue_jobs(self, n=2):
        jobs = []
        for i in range(n):
            job = services.prepare_segments_job(self.user, self.doc(f"夜の文{i}。"), project=self.project)
            services.confirm(job, self.user, launch="night")
            job.refresh_from_db()
            jobs.append(job)
        return jobs

    def test_night_queue_runs_in_order_during_the_window(self):
        first, second = self.queue_jobs()
        self.assertEqual((first.status, first.queue_position, second.queue_position), ("scheduled", 1, 2))
        Q.move(second, self.user, "up")
        first.refresh_from_db(), second.refresh_from_db()
        self.assertEqual((second.queue_position, first.queue_position), (1, 2))
        self.assertEqual(self.tick(at(0, 21, 59))["started"], [])  # avant la plage
        report = self.tick(at(0, 22, 1))  # à l'heure : la plage s'ouvre, le premier de la file part
        self.assertEqual(report["started"], [second.pk])
        self.assertEqual(self.stub.texts, ["夜の文1。"])
        report = self.tick(at(0, 22, 2))
        self.assertEqual(report["started"], [first.pk])
        # au matin : compte rendu
        report = self.tick(at(1, 7, 1))
        self.assertEqual(report["night_reports"], 1)
        notification = Notification.objects.get(recipient=self.user, title="Compte rendu de la nuit")
        self.assertIn("2 tâche(s) : 2 élément(s) traduit(s), 0 restant(s), 0 en échec", notification.body)

    def test_late_window_asks_for_confirmation(self):
        (job,) = self.queue_jobs(1)
        report = self.tick(at(0, 23, 30))  # J-ed démarré à 23 h 30 pour une plage de 22 h
        job.refresh_from_db()
        self.assertEqual((job.status, report["started"]), ("late", []))
        self.assertEqual(self.stub.texts, [])
        self.assertTrue(Notification.objects.filter(recipient=self.user, title="File de nuit non lancée : à confirmer")
                        .exists())
        self.assertEqual(self.tick(at(0, 23, 31))["started"], [])  # toujours rien
        Q.back_to_night(job, self.user)  # remise dans la file : partira la nuit suivante, à l'heure
        self.assertEqual(self.tick(at(1, 22, 0))["started"], [job.pk])

    def test_end_of_window_pauses_between_chunks_and_resumes_next_night(self):
        job = services.prepare_segments_job(self.user, self.doc("一。", "二。", "三。"), project=self.project)
        services.confirm(job, self.user, launch="night")
        self.tick(at(0, 22, 0))  # ouverture ; la tâche part
        job.refresh_from_db()
        self.assertEqual(job.status, "done")  # mode immédiat : tout le travail tient dans la plage
        # deuxième tâche, plage terminée pendant le travail : pause après le premier paquet
        job = services.prepare_segments_job(self.user, self.doc("四。", "五。"), project=self.project)
        services.confirm(job, self.user, launch="night")
        job.refresh_from_db()
        job.status = "running"
        job.save()
        with mock.patch.object(DeepLEngine, "max_items", 1), \
                mock.patch("django.utils.timezone.now", return_value=at(1, 7, 5)):
            services.process_next_chunk(job.pk)
        job.refresh_from_db()
        self.assertEqual((job.status, job.pause_reason), ("paused", "night_end"))
        self.assertNotIn("四。", self.stub.texts)  # rien n'a été envoyé après la fin de la plage
        self.assertEqual(job.status_label, "En pause — fin de la plage de nuit")
        self.assertEqual(self.tick(at(1, 22, 0))["started"], [job.pk])
        job.refresh_from_db()
        self.assertEqual(job.status, "done")


class CapsAndPauseTests(PipelineTestCase):
    def test_monthly_cap_checked_before_each_send(self):
        """Plafond atteint EN COURS de tâche (par exemple par une autre tâche) : pause avant l'envoi suivant."""
        segs = self.doc("一つ目。", "二つ目。", "三つ目。")
        job = services.prepare_segments_job(self.user, segs, project=self.project)
        EngineSetting.objects.filter(user=self.user, engine="deepl").update(monthly_char_cap=len("一つ目。") * 2)
        TranslationJob.objects.filter(pk=job.pk).update(status="running", started_at=timezone.now())
        with mock.patch.object(DeepLEngine, "max_items", 1):
            while services.process_next_chunk(job.pk):
                pass
        job.refresh_from_db()
        self.assertEqual((job.status, job.pause_reason, job.done_items), ("paused", "cap", 2))
        self.assertEqual(self.stub.texts, ["一つ目。", "二つ目。"])  # le troisième n'est jamais parti
        self.assertIn("aucun autre moteur", job.error_summary)
        notification = Notification.objects.get(recipient=self.user, event_type="task_paused")
        self.assertIn("plafond atteint", notification.title)
        with self.assertRaises(services.TranslationUnavailable):  # plafond toujours atteint : reprise refusée
            services.resume(job, self.user)

    def test_user_pause_resume_and_cancel(self):
        job = services.prepare_segments_job(self.user, self.doc("一。"), project=self.project)
        services.confirm(job, self.user, launch="scheduled", scheduled_for=timezone.now() + timedelta(hours=1))
        Q.pause(job, self.user)
        job.refresh_from_db()
        self.assertEqual((job.status, job.status_label), ("paused", "En pause — demande de l'utilisateur"))
        self.assertEqual(self.tick(timezone.now() + timedelta(hours=2))["started"], [])  # en pause : ne part pas
        services.resume(job, self.user)
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        other = services.prepare_segments_job(self.user, self.doc("二。"), project=self.project)
        services.confirm(other, self.user, launch="scheduled", scheduled_for=timezone.now() + timedelta(hours=1))
        services.cancel(other, self.user)
        other.refresh_from_db()
        self.assertEqual(other.status, "cancelled")

    def test_status_label_for_errors(self):
        job = TranslationJob(status="done", failed_items=2)
        self.assertEqual(job.status_label, "Terminée avec erreurs")


class NowTests(PipelineTestCase):
    def setUp(self):
        super().setUp()
        from apps.catalog.models import Catalogue, Record

        self.record = Record.objects.create(catalogue=Catalogue.objects.get(code="codh-pmjt"), source_id="lot3-1",
                                            original_title="架空の書名", description_original="架空の説明。")
        self.client.force_login(self.user)

    def post(self, mode="now"):
        return self.client.post("/traduction/notices/maintenant/", {"records": self.record.record_id, "mode": mode,
                                                                     "next": self.record.get_absolute_url()})

    def test_paid_engine_goes_through_confirmation_unless_under_threshold(self):
        response = self.post()
        job = TranslationJob.objects.get(launch="now")
        self.assertRedirects(response, f"/traduction/taches/{job.pk}/", fetch_redirect_response=False)
        self.assertEqual(job.status, "draft")
        page = self.client.get(f"/traduction/taches/{job.pk}/").content.decode()
        self.assertIn('value="now" id="launch-now" checked', page)
        # seuil choisi par l'utilisateur, au-dessus du coût estimé : départ direct, résultat sur la fiche
        TranslationPreference.objects.filter(user=self.user).update(confirm_below=Decimal("1"))
        tariff = {"amount": Decimal("0.0002"), "currency": "USD", "basis": "tarif fictif", "tokens_in": 0,
                  "tokens_out": 0}
        with mock.patch("apps.translation.services.estimate", return_value=tariff):
            response = self.post()
        self.assertRedirects(response, self.record.get_absolute_url(), fetch_redirect_response=False)
        job = TranslationJob.objects.filter(launch="now").latest("created_at")
        self.assertEqual(job.status, "done")
        self.assertEqual(Q.queue_for(job), "maintenant")
        page = self.client.get(self.record.get_absolute_url()).content.decode()
        self.assertIn("Traduction prête", page)
        self.assertIn(f"/traduction/notices/{self.record.record_id}/", page)

    def test_threshold_never_skips_pending_terms(self):
        from apps.core.models import AuditLog
        from apps.translation import terms

        TranslationPreference.objects.filter(user=self.user).update(confirm_below=Decimal("1"))
        AuditLog.objects.filter(action=terms.ACTION).delete()
        self.post()
        self.assertEqual(TranslationJob.objects.get(launch="now").status, "draft")

    def test_night_from_the_record(self):
        response = self.post("night")
        job = TranslationJob.objects.get()
        self.assertRedirects(response, f"/traduction/taches/{job.pk}/?lancement=nuit", fetch_redirect_response=False)
        page = self.client.get(f"/traduction/taches/{job.pk}/?lancement=nuit").content.decode()
        self.assertIn('id="launch-night" checked disabled', page.replace("  ", " "))  # pas de plage : désactivé
        self.assertIn("Choisissez d'abord votre plage horaire", page)

    def test_library_buttons_and_reader_refused(self):
        from apps.library.models import LibraryEntry

        LibraryEntry.objects.create(user=self.user, record=self.record)
        page = self.client.get("/bibliotheque/").content.decode()
        self.assertIn('value="translate_now"', page)
        self.assertIn('value="translate_night"', page)
        self.client.force_login(self.reader)
        self.assertEqual(self.post().status_code, 403)

    def test_queue_routing(self):
        job = TranslationJob(launch="now", total_items=500)
        self.assertEqual(Q.queue_for(job), "maintenant")
        job.launch, job.total_items = "immediate", 5
        self.assertEqual(Q.queue_for(job), "maintenant")
        job.total_items = 500
        self.assertEqual(Q.queue_for(job), "traduction")
        job.launch, job.total_items = "night", 1
        self.assertEqual(Q.queue_for(job), "traduction")


class PageTests(PipelineTestCase):
    def test_tasks_page_sections_indicator_and_admin_view(self):
        secret = TranslationProject.objects.create(owner=self.user, title="Projet secret fictif", confidential=True)
        job = TranslationJob.objects.create(user=self.user, project=secret, engine="argos", status="running",
                                            heartbeat_at=timezone.now(), total_items=3,
                                            scope_label="3 segment(s) — Projet secret fictif")
        self.client.force_login(self.user)
        page = self.client.get("/traduction/taches/").content.decode()
        for title in ("En cours", "File de nuit", "Programmées", "À décider", "Terminées"):
            self.assertIn(f">{title}</h2>", page)
        self.assertIn("Projet secret fictif", page)
        self.assertIn("1 traduction en cours", page)  # indicateur de la barre de menu
        self.client.force_login(self.admin)
        page = self.client.get("/traduction/taches/?tous=1").content.decode()
        self.assertIn("Projet confidentiel", page)
        self.assertNotIn("Projet secret fictif", page)
        self.assertEqual(self.client.get(f"/traduction/taches/{job.pk}/").status_code, 404)  # contenu : auteur seul

    def test_report_on_finished_job(self):
        job = self.run_job(services.prepare_segments_job(self.user, self.doc("一つ目の文。"), project=self.project))
        report = services.job_report(job)
        self.assertEqual((report["done"], report["failed"], report["pending"]), (1, 0, 0))
        self.assertEqual(report["links"][0][0], "Document fictif")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(f"/traduction/taches/{job.pk}/"), "Compte rendu")


class WorkersTests(PipelineTestCase):
    def test_each_queue_needs_a_worker(self):
        from apps.core import health

        with self.settings(CELERY_TASK_ALWAYS_EAGER=False), \
                mock.patch("config.celery.app.control.ping", return_value=[{"courts@a": {"ok": "pong"}}]), \
                mock.patch("config.celery.app.control.inspect") as inspect:
            inspect.return_value.active_queues.return_value = {"courts@a": [{"name": "celery"}],
                                                               "traduction@b": [{"name": "traduction"}]}
            check = health.check_workers()
            self.assertEqual(check.level, health.ERROR)
            self.assertIn("« maintenant »", check.summary)
            inspect.return_value.active_queues.return_value["maintenant@c"] = [{"name": "maintenant"}]
            self.assertEqual(health.check_workers().level, health.OK)

    def test_clock_runs_on_the_short_queue(self):
        from django.conf import settings

        self.assertEqual(settings.CELERY_TASK_ROUTES["apps.translation.tasks.clock"]["queue"], "celery")
        self.assertEqual(settings.CELERY_BEAT_SCHEDULE["horloge-taches"]["task"], "apps.translation.tasks.clock")


class MigrationTests(TransactionTestCase):
    def test_rollback_maps_new_statuses_to_interrupted(self):
        from apps.accounts.models import User

        user = User.objects.create_user("migration-lot3", password="x-fictif-123456", role="researcher")
        for status in ("scheduled", "paused", "late", "done"):
            TranslationJob.objects.create(user=user, engine="deepl", status=status)
        executor = MigrationExecutor(connection)
        executor.migrate([("translation", "0002_paquets_argos")])
        with connection.cursor() as cursor:
            cursor.execute("SELECT status, COUNT(*) FROM translation_translationjob GROUP BY status ORDER BY status")
            self.assertEqual(cursor.fetchall(), [("done", 1), ("interrupted", 3)])
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
