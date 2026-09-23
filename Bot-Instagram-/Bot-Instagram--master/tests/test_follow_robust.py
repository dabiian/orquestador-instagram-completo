import importlib.util
import sys
import types
from pathlib import Path

# Minimal Selenium stubs for importing InstagramProfileService.
selenium = types.ModuleType("selenium")
webdriver = types.ModuleType("selenium.webdriver")
common = types.ModuleType("selenium.webdriver.common")
by_mod = types.ModuleType("selenium.webdriver.common.by")
keys_mod = types.ModuleType("selenium.webdriver.common.keys")

class By:
    XPATH = "xpath"

class Keys:
    ESCAPE = "ESCAPE"

by_mod.By = By
keys_mod.Keys = Keys
sys.modules.setdefault("selenium", selenium)
sys.modules.setdefault("selenium.webdriver", webdriver)
sys.modules.setdefault("selenium.webdriver.common", common)
sys.modules.setdefault("selenium.webdriver.common.by", by_mod)
sys.modules.setdefault("selenium.webdriver.common.keys", keys_mod)

service_path = Path(__file__).parents[1] / "app" / "services" / "instagram_profile_service.py"
spec = importlib.util.spec_from_file_location("instagram_profile_service_test", service_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
InstagramProfileService = mod.InstagramProfileService

for _name in [
    "selenium.webdriver.common.keys",
    "selenium.webdriver.common.by",
    "selenium.webdriver.common",
    "selenium.webdriver",
    "selenium",
]:
    sys.modules.pop(_name, None)


class FakeBrowser:
    def __init__(self):
        self.calls = []
        self.driver = types.SimpleNamespace(current_url="https://www.instagram.com/diazcompleteautocaree/")

    def is_visible(self, xpath):
        self.calls.append(("is_visible", xpath))
        return xpath == "FOLLOWING"

    def click(self, xpath, **kwargs):
        self.calls.append(("click", xpath, kwargs))
        return True

    def time_sleep(self, seconds):
        self.calls.append(("sleep", seconds))


class FollowService(InstagramProfileService):
    def __init__(self, browser):
        self.browser = browser
        self.log = None

    def open_url(self, url):
        self.browser.calls.append(("open_url", url))

    def sleep(self, seconds):
        self.browser.calls.append(("sleep", seconds))

    def visible_any(self, xpaths):
        self.browser.calls.append(("visible_any", tuple(xpaths)))
        return getattr(self, "_next_visible", "")

    def click_xpath(self, xpath):
        self.browser.calls.append(("click_xpath", xpath))
        return self._click_result

    def _set_visible_sequence(self, *values):
        values = list(values)
        def visible(xpaths):
            self.browser.calls.append(("visible_any", tuple(xpaths)))
            return values.pop(0) if values else ""
        self.visible_any = visible


def test_proven_follow_path_navigates_profile_then_uses_existing_click_helper():
    browser = FakeBrowser()
    service = FollowService(browser)
    service._click_result = True
    service._set_visible_sequence("", "FOLLOW", "FOLLOWING")

    result = service.ensure_follow_profile(
        "https://www.instagram.com/diazcompleteautocaree/"
    )

    assert result == "followed"
    assert ("open_url", "https://www.instagram.com/diazcompleteautocaree/") in browser.calls
    assert any(call[0] == "click_xpath" and call[1] == "FOLLOW" for call in browser.calls)


def test_already_following_does_not_click():
    browser = FakeBrowser()
    service = FollowService(browser)
    service._set_visible_sequence("FOLLOWING")

    result = service.ensure_follow_profile(
        "https://www.instagram.com/diazcompleteautocaree/"
    )

    assert result == "already_following"
    assert not any(call[0] == "click_xpath" for call in browser.calls)


def test_missing_follow_button_fails_cleanly():
    browser = FakeBrowser()
    service = FollowService(browser)
    service._set_visible_sequence("", "")

    result = service.ensure_follow_profile(
        "https://www.instagram.com/diazcompleteautocaree/"
    )

    assert result == "error"
    assert not any(call[0] == "click_xpath" for call in browser.calls)


def test_click_failure_does_not_continue_as_followed():
    browser = FakeBrowser()
    service = FollowService(browser)
    service._click_result = False
    service._set_visible_sequence("", "FOLLOW")

    result = service.ensure_follow_profile(
        "https://www.instagram.com/diazcompleteautocaree/"
    )

    assert result == "error"


def test_inline_flow_uses_proven_profile_follow_then_returns_to_post():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "tasks"
        / "instagram_prospect_discovery_task.py"
    ).read_text(encoding="utf-8")

    start = source.index("def _inline_follow_and_comment_candidate")
    end = source.index("# =========================================================\n    # RECENT POSTS", start)
    block = source[start:end]

    assert "ensure_follow_profile(profile_url)" in block
    assert "self.profile_service.open_url(post_url)" in block
    assert "before_follow" in block
    assert "after_ensure_follow_profile" in block


def test_inline_flow_stops_before_comment_when_follow_is_not_confirmed():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "tasks"
        / "instagram_prospect_discovery_task.py"
    ).read_text(encoding="utf-8")

    start = source.index("def _inline_follow_and_comment_candidate")
    end = source.index("# =========================================================\n    # RECENT POSTS", start)
    block = source[start:end]

    follow_result = block.index("follow_status = self.profile_service.ensure_follow_profile")
    failure_return = block.index("return False", follow_result)
    comment_generation = block.index("generate_prospecting_comment_from_saved_post")

    assert failure_return < comment_generation
