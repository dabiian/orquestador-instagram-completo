from __future__ import annotations

from orchestrator.core.config import Settings


def test_instagram_integration_settings_are_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "BOT_TOKENS",
        '{"instagram-worker-secret":"instagram-backend-01"}',
    )
    monkeypatch.setenv("INSTAGRAM_BACKEND_URL", "http://10.0.0.90:8004")
    monkeypatch.setenv("INSTAGRAM_BACKEND_TOKEN", "catalog-secret")

    settings = Settings(_env_file=None)

    assert settings.bot_tokens == {"instagram-worker-secret": "instagram-backend-01"}
    assert settings.bot_tokens.get("instagram-worker-secret") == "instagram-backend-01"
    assert settings.instagram_backend_url == "http://10.0.0.90:8004"
    assert settings.instagram_backend_token == "catalog-secret"
