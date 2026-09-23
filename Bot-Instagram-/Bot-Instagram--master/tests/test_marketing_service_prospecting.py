import json

from app.services.instagram_prospect_classification_service import InstagramProspectClassificationService
from app.utils.instagram_url import _normalize_instagram_href, _extract_username_from_url


class FakeAI:
    def __init__(self, payload):
        self.payload = payload
    def get_bot_ia_long_prompt(self, *_args):
        return True, json.dumps(self.payload)


def campaign(**overrides):
    c = {
        "id": 10,
        "name": "Chicago Local Business Growth",
        "services_snapshot": [
            "social media management", "social media marketing", "content creation",
            "lead generation", "local business marketing", "online advertising",
            "facebook marketing", "instagram marketing", "local seo"
        ],
        "strategy_snapshot": {
            "hashtags": ["#ChicagoSmallBusiness", "#ChicagoLocalBusiness"],
            "keywords": [],
            "locations": ["Chicago, IL", "Chicago Metropolitan Area"],
        },
    }
    c.update(overrides)
    return c


def payload(**overrides):
    p = {
        "competitor_score": 0, "is_competitor": False, "is_blacklisted": False,
        "blacklist_reason": "", "profile_classification": "LOCAL_BUSINESS_PAGE",
        "business_role": "COMPANY_PAGE", "business_vertical": "FOOD",
        "competitor_relation": "UNKNOWN", "commercial_intent_score": 82,
        "classification_confidence": 92,
        "classification_evidence": ["Restaurant business serving Chicago customers."],
        "industry_detected": "restaurant", "location_match": True,
        "location_confidence": "high", "location_evidence": ["Located in Chicago, IL"],
        "skip_post": False, "mode": "normal_prospecting",
        "selected_service": "social media marketing", "b2b_target_type": "",
        "b2b_angle": "", "b2b_confidence": "medium",
        "request_directness": "indirect",
        "service_match_reason": "Local restaurant has active commercial presence.",
        "comment": "Your restaurant content could benefit from stronger social media marketing. Message us for details.",
    }
    p.update(overrides)
    return p


def test_marketing_campaign_is_service_prospecting_not_marketing_industry_target():
    s = InstagramProspectClassificationService(FakeAI(payload()))
    c = campaign()
    industry = s.detect_campaign_industry(c)
    assert industry == "marketing"
    assert s.is_service_prospecting_campaign(c, industry) is True
    prompt = s.build_prompt(c, industry, s.load_competitor_rules(industry), {"username":"restaurant","bio":"Chicago restaurant"}, {"caption_text":"New menu"}, [])
    assert "SERVICE-PROSPECTING campaign" in prompt
    assert "Do NOT require industry_detected to equal marketing" in prompt


def test_marketing_prospect_is_not_discarded_just_because_industry_differs():
    s = InstagramProspectClassificationService(FakeAI(payload(industry_detected="food", business_vertical="FOOD")))
    ok, result = s.classify(53, campaign(), {"username":"chicago_restaurant","display_name":"Chicago Restaurant","bio":"Restaurant in Chicago. DM for reservations."}, {"caption_text":"Our new menu in Chicago."}, [])
    assert ok
    assert result["industry_target"] == "marketing"
    assert result["industry_detected"] == "food"
    assert result["skip_post"] is False
    assert result["engageable"] is True
    assert result["qualification_score"] >= 6


def test_marketing_agency_in_post_is_caught_as_competitor():
    s = InstagramProspectClassificationService(FakeAI(payload()))
    result = s.detect_obvious_competitor(
        campaign(),
        {"username":"weareclouise", "display_name":"C__LOUISE", "bio":""},
        {"caption_text":"C__LOUISE is a boutique PR, marketing, and social media agency helping brands."},
        [],
    )
    assert result is not None
    assert result["is_competitor"] is True
    assert result["skip_post"] is True
    assert result["competitor_relation"] == "DIRECT_COMPETITOR"


def test_invalid_browser_error_url_is_rejected():
    assert _normalize_instagram_href("chrome-error://chromewebdata/") == ""
    assert _normalize_instagram_href("javascript:void(0)") == ""
    assert _normalize_instagram_href("https://example.com/p/ABC/") == ""
    assert _extract_username_from_url("chrome-error://chromewebdata/") == ""


