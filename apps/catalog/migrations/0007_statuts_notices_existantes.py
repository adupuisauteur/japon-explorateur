"""2.0.0, lot 2 : statuts des notices déjà enregistrées.

Calculés à partir des métadonnées stockées (champs et données brutes de la source), **sans appel réseau et
sans modifier les notices** : seule la nouvelle table `catalog_recordstatus` est remplie. Ce qui ne peut pas
être déduit reste « non vérifié ». Le retour en arrière vide la table.
"""
from django.db import migrations

BATCH = 500


def fill(apps, schema_editor):
    from apps.catalog.statuses import derive

    Record = apps.get_model("catalog", "Record")
    RecordStatus = apps.get_model("catalog", "RecordStatus")
    db = schema_editor.connection.alias
    done = set(RecordStatus.objects.using(db).values_list("record_id", "kind"))
    batch = []
    for record in Record.objects.using(db).select_related("catalogue").iterator(chunk_size=BATCH):
        for kind, status in derive(record).items():
            if (record.pk, kind) in done:
                continue
            batch.append(RecordStatus(record_id=record.pk, kind=kind, value=status.value, origin=status.origin,
                                      url=status.url[:600], detail=status.detail[:500],
                                      checked_at=status.checked_at))
        if len(batch) >= BATCH:
            RecordStatus.objects.using(db).bulk_create(batch)
            batch = []
    if batch:
        RecordStatus.objects.using(db).bulk_create(batch)


def empty(apps, schema_editor):
    RecordStatus = apps.get_model("catalog", "RecordStatus")
    RecordStatus.objects.using(schema_editor.connection.alias).all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_statuts_notice"),
    ]

    operations = [
        migrations.RunPython(fill, empty),
    ]
