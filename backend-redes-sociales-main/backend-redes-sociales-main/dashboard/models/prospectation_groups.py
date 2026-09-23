from django.db import models
from django.utils import timezone

from dashboard.models.campaign_info import CampaignInfo

class ProspectationGroups(models.Model):
    group_name = models.CharField(max_length=255)
    group_url = models.TextField()
    service_category = models.CharField(max_length=255)
    city = models.CharField(max_length=20, default="active")

    class Meta:
        db_table = "prospectation_groups"


class CampaignProspectationGroup(models.Model):
    campaign = models.ForeignKey(
        CampaignInfo,
        on_delete=models.CASCADE,
        db_column="campaign_id",
    )
    prospectation_group = models.ForeignKey(
        ProspectationGroups,
        on_delete=models.CASCADE,
        db_column="prospectation_group_id",
    )

    class Meta:
        db_table = "campaign_prospectation_groups"
        unique_together = ("campaign", "prospectation_group")