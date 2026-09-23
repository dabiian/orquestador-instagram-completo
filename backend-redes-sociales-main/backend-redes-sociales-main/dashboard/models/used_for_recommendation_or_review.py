from django.db import models
from django.utils import timezone

from dashboard.models.social_media_account import SocialMediaAccount

class UsedForRecommendationOrReview(models.Model):
    account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.CASCADE,
        db_column="account_id",
    )
    review = models.BooleanField(default=False)
    mention = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "used_for_recommendation_or_review"
        constraints = [
            models.UniqueConstraint(
                fields=["account"],
                name="unique_used_for_recommendation_or_review_account"
            )
        ]