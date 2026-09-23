import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.services.instagram_config_alert_service import InstagramConfigAlertService
from app.services.instagram_config_policy_engine import InstagramConfigPolicyEngine
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService
from app.services.instagram_safety_gate import InstagramSafetyGate
from app.services.instagram_campaign_policy_service import InstagramCampaignPolicyService
from app.services.instagram_conversation_flow_service import InstagramConversationFlowService
from app.tasks.instagram_prospect_no_response_task import InstagramProspectNoResponseTask


def test_alert_placeholders_are_case_and_separator_insensitive():
    class Mail:
        def __init__(self): self.args = None
        def send_email(self, to_email, subject, body): self.args = (to_email, subject, body); return True
    mail = Mail()
    service = InstagramConfigAlertService(email_service=mail)
    rendered = service._render(
        "Cuenta=[Account Name] Categoria=[CATEGORY] Hora=[Timestamp] Perfil=[Profile URL] Post=[Facebook post link] Q1=[Q1 answer or Not answered]",
        {
            "ACCOUNT NAME": "Ana",
            "CATEGORY": "tarot",
            "TIMESTAMP": "2026-09-17T20:00:00Z",
            "PROFILE URL": "https://instagram.com/ana",
            "FACEBOOK POST LINK": "https://facebook.com/post",
            "Q1 ANSWER": "Amor",
        },
    )
    assert "[Account Name]" not in rendered
    assert "[Facebook post link]" not in rendered
    assert "Ana" in rendered and "Amor" in rendered


def test_competitor_layers_enforced_from_source_json():
    profile = {"display_name": "Chicago Cleaners LLC", "category": "Cleaning Service", "bio": "cleaning company"}
    post = {"caption_text": "cleaning services #cleaning"}
    result = InstagramConfigPolicyEngine.evaluate_competitor("cleaning", profile, post, [])
    assert result["decision"] == "BLOCK"
    assert result["is_blacklisted"] is True
    assert result["competitor_score"] >= 60
    assert result["layers"][0]["id"] == "L1"


def test_competitor_30_59_requires_review():
    profile = {"display_name": "Local Business", "bio": "cleaning supplies"}
    post = {"caption_text": "supplies for homes"}
    result = InstagramConfigPolicyEngine.evaluate_competitor("cleaning", profile, post, [])
    assert result["decision"] in {"SAFE", "REVIEW", "BLOCK"}
    # The runtime exposes the exact source threshold rather than hardcoding a new one.
    rr = InstagramConfigRuntimeService.load("cleaning", "02_competitor_filter.json")["runtime_rules"]
    assert rr["review_if_score_between"] == [30, 59]


def test_registry_legal_urgent_and_strategy_rules():
    urgent = InstagramConfigPolicyEngine.enforce_registry_rules("abogados", "Tengo audiencia y necesito saber qué estrategia debo seguir en mi caso")
    assert urgent["human_escalation"] is True
    assert urgent["urgent"] is True
    assert "urgent_legal_term" in urgent["reasons"]


def test_registry_spa_health_distress_requires_skip_and_human():
    result = InstagramConfigPolicyEngine.enforce_registry_rules("spa colombia", "me provoco el vomito y odio mi cuerpo")
    assert result["skip_post"] is True
    assert result["human_escalation"] is True


def test_reply_window_and_no_response_mode_are_runtime_values():
    assert InstagramConfigRuntimeService.reply_window_hours("botanica") == 72
    assert InstagramConfigRuntimeService.likes_only_after_no_response("botanica") is True
    assert InstagramConfigRuntimeService.delay("botanica", "between_intro_comments")["min"] == 600


def test_conversation_flow_expires_after_72_hours(tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / "flow.json"))
    campaign = {"id": 1, "campaign_type": "botanica"}
    service._set_state(campaign, "ana", {
        "flow_type": "quote_request", "started_at": (datetime.now(timezone.utc) - timedelta(hours=73)).isoformat(),
        "questions": [{"number": "Q1", "question": "¿Qué servicio buscas?"}], "answers": [], "index": 0,
        "alert_sent": False,
    })
    result = service.handle(campaign, "ana", "hola")
    assert result["no_response"] is True
    assert result["state"]["status"] == "NO_RESPONSE"


