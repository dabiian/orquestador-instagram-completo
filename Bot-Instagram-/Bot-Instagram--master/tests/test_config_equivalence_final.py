import json
from pathlib import Path
from app.services.instagram_config_policy_engine import InstagramConfigPolicyEngine
from app.services.instagram_conversation_flow_service import InstagramConversationFlowService

ROOT=Path(__file__).resolve().parents[1]/'app'/'config'/'business_config'

def test_botanica_l2_review_category_is_not_safe():
    r=InstagramConfigPolicyEngine.evaluate_competitor('botanica', {'category':'Health/Beauty'}, {}, [])
    assert r['decision']=='REVIEW'
    assert r['competitor_score']==35

def test_botanica_l4_single_mystic_post_with_cta_blocks():
    r=InstagramConfigPolicyEngine.evaluate_competitor('botanica', {}, {'caption_text':'Agenda tu lectura de tarot'}, [])
    assert r['decision']=='BLOCK'
    assert r['competitor_score']>=60

def test_botanica_l5_requires_thematic_context():
    r=InstagramConfigPolicyEngine.evaluate_competitor('botanica', {}, {'hashtags':['#Tarot','#Horoscopo']}, [])
    assert r['decision']!='BLOCK'

def test_botanica_l5_blocks_with_context():
    r=InstagramConfigPolicyEngine.evaluate_competitor('botanica', {'bio':'Tarot y astrologia'}, {'hashtags':['#Tarot','#Horoscopo']}, [])
    assert r['decision']=='BLOCK'

def test_short_positive_is_d2():
    s=InstagramConversationFlowService(state_path='/tmp/instagram_flow_equiv_test.json')
    c={'id':99,'campaign_type':'botanica','whatsapp':'3001234567'}
    r=s.handle(c,'user_equiv','quiero saber')
    assert r['handled'] and r['flow_type']=='data_request'
    assert r['template_id']=='D2'
    assert 'WhatsApp' in r['reply']

def test_d3_declares_required_followup_dm():
    s=InstagramConversationFlowService(state_path='/tmp/instagram_flow_equiv_test2.json')
    c={'id':100,'campaign_type':'botanica','whatsapp':'3001234567'}
    r=s.handle(c,'user_equiv','por privado')
    assert r['template_id']=='D3'
    assert r['dm_follow_up'] is True
    assert r['dm_follow_up_text']

def test_all_source_jsons_load_from_single_runtime_tree():
    for industry in [p.name for p in ROOT.iterdir() if p.is_dir()]:
        assert (ROOT/industry/'02_competitor_filter.json').exists()
        assert (ROOT/industry/'05_response_data_request.json').exists()
        assert (ROOT/industry/'06_response_quote_request.json').exists()

def test_botanica_l3_single_mystic_identity_keyword_blocks_from_source_rule():
    r = InstagramConfigPolicyEngine.evaluate_competitor(
        'botanica', {'bio': 'Maestro espiritual'}, {}, []
    )
    assert r['decision'] == 'BLOCK'
    assert r['competitor_score'] >= 60
    l3 = next(x for x in r['layers'] if x['id'] == 'L3')
    assert 'maestro espiritual' in l3['mystic_identity_hits']


def test_botanica_l3_single_generic_keyword_still_uses_generic_threshold():
    r = InstagramConfigPolicyEngine.evaluate_competitor(
        'botanica', {'bio': 'contenido espiritual'}, {}, []
    )
    assert r['decision'] == 'REVIEW'
    assert r['competitor_score'] == 40
