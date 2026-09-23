from __future__ import annotations
import json, os, re
from pathlib import Path
from typing import Any
from app.config.industry_prompt_rules import normalize_campaign_type

class InstagramConfigRuntimeService:
    """Single runtime adapter for the supplied campaign JSON configuration."""
    ROOT = Path(__file__).resolve().parents[1] / 'config' / 'business_config'

    @classmethod
    def campaign(cls, campaign_type: str) -> str:
        return normalize_campaign_type(campaign_type or '')

    @classmethod
    def load(cls, campaign_type: str, filename: str) -> dict:
        key = cls.campaign(campaign_type)
        path = cls.ROOT / key / filename
        if not path.exists() and key == 'spa_colombia':
            path = cls.ROOT / 'spa colombia' / filename
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @classmethod
    def response(cls, campaign_type: str, flow_type: str) -> dict:
        suffix = '05_response_data_request.json' if flow_type == 'data_request' else '06_response_quote_request.json'
        return cls.load(campaign_type, suffix)

    @classmethod
    def app_config(cls, campaign_type: str) -> dict:
        return cls.load(campaign_type, '00_app_config.json')

    @classmethod
    def workflow(cls, campaign_type: str) -> dict:
        return cls.load(campaign_type, '01_workflow.json')

    @classmethod
    def registry(cls, campaign_type: str) -> dict:
        key = cls.campaign(campaign_type)
        if key == 'abogados':
            return cls.load(key, '01_prospect_registry_lopez_lopez_abogados.json')
        if key == 'spa colombia' or key == 'spa_colombia':
            return cls.load('spa colombia', '01_prospect_registry_dra_deysi_torres.json')
        return cls.load(key, '01_prospect_registry.json')

    @classmethod
    def alerts(cls, campaign_type: str) -> dict:
        return cls.load(campaign_type, '07_alerts.json')

    @classmethod
    def database_schema(cls, campaign_type: str) -> dict:
        return cls.load(campaign_type, '08_database_schema.json')

    @classmethod
    def safety(cls, campaign_type: str) -> dict:
        app = cls.app_config(campaign_type)
        return app.get('safety_limits') or {}

    @classmethod
    def workflow_rules(cls, campaign_type: str) -> dict:
        app = cls.app_config(campaign_type)
        return app.get('workflow') or {}

    @classmethod
    def runtime_rules(cls, campaign_type: str) -> dict:
        reg = cls.registry(campaign_type)
        return reg.get('runtime_rules') or {}

    @classmethod
    def is_human_takeover(cls, state: dict | None) -> bool:
        return bool((state or {}).get('human_takeover'))

    @classmethod
    def forbidden_public_content(cls, campaign_type: str, text: str) -> list[str]:
        t = str(text or '').lower()
        reasons=[]
        rr = cls.runtime_rules(campaign_type)
        if rr.get('never_give_legal_advice') and any(x in t for x in ('debes demandar','haz esto legalmente','mi consejo legal','te recomiendo demandar')):
            reasons.append('legal_advice')
        if rr.get('never_request_sensitive_case_details_publicly') and any(x in t for x in ('cédula','cedula','número de expediente','expediente completo','contraseña')):
            reasons.append('sensitive_case_details')
        if rr.get('never_give_medical_advice') and any(x in t for x in ('toma esta dosis','suspende el medicamento','te recomiendo este tratamiento')):
            reasons.append('medical_advice')
        if rr.get('never_diagnose_publicly') and any(x in t for x in ('tienes cáncer','tienes cancer','estás embarazada','estas embarazada','tienes depresión','tienes depresion')):
            reasons.append('medical_diagnosis')
        if rr.get('never_comment_on_negative_body_image_posts') and any(x in t for x in ('eres gorda','eres gordo','tu cuerpo está mal','tu cuerpo esta mal','deberías bajar de peso','deberias bajar de peso')):
            reasons.append('negative_body_image')
        rules = cls.safety(campaign_type).get('content_safety_rules') or []
        for rule in rules:
            # Turn declarative config statements into conservative phrase gates.
            r = str(rule).lower()
            if 'no afirmar poderes absolutos' in r:
                absolute_power_patterns = (
                    r'\btengo\s+poderes\s+absolutos?\b',
                    r'\bposeo\s+poderes\s+absolutos?\b',
                    r'\bposeo\s+poderes\b',
                    r'\bpuedo\s+controlar\s+(?:tu|el|la|los|las)\b',
                    r'\bpuedo\s+hacer\s+que\s+(?:tu|el|la|los|las)\b',
                    r'\bpuedo\s+determinar\s+con\s+certeza\b',
                    r'\bpuedo\s+asegurar\s+(?:tu|el|la|los|las)\b',
                )
                if any(re.search(pattern, t, flags=re.IGNORECASE) for pattern in absolute_power_patterns):
                    reasons.append('absolute_powers')
            if 'no prometer resultados' in r and any(x in t for x in ('garantizo','garantizado','resultado seguro','100% seguro')):
                reasons.append('guaranteed_result')
            if 'no usar miedo' in r and any(x in t for x in ('si no haces','te va a pasar','maldición','amenaza')):
                reasons.append('fear_pressure')
            if 'no pedir datos íntimos' in r and any(x in t for x in ('documento','cédula','contraseña','número de cuenta')):
                reasons.append('sensitive_public_data')
            if 'no diagnosticar' in r and any(x in t for x in ('te diagnostico','tienes cáncer','estás embarazada','tienes depresión')):
                reasons.append('diagnosis')
        return sorted(set(reasons))

    @classmethod
    def limits(cls, campaign_type: str) -> dict:
        return cls.safety(campaign_type).get('daily_limits') or {}

    @classmethod
    def delay(cls, campaign_type: str, action: str) -> dict:
        return (cls.safety(campaign_type).get('delays_seconds') or {}).get(action) or {}

    @classmethod
    def workflow_value(cls, campaign_type: str, key: str, default=None):
        app = cls.app_config(campaign_type)
        value = (app.get('workflow') or {}).get(key, default)
        if value is default:
            value = (cls.workflow(campaign_type).get('workflow') or {}).get(key, default)
        return value

    @classmethod
    def reply_window_hours(cls, campaign_type: str, default: int = 72) -> int:
        value = cls.workflow_value(campaign_type, 'reply_window_hours', default)
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    @classmethod
    def alert_priority(cls, campaign_type: str, flow_type: str = 'quote_request', default: str | None = None) -> str | None:
        """Return the alert priority declared by the response-flow config.

        ``service_request`` uses the quote-response configuration because the
        source config defines its alert rules there. No priority is inferred
        from the flow name when the config explicitly provides one.
        """
        cfg = cls.response(campaign_type, flow_type)
        rules = cfg.get('rules') or {}
        value = rules.get('alert_priority')
        if value is None and flow_type == 'service_request':
            cfg = cls.response(campaign_type, 'quote_request')
            value = (cfg.get('rules') or {}).get('alert_priority')
        return str(value).strip() if value is not None and str(value).strip() else default

    @classmethod
    def response_rule(cls, campaign_type: str, flow_type: str, key: str, default=None):
        cfg = cls.response(campaign_type, flow_type)
        rules = cfg.get('rules') or {}
        return rules.get(key, default)

    @classmethod
    def workflow_rule(cls, campaign_type: str, key: str, default=None):
        return cls.workflow_value(campaign_type, key, default)

    @classmethod
    def public_response_violations(cls, campaign_type: str, flow_type: str, text: str) -> list[str]:
        """Deterministically enforce public-response rules from the response/workflow JSON."""
        t = str(text or '')
        low = t.lower()
        reasons = []
        if flow_type in {'quote_request', 'service_request'}:
            if cls.response_rule(campaign_type, 'quote_request', 'bot_never_sends_price_publicly', False):
                price_pattern = re.compile(r'(?:\$|€|£|\b(?:usd|cop|mxn|eur|gbp)\b|\b(?:price|precio|costo|cost|honorarios|tarifa|pricing)\b)\s*[:=]?\s*\d', re.I)
                if price_pattern.search(t):
                    reasons.append('price_publicly_forbidden')
            if cls.response_rule(campaign_type, 'quote_request', 'bot_never_guarantees_results', False) or cls.workflow_rule(campaign_type, 'never_make_guaranteed_results_claims', False):
                if re.search(r'\b(?:garantizamos?|garantizado|garantizada|resultado seguro|100% seguro|guaranteed|guarantee)\b', low):
                    reasons.append('guaranteed_result_forbidden')
            if cls.response_rule(campaign_type, 'quote_request', 'do_not_collect_sensitive_details_publicly', False) or cls.response_rule(campaign_type, 'data_request', 'public_reply_must_not_ask_private_case_details', False):
                if re.search(r'\b(?:cédula|cedula|contraseña|password|número de expediente|numero de expediente|expediente completo|documento de identidad|account number|numero de cuenta)\b', low):
                    reasons.append('sensitive_details_publicly_forbidden')
            if cls.workflow_rule(campaign_type, 'never_pressure_with_fear_or_urgency', False):
                if re.search(r'\b(?:si no haces|te va a pasar|maldición|amenaza|you will suffer|if you don\'t)\b', low):
                    reasons.append('fear_pressure_forbidden')
        return sorted(set(reasons))

    @classmethod
    def likes_only_after_no_response(cls, campaign_type: str) -> bool:
        return bool(cls.workflow_value(campaign_type, 'likes_only_mode_after_no_response', False))


class InstagramConfigSchemaValidator:
    @classmethod
    def required_tables(cls, campaign_type: str='botanica') -> set[str]:
        return {str(t.get('name')) for t in (InstagramConfigRuntimeService.database_schema(campaign_type).get('tables') or []) if t.get('name')}

    @classmethod
    def validate_table_payload(cls, campaign_type: str, table_name: str, payload: dict) -> tuple[bool,list[str]]:
        schema=InstagramConfigRuntimeService.database_schema(campaign_type)
        table=next((t for t in schema.get('tables',[]) if t.get('name')==table_name),None)
        if not table: return False,['unknown_table']
        cols={str(c[0]) for c in table.get('columns',[]) if isinstance(c,list) and c}
        return True,[k for k in payload if k not in cols]