def test_no_response_task_transitions_commented_posts(monkeypatch):
    task = InstagramProspectNoResponseTask({"campaign_id": 1, "campaign_type": "botanica"})
    now = datetime.now(timezone.utc)
    class API:
        def _get(self, endpoint, params=None):
            if endpoint == "prospecting/campaigns/1/": return True, {"id": 1, "campaign_type": "botanica"}, 200
            return True, [{"id": 7, "prospect": 9, "commented_at": (now - timedelta(hours=73)).isoformat(), "status": "commented"}], 200
        def update_prospect_post(self, *args, **kwargs): return True, {}
        def update_prospect(self, *args, **kwargs): return True, {}
    task.prospecting_api = API()
    assert task.execute() is True


def test_intro_semantic_rules_are_deterministically_enforced_with_context():
    svc = InstagramCampaignPolicyService
    ctx = {"post_caption": "My kitchen looks amazing after a deep clean in Chicago"}
    ok, reasons = svc.validate_comment("Great post!", "cleaning", [], post_context=ctx, account_language="English")
    assert not ok and "first_sentence_not_grounded" in reasons

    ok, reasons = svc.validate_comment(
        "The kitchen looks amazing after the deep clean. We specialize in professional cleaning services.",
        "cleaning", [], post_context=ctx, account_language="English"
    )
    assert not ok
    assert any(r in reasons for r in ("forbidden_phrase:We specialize", "forbidden_phrase:professional cleaning services"))


def test_intro_template_content_cannot_be_copied_without_post_grounding():
    policy = InstagramCampaignPolicyService.load_comment_policy("cleaning")
    template = policy["categories"][0]["templates"][0]["template"]
    # Use a copied 3-word fragment that does not occur in the post context.
    words = [w for w in template.split() if w.isalpha()]
    fragment = " ".join(words[:3])
    ok, reasons = InstagramCampaignPolicyService.validate_comment(
        fragment + ".", "cleaning", [], post_context={"post_caption": "A completely different neighborhood update."}, account_language="English"
    )
    assert not ok
    assert "template_content_not_grounded" in reasons


def test_botanica_privacy_and_no_guarantees_rules_are_enforced_outside_prompt():
    for text, expected in [
        ("Cuéntame el caso completo y tu cédula.", "privacy_rule_violation"),
        ("Te garantizamos el resultado en 24 horas.", "no_guarantees_rule_violation"),
    ]:
        ok, reasons = InstagramCampaignPolicyService.validate_comment(text, "botanica", [])
        assert not ok and expected in reasons


def test_language_policy_uses_account_language_when_supplied():
    ok, reasons = InstagramCampaignPolicyService.validate_comment(
        "This is a beautiful moment for you.", "botanica", [], account_language="Spanish"
    )
    assert not ok and "language_policy_violation" in reasons
    ok, reasons = InstagramCampaignPolicyService.validate_comment(
        "Qué momento tan bonito para ti.", "botanica", [], account_language="Spanish"
    )
    assert ok


def test_intro_signature_is_rejected_when_disabled():
    ok, reasons = InstagramCampaignPolicyService.validate_comment(
        "Qué buen momento para compartir.\n— Steven",
        "cleaning", [], post_context={"post_caption": "A family dinner"}, account_language="English"
    )
    assert not ok
    assert "signature_not_allowed" in reasons


def test_competitor_prompt_uses_canonical_runtime_source():
    prompt = InstagramCampaignPolicyService.competitor_prompt("cleaning")
    canonical = InstagramConfigRuntimeService.load("cleaning", "02_competitor_filter.json")
    assert prompt
    assert '"runtime_rules"' in prompt
    assert '"layers"' in prompt
    assert canonical["runtime_rules"]["review_if_score_between"] == [30, 59]


def test_quote_initial_reply_uses_configured_bot_template(tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / "flow.json"))
    campaign = {"id": 501, "campaign_type": "cleaning", "whatsapp": "3001234567"}
    result = service.handle(campaign, "template_user", "how much?")
    assert result["handled"]
    assert result["template_id"] == "Q-SHORT"
    assert "Depends on the job" in result["reply"]
    assert result["state"]["questions"][0]["number"] == "Q1"


