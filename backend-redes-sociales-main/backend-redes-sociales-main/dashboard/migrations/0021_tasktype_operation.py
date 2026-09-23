from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0020_campaigninfo_category_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="tasktype",
            name="operation",
            field=models.CharField(
                blank=True,
                choices=[
                    ("maduracion", "Maduración"),
                    ("prospecting", "Prospección"),
                ],
                help_text="Categoría funcional usada por el orquestador de Instagram.",
                max_length=32,
                null=True,
            ),
        ),
    ]
