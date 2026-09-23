from pathlib import Path

from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)


def test_spa_does_not_inject_contaminated_fence_classifier():
    service = object.__new__(InstagramProspectClassificationService)
    rules = service._load_long_form_classification_rules("spa")

    assert rules == ""

    spa_prompt = (
        Path(__file__).resolve().parents[1]
        / "app/config/prompts/facebook_compatible/spa_classification_prompt.txt"
    ).read_text(encoding="utf-8")

    # Regression guard: the legacy file is known to contain the fence rubric,
    # so it must never become the active long-form classifier for spa.
    assert "fence / fence installation services" in spa_prompt.lower()
    assert "fence installation" in spa_prompt.lower()


def test_spa_colombia_keeps_its_dedicated_classifier():
    service = object.__new__(InstagramProspectClassificationService)
    rules = service._load_long_form_classification_rules("spa colombia")

    assert "medicina estética" in rules.lower()
    assert "fence / fence installation services" not in rules.lower()


def test_fences_keeps_its_dedicated_classifier():
    service = object.__new__(InstagramProspectClassificationService)
    rules = service._load_long_form_classification_rules("fences")

    assert "fence / fence installation services" in rules.lower()