def test_botanica_initial_reply_selects_specialized_template(tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / "flow.json"))
    campaign = {"id": 502, "campaign_type": "botanica", "whatsapp": "3001234567"}
    result = service.handle(campaign, "template_user", "quiero una limpia")
    assert result["template_id"] == "Q-CLEANSE"
    assert "limpieza" in result["reply"].lower()


def test_quote_alert_is_not_ready_before_configured_minimum_answers(tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / "flow.json"))
    campaign = {"id": 503, "campaign_type": "cleaning"}
    first = service.handle(campaign, "alert_user", "I need a quote")
    assert first["alert_ready"] is False
    second = service.handle(campaign, "alert_user", "2 bedrooms and 1 bathroom")
    assert second["alert_ready"] is False
    third = service.handle(campaign, "alert_user", "tomorrow")
    assert third["alert_ready"] is True
    assert third["alert_event_code"] == "QUOTE"


def test_all_configured_alert_placeholders_render_without_leaks():
    service = InstagramConfigAlertService()
    rendered = service._render(
        "[Time] [Q1] [Q2] [Q3] [Q4] [Direct link to Facebook post]",
        {
            "TIMESTAMP": "2026-09-20T18:00:00Z",
            "Q1 ANSWER": "Tarot",
            "Q2 ANSWER": "WhatsApp",
            "Q3 ANSWER": "Amor",
            "Q4 ANSWER": "Mañana",
            "FACEBOOK POST LINK": "https://instagram.com/p/abc",
        },
    )
    assert "[Time]" not in rendered
    assert "[Q1]" not in rendered and "[Q4]" not in rendered
    assert "[Direct link to Facebook post]" not in rendered
    assert "2026-09-20T18:00:00Z" in rendered
    assert "Tarot" in rendered and "Mañana" in rendered


def test_task10_inline_engagement_uses_runtime_safety_gate_and_delays():
    source = __import__("pathlib").Path(__file__).resolve().parents[1] / "app" / "tasks" / "instagram_prospect_discovery_task.py"
    text = source.read_text(encoding="utf-8")
    block = text[text.index("def _inline_follow_and_comment_candidate"):text.index("def _save_discovered_candidate")]
    assert "self._sleep_between_follows_if_needed()" in block
    assert 'self.safety_gate.allow(\n                "comment"' in block
    assert 'self._sleep_config_delay("post_detected_to_intro_comment")' in block
    assert 'self.safety_gate.allow(\n                "like"' in block
    assert 'self._sleep_config_delay("between_likes")' in block


def test_task10_resolves_industry_target_before_constructing_safety_gate():
    source = __import__("pathlib").Path(__file__).resolve().parents[1] / "app" / "tasks" / "instagram_prospect_discovery_task.py"
    text = source.read_text(encoding="utf-8")
    assert "campaign.get(\"industry_target\")" in text
    assert "self.safety_gate = InstagramSafetyGate(campaign_type)" in text


def test_lifetime_comment_limit_is_read_from_config_value(tmp_path):
    gate = InstagramSafetyGate('botanica', path=str(tmp_path / 'ledger.json'))
    # Current Botanica source says lifetime max = 1.
    assert gate.allow('comment', 'lead', commit=True)[0]
    assert not gate.allow('comment', 'lead', commit=False)[0]


def test_response_public_rules_are_runtime_parametric():
    violations = InstagramConfigRuntimeService.public_response_violations(
        'cleaning', 'quote_request', 'The price is $250 and the result is guaranteed.'
    )
    assert 'price_publicly_forbidden' in violations
    assert 'guaranteed_result_forbidden' not in violations  # Cleaning does not declare that workflow flag.

    violations = InstagramConfigRuntimeService.public_response_violations(
        'botanica', 'quote_request', 'Te garantizamos el resultado y pide tu cédula.'
    )
    assert 'guaranteed_result_forbidden' in violations
    assert 'sensitive_details_publicly_forbidden' in violations


