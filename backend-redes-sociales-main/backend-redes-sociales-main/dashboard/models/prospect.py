from django.db import models

from dashboard.models.social_media_account import SocialMediaAccount
from dashboard.models.social_media_messages import SocialMediaMessage


class Prospect(models.Model):
    STATUS_CHOICES = [
        ("NEW", "New"),
        ("COMMENTED", "Commented"),
        ("NO_RESPONSE", "No Response"),
        ("RESPONDED", "Responded"),
        ("REQUESTED_DATA", "Requested Data"),
        ("REQUESTED_QUOTE", "Requested Quote"),
        ("ALERTED", "Alerted"),
        ("BLACKLISTED", "Blacklisted"),
    ]

    platform = models.CharField(
        max_length=20,
        default="facebook",
        editable=False,
        db_index=True,
    )
    external_account_id = models.CharField(max_length=255, unique=True, db_index=True)
    account_name = models.CharField(max_length=255, blank=True, null=True)
    category_key = models.CharField(max_length=100, blank=True, null=True)
    profile_url = models.URLField(max_length=1000, blank=True, null=True)
    source_hashtag = models.CharField(max_length=255, blank=True, null=True)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="NEW",
        db_index=True,
    )

    discovered_by_account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovered_prospects",
        to_field="id",
    )

    first_seen_at = models.DateTimeField(auto_now_add=True)
    first_commented_at = models.DateTimeField(blank=True, null=True)
    last_checked_at = models.DateTimeField(blank=True, null=True)
    last_response_at = models.DateTimeField(blank=True, null=True)
    last_alert_at = models.DateTimeField(blank=True, null=True)

    competitor_score = models.PositiveIntegerField(default=0)
    is_blacklisted = models.BooleanField(default=False, db_index=True)
    blacklist_reason = models.TextField(blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prospects"
        indexes = [
            models.Index(fields=["platform"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_blacklisted"]),
            models.Index(fields=["account_name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.account_name or self.external_account_id


class ProspectPost(models.Model):
    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        related_name="posts",
    )

    external_post_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    post_url = models.URLField(max_length=1000, blank=True, null=True)
    post_text = models.TextField(blank=True, null=True)
    post_published_at = models.DateTimeField(blank=True, null=True)
    matched_hashtag = models.CharField(max_length=255, blank=True, null=True)
    used_for_intro_comment = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prospect_posts"
        indexes = [
            models.Index(fields=["external_post_id"]),
            models.Index(fields=["used_for_intro_comment"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.external_post_id or f"post-{self.pk}"


class ProspectComment(models.Model):
    ACTOR_CHOICES = [
        ("BOT", "Bot"),
        ("PROSPECT", "Prospect"),
        ("HUMAN", "Human"),
    ]

    COMMENT_KIND_CHOICES = [
        ("INTRO", "Intro"),
        ("AUTO_REPLY_DATA", "Auto Reply Data"),
        ("AUTO_REPLY_QUOTE", "Auto Reply Quote"),
        ("FOLLOW_UP", "Follow Up"),
        ("HUMAN_REPLY", "Human Reply"),
        ("OTHER", "Other"),
    ]

    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    post = models.ForeignKey(
        ProspectPost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comments",
    )

    bot_account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospect_comments",
        to_field="id",
    )

    related_message = models.ForeignKey(
        SocialMediaMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospect_comments",
        to_field="id",
    )

    platform_comment_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    actor_type = models.CharField(max_length=20, choices=ACTOR_CHOICES, db_index=True)
    comment_kind = models.CharField(
        max_length=30,
        choices=COMMENT_KIND_CHOICES,
        default="OTHER",
        db_index=True,
    )

    template_id = models.CharField(max_length=100, blank=True, null=True)
    body = models.TextField()
    is_public = models.BooleanField(default=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prospect_comments"
        indexes = [
            models.Index(fields=["platform_comment_id"]),
            models.Index(fields=["actor_type"]),
            models.Index(fields=["comment_kind"]),
            models.Index(fields=["sent_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.actor_type} - {self.comment_kind} - {self.pk}"


class ProspectReplyClassification(models.Model):
    INTENT_CHOICES = [
        ("REQUESTED_DATA", "Requested Data"),
        ("REQUESTED_QUOTE", "Requested Quote"),
        ("POSITIVE", "Positive"),
        ("AMBIGUOUS", "Ambiguous"),
        ("IGNORE", "Ignore"),
    ]

    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        related_name="classifications",
    )

    comment = models.ForeignKey(
        ProspectComment,
        on_delete=models.CASCADE,
        related_name="classifications",
    )

    intent = models.CharField(max_length=30, choices=INTENT_CHOICES, db_index=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    matched_keywords = models.JSONField(default=list, blank=True)
    priority = models.CharField(max_length=20, blank=True, null=True)
    decision_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prospect_reply_classifications"
        indexes = [
            models.Index(fields=["intent"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.intent} - {self.confidence}"


class AlertLog(models.Model):
    EVENT_CHOICES = [
        ("DATA_REQUEST", "Data Request"),
        ("QUOTE_REQUEST", "Quote Request"),
    ]

    PRIORITY_CHOICES = [
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
    ]

    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        related_name="alerts",
    )

    bot_account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prospect_alerts",
        to_field="id",
    )

    event_code = models.CharField(max_length=30, choices=EVENT_CHOICES, db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="NORMAL", db_index=True)

    email_sent = models.BooleanField(default=False)
    whatsapp_sent = models.BooleanField(default=False)
    email_message_id = models.CharField(max_length=255, blank=True, null=True)
    whatsapp_message_id = models.CharField(max_length=255, blank=True, null=True)

    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alerts_log"
        indexes = [
            models.Index(fields=["event_code"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["sent_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.event_code} - {self.priority}"


class BlacklistAccount(models.Model):
    platform = models.CharField(
        max_length=20,
        default="facebook",
        editable=False,
        db_index=True,
    )

    external_account_id = models.CharField(max_length=255, unique=True, db_index=True)
    account_name = models.CharField(max_length=255, blank=True, null=True)
    profile_url = models.URLField(max_length=1000, blank=True, null=True)

    source = models.CharField(max_length=50, blank=True, null=True)
    score = models.PositiveIntegerField(default=0)
    matched_layers = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blacklist_accounts"
        indexes = [
            models.Index(fields=["platform"]),
            models.Index(fields=["external_account_id"]),
            models.Index(fields=["account_name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.account_name or self.external_account_id


class QuoteAnswer(models.Model):
    prospect = models.OneToOneField(
        Prospect,
        on_delete=models.CASCADE,
        related_name="quote_answer",
    )

    q1_type_of_cleaning = models.TextField(blank=True, null=True)
    q2_space_size = models.TextField(blank=True, null=True)
    q3_needed_date = models.TextField(blank=True, null=True)
    q4_condition = models.TextField(blank=True, null=True)

    min_answers_ready_for_alert = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "quote_answers"

    def __str__(self):
        return f"QuoteAnswer - Prospect {self.prospect_id}"