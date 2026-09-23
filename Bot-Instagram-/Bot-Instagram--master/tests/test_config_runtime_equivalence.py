import json
from pathlib import Path
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService
from app.services.instagram_config_alert_service import InstagramConfigAlertService
from app.services.instagram_conversation_flow_service import InstagramConversationFlowService
from app.services.instagram_safety_gate import InstagramSafetyGate

INDUSTRIES = ['abogados','botanica','cleaning','fences','marketing','spa','spa colombia']
ROOT = Path(__file__).resolve().parents[1] / 'app' / 'config' / 'business_config'

def test_all_source_response_configs_are_runtime_loadable():
    for ind in INDUSTRIES:
        for name in ('05_response_data_request.json','06_response_quote_request.json'):
            assert (ROOT/ind/name).exists(), (ind,name)
            assert InstagramConfigRuntimeService.load(ind,name)
    assert InstagramConfigRuntimeService.alerts('botanica')
    for ind in INDUSTRIES:
        if ind != 'botanica':
            assert InstagramConfigRuntimeService.alerts(ind) == {}

def test_runtime_preserves_botanica_workflow_and_schema_contract():
    app=InstagramConfigRuntimeService.app_config('botanica')
    wf=InstagramConfigRuntimeService.workflow('botanica')
    schema=InstagramConfigRuntimeService.database_schema('botanica')
    assert app['workflow']['human_takeover_stops_bot'] is True
    assert app['workflow']['reply_window_hours'] == 72
    assert wf['main_flow']
    assert {x['name'] for x in schema['tables']} >= {'prospects','prospect_comments','alerts_log','config_snapshots'}

def test_conversation_service_human_takeover_blocks_future_bot_reply(tmp_path):
    service=InstagramConversationFlowService(state_path=str(tmp_path/'state.json'))
    campaign={'id':1,'campaign_type':'botanica','phone':'555'}
    first=service.handle(campaign,'lead','quiero precio de una lectura')
    assert first['handled'] and not first['completed']
    state=first['state']; qs=state['questions']
    # The source rule says the alert/takeover threshold is Q1+Q2, not all Q4.
    result=service.handle(campaign,'lead','respuesta 1')
    assert result and not result['alert_ready']
    result=service.handle(campaign,'lead','respuesta 2')
    assert result and result['completed'] and result['human_takeover'] and result['alert_ready']
    blocked=service.handle(campaign,'lead','quiero agregar algo')
    assert blocked['human_takeover'] and blocked['reply']==''

def test_alert_service_uses_config_event_and_independent_channels(monkeypatch):
    sent=[]
    class Email:
        def send_email(self,to_email,subject,body): sent.append(('email',to_email,subject,body)); return True
    svc=InstagramConfigAlertService(email_service=Email(), whatsapp_sender=lambda to,msg: sent.append(('wa',to,msg)) or True)
    out=svc.send('botanica','QUOTE',{'ACCOUNT NAME':'lead','CATEGORY':'tarot','EXACT REPLY TEXT':'precio?','Q1 ANSWER':'tarot','Q2 ANSWER':'WhatsApp','Q3 ANSWER':'general','Q4 ANSWER':'hoy','FACEBOOK POST LINK':'https://example.test','CAMPAIGN EMAIL':'owner@example.test','ALERT WHATSAPP':'3000000000'})
    assert out['email_sent'] and out['whatsapp_sent'] and out['ok']
    assert {x[0] for x in sent}=={'email','wa'}

def test_safety_gate_enforces_config_limits(tmp_path):
    gate=InstagramSafetyGate('botanica', path=str(tmp_path/'ledger.json'))
    # First comment for account is allowed, second is blocked by lifetime rule.
    assert gate.allow('comment','lead',commit=True)[0]
    assert not gate.allow('comment','lead',commit=False)[0]

