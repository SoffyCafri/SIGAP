from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evaluation", "0004_alter_evaluaciones_fecha_evaluacion"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="evaluaciones",
            constraint=models.UniqueConstraint(
                fields=("proyecto", "no_revision"),
                name="evaluacion_proyecto_no_revision_unica",
            ),
        ),
    ]