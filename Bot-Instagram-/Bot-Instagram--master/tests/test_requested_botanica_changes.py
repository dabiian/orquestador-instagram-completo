import json

from app.api.prospecting_api import ProspectingAPI
from app.services.instagram_prospect_classification_service import InstagramProspectClassificationService


class FakeAI:
    def __init__(self, payload):
        self.payload = payload

    def get_bot_ia_long_prompt(self, *_args):
        return True, json.dumps(self.payload, ensure_ascii=False)


def _payload(industry_detected="real_estate"):
    return {
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
        "classification_evidence": ["Business profile evidence."],
        "industry_detected": industry_detected,
        "location_match": True,
        "location_confidence": "high",
        "location_evidence": ["Business evidence."],
        "skip_post": False,
        "mode": "normal_prospecting",
        "selected_service": "spiritual products",
        "b2b_target_type": "",
        "b2b_angle": "",
        "b2b_confidence": "low",
        "request_directness": "indirect",
        "service_match_reason": "Relevant.",
        "comment": "Relevant business.",
    }


def test_botanica_campaign_without_explicit_industry_does_not_fall_back_to_cleaning():
    service = InstagramProspectClassificationService(FakeAI(_payload()))
    campaign = {
        "id": 4,
        "name": "botanica",
        "services_snapshot": [
            "botanica", "spiritual products", "spiritual supplies",
            "herbal products", "ritual products", "religious supplies",
            "spiritual consultations",
        ],
    }
    assert service.detect_campaign_industry(campaign) == "botanica"


def test_industry_detected_prompt_example_is_neutral():
    service = InstagramProspectClassificationService(FakeAI(_payload()))
    prompt = service.build_prompt(
        {"name": "botanica", "services_snapshot": ["botanica"]},
        "botanica",
        {},
        {},
        {},
        [],
    )
    assert '"industry_detected": "UNKNOWN"' in prompt
    assert '"industry_detected": "botanica"' not in prompt
    assert '"industry_detected": "cleaning"' not in prompt


def test_existing_prospect_with_zero_score_is_patched():
    api = object.__new__(ProspectingAPI)
    captured = {}

    api.find_prospect_by_username = lambda **kwargs: (True, {"id": 76, "qualification_score": 0})

    def fake_patch(endpoint, payload, timeout=30):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return True, {"id": 76, **payload}

    api._patch = fake_patch
    ok, data, created = api.get_or_create_prospect(
        campaign_id=4,
        platform="instagram",
        username="orlando",
        profile_url="https://www.instagram.com/orlando/",
        industry_detected="real_estate",
        qualification_score=8,
        qualification_reason="Updated classification.",
    )

    assert ok is True
    assert created is False
    assert captured["endpoint"] == "prospecting/prospects/76/"
    assert captured["payload"]["qualification_score"] == 8
    assert captured["payload"]["industry_detected"] == "real_estate"
    assert data["id"] == 76
