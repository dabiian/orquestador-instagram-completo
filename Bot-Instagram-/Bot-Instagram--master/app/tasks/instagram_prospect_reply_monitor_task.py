import os
import json
import random
import re
from typing import Optional

from selenium.webdriver.common.by import By

from app.core.interfaces import ITask
from app.utils.logger import get_logger
from app.api.prospecting_api import ProspectingAPI
from app.services.instagram_profile_service import InstagramProfileService
from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.services.email_alert_service import EmailAlertService
from app.services.instagram_conversation_flow_service import InstagramConversationFlowService
from app.services.instagram_config_alert_service import InstagramConfigAlertService
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService
from app.services.instagram_safety_gate import InstagramSafetyGate
from app.config.locators.instagram_reply_monitor_locators import (
    InstagramReplyMonitorLocators,
)


class InstagramProspectReplyMonitorTask(ITask):
    """
    Revisa replies en posts ya comentados y, si hay intención,
    responde automáticamente usando IA + teléfono de la campaña.

    Flujo:
    - busca prospect_posts con status="commented"
    - abre el post
    - expande replies
    - detecta respuestas del prospecto
    - clasifica la respuesta con IA
    - da like al comentario/reply del prospecto si no es negativo/irrelevante
    - responde con IA usando el teléfono si la clasificación es interested/question
    - guarda interacción inbound/outbound
    - actualiza prospect y prospect_post
    """

    def __init__(self, browser, data: dict, account_api, ai_api):
        self.browser = browser
        self.data = data or {}
        self.account_api = account_api
        self.ai_api = ai_api
        self.log = get_logger(self.__class__.__name__)

        self.prospecting_api = ProspectingAPI()
        self.email_alert_service = EmailAlertService(logger=self.log)

        self.profile_service = InstagramProfileService(
            browser=self.browser,
            logger=self.log,
        )

        self.post_interaction_service = InstagramPostInteractionService(
            browser=self.browser,
            logger=self.log,
        )

        self.conversation_flow_service = InstagramConversationFlowService(logger=self.log)
        self.config_alert_service = InstagramConfigAlertService(logger=self.log)
        self.safety_gate = None

    def execute(self) -> bool:
        try:
            account_id = self._get_social_media_account_id()

            if not account_id:
                self.log.warning("No se encontró social_media_account.id en ReplyMonitorTask")
                return False

            ok_campaign, campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            self.log.info(
                "[prospecting-reply] get_active_campaign | ok=%s | campaign=%s | account_id=%s",
                ok_campaign,
                self._shorten_for_log(campaign),
                account_id,
            )

            if not ok_campaign or not isinstance(campaign, dict):
                self.log.warning("No se encontró campaña activa para revisar replies.")
                return False

            campaign_id = campaign["id"]
            campaign_type = InstagramConfigRuntimeService.campaign(
                campaign.get("campaign_type") or campaign.get("industry_target") or campaign.get("industry") or "botanica"
            )
            self.safety_gate = InstagramSafetyGate(campaign_type)
            follow_up_phone = str(campaign.get("follow_up_phone") or "").strip()

            ok_posts, posts_payload = self.prospecting_api._get(
                "prospecting/prospect-posts/",
                params={
                    "campaign_id": campaign_id,
                    "status": "commented",
                },
            )[:2]

            posts = self._normalize_api_list_payload(posts_payload)

            if not ok_posts or not posts:
                self.log.warning("No hay posts comentados para revisar replies.")
                return False

            processed_posts = 0
            detected_total = 0
            found_replies_total = 0
            already_registered_total = 0
            failed_posts = 0
            max_posts_to_review = 10

            for post in posts:
                if processed_posts >= max_posts_to_review:
                    break

                try:
                    prospect_id = post.get("prospect")
                    post_id = post.get("id")
                    post_url = str(post.get("post_url") or "").strip()
                    last_comment_text = str(post.get("last_comment_text") or "").strip()
                    original_caption = str(post.get("caption_text") or "").strip()

                    if not prospect_id or not post_id or not post_url:
                        continue

                    if not self._post_was_commented_by_this_account(
                        prospect_post_id=post_id,
                        social_media_account_id=account_id,
                    ):
                        self.log.info(
                            "[prospecting-reply] post comentado por otra cuenta, se omite | post_id=%s | account_id=%s",
                            post_id,
                            account_id,
                        )
                        continue

                    prospect_data = self._get_prospect_by_id(prospect_id)

                    if not prospect_data:
                        self.log.warning(
                            "[prospecting-reply] no se pudo obtener prospect_id=%s",
                            prospect_id,
                        )
                        continue

                    prospect_username = str(
                        prospect_data.get("username") or ""
                    ).strip().lower()

                    if not prospect_username:
                        continue

                    self.profile_service.open_url(post_url)
                    self.browser.time_sleep(random.randint(3, 5))

                    self._expand_reply_thread_for_our_comment(last_comment_text)
                    self._debug_reply_permalink_count()

                    self.log.info(
                        "[prospecting-reply] filtro prospect_username=%s | last_comment_text=%s | account_id=%s",
                        prospect_username,
                        last_comment_text,
                        account_id,
                    )

                    replies = self._extract_replies_from_prospect(
                        prospect_username=prospect_username,
                        last_comment_text=last_comment_text,
                    )

                    if not replies:
                        self.browser.time_sleep(1.5)
                        replies = self._extract_replies_from_prospect(
                            prospect_username=prospect_username,
                            last_comment_text=last_comment_text,
                        )

                    seen_reply_texts = set()

                    for reply in replies:
                        reply_text = str(reply.get("text") or "").strip()

                        if not reply_text:
                            continue

                        normalized_reply = self._normalize_text(reply_text)

                        if not normalized_reply:
                            continue

                        if normalized_reply in seen_reply_texts:
                            continue

                        seen_reply_texts.add(normalized_reply)

                        found_replies_total += 1

                        if self._already_registered_inbound_reply(
                            prospect_post_id=post_id,
                            reply_text=reply_text,
                        ):
                            already_registered_total += 1
                            self.log.info(
                                "[prospecting-reply] reply ya registrada, se omite | post_id=%s | reply=%s",
                                post_id,
                                reply_text,
                            )
                            continue

                        classification_payload = self._classify_reply_with_ai(
                            reply_text=reply_text,
                            original_comment_text=last_comment_text,
                            original_post_caption=original_caption,
                        )

                        classification = str(
                            classification_payload.get("classification") or "neutral"
                        ).strip().lower()

                        reason = str(
                            classification_payload.get("reason") or ""
                        ).strip()

                        inbound_interaction = self._create_inbound_reply_interaction(
                            prospect_id=prospect_id,
                            prospect_post_id=post_id,
                            reply_text=reply_text,
                            classification=classification,
                            social_media_account_id=account_id,
                        )

                        interaction_id = None

                        if isinstance(inbound_interaction, dict):
                            interaction_id = inbound_interaction.get("id")

                        self.log.info(
                            "[prospecting-reply] reply clasificado | post_id=%s | classification=%s | reason=%s | reply=%s | account_id=%s",
                            post_id,
                            classification,
                            reason,
                            reply_text,
                            account_id,
                        )

                        if classification not in {"negative", "irrelevant"}:
                            account_key = str(prospect_username or prospect_id or post_id)
                            can_like, like_reason = self.safety_gate.allow("like", account_key, commit=False)
                            if not can_like:
                                self.log.info("[safety-gate] like de reply omitido: %s", like_reason)
                                like_ok = False
                            else:
                                like_ok = self._click_like_on_comment(reply)
                                if like_ok:
                                    self.safety_gate.allow("like", account_key, commit=True)

                            self.log.info(
                                "[prospecting-reply] like al reply | post_id=%s | like_ok=%s | reply=%s",
                                post_id,
                                like_ok,
                                reply_text,
                            )

                            if like_ok:
                                self.prospecting_api.create_prospect_interaction(
                                    prospect_id=prospect_id,
                                    prospect_post_id=post_id,
                                    social_media_account_id=account_id,
                                    interaction_type="liked",
                                    direction="outbound",
                                    content_text="reply_like",
                                    status="success",
                                )

                        if classification in {"interested", "question"}:
                            self.prospecting_api.update_prospect(
                                prospect_id,
                                status="interested",
                            )

                            self.prospecting_api.update_prospect_post(
                                post_id,
                                status="follow_up_pending",
                            )

                            # Do not send the legacy generic interest alert here.
                            # Task 12 must respect 06/07 configured minimum-answer
                            # thresholds; the unified conversation flow below is
                            # the single source of truth for alert readiness.

                            # Use the same persistent data/quote flow used by DMs.
                            # The public-reply monitor and DM inbox are two entry
                            # points into the same prospect conversation.
                            flow_result = None
                            try:
                                selected_service = str(
                                    prospect_data.get("selected_service")
                                    or prospect_data.get("service")
                                    or ""
                                ).strip()
                                flow_result = self.conversation_flow_service.handle(
                                    campaign=campaign,
                                    username=prospect_username,
                                    incoming_text=reply_text,
                                    selected_service=selected_service,
                                )
                            except Exception as flow_exc:
                                self.log.warning(
                                    "[prospecting-reply] conversation flow error: %r",
                                    flow_exc,
                                )

                            if flow_result and flow_result.get("handled"):
                                flow_type = str(flow_result.get("flow_type") or "")
                                if flow_result.get("human_takeover"):
                                    self.prospecting_api.update_prospect(prospect_id, status="human_takeover")
                                if (flow_result.get("completed") or flow_result.get("alert_ready")) and flow_type in {"data_request", "quote_request", "service_request"}:
                                    event_code = str(flow_result.get("alert_event_code") or ("DATA" if flow_type == "data_request" else ("QUOTE" if flow_type == "quote_request" else "SERVICE")))
                                    answers = ((flow_result.get("state") or {}).get("answers") or [])
                                    answer_map = {str(a.get("number") or "").upper(): a.get("answer", "") for a in answers}
                                    alert_ctx = {
                                        "ACCOUNT NAME": prospect_data.get("display_name") or prospect_username,
                                        "CATEGORY": prospect_data.get("industry_detected") or campaign.get("category") or campaign.get("campaign_type"),
                                        "TIMESTAMP": __import__('datetime').datetime.utcnow().isoformat(),
                                        "PROFILE URL": prospect_data.get("profile_url") or "",
                                        "EXACT REPLY TEXT": reply_text,
                                        "INTENT": event_code,
                                        "MATCHED KEYWORDS": reason,
                                        "CONFIDENCE": classification_payload.get("confidence", ""),
                                        "Q1 ANSWER": answer_map.get("Q1", "Not answered"),
                                        "Q2 ANSWER": answer_map.get("Q2", "Not answered"),
                                        "Q3 ANSWER": answer_map.get("Q3", "Not answered"),
                                        "Q4 ANSWER": answer_map.get("Q4", "Not answered"),
                                        "FACEBOOK POST LINK": post_url,
                                        "CAMPAIGN EMAIL": campaign.get("business_email") or campaign.get("email"),
                                        "ALERT WHATSAPP": campaign.get("alert_whatsapp") or campaign.get("owner_alert_whatsapp"),
                                    }
                                    alert_result = self.config_alert_service.send(self.conversation_flow_service._campaign_type(campaign), event_code, alert_ctx)
                                    self.log.info("[config-alert] event=%s result=%s", event_code, alert_result)
                                auto_response = str(flow_result.get("reply") or "").strip()
                                classification = "question"
                            else:
                                auto_response = self._generate_follow_up_reply_with_ai(
                                    reply_text=reply_text,
                                    classification=classification,
                                    follow_up_phone=follow_up_phone,
                                    original_comment_text=last_comment_text,
                                    original_post_caption=original_caption,
                                )

                            if flow_result and flow_result.get("human_takeover"):
                                auto_response = ""
                            if auto_response:
                                violations = InstagramConfigRuntimeService.public_response_violations(
                                    campaign_type, flow_result.get("flow_type", "quote_request") if flow_result else "quote_request", auto_response
                                )
                                if violations:
                                    self.log.warning(
                                        "[config-policy] auto-reply blocked by public response rules | campaign_type=%s | violations=%s",
                                        campaign_type, violations,
                                    )
                                    auto_response = ""
                            if auto_response:
                                self.log.info(
                                    "[prospecting-reply] auto_response_ia=%s",
                                    auto_response,
                                )

                                account_key = str(prospect_username or prospect_id or post_id)
                                can_reply, reply_reason = self.safety_gate.allow("auto_reply", account_key, commit=False)
                                if not can_reply:
                                    self.log.info("[safety-gate] auto-reply omitido: %s", reply_reason)
                                    continue
                                rules = InstagramConfigRuntimeService.response(
                                    campaign_type, "data_request" if (flow_result and flow_result.get("flow_type") == "data_request") else "quote_request"
                                ).get("rules") or {}
                                if rules.get("reply_in_same_comment_thread", True) is False:
                                    self.log.info("[config-policy] reply_in_same_comment_thread=false; no se publica respuesta pública")
                                    continue
                                clicked_reply = self._click_reply_on_comment(reply)

                                if clicked_reply:
                                    delay = InstagramConfigRuntimeService.delay(campaign_type, "comment_to_auto_reply")
                                    try:
                                        self.browser.time_sleep(random.uniform(float(delay.get("min", 0)), float(delay.get("max", delay.get("min", 0)))))
                                    except (TypeError, ValueError):
                                        pass
                                    replied_ok = (
                                        self.post_interaction_service.reply_current_post_visible(
                                            auto_response
                                        )
                                    )

                                    if replied_ok:
                                        self.safety_gate.allow("auto_reply", account_key, commit=True)
                                        self.prospecting_api.create_prospect_interaction(
                                            prospect_id=prospect_id,
                                            prospect_post_id=post_id,
                                            social_media_account_id=account_id,
                                            interaction_type="commented",
                                            direction="outbound",
                                            content_text=auto_response,
                                            classification=self._map_classification_for_db(
                                                classification
                                            ),
                                            status="success",
                                        )
                                else:
                                    self.log.warning(
                                        "[prospecting-reply] no se pudo activar modo responder sobre el reply | post_id=%s",
                                        post_id,
                                    )

                        detected_total += 1

                    processed_posts += 1

                except Exception as e:
                    failed_posts += 1
                    self.log.warning(
                        "[prospecting-reply] error procesando post=%s | error=%r",
                        self._shorten_for_log(post),
                        e,
                    )
                    continue

            self.log.info(
                "[prospecting-reply] task finalizada | posts_revisados=%s | replies_encontradas=%s | ya_registradas=%s | nuevas=%s | errores_post=%s | account_id=%s",
                processed_posts,
                found_replies_total,
                already_registered_total,
                detected_total,
                failed_posts,
                account_id,
            )

            # A clean scan with zero new replies is a successful no-op, not an ERR.
            # The task only fails when nothing could be processed or every reviewed
            # post failed unexpectedly.
            return bool(processed_posts > 0 and failed_posts < processed_posts)

        except Exception as e:
            self.log.exception("Error en InstagramProspectReplyMonitorTask: %s", e)
            return False

    # =========================================================
    # HELPERS BASE
    # =========================================================

    def _get_social_media_account_id(self) -> Optional[int]:
        try:
            social_media_account = self.data.get("social_media_account") or {}

            if isinstance(social_media_account, dict):
                account_id = social_media_account.get("id")

                if account_id:
                    return int(account_id)

            account_id = self.data.get("social_media_account_id")

            if account_id:
                return int(account_id)

            return None

        except Exception:
            return None

    def _get_bot_personality_id(self) -> Optional[int]:
        try:
            social_media_account = self.data.get("social_media_account") or {}

            if isinstance(social_media_account, dict):
                bot_personality = social_media_account.get("bot_personality") or {}

                if isinstance(bot_personality, dict):
                    bot_personality_id = bot_personality.get("id")

                    if bot_personality_id:
                        return int(bot_personality_id)

            bot_personality_id = self.data.get("bot_personality_id")

            if bot_personality_id:
                return int(bot_personality_id)

            return None

        except Exception:
            return None

    def _get_prospect_by_id(self, prospect_id: int) -> Optional[dict]:
        try:
            ok, payload = self.prospecting_api._get(
                f"prospecting/prospects/{prospect_id}/"
            )[:2]

            if ok and isinstance(payload, dict):
                return payload

            return None

        except Exception:
            return None

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _normalize_api_list_payload(self, payload) -> list[dict]:
        try:
            if isinstance(payload, list):
                return [x for x in payload if isinstance(x, dict)]

            if isinstance(payload, dict):
                for key in ["results", "data", "items"]:
                    value = payload.get(key)

                    if isinstance(value, list):
                        return [x for x in value if isinstance(x, dict)]

            return []

        except Exception:
            return []

    def _map_classification_for_db(self, classification: str) -> str:
        classification = str(classification or "").strip().lower()

        allowed = {
            "neutral",
            "interested",
            "question",
            "irrelevant",
            "negative",
        }

        return classification if classification in allowed else "neutral"

    def _shorten_for_log(self, value, max_len: int = 1200):
        try:
            text = value

            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False, default=str)

            text = text.replace("\\n", " ").replace("\n", " ").strip()

            if len(text) > max_len:
                return text[:max_len] + "...[truncated]"

            return text

        except Exception:
            return str(value)

    # =========================================================
    # DEDUPE / INTERACTIONS
    # =========================================================

    def _already_registered_inbound_reply(
        self,
        prospect_post_id: int,
        reply_text: str,
    ) -> bool:
        try:
            ok, interactions_payload = self.prospecting_api._get(
                "prospecting/prospect-interactions/",
                params={
                    "prospect_post_id": prospect_post_id,
                    "interaction_type": "reply_received",
                    "direction": "inbound",
                },
            )[:2]

            interactions = self._normalize_api_list_payload(interactions_payload)

            if not ok or not interactions:
                return False

            target = self._normalize_text(reply_text)

            for item in interactions:
                existing = self._normalize_text(item.get("content_text") or "")

                if existing and existing == target:
                    return True

            return False

        except Exception:
            return False

    def _create_inbound_reply_interaction(
        self,
        prospect_id: int,
        prospect_post_id: int,
        reply_text: str,
        classification: str,
        social_media_account_id: Optional[int] = None,
    ) -> Optional[dict]:
        try:
            result = self.prospecting_api.create_prospect_interaction(
                prospect_id=prospect_id,
                prospect_post_id=prospect_post_id,
                social_media_account_id=social_media_account_id,
                interaction_type="reply_received",
                direction="inbound",
                content_text=reply_text,
                classification=self._map_classification_for_db(classification),
                status="success",
            )

            if isinstance(result, tuple):
                ok = result[0] if len(result) > 0 else False
                payload = result[1] if len(result) > 1 else None

                if ok and isinstance(payload, dict):
                    return payload

            if isinstance(result, dict):
                return result

            return None

        except Exception as e:
            self.log.warning(
                "[prospecting-reply] no se pudo crear interacción inbound | prospect_post_id=%s | account_id=%s | error=%r",
                prospect_post_id,
                social_media_account_id,
                e,
            )
            return None

    def _post_was_commented_by_this_account(
        self,
        prospect_post_id: int,
        social_media_account_id: int,
    ) -> bool:
        try:
            ok, interactions_payload = self.prospecting_api._get(
                "prospecting/prospect-interactions/",
                params={
                    "prospect_post_id": prospect_post_id,
                    "interaction_type": "commented",
                    "direction": "outbound",
                    "social_media_account_id": social_media_account_id,
                },
            )[:2]

            interactions = self._normalize_api_list_payload(interactions_payload)

            if not ok or not interactions:
                return False

            return len(interactions) > 0

        except Exception as e:
            self.log.warning(
                "[prospecting-reply] error verificando si la cuenta comentó el post | post_id=%s | account_id=%s | error=%r",
                prospect_post_id,
                social_media_account_id,
                e,
            )
            return False

    # =========================================================
    # EMAIL ALERT
    # =========================================================

    def _get_follow_up_alert_email(self, campaign: dict) -> str:
        try:
            email_to = (
                self.data.get("email_to")
                or campaign.get("follow_up_email")
                or campaign.get("notification_email")
                or os.getenv("FOLLOW_UP_ALERT_EMAIL")
                or os.getenv("SMTP_ALERT_TO")
                or ""
            )

            return str(email_to or "").strip()

        except Exception:
            return ""

    def _already_follow_up_alerted(
        self,
        interaction_id: Optional[int],
        email_to: str,
    ) -> bool:
        try:
            if not interaction_id:
                return False

            ok, alerts_payload = self.prospecting_api._get(
                "prospecting/follow-up-alerts/",
                params={
                    "interaction_id": interaction_id,
                },
            )[:2]

            alerts = self._normalize_api_list_payload(alerts_payload)

            if not ok or not alerts:
                return False

            email_to_norm = str(email_to or "").strip().lower()

            for item in alerts:
                item_email = str(item.get("email_to") or "").strip().lower()

                if item_email == email_to_norm:
                    return True

            return False

        except Exception as e:
            self.log.warning(
                "[prospecting-reply] error verificando alerta existente | interaction_id=%s | error=%r",
                interaction_id,
                e,
            )
            return False

    def _send_interest_email_alert_once(
        self,
        campaign: dict,
        prospect: dict,
        post: dict,
        reply_text: str,
        classification: str,
        reason: str = "",
        interaction_id: Optional[int] = None,
        social_media_account_id: Optional[int] = None,
    ) -> bool:
        try:
            email_to = self._get_follow_up_alert_email(campaign)

            if not email_to:
                self.log.warning(
                    "[prospecting-reply] no se envió alerta: falta FOLLOW_UP_ALERT_EMAIL o email en campaña."
                )
                return False

            if self._already_follow_up_alerted(interaction_id, email_to):
                self.log.info(
                    "[prospecting-reply] alerta ya enviada para interaction_id=%s",
                    interaction_id,
                )
                return True

            prospect_id = prospect.get("id")
            prospect_post_id = post.get("id")

            subject = self._build_interest_email_subject(
                prospect=prospect,
                classification=classification,
            )

            body = self._build_interest_email_body(
                campaign=campaign,
                prospect=prospect,
                post=post,
                reply_text=reply_text,
                classification=classification,
                reason=reason,
            )

            sent_ok = self.email_alert_service.send_email(
                to_email=email_to,
                subject=subject,
                body=body,
            )

            if not sent_ok:
                self.log.warning(
                    "[prospecting-reply] falló envío de email | prospect_id=%s | post_id=%s",
                    prospect_id,
                    prospect_post_id,
                )
                return False

            try:
                self.prospecting_api.create_follow_up_alert(
                    prospect_id=prospect_id,
                    prospect_post_id=prospect_post_id,
                    interaction_id=interaction_id,
                    alert_type="email",
                    status="pending",
                    email_to=email_to,
                    payload_json={
                        "reason": "Prospecto respondió con interés o pregunta",
                        "reply_text": reply_text,
                        "classification": classification,
                        "classification_reason": reason,
                        "delivery": "sent",
                        "source": "InstagramProspectReplyMonitorTask",
                        "social_media_account_id": social_media_account_id,
                    },
                )
            except Exception as e:
                self.log.warning(
                    "[prospecting-reply] correo enviado pero no se pudo registrar follow_up_alert | error=%r",
                    e,
                )

            try:
                self.prospecting_api.create_prospect_interaction(
                    prospect_id=prospect_id,
                    prospect_post_id=prospect_post_id,
                    social_media_account_id=social_media_account_id,
                    interaction_type="email_alerted",
                    direction="outbound",
                    content_text=f"Email alert sent to {email_to}",
                    classification=self._map_classification_for_db(classification),
                    status="success",
                )
            except Exception as e:
                self.log.warning(
                    "[prospecting-reply] no se pudo registrar interaction email_alerted | error=%r",
                    e,
                )

            self.log.info(
                "[prospecting-reply] email de alerta enviado | to=%s | prospect_id=%s | post_id=%s | account_id=%s",
                email_to,
                prospect_id,
                prospect_post_id,
                social_media_account_id,
            )

            return True

        except Exception as e:
            self.log.exception(
                "[prospecting-reply] error enviando alerta de interés por email: %s",
                e,
            )
            return False

    def _build_interest_email_subject(self, prospect: dict, classification: str) -> str:
        username = str(prospect.get("username") or "unknown").strip()
        classification = str(classification or "").strip().lower()

        if classification == "question":
            return f"[Instagram] Prospecto pidió información: {username}"

        return f"[Instagram] Prospecto interesado: {username}"

    def _build_interest_email_body(
        self,
        campaign: dict,
        prospect: dict,
        post: dict,
        reply_text: str,
        classification: str,
        reason: str = "",
    ) -> str:
        campaign_name = str(
            campaign.get("name")
            or campaign.get("campaign_name")
            or campaign.get("title")
            or ""
        ).strip()

        username = str(prospect.get("username") or "").strip()
        display_name = str(prospect.get("display_name") or "").strip()
        profile_url = str(prospect.get("profile_url") or "").strip()
        bio = str(prospect.get("bio") or "").strip()

        post_url = str(post.get("post_url") or "").strip()
        post_caption = str(post.get("caption_text") or "").strip()
        last_comment_text = str(post.get("last_comment_text") or "").strip()

        classification = str(classification or "").strip()

        parts = [
            "Se detectó un prospecto con interés desde Instagram.",
            "",
            "DATOS DE CAMPAÑA",
            f"Campaña: {campaign_name}",
            "",
            "DATOS DEL PROSPECTO",
            f"Username: {username}",
            f"Display name: {display_name}",
            f"Profile URL: {profile_url}",
            f"Bio: {bio}",
            "",
            "INTERACCIÓN DETECTADA",
            f"Clasificación: {classification}",
            f"Razón IA: {reason}",
            f"Respuesta del prospecto: {reply_text}",
            "",
            "POST",
            f"Post URL: {post_url}",
            f"Comentario enviado por el bot: {last_comment_text}",
            f"Caption del post: {post_caption}",
        ]

        return "\n".join(parts)

    # =========================================================
    # DOM / REPLIES
    # =========================================================

    def _debug_reply_li_count(self):
        try:
            count = self.browser.driver.execute_script(
                InstagramReplyMonitorLocators.DEBUG_REPLY_LI_COUNT_SCRIPT
            )
            self.log.info("[prospecting-reply] debug li._a9ye count=%s", count)
        except Exception as e:
            self.log.warning("debug li._a9ye error: %r", e)

    def _debug_reply_permalink_count(self):
        try:
            count = self.browser.driver.execute_script(
                InstagramReplyMonitorLocators.DEBUG_REPLY_PERMALINK_COUNT_SCRIPT
            )
            self.log.info("[prospecting-reply] debug reply permalink count=%s", count)
        except Exception as e:
            self.log.warning("debug reply permalink error: %r", e)

    def _expand_all_reply_threads(self) -> None:
        try:
            for _ in range(5):
                buttons = self.browser.driver.find_elements(
                    By.XPATH,
                    InstagramReplyMonitorLocators.EXPAND_ALL_REPLY_THREADS_XPATH,
                )

                clicked_any = False

                for btn in buttons:
                    try:
                        if not btn.is_displayed():
                            continue

                        try:
                            btn.click()
                        except Exception:
                            self.browser.driver.execute_script(
                                InstagramReplyMonitorLocators.CLICK_ELEMENT_SCRIPT,
                                btn,
                            )

                        clicked_any = True
                        self.browser.time_sleep(1)

                    except Exception:
                        continue

                if not clicked_any:
                    break

        except Exception as e:
            self.log.warning("Error expandiendo replies: %r", e)

    def _expand_reply_thread_for_our_comment(self, last_comment_text: str) -> bool:
        try:
            snippet = self._normalize_text(last_comment_text)[:80]

            if not snippet:
                return False

            clicked = self.browser.driver.execute_script(
                InstagramReplyMonitorLocators.EXPAND_REPLY_THREAD_FOR_OUR_COMMENT_SCRIPT,
                snippet,
            )

            self.log.info(
                "[prospecting-reply] expand reply thread near our comment | clicked=%s | snippet=%s",
                clicked,
                snippet,
            )

            if clicked:
                self.browser.time_sleep(2)
                return True

            return False

        except Exception as e:
            self.log.warning("Error expandiendo replies del comentario propio: %r", e)
            return False

    def _extract_replies_from_prospect(
        self,
        prospect_username: str,
        last_comment_text: str,
    ) -> list[dict]:
        try:
            snippet = self._normalize_text(last_comment_text)

            data = self.browser.driver.execute_script(
                InstagramReplyMonitorLocators.EXTRACT_REPLIES_FROM_PROSPECT_SCRIPT,
                prospect_username,
                snippet,
            ) or []

            cleaned = [x for x in data if isinstance(x, dict)]

            self.log.info(
                "[prospecting-reply] replies limpias extraídas=%s | prospect_username=%s | data=%s",
                len(cleaned),
                prospect_username,
                self._shorten_for_log(cleaned),
            )

            return cleaned

        except Exception as e:
            self.log.warning("Error extrayendo replies reales del prospecto: %r", e)
            return []

    def _click_reply_on_comment(self, comment: dict) -> bool:
        try:
            profile_href = (comment.get("profile_href") or "").strip()
            permalink = (comment.get("permalink") or "").strip()

            if not profile_href:
                return False

            result = self.browser.driver.execute_script(
                InstagramReplyMonitorLocators.CLICK_REPLY_ON_COMMENT_SCRIPT,
                profile_href,
                permalink,
            )

            self.log.info("[prospecting-reply] resultado click reply js: %s", result)

            if result and result.get("ok"):
                self.browser.time_sleep(1.5)
                return True

            return False

        except Exception as e:
            self.log.warning("Error activando reply sobre comentario exacto: %r", e)
            return False

    def _click_like_on_comment(self, comment: dict) -> bool:
        try:
            profile_href = (comment.get("profile_href") or "").strip()
            permalink = (comment.get("permalink") or "").strip()

            if not profile_href:
                self.log.warning("[prospecting-reply] no hay profile_href para buscar like")
                return False

            result = self.browser.driver.execute_script(
                InstagramReplyMonitorLocators.CLICK_LIKE_ON_COMMENT_SCRIPT,
                profile_href,
                permalink,
            )

            self.log.info("[prospecting-reply] resultado like js: %s", result)

            return bool(result and result.get("ok"))

        except Exception as e:
            self.log.warning("Error dando like al comentario/reply: %r", e)
            return False

    # =========================================================
    # IA - CLASIFICACIÓN
    # =========================================================

    def _classify_reply_with_ai(
        self,
        reply_text: str,
        original_comment_text: str,
        original_post_caption: str,
    ) -> dict:
        try:
            bot_personality_id = self._get_bot_personality_id()

            if not bot_personality_id:
                return self._classify_reply_fallback(reply_text)

            prompt = f"""
Classify this Instagram reply from a prospect.

INPUT:
- ORIGINAL_PUBLIC_COMMENT = {original_comment_text}
- ORIGINAL_POST_CAPTION = {original_post_caption}
- PROSPECT_REPLY = {reply_text}

VALID classification values:
- interested
- question
- neutral
- negative
- irrelevant

RULES:
- Use "interested" when the reply clearly shows intent, contact desire, service interest, or buying intent.
- Use "question" when the reply asks for information, details, price, or next steps.
- Use "neutral" for thanks, short acknowledgments, or low-intent replies.
- Use "negative" for rejection or stop signals.
- Use "irrelevant" if it does not relate to the interaction.

Return ONLY valid JSON:

{{
  "classification": "question",
  "reason": "The prospect is asking for more information."
}}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                prompt,
            )

            if not ok_ai or not raw_response:
                return self._classify_reply_fallback(reply_text)

            parsed = self._parse_json(raw_response)

            if not parsed:
                return self._classify_reply_fallback(reply_text)

            classification = str(
                parsed.get("classification") or "neutral"
            ).strip().lower()

            reason = str(parsed.get("reason") or "").strip()

            if classification not in {
                "interested",
                "question",
                "neutral",
                "negative",
                "irrelevant",
            }:
                classification = "neutral"

            return {
                "classification": classification,
                "reason": reason,
            }

        except Exception:
            return self._classify_reply_fallback(reply_text)

    def _classify_reply_fallback(self, reply_text: str) -> dict:
        text = self._normalize_text(reply_text)

        if any(
            x in text
            for x in [
                "more info",
                "information",
                "details",
                "price",
                "how much",
                "info",
            ]
        ):
            return {
                "classification": "question",
                "reason": "Asked for more information.",
            }

        if any(
            x in text
            for x in [
                "interested",
                "call me",
                "phone",
                "number",
                "contact me",
                "i want it",
            ]
        ):
            return {
                "classification": "interested",
                "reason": "Shows strong interest.",
            }

        if any(x in text for x in ["thanks", "thank you", "gracias"]):
            return {
                "classification": "neutral",
                "reason": "Neutral gratitude.",
            }

        if any(x in text for x in ["no thanks", "stop", "not interested"]):
            return {
                "classification": "negative",
                "reason": "Negative reply.",
            }

        return {
            "classification": "neutral",
            "reason": "No clear intent detected.",
        }

    # =========================================================
    # IA - RESPUESTA AUTOMÁTICA
    # =========================================================

    def _generate_follow_up_reply_with_ai(
        self,
        reply_text: str,
        classification: str,
        follow_up_phone: str,
        original_comment_text: str,
        original_post_caption: str,
    ) -> str:
        try:
            if not follow_up_phone:
                self.log.warning("No hay follow_up_phone configurado en la campaña.")
                return ""

            bot_personality_id = self._get_bot_personality_id()

            if not bot_personality_id:
                return self._build_follow_up_reply_fallback(follow_up_phone)

            prompt = f"""
