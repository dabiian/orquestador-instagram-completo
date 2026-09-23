from self_healer.api.server import HealingAPIService
from self_healer.core.config import SelfHealerConfig
from self_healer.core.models import LocatorCandidate, LocatorIdentity
from self_healer.core.sqlite_store import SelfHealerStore
from self_healer.providers.fake_provider import FakeLocatorGenerator


def _service() -> HealingAPIService:
    config = SelfHealerConfig(project_name="bot-test", db_path=":memory:")
    store = SelfHealerStore(db_path=":memory:", disable_after_failures=config.disable_after_failures)
    generator = FakeLocatorGenerator(
        [LocatorCandidate(strategy="css", value='[data-testid="save"]', name="save-btn", confidence=0.95, reason="stable test selector")]
    )
    return HealingAPIService(config=config, store=store, locator_generator=generator)


def test_suggest_returns_candidates():
    service = _service()
    response = service.suggest(
        {
            "identity": {"project_name": "bot-test", "page_key": "home", "element_key": "save_btn"},
            "url": "https://example.com",
            "original_strategy": "xpath",
            "original_value": "//button[@id='save']",
            "html": "<html><body><button data-testid='save'>Save</button></body></html>",
            "target_description": "save button",
        }
    )

    assert response["ok"] is True
    assert response["count"] == 1
    assert response["candidates"][0]["value"] == '[data-testid="save"]'


def test_feedback_persists_locator():
    service = _service()
    identity = LocatorIdentity(project_name="bot-test", page_key="home", element_key="save_btn")
    payload = {
        "identity": {"project_name": "bot-test", "page_key": "home", "element_key": "save_btn"},
        "url": "https://example.com",
        "original_strategy": "xpath",
        "original_value": "//button[@id='save']",
        "html": "<html><body><button data-testid='save'>Save</button></body></html>",
        "candidate": {"strategy": "css", "value": '[data-testid="save"]', "name": "save-btn", "confidence": 0.95, "reason": "stable test selector"},
        "status": "success",
    }

    response = service.feedback(payload)

    assert response == {"ok": True, "status": "success"}
    locators = service.store.list_locators(identity)
    assert len(locators) == 1
    assert locators[0]["value"] == '[data-testid="save"]'