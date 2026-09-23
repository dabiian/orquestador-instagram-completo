
import sys
import types

# The production project normally provides Selenium. These tests are intentionally
# self-contained so deterministic integrity logic can be exercised in environments
# where the optional Selenium dependency is not installed.
selenium = types.ModuleType("selenium")
webdriver = types.ModuleType("selenium.webdriver")
common = types.ModuleType("selenium.webdriver.common")
by_mod = types.ModuleType("selenium.webdriver.common.by")
keys_mod = types.ModuleType("selenium.webdriver.common.keys")
ac_mod = types.ModuleType("selenium.webdriver.common.action_chains")

class By:
    CSS_SELECTOR = "css selector"
    XPATH = "xpath"
    TAG_NAME = "tag name"

class Keys:
    ESCAPE = "ESCAPE"
    ENTER = "ENTER"
    SPACE = "SPACE"
    CONTROL = "CONTROL"
    BACKSPACE = "BACKSPACE"

class ActionChains:
    def __init__(self, driver): pass
    def move_to_element(self, element): return self
    def pause(self, seconds): return self
    def click(self): return self
    def perform(self): return None

by_mod.By = By
keys_mod.Keys = Keys
ac_mod.ActionChains = ActionChains
sys.modules.setdefault("selenium", selenium)
sys.modules.setdefault("selenium.webdriver", webdriver)
sys.modules.setdefault("selenium.webdriver.common", common)
sys.modules.setdefault("selenium.webdriver.common.by", by_mod)
sys.modules.setdefault("selenium.webdriver.common.keys", keys_mod)
sys.modules.setdefault("selenium.webdriver.common.action_chains", ac_mod)
exceptions_mod = types.ModuleType("selenium.common.exceptions")
class StaleElementReferenceException(Exception):
    pass
exceptions_mod.StaleElementReferenceException = StaleElementReferenceException
selenium_common = types.ModuleType("selenium.common")
selenium_common.exceptions = exceptions_mod
sys.modules.setdefault("selenium.common", selenium_common)
sys.modules.setdefault("selenium.common.exceptions", exceptions_mod)

from app.services.instagram_profile_service import InstagramProfileService
import importlib.util

_nav_spec = importlib.util.spec_from_file_location(
    "instagram_followback_navigation_hardened",
    "app/tasks/instagram_followback/instagram_followback_navigation.py",
)
_nav_mod = importlib.util.module_from_spec(_nav_spec)
_nav_spec.loader.exec_module(_nav_mod)
InstagramFollowbackNavigationMixin = _nav_mod.InstagramFollowbackNavigationMixin


class FakeElement:
    def __init__(self, href="", displayed=True, enabled=True):
        self.href = href
        self.displayed = displayed
        self.enabled = enabled
        self.clicked = False
    def get_attribute(self, name):
        if name == "href":
            return self.href
        if name == "value":
            return self.value if hasattr(self, "value") else ""
        return ""
    def is_displayed(self):
        return self.displayed
    def is_enabled(self):
        return self.enabled
    def click(self):
        self.clicked = True
    def send_keys(self, *args):
        self.value = getattr(self, "value", "") + "".join(str(x) for x in args if str(x) not in {"CONTROL", "BACKSPACE"})


class FakeDriver:
    def __init__(self, url="https://www.instagram.com/target/"):
        self.current_url = url
        self.title = ""
        self.author = ""
        self.context = {}
        self.interactable = True
        self.executed_scripts = []
        self.search_inputs = []
    def execute_script(self, script, *args):
        self.executed_scripts.append(script)
        if "author_username" in script and "caption_text" in script:
            return self.context
        if "OPENED_POST_AUTHOR_USERNAME" in script:
            return self.author
        if "elementFromPoint" in script:
            return self.interactable
        if "PROFILE_GRID_POST_TARGETS" in script:
            return []
        return self.author
    def find_elements(self, by, selector):
        if by == By.CSS_SELECTOR:
            return self.search_inputs
        return []
    def find_element(self, by, selector):
        raise AssertionError("Unexpected find_element in deterministic test")


