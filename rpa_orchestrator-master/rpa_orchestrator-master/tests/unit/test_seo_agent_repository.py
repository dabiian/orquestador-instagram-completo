from __future__ import annotations

from typing import Any

from orchestrator.infrastructure.seo_agent import management as management_module
from orchestrator.infrastructure.seo_agent.management import (
    SqlAlchemySeoAgentManagementRepository,
)


class RecordingConnection:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict[str, Any] = {}

    async def execute(self, statement: Any, params: dict[str, Any]) -> Any:
        self.statement = str(statement)
        self.params = params

        class Result:
            def scalar_one_or_none(self) -> int:
                return 302

        return Result()


class BeginContext:
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> RecordingConnection:
        return self.connection

    async def __aexit__(self, *args: Any) -> None:
        return None


class RecordingEngine:
    def __init__(self) -> None:
        self.connection = RecordingConnection()

    def begin(self) -> BeginContext:
        return BeginContext(self.connection)


async def test_queue_result_update_casts_reused_status_parameter(
    monkeypatch: Any,
) -> None:
    engine = RecordingEngine()
    monkeypatch.setattr(
        management_module,
        "get_seo_agent_engine",
        lambda: engine,
    )

    await SqlAlchemySeoAgentManagementRepository().update_queue_result(
        302,
        status="failed",
        result_status="failed",
        error_message="Orchestrator workflow failed",
    )

    assert "status = CAST(:status AS VARCHAR)" in engine.connection.statement
    assert "WHEN CAST(:status AS VARCHAR)" in engine.connection.statement
    assert engine.connection.params == {
        "queue_id": 302,
        "status": "failed",
        "result_status": "failed",
        "error_message": "Orchestrator workflow failed",
    }


async def test_queue_start_is_atomic_and_increments_attempts(monkeypatch: Any) -> None:
    engine = RecordingEngine()
    monkeypatch.setattr(management_module, "get_seo_agent_engine", lambda: engine)

    claimed = await SqlAlchemySeoAgentManagementRepository().mark_queue_running(302)

    assert claimed is True
    assert "WHERE id = :queue_id AND status = 'queued'" in engine.connection.statement
    assert "attempts = COALESCE(attempts, 0) + 1" in engine.connection.statement
    assert "RETURNING id" in engine.connection.statement


async def test_start_error_only_updates_running_queue(monkeypatch: Any) -> None:
    engine = RecordingEngine()
    monkeypatch.setattr(management_module, "get_seo_agent_engine", lambda: engine)

    await SqlAlchemySeoAgentManagementRepository().note_queue_start_error(
        302, "Flow startup interrupted"
    )

    assert "WHERE id = :queue_id AND status = 'running'" in engine.connection.statement
    assert engine.connection.params == {
        "queue_id": 302,
        "error_message": "Flow startup interrupted",
    }