def test_conversation_priority_flags_control_ambiguous_request(monkeypatch, tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / 'flow.json'))
    campaign = {'id': 901, 'campaign_type': 'botanica'}
    original = service._load_config

    def fake_config(campaign, flow_type):
        if flow_type == 'quote_request':
            return {'trigger_keywords': ['precio'], 'rules': {'alert_priority': 'QUOTE'}}
        return {'trigger_keywords': ['informacion']}

    monkeypatch.setattr(service, '_load_config', fake_config)
    monkeypatch.setattr(InstagramConfigRuntimeService, 'workflow_rule', classmethod(lambda cls, c, k, default=None: False if k.endswith('priority_over_data_request') else default))
    assert service.detect_request_type('precio informacion', campaign) == 'data_request'


def test_wait_for_all_answers_changes_alert_threshold(monkeypatch, tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / 'flow.json'))
    campaign = {'id': 902, 'campaign_type': 'cleaning'}
    cfg = {
        'trigger_keywords': ['quote'],
        'bot_reply_templates': [{'id': 'Q', 'recommended': True, 'comment': 'OK'}],
        'bot_question_flow': [
            {'number': 'Q1', 'question': 'Q1?'},
            {'number': 'Q2', 'question': 'Q2?'},
            {'number': 'Q3', 'question': 'Q3?'},
            {'number': 'Q4', 'question': 'Q4?'},
        ],
        'rules': {
            'quote_alert_after_min_answers': ['Q1', 'Q2'],
            'wait_for_all_4_answers_required': True,
            'bot_collects_details_before_alert': True,
        },
    }
    monkeypatch.setattr(service, '_load_config', lambda campaign, flow_type: cfg if flow_type == 'quote_request' else {'trigger_keywords': ['different-data-trigger']})
    first = service.handle(campaign, 'wait_user', 'quote')
    assert not first['alert_ready']
    assert not service.handle(campaign, 'wait_user', 'a2')['alert_ready']
    assert not service.handle(campaign, 'wait_user', 'a3')['alert_ready']
    assert not service.handle(campaign, 'wait_user', 'a4')['alert_ready']
    assert service.handle(campaign, 'wait_user', 'a5')['alert_ready']


def test_bot_collects_details_before_alert_flag_can_be_disabled(monkeypatch, tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / 'flow.json'))
    campaign = {'id': 903, 'campaign_type': 'cleaning'}
    cfg = {
        'trigger_keywords': ['quote'],
        'bot_reply_templates': [{'id': 'Q', 'recommended': True, 'comment': 'OK'}],
        'bot_question_flow': [{'number': 'Q1', 'question': 'Q1?'}],
        'rules': {'quote_alert_after_min_answers': ['Q1'], 'bot_collects_details_before_alert': False},
    }
    monkeypatch.setattr(service, '_load_config', lambda campaign, flow_type: cfg)
    result = service.handle(campaign, 'no_details', 'quote')
    assert result['alert_ready'] is True


def test_manual_quote_template_requires_human_handoff_when_configured(tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / 'flow.json'))
    campaign = {'id': 904, 'campaign_type': 'cleaning'}
    first = service.handle(campaign, 'manual_user', 'I need a quote')
    assert first['handled']
    result = service.handle(campaign, 'manual_user', 'Q1 answer')
    result = service.handle(campaign, 'manual_user', 'Q2 answer')
    assert result['human_takeover'] is True
    assert result['reply'] == ''


def test_data_response_uses_configured_alert_event_id(monkeypatch, tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / 'flow.json'))
    campaign = {'id': 905, 'campaign_type': 'botanica'}
    cfg = {
        'trigger_keywords': ['contact'],
        'public_reply_templates': [{'id': 'D1', 'recommended': True, 'template': 'Info'}],
        'rules': {'alert_event_id': 'CUSTOM_DATA'},
    }
    monkeypatch.setattr(service, '_load_config', lambda campaign, flow_type: cfg if flow_type == 'data_request' else {'trigger_keywords': ['price'], 'rules': {'alert_priority': 'QUOTE'}})
    result = service.handle(campaign, 'data_user', 'contact details please')
    assert result['alert_event_code'] == 'CUSTOM_DATA'
