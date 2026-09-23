from self_healer.core.models import HealingContext, LocatorIdentity
from self_healer.providers.openai_provider import OpenAILocatorGenerator


def test_user_prompt_includes_locator_hint_from_description():
    provider = OpenAILocatorGenerator(client=object())
    ctx = HealingContext(
        identity=LocatorIdentity(project_name="p", page_key="login", element_key="auto-key"),
        url="https://example.com/login",
        original_strategy="xpath",
        original_value="//input[@id='email']",
        html="<input id='email' />",
        action="find_element",
        target_description="input login",
    )

    prompt = provider._build_user_prompt(ctx)
    assert "Locator hint: input login" in prompt


def test_user_prompt_falls_back_to_element_key_when_description_missing():
    provider = OpenAILocatorGenerator(client=object())
    ctx = HealingContext(
        identity=LocatorIdentity(project_name="p", page_key="login", element_key="email-input"),
        url="https://example.com/login",
        original_strategy="xpath",
        original_value="//input[@id='email']",
        html="<input id='email' />",
        action="find_element",
    )

    prompt = provider._build_user_prompt(ctx)
    assert "Locator hint: email-input" in prompt
