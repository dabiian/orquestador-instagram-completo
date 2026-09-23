from django.db import models
from django.utils import timezone


class AccountOwner(models.Model):
    owner_name = models.CharField(max_length=255)
    owner_email = models.EmailField()
    owner_phone = models.CharField(max_length=20)
    owner_urls = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.owner_name
