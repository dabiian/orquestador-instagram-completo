from django.db import models
from django.utils import timezone

from .task_bot import TaskBot


class BotExecutionReport(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_PARTIAL = "PARTIAL"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    task_bot = models.ForeignKey(
        TaskBot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_reports",
    )
    bot_executor = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
        db_index=True,
    )
    summary = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bot_execution_reports"
        indexes = [
            models.Index(fields=["task_bot", "-id"], name="bot_report_task_id_idx"),
            models.Index(fields=["status", "-id"], name="bot_report_status_id_idx"),
            models.Index(fields=["started_at"], name="bot_report_started_idx"),
        ]

    def __str__(self):
        return f"Report {self.pk} - {self.status}"


class BotExecutionStep(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_SKIPPED = "SKIPPED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    report = models.ForeignKey(
        BotExecutionReport,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
        db_index=True,
    )
    order = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bot_execution_steps"
        ordering = ["report_id", "order", "id"]
        indexes = [
            models.Index(fields=["report", "order"], name="bot_step_report_order_idx"),
            models.Index(fields=["status", "-id"], name="bot_step_status_id_idx"),
        ]

    def __str__(self):
        return f"{self.name} - {self.status}"


class BotExecutionArtifact(models.Model):
    TYPE_SCREENSHOT = "SCREENSHOT"
    TYPE_HTML = "HTML"
    TYPE_LOG = "LOG"
    TYPE_OTHER = "OTHER"

    ARTIFACT_TYPE_CHOICES = [
        (TYPE_SCREENSHOT, "Screenshot"),
        (TYPE_HTML, "HTML"),
        (TYPE_LOG, "Log"),
        (TYPE_OTHER, "Other"),
    ]

    report = models.ForeignKey(
        BotExecutionReport,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    step = models.ForeignKey(
        BotExecutionStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="artifacts",
    )
    artifact_type = models.CharField(
        max_length=20,
        choices=ARTIFACT_TYPE_CHOICES,
        default=TYPE_SCREENSHOT,
        db_index=True,
    )
    file = models.FileField(upload_to="bot_execution_artifacts/%Y/%m/%d/")
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    content_type = models.CharField(max_length=255, blank=True, null=True)
    size_bytes = models.PositiveBigIntegerField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bot_execution_artifacts"
        indexes = [
            models.Index(fields=["report", "-id"], name="bot_artifact_report_id_idx"),
            models.Index(fields=["step", "-id"], name="bot_artifact_step_id_idx"),
            models.Index(fields=["artifact_type", "-id"], name="bot_artifact_type_id_idx"),
        ]

    def __str__(self):
        return f"{self.artifact_type} - {self.file.name}"
