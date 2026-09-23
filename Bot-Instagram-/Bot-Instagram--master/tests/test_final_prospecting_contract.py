import json

from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)
from app.utils.instagram_url import (
    _normalize_instagram_href,
    _extract_username_from_url,
)


class FakeAI:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get_bot_ia_long_prompt(self, *_args):
        self.calls += 1
        return True, json.dumps(self.payload, ensure_ascii=False)


def payload(**overrides):
    data = {
        "competitor_score": 0,
        "is_competitor": False,
        "is_blacklisted": False,
        "blacklist_reason": "",
        "profile_classification": "BUSINESS",
        "business_role": "COMPANY_PAGE",
        "business_vertical": "REAL_ESTATE",
        "competitor_relation": "ADJACENT_LOCAL_SERVICE",
        "commercial_intent_score": 80,
        "classification_confidence": 90,
        "classification_evidence": ["Business is a real estate company."],
        "industry_detected": "real estate",
        "location_match": True,
        "location_confidence": "high",
        "location_evidence": ["Serving Chicago, IL"],
        "skip_post": False,
        "mode": "normal_prospecting",
        "selected_service": "property buying",
        "b2b_target_type": "",
        "b2b_angle": "",
        "b2b_confidence": "low",
        "request_directness": "indirect",
        "service_match_reason": "Real estate activity.",
        "comment": "Relevant business.",
    }
    data.update(overrides)
    return data


def campaign(**overrides):
    data = {
        "id": 1,
        "name": "Chicago Real Estate",
        "services_snapshot": ["residential real estate", "property buying"],
        "strategy_snapshot": {
            "hashtags": ["#ChicagoRealEstate", "#ChicagoRealEstate"],
            "locations": [],
        },
    }
    data.update(overrides)
    return data


def test_campaign_target_is_not_prospect_industry():
    ai = FakeAI(payload(industry_detected="construction", business_vertical="CONSTRUCTION"))
    service = InstagramProspectClassificationService(ai)
    ok, result = service.classify(
        1,
        campaign(),
        {"username": "builder", "bio": "General contractor"},
        {"caption_text": "Commercial construction project"},
        [],
    )
    assert ok
    assert result["industry_target"] == "real_estate"
    assert result["industry_detected"] == "construction"


def test_empty_locations_disable_geo_filter():
    ai = FakeAI(payload(industry_detected="real_estate"))
    service = InstagramProspectClassificationService(ai)
    ok, result = service.classify(
        1,
        campaign(),
        {"username": "maria", "bio": "Realtor"},
        {"caption_text": "Listing in Burlington"},
        [],
    )
    assert ok
    assert result["location_match"] is True


def test_hashtag_alone_is_not_location_proof():
    ai = FakeAI(payload(location_match=True, location_confidence="high",
                         location_evidence=["Hashtag #ChicagoContractor"]))
    service = InstagramProspectClassificationService(ai)
    ok, result = service.classify(
        1,
        campaign(
            name="Chicago Cleaning",
            industry_target="cleaning",
            services_snapshot=["deep cleaning"],
            strategy_snapshot={"locations": ["Chicago, IL"], "hashtags": []},
        ),
        {"username": "contractor", "bio": "General contractor"},
        {"caption_text": "#ChicagoContractor"},
        [],
    )
    assert ok
    assert result["location_match"] is None
    assert result["location_confidence"] == "low"
    assert result["skip_post"] is True


def test_explicit_outside_location_is_false():
    ai = FakeAI(payload(
        industry_detected="construction",
        business_vertical="CONSTRUCTION",
        selected_service="property buying",
        location_match=False,
        location_evidence=["Business operates in Fort Worth, Texas"],
    ))
    service = InstagramProspectClassificationService(ai)
    ok, result = service.classify(
        1,
        campaign(
            name="Chicago Cleaning",
            industry_target="cleaning",
            services_snapshot=["property buying"],
            strategy_snapshot={"locations": ["Chicago, IL"], "hashtags": []},
        ),
        {"username": "roofer", "bio": "Roofing contractor in Fort Worth, Texas"},
        {"caption_text": "Fort Worth project"},
        [],
    )
    assert ok
    assert result["location_match"] is False
    assert result["skip_post"] is True


def test_low_score_is_review_not_invalid():
    ai = FakeAI(payload(commercial_intent_score=40))
    service = InstagramProspectClassificationService(ai)
    ok, result = service.classify(
        1,
        campaign(),
        {"username": "maria", "bio": "Realtor serving Chicago"},
        {"caption_text": "Listing in Chicago"},
        [],
    )
    assert ok
    assert result["qualification_decision"] == "REVIEW"
    assert result["engageable"] is False
    assert result["skip_post"] is False


def test_url_normalization_deduplicates_reels():
    assert _normalize_instagram_href(
        "https://www.instagram.com/reels/ABC/?utm_source=x"
    ) == "https://www.instagram.com/reel/ABC/"
    assert _normalize_instagram_href(
        "https://www.instagram.com/foo/reels/ABC/"
    ) == "https://www.instagram.com/reel/ABC/"
    assert _extract_username_from_url(
        "https://www.instagram.com/Some_User/?utm_source=x"
    ) == "some_user"
