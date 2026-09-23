import json
from pathlib import Path

from app.services.instagram_conversation_flow_service import InstagramConversationFlowService

BASE = Path(__file__).parent / "app" / "utils" / "config" / "response_rules"
INDUSTRIES = ("abogados", "botanica", "cleaning", "fences", "marketing", "spa", "spa colombia")


def test_every_industry_has_source_response_rules():
    for industry in INDUSTRIES:
        for suffix in ("05_response_data_request", "06_response_quote_request"):
            data = json.loads((BASE / f"{industry}_{suffix}.json").read_text(encoding="utf-8"))
            assert data.get("trigger_keywords")
            assert data.get("rules")
            if suffix.startswith("06"):
                assert data.get("bot_question_flow")


def test_detect_quote_before_data_using_source_rules(tmp_path):
    svc = InstagramConversationFlowService(state_path=str(tmp_path / "flows.json"))
    for industry in INDUSTRIES:
        campaign = {"id": industry, "campaign_type": industry}
        assert svc.detect_request_type("price quote please", campaign) == "quote_request"


def test_data_request_uses_source_template(tmp_path):
    svc = InstagramConversationFlowService(state_path=str(tmp_path / "flows.json"))
    campaign = {"id": 1, "campaign_type": "fences", "follow_up_phone": "555-0100", "website": "https://example.com"}
    result = svc.handle(campaign, "alice", "send info")
    assert result["flow_type"] == "data_request"
    assert result["completed"] is True
    assert "555-0100" in result["reply"]


def test_quote_flow_stops_at_configured_minimum(tmp_path):
    svc = InstagramConversationFlowService(state_path=str(tmp_path / "flows.json"))
    campaign = {"id": 10, "campaign_type": "fences", "services_snapshot": ["fence installation"], "follow_up_phone": "123"}
    first = svc.handle(campaign, "alice", "I need a quote", "fence installation")
    assert first["completed"] is False
    second = svc.handle(campaign, "alice", "New fence installation", "fence installation")
    assert second["completed"] is False
    third = svc.handle(campaign, "alice", "I don't know", "fence installation")
    # Q1 + Q2 is the configured minimum for fences, so the handoff happens here.
    assert third["completed"] is True
    assert third["human_takeover"] is False
    assert third["alert_ready"] is True
    assert "123" in third["reply"]
    assert not svc.active(campaign, "alice")


def test_spa_conditional_questions_follow_source_rules(tmp_path):
    svc = InstagramConversationFlowService(state_path=str(tmp_path / "flows.json"))
    campaign = {"id": 12, "campaign_type": "spa", "services_snapshot": ["spa"]}
    first = svc.handle(campaign, "s", "How much does it cost?")
    assert first["flow_type"] == "quote_request"
    # Source SPA rules require Q1 first; optional Q2 is not asked unless a treatment was mentioned.
    assert "face" in first["reply"].lower()
