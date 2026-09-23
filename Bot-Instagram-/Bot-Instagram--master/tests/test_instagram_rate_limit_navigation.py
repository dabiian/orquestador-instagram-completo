
import time

from app.services.instagram_profile_service import (
    InstagramProfileService,
    InstagramRateLimitError,
)


class DummyDriver:
    title = ""
    current_url = "https://www.instagram.com/"
    def __init__(self, body=""):
        self.body = body
        self.get_calls = []
    def get(self, url):
        self.get_calls.append(url)
        self.current_url = url
    def find_element(self, by, value):
        class Body:
            def __init__(self, text):
                self.text = text
        return Body(self.body)


class DummyBrowser:
    def __init__(self, body=""):
        self.driver = DummyDriver(body)
    def go_to_url(self, url):
        self.driver.get(url)
    def time_sleep(self, seconds):
        # Keep tests fast; navigation timestamp is still managed by the service.
        time.sleep(0)


def test_rate_limit_page_raises_and_sets_cooldown(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_429_COOLDOWN_SECONDS", "30")
    browser = DummyBrowser("Please wait a few minutes before you try again.")
    service = InstagramProfileService(browser)

    try:
        service.open_url("https://www.instagram.com/example/")
        assert False, "Expected InstagramRateLimitError"
    except InstagramRateLimitError:
        pass

    assert service.is_rate_limited()
    assert browser.driver.get_calls == ["https://www.instagram.com/example/"]


def test_rate_limit_cooldown_blocks_second_navigation(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_429_COOLDOWN_SECONDS", "30")
    browser = DummyBrowser("Too Many Requests")
    service = InstagramProfileService(browser)

    try:
        service.open_url("https://www.instagram.com/example/")
    except InstagramRateLimitError:
        pass

    calls = len(browser.driver.get_calls)

    try:
        service.open_url("https://www.instagram.com/another/")
        assert False, "Expected cooldown to block navigation"
    except InstagramRateLimitError:
        pass

    assert len(browser.driver.get_calls) == calls


def test_normal_page_does_not_trigger_rate_limit(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_429_COOLDOWN_SECONDS", "30")
    browser = DummyBrowser("Welcome to Instagram")
    service = InstagramProfileService(browser)

    service.open_url("https://www.instagram.com/example/")

    assert not service.is_rate_limited()
    assert browser.driver.get_calls == ["https://www.instagram.com/example/"]
