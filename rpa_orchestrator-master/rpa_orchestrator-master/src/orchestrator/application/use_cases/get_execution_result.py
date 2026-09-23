from __future__ import annotations

from typing import Any
from uuid import UUID

from orchestrator.domain.entities import ExecutionStatus
from orchestrator.domain.ports import ExecutionRepository, FlowDocumentRepository


class GetExecutionResult:
    """Read-only access to a stored execution output document.

    Instagram standalone executions intentionally expose only the document
    payload.  The Mongo document id, storage metadata and internal envelope
    remain an implementation detail of the orchestrator.
    """

    def __init__(
        self,
        execution_repository: ExecutionRepository,
        flow_document_repository: FlowDocumentRepository,
    ) -> None:
        self._execution_repository = execution_repository
        self._flow_document_repository = flow_document_repository

    async def execute(
        self,
        execution_id: UUID,
    ) -> tuple[ExecutionStatus | None, dict[str, Any] | None]:
        execution = await self._execution_repository.get(execution_id)
        if execution is None:
            return None, None

        if execution.output_document_id is None:
            return execution.status, None

        document = await self._flow_document_repository.get_document(
            execution.output_document_id
        )
        if document is None:
            return execution.status, None

        payload = document.get("payload")
        if not isinstance(payload, dict):
            return execution.status, None

        return execution.status, payload
