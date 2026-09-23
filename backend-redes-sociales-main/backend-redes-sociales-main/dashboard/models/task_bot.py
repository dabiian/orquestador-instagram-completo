from django.db import models
from django.utils import timezone
from .social_media_account import SocialMediaAccount
from .task_type import TaskType
from django.contrib.postgres.fields import ArrayField

class TaskBot(models.Model):
    task_type = ArrayField(
        base_field=models.IntegerField(),
        default=list,
        blank=True,
        null=True,
        db_column="task_type_id",
    )
    bot_executor = models.CharField(max_length=255, null=True, blank=True)
    status_process = models.CharField(max_length=255, null=True, blank=True)
    comment = models.JSONField(null=True, blank=True)
    social_media_account = models.ForeignKey(
        SocialMediaAccount, on_delete=models.CASCADE, null=True, blank=True
    )
    start_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    custom_task = models.JSONField(null=True, blank=True, default=dict)

    class Meta:
        indexes = [
            models.Index(
                fields=["status_process", "-id"],
                name="taskbot_status_id_idx",
            ),
            models.Index(
                fields=["bot_executor", "-id"],
                name="taskbot_executor_id_idx",
            ),
        ]

    def __str__(self):
        return f"{self.task_type} : {self.status_process} {self.bot_executor}: {self.social_media_account}"
