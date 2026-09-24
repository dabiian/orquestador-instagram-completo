from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0022_instagram_prospecting"),
    ]

    operations = [
        migrations.AddField(
            model_name="instagramprospectpost",
            name="no_response_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