def test_runtime_config_matches_embedded_source_manifest():
    import hashlib
    manifest=json.loads((Path(__file__).resolve().parent/'config_source_sha256.json').read_text(encoding='utf-8'))
    runtime=Path(__file__).resolve().parents[1]/'app'/'config'/'business_config'
    actual={str(p.relative_to(runtime)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(runtime.rglob('*.json'))}
    assert actual == manifest
    assert len(actual) == 41

def test_registry_specific_safety_rules_are_runtime_enforced():
    assert 'legal_advice' in InstagramConfigRuntimeService.forbidden_public_content('abogados','Mi consejo legal es que debes demandar ahora.')
    assert 'medical_diagnosis' in InstagramConfigRuntimeService.forbidden_public_content('spa colombia','Tienes cáncer y debes hacer este tratamiento.')

def test_schema_is_runtime_addressable():
    from app.services.instagram_config_runtime_service import InstagramConfigSchemaValidator
    assert 'alerts_log' in InstagramConfigSchemaValidator.required_tables('botanica')
    ok, unknown=InstagramConfigSchemaValidator.validate_table_payload('botanica','alerts_log',{'event_code':'QUOTE','priority':1})
    assert ok and unknown==[]


def test_safety_gate_enforces_weekly_like_per_account(tmp_path):
    gate=InstagramSafetyGate('botanica', path=str(tmp_path/'ledger.json'))
    for _ in range(3):
        assert gate.allow('like','lead',commit=True)[0]
    assert not gate.allow('like','lead',commit=False)[0]


def test_missing_optional_config_is_not_invented():
    assert InstagramConfigRuntimeService.app_config('cleaning') == {}
    assert InstagramConfigRuntimeService.workflow('cleaning') == {}
    assert InstagramConfigRuntimeService.database_schema('cleaning') == {}


def test_alert_priority_is_read_from_response_config_not_inferred_from_flow_name(tmp_path):
    service = InstagramConversationFlowService(state_path=str(tmp_path / 'state.json'))
    campaign = {'id': 312, 'campaign_type': 'spa', 'phone': '555'}

    first = service.handle(campaign, 'lead', 'quiero precio de un tratamiento')
    assert first['handled'] and not first['completed']

    # SPA declares CONSULTATION even though the runtime flow is quote_request.
    result = service.handle(campaign, 'lead', 'ambos')
    assert result['completed']
    assert result['alert_ready'] is True
    assert result['alert_event_code'] == 'QUOTE'
    assert result['alert_priority'] == 'CONSULTATION'
    assert result['state']['alert_priority'] == 'CONSULTATION'


def test_alert_priority_falls_back_only_when_config_does_not_declare_one():
    assert InstagramConfigRuntimeService.alert_priority('cleaning', 'quote_request') == 'QUOTE'
    assert InstagramConfigRuntimeService.alert_priority('spa', 'service_request') == 'CONSULTATION'


def test_botanica_rejects_absolute_power_claims_from_config_safety_rule():
    blocked = InstagramConfigRuntimeService.forbidden_public_content(
        'botanica',
        'Tengo poderes absolutos y puedo asegurar tu resultado.',
    )
    assert 'absolute_powers' in blocked


def test_botanica_allows_orientation_language_without_absolute_power_claim():
    allowed = InstagramConfigRuntimeService.forbidden_public_content(
        'botanica',
        'Puedo orientarte y acompañarte en una consulta espiritual.',
    )
    assert 'absolute_powers' not in allowed

def test_classifier_competitor_prompt_source_is_canonical_business_config():
    from app.services.instagram_prospect_classification_service import InstagramProspectClassificationService
    service = object.__new__(InstagramProspectClassificationService)
    for industry in ('abogados', 'botanica', 'cleaning', 'fences', 'marketing', 'spa', 'spa colombia'):
        loaded = service.load_competitor_rules(industry)
        canonical = InstagramConfigRuntimeService.load(industry, '02_competitor_filter.json')
        assert loaded == canonical
        assert 'layers' in loaded
        assert 'runtime_rules' in loaded


def test_auto_reply_limit_is_enforced_by_safety_gate(tmp_path):
    gate = InstagramSafetyGate('botanica', path=str(tmp_path / 'ledger.json'))
    # Botanica currently declares null, meaning unlimited; verify the action is
    # still routed through the same config-backed limiter without a hardcoded cap.
    for _ in range(3):
        assert gate.allow('auto_reply', 'lead', commit=True)[0]
