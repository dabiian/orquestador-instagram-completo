from django.db import models
from django.utils import timezone
from .social_media_platform import SocialMediaPlatform


class TaskType(models.Model):
    OPERATION_CHOICES = (
        ("maduracion", "Maduración"),
        ("prospecting", "Prospección"),
    )

    task_name = models.CharField(max_length=255)
    creator = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=255, default="detail")
    create_date = models.DateTimeField(default=timezone.now)
    platform = models.ForeignKey(SocialMediaPlatform, on_delete=models.CASCADE)
    operation = models.CharField(
        max_length=32,
        choices=OPERATION_CHOICES,
        null=True,
        blank=True,
        help_text="Categoría funcional usada por el orquestador de Instagram.",
    )

    def __str__(self):
        return self.task_name