class FakeBrowser:
    def __init__(self, driver):
        self.driver = driver
        self.navigated = []
    def go_to_url(self, url):
        self.navigated.append(url)
        self.driver.current_url = url
    def time_sleep(self, seconds):
        pass


def make_service(url="https://www.instagram.com/target/"):
    driver = FakeDriver(url)
    return InstagramProfileService(FakeBrowser(driver)), driver


def test_recent_post_accepts_only_expected_url_and_author():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    driver.author = "target"
    assert service.open_recent_post_from_profile_grid(
        "https://www.instagram.com/target/",
        "https://www.instagram.com/p/AAA/",
        expected_author_username="target",
    )


def test_recent_post_rejects_wrong_author():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    driver.author = "other"
    assert not service.open_recent_post_from_profile_grid(
        "https://www.instagram.com/target/",
        "https://www.instagram.com/p/AAA/",
        expected_author_username="target",
    )


def test_recent_post_rejects_wrong_current_url():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    service.open_url = lambda url: setattr(driver, "current_url", "https://www.instagram.com/p/BBB/")
    driver.author = "target"
    result = service.open_recent_post_from_profile_grid(
        "https://www.instagram.com/target/",
        "https://www.instagram.com/p/AAA/",
        expected_author_username="target",
    )
    assert not result

def test_recent_context_rejects_url_and_author_mismatch():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    driver.context = {
        "post_url": "https://www.instagram.com/p/AAA/",
        "author_username": "other",
        "caption_text": "x",
        "post_type": "post",
    }
    assert service.extract_recent_post_context(
        expected_url="https://www.instagram.com/p/AAA/",
        expected_author_username="target",
    ) == {}


def test_recent_context_accepts_matching_identity():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    driver.context = {
        "post_url": "https://www.instagram.com/p/AAA/",
        "author_username": "target",
        "author_profile_url": "https://www.instagram.com/target/",
        "caption_text": "x",
        "post_type": "post",
    }
    context = service.extract_recent_post_context(
        expected_url="https://www.instagram.com/p/AAA/",
        expected_author_username="target",
    )
    assert context["author_username"] == "target"
    assert context["post_url"].endswith("/p/AAA/")


def test_search_input_covered_by_overlay_is_not_pointer_interactable():
    class Harness(InstagramFollowbackNavigationMixin):
        pass
    driver = FakeDriver()
    driver.interactable = False
    browser = FakeBrowser(driver)
    harness = Harness()
    harness.browser = browser
    element = FakeElement()
    assert not harness._element_is_pointer_interactable(element)


def test_search_input_is_pointer_interactable_when_topmost():
    class Harness(InstagramFollowbackNavigationMixin):
        pass
    driver = FakeDriver()
    driver.interactable = True
    browser = FakeBrowser(driver)
    harness = Harness()
    harness.browser = browser
    element = FakeElement()
    assert harness._element_is_pointer_interactable(element)


def test_known_search_inputs_use_raw_driver_and_never_self_healer():
    class Harness(InstagramFollowbackNavigationMixin):
        pass
    driver = FakeDriver()
    input_el = FakeElement()
    driver.search_inputs = [input_el]
    wrapped = types.SimpleNamespace(raw=driver)
    browser = types.SimpleNamespace(driver=wrapped)
    harness = Harness()
    harness.browser = browser
    assert harness._get_visible_search_inputs() == [input_el]


def test_profile_grid_refuses_to_collect_when_browser_is_on_another_profile():
    service, driver = make_service("https://www.instagram.com/other/")
    assert service.collect_profile_grid_post_targets(
        "https://www.instagram.com/target/",
        "target",
        limit=3,
    ) == []
    assert driver.executed_scripts == []


def test_recent_context_requires_author_when_expected_author_is_supplied():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    driver.context = {
        "post_url": "https://www.instagram.com/p/AAA/",
        "author_username": "",
        "caption_text": "x",
        "post_type": "post",
    }
    assert service.extract_recent_post_context(
        expected_url="https://www.instagram.com/p/AAA/",
        expected_author_username="target",
    ) == {}


