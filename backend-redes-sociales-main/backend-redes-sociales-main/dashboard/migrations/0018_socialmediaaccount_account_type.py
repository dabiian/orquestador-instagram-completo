from django.db import migrations, models


class Migration(migrations.Migration):
    """Persist the account_type field already present in the Django model.

    This is intentionally a focused migration.  The legacy project contains
    other model/state drift that predates the Instagram orchestrator adapter;
    folding those unrelated changes into this migration would make deployment
    unsafe.  The adapter, catalog and task-claim endpoint all require this
    column to distinguish Instagram accounts fail-closed.
    """

    dependencies = [
        ("dashboard", "0017_orchestrator_instagram"),
    ]

    operations = [
        migrations.AddField(
            model_name="socialmediaaccount",
            name="account_type",
            field=models.CharField(default="personal_account", max_length=255),
        ),
    ]
