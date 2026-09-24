from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from uuid import UUID, uuid4

import httpx
import websockets
from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from dashboard.models import (
    ActiveWebSocketConnection,
    InstagramProspectingCampaignAccount,
    OrchestratorInstagramExecution,
    OrchestratorInstagramTask,
    SocialMediaAccount,
    TaskBot,
    TaskType,
)

logger = logging.getLogger(__name__)

CAPABILITIES = {"instagram.maduracion", "instagram.prospecting"}
TERMINAL_TASK_STATES = {"OK", "ER", "CA", "CANCELLED"}


def _scheduled_start_date(schedule: dict[str, Any] | None):
    start_date = (schedule or {}).get("start_date")
    if not start_date:
        return timezone.now()
    parsed = parse_datetime(str(start_date))
    if parsed is None or timezone.is_naive(parsed):
        raise ValueError("schedule.start_date must be a timezone-aware ISO datetime")
    return parsed


def _normalize_url(value: str, default: str) -> str:
    return (value or default).strip().rstrip("/")


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError, AttributeError):
        return None


class InstagramOrchestratorAdapter:
    """Django-side bridge between the RPA Orchestrator and legacy Instagram TaskBots."""

    def __init__(self) -> None:
        self.orchestrator_url = _normalize_url(
            os.getenv("ORCHESTRATOR_URL", "http://10.0.0.92:8005"),
            "http://10.0.0.92:8005",
        )
        default_ws = self.orchestrator_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/v1/bots/ws"
        self.ws_url = _normalize_url(os.getenv("ORCHESTRATOR_WS_URL", default_ws), default_ws)
        self.bot_key = os.getenv("ORCHESTRATOR_BOT_KEY", "instagram-backend-01").strip()
        self.token = os.getenv("ORCHESTRATOR_BOT_TOKEN", "").strip()
        self.bot_name = os.getenv("ORCHESTRATOR_BOT_NAME", "Instagram Backend").strip()
        self.version = os.getenv("ORCHESTRATOR_BOT_VERSION", "instagram-backend-adapter-v1").strip()
        self.max_concurrency = max(1, int(os.getenv("ORCHESTRATOR_MAX_CONCURRENCY", "1")))
        self.heartbeat_seconds = max(5, int(os.getenv("ORCHESTRATOR_HEARTBEAT_SECONDS", "15")))
        self.poll_seconds = max(2, int(os.getenv("ORCHESTRATOR_TASK_POLL_SECONDS", "5")))
        self.request_timeout = max(5.0, float(os.getenv("ORCHESTRATOR_HTTP_TIMEOUT_SECONDS", "20")))
        self.default_bot_executor = os.getenv("ORCHESTRATOR_DEFAULT_BOT_EXECUTOR", "").strip() or None
        self._stop = asyncio.Event()
        self._monitor_tasks: set[asyncio.Task[Any]] = set()

    async def run_forever(self) -> None:
        if not self.token:
            raise RuntimeError("ORCHESTRATOR_BOT_TOKEN is required")
        delay = 2
        while not self._stop.is_set():
            try:
                await self._run_connection()
                delay = 2
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Instagram orchestrator adapter connection failed")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def stop(self) -> None:
        self._stop.set()
        for task in list(self._monitor_tasks):
            task.cancel()
        await asyncio.gather(*self._monitor_tasks, return_exceptions=True)

    async def _run_connection(self) -> None:
        headers = {"Authorization": f"Bearer {self.token}"}
        async with websockets.connect(
            self.ws_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=15,
            close_timeout=5,
        ) as websocket:
            await websocket.send(_json(await self._register_payload()))
            registered = _loads(await websocket.recv())
            if registered.get("type") != "bot.registered" or registered.get("status") != "ok":
                raise RuntimeError(f"Orchestrator registration rejected: {registered}")
            logger.info("[ORCHESTRATOR] registered bot_key=%s", self.bot_key)

            for execution_id in await sync_to_async(self._active_execution_ids)():
                self._track(asyncio.create_task(self._monitor_execution(websocket, UUID(execution_id))))

            heartbeat = asyncio.create_task(self._heartbeat_loop(websocket))
            try:
                while not self._stop.is_set():
                    message = _loads(await websocket.recv())
                    kind = message.get("type")
                    if kind == "execution.run":
                        self._track(asyncio.create_task(self._handle_execution(websocket, message)))
                    elif kind == "execution.cancel":
                        self._track(asyncio.create_task(self._handle_cancel(websocket, message)))
                    elif kind not in {"bot.heartbeat.ack", "execution.ack", "execution.progress.ack"}:
                        logger.warning("[ORCHESTRATOR] unknown message type=%s", kind)
            finally:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)

    async def _register_payload(self) -> dict[str, Any]:
        return {
            "type": "bot.register",
            "bot_key": self.bot_key,
            "name": self.bot_name,
            "bot_type": "instagram",
            "capabilities": sorted(CAPABILITIES),
            "version": self.version,
            "max_concurrency": self.max_concurrency,
            "available_slots": await sync_to_async(self._available_slots)(),
            "active_executions": await sync_to_async(self._active_execution_ids)(),
            "metadata": {"adapter": "django", "protocol_version": "1"},
        }

    async def _heartbeat_loop(self, websocket: Any) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            slots = await sync_to_async(self._available_slots)()
            await websocket.send(_json({
                "type": "bot.heartbeat",
                "current_jobs": max(0, self.max_concurrency - slots),
                "available_slots": slots,
            }))

    def _track(self, task: asyncio.Task[Any]) -> None:
        self._monitor_tasks.add(task)
        task.add_done_callback(self._monitor_tasks.discard)

    async def _handle_execution(self, websocket: Any, message: dict[str, Any]) -> None:
        execution_id = _uuid(message.get("execution_id"))
        capability = str(message.get("capability") or "")
        if execution_id is None or capability not in CAPABILITIES:
            await websocket.send(_json({"type": "error", "code": "invalid_message", "message": "Invalid Instagram execution.run"}))
            return
        try:
            payload = await self._get_input(execution_id)
            created, duplicate = await sync_to_async(self._create_execution_tasks)(
                execution_id, capability, message.get("stage"), payload
            )
            await websocket.send(_json({"type": "execution.started", "execution_id": str(execution_id)}))
            if not duplicate:
                await self._send_progress(websocket, execution_id, {
                    "event_type": "run.start",
                    "stage": message.get("stage"),
                    "summary": f"Created {len(created)} Instagram TaskBot task(s)",
                    "payload": {"task_bot_ids": created},
                })
            self._track(asyncio.create_task(self._monitor_execution(websocket, execution_id)))
        except Exception as exc:
            logger.exception("[ORCHESTRATOR] failed to start execution %s", execution_id)
            await websocket.send(_json({
                "type": "execution.failed",
                "execution_id": str(execution_id),
                "error": str(exc),
                "payload": {"schema_version": "instagram.adapter.error.v1", "ok": False},
            }))

    async def _handle_cancel(self, websocket: Any, message: dict[str, Any]) -> None:
        execution_id = _uuid(message.get("execution_id"))
        if execution_id is None:
            return
        changed = await sync_to_async(self._request_cancel)(execution_id)
        if changed:
            await self._send_progress(websocket, execution_id, {
                "event_type": "log",
                "stage": "instagram",
                "summary": "Cancellation requested",
                "payload": {},
            })

    async def _get_input(self, execution_id: UUID) -> dict[str, Any]:
        url = f"{self.orchestrator_url}/api/v1/executions/{execution_id}/input"
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {self.token}"})
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Instagram execution input must be an object")
        return payload

    def _create_execution_tasks(
        self, execution_id: UUID, capability: str, stage: str | None, payload: dict[str, Any]
    ) -> tuple[list[int], bool]:
        with transaction.atomic():
            execution, created = OrchestratorInstagramExecution.objects.get_or_create(
                execution_id=execution_id,
                defaults={
                    "capability": capability,
                    "stage": stage,
                    "status": "running",
                    "request_payload": payload,
                    "started_at": timezone.now(),
                },
            )
            if not created:
                return list(execution.tasks.values_list("task_bot_id", flat=True)), True

            targets = payload.get("targets") or {}
            accounts = self._resolve_accounts(targets)
            task_types = self._resolve_task_types(payload.get("task_types") or [], capability)
            options = payload.get("options") or {}
            max_accounts = options.get("max_accounts")
            if max_accounts is not None:
                accounts = accounts[: max(0, int(max_accounts))]
            if not accounts:
                raise ValueError("No authorized Instagram accounts matched the execution targets")

            custom_task = payload.get("custom_task") or {}
            start_date = _scheduled_start_date(payload.get("schedule"))
            executor = options.get("bot_executor") or self.default_bot_executor or "NONE"
            task_ids: list[int] = []
            for account in accounts:
                task = TaskBot.objects.create(
                    task_type=task_types,
                    bot_executor=executor,
                    status_process="SP",
                    comment={"status": "Pending...", "orchestrator_execution_id": str(execution_id)},
                    social_media_account=account,
                    custom_task=custom_task,
                    start_date=start_date,
                )
                OrchestratorInstagramTask.objects.create(
                    execution=execution,
                    task_bot=task,
                    account_id=account.id,
                )
                task_ids.append(task.id)
            return task_ids, False

    def _resolve_task_types(self, task_type_ids: list[Any], capability: str) -> list[int]:
        ids = [int(value) for value in task_type_ids]
        rows = list(TaskType.objects.select_related("platform").filter(id__in=ids))
        found = {row.id: row for row in rows}
        missing = [value for value in ids if value not in found]
        if missing:
            raise ValueError(f"Unknown Instagram task_type ids: {missing}")
        invalid = [row.id for row in rows if (row.platform.platform_name or "").strip().lower() != "instagram"]
        if invalid:
            raise ValueError(f"Task types are not Instagram tasks: {invalid}")

        operation = capability.rsplit(".", 1)[-1]
        uncategorized = [row.id for row in rows if not row.operation]
        if uncategorized:
            raise ValueError(
                f"Instagram task types are missing an operation category: {uncategorized}"
            )
        mismatched = [row.id for row in rows if row.operation != operation]
        if mismatched:
            raise ValueError(
                f"Task types do not belong to Instagram operation {operation}: {mismatched}"
            )
        return ids

    def _resolve_accounts(self, targets: dict[str, Any]) -> list[SocialMediaAccount]:
        mode = targets.get("mode")
        # Instagram membership is defined by the active campaign-account assignment,
        # not by the legacy SocialMediaAccount.account_type field.
        instagram_ids = InstagramProspectingCampaignAccount.objects.filter(
            platform__iexact="instagram",
            role="prospecting",
            is_active=True,
        ).values_list("social_media_account_id", flat=True)
        base = SocialMediaAccount.objects.select_related("owner").filter(id__in=instagram_ids).distinct()
        if mode == "accounts":
            ids = [int(value) for value in targets.get("account_ids") or []]
            return list(base.filter(id__in=ids).order_by("id"))
        if mode == "owner":
            owner_id = targets.get("owner_id")
            return list(base.filter(owner_id=owner_id).order_by("id"))
        if mode == "all":
            return list(base.order_by("id"))
        raise ValueError("targets.mode must be accounts, owner, or all")

    def _request_cancel(self, execution_id: UUID) -> bool:
        execution = OrchestratorInstagramExecution.objects.filter(execution_id=execution_id).first()
        if execution is None or execution.status in {"succeeded", "failed", "cancelled"}:
            return False
        execution.cancel_requested = True
        execution.status = "cancelling"
        execution.save(update_fields=["cancel_requested", "status", "updated_at"])
        for link in execution.tasks.select_related("task_bot").all():
            task = link.task_bot
            if task.status_process in {"SP", "EQ"}:
                task.status_process = "CA"
                task.end_date = timezone.now()
                task.comment = {"status": "Cancelled by orchestrator", "execution_id": str(execution_id)}
                task.save(update_fields=["status_process", "end_date", "comment"])
        return True

    def _active_execution_ids(self) -> list[str]:
        return [str(value) for value in OrchestratorInstagramExecution.objects.filter(status__in=["running", "cancelling"]).values_list("execution_id", flat=True)]

    def _capacity(self) -> int:
        return self.max_concurrency

    def _available_slots(self) -> int:
        active = OrchestratorInstagramExecution.objects.filter(
            status__in=["running", "cancelling"],
        ).count()
        return max(0, self._capacity() - active)

    async def _monitor_execution(self, websocket: Any, execution_id: UUID) -> None:
        last_signature: tuple[Any, ...] | None = None
        while True:
            snapshot = await sync_to_async(self._execution_snapshot)(execution_id)
            if snapshot is None:
                return
            if snapshot["signature"] != last_signature:
                last_signature = snapshot["signature"]
                await self._send_progress(websocket, execution_id, {
                    "event_type": "stats",
                    "stage": "instagram",
                    "summary": "Instagram execution progress",
                    "payload": snapshot["payload"].get("totals", {}),
                })
            if snapshot["terminal"]:
                if snapshot["cancelled"]:
                    await websocket.send(_json({"type": "execution.cancelled", "execution_id": str(execution_id)}))
                elif snapshot["ok"]:
                    await websocket.send(_json({"type": "execution.succeeded", "execution_id": str(execution_id), "payload": snapshot["payload"]}))
                else:
                    await websocket.send(_json({"type": "execution.failed", "execution_id": str(execution_id), "error": snapshot["error"], "payload": snapshot["payload"]}))
                await sync_to_async(self._mark_finished)(execution_id, snapshot)
                return
            await asyncio.sleep(self.poll_seconds)

    def _execution_snapshot(self, execution_id: UUID) -> dict[str, Any] | None:
        execution = OrchestratorInstagramExecution.objects.filter(execution_id=execution_id).first()
        if execution is None:
            return None
        links = list(execution.tasks.select_related("task_bot", "task_bot__social_media_account").all())
        statuses = [link.task_bot.status_process or "" for link in links]
        total = len(links)
        done = sum(status in TERMINAL_TASK_STATES for status in statuses)
        errors = sum(status == "ER" for status in statuses)
        cancelled = execution.cancel_requested and done == total and total > 0
        terminal = total > 0 and done == total
        ok = terminal and errors == 0 and not cancelled
        payload = self._build_result(execution, links, statuses)
        return {
            "terminal": terminal,
            "ok": ok,
            "cancelled": cancelled,
            "error": None if ok or cancelled else f"{errors} Instagram TaskBot task(s) failed",
            "payload": payload,
            "signature": (tuple(statuses), execution.cancel_requested, total),
        }

    def _build_result(self, execution: OrchestratorInstagramExecution, links: list[OrchestratorInstagramTask], statuses: list[str]) -> dict[str, Any]:
        tasks = []
        for link, status in zip(links, statuses):
            task = link.task_bot
            tasks.append({
                "task_bot_id": task.id,
                "account_id": link.account_id,
                "status": status,
                "bot_executor": task.bot_executor,
                "end_date": task.end_date.isoformat() if task.end_date else None,
                "comment": task.comment or {},
            })
        return {
            "schema_version": f"{execution.capability}.result.v1",
            "ok": all(item["status"] == "OK" for item in tasks),
            "stage": execution.stage,
            "totals": {
                "created": len(tasks),
                "ok": sum(item["status"] == "OK" for item in tasks),
                "error": sum(item["status"] == "ER" for item in tasks),
                "cancelled": sum(item["status"] in {"CA", "CANCELLED"} for item in tasks),
            },
            "tasks": tasks,
        }

    async def _send_progress(self, websocket: Any, execution_id: UUID, event: dict[str, Any]) -> None:
        sequence = await sync_to_async(self._store_sequence)(execution_id)
        await websocket.send(_json({
            "type": "execution.progress",
            "event_id": str(uuid4()),
            "execution_id": str(execution_id),
            "sequence": sequence,
            "event_type": event["event_type"],
            "stage": event.get("stage"),
            "summary": event.get("summary"),
            "payload": event.get("payload") or {},
        }))

    def _store_sequence(self, execution_id: UUID) -> int:
        execution = OrchestratorInstagramExecution.objects.get(execution_id=execution_id)
        payload = dict(execution.result_payload or {})
        sequence = int(payload.get("last_sequence", 0)) + 1
        payload["last_sequence"] = sequence
        execution.result_payload = payload
        execution.save(update_fields=["result_payload", "updated_at"])
        return sequence

    def _mark_finished(self, execution_id: UUID, snapshot: dict[str, Any]) -> None:
        execution = OrchestratorInstagramExecution.objects.get(execution_id=execution_id)
        execution.status = "cancelled" if snapshot["cancelled"] else ("succeeded" if snapshot["ok"] else "failed")
        execution.finished_at = timezone.now()
        execution.result_payload = snapshot["payload"]
        execution.save(update_fields=["status", "finished_at", "result_payload", "updated_at"])


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Any) -> dict[str, Any]:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("WebSocket message must be an object")
    return payload


