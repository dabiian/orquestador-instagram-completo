from __future__ import annotations
import os, re, logging, requests
from app.services.email_alert_service import EmailAlertService
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService

class InstagramConfigAlertService:
    """Executes alert rules from 07_alerts.json. Delivery channels are independent."""
    def __init__(self, logger=None, email_service=None, whatsapp_sender=None):
        self.log = logger or logging.getLogger(self.__class__.__name__)
        self.email = email_service or EmailAlertService(logger=self.log)
        self.whatsapp_sender = whatsapp_sender

    @staticmethod
    def _placeholder_key(value):
        return re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")

    def _render(self, value, data):
        text = str(value or '')
        normalized = {self._placeholder_key(k): ('' if v is None else str(v)) for k, v in (data or {}).items()}
        aliases = {
            'CAMPAIGN_PHONE': 'CAMPAIGN_PHONE_NUMBER',
            'CAMPAIGN_PHONE_NUMBER': 'CAMPAIGN_PHONE_NUMBER',
            'CAMPAIGN_WHATSAPP': 'CAMPAIGN_WHATSAPP',
            'CAMPAIGN_URL': 'CAMPAIGN_URL',
            'CAMPAIGN_FACEBOOK_URL': 'CAMPAIGN_FACEBOOK',
            'CAMPAIGN_FACEBOOK': 'CAMPAIGN_FACEBOOK',
            'OWNER_ALERT_WHATSAPP': 'ALERT_WHATSAPP',
            # The 07_alerts source uses short labels in WhatsApp templates
            # ([Time], [Q1]..[Q4]) and a long-form link label in email.
            # Runtime context uses canonical names; map both vocabularies so
            # no source placeholder leaks into a delivered alert.
            'TIME': 'TIMESTAMP',
            'DIRECT_LINK_TO_FACEBOOK_POST': 'FACEBOOK_POST_LINK',
            'Q1': 'Q1_ANSWER',
            'Q2': 'Q2_ANSWER',
            'Q3': 'Q3_ANSWER',
            'Q4': 'Q4_ANSWER',
        }
        for source, target in aliases.items():
            if source in normalized and target not in normalized:
                normalized[target] = normalized[source]
        # Some aliases are expressed in the source template direction
        # (e.g. [Q1] -> context key [Q1 ANSWER]). Add those reverse labels
        # explicitly so both template vocabularies resolve.
        reverse_aliases = {
            'TIME': 'TIMESTAMP',
            'DIRECT_LINK_TO_FACEBOOK_POST': 'FACEBOOK_POST_LINK',
            'Q1': 'Q1_ANSWER',
            'Q2': 'Q2_ANSWER',
            'Q3': 'Q3_ANSWER',
            'Q4': 'Q4_ANSWER',
        }
        for target, source in reverse_aliases.items():
            if source in normalized and target not in normalized:
                normalized[target] = normalized[source]

        def replace(match):
            key = self._placeholder_key(match.group(1))
            if key in normalized:
                return normalized[key]
            # Source config uses placeholders such as [Q1 answer or Not answered].
            # Treat the fallback text after "or" as display guidance, not part of the key.
            if "_OR_" in key:
                base = key.split("_OR_", 1)[0].strip("_")
                if base in normalized:
                    return normalized[base]
            return match.group(0)

        return re.sub(r"\[([^\]]+)\]", replace, text)

    def _event(self, campaign_type, event_code):
        events = (InstagramConfigRuntimeService.alerts(campaign_type).get('events') or [])
        return next((e for e in events if str(e.get('id','')).upper()==event_code.upper()), None)

    def send(self, campaign_type, event_code, context: dict) -> dict:
        event = self._event(campaign_type, event_code)
        if not event:
            return {'ok': False, 'email_sent': False, 'whatsapp_sent': False, 'reason': 'event_not_configured'}
        delivery = InstagramConfigRuntimeService.alerts(campaign_type).get('delivery') or {}
        data = {str(k).upper(): v for k,v in (context or {}).items()}
        email_cfg = event.get('email') or {}
        email_to = str(context.get('CAMPAIGN EMAIL') or context.get('campaign_email') or delivery.get('business_email') or os.getenv('CAMPAIGN_EMAIL','')).strip()
        if email_to.startswith('['): email_to = os.getenv('CAMPAIGN_EMAIL','').strip()
        subject = self._render(email_cfg.get('subject',''), data)
        body = self._render(email_cfg.get('body',''), data)
        email_sent = self.email.send_email(email_to, subject, body) if email_to else False

        wa_template = self._render(event.get('whatsapp',''), data)
        wa_to = str(context.get('ALERT WHATSAPP') or context.get('alert_whatsapp') or delivery.get('whatsapp') or os.getenv('OWNER_ALERT_WHATSAPP','')).strip()
        if wa_to.startswith('['): wa_to = os.getenv('OWNER_ALERT_WHATSAPP','').strip()
        whatsapp_sent = False
        if self.whatsapp_sender:
            try: whatsapp_sent = bool(self.whatsapp_sender(wa_to, wa_template))
            except Exception as exc: self.log.warning('WhatsApp alert error: %r', exc)
        else:
            webhook = os.getenv('WHATSAPP_ALERT_WEBHOOK','').strip()
            if webhook and wa_to:
                try:
                    r=requests.post(webhook,json={'to':wa_to,'message':wa_template,'event':event_code},timeout=20)
                    whatsapp_sent = 200 <= r.status_code < 300
                except Exception as exc: self.log.warning('WhatsApp webhook error: %r', exc)

        return {'ok': email_sent or whatsapp_sent, 'email_sent': email_sent, 'whatsapp_sent': whatsapp_sent,
                'event_code': event_code, 'priority': event.get('priority'), 'response_target': delivery.get('response_target')}
