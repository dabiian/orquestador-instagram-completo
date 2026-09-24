from django.db import models

from .social_media_account import SocialMediaAccount


class InstagramProspectingCampaign(models.Model):
    name = models.CharField(max_length=150)
    platform = models.CharField(max_length=30, default="instagram", db_index=True)
    status = models.CharField(max_length=30, default="active", db_index=True)

    social_media_account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.CASCADE,
        related_name="instagram_prospecting_campaigns",
    )

    services_snapshot = models.JSONField(default=list, blank=True)
    strategy_snapshot = models.JSONField(default=dict, blank=True)
    business_description = models.TextField(null=True, blank=True)
    business_hours = models.TextField(null=True, blank=True)
    follow_up_phone = models.CharField(max_length=50, null=True, blank=True)
    follow_up_email = models.EmailField(null=True, blank=True)
    owner_instagram_profile_url = models.CharField(max_length=1000, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instagram_prospecting_campaigns"
        indexes = [
            models.Index(fields=["platform", "status"]),
            models.Index(fields=["social_media_account", "status"]),
        ]

    def __str__(self):
        return self.name


class InstagramProspectingCampaignAccount(models.Model):
    campaign = models.ForeignKey(
        InstagramProspectingCampaign,
        on_delete=models.CASCADE,
        related_name="account_assignments",
    )
    social_media_account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.CASCADE,
        related_name="instagram_prospecting_assignments",
    )
    platform = models.CharField(max_length=30, default="instagram", db_index=True)
    role = models.CharField(max_length=30, default="prospecting")
    is_active = models.BooleanField(default=True, db_index=True)
    daily_limit = models.PositiveIntegerField(null=True, blank=True)
    total_limit = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instagram_prospecting_campaign_accounts"
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "social_media_account"],
                name="uniq_instagram_campaign_account",
            )
        ]
        indexes = [
            models.Index(fields=["social_media_account", "platform", "is_active"], name="ig_ca_acct_plat_active"),
            models.Index(fields=["campaign", "is_active"], name="ig_ca_campaign_active"),
        ]

    def __str__(self):
        return f"{self.campaign_id}:{self.social_media_account_id}:{self.platform}"


class InstagramProspect(models.Model):
    campaign = models.ForeignKey(
        InstagramProspectingCampaign,
        on_delete=models.CASCADE,
        related_name="prospects",
    )

    platform = models.CharField(max_length=30, default="instagram", db_index=True)
    username = models.CharField(max_length=255, db_index=True)
    profile_url = models.URLField(max_length=1000)

    display_name = models.CharField(max_length=255, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    industry_detected = models.CharField(max_length=255, blank=True, default="")

    source_type = models.CharField(max_length=50, default="keyword")
    source_value = models.CharField(max_length=500, blank=True, default="")

    status = models.CharField(max_length=50, default="new", db_index=True)
    qualification_score = models.FloatField(default=0)
    qualification_reason = models.TextField(blank=True, default="")

    metadata_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instagram_prospects"
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "platform", "username"],
                name="uniq_instagram_prospect_campaign_platform_username",
            )
        ]
        indexes = [
            models.Index(fields=["campaign", "platform", "username"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.username


class InstagramProspectPost(models.Model):
    prospect = models.ForeignKey(
        InstagramProspect,
        on_delete=models.CASCADE,
        related_name="posts",
    )

    post_url = models.URLField(max_length=1000)
    post_type = models.CharField(max_length=50, default="post")
    caption_text = models.TextField(blank=True, default="")

    analysis_status = models.CharField(max_length=50, default="pending", db_index=True)
    is_relevant = models.BooleanField(null=True, blank=True)
    analysis_reason = models.TextField(blank=True, default="")

    status = models.CharField(max_length=50, default="new", db_index=True)
    commented_at = models.DateTimeField(null=True, blank=True)
    no_response_at = models.DateTimeField(null=True, blank=True)
    last_comment_text = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instagram_prospect_posts"
        constraints = [
            models.UniqueConstraint(
                fields=["prospect", "post_url"],
                name="uniq_instagram_prospect_post_url",
            )
        ]

    def __str__(self):
        return self.post_url


class InstagramProspectInteraction(models.Model):
    prospect = models.ForeignKey(
        InstagramProspect,
        on_delete=models.CASCADE,
        related_name="interactions",
    )

    prospect_post = models.ForeignKey(
        InstagramProspectPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interactions",
    )

    social_media_account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instagram_prospecting_interactions",
    )

    interaction_type = models.CharField(max_length=50, db_index=True)
    direction = models.CharField(max_length=30, default="outbound")
    content_text = models.TextField(blank=True, default="")
    classification = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=50, default="success", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "instagram_prospect_interactions"

    def __str__(self):
        return f"{self.prospect_id}:{self.interaction_type}"


class InstagramFollowUpAlert(models.Model):
    prospect = models.ForeignKey(
        InstagramProspect,
        on_delete=models.CASCADE,
        related_name="follow_up_alerts",
    )

    prospect_post = models.ForeignKey(
        InstagramProspectPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_alerts",
    )

    interaction = models.ForeignKey(
        InstagramProspectInteraction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_alerts",
    )

    alert_type = models.CharField(max_length=50, default="email")
    status = models.CharField(max_length=50, default="pending", db_index=True)
    email_to = models.EmailField(null=True, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instagram_follow_up_alerts"

    def __str__(self):
        return f"{self.alert_type}:{self.prospect_id}:{self.status}"

