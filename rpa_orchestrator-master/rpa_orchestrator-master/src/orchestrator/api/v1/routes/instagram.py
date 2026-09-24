from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from orchestrator.api.v1.auth import require_dashboard_operator
from orchestrator.core.config import get_settings

router = APIRouter()

_ADMIN_RESOURCES = {
    "personalities": "bot_personalities",
    "owners": "account_owners",
    "proxies": "proxy",
    "accounts": "social_media_accounts",
    "campaigns": "prospecting/campaigns",
    "assignments": "prospecting/campaign-accounts",
}


def _backend_url(path: str) -> str:
    settings = get_settings()
    return settings.instagram_backend_url.rstrip("/") + "/api/" + path.lstrip("/")


def _backend_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Accept": "application/json"}
    if settings.instagram_backend_token:
        headers["X-Orchestrator-Token"] = settings.instagram_backend_token
    return headers


async def _proxy(
    method: str,
    path: str,
    *,
    params: Any = None,
    payload: Any = None,
) -> JSONResponse:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.bot_request_timeout_seconds) as client:
            response = await client.request(
                method,
                _backend_url(path),
                headers=_backend_headers(),
                params=params,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Instagram backend is unavailable",
        ) from exc

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text or f"HTTP {response.status_code}"}

    return JSONResponse(content=data, status_code=response.status_code)


@router.get("/catalog", dependencies=[Depends(require_dashboard_operator)])
async def instagram_catalog() -> dict:
    settings = get_settings()
    if not settings.instagram_backend_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Instagram backend catalog token is not configured",
        )
    response = await _proxy("GET", "orchestrator/instagram/catalog/")
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Instagram backend catalog returned HTTP {response.status_code}",
        )
    import json

    payload = json.loads(response.body)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Invalid Instagram catalog payload")
    return payload


@router.get("/admin/{resource}", dependencies=[Depends(require_dashboard_operator)])
async def list_instagram_resource(resource: str, request: Request) -> JSONResponse:
    backend_path = _resource_path(resource)
    return await _proxy("GET", backend_path + "/", params=request.query_params)


@router.post("/admin/{resource}", dependencies=[Depends(require_dashboard_operator)])
async def create_instagram_resource(
    resource: str,
    payload: dict[str, Any] = Body(...),
) -> JSONResponse:
    backend_path = _resource_path(resource)
    return await _proxy("POST", backend_path + "/", payload=payload)


@router.get("/admin/{resource}/{item_id}", dependencies=[Depends(require_dashboard_operator)])
async def get_instagram_resource(resource: str, item_id: int) -> JSONResponse:
    backend_path = _resource_path(resource)
    return await _proxy("GET", f"{backend_path}/{item_id}/")


@router.patch("/admin/{resource}/{item_id}", dependencies=[Depends(require_dashboard_operator)])
async def patch_instagram_resource(
    resource: str,
    item_id: int,
    payload: dict[str, Any] = Body(...),
) -> JSONResponse:
    backend_path = _resource_path(resource)
    return await _proxy("PATCH", f"{backend_path}/{item_id}/", payload=payload)


@router.delete("/admin/{resource}/{item_id}", dependencies=[Depends(require_dashboard_operator)])
async def delete_instagram_resource(resource: str, item_id: int) -> JSONResponse:
    backend_path = _resource_path(resource)
    return await _proxy("DELETE", f"{backend_path}/{item_id}/")


@router.patch("/admin/accounts/{item_id}/cookie", dependencies=[Depends(require_dashboard_operator)])
async def update_instagram_cookie(
    item_id: int,
    payload: list[dict[str, Any]] = Body(...),
) -> JSONResponse:
    return await _proxy(
        "PATCH",
        f"social_media_accounts/{item_id}/update_cookie/",
        payload=payload,
    )


@router.get("/admin/accounts/{item_id}/verify", dependencies=[Depends(require_dashboard_operator)])
async def verify_instagram_account(item_id: int) -> JSONResponse:
    return await _proxy(
        "GET",
        "prospecting/campaigns/active/",
        params={"social_media_account_id": item_id, "platform": "instagram"},
    )


def _resource_path(resource: str) -> str:
    path = _ADMIN_RESOURCES.get(resource)
    if path is None:
        raise HTTPException(status_code=404, detail="Unknown Instagram admin resource")
    return path
