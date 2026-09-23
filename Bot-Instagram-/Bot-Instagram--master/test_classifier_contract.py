"""Regression tests for the final Instagram classifier contract."""

from app.services.instagram_prospect_classification_service import (
    InstagramProspectClassificationService,
)


class Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class FakeAI:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get_bot_ia_long_prompt(self, bot_personality_id, prompt):
        self.calls += 1
        return True, {"response": self.payload}


def run():
    cases = [
        {
            "name": "industry cannot be replaced by AI unknown",
            "campaign": {
                "campaign_type": "marketing",
                "services_snapshot": ["Social Media Management", "Lead Generation"],
            },
            "payload": {
                "competitor_score": 10,
                "is_competitor": False,
                "is_blacklisted": False,
                "profile_classification": "LOCAL_BUSINESS_PAGE",
                "business_role": "COMPANY_PAGE",
                "business_vertical": "FOOD",
                "competitor_relation": "ADJACENT_LOCAL_SERVICE",
                "commercial_intent_score": 70,
                "classification_confidence": 90,
                "classification_evidence": ["Local restaurant"],
                "industry_detected": "unknown",
                "skip_post": False,
                "mode": "normal_prospecting",
                "selected_service": "Social Media Management",
                "b2b_confidence": "low",
                "request_directness": "indirect",
                "comment": "Relevant business post.",
            },
            "assertions": lambda result: (
                result["industry_target"] == "marketing"
                and result["industry_detected"] == "food"
                and result["selected_service"] == "Social Media Management"
                and result["skip_post"] is False
            ),
        },
        {
            "name": "industry-specific direct competitor alias",
            "campaign": {
                "campaign_type": "abogados",
                "services_snapshot": ["Legal Services"],
            },
            "payload": {
                "competitor_score": 80,
                "is_competitor": True,
                "is_blacklisted": True,
                "profile_classification": "LOCAL_BUSINESS_PAGE",
                "business_role": "COMPANY_PAGE",
                "business_vertical": "OTHER_SERVICE",
                "competitor_relation": "DIRECT_LEGAL_COMPETITOR",
                "commercial_intent_score": 100,
                "classification_confidence": 99,
                "classification_evidence": ["Law firm"],
                "industry_detected": "abogados",
            },
            "assertions": lambda result: (
                result["competitor_relation"] == "DIRECT_COMPETITOR"
                and result["is_blacklisted"] is True
                and result["skip_post"] is True
                and result["mode"] == "skip"
            ),
        },
        {
            "name": "geographic mismatch must be skipped",
            "campaign": {
                "campaign_type": "cleaning",
                "services_snapshot": ["Commercial Cleaning"],
                "strategy_snapshot": {"locations": ["Chicago, IL", "Chicago Metropolitan Area"]},
            },
            "payload": {
                "competitor_score": 0,
                "is_competitor": False,
                "is_blacklisted": False,
                "profile_classification": "LOCAL_BUSINESS_PAGE",
                "business_role": "COMPANY_PAGE",
                "business_vertical": "CONSTRUCTION",
                "competitor_relation": "ADJACENT_LOCAL_SERVICE",
                "commercial_intent_score": 30,
                "classification_confidence": 90,
                "classification_evidence": ["Business based in Granbury, Texas."],
                "industry_detected": "cleaning",
                "location_match": False,
                "location_confidence": "high",
                "location_evidence": ["Granbury, Texas is outside Chicago."],
                "skip_post": False,
                "mode": "b2b_referral",
                "selected_service": "Commercial Cleaning",
                "b2b_target_type": "contractor",
                "b2b_angle": "referral",
                "b2b_confidence": "low",
                "request_directness": "indirect",
                "comment": "Possible referral."
            },
            "assertions": lambda result: (
                result["location_match"] is False
                and result["skip_post"] is True
                and result["mode"] == "skip"
                and result["commercial_intent_score"] == 30
            ),
        },
        {
            "name": "geographic unknown must be skipped",
            "campaign": {
                "campaign_type": "cleaning",
                "services_snapshot": ["Commercial Cleaning"],
                "strategy_snapshot": {"locations": ["Chicago, IL"]},
            },
            "payload": {
                "competitor_score": 0,
                "is_competitor": False,
                "is_blacklisted": False,
                "profile_classification": "LOCAL_BUSINESS_PAGE",
                "business_role": "COMPANY_PAGE",
                "business_vertical": "OTHER_SERVICE",
                "competitor_relation": "ADJACENT_LOCAL_SERVICE",
                "commercial_intent_score": 70,
                "classification_confidence": 70,
                "classification_evidence": ["No reliable location evidence."],
                "industry_detected": "cleaning",
                "skip_post": True,
                "mode": "skip",
                "selected_service": "",
                "location_match": None,
                "location_confidence": "low",
                "location_evidence": [],
            },
            "assertions": lambda result: (
                result["location_match"] is None
                and result["skip_post"] is True
                and result["mode"] == "skip"
            ),
        },
        {
            "name": "explicit skip cannot be overwritten by mode",
            "campaign": {
                "campaign_type": "cleaning",
                "services_snapshot": ["Commercial Cleaning"],
            },
            "payload": {
                "competitor_score": 0,
                "is_competitor": False,
                "is_blacklisted": False,
                "profile_classification": "COMMON_PERSON",
                "business_role": "UNKNOWN",
                "business_vertical": "PERSONAL",
                "competitor_relation": "PERSONAL_PROFILE",
                "commercial_intent_score": 90,
                "classification_confidence": 95,
                "classification_evidence": ["Personal employee account."],
                "industry_detected": "cleaning",
                "skip_post": True,
                "mode": "normal_prospecting",
                "selected_service": "Commercial Cleaning",
            },
            "assertions": lambda result: (
                result["skip_post"] is True
                and result["mode"] == "skip"
                and result["skip_post"] is True
            ),
        },
        {
            "name": "empty locations means unrestricted",
            "campaign": {
                "campaign_type": "cleaning",
                "services_snapshot": ["Commercial Cleaning"],
                "strategy_snapshot": {"locations": []},
            },
            "payload": {
                "competitor_score": 0,
                "is_competitor": False,
                "is_blacklisted": False,
                "profile_classification": "LOCAL_BUSINESS_PAGE",
                "business_role": "COMPANY_PAGE",
                "business_vertical": "OTHER_SERVICE",
                "competitor_relation": "ADJACENT_LOCAL_SERVICE",
                "commercial_intent_score": 70,
                "classification_confidence": 90,
                "classification_evidence": ["Business profile."],
                "industry_detected": "cleaning",
                "skip_post": False,
                "mode": "normal_prospecting",
                "selected_service": "Commercial Cleaning",
                "comment": "Relevant business."
            },
            "assertions": lambda result: (
                result["location_match"] is True
                and result["skip_post"] is False
            ),
        },
    ]

    for case in cases:
        ai = FakeAI(__import__("json").dumps(case["payload"], ensure_ascii=False))
        service = InstagramProspectClassificationService(ai, Logger())
        ok, result = service.classify(
            bot_personality_id=7,
            campaign=case["campaign"],
            profile_context={"username": "test_profile", "bio": "test business"},
            post_context={"caption_text": "test post"},
            recent_posts=[],
        )
        assert ok, (case["name"], result)
        assert case["assertions"](result), (case["name"], result)

    print("✓ classifier contract regression tests: PASS")


if __name__ == "__main__":
    run()
