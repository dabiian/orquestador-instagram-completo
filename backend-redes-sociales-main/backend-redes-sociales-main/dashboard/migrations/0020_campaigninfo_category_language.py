from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0019_fix_taskbot_task_type_array"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaigninfo",
            name="category",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="campaigninfo",
            name="language",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
