from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api.v1.auth import BotExecutionPrincipal, require_bot_execution_access, require_dashboard_operator
from orchestrator.api.v1.dependencies import (
    cancel_execution_use_case,
    create_standalone_instagram_use_case,
    create_standalone_pagespeed_use_case,
    db_session,
    dispatch_execution_use_case,
    execution_event_repository,
    get_execution_input_use_case,
    get_execution_result_use_case,
    submit_execution_result_use_case,
)
from orchestrator.application.dtos import (
    DispatchExecutionRequest,
    ExecutionCompletionResponse,
    ExecutionEventResponse,
    ExecutionResponse,
    ExecutionResultRequest,
    StandaloneInstagramRequest,
    StandalonePageSpeedRequest,
)
from orchestrator.application.use_cases.cancel_execution import CancelExecution
from orchestrator.application.use_cases.create_standalone_instagram import CreateStandaloneInstagram
from orchestrator.application.use_cases.create_standalone_pagespeed import CreateStandalonePageSpeed
from orchestrator.application.use_cases.dispatch_execution import DispatchExecution
from orchestrator.application.use_cases.execution_documents import GetExecutionInput, SubmitExecutionResult
from orchestrator.application.use_cases.get_execution_result import GetExecutionResult
from orchestrator.domain.entities import ExecutionStatus
from orchestrator.infrastructure.postgres.models import ExecutionModel
from orchestrator.infrastructure.postgres.repositories import SqlAlchemyExecutionEventRepository

router = APIRouter()


@router.post("/standalone/pagespeed", response_model=ExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_standalone_pagespeed(
    payload: StandalonePageSpeedRequest,
    use_case: CreateStandalonePageSpeed = Depends(create_standalone_pagespeed_use_case),
) -> ExecutionResponse:
    return await use_case.execute(payload)


@router.post(
    "/standalone/instagram",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_dashboard_operator)],
)
async def create_standalone_instagram(
    payload: StandaloneInstagramRequest,
    use_case: CreateStandaloneInstagram = Depends(create_standalone_instagram_use_case),
) -> ExecutionResponse:
    return await use_case.execute(payload)


@router.post("", response_model=ExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def dispatch_execution(
    payload: DispatchExecutionRequest,
    use_case: DispatchExecution = Depends(dispatch_execution_use_case),
) -> ExecutionResponse:
    try:
        return await use_case.execute(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", dependencies=[Depends(require_dashboard_operator)])
async def list_executions(
    capability: str | None = None,
    bot_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = 50,
    cursor: str | None = None,
    session: AsyncSession = Depends(db_session),
) -> dict[str, Any]:
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")
    parsed_status = None
    if status_filter:
        try:
            parsed_status = ExecutionStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid execution status") from exc

    statement = select(ExecutionModel).order_by(
        ExecutionModel.created_at.desc(),
        ExecutionModel.id.desc(),
    ).limit(limit + 1)
    if capability:
        statement = statement.where(ExecutionModel.requested_capability == capability)
    if bot_type:
        if bot_type != "instagram":
            raise HTTPException(status_code=422, detail="Unsupported bot_type filter")
        statement = statement.where(
            ExecutionModel.requested_capability.in_(
                ["instagram.maduracion", "instagram.prospecting"]
            )
        )
    if cursor:
        try:
            cursor_dt_raw, cursor_id_raw = cursor.split("|", 1)
            from datetime import datetime
            cursor_dt = datetime.fromisoformat(cursor_dt_raw.replace("Z", "+00:00"))
            cursor_id = UUID(cursor_id_raw)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Invalid cursor") from exc
        statement = statement.where(
            or_(
                ExecutionModel.created_at < cursor_dt,
                (
                    (ExecutionModel.created_at == cursor_dt)
                    & (ExecutionModel.id < cursor_id)
                ),
            )
        )
    if parsed_status is not None:
        statement = statement.where(ExecutionModel.status == parsed_status)
    result = await session.execute(statement)
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [ExecutionResponse.model_validate(item) for item in rows]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return {"items": items, "total": len(items), "next_cursor": next_cursor}


@router.get("/{execution_id}", response_model=ExecutionResponse, dependencies=[Depends(require_dashboard_operator)])
async def get_execution(
    execution_id: UUID,
    use_case: DispatchExecution = Depends(dispatch_execution_use_case),
) -> ExecutionResponse:
    execution = await use_case.get_execution(execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


@router.get("/{execution_id}/input")
async def get_execution_input(
    execution_id: UUID,
    _principal: Annotated[BotExecutionPrincipal, Depends(require_bot_execution_access)],
    use_case: GetExecutionInput = Depends(get_execution_input_use_case),
) -> dict[str, Any]:
    document = await use_case.execute(execution_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution input not found")
    return document


@router.get("/{execution_id}/result", dependencies=[Depends(require_dashboard_operator)])
async def get_execution_result(
    execution_id: UUID,
    use_case: GetExecutionResult = Depends(get_execution_result_use_case),
) -> dict[str, Any]:
    execution_status, payload = await use_case.execute(execution_id)
    if execution_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    if payload is None:
        if execution_status in {ExecutionStatus.PENDING, ExecutionStatus.QUEUED, ExecutionStatus.RUNNING, ExecutionStatus.CANCELLING}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Execution result is not available yet")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution result not found")
    return payload


@router.post("/{execution_id}/result", response_model=ExecutionCompletionResponse)
async def submit_execution_result(
    execution_id: UUID,
    payload: ExecutionResultRequest,
    _principal: Annotated[BotExecutionPrincipal, Depends(require_bot_execution_access)],
    use_case: SubmitExecutionResult = Depends(submit_execution_result_use_case),
) -> ExecutionCompletionResponse:
    execution = await use_case.execute(execution_id, payload)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


@router.post(
    "/{execution_id}/cancel",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_dashboard_operator)],
)
async def cancel_execution(
    execution_id: UUID,
    use_case: CancelExecution = Depends(cancel_execution_use_case),
) -> ExecutionResponse:
    try:
        execution = await use_case.execute(execution_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


@router.get(
    "/{execution_id}/events",
    response_model=list[ExecutionEventResponse],
    dependencies=[Depends(require_dashboard_operator)],
)
async def list_execution_events(
    execution_id: UUID,
    after_sequence: int = 0,
    limit: int = 500,
    repository: SqlAlchemyExecutionEventRepository = Depends(execution_event_repository),
    use_case: DispatchExecution = Depends(dispatch_execution_use_case),
) -> list[ExecutionEventResponse]:
    if after_sequence < 0 or not 1 <= limit <= 1_000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="after_sequence must be >= 0 and limit must be between 1 and 1000",
        )
    if await use_case.get_execution(execution_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    events = await repository.list_by_execution(execution_id, after_sequence=after_sequence, limit=limit)
    return [ExecutionEventResponse.model_validate(event) for event in events]
