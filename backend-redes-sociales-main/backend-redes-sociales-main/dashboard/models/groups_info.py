from django.db import models
from django.utils import timezone

class GroupsInfo(models.Model):
    group_name = models.CharField(max_length=255)
    description = models.TextField()
    rules = models.TextField()
    status = models.CharField(max_length=20, default="active")
    group_url = models.TextField(default="")
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = "groups_info"