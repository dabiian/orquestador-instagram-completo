from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from orchestrator.api.v1.routes import instagram
from orchestrator.api.v1.routes.instagram import _resource_path


def test_instagram_admin_resource_allowlist_matches_backend_contract() -> None:
    assert _resource_path("personalities") == "bot_personalities"
    assert _resource_path("owners") == "account_owners"
    assert _resource_path("proxies") == "proxy"
    assert _resource_path("accounts") == "social_media_accounts"
    assert _resource_path("campaigns") == "prospecting/campaigns"
    assert _resource_path("assignments") == "prospecting/campaign-accounts"


def test_instagram_admin_resource_allowlist_rejects_arbitrary_backend_paths() -> None:
    with pytest.raises(HTTPException) as exc:
        _resource_path("../task_bots")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_expanded_account_uses_documented_social_medias_endpoint(monkeypatch) -> None:
    calls = []

    async def fake_proxy(method, path, *, params=None, payload=None):
        calls.append((method, path, params, payload))
        return JSONResponse({"id": 25, "owner": {"id": 3}, "proxy": {"id": 15}, "bot_personality": {"id": 2}})

    monkeypatch.setattr(instagram, "_proxy", fake_proxy)
    response = await instagram.get_instagram_account_expanded(25)

    assert calls == [("GET", "social_medias/25/", None, None)]
    assert json.loads(response.body)["owner"]["id"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resource", "backend_path"),
    [
        ("personalities", "bot_personalities"),
        ("owners", "account_owners"),
        ("proxies", "proxy"),
        ("accounts", "social_media_accounts"),
        ("campaigns", "prospecting/campaigns"),
        ("assignments", "prospecting/campaign-accounts"),
    ],
)
async def test_admin_crud_proxies_all_documented_resources(monkeypatch, resource, backend_path) -> None:
    calls = []

    async def fake_proxy(method, path, *, params=None, payload=None):
        calls.append((method, path, params, payload))
        return JSONResponse({"ok": True})

    monkeypatch.setattr(instagram, "_proxy", fake_proxy)

    await instagram.create_instagram_resource(resource, {"name": "x"})
    await instagram.get_instagram_resource(resource, 7)
    await instagram.patch_instagram_resource(resource, 7, {"name": "y"})
    await instagram.delete_instagram_resource(resource, 7)

    assert calls == [
        ("POST", f"{backend_path}/", None, {"name": "x"}),
        ("GET", f"{backend_path}/7/", None, None),
        ("PATCH", f"{backend_path}/7/", None, {"name": "y"}),
        ("DELETE", f"{backend_path}/7/", None, None),
    ]


@pytest.mark.asyncio
async def test_cookie_update_and_active_campaign_verification(monkeypatch) -> None:
    calls = []

    async def fake_proxy(method, path, *, params=None, payload=None):
        calls.append((method, path, params, payload))
        return JSONResponse({"ok": True, "campaign": {"id": 9}})

    monkeypatch.setattr(instagram, "_proxy", fake_proxy)
    cookies = [{"name": "sessionid", "value": "abc"}]

    await instagram.update_instagram_cookie(25, cookies)
    response = await instagram.verify_instagram_account(25)

    assert calls == [
        ("PATCH", "social_media_accounts/25/update_cookie/", None, cookies),
        ("GET", "prospecting/campaigns/active/", {"social_media_account_id": 25, "platform": "instagram"}, None),
    ]
    assert json.loads(response.body)["campaign"]["id"] == 9
