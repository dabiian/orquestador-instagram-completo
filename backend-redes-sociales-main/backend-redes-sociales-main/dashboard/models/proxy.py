from django.db import models
from django.utils import timezone


class Proxy(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    port = models.PositiveIntegerField(unique=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.ip_address}:{self.port}"
