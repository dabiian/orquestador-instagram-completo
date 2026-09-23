from django.db import models
from django.utils import timezone


class OrchestratorInstagramExecution(models.Model):
    """Correlation between one RPA execution and the legacy Instagram TaskBots."""

    execution_id = models.UUIDField(unique=True, db_index=True)
    capability = models.CharField(max_length=120)
    stage = models.CharField(max_length=120, blank=True, null=True)
    status = models.CharField(max_length=30, default="running", db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    cancel_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orchestrator_instagram_executions"
        indexes = [
            models.Index(fields=["status", "-id"], name="orch_ig_exec_status_idx"),
            models.Index(fields=["capability", "-id"], name="orch_ig_exec_capability_idx"),
        ]


class OrchestratorInstagramTask(models.Model):
    """Links a legacy TaskBot to an RPA execution without changing TaskBot."""

    execution = models.ForeignKey(
        OrchestratorInstagramExecution,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    task_bot = models.OneToOneField(
        "dashboard.TaskBot",
        on_delete=models.CASCADE,
        related_name="orchestrator_link",
    )
    account_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "orchestrator_instagram_tasks"
        indexes = [
            models.Index(fields=["execution", "account_id"], name="orch_ig_task_exec_acc_idx"),
        ]
