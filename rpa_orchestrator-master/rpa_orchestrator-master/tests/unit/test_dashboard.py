from __future__ import annotations

import base64
from pathlib import Path

from starlette.routing import Mount

from orchestrator.main import (
    _find_frontend_directory,
    _is_bot_write_path,
    _valid_basic_auth,
    create_app,
)


def _dashboard_source() -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "app.core.js").read_text(encoding="utf-8")


def test_dashboard_is_mounted() -> None:
    app = create_app()

    assert any(
        isinstance(route, Mount) and route.path == "/dashboard"
        for route in app.routes
    )


def test_frontend_directory_is_resolved_from_project_root() -> None:
    directory = _find_frontend_directory()

    assert directory is not None
    assert (directory / "index.html").is_file()


def test_dashboard_uses_campaign_filter_and_has_no_html_preview() -> None:
    root = Path(__file__).resolve().parents[2]
    app_source = _dashboard_source()
    html_source = (root / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "campaign_id" in app_source
    assert "global-campaign" in html_source
    assert "html_preview" not in app_source
    assert "html-preview" not in html_source


def test_dashboard_keeps_original_form_and_renders_dynamic_mongo_json() -> None:
    root = Path(__file__).resolve().parents[2]
    app_source = _dashboard_source()
    html_source = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    css_source = (root / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'class="form-panel"' in html_source
    assert 'class="toggle-option' in html_source
    assert 'id="artifact-rendered"' in html_source
    assert "DOCUMENTO MONGODB" in html_source
    assert "renderDynamicJson" in app_source
    assert "renderPageSpeedResult" in app_source
    assert "getPageSpeedData" in app_source
    assert "profile.scores?.performance" in app_source
    assert "profile.performance," in app_source
    assert "pagespeed-report" in css_source
    assert "pagespeed-highlights" in css_source


def test_dashboard_shows_registered_page_position_from_brightlocal() -> None:
    app_source = _dashboard_source()

    assert 'class="button position check-position"' in app_source
    assert "/rank-position" in app_source
    assert "Posición:" in app_source
    assert "Fuera del top" in app_source
    assert "consume un crédito del proveedor de búsqueda" in app_source


def test_dashboard_has_independent_post_monitor_view() -> None:
    root = Path(__file__).resolve().parents[2]
    app_source = _dashboard_source()
    html_source = (root / "frontend" / "index.html").read_text(encoding="utf-8")

    assert 'data-view="post-monitor"' in html_source
    assert 'id="view-post-monitor"' in html_source
    assert 'id="post-alerts-body"' in html_source
    assert 'id="post-runs-body"' in html_source
    assert 'api("/post-monitor/overview")' in app_source
    assert "post_monitor" not in html_source


def test_dashboard_disables_page_execution_when_queue_is_active() -> None:
    app_source = _dashboard_source()

    assert "hasActiveExecution = Number(page.active_queue_count || 0) > 0" in app_source
    assert 'hasActiveExecution ? "Ejecución activa" : "Ejecutar"' in app_source


def test_dashboard_basic_auth_uses_exact_credentials() -> None:
    token = base64.b64encode(b"admin:secret").decode("ascii")

    assert _valid_basic_auth(f"Basic {token}", "admin", "secret")
    assert not _valid_basic_auth(f"Basic {token}", "admin", "different")


def test_page_flow_log_and_artifact_writes_are_identified() -> None:
    assert _is_bot_write_path(
        "PUT",
        "/api/v1/page-executions/302/artifacts/result.json",
    )
    assert _is_bot_write_path("PUT", "/api/v1/page-executions/302/log")
    assert not _is_bot_write_path("GET", "/api/v1/page-executions/302/log")


def test_instagram_dashboard_contract_is_present() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "frontend" / "instagram.js").read_text(encoding="utf-8")

    assert 'api("/instagram/catalog")' in source
    assert 'api("/executions/standalone/instagram"' in source
    assert '/events?after_sequence=' in source
    assert '/result' in source
    assert '/cancel' in source
    assert 'credentials: "same-origin"' in source
    assert 'Opciones avanzadas' in source
    assert 'task.operation===operation' in source
    assert '/input' not in source
    assert 'BOT_TOKENS' not in source
    assert 'Administración de cuentas Instagram' in source
    assert '/instagram/admin/personalities' in source
    assert '/instagram/admin/owners' in source
    assert '/instagram/admin/proxies' in source
    assert '/instagram/admin/accounts' in source
    assert '/instagram/admin/campaigns' in source
    assert '/instagram/admin/assignments' in source
    assert '/verify' in source
    assert 'WebSocket' not in source
    assert 'setTimeout(' in source
    assert 'setInterval(' not in source
    assert 'AbortController' in source
    assert 'toISOString()' in source
    assert 'aria-live="polite"' in source
    assert 'La cancelación puede tardar mientras el bot termina una operación atómica.' in source
    assert 'Bot asignado' in source
    assert 'Tiempo transcurrido' in source
    assert 'error_message' in source
    assert 'next_cursor' in source
    assert 'Cargar más' in source
    assert 'window.confirm(' in source
    assert 'innerHTML = payload' not in source
    assert 'textContent =' in source
