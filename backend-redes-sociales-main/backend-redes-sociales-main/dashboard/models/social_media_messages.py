import hashlib
from django.db import models
from django.utils import timezone
from .social_media_account import SocialMediaAccount


class SocialMediaMessage(models.Model):

    STATUS_CHOICES = (
        ("active", "Active"),
        ("disabled", "Disabled"),
    )

    account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.CASCADE,
        related_name="messages",
        db_column="account_id",
    )

    message_text = models.TextField()
    category = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    message_hash = models.CharField(max_length=32, editable=False)

    class Meta:
        db_table = "social_media_messages"
        unique_together = ("account", "message_hash")

    def save(self, *args, **kwargs):
        normalized = (self.message_text or "").strip()
        self.message_text = normalized
        self.message_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_id} - {self.category}"