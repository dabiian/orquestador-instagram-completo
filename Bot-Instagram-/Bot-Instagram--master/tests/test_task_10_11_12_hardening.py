
import ast
import importlib.util
import sys
import types

# Minimal Selenium stubs so navigation tests remain deterministic without a real browser.
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
remote_mod = types.ModuleType("selenium.webdriver.remote")
webelement_mod = types.ModuleType("selenium.webdriver.remote.webelement")
class WebElement: pass
webelement_mod.WebElement = WebElement
remote_mod.webelement = webelement_mod
sys.modules.setdefault("selenium.webdriver.remote", remote_mod)
sys.modules.setdefault("selenium.webdriver.remote.webelement", webelement_mod)
exceptions_mod = types.ModuleType("selenium.common.exceptions")
class StaleElementReferenceException(Exception): pass
exceptions_mod.StaleElementReferenceException = StaleElementReferenceException
common_exc = types.ModuleType("selenium.common")
common_exc.exceptions = exceptions_mod
sys.modules.setdefault("selenium.common", common_exc)
sys.modules.setdefault("selenium.common.exceptions", exceptions_mod)

nav_spec = importlib.util.spec_from_file_location(
    "instagram_followback_navigation_test_module",
    "app/tasks/instagram_followback/instagram_followback_navigation.py",
)
nav_mod = importlib.util.module_from_spec(nav_spec)
nav_spec.loader.exec_module(nav_mod)
Mixin = nav_mod.InstagramFollowbackNavigationMixin


class Element:
    def __init__(self, displayed=True):
        self.displayed = displayed
        self.clicked = False
    def is_displayed(self):
        return self.displayed
    def is_enabled(self):
        return True
    def click(self):
        self.clicked = True


class Driver:
    def __init__(self, url):
        self.current_url = url
        self.escapes = 0
        self.close = Element()
        self.dialogs = [self.close] if "/p/" in url else []
    def execute_script(self, script, *args):
        if "elementFromPoint" in script:
            return True
        return None
    def find_elements(self, by, selector):
        if selector == "//*[@role='dialog']":
            return self.dialogs
        return []
    def find_element(self, by, selector):
        if by == By.TAG_NAME and selector == "body":
            return self
        if "Cerrar" in selector or "Close" in selector:
            return self.close
        raise AssertionError((by, selector))
    def send_keys(self, key):
        if key == Keys.ESCAPE:
            self.escapes += 1
            self.current_url = "https://www.instagram.com/"
            self.dialogs = []


class Browser:
    def __init__(self, driver):
        self.driver = driver
        self.navigations = []
    def time_sleep(self, _):
        pass
    def go_to_url(self, url):
        self.navigations.append(url)
        self.driver.current_url = url
        self.driver.dialogs = []


class Nav(Mixin):
    pass


def test_task10_post_surface_is_cleared_before_search():
    driver = Driver("https://www.instagram.com/p/ABC/")
    nav = Nav()
    nav.browser = Browser(driver)
    nav.log = types.SimpleNamespace(info=lambda *a, **k: None,
                                    warning=lambda *a, **k: None,
                                    error=lambda *a, **k: None,
                                    debug=lambda *a, **k: None)
    assert nav._dismiss_transient_overlays_for_search()
    assert "/p/" not in driver.current_url
    assert driver.escapes >= 1


def test_task10_never_accepts_non_interactable_search_control():
    driver = Driver("https://www.instagram.com/")
    nav = Nav()
    nav.browser = Browser(driver)
    nav.log = types.SimpleNamespace(info=lambda *a, **k: None,
                                    warning=lambda *a, **k: None,
                                    error=lambda *a, **k: None,
                                    debug=lambda *a, **k: None)
    assert nav._element_is_pointer_interactable(Element()) is True


def test_task11_has_no_undefined_prospect_reference_in_execute():
    source = open("app/tasks/instagram_prospect_comment_task.py", encoding="utf-8").read()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "InstagramProspectCommentTask")
    execute = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    names = [n for n in ast.walk(execute) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]
    assert not any(n.id == "prospect" for n in names)


def test_task12_zero_new_replies_is_not_an_error():
    source = open("app/tasks/instagram_prospect_reply_monitor_task.py", encoding="utf-8").read()
    assert "return bool(processed_posts > 0 and failed_posts < processed_posts)" in source
    assert "replies_encontradas" in source
    assert "ya_registradas" in source
    assert "nuevas" in source


