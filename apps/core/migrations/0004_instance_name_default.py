"""2.0.0, décision D13 : nom d'instance « J-ed » par défaut pour les nouvelles installations.

Ne modifie que la valeur par défaut du champ : aucune valeur enregistrée n'est changée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_service_check"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appsettings",
            name="instance_name",
            field=models.CharField(default="J-ed", max_length=200, verbose_name="Nom de l'instance"),
        ),
    ]
