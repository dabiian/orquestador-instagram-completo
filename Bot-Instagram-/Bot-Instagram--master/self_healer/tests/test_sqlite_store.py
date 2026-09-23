from self_healer.core.sqlite_store import SelfHealerStore
from self_healer.core.models import LocatorIdentity, LocatorCandidate, HealingContext


def test_sqlite_store_upsert_and_query():
    store = SelfHealerStore(db_path=":memory:")
    identity = LocatorIdentity(project_name="testproj", page_key="home", element_key="btn1")
    context = HealingContext(identity=identity, url="http://example", original_strategy="css", original_value='[id="orig"]', html="<div></div>")
    candidate = LocatorCandidate(strategy="css", value='[data-testid="x"]', name="x", confidence=0.7)

    assert store.get_best_locator(identity) is None
    store.save_success(context, candidate)
    best = store.get_best_locator(identity)
    assert best is not None
    assert best.value == candidate.value
    locs = store.list_locators(identity)
    assert len(locs) == 1
    assert int(locs[0]["successes"]) >= 1
    store.close()