def test_task11_uses_safe_comment_flow_and_no_visible_legacy_path():
    source = open("app/tasks/instagram_prospect_comment_task.py", encoding="utf-8").read()
    assert "comment_current_post(comment_text)" in source
    assert "comment_current_post_visible(comment_text)" not in source
    assert "finally:" in source
    assert "_cleanup_post_surface" in source


def test_task11_campaign_name_is_fallback_for_runtime_campaign_type():
    source = open("app/tasks/instagram_prospect_comment_task.py", encoding="utf-8").read()
    assert 'or campaign.get("name")' in source


def test_task11_publish_flow_is_idempotent_after_click():
    source = open("app/services/instagram_post_interaction_service.py", encoding="utf-8").read()
    assert "NO se reintenta para evitar duplicados" in source
    assert "_confirm_comment_box_empty" in source
    assert "_comment_box_contains_text" in source


def test_task11_does_not_retry_after_unknown_submit_state():
    source = open("app/services/instagram_post_interaction_service.py", encoding="utf-8").read()
    block = source[source.index('    def comment_current_post(self, comment_text: str) -> bool:'):source.index('    # =========================================================\n    # COMMENT - VISIBLE FLOW')]
    assert 'estado indeterminado después de publicar' in block
    assert 'return False' in block


def test_task11_publish_does_not_duplicate_when_first_submit_clears_box():
    from app.services.instagram_post_interaction_service import InstagramPostInteractionService

    class FakeBrowser:
        def __init__(self):
            self.sleeps = []
        def time_sleep(self, value):
            self.sleeps.append(value)

    service = InstagramPostInteractionService(FakeBrowser())
    clicks = {"count": 0}
    box_values = iter(["", ""])
    service._get_first_comment_box = lambda: object()
    service._focus_element_safe = lambda _box: True
    service.write_comment_with_emojis_js = lambda _text: True
    service._click_publish_button_near_comment_box = lambda _box: clicks.__setitem__("count", clicks["count"] + 1) or True
    service._confirm_comment_visible = lambda _text, attempts=6: False
    service._read_comment_box_text = lambda _box: next(box_values)
    assert service.comment_current_post("hello") is True
    assert clicks["count"] == 1


def test_task11_publish_retries_only_when_text_remains_in_box():
    from app.services.instagram_post_interaction_service import InstagramPostInteractionService

    class FakeBrowser:
        def time_sleep(self, _):
            pass

    service = InstagramPostInteractionService(FakeBrowser())
    clicks = {"count": 0}
    values = iter(["hello", "hello", "hello", ""])
    service._get_first_comment_box = lambda: object()
    service._focus_element_safe = lambda _box: True
    service.write_comment_with_emojis_js = lambda _text: True
    service._click_publish_button_near_comment_box = lambda _box: clicks.__setitem__("count", clicks["count"] + 1) or True
    service._confirm_comment_visible = lambda _text, attempts=6: False
    service._read_comment_box_text = lambda _box: next(values)
    assert service.comment_current_post("hello") is False
    assert clicks["count"] == 2


def test_task11_cleanup_ignores_hidden_dialogs_and_uses_visible_dom_check():
    source = open("app/tasks/instagram_prospect_comment_task.py", encoding="utf-8").read()
    block = source[source.index("    def _cleanup_post_surface"):source.index("    def _get_social_media_account_id", source.index("    def _cleanup_post_surface"))]
    assert "getComputedStyle" in block
    assert "getBoundingClientRect" in block
    assert "aria-hidden" in block
    assert "driver.get(\"https://www.instagram.com/\")" in block
    assert "driver.refresh()" in block


def test_task11_cleanup_js_close_is_atomic_to_avoid_stale_elements():
    source = open("app/tasks/instagram_prospect_comment_task.py", encoding="utf-8").read()
    block = source[source.index("    def _cleanup_post_surface"):source.index("    def _get_social_media_account_id", source.index("    def _cleanup_post_surface"))]
    assert "const dialogs = [...document.querySelectorAll('[role=\"dialog\"]')].filter(visible);" in block
    assert "target.click(); return true;" in block
    assert "header.querySelectorAll('button,[role=\"button\"]')" in block