def test_campaign_account_invariant_is_present_in_source():
    source = open(
        "app/tasks/instagram_prospect_discovery_task.py",
        encoding="utf-8",
    ).read()
    assert "def _campaign_account_matches" in source
    assert "[account-integrity] BLOQUEADO campaign/account mismatch" in source


def test_comment_confirmation_rejects_publish_click_without_visible_comment():
    from app.services.instagram_post_interaction_service import InstagramPostInteractionService
    browser = types.SimpleNamespace(time_sleep=lambda seconds: None)
    service = InstagramPostInteractionService(browser=browser)
    service._execute_script_safe = lambda script, *args: False
    assert not service._confirm_comment_visible("Comentario único")


def test_comment_confirmation_accepts_rendered_comment():
    from app.services.instagram_post_interaction_service import InstagramPostInteractionService
    browser = types.SimpleNamespace(time_sleep=lambda seconds: None)
    service = InstagramPostInteractionService(browser=browser)
    service._execute_script_safe = lambda script, *args: True
    assert service._confirm_comment_visible("Comentario único")


def test_search_control_resolver_has_live_dom_fallbacks():
    from app.config.locators.instagram_followback_locators import InstagramFollowbackLocators
    assert "SEARCH_NAV_JS" in dir(InstagramFollowbackLocators)
    assert "aria-label" in InstagramFollowbackLocators.SEARCH_NAV_JS
    assert "href" in InstagramFollowbackLocators.SEARCH_NAV_JS


def test_search_open_retries_when_control_is_temporarily_missing():
    class Harness(InstagramFollowbackNavigationMixin):
        pass
    driver = FakeDriver()
    harness = Harness()
    harness.browser = FakeBrowser(driver)
    harness.log = types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)
    harness._dismiss_transient_overlays_for_search = lambda: None
    calls = {"n": 0}
    def resolve():
        calls["n"] += 1
        return None if calls["n"] < 3 else FakeElement()
    harness._resolve_search_control = resolve
    harness._search_opened = lambda: False
    assert not harness._open_search_button()
    assert calls["n"] >= 3


def test_search_failure_does_not_continue_with_all_hashtags_source_contract():
    source = open(
        "app/tasks/instagram_prospect_discovery_task.py",
        encoding="utf-8",
    ).read()
    assert "[search-ui] ABORTADO discovery" in source
    assert "recuperación" in source.lower()


def test_follow_from_current_post_uses_proven_profile_flow():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    states = iter(["", "FOLLOW_XPATH", "FOLLOWING_XPATH"])
    service.visible_any = lambda _xpaths: next(states)
    clicks = {"count": 0}
    service.click_xpath = lambda _xpath: clicks.__setitem__("count", clicks["count"] + 1) or True
    service.sleep = lambda _seconds: None

    result = service.ensure_follow_profile("https://www.instagram.com/target/")

    assert result == "followed"
    assert clicks["count"] == 1
    assert driver.current_url == "https://www.instagram.com/target/"

def test_follow_from_current_post_rejects_wrong_author_without_navigation():
    service, driver = make_service("https://www.instagram.com/p/AAA/")
    service.get_opened_post_author_username = lambda: "other"
    service.open_url = lambda _url: (_ for _ in ()).throw(AssertionError("profile navigation forbidden"))
    assert service.ensure_follow_profile("https://www.instagram.com/target/") == "error"
    assert driver.current_url == "https://www.instagram.com/p/AAA/"


def test_follow_from_profile_still_navigates_when_not_on_post():
    service, driver = make_service("https://www.instagram.com/")
    calls = []
    service.open_url = lambda url: calls.append(url)
    service.sleep = lambda _seconds: None
    states = iter(["", "FOLLOW_XPATH", "FOLLOWING_XPATH"])
    service.visible_any = lambda _xpaths: next(states)
    service.click_xpath = lambda _xpath: True

    assert service.ensure_follow_profile("https://www.instagram.com/target/") == "followed"
    assert calls == ["https://www.instagram.com/target/"]
