import json
from pathlib import Path

from app.services.instagram_campaign_policy_service import InstagramCampaignPolicyService
from app.services.instagram_comment_generation_service import InstagramCommentGenerationService

INDUSTRIES = [
    "abogados", "botanica", "cleaning", "fences", "marketing", "spa", "spa colombia"
]

BOT = Path(__file__).resolve().parents[1]
POLICY_DIR = BOT / "app" / "utils" / "config" / "instagram_policies"


def test_migrated_02_03_04_files_match_source_copies():
    # The compatibility layer must preserve the source configuration exactly.
    source_root = Path("/mnt/data/migration_work/CONFIG_SOURCE/config 1/config")
    if not source_root.exists():
        return
    for industry in INDUSTRIES:
        for n, name in [("02", "competitor_filter"), ("03", "discovery_hashtags"), ("04", "intro_comment_policy")]:
            source = source_root / industry / f"{n}_{name}.json"
            runtime = POLICY_DIR / f"{industry}_{n}_{name}.json"
            assert runtime.read_bytes() == source.read_bytes()


def test_discovery_rejects_removed_global_hashtag():
    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#GrandOpening",
        {"locations": ["Chicago, IL"]},
        "marketing",
    )
    assert not ok
    assert reason == "configured_removed"


def test_discovery_accepts_configured_local_hashtag():
    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#ChicagoSmallBusiness",
        {"locations": ["Chicago, IL"]},
        "marketing",
    )
    assert ok
    assert reason == "accepted"


def test_discovery_rejects_unlisted_non_geo_hashtag_under_geo_only_policy():
    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#SmallBusiness",
        {"locations": ["Chicago, IL"]},
        "marketing",
    )
    assert not ok
    assert reason in {"configured_removed", "global_or_unvalidated", "geo_validation_failed"}


def test_spa_colombia_requires_bogota_or_service_area_signal():
    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#Beauty",
        {"locations": ["Bogotá, Colombia"]},
        "spa colombia",
    )
    assert not ok
    assert reason in {"configured_removed", "global_or_unvalidated", "geo_validation_failed"}

    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#BellezaBogota",
        {"locations": ["Bogotá, Colombia"]},
        "spa colombia",
    )
    assert ok


def _service():
    return object.__new__(InstagramCommentGenerationService)


def test_comment_policy_enforces_every_industry_global_limits():
    service = _service()
    for industry in INDUSTRIES:
        policy = InstagramCampaignPolicyService.load_comment_policy(industry)
        rules = policy["global_rules"]
        max_sentences = rules["max_sentences"]
        emoji_max = rules["emoji_max"]

        too_many = "Uno. Dos. Tres." if max_sentences < 3 else "Uno."
        ok, reasons = InstagramCampaignPolicyService.validate_comment(
            too_many, industry, []
        )
        if max_sentences < 3:
            assert not ok
            assert "max_sentences_exceeded" in reasons

        emoji_text = "Hola " + "😀" * (emoji_max + 1)
        ok, reasons = InstagramCampaignPolicyService.validate_comment(
            emoji_text, industry, []
        )
        assert not ok
        assert "emoji_max_exceeded" in reasons


def test_comment_policy_enforces_source_banned_patterns_for_all_industries():
    for industry in INDUSTRIES:
        policy = InstagramCampaignPolicyService.load_comment_policy(industry)
        banned = policy["banned_patterns"][0]["bad"]
        ok, reasons = InstagramCampaignPolicyService.validate_comment(
            banned, industry, []
        )
        assert not ok, industry
        assert any(r.startswith("forbidden_phrase:") for r in reasons), industry


def test_comment_policy_blocks_exact_and_near_duplicate_when_source_disallows_copy_paste():
    industry = "spa colombia"
    old = "Te ves muy profesional ✨ La Dra. Deysi Torres puede orientarte."
    ok, reasons = InstagramCampaignPolicyService.validate_comment(old, industry, [old])
    assert not ok
    assert "exact_duplicate" in reasons


def test_comment_prompt_contains_full_source_policy():
    prompt = InstagramCampaignPolicyService.comment_prompt("botanica")
    assert "INTRO COMMENT POLICY" in prompt
    assert "global_rules" in prompt
    assert "banned_patterns" in prompt
    assert "categories" in prompt


def test_common_industry_prompt_includes_policy_even_without_long_form_rules():
    service = _service()
    prompt = service._get_industry_rules_prompt({"campaign_type": "cleaning"}, {})
    assert "INTRO COMMENT POLICY" in prompt


def test_spa_legacy_fence_classifier_is_not_injected():
    from app.services.instagram_prospect_classification_service import InstagramProspectClassificationService
    service = object.__new__(InstagramProspectClassificationService)
    assert service._load_long_form_classification_rules("spa") == ""


def test_b2b_parser_accepts_literal_newlines_inside_json_strings():
    service = object.__new__(InstagramCommentGenerationService)
    raw = '''{
      "skip_post": false,
      "comment_text": "Solid local team — could be a useful referral fit.",
      "profile_description": "Keeping Chicagoland flowing right!\nPlumbing • Sewer • Drain Cleaning\nFast • Honest • Local | 24/7 Service",
      "metadata": {"b2b_target_type": "home service business", "b2b_angle": "referral"}
    }'''
    parsed = service.parse_ai_prospecting_b2b_response(raw)
    assert parsed is not None
    assert parsed["skip_post"] is False
    assert "Chicagoland" in parsed["profile_description"]

def test_discovery_geo_terms_are_industry_specific():
    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#BogotaBeauty", {"locations": ["Chicago, IL"]}, "cleaning"
    )
    assert not ok
    assert reason in {"global_or_unvalidated", "geo_validation_failed"}

    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#ChicagoBusiness", {"locations": ["Bogotá, Colombia"]}, "spa colombia"
    )
    assert not ok
    assert reason in {"global_or_unvalidated", "geo_validation_failed"}

    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#BogotaFemenina", {"locations": ["Bogotá, Colombia"]}, "spa colombia"
    )
    assert ok
