from selenium.webdriver.common.by import By

from self_healer.selenium_adapter.locator_mapper import map_by_to_candidate, candidate_to_by
from self_healer.core.models import LocatorCandidate


def test_map_id_to_css_candidate():
    c = map_by_to_candidate(By.ID, "my-id")
    assert c.strategy == "css"
    assert 'id' in c.name or c.value.startswith('[id="')


def test_map_class_and_xpath_and_roundtrip():
    c1 = map_by_to_candidate(By.CLASS_NAME, "btn-primary")
    assert c1.strategy == "css"
    by, val = candidate_to_by(c1)
    assert by == By.CSS_SELECTOR

    c2 = map_by_to_candidate(By.XPATH, "//div[@role='main']")
    assert c2.strategy == "xpath"
    by2, val2 = candidate_to_by(c2)
    assert by2 == By.XPATH


def test_link_text_creates_xpath_literal():
    c = map_by_to_candidate(By.LINK_TEXT, "Click here")
    assert c.strategy == "xpath"
    assert "//a" in c.value