Write ONE short public Instagram reply to a prospect.

CONTEXT:
- ORIGINAL_PUBLIC_COMMENT = {original_comment_text}
- ORIGINAL_POST_CAPTION = {original_post_caption}
- PROSPECT_REPLY = {reply_text}
- CLASSIFICATION = {classification}
- PHONE_TO_SHARE = {follow_up_phone}

GOAL:
- Respond naturally and briefly.
- Include the phone number naturally.
- Sound human, calm, and helpful.
- Do not sound robotic or overly salesy.
- Do not use hashtags.
- Do not use links.
- Do not use email.
- Do not overexplain.
- Maximum 18 words.
- Single line only.
- 0 or 1 emoji only if natural.

STYLE:
- If classification is "question", sound helpful and informative.
- If classification is "interested", sound warm and direct.
- Keep it low-pressure.

Return ONLY valid JSON:

{{
  "reply_text": "Thanks for reaching out — you can call us at 312-000-0000."
}}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                prompt,
            )

            if not ok_ai or not raw_response:
                return self._build_follow_up_reply_fallback(follow_up_phone)

            parsed = self._parse_json(raw_response)

            if not parsed:
                return self._build_follow_up_reply_fallback(follow_up_phone)

            reply = str(parsed.get("reply_text") or "").strip()
            reply = self._sanitize_follow_up_reply(reply, follow_up_phone)

            if not reply:
                return self._build_follow_up_reply_fallback(follow_up_phone)

            return reply

        except Exception as e:
            self.log.warning("Error generando respuesta follow-up con IA: %r", e)
            return self._build_follow_up_reply_fallback(follow_up_phone)

    def _build_follow_up_reply_fallback(self, follow_up_phone: str) -> str:
        if not follow_up_phone:
            return ""

        return f"Thanks for reaching out. You can call us at {follow_up_phone}."

    def _sanitize_follow_up_reply(self, reply_text: str, follow_up_phone: str) -> str:
        try:
            text = str(reply_text or "").strip()

            if not text:
                return ""

            text = " ".join(text.split())

            if follow_up_phone not in text:
                return ""

            banned_fragments = [
                "http://",
                "https://",
                "www.",
                "@gmail.com",
                "email us",
                "email me",
            ]

            lower = text.lower()

            if any(item in lower for item in banned_fragments):
                return ""

            if len(text) > 180:
                text = text[:180].strip()

            return text

        except Exception:
            return ""

    # =========================================================
    # JSON
    # =========================================================

    def _parse_json(self, raw_response) -> Optional[dict]:
        try:
            if isinstance(raw_response, dict):
                if "response" in raw_response and isinstance(
                    raw_response["response"],
                    str,
                ):
                    text = raw_response["response"].strip()
                else:
                    text = json.dumps(raw_response, ensure_ascii=False)
            else:
                text = str(raw_response).strip()

            if text.startswith("```"):
                text = text.replace("```json", "").replace("```", "").strip()

            start = text.find("{")
            end = text.rfind("}")

            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]

            parsed = json.loads(text)

            return parsed if isinstance(parsed, dict) else None

        except Exception:
            return None