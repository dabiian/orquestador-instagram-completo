from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0016_bot_execution_models")]

    operations = [
        migrations.CreateModel(
            name="OrchestratorInstagramExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("execution_id", models.UUIDField(db_index=True, unique=True)),
                ("capability", models.CharField(max_length=120)),
                ("stage", models.CharField(blank=True, max_length=120, null=True)),
                ("status", models.CharField(db_index=True, default="running", max_length=30)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("result_payload", models.JSONField(blank=True, default=dict)),
                ("cancel_requested", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "orchestrator_instagram_executions"},
        ),
        migrations.CreateModel(
            name="OrchestratorInstagramTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("account_id", models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "execution",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="dashboard.orchestratorinstagramexecution",
                    ),
                ),
                (
                    "task_bot",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orchestrator_link",
                        to="dashboard.taskbot",
                    ),
                ),
            ],
            options={"db_table": "orchestrator_instagram_tasks"},
        ),
        migrations.AddIndex(
            model_name="orchestratorinstagramexecution",
            index=models.Index(fields=["status", "-id"], name="orch_ig_exec_status_idx"),
        ),
        migrations.AddIndex(
            model_name="orchestratorinstagramexecution",
            index=models.Index(fields=["capability", "-id"], name="orch_ig_exec_capability_idx"),
        ),
        migrations.AddIndex(
            model_name="orchestratorinstagramtask",
            index=models.Index(fields=["execution", "account_id"], name="orch_ig_task_exec_acc_idx"),
        ),
    ]