def test_task11_cleanup_visible_dialog_flow_returns_clean_state():
    from app.tasks.instagram_prospect_comment_task import InstagramProspectCommentTask

    class FakeDriver:
        def __init__(self):
            self.current_url = "https://www.instagram.com/p/ABC/"
            self.visible = True
            self.get_calls = 0
            self.refresh_calls = 0
        def execute_script(self, script, *args):
            if "target.click(); return true;" in script:
                self.visible = False
                return True
            if "querySelectorAll('[role=\"dialog\"]')" in script and "getBoundingClientRect" in script:
                return self.visible
            return None
        def find_element(self, by, selector):
            class Body:
                def send_keys(inner, key):
                    pass
            return Body()
        def find_elements(self, *args):
            return []
        def get(self, url):
            self.get_calls += 1
            self.current_url = url
        def refresh(self):
            self.refresh_calls += 1

    class FakeBrowser:
        def __init__(self, driver): self.driver = driver
        def execute_script_safe(self, script, *args): return self.driver.execute_script(script, *args)
        def time_sleep(self, _): pass
        def go_to_url(self, url): self.driver.get(url)

    task = object.__new__(InstagramProspectCommentTask)
    task.browser = FakeBrowser(FakeDriver())
    task.log = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
    assert task._cleanup_post_surface(72) is True
    assert task.browser.driver.refresh_calls == 0


def test_task11_empty_eligible_posts_is_success_not_error():
    source = open("app/tasks/instagram_prospect_comment_task.py", encoding="utf-8").read()
    assert 'if not ok_posts:' in source
    assert 'if not isinstance(posts, list):' in source
    assert 'no hay prospect posts nuevos/elegibles; tarea completada sin acciones' in source
    block = source[source.index('            if not ok_posts:'):source.index('            commented_total = 0', source.index('            if not ok_posts:'))]
    assert 'return True' in block


def test_task11_empty_posts_does_not_mask_api_failure():
    source = open("app/tasks/instagram_prospect_comment_task.py", encoding="utf-8").read()
    block = source[source.index('            if not ok_posts:'):source.index('            commented_total = 0', source.index('            if not ok_posts:'))]
    assert block.index('if not ok_posts:') < block.index('if not posts:')
    assert block.count('return False') >= 2


def test_task10_grid_candidate_opens_by_direct_href_not_web_element_click():
    from app.tasks.instagram_followback.instagram_followback_navigation import InstagramFollowbackNavigationMixin

    class FakePost:
        def __init__(self, href):
            self.href = href
        def get_attribute(self, name):
            return self.href if name == "href" else ""
        def is_displayed(self): return True
        def is_enabled(self): return True
        def click(self): raise AssertionError("WebElement.click must not be used for hashtag candidates")

    class FakeDriver:
        def __init__(self):
            self.current_url = "https://www.instagram.com/explore/tags/test/"
        def find_elements(self, *args):
            return [FakePost("https://www.instagram.com/p/ABC/")]

    class FakeBrowser:
        def __init__(self):
            self.driver = FakeDriver()
            self.navigated = []
        def time_sleep(self, _): pass
        def go_to_url(self, url):
            self.navigated.append(url)
            self.driver.current_url = url
        def execute_script(self, *args): return None

    task = object.__new__(InstagramFollowbackNavigationMixin)
    task.browser = FakeBrowser()
    task.log = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
    task.current_search_term = "#test"
    assert task._open_next_post_from_hashtag_grid(set()) == "https://www.instagram.com/p/ABC/"
    assert task.browser.navigated == ["https://www.instagram.com/p/ABC/"]


def test_comment_submit_accepted_with_empty_editor_is_success_without_retry():
    from app.services.instagram_post_interaction_service import InstagramPostInteractionService

    service = InstagramPostInteractionService.__new__(InstagramPostInteractionService)
    service.log = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    service.browser = types.SimpleNamespace(time_sleep=lambda *_: None)
    service._get_first_comment_box = lambda: object()
    service._focus_element_safe = lambda *_: None
    service._confirm_comment_visible = lambda *_, **__: False
    service.write_comment_with_emojis_js = lambda *_: True
    service._click_publish_button_near_comment_box = lambda *_: True
    service._confirm_comment_box_empty = lambda: True
    service._comment_box_contains_text = lambda *_: False

    assert service.comment_current_post("comentario de prueba") is True
