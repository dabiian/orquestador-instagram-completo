from app.services.instagram_post_interaction_service import InstagramPostInteractionService


class _FakeBrowser:
    def __init__(self):
        self.scripts = []
        self.sleeps = []
        self.calls = 0

    def execute_script_safe(self, script, *args):
        self.scripts.append(script)
        self.calls += 1
        # First pass: comment is not found. Second pass: after the simulated
        # scroll pass, the comment is found.
        return self.calls >= 2

    def time_sleep(self, value):
        self.sleeps.append(value)


class _FakeLogger:
    def __init__(self):
        self.info_messages = []
        self.warning_messages = []

    def info(self, *args, **kwargs):
        self.info_messages.append(args)

    def warning(self, *args, **kwargs):
        self.warning_messages.append(args)


def _service(browser):
    service = object.__new__(InstagramPostInteractionService)
    service.browser = browser
    service.log = _FakeLogger()
    return service


def test_confirm_comment_visible_searches_after_scrolling_comment_containers():
    browser = _FakeBrowser()
    service = _service(browser)

    assert service._confirm_comment_visible("Mi comentario", attempts=3) is True
    assert browser.calls == 2
    script = browser.scripts[0]
    assert "scrollTop" in script
    assert "scrollHeight" in script
    assert "window.scrollBy" in script
    assert "role=\"dialog\"" in script


def test_confirm_comment_visible_does_not_retry_publish_or_click_anything():
    browser = _FakeBrowser()
    service = _service(browser)

    result = service._confirm_comment_visible("Mi comentario", attempts=1)

    assert result is False
    # The verifier only executes JS/scroll checks; it has no publish click path.
    assert not any("click" in script.lower() and "publish" in script.lower() for script in browser.scripts)


def test_confirm_comment_visible_uses_multiple_short_verification_passes():
    browser = _FakeBrowser()
    service = _service(browser)

    assert service._confirm_comment_visible("Mi comentario", attempts=3) is True
    assert browser.sleeps == [1.2]
