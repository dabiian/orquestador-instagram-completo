from self_healer.providers.fake_provider import FakeLocatorGenerator
from self_healer.core.models import LocatorIdentity, HealingContext


def test_fake_provider_returns_candidates():
    gen = FakeLocatorGenerator()
    identity = LocatorIdentity(project_name="p")
    ctx = HealingContext(identity=identity, url="http://x", original_strategy="css", original_value="v", html="<div></div>")
    candidates = gen.generate(ctx)
    assert isinstance(candidates, list)
    assert len(candidates) >= 1
    assert candidates[0].strategy in {"css", "xpath"}
