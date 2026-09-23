from app.config.industry_prompt_rules import get_industry_prompt_rules, normalize_campaign_type


def test_industry_prompt_aliases():
    assert normalize_campaign_type("Spa Colombia") == "spa colombia"
    assert normalize_campaign_type("Botánicas") == "botanica"
    assert normalize_campaign_type("FENCING") == "fences"


def test_long_form_prompts_are_available():
    for industry in ("marketing", "fences", "spa", "botanica", "abogados"):
        rules = get_industry_prompt_rules(industry)
        assert len(rules) > 1000
        assert "skip_post" in rules.lower()


def test_structured_rules_cover_other_instagram_industries():
    for industry in ("cleaning", "construction", "real_estate"):
        rules = get_industry_prompt_rules(industry)
        assert "INDUSTRY RULES" in rules
        assert len(rules) > 200


def test_all_facebook_industries_have_classification_rules():
    from pathlib import Path
    base = Path(__file__).parent / "app" / "config" / "prompts" / "facebook_compatible"
    for industry in ("botanica", "fences", "spa", "spa colombia", "abogados", "marketing", "cleaning"):
        text = (base / f"{industry}_classification_prompt.txt").read_text(encoding="utf-8")
        assert len(text) > 1000
        assert "PROFILE DATA" in text or "Mensaje de sistema" in text
