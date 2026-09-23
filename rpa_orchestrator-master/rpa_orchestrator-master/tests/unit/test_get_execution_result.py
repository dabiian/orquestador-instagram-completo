from __future__ import annotations

from uuid import uuid4

import pytest

from orchestrator.application.use_cases.get_execution_result import GetExecutionResult
from orchestrator.domain.entities import Execution, ExecutionStatus


class FakeExecutionRepository:
    def __init__(self, execution: Execution | None) -> None:
        self.execution = execution

    async def get(self, execution_id):
        if self.execution is not None and self.execution.id == execution_id:
            return self.execution
        return None


class FakeDocumentRepository:
    def __init__(self, documents: dict[str, dict]) -> None:
        self.documents = documents

    async def get_document(self, document_id: str):
        return self.documents.get(document_id)


@pytest.mark.asyncio
async def test_result_returns_only_payload() -> None:
    execution = Execution(
        flow_id=str(uuid4()),
        requested_capability="instagram.prospecting",
        status=ExecutionStatus.SUCCEEDED,
        output_document_id="out-1",
    )
    repository = FakeExecutionRepository(execution)
    documents = FakeDocumentRepository(
        {
            "out-1": {
                "payload": {"ok": True, "tasks": [{"task_bot_id": 1}]},
                "_internal": "must-not-leak",
            }
        }
    )

    status, payload = await GetExecutionResult(repository, documents).execute(execution.id)

    assert status is ExecutionStatus.SUCCEEDED
    assert payload == {"ok": True, "tasks": [{"task_bot_id": 1}]}


@pytest.mark.asyncio
async def test_pending_result_is_unavailable() -> None:
    execution = Execution(
        flow_id=str(uuid4()),
        requested_capability="instagram.maduracion",
        status=ExecutionStatus.RUNNING,
    )

    status, payload = await GetExecutionResult(
        FakeExecutionRepository(execution),
        FakeDocumentRepository({}),
    ).execute(execution.id)

    assert status is ExecutionStatus.RUNNING
    assert payload is None


@pytest.mark.asyncio
async def test_unknown_execution_is_not_found() -> None:
    execution = Execution(
        flow_id=str(uuid4()),
        requested_capability="instagram.maduracion",
        status=ExecutionStatus.SUCCEEDED,
    )

    status, payload = await GetExecutionResult(
        FakeExecutionRepository(execution),
        FakeDocumentRepository({}),
    ).execute(uuid4())

    assert status is None
    assert payload is None
