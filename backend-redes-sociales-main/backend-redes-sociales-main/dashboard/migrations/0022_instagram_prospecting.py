import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0021_tasktype_operation"),
    ]

    operations = [
        migrations.CreateModel(
            name="InstagramProspectingCampaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("platform", models.CharField(db_index=True, default="instagram", max_length=30)),
                ("status", models.CharField(db_index=True, default="active", max_length=30)),
                ("services_snapshot", models.JSONField(blank=True, default=list)),
                ("strategy_snapshot", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "social_media_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="instagram_prospecting_campaigns",
                        to="dashboard.socialmediaaccount",
                    ),
                ),
            ],
            options={
                "db_table": "instagram_prospecting_campaigns",
            },
        ),

        migrations.CreateModel(
            name="InstagramProspect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(db_index=True, default="instagram", max_length=30)),
                ("username", models.CharField(db_index=True, max_length=255)),
                ("profile_url", models.URLField(max_length=1000)),
                ("display_name", models.CharField(blank=True, default="", max_length=255)),
                ("bio", models.TextField(blank=True, default="")),
                ("industry_detected", models.CharField(blank=True, default="", max_length=255)),
                ("source_type", models.CharField(default="keyword", max_length=50)),
                ("source_value", models.CharField(blank=True, default="", max_length=500)),
                ("status", models.CharField(db_index=True, default="new", max_length=50)),
                ("qualification_score", models.FloatField(default=0)),
                ("qualification_reason", models.TextField(blank=True, default="")),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prospects",
                        to="dashboard.instagramprospectingcampaign",
                    ),
                ),
            ],
            options={
                "db_table": "instagram_prospects",
            },
        ),

        migrations.CreateModel(
            name="InstagramProspectPost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("post_url", models.URLField(max_length=1000)),
                ("post_type", models.CharField(default="post", max_length=50)),
                ("caption_text", models.TextField(blank=True, default="")),
                ("analysis_status", models.CharField(db_index=True, default="pending", max_length=50)),
                ("is_relevant", models.BooleanField(blank=True, null=True)),
                ("analysis_reason", models.TextField(blank=True, default="")),
                ("status", models.CharField(db_index=True, default="new", max_length=50)),
                ("commented_at", models.DateTimeField(blank=True, null=True)),
                ("last_comment_text", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "prospect",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="posts",
                        to="dashboard.instagramprospect",
                    ),
                ),
            ],
            options={
                "db_table": "instagram_prospect_posts",
            },
        ),

        migrations.CreateModel(
            name="InstagramProspectInteraction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("interaction_type", models.CharField(db_index=True, max_length=50)),
                ("direction", models.CharField(default="outbound", max_length=30)),
                ("content_text", models.TextField(blank=True, default="")),
                ("classification", models.JSONField(blank=True, null=True)),
                ("status", models.CharField(db_index=True, default="success", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "prospect",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interactions",
                        to="dashboard.instagramprospect",
                    ),
                ),
                (
                    "social_media_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="instagram_prospecting_interactions",
                        to="dashboard.socialmediaaccount",
                    ),
                ),
                (
                    "prospect_post",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="interactions",
                        to="dashboard.instagramprospectpost",
                    ),
                ),
            ],
            options={
                "db_table": "instagram_prospect_interactions",
            },
        ),

        migrations.CreateModel(
            name="InstagramFollowUpAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alert_type", models.CharField(default="email", max_length=50)),
                ("status", models.CharField(db_index=True, default="pending", max_length=50)),
                ("email_to", models.EmailField(blank=True, max_length=254, null=True)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "prospect",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="follow_up_alerts",
                        to="dashboard.instagramprospect",
                    ),
                ),
                (
                    "interaction",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="follow_up_alerts",
                        to="dashboard.instagramprospectinteraction",
                    ),
                ),
                (
                    "prospect_post",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="follow_up_alerts",
                        to="dashboard.instagramprospectpost",
                    ),
                ),
            ],
            options={
                "db_table": "instagram_follow_up_alerts",
            },
        ),

        migrations.AddIndex(
            model_name="instagramprospectingcampaign",
            index=models.Index(
                fields=["platform", "status"],
                name="instagram_p_platfor_bc8970_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="instagramprospectingcampaign",
            index=models.Index(
                fields=["social_media_account", "status"],
                name="instagram_p_social__fe8762_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="instagramprospect",
            index=models.Index(
                fields=["campaign", "platform", "username"],
                name="instagram_p_campaig_1ea60e_idx",
            ),
        ),

        migrations.AddIndex(
            model_name="instagramprospect",
            index=models.Index(
                fields=["status"],
                name="instagram_p_status_31bd46_idx",
            ),
        ),

        migrations.AddConstraint(
            model_name="instagramprospect",
            constraint=models.UniqueConstraint(
                fields=("campaign", "platform", "username"),
                name="uniq_instagram_prospect_campaign_platform_username",
            ),
        ),

        migrations.AddConstraint(
            model_name="instagramprospectpost",
            constraint=models.UniqueConstraint(
                fields=("prospect", "post_url"),
                name="uniq_instagram_prospect_post_url",
            ),
        ),
    ]
