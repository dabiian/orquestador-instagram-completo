from django.db import migrations, models


PROSPECTING_TASK_IDS = [1, 7, 10, 11, 12, 15, 16]
MADURACION_TASK_IDS = [2, 3, 4, 5, 6, 8, 9, 13, 14]


def classify_instagram_task_types(apps, schema_editor):
    TaskType = apps.get_model("dashboard", "TaskType")
    instagram = TaskType.objects.filter(platform__platform_name__iexact="instagram")

    # Official mapping confirmed for the existing Instagram bot TASK_REGISTRY.
    # Restrict updates to Instagram so matching IDs on other platforms are untouched.
    instagram.filter(id__in=PROSPECTING_TASK_IDS).update(operation="prospecting")
    instagram.filter(id__in=MADURACION_TASK_IDS).update(operation="maduracion")


def unclassify_instagram_task_types(apps, schema_editor):
    TaskType = apps.get_model("dashboard", "TaskType")
    TaskType.objects.filter(
        platform__platform_name__iexact="instagram",
        id__in=PROSPECTING_TASK_IDS + MADURACION_TASK_IDS,
    ).update(operation=None)


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
        migrations.RunPython(
            classify_instagram_task_types,
            unclassify_instagram_task_types,
        ),
    ]
