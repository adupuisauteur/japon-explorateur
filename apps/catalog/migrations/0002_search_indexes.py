"""Index de recherche PostgreSQL (trigrammes) pour les recherches par sous-chaîne en japonais.

Sans effet sur SQLite (installation d'essai)."""
from django.db import migrations


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS catalog_record_search_trgm ON catalog_record USING gin (search_text gin_trgm_ops)")
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS catalog_record_title_trgm ON catalog_record USING gin (original_title gin_trgm_ops)")


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS catalog_record_search_trgm")
    schema_editor.execute("DROP INDEX IF EXISTS catalog_record_title_trgm")


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
