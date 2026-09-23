import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0018_socialmediaaccount_account_type"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE dashboard_taskbot
                        DROP CONSTRAINT IF EXISTS dashboard_taskbot_task_type_id_9db926a9_fk_dashboard;

                        DROP INDEX IF EXISTS dashboard_taskbot_task_type_id_9db926a9;

                        ALTER TABLE dashboard_taskbot
                        ALTER COLUMN task_type_id TYPE integer[]
                        USING CASE
                            WHEN task_type_id IS NULL THEN NULL
                            ELSE ARRAY[task_type_id::integer]
                        END;
                    """,
                    reverse_sql="""
                        ALTER TABLE dashboard_taskbot
                        ALTER COLUMN task_type_id TYPE bigint
                        USING CASE
                            WHEN task_type_id IS NULL OR cardinality(task_type_id) = 0 THEN NULL
                            ELSE task_type_id[1]::bigint
                        END;

                        CREATE INDEX dashboard_taskbot_task_type_id_9db926a9
                        ON dashboard_taskbot (task_type_id);

                        ALTER TABLE dashboard_taskbot
                        ADD CONSTRAINT dashboard_taskbot_task_type_id_9db926a9_fk_dashboard
                        FOREIGN KEY (task_type_id)
                        REFERENCES dashboard_tasktype(id)
                        DEFERRABLE INITIALLY DEFERRED;
                    """,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="taskbot",
                    name="task_type",
                    field=django.contrib.postgres.fields.ArrayField(
                        base_field=models.IntegerField(),
                        blank=True,
                        db_column="task_type_id",
                        default=list,
                        null=True,
                        size=None,
                    ),
                ),
            ],
        ),
    ]
