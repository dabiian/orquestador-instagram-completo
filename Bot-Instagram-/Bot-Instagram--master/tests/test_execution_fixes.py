
from app.services.instagram_comment_generation_service import InstagramCommentGenerationService
from app.services.instagram_campaign_policy_service import InstagramCampaignPolicyService


def _comment_service():
    return object.__new__(InstagramCommentGenerationService)


def test_b2b_parser_recovers_literal_newlines_tabs_and_fenced_json():
    service = _comment_service()
    raw = """```json
{
  "skip_post": false,
  "comment_text": "Could be a useful referral fit.",
  "metadata": {
    "profile_description": "Line one
Line two\twith tab
Line three"
  }
}
```"""
    parsed = service.parse_ai_prospecting_b2b_response(raw)
    assert parsed is not None
    assert parsed["skip_post"] is False
    assert "Line two" in parsed["metadata"]["profile_description"]


def test_b2b_parser_preserves_valid_escaped_newlines():
    service = _comment_service()
    raw = r'{"skip_post":false,"comment_text":"Good fit.","metadata":{"x":"line one\nline two"}}'
    parsed = service.parse_ai_prospecting_b2b_response(raw)
    assert parsed["metadata"]["x"] == "line one\nline two"


def test_geo_only_rejects_non_geo_even_when_not_removed():
    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#SmallBusinessOwners",
        {"locations": ["Chicago, IL"]},
        "cleaning",
    )
    assert not ok
    assert reason in {"geo_validation_failed", "global_or_unvalidated"}


def test_geo_only_accepts_configured_local_tag():
    ok, reason = InstagramCampaignPolicyService.validate_hashtag(
        "#AirbnbChicago",
        {"locations": ["Chicago, IL"]},
        "cleaning",
    )
    assert ok


def test_comment_policy_blocks_hard_cta_for_every_campaign():
    for industry in ["abogados", "botanica", "cleaning", "fences", "marketing", "spa", "spa colombia"]:
        ok, reasons = InstagramCampaignPolicyService.validate_comment("Book now.", industry, [])
        assert not ok
        assert "hard_cta_not_allowed" in reasons


def test_comment_policy_blocks_source_forbidden_phrase():
    ok, reasons = InstagramCampaignPolicyService.validate_comment(
        "Guaranteed results", "spa colombia", []
    )
    assert not ok
    assert any(x.startswith("forbidden_phrase:") for x in reasons)
