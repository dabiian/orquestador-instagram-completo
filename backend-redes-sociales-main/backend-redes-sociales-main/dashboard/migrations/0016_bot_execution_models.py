# Generated manually for bot execution reporting models.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0015_taskbot_executor_id_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotExecutionReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("bot_executor", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("RUNNING", "Running"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                            ("PARTIAL", "Partial"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        db_index=True,
                        default="RUNNING",
                        max_length=20,
                    ),
                ),
                ("summary", models.TextField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "started_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now),
                ),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "task_bot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="execution_reports",
                        to="dashboard.taskbot",
                    ),
                ),
            ],
            options={
                "db_table": "bot_execution_reports",
            },
        ),
        migrations.CreateModel(
            name="BotExecutionStep",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("RUNNING", "Running"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                            ("SKIPPED", "Skipped"),
                        ],
                        db_index=True,
                        default="RUNNING",
                        max_length=20,
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("message", models.TextField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="dashboard.botexecutionreport",
                    ),
                ),
            ],
            options={
                "db_table": "bot_execution_steps",
                "ordering": ["report_id", "order", "id"],
            },
        ),
        migrations.CreateModel(
            name="BotExecutionArtifact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "artifact_type",
                    models.CharField(
                        choices=[
                            ("SCREENSHOT", "Screenshot"),
                            ("HTML", "HTML"),
                            ("LOG", "Log"),
                            ("OTHER", "Other"),
                        ],
                        db_index=True,
                        default="SCREENSHOT",
                        max_length=20,
                    ),
                ),
                (
                    "file",
                    models.FileField(upload_to="bot_execution_artifacts/%Y/%m/%d/"),
                ),
                ("original_filename", models.CharField(blank=True, max_length=255, null=True)),
                ("content_type", models.CharField(blank=True, max_length=255, null=True)),
                ("size_bytes", models.PositiveBigIntegerField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifacts",
                        to="dashboard.botexecutionreport",
                    ),
                ),
                (
                    "step",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="artifacts",
                        to="dashboard.botexecutionstep",
                    ),
                ),
            ],
            options={
                "db_table": "bot_execution_artifacts",
            },
        ),
        migrations.AddIndex(
            model_name="botexecutionreport",
            index=models.Index(
                fields=["task_bot", "-id"],
                name="bot_report_task_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="botexecutionreport",
            index=models.Index(
                fields=["status", "-id"],
                name="bot_report_status_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="botexecutionreport",
            index=models.Index(fields=["started_at"], name="bot_report_started_idx"),
        ),
        migrations.AddIndex(
            model_name="botexecutionstep",
            index=models.Index(
                fields=["report", "order"],
                name="bot_step_report_order_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="botexecutionstep",
            index=models.Index(
                fields=["status", "-id"],
                name="bot_step_status_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="botexecutionartifact",
            index=models.Index(
                fields=["report", "-id"],
                name="bot_artifact_report_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="botexecutionartifact",
            index=models.Index(
                fields=["step", "-id"],
                name="bot_artifact_step_id_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="botexecutionartifact",
            index=models.Index(
                fields=["artifact_type", "-id"],
                name="bot_artifact_type_id_idx",
            ),
        ),
    ]