def test_marketing_prompt_does_not_load_legacy_spa_classifier():
    s = InstagramProspectClassificationService(FakeAI(payload()))
    prompt = s.build_prompt(
        campaign(),
        "marketing",
        s.load_competitor_rules("marketing"),
        {"username": "jva_services", "bio": "Window cleaning and pressure washing in Chicago"},
        {"caption_text": "Serving Chicago & surrounding areas"},
        [],
    )
    assert "spa, med spa, skincare" not in prompt.lower()
    assert "SERVICE-PROSPECTING campaign" in prompt
    assert "Restaurants, contractors, salons" in prompt


def test_marketing_ai_overconservative_skip_is_recovered_for_local_business():
    ai = FakeAI(payload(
        skip_post=True,
        mode="skip",
        selected_service="",
        competitor_relation="UNKNOWN",
        business_vertical="OTHER_SERVICE",
        profile_classification="LOCAL_BUSINESS_PAGE",
        business_role="COMPANY_PAGE",
        commercial_intent_score=85,
        location_match=True,
    ))
    s = InstagramProspectClassificationService(ai)
    ok, result = s.classify(
        53,
        campaign(),
        {
            "username": "jva_services",
            "display_name": "JVA SERVICES",
            "bio": "Window cleaning, junk removal, pressure washing. Serving Chicago & Surrounding Areas. Call or Text for Free Estimates.",
        },
        {"caption_text": "Free estimates for local customers in Chicago."},
        [],
    )
    assert ok
    assert result["skip_post"] is False
    assert result["qualification_score"] >= 8
    assert result["qualification_decision"] == "QUALIFIED"
    assert result["engageable"] is True
    assert result["selected_service"] == "social media management"


def test_marketing_service_request_is_not_deterministically_blacklisted():
    s = InstagramProspectClassificationService(FakeAI(payload()))
    result = s.detect_obvious_competitor(
        campaign(),
        {"username": "local_owner", "display_name": "Local Owner", "bio": "Small business owner in Chicago"},
        {"caption_text": "Looking for a digital marketing agency to help my business grow in Chicago."},
        [],
    )
    assert result is None


def test_real_bot_log_local_food_business_is_recovered_from_ai_industry_mismatch():
    # Mirrors the 2026-09-17 bot_log case: the AI called the profile BUSINESS,
    # detected food/catering, but incorrectly used UNRELATED_BUSINESS and scored
    # it 18 because the campaign target is marketing.
    ai = FakeAI(payload(
        profile_classification="BUSINESS",
        business_role="UNKNOWN",
        business_vertical="UNKNOWN",
        competitor_relation="UNRELATED_BUSINESS",
        commercial_intent_score=18,
        qualification_score=0,
        qualification_decision="DISCARDED",
        engageable=False,
        industry_detected="food & beverage / catering & baking",
        location_match=True,
        location_confidence="medium",
        location_evidence=["Chicago food business"],
        skip_post=True,
        mode="skip",
        selected_service="",
        comment="",
    ))
    s = InstagramProspectClassificationService(ai)
    ok, result = s.classify(
        53,
        campaign(),
        {
            "username": "tastebuddiaries",
            "display_name": "",
            "bio": "Photo by Erica | Chicago Food Expert",
        },
        {
            "caption_text": (
                "As a caterer and baker, I loved hearing about creativity. "
                "Food is truly my passion and the business of food."
            )
        },
        [
            {
                "caption_text": (
                    "Chicago food event. If you're a woman working in food "
                    "or beverage, DM me."
                )
            }
        ],
    )
    assert ok
    assert result["industry_target"] == "marketing"
    assert result["industry_detected"] == "food"
    assert result["business_vertical"] == "FOOD"
    assert result["competitor_relation"] == "UNKNOWN"
    assert result["is_competitor"] is False
    assert result["is_blacklisted"] is False
    assert result["skip_post"] is False
    assert result["selected_service"] == "social media management"
    assert result["commercial_intent_score"] >= 60
    assert result["qualification_score"] >= 6
    assert result["qualification_decision"] == "QUALIFIED"
    assert result["engageable"] is True
