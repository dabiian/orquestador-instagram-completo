import pytest

from app.api.ai_api import AIAPI


class _Driver:
    def __init__(self, current_url):
        self.current_url = current_url


class _Browser:
    def __init__(self, current_url):
        self.driver = _Driver(current_url)


def _profile_service():
    pytest.importorskip("selenium")
    from app.services.instagram_profile_service import InstagramProfileService
    return InstagramProfileService


def test_profile_integrity_accepts_identical_canonical_profile_urls():
    InstagramProfileService = _profile_service()
    browser = _Browser("https://www.instagram.com/ljs.construction_management/")
    service = InstagramProfileService(browser)
    assert service._is_expected_profile_page(
        "https://www.instagram.com/ljs.construction_management/",
        "ljs.construction_management",
    ) is True


def test_profile_integrity_rejects_post_as_profile():
    InstagramProfileService = _profile_service()
    browser = _Browser("https://www.instagram.com/p/ABC123/")
    service = InstagramProfileService(browser)
    assert service._is_expected_profile_page(
        "https://www.instagram.com/ljs.construction_management/",
        "ljs.construction_management",
    ) is False


def test_ai_post_500_falls_back_to_legacy_get(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status, payload=None, text=""):
            self.status_code = status
            self._payload = payload
            self.text = text
            self.reason = "Internal Server Error" if status == 500 else "OK"

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests
                raise requests.exceptions.HTTPError(
                    f"{self.status_code} error", response=self
                )

        def json(self):
            return self._payload

    def fake_post(*args, **kwargs):
        calls.append(("post", kwargs.get("json")))
        return Response(500, text="legacy endpoint; use GET")

    def fake_get(*args, **kwargs):
        calls.append(("get", kwargs.get("params")))
        return Response(200, {"comment": "ok"})

    monkeypatch.setattr("app.api.ai_api.requests.post", fake_post)
    monkeypatch.setattr("app.api.ai_api.requests.get", fake_get)

    api = AIAPI()
    ok, payload = api.get_bot_ia_long_prompt(10, "test prompt")

    assert ok is True
    assert payload == {"comment": "ok"}
    assert calls[0][0] == "post"
    assert calls[1][0] == "get"
    assert calls[1][1] == {"bot_personality_id": 10, "user_prompt": "test prompt"}
