import json
from pathlib import Path

from app.api.prospecting_api import _normalize_qualification_score
from app.services.instagram_prospect_classification_service import InstagramProspectClassificationService


class FakeAI:
    def __init__(self, payload): self.payload = payload
    def get_bot_ia_long_prompt(self, *_args): return True, json.dumps(self.payload, ensure_ascii=False)


def base_payload(**overrides):
    p={
      "competitor_score":0,"is_competitor":False,"is_blacklisted":False,"blacklist_reason":"",
      "profile_classification":"UNKNOWN","business_role":"UNKNOWN","business_vertical":"REAL_ESTATE",
      "competitor_relation":"ADJACENT_LOCAL_SERVICE","commercial_intent_score":68,"classification_confidence":90,
      "classification_evidence":["Business evidence"],"industry_detected":"mortgage lending",
      "location_match":True,"location_confidence":"high","location_evidence":["Serving Chicago, IL"],
      "skip_post":False,"mode":"b2b_referral","selected_service":"property buying",
      "b2b_target_type":"mortgage_lender","b2b_angle":"partnership","b2b_confidence":"high",
      "request_directness":"indirect","service_match_reason":"Relevant","comment":"Relevant"
    }; p.update(overrides); return p


def campaign(**overrides):
    p={"id":1,"name":"Chicago Real Estate","industry_target":"real_estate","services_snapshot":["property buying"],"strategy_snapshot":{"locations":["Chicago, IL"],"hashtags":[]}}; p.update(overrides); return p


def test_score_is_backend_integer():
    assert _normalize_qualification_score(6.8) == 7
    assert _normalize_qualification_score("6.8") == 7
    assert _normalize_qualification_score(100) == 10


def test_real_estate_rules_exist():
    path=Path(__file__).resolve().parents[1]/"app/utils/config/real_estate/02_competitor_filter.json"
    assert path.exists()
    data=json.loads(path.read_text(encoding="utf-8"))
    assert data["industry"] == "real_estate"


def test_unknown_business_profile_is_resolved_from_evidence():
    s=InstagramProspectClassificationService(FakeAI(base_payload()))
    ok,r=s.classify(1,campaign(),{"username":"klopasstrattonrealestate","bio":"Real estate team serving Chicago"},{"caption_text":"Chicago listing"},[])
    assert ok
    assert r["profile_classification"] == "BUSINESS"
    assert r["business_role"] == "REALTOR"
    assert r["industry_target"] == "real_estate"
    assert r["industry_detected"] == "real_estate"
    assert isinstance(r["qualification_score"], int)


def test_target_and_detected_remain_separate():
    s=InstagramProspectClassificationService(FakeAI(base_payload(industry_detected="construction",business_vertical="CONSTRUCTION")))
    ok,r=s.classify(1,campaign(),{"username":"builder","bio":"General contractor"},{"caption_text":"Construction"},[])
    assert ok
    assert r["industry_target"] == "real_estate"
    assert r["industry_detected"] == "construction"


def test_empty_locations_are_unrestricted():
    s=InstagramProspectClassificationService(FakeAI(base_payload(location_match=False,location_confidence="low",location_evidence=[])))
    ok,r=s.classify(1,campaign(strategy_snapshot={"locations":[],"hashtags":[]}),{"username":"business","bio":"Company"},{"caption_text":"Project"},[])
    assert ok and r["location_match"] is True


def test_hashtag_is_not_location_proof():
    s=InstagramProspectClassificationService(FakeAI(base_payload(location_match=True,location_confidence="high",location_evidence=["Hashtag #ChicagoContractor"])))
    ok,r=s.classify(1,campaign(),{"username":"contractor","bio":"General contractor"},{"caption_text":"#ChicagoContractor"},[])
    assert ok and r["location_match"] is None and r["location_confidence"] == "low" and r["skip_post"] is True


def test_location_normalization_handles_state_and_metro_variants():
    s=InstagramProspectClassificationService(FakeAI(base_payload()))
    assert s._location_terms("Chicago, Illinois")[:2] == ["chicago illinois", "chicago"]
    assert "chicago" in s._location_terms("Chicago Metropolitan Area")
    assert "dallas fort worth" in s._location_terms("Dallas-Fort Worth Metroplex")


def test_explicit_ai_location_mismatch_is_preserved():
    s=InstagramProspectClassificationService(FakeAI(base_payload(location_match=False, location_evidence=["Business operates in Springfield, Illinois"])))
    ok,r=s.classify(1,campaign(),{"username":"business","bio":"Business in Springfield, Illinois"},{"caption_text":"Springfield project"},[])
    assert ok and r["location_match"] is False and r["skip_post"] is True


def test_api_create_normalizes_backend_score(monkeypatch):
    from app.api.prospecting_api import ProspectingAPI
    api=object.__new__(ProspectingAPI)
    captured={}
    def fake_post(endpoint, payload, timeout=30):
        captured["payload"]=payload
        return True, {"id":1}
    api._post=fake_post
    ok,data=api.create_prospect(1,"instagram","user","https://www.instagram.com/user/",qualification_score=6.8)
    assert ok and captured["payload"]["qualification_score"] == 7
