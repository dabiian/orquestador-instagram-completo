from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0023_instagram_prospect_post_no_response_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountowner",
            name="services",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="socialmediaaccount",
            name="group",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="socialmediaaccount",
            name="account_kind",
            field=models.CharField(default="business", max_length=20),
        ),
        migrations.AlterField(
            model_name="proxy",
            name="port",
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name="instagramprospectingcampaign",
            name="name",
            field=models.CharField(max_length=150),
        ),
        migrations.AddField(
            model_name="instagramprospectingcampaign",
            name="business_description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="instagramprospectingcampaign",
            name="business_hours",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="instagramprospectingcampaign",
            name="follow_up_phone",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="instagramprospectingcampaign",
            name="follow_up_email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name="instagramprospectingcampaign",
            name="owner_instagram_profile_url",
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
        migrations.CreateModel(
            name="InstagramProspectingCampaignAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(db_index=True, default="instagram", max_length=30)),
                ("role", models.CharField(default="prospecting", max_length=30)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("daily_limit", models.PositiveIntegerField(blank=True, null=True)),
                ("total_limit", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="account_assignments", to="dashboard.instagramprospectingcampaign")),
                ("social_media_account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="instagram_prospecting_assignments", to="dashboard.socialmediaaccount")),
            ],
            options={"db_table": "instagram_prospecting_campaign_accounts"},
        ),
        migrations.AddConstraint(
            model_name="instagramprospectingcampaignaccount",
            constraint=models.UniqueConstraint(fields=("campaign", "social_media_account"), name="uniq_instagram_campaign_account"),
        ),
        migrations.AddIndex(
            model_name="instagramprospectingcampaignaccount",
            index=models.Index(fields=["social_media_account", "platform", "is_active"], name="ig_ca_acct_plat_active"),
        ),
        migrations.AddIndex(
            model_name="instagramprospectingcampaignaccount",
            index=models.Index(fields=["campaign", "is_active"], name="ig_ca_campaign_active"),
        ),
    ]
