from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from app.config.industry_prompt_rules import normalize_campaign_type
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService


class InstagramConversationFlowService:
    """Instagram-native implementation of the supplied Facebook response rules.

    The JSON files are kept as the business-rule source of truth, while the
    runtime remains native to Instagram.  State is persisted locally so a
    multi-message quote flow survives task iterations/restarts.
    """

    _lock = threading.RLock()

    def __init__(self, logger=None, state_path: str | None = None):
        self.log = logger
        self.state_path = Path(
            state_path
            or (Path(__file__).resolve().parents[2] / "data" / "instagram_conversation_flows.json")
        )
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _norm(text: object) -> str:
        return " ".join(str(text or "").strip().lower().split())

    @staticmethod
    def _campaign_type(campaign: dict) -> str:
        strategy = campaign.get("strategy_snapshot") or {}
        return normalize_campaign_type(
            campaign.get("campaign_type")
            or strategy.get("campaign_type")
            or campaign.get("category")
            or campaign.get("industry")
            or ""
        )

    def _load_config(self, campaign: dict, flow_type: str) -> dict:
        industry = self._campaign_type(campaign)
        # Business-config JSON is the sole runtime source of truth.
        return InstagramConfigRuntimeService.response(industry, flow_type)

    def _load(self) -> dict:
        with self._lock:
            try:
                if not self.state_path.exists():
                    return {}
                value = json.loads(self.state_path.read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else {}
            except Exception:
                return {}

    def _save(self, state: dict) -> None:
        with self._lock:
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)

    @staticmethod
    def _key(campaign: dict, username: str) -> str:
        cid = campaign.get("id") or campaign.get("campaign_id") or "unknown"
        return f"{cid}:{str(username or '').strip().lower()}"

    def _get_state(self, campaign: dict, username: str) -> dict | None:
        return self._load().get(self._key(campaign, username))

    def _set_state(self, campaign: dict, username: str, value: dict) -> None:
        state = self._load()
        state[self._key(campaign, username)] = value
        self._save(state)

    def _clear_state(self, campaign: dict, username: str) -> None:
        state = self._load()
        state.pop(self._key(campaign, username), None)
        self._save(state)

    def active(self, campaign: dict, username: str) -> bool:
        return self._get_state(campaign, username) is not None

    @staticmethod
    def _contains(text: str, phrases: list[str]) -> bool:
        return any(str(p).strip().lower() in text for p in phrases if str(p).strip())

    def detect_request_type(self, text: str, campaign: dict | None = None) -> str | None:
        """Use the exact campaign trigger lists; quote wins over data."""
        t = self._norm(text)
        campaign = campaign or {}
        quote_cfg = self._load_config(campaign, "quote_request")
        data_cfg = self._load_config(campaign, "data_request")

        quote_match = self._contains(t, quote_cfg.get("trigger_keywords") or [])
        data_match = self._contains(t, data_cfg.get("trigger_keywords") or []) or self._contains(t, ["por privado", "por dm", "mensaje privado", "escribeme por privado", "escríbeme por privado"])
        service_terms = ("lectura", "consulta", "limpieza", "limpia", "amarre", "ritual", "protección", "proteccion", "servicio", "tarot")
        price_terms = ("precio", "costo", "tarifa", "cotiza", "cotización", "cotizacion", "price", "pricing", "cost")
        is_service = quote_match and any(x in t for x in service_terms) and not any(x in t for x in price_terms)
        if quote_match and data_match:
            # The source workflow, not Python ordering, decides which intent wins.
            priority_key = 'service_request_priority_over_data_request' if is_service else 'price_request_priority_over_data_request'
            if InstagramConfigRuntimeService.workflow_rule(self._campaign_type(campaign), priority_key, False):
                return 'service_request' if is_service else 'quote_request'
            return 'data_request'
        if quote_match:
            return 'service_request' if is_service else 'quote_request'
        if data_match:
            return 'data_request'
        # A source contact policy may conditionally reveal a cell only after an
        # explicit text/SMS request; that request is itself a data/contact flow.
        if self._explicit_text_or_sms_request(t):
            return "data_request"
        # The source templates explicitly define short positive replies as D2.
        if self._is_short_positive(t):
            return "data_request"

        # Fallback only for a campaign type whose source config is unavailable.
        if self._contains(t, ["quote", "quotation", "estimate", "price", "pricing", "cost", "cotizacion", "cotización", "precio", "costo"]):
            return "quote_request"
        if self._contains(t, ["more info", "information", "details", "info", "más información", "información", "contacto"]):
            return "data_request"
        return None

    @staticmethod
    def _explicit_text_or_sms_request(text: str) -> bool:
        """Return True only for an explicit request to text/SMS.

        A generic request to "message me" means Instagram DM and must not
        unlock a private cell number.
        """
        t = InstagramConversationFlowService._norm(text)
        patterns = (
            r"\btext(?: me| you)?\b",
            r"\btexting\b",
            r"\bsms\b",
            r"\bmensaje(?:s)? de texto\b",
            r"\bpor texto\b",
            r"\btexte(?:ar|ame|arte|o)\b",
            r"\bmand(?:a|ame|ar)\s+(?:un\s+)?(?:sms|texto|mensaje de texto)\b",
            r"\benv(?:ia|iame|iar)\s+(?:un\s+)?(?:sms|texto|mensaje de texto)\b",
            r"\bpuedo\s+(?:mandar|enviar|hacer)\s+(?:un\s+)?(?:sms|texto|mensaje de texto)\b",
        )
        return any(re.search(pattern, t, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _phone_tokens(text: str) -> list[str]:
        return re.findall(r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)", str(text or ""))

    @classmethod
    def _apply_contact_policy(cls, text: str, cfg: dict, incoming: str) -> str:
        """Enforce contact/privacy rules declared in 05_response_data_request."""
        rules = cfg.get("rules") or {}
        policy = str(rules.get("cell_reveal_policy") or "").strip().lower()
        office_sms_allowed = rules.get("office_phone_sms_allowed")
        explicit_text = cls._explicit_text_or_sms_request(incoming)

        # Private cell is allowed only when the source policy explicitly says
        # the prospect requested text/SMS. This is intentionally applied to
        # every rendered D1/D2/D3/DM copy, not just the public comment path.
        if policy == "reveal_cell_only_if_prospect_explicitly_requests_text_or_sms" and not explicit_text:
            lines = str(text).splitlines()
            kept = []
            for line in lines:
                low = line.lower()
                if "cell" in low and any(ch.isdigit() for ch in line):
                    continue
                if "call or text the cell" in low or "call or text this cell" in low:
                    continue
                kept.append(line)
            text = "\n".join(kept)

        elif policy == "never_reveal_private_owner_cell_publicly_use_campaign_phone_or_dm_only":
            # Remove explicitly-labelled private-cell content. Campaign phone
            # placeholders remain available as the approved public channel.
            lines = str(text).splitlines()
            kept = []
            for line in lines:
                low = line.lower()
                if "private owner cell" in low:
                    continue
                if "cell" in low and any(ch.isdigit() for ch in line):
                    continue
                kept.append(line)
            text = "\n".join(kept)

        # When the config says the office phone is call-only, do not expose it
        # as an SMS destination even if a future template uses "call or text".
        if office_sms_allowed is False:
            lines = []
            for line in str(text).splitlines():
                # A conditional private-cell line may legitimately say
                # "call or text" after an explicit SMS request. The
                # call-only restriction applies to the office/campaign phone,
                # not to that separately governed cell.
                if "cell" not in line.lower():
                    line = re.sub(r"(?i)call\s+or\s+text", "Call", line)
                lines.append(line)
            text = "\n".join(lines)

        return text.strip()

    @classmethod
    def _render_template(cls, template: str, campaign: dict, cfg: dict | None = None, incoming: str = "") -> str:
        text = str(template or "")
        social = campaign.get("social_media_account") or {}
        phone = str(
            campaign.get("follow_up_phone")
            or campaign.get("phone")
            or campaign.get("contact_phone")
            or social.get("phone")
            or social.get("business_phone")
            or ""
        ).strip()
        whatsapp = str(campaign.get("whatsapp") or campaign.get("whatsapp_number") or phone).strip()
        url = str(campaign.get("website") or campaign.get("url") or campaign.get("campaign_url") or "").strip()
        facebook = str(campaign.get("facebook_url") or url).strip()

        replacements = {
            "[CAMPAIGN PHONE NUMBER]": phone or "el número de contacto de la campaña",
            "[CAMPAIGN WHATSAPP]": whatsapp or phone or "nuestro WhatsApp",
            "[CAMPAIGN URL]": url or "nuestro sitio web",
            "[CAMPAIGN FACEBOOK]": facebook or url or "nuestro perfil",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        # Do not blindly replace every numeric sequence: some source templates
        # intentionally contain a distinct private/business contact number
        # whose visibility is governed by cell_reveal_policy.
        if cfg:
            text = cls._apply_contact_policy(text, cfg, incoming)
        return text.strip()

    @staticmethod
    def _is_short_positive(text: str) -> bool:
        t = text.strip().lower()
        return len(t) <= 40 and any(x in t for x in ("interested", "info", "me interesa", "need this", "send it", "sounds good", "quiero saber"))

    def _data_reply(self, campaign: dict, incoming: str) -> str:
        cfg = self._load_config(campaign, "data_request")
        templates = cfg.get("public_reply_templates") or []
        if not templates:
            return "Gracias por escribirnos. Con gusto te compartimos más información."
        low = self._norm(incoming)
        if self._contains(low, ["dm me", "message me", "inbox", "mensaje privado", "por privado"]):
            preferred = next((x for x in templates if x.get("id") == "D3"), None)
        elif self._is_short_positive(incoming):
            preferred = next((x for x in templates if x.get("id") == "D2"), None)
        else:
            preferred = next((x for x in templates if x.get("recommended")), None) or templates[0]
        return self._render_template(preferred.get("template", ""), campaign, cfg=cfg, incoming=incoming)

    @staticmethod
    def _min_questions(cfg: dict) -> set[str]:
        rules = cfg.get("rules") or {}
        return {str(x).upper() for x in (rules.get("quote_alert_after_min_answers") or rules.get("service_alert_after_min_answers") or [])}

    @staticmethod
    def _all_question_keys(cfg: dict) -> set[str]:
        return {str(q.get('number') or '').upper() for q in (cfg.get('bot_question_flow') or []) if q.get('number')}

    @classmethod
    def _alert_threshold_reached(cls, cfg: dict, answered_keys: set[str]) -> bool:
        rules = cfg.get('rules') or {}
        minimum = cls._min_questions(cfg)
        if bool(rules.get('wait_for_all_4_answers_required')):
            required = cls._all_question_keys(cfg)
            return bool(required) and required.issubset(answered_keys)
        return bool(minimum and minimum.issubset(answered_keys))

    @staticmethod
    def _question_key(q: dict) -> str:
        return str(q.get("number") or "").upper()

    @staticmethod
    def _is_event_context(text: str) -> bool:
        return any(x in text.lower() for x in ("wedding", "quince", "event", "photoshoot", "trip", "boda", "quinceañera", "evento", "viaje", "grado"))

    def _prepare_questions(self, cfg: dict, initial_text: str) -> list[dict]:
        questions = list(cfg.get("bot_question_flow") or [])
        initial = self._norm(initial_text)
        result = []
        for q in questions:
            question = dict(q)
            raw = str(question.get("question") or "")
            # Source rules explicitly mark some questions as conditional.
            if "only ask if they already mentioned a treatment" in raw.lower():
                if not any(x in initial for x in ("botox", "filler", "facial", "laser", "body contouring", "skin tightening", "relleno", "hilos", "endolifting")):
                    continue
            if "only ask if they mention a wedding" in raw.lower() or "only ask if they mention a wedding, quinceañera" in raw.lower():
                if not self._is_event_context(initial):
                    continue
            result.append(question)
        return result

    def _select_bot_reply_template(self, cfg: dict, incoming: str) -> dict | None:
        """Select the configured initial quote/service reply template.

        ``06_response_quote_request.json`` stores these under
        ``bot_reply_templates`` and calls the text field ``comment``.  The
        previous Instagram flow ignored this section and jumped straight to
        ``bot_question_flow``.
        """
        templates = [x for x in (cfg.get("bot_reply_templates") or []) if isinstance(x, dict)]
        if not templates:
            return None
        text = self._norm(incoming)

        def find(template_id: str):
            return next((x for x in templates if str(x.get("id") or "").upper() == template_id), None)

        urgent_terms = (
            "urgent", "urgente", "today", "hoy", "tomorrow", "mañana", "manana",
            "last minute", "citación", "citacion", "audiencia", "fiscalía", "fiscalia",
            "proceso activo", "asap",
        )
        if any(term in text for term in urgent_terms):
            chosen = find("Q-URGENT")
            if chosen:
                return chosen

        love_terms = (
            "amarre", "endulzamiento", "regreso de pareja", "volver con", "volverá",
            "volvera", "pareja", "amor",
        )
        if any(term in text for term in love_terms):
            chosen = find("Q-LOVE")
            if chosen:
                return chosen

        cleanse_terms = (
            "limpia", "limpieza", "protección", "proteccion", "malas energías",
            "malas energias", "bloqueo",
        )
        if any(term in text for term in cleanse_terms):
            chosen = find("Q-CLEANSE")
            if chosen:
                return chosen

        short_price = len(text.split()) <= 6 and any(
            term in text for term in (
                "precio", "cuánto", "cuanto", "costo", "cost", "price", "pricing",
                "how much", "honorarios", "tarifa", "info",
            )
        )
        if short_price:
            chosen = find("Q-SHORT")
            if chosen:
                return chosen

        return next((x for x in templates if bool(x.get("recommended"))), templates[0])

    def _bot_reply_text(self, cfg: dict, incoming: str, campaign: dict) -> tuple[str, str]:
        template = self._select_bot_reply_template(cfg, incoming)
        if not template:
            return "", ""
        raw = template.get("comment") or template.get("template") or template.get("text") or ""
        return self._render_template(str(raw), campaign, cfg=cfg, incoming=incoming), str(template.get("id") or "")

    def _question_reply(self, q: dict) -> str:
        text = str(q.get("question") or "").strip()
        options = q.get("options")
        if options and isinstance(options, list):
            # Keep source wording, but present options compactly so the user
            # can answer naturally without forcing an exact enum.
            clean = [str(x).strip() for x in options if str(x).strip()]
            if clean and len(clean) <= 10 and "options:" not in text.lower():
                text += "\nOpciones: " + " · ".join(clean)
        return text

    def _final_handoff(self, campaign: dict, cfg: dict, flow_type: str, state: dict) -> str:
        rules = cfg.get("rules") or {}
        phone = str(campaign.get("follow_up_phone") or campaign.get("phone") or campaign.get("contact_phone") or "").strip()
        if flow_type == "quote_request":
            reply = "Gracias. Ya tenemos la información inicial para que el equipo pueda revisar tu solicitud y continuar con la cotización."
        else:
            reply = "Gracias. Ya tenemos la información inicial para orientarte mejor."
        whatsapp = str(campaign.get("whatsapp") or campaign.get("whatsapp_number") or "").strip()
        if flow_type == "data_request" and rules.get("whatsapp_preferred_for_private_consultation") and whatsapp:
            reply += f" Puedes escribirnos por WhatsApp al {whatsapp}."
        elif phone:
            reply += f" Puedes contactarnos al {phone}."
        if rules.get("human_sends_final_quote_via_dm") or rules.get("human_sends_final_quote_or_guidance_via_dm_or_whatsapp"):
            reply += " El equipo continuará contigo por el canal de contacto disponible."
        return reply

    def handle(self, campaign: dict, username: str, incoming_text: str, selected_service: str = "") -> dict | None:
        if not isinstance(campaign, dict) or not username or not incoming_text:
            return None

        state = self._get_state(campaign, username)
        request_type = self.detect_request_type(incoming_text, campaign)

        # The source workflow defines a finite reply window. Expired quote/service
        # conversations become NO_RESPONSE instead of remaining active forever.
        if state is not None:
            try:
                started = datetime.fromisoformat(str(state.get("started_at")))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                window = InstagramConfigRuntimeService.reply_window_hours(self._campaign_type(campaign), 72)
                if datetime.now(timezone.utc) - started >= timedelta(hours=window):
                    state["status"] = "NO_RESPONSE"
                    state["no_response_at"] = datetime.now(timezone.utc).isoformat()
                    self._set_state(campaign, username, state)
                    self._clear_state(campaign, username)
                    return {"handled": True, "reply": "", "flow_type": state.get("flow_type"), "completed": True, "no_response": True, "state": state}
            except (TypeError, ValueError):
                pass

        # Existing flow always wins: an answer such as "Bogotá" must never be
        # mistaken for a new request.
        if state is not None:
            if InstagramConfigRuntimeService.is_human_takeover(state):
                return {"handled": True, "reply": "", "flow_type": state.get("flow_type"), "completed": True, "human_takeover": True, "state": state}
            cfg = self._load_config(campaign, state.get("flow_type", "quote_request"))
            questions = state.get("questions") or []
            idx = int(state.get("index") or 0)
            answers = state.setdefault("answers", [])
            min_keys = self._min_questions(cfg)
            if idx < len(questions):
                answers.append({"number": self._question_key(questions[idx]), "question": questions[idx].get("question", ""), "answer": str(incoming_text).strip()})
                idx += 1
                state["index"] = idx
            state["last_inbound_at"] = datetime.now(timezone.utc).isoformat()

            answered_keys = {str(a.get("number") or "").upper() for a in answers}
            minimum_reached = self._alert_threshold_reached(cfg, answered_keys)
            rules = cfg.get('rules') or {}
            if not rules.get('bot_collects_details_before_alert', True):
                minimum_reached = True
            flow_type = state.get("flow_type", "quote_request")
            alert_ready = minimum_reached and not bool(state.get("alert_sent"))
            if minimum_reached:
                state["alert_ready"] = True
                # Event code identifies the configured alert event; priority is
                # a separate business rule and must come from the response JSON.
                state["alert_event_code"] = "SERVICE" if flow_type == "service_request" else "QUOTE"
                state["alert_priority"] = InstagramConfigRuntimeService.alert_priority(
                    self._campaign_type(campaign), flow_type,
                    default="SERVICE" if flow_type == "service_request" else "QUOTE",
                )

            if minimum_reached or idx >= len(questions):
                reply = self._final_handoff(campaign, cfg, flow_type, state)
                state["completed"] = True
                workflow = InstagramConfigRuntimeService.workflow_rules(self._campaign_type(campaign))
                manual_quote = bool(rules.get("dm_quote_template_manual")) and bool(
                    rules.get("human_sends_final_quote_via_dm") or
                    rules.get("human_sends_final_quote_or_guidance_via_dm_or_whatsapp")
                )
                state["human_takeover"] = bool(
                    (workflow.get("human_takeover_stops_bot") or manual_quote)
                    and flow_type in {"quote_request", "service_request"}
                )
                if state["human_takeover"]:
                    self._set_state(campaign, username, state)
                else:
                    self._clear_state(campaign, username)
                return {"handled": True, "reply": reply if not state["human_takeover"] else "", "flow_type": flow_type, "completed": True, "human_takeover": state["human_takeover"], "alert_ready": alert_ready, "alert_event_code": state.get("alert_event_code"), "alert_priority": state.get("alert_priority"), "state": state}

            self._set_state(campaign, username, state)
            return {"handled": True, "reply": self._question_reply(questions[idx]), "flow_type": state.get("flow_type"), "completed": False, "alert_ready": False, "state": state}

        if not request_type:
            return None

        config_type = "quote_request" if request_type == "service_request" else request_type
        cfg = self._load_config(campaign, config_type)
        if request_type == "data_request":
            cfg = self._load_config(campaign, "data_request")
            reply = self._data_reply(campaign, incoming_text)
            # D3 explicitly requires a subsequent DM containing the full D1 content.
            low = self._norm(incoming_text)
            template_id = "D3" if self._contains(low, ["dm me", "message me", "inbox", "mensaje privado", "por privado"]) else ("D2" if self._is_short_positive(incoming_text) else "D1")
            d1 = next((x for x in (cfg.get("public_reply_templates") or []) if x.get("id") == "D1"), None)
            return {"handled": True, "reply": reply, "flow_type": request_type, "completed": True,
                    "alert_ready": True, "alert_event_code": str((cfg.get("rules") or {}).get("alert_event_id") or "DATA"),
                    "template_id": template_id,
                    "dm_follow_up": template_id in set(cfg.get("rules", {}).get("dm_follow_up_only_for_template_ids") or []),
                    "dm_follow_up_text": self._render_template((d1 or {}).get("template", ""), campaign, cfg=cfg, incoming=incoming_text),
                    "state": {"initial_text": incoming_text}}

        questions = self._prepare_questions(cfg, incoming_text)
        state = {
            "flow_type": request_type,
            "industry": self._campaign_type(campaign),
            "selected_service": selected_service or "",
            "initial_text": str(incoming_text).strip(),
            "questions": questions,
            "answers": [],
            "index": 0,
            "alert_ready": False,
            "alert_sent": False,
            "status": "RESPONDED",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_inbound_at": datetime.now(timezone.utc).isoformat(),
            "reply_window_hours": InstagramConfigRuntimeService.reply_window_hours(self._campaign_type(campaign), 72),
        }
        rules = cfg.get("rules") or {}
        if not rules.get("bot_collects_details_before_alert", True):
            state["alert_ready"] = True
            state["alert_event_code"] = "SERVICE" if request_type == "service_request" else "QUOTE"
            state["alert_priority"] = InstagramConfigRuntimeService.alert_priority(
                self._campaign_type(campaign), request_type,
                default="SERVICE" if request_type == "service_request" else "QUOTE",
            )
        self._set_state(campaign, username, state)

        # The source config defines an initial bot reply template in addition
        # to the persistent Q1..Q4 flow.  Send that configured template first;
        # subsequent inbound messages advance through the question flow.
        template_reply, template_id = self._bot_reply_text(cfg, incoming_text, campaign)
        first = template_reply or (self._question_reply(questions[0]) if questions else self._final_handoff(campaign, cfg, request_type, state))
        if not questions:
            self._clear_state(campaign, username)
        return {
            "handled": True,
            "reply": first,
            "flow_type": request_type,
            "completed": not bool(questions),
            "alert_ready": False,
            "alert_event_code": "SERVICE" if request_type == "service_request" else "QUOTE",
            "alert_priority": InstagramConfigRuntimeService.alert_priority(
                self._campaign_type(campaign), request_type,
                default="SERVICE" if request_type == "service_request" else "QUOTE",
            ),
            "template_id": template_id or None,
            "state": state,
        }
