from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from orchestrator.api.v1.auth import require_dashboard_operator
from orchestrator.core.config import get_settings

router = APIRouter()


@router.get("/catalog", dependencies=[Depends(require_dashboard_operator)])
async def instagram_catalog() -> dict:
    settings = get_settings()
    if not settings.instagram_backend_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Instagram backend catalog token is not configured",
        )
    url = settings.instagram_backend_url.rstrip("/") + "/api/orchestrator/instagram/catalog/"
    try:
        async with httpx.AsyncClient(timeout=settings.bot_request_timeout_seconds) as client:
            response = await client.get(url, headers={"X-Orchestrator-Token": settings.instagram_backend_token})
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Instagram backend catalog returned HTTP {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Instagram backend catalog is unavailable") from exc
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Invalid Instagram catalog payload")
    return payload
