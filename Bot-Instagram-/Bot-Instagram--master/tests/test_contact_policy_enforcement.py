import pytest

from app.services.instagram_conversation_flow_service import InstagramConversationFlowService
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService


@pytest.fixture
def service(tmp_path):
    return InstagramConversationFlowService(state_path=str(tmp_path / "flows.json"))


def campaign(industry: str) -> dict:
    return {
        "id": 9001,
        "campaign_type": industry,
        "follow_up_phone": "312-555-0100",
        "website": "https://example.test",
        "whatsapp": "312-555-0100",
    }


def render_d1(service, industry, incoming):
    cfg = service._load_config(campaign(industry), "data_request")
    d1 = next(x for x in cfg["public_reply_templates"] if x["id"] == "D1")
    return service._render_template(d1["template"], campaign(industry), cfg=cfg, incoming=incoming)


def test_cleaning_hides_private_cell_for_generic_info_request(service):
    reply = render_d1(service, "cleaning", "Can you send me more info?")
    assert "773-349-7935" not in reply
    assert "Cell (call or text)" not in reply
    assert "call or text the cell" not in reply.lower()
    assert "312-555-0100" in reply
    assert "Office (call)" in reply


def test_cleaning_reveals_private_cell_only_for_explicit_text_request(service):
    for incoming in (
        "Can I text you?",
        "Can you text me?",
        "Do you accept SMS?",
        "¿Puedo mandar un mensaje de texto?",
        "¿Me pueden contactar por texto?",
    ):
        reply = render_d1(service, "cleaning", incoming)
        assert "773-349-7935" in reply
        assert "Cell (call or text)" in reply
    assert "Feel free to call or text the cell" in reply


def test_cleaning_dm_request_does_not_unlock_cell_without_text_request(service):
    reply = render_d1(service, "cleaning", "DM me please")
    assert "773-349-7935" not in reply
    assert "Cell (call or text)" not in reply


def test_cleaning_handle_explicit_text_request_is_data_flow(service):
    result = service.handle(campaign("cleaning"), "prospect", "Can I text you?")
    assert result["flow_type"] == "data_request"
    assert "773-349-7935" in result["reply"]
    assert "312-555-0100" in result["reply"]


def test_cleaning_handle_generic_info_hides_private_cell(service):
    result = service.handle(campaign("cleaning"), "prospect", "I need information")
    assert result["flow_type"] == "data_request"
    assert "773-349-7935" not in result["reply"]
    assert "312-555-0100" in result["reply"]


def test_spa_never_exposes_private_owner_cell(service):
    cfg = service._load_config(campaign("spa"), "data_request")
    assert cfg["rules"]["cell_reveal_policy"] == "never_reveal_private_owner_cell_publicly_use_campaign_phone_or_dm_only"
    reply = render_d1(service, "spa", "Can I text you?")
    assert "312-555-0100" in reply
    assert "cell" not in reply.lower()


def test_spa_dm_stays_on_campaign_phone(service):
    result = service.handle(campaign("spa"), "prospect", "DM me")
    assert result["flow_type"] == "data_request"
    assert result["dm_follow_up"] is True
    assert "312-555-0100" in result["dm_follow_up_text"]
    assert "cell" not in result["dm_follow_up_text"].lower()


@pytest.mark.parametrize("industry", ["spa colombia", "abogados"])
def test_business_whatsapp_policy_allows_configured_business_contact(service, industry):
    cfg = service._load_config(campaign(industry), "data_request")
    assert cfg["rules"]["cell_reveal_policy"] == "business_whatsapp_can_be_shared_publicly"
    reply = render_d1(service, industry, "I need information")
    # These source templates contain the business WhatsApp number directly;
    # the policy explicitly permits it to remain public.
    assert any(ch.isdigit() for ch in reply)


def test_marketing_policy_does_not_require_private_cell_removal(service):
    cfg = service._load_config(campaign("marketing"), "data_request")
    assert cfg["rules"]["cell_reveal_policy"].startswith("no_private_cell_available")
    reply = render_d1(service, "marketing", "send info")
    assert "Free SEO Audit" in reply
    assert "312-555-0100" not in reply or "888-315-2721" in reply


def test_fences_conditional_policy_is_safe_when_template_has_no_cell(service):
    cfg = service._load_config(campaign("fences"), "data_request")
    assert cfg["rules"]["cell_reveal_policy"] == "reveal_cell_only_if_prospect_explicitly_requests_text_or_sms"
    normal = render_d1(service, "fences", "send info")
    explicit = render_d1(service, "fences", "Can I text you?")
    assert normal == explicit
    assert "312-555-0100" in normal


def test_office_phone_sms_flag_is_enforced_for_call_only_policy(service):
    cfg = service._load_config(campaign("cleaning"), "data_request")
    text = service._render_template(
        "Call or text: [CAMPAIGN PHONE NUMBER]",
        campaign("cleaning"),
        cfg=cfg,
        incoming="I need information",
    )
    assert text == "Call: 312-555-0100"


def test_explicit_sms_detection_does_not_treat_instagram_dm_as_sms():
    cases = {
        "DM me": False,
        "Message me": False,
        "Inbox me": False,
        "Can I text you?": True,
        "Please send an SMS": True,
        "¿Puedo enviar un mensaje de texto?": True,
    }
    for text, expected in cases.items():
        assert InstagramConversationFlowService._explicit_text_or_sms_request(text) is expected


def test_runtime_contact_policies_are_loaded_for_industries_that_declare_them(service):
    industries = ["spa", "cleaning", "spa colombia", "abogados", "marketing", "fences"]
    for industry in industries:
        cfg = InstagramConfigRuntimeService.response(industry, "data_request")
        rules = cfg.get("rules") or {}
        assert "cell_reveal_policy" in rules
        assert "office_phone_sms_allowed" in rules


def test_botanica_without_contact_policy_keeps_existing_contact_template_behavior(service):
    cfg = InstagramConfigRuntimeService.response("botanica", "data_request")
    assert "cell_reveal_policy" not in (cfg.get("rules") or {})
    reply = render_d1(service, "botanica", "info")
    assert "312-555-0100" in reply
