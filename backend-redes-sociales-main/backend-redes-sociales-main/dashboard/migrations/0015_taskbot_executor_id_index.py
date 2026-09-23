from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0014_taskbot_status_id_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="taskbot",
            index=models.Index(
                fields=["bot_executor", "-id"],
                name="taskbot_executor_id_idx",
            ),
        ),
    ]
