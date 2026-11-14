"""Évolution 1.3.0 — vérification avant retour à la 1.2.0 (commande en lecture seule)."""
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command

from apps.catalog.models import EditorialContent
from apps.catalog.services import upsert_record, validate_translation
from apps.translation import projects as P
from apps.translation.models import Glossary, TranslationProject, TranslationVersion

from .helpers import AppTestCase


class RollbackCheckTests(AppTestCase):
    def test_reports_and_exports_without_modifying_anything(self):
        project = TranslationProject.objects.create(owner=self.researcher, title="Projet fictif")
        document = P.create_document(project, title="Doc", text="架空の文。")
        P.add_human_version(document.segments.get(), self.researcher, "Phrase fictive.")
        Glossary.objects.create(owner=self.researcher, name="Glossaire fictif", remote_copies={"1": {"glossary_id": "x"}})
        record, _ = upsert_record(self.catalogue("codh-pmjt"), {"source_id": "R1", "original_title": "架空の書"})
        ed = EditorialContent.objects.create(record=record, kind="translation", target_field="original_title",
                                             content="Livre fictif", origin="mt", author=self.researcher)
        validate_translation(ed, self.admin)
        before = (TranslationVersion.objects.count(), EditorialContent.objects.count(), Glossary.objects.count())
        out = StringIO()
        path = Path(tempfile.mkdtemp()) / "sauvegarde.json"
        call_command("verifier_retour_120", exporter=str(path), stdout=out)
        text = out.getvalue()
        self.assertIn("traductions (versions) : 1", text)
        self.assertIn("propositions dans la couche éditoriale : 1", text)
        self.assertIn("titres traduits adoptés dans des notices : 1", text)
        self.assertIn("Glossaires ayant une copie chez DeepL : 1", text)
        self.assertIn("RUN_MIGRATIONS=0", text)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["notices_champs_mt"][0]["valeur"], "Livre fictif")
        self.assertEqual(len(data["couche_editoriale_mt"]), 1)
        self.assertNotIn("encrypted_key", path.read_text(encoding="utf-8"))
        self.assertEqual(before, (TranslationVersion.objects.count(), EditorialContent.objects.count(),
                                  Glossary.objects.count()))
