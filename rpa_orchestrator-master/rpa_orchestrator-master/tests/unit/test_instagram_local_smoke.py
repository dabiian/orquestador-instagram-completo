from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from orchestrator.api.v1.routes import instagram as instagram_routes
from orchestrator.core.config import get_settings
from orchestrator.main import create_app


def test_instagram_catalog_is_registered_even_without_backend_token(monkeypatch) -> None:
    monkeypatch.setattr(
        instagram_routes,
        "get_settings",
        lambda: SimpleNamespace(instagram_backend_token=""),
    )
    app = create_app()
    assert "/api/v1/instagram/catalog" in app.openapi()["paths"]
    settings = get_settings()
    auth = (settings.dashboard_user, settings.dashboard_pass) if settings.dashboard_user else None
    response = TestClient(app).get("/api/v1/instagram/catalog", auth=auth)
    assert response.status_code == 503
    assert response.json()["detail"] == "Instagram backend catalog token is not configured"


def test_instagram_dashboard_assets_are_served_by_same_application() -> None:
    app = create_app()
    settings = get_settings()
    auth = (settings.dashboard_user, settings.dashboard_pass) if settings.dashboard_user else None
    client = TestClient(app)
    bootstrap = client.get("/dashboard/app.js", auth=auth)
    assert bootstrap.status_code == 200
    assert 'import("/dashboard/app.core.js")' in bootstrap.text
    assert 'import("/dashboard/instagram.js")' in bootstrap.text
    assert client.get("/dashboard/instagram.js", auth=auth).status_code == 200
