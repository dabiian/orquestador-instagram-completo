from django.db import models
from django.utils import timezone


class SocialMediaPlatform(models.Model):
    platform_name = models.TextField(null=True, blank=True, unique=True)
    platform_api_url = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.platform_name
