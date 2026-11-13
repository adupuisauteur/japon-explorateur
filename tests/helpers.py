"""Outils communs aux tests."""
import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.catalog.models import Catalogue

EXAMPLES = Path(__file__).resolve().parent.parent / "docs" / "exemples"
TMP = tempfile.mkdtemp(prefix="japon-tests-")


@override_settings(MEDIA_ROOT=TMP + "/files", BACKUP_DIR=Path(TMP) / "backups", CELERY_TASK_ALWAYS_EAGER=True,
                   AI_KEYS_ENCRYPTION_KEY="0cVdN3wJ3LPWRYZaWXkkGKs3MQs8Z1Ev3YyqHw2pTqU=",
                   STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class AppTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_sources", verbosity=0)
        cls.admin = User.objects.create_user("admin", password="motdepasse-solide-1", role="admin",
                                             is_staff=True, is_superuser=True)
        cls.researcher = User.objects.create_user("chercheur", password="motdepasse-solide-2", role="researcher")
        cls.reader = User.objects.create_user("lecteur", password="motdepasse-solide-3", role="reader")

    def setUp(self):
        self.client.force_login(self.admin)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def catalogue(self, code):
        return Catalogue.objects.get(code=code)

    def upload_example(self, name, catalogue="codh-pmjt", **extra):
        data = (EXAMPLES / name).read_bytes()
        response = self.client.post("/mises-a-jour/import/nouveau/", {
            "file": SimpleUploadedFile(name, data), "catalogue": catalogue, "preset": "auto",
            "dataset_label": "Jeu d'essai", "archive_source": "1", **extra})
        from apps.updates.models import ImportJob

        return response, ImportJob.objects.latest("pk")

    def import_example(self, name="exemple_inventaire.csv", catalogue="codh-pmjt"):
        _, job = self.upload_example(name, catalogue)
        mapping = {f"map_{k}": v for k, v in job.mapping.items()}
        self.client.post(job.get_absolute_url(), {"action": "stage", "duplicate_strategy": "version", **mapping})
        job.refresh_from_db()
        job.incoming.filter(comparison="new").update(decision="accept")
        self.client.post(job.get_absolute_url(), {"action": "apply"})
        job.refresh_from_db()
        return job
