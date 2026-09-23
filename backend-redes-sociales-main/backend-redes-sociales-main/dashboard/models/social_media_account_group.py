from django.db import models

from dashboard.models.groups_info import GroupsInfo
from dashboard.models.social_media_account import SocialMediaAccount

class SocialMediaAccountGroup(models.Model):
    account = models.ForeignKey(
        SocialMediaAccount,
        on_delete=models.CASCADE,
        db_column="account_id",
    )
    group = models.ForeignKey(
        GroupsInfo,
        on_delete=models.CASCADE,
        db_column="group_id",
    )
    
    growth = models.BooleanField(default=False)
    is_prospection = models.BooleanField(default=False)

    class Meta:
        db_table = "social_media_account_groups"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "group"],
                name="uq_socialmediaaccount_group",
            )
        ]
