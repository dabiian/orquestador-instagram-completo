from fastapi import HTTPException

from orchestrator.api.v1.routes.instagram import _resource_path


def test_instagram_admin_resource_allowlist_matches_backend_contract() -> None:
    assert _resource_path("personalities") == "bot_personalities"
    assert _resource_path("owners") == "account_owners"
    assert _resource_path("proxies") == "proxy"
    assert _resource_path("accounts") == "social_media_accounts"
    assert _resource_path("campaigns") == "prospecting/campaigns"
    assert _resource_path("assignments") == "prospecting/campaign-accounts"


def test_instagram_admin_resource_allowlist_rejects_arbitrary_backend_paths() -> None:
    try:
        _resource_path("../task_bots")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Unknown resources must be rejected")
