"""2.0.0 (lot 4) : migration de données séparée du schéma (0004).

En retour arrière, elle s'exécute d'abord, dans sa propre transaction ; PostgreSQL refuse de modifier une table
dans la transaction qui vient d'en mettre des lignes à jour (« pending trigger events », constaté le 16 novembre
2026 lors de l'aller-retour sur une base temporaire). En avant, elle ne fait rien.
"""
from django.db import migrations


def back_to_known_values(apps, schema_editor):
    """Retour arrière : les tâches de résumé sont annulées (aucune supprimée), le lancement « après » devient
    « immédiat » ; les états et lancements restent ainsi connus de la version précédente."""
    Job = apps.get_model("translation", "TranslationJob")
    Job.objects.filter(kind="summary").exclude(status__in=("done", "failed", "cancelled")).update(status="cancelled")
    Job.objects.filter(launch="after").update(launch="immediate")


class Migration(migrations.Migration):

    dependencies = [
        ("translation", "0004_resumes_et_textes_anciens"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, back_to_known_values),
    ]
