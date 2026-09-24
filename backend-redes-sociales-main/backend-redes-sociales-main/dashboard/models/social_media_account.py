from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from .account_owner import AccountOwner
from .Bot_personality import BotPersonality
from .proxy import Proxy
from .campaign_info import CampaignInfo


class SocialMediaAccount(models.Model):
    bot_personality = models.ForeignKey(
        BotPersonality, null=True, on_delete=models.SET_NULL
    )
    groups_to_search = ArrayField(models.CharField(max_length=255), default=list, blank=True)
    professional_mode = models.BooleanField(null=False, default=False)
    account_name = models.CharField(max_length=255)
    group = models.JSONField(default=list)
    account_kind = models.CharField(max_length=20, default="business")
    access_token = models.CharField(max_length=255, null=True, blank=True)
    access_secret = models.CharField(max_length=255, null=True, blank=True)
    other_credentials = models.JSONField(null=True, blank=True)
    owner = models.ForeignKey(AccountOwner, on_delete=models.CASCADE)
    proxy = models.OneToOneField(
        Proxy, null=True, blank=True, on_delete=models.SET_NULL
    )
    campaign_info = models.ForeignKey(
        CampaignInfo, null=True, blank=True, on_delete=models.SET_NULL
    )
    account_type = models.CharField(max_length=255, default='personal_account')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
     
    def __str__(self):
        return self.account_name + " : " + str(self.id)
