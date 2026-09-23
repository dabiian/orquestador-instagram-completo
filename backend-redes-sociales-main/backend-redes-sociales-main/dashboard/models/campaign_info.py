from django.db import models
from django.utils import timezone

class CampaignInfo(models.Model):
    campaign_name = models.CharField(max_length=255)
    category = models.CharField(max_length=255, default="", blank=True)
    language = models.CharField(max_length=255, default="", blank=True)
    campaign_info = models.TextField()
    phone_number = models.CharField(max_length=255)
    alt_phone_number = models.CharField(max_length=255)
    webpage_url = models.TextField()
    fanpage_url = models.TextField()
    status = models.CharField(max_length=20, default="active")
    prospectation_groups = models.ManyToManyField(
        "dashboard.ProspectationGroups",
        through="dashboard.CampaignProspectationGroup",
        related_name="campaigns",
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = "campaign_info"