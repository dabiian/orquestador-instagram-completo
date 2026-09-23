from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0013_remove_socialmediaaccount_group_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="taskbot",
            index=models.Index(
                fields=["status_process", "-id"],
                name="taskbot_status_id_idx",
            ),
        ),
    ]
