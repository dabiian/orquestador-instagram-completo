import os
import json
import random
import re
from typing import List, Optional, TypedDict

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from app.core.interfaces import IBrowser, ITask
from app.utils.logger import get_logger
from app.api.prospecting_api import ProspectingAPI
from app.services.email_alert_service import EmailAlertService
from app.services.instagram_conversation_flow_service import InstagramConversationFlowService
from app.services.instagram_config_alert_service import InstagramConfigAlertService
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService
from app.config.locators.instagram_dm_locators import InstagramDMLocators


class DMTaskResult(TypedDict):
    ok: bool
    message: str
    unread_found_initial: int
    chats_processed: int
    replies_sent: int
    failed_chats: int
    processed_chat_names: List[str]


class InteractWithInstagramUnreadMessagesTask(ITask):
    """
    Flujo:
    1. Abre inbox de Instagram
    2. Busca chats no leídos
    3. Abre chat no leído
    4. Lee historial visible
    5. Si la cuenta es business:
       - valida que el contacto sea prospecto relacionado
       - clasifica el mensaje como interested/question/neutral/etc
       - si hay interés o pregunta, envía alerta por correo
       - responde de forma comercial/contextual
    6. Si no es business:
       - responde como cuenta personal usando el prompt casual
    7. Escribe y envía el DM
    """

    def __init__(self, browser: IBrowser, data: dict, account_api=None, ai_api=None):
        self.browser = browser
        self.data = data or {}
        self.account_api = account_api
        self.ai_api = ai_api
        self.log = get_logger(self.__class__.__name__)

        self.prospecting_api = ProspectingAPI()
        self.email_alert_service = EmailAlertService(logger=self.log)
        self.conversation_flow_service = InstagramConversationFlowService(logger=self.log)
        self.config_alert_service = InstagramConfigAlertService(logger=self.log)

    def execute(self) -> str:
        try:
            self.browser.time_sleep(random.randint(4, 6))
            self.log.info("Starting InteractWithInstagramUnreadMessagesTask.")

            account_id = self._get_social_media_account_id()
            if not account_id:
                return "✗ No se encontró social_media_account.id"

            is_business = self._is_business_account()
            active_campaign = self._get_active_campaign_for_dm()

            self.log.info(
                "DM task account_id=%s | is_business=%s",
                account_id,
                is_business,
            )

            ok_inbox = self._open_messages_inbox()
            if not ok_inbox:
                return "✗ No se pudo abrir el inbox de mensajes"

            initial_unread = self._count_unread_chats()
            if initial_unread <= 0:
                return "✗ No se encontraron chats no leídos"

            processed_chat_names: List[str] = []
            replies_sent = 0
            failed_chats = 0
            chats_processed = 0
            emails_sent = 0
            prospect_chats = 0
            personal_chats = 0

            max_loops = min(max(initial_unread + 5, 10), 50)

            for loop_idx in range(1, max_loops + 1):
                self.log.info(
                    "Loop unread chats %s/%s | procesados=%s | enviados=%s | fallidos=%s | emails=%s",
                    loop_idx,
                    max_loops,
                    chats_processed,
                    replies_sent,
                    failed_chats,
                    emails_sent,
                )

                ok_inbox = self._open_messages_inbox()
                if not ok_inbox:
                    self.log.warning("No se pudo reabrir el inbox en iteración %s", loop_idx)
                    break

                unread_chats = self._get_unread_chat_elements()
                if not unread_chats:
                    self.log.info("Ya no hay chats no leídos. Fin del proceso.")
                    break

                opened_name = self._open_next_unread_chat(
                    unread_chats,
                    processed_chat_names,
                )

                if not opened_name:
                    self.log.info("No se pudo abrir un nuevo chat no leído sin repetir.")
                    break

                processed_chat_names.append(opened_name)
                chats_processed += 1

                self.browser.time_sleep(random.randint(2, 4))

                contact_name = self._get_open_chat_contact_name() or opened_name
                visible_messages = self._get_visible_chat_messages()

                self.log.info("Contacto abierto: %s", contact_name)
                self.log.info("Mensajes visibles: %s", len(visible_messages))

                if not visible_messages:
                    failed_chats += 1
                    self.log.warning(
                        "No se pudo leer historial visible del chat: %s",
                        opened_name,
                    )
                    continue

                conversation_context = self._build_conversation_context(
                    visible_messages,
                    max_messages=20,
                )

                self.log.info("Contexto conversación:\n%s", conversation_context)

                related_prospect = None
                dm_classification = "neutral"
                dm_classification_reason = ""

                related_prospect = self._resolve_related_prospect_from_dm(
                    contact_name=contact_name,
                    messages=visible_messages,
                )

                if related_prospect:
                    prospect_chats += 1

                    self.log.info(
                        "Chat relacionado con prospecto | prospect_id=%s | username=%s | account_id=%s | is_business=%s",
                        related_prospect.get("id"),
                        related_prospect.get("username"),
                        account_id,
                        is_business,
                    )

                    classification_payload = self._classify_dm_interest_with_ai(
                        messages=visible_messages,
                        related_prospect=related_prospect,
                    )

                    dm_classification = str(
                        classification_payload.get("classification") or "neutral"
                    ).strip().lower()

                    dm_classification_reason = str(
                        classification_payload.get("reason") or ""
                    ).strip()

                    self.log.info(
                        "DM clasificado | contact_name=%s | classification=%s | reason=%s",
                        contact_name,
                        dm_classification,
                        dm_classification_reason,
                    )

                    self._create_dm_inbound_interaction_safe(
                        related_prospect=related_prospect,
                        messages=visible_messages,
                        classification=dm_classification,
                        social_media_account_id=account_id,
                    )

                    if dm_classification in {"interested", "question"}:
                        self._mark_dm_prospect_interested_safe(
                            related_prospect=related_prospect,
                        )

                        email_ok = self._send_dm_interest_email_alert_once(
                            related_prospect=related_prospect,
                            contact_name=contact_name,
                            messages=visible_messages,
                            classification=dm_classification,
                            reason=dm_classification_reason,
                            social_media_account_id=account_id,
                        )

                        if email_ok:
                            emails_sent += 1

                    # Facebook's response/data/quote behaviour is represented
                    # here by a persistent Instagram-native conversation flow.
                    # It runs after classification so the normal alert/DB
                    # pipeline remains intact, but before the generic reply
                    # generator so an active question flow cannot be lost.
                    flow_result = None
                    try:
                        username_for_flow = str(
                            related_prospect.get("username")
                            or self._extract_dm_other_username(visible_messages, contact_name)
                            or contact_name
                        ).strip()
                        selected_service = str(
                            related_prospect.get("selected_service")
                            or related_prospect.get("service")
                            or ""
                        ).strip()
                        if active_campaign and username_for_flow:
                            last_incoming = self._get_last_incoming_message(visible_messages)
                            incoming_text = str((last_incoming or {}).get("text") or "").strip()
                            if incoming_text:
                                flow_result = self.conversation_flow_service.handle(
                                    campaign=active_campaign,
                                    username=username_for_flow,
                                    incoming_text=incoming_text,
                                    selected_service=selected_service,
                                )
                    except Exception as flow_exc:
                        self.log.warning("Conversation flow no pudo procesar DM: %r", flow_exc)
                        flow_result = None

                    if flow_result and flow_result.get("handled"):
                        flow_type = str(flow_result.get("flow_type") or "")
                        if flow_result.get("human_takeover") and related_prospect:
                            try:
                                self.prospecting_api.update_prospect(related_prospect.get("id"), status="human_takeover")
                            except Exception as exc:
                                self.log.warning("No se pudo marcar HUMAN_TAKEOVER: %r", exc)
                        if (flow_result.get("completed") or flow_result.get("alert_ready")) and flow_type in {"data_request", "quote_request", "service_request"} and related_prospect:
                            event_code = str(flow_result.get("alert_event_code") or ("DATA" if flow_type == "data_request" else ("QUOTE" if flow_type == "quote_request" else "SERVICE")))
                            answers = ((flow_result.get("state") or {}).get("answers") or [])
                            answer_map = {str(a.get("number") or "").upper(): a.get("answer", "") for a in answers}
                            ctx = {
                                "ACCOUNT NAME": contact_name, "CATEGORY": related_prospect.get("industry_detected") or active_campaign.get("campaign_type"),
                                "TIMESTAMP": __import__('datetime').datetime.utcnow().isoformat(), "PROFILE URL": related_prospect.get("profile_url") or "",
                                "EXACT REPLY TEXT": incoming_text, "INTENT": event_code, "Q1 ANSWER": answer_map.get("Q1", "Not answered"),
                                "Q2 ANSWER": answer_map.get("Q2", "Not answered"), "Q3 ANSWER": answer_map.get("Q3", "Not answered"), "Q4 ANSWER": answer_map.get("Q4", "Not answered"),
                                "FACEBOOK POST LINK": related_prospect.get("profile_url") or "", "CAMPAIGN EMAIL": active_campaign.get("business_email") or active_campaign.get("email"),
                                "ALERT WHATSAPP": active_campaign.get("alert_whatsapp") or active_campaign.get("owner_alert_whatsapp"),
                            }
                            alert_result = self.config_alert_service.send(self.conversation_flow_service._campaign_type(active_campaign), event_code, ctx)
                            self.log.info("[config-alert] DM event=%s result=%s", event_code, alert_result)
                        dm_classification = "question" if flow_type in {"data_request", "quote_request", "service_request"} else dm_classification
                        dm_classification_reason = (
                            "Instagram data/quote request flow"
                            if flow_result.get("flow_type") in {"data_request", "quote_request"}
                            else dm_classification_reason
                        )
                        reply_text = "" if flow_result.get("human_takeover") else str(flow_result.get("reply") or "").strip()
                    else:
                        reply_text = self._generate_dm_reply_from_history(
                            visible_messages,
                            use_contact_name=True,
                            related_prospect=related_prospect,
                            dm_classification=dm_classification,
                            dm_classification_reason=dm_classification_reason,
                        )

                else:
                    personal_chats += 1

                    if is_business:
                        failed_chats += 1
                        self.log.info(
                            "Chat omitido porque no pertenece a un prospecto relacionado | contact_name=%s | opened_name=%s | account_id=%s",
                            contact_name,
                            opened_name,
                            account_id,
                        )
                        continue

                    self.log.info(
                        "Cuenta personal: chat no relacionado con prospecto, se responderá normal | contact_name=%s | account_id=%s",
                        contact_name,
                        account_id,
                    )
                    reply_text = self._generate_dm_reply_from_history(
                        visible_messages,
                        use_contact_name=True,
                        related_prospect=None,
                        dm_classification="neutral",
                        dm_classification_reason="",
                    )

                if not reply_text:
                    failed_chats += 1
                    self.log.warning("No se pudo generar reply para el chat: %s", opened_name)
                    continue

                self.log.info("Reply DM generado: %s", reply_text)

                sent_ok = self._send_dm_message(reply_text)
                self.log.info("DM enviado correctamente: %s", sent_ok)

                if sent_ok:
                    replies_sent += 1

                    if related_prospect:
                        self._create_dm_outbound_interaction_safe(
                            related_prospect=related_prospect,
                            reply_text=reply_text,
                            classification=dm_classification,
                            social_media_account_id=account_id,
                        )
                else:
                    failed_chats += 1

                self.browser.time_sleep(random.randint(2, 4))

            if chats_processed == 0:
                return "✗ No se pudo procesar ningún chat no leído"

            return (
                f"✓ Chats no leídos atendidos | "
                f"unread_inicial={initial_unread} | "
                f"procesados={chats_processed} | "
                f"prospect_chats={prospect_chats} | "
                f"personal_chats={personal_chats} | "
                f"replies_ok={replies_sent} | "
                f"emails_ok={emails_sent} | "
                f"fallidos={failed_chats} | "
                f"chats={processed_chat_names}"
            )

        except Exception as e:
            self.log.error("Error en InteractWithInstagramUnreadMessagesTask: %r", e)
            return f"✗ Error en InteractWithInstagramUnreadMessagesTask: {repr(e)}"

    # =========================================================
    # NAVEGACIÓN INBOX
    # =========================================================

    def _open_messages_inbox(self) -> bool:
        try:
            if not self.browser.is_visible(InstagramDMLocators.MESSAGES_NAV):
                self.log.warning("No se encontró el acceso a Mensajes.")
                return False

            nav_elements = self.browser.obtener_elementos(
                InstagramDMLocators.MESSAGES_NAV,
                time_x=10,
            )

            if not nav_elements:
                self.log.warning("No se pudo obtener el elemento de Mensajes.")
                return False

            nav_el = nav_elements[0]

            try:
                ActionChains(self.browser.driver).move_to_element(nav_el).pause(
                    random.uniform(0.3, 0.8)
                ).perform()
                self.log.info("Hover aplicado sobre Mensajes.")
            except Exception as e:
                self.log.warning("Falló hover sobre Mensajes: %r", e)

            self.browser.time_sleep(random.randint(1, 2))

            try:
                nav_el.click()
                self.log.info("Click directo en Mensajes OK.")
            except Exception:
                try:
                    ActionChains(self.browser.driver).move_to_element(nav_el).pause(
                        random.uniform(0.2, 0.5)
                    ).click().perform()
                    self.log.info("Click con ActionChains en Mensajes OK.")
                except Exception:
                    try:
                        self.browser.driver.execute_script(
                            InstagramDMLocators.CLICK_ELEMENT_SCRIPT,
                            nav_el,
                        )
                        self.log.info("Click por JS en Mensajes OK.")
                    except Exception as e:
                        self.log.warning("No se pudo hacer click en Mensajes: %r", e)
                        return False

            self.browser.time_sleep(random.randint(3, 5))

            inbox_visible = self.browser.is_visible(InstagramDMLocators.INBOX_LIST)
            self.log.info("Inbox visible tras abrir Mensajes: %s", inbox_visible)

            return bool(inbox_visible)

        except Exception as e:
            self.log.warning("Error abriendo inbox de mensajes: %r", e)
            return False

    def _get_unread_chat_elements(self) -> List:
        try:
            if not self.browser.is_visible(InstagramDMLocators.INBOX_LIST):
                self.log.warning("La lista del inbox no está visible.")
                return []

            elements = self.browser.driver.find_elements(
                By.XPATH,
                InstagramDMLocators.UNREAD_CHAT_ITEMS,
            )

            self.log.info("Chats no leídos detectados: %s", len(elements))
            return elements

        except Exception as e:
            self.log.warning("Error obteniendo chats no leídos: %r", e)
            return []

    def _get_chat_name(self, chat_element) -> str:
        try:
            name_el = chat_element.find_element(
                By.XPATH,
                InstagramDMLocators.CHAT_TITLE_REL,
            )
            return (name_el.text or "").strip()
        except Exception:
            return ""

    def _open_next_unread_chat(
        self,
        unread_chats: List,
        processed_chat_names: Optional[List[str]] = None,
    ) -> Optional[str]:
        processed_chat_names = processed_chat_names or []

        processed_norm = {
            (name or "").strip().lower()
            for name in processed_chat_names
        }

        for idx, chat_el in enumerate(unread_chats, start=1):
            try:
                chat_name = self._get_chat_name(chat_el)
                chat_name_norm = (chat_name or "").strip().lower()

                if chat_name_norm and chat_name_norm in processed_norm:
                    self.log.info(
                        "Saltando chat ya procesado %s/%s: %s",
                        idx,
                        len(unread_chats),
                        chat_name,
                    )
                    continue

                self.log.info(
                    "Intentando abrir siguiente chat no leído %s/%s: %s",
                    idx,
                    len(unread_chats),
                    chat_name or "[sin nombre]",
                )

                try:
                    self.browser.driver.execute_script(
                        InstagramDMLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                        chat_el,
                    )
                except Exception:
                    pass

                self.browser.time_sleep(random.uniform(0.8, 1.5))

                try:
                    ActionChains(self.browser.driver).move_to_element(chat_el).pause(
                        random.uniform(0.2, 0.5)
                    ).perform()
                except Exception:
                    pass

                self.browser.time_sleep(random.uniform(0.5, 1.0))

                try:
                    chat_el.click()
                except Exception:
                    try:
                        ActionChains(self.browser.driver).move_to_element(chat_el).pause(
                            random.uniform(0.2, 0.5)
                        ).click().perform()
                    except Exception:
                        try:
                            self.browser.driver.execute_script(
                                InstagramDMLocators.CLICK_ELEMENT_SCRIPT,
                                chat_el,
                            )
                        except Exception as e:
                            self.log.warning(
                                "No se pudo abrir el chat '%s': %r",
                                chat_name,
                                e,
                            )
                            continue

                self.browser.time_sleep(random.randint(3, 5))

                if self.browser.is_visible(InstagramDMLocators.DM_CHAT_ROOT):
                    return chat_name or "chat_no_leido"

            except Exception as e:
                self.log.warning("Error abriendo chat no leído: %r", e)
                continue

        return None

    # =========================================================
    # LECTURA DEL CHAT
    # =========================================================

    def _get_open_chat_contact_name(self) -> str:
        try:
            elems = self.browser.driver.find_elements(
                By.XPATH,
                InstagramDMLocators.DM_CONTACT_NAME,
            )

            for el in elems:
                name = (el.text or "").strip()
                if name:
                    self.log.info("Nombre del contacto detectado: %s", name)
                    return name

            return ""

        except Exception as e:
            self.log.warning("Error obteniendo nombre del contacto: %r", e)
            return ""

    def _get_visible_chat_messages(self) -> list[dict]:
        try:
            payload = self.browser.driver.execute_script(
                InstagramDMLocators.GET_VISIBLE_CHAT_MESSAGES_SCRIPT
            ) or {}

            messages = payload.get("messages") or []
            contact_name = str(payload.get("contact_name") or "").strip()

            self.log.info(
                "Mensajes visibles detectados=%s | contacto=%s",
                len(messages),
                contact_name,
            )

            cleaned = []
            seen = set()

            for idx, msg in enumerate(messages, start=1):
                sender = str(msg.get("sender") or "").strip()
                text = str(msg.get("text") or "").strip()
                time_text = str(msg.get("time") or "").strip()
                profile_href = str(msg.get("profile_href") or "").strip()

                if not text:
                    continue

                dedupe_key = f"{sender}|{time_text}|{text}|{profile_href}"
                if dedupe_key in seen:
                    continue

                seen.add(dedupe_key)

                cleaned.append({
                    "index": idx,
                    "sender": sender,
                    "text": text,
                    "time": time_text,
                    "profile_href": profile_href,
                    "contact_name": contact_name,
                })

            return cleaned

        except Exception as e:
            self.log.warning("Error obteniendo mensajes visibles del chat: %r", e)
            return []

    def _build_conversation_context(self, messages: list[dict], max_messages: int = 20) -> str:
        try:
            if not messages:
                return ""

            trimmed = messages[-max_messages:]
            lines = []

            for msg in trimmed:
                sender = "Contacto" if msg.get("sender") == "other" else "Yo"
                text = str(msg.get("text") or "").strip()
                time_text = str(msg.get("time") or "").strip()

                if not text:
                    continue

                if time_text:
                    lines.append(f"[{time_text}] {sender}: {text}")
                else:
                    lines.append(f"{sender}: {text}")

            return "\n".join(lines).strip()

        except Exception as e:
            self.log.warning("Error construyendo contexto de conversación: %r", e)
            return ""

    def _get_last_incoming_message(self, messages: list[dict]) -> Optional[dict]:
        try:
            for msg in reversed(messages or []):
                if msg.get("sender") == "other":
                    return msg
            return None
        except Exception:
            return None

    # =========================================================
    # BASE HELPERS
    # =========================================================

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _normalize_username(self, value: str) -> str:
        try:
            return str(value or "").replace("@", "").strip().lower()
        except Exception:
            return ""

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

    def _parse_json_object(self, raw_response) -> Optional[dict]:
        try:
            content = raw_response

            if isinstance(content, dict) and "response" in content:
                content = content["response"]

            if isinstance(content, dict):
                return content

            text = str(content or "").strip()

            if text.startswith("```"):
                text = text.replace("```json", "").replace("```", "").strip()

            start = text.find("{")
            end = text.rfind("}")

            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]

            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None

        except Exception as e:
            self.log.warning("No se pudo parsear JSON/dict: %r", e)
            return None

    # =========================================================
    # SOCIAL ACCOUNT / CAMPAÑA
    # =========================================================

    def _get_social_media_account(self) -> dict:
        try:
            value = self.data.get("social_media_account") or {}
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _get_social_media_account_id(self) -> Optional[int]:
        try:
            social_media_account = self._get_social_media_account()

            value = social_media_account.get("id")
            if value:
                return int(value)

            value = self.data.get("social_media_account_id")
            if value:
                return int(value)

            return None

        except Exception:
            return None

    def _get_social_media_account_kind(self) -> str:
        try:
            social_media_account = self._get_social_media_account()

            value = (
                social_media_account.get("account_kind")
                or social_media_account.get("sa_account_kind")
                or social_media_account.get("social_account_kind")
                or social_media_account.get("account_type")
                or social_media_account.get("kind")
                or self.data.get("account_kind")
                or self.data.get("sa_account_kind")
                or self.data.get("social_account_kind")
                or self.data.get("account_type")
                or ""
            )

            return str(value or "").strip().lower()

        except Exception:
            return ""

    def _is_business_account(self) -> bool:
        kind = self._get_social_media_account_kind()

        return kind in {
            "business",
            "bussiness",
            "business_account",
            "empresa",
            "negocio",
            "commercial",
            "company",
        }

    def _get_bot_personality(self) -> dict:
        try:
            social_media_account = self._get_social_media_account()
            value = social_media_account.get("bot_personality") or {}
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _get_bot_personality_id(self) -> Optional[int]:
        try:
            bot_personality = self._get_bot_personality()
            value = bot_personality.get("id")
            return int(value) if value is not None else None
        except Exception:
            return None

    def _get_active_campaign_for_dm(self) -> dict:
        try:
            account_id = self._get_social_media_account_id()

            if not account_id:
                return {}

            ok_campaign, campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            if ok_campaign and isinstance(campaign, dict):
                return campaign

            return {}

        except Exception as e:
            self.log.warning("No se pudo obtener campaña activa para DM: %r", e)
            return {}

    # =========================================================
    # PROSPECTO RELACIONADO
    # =========================================================

    def _extract_instagram_username_from_url(self, value: str) -> str:
        try:
            value = str(value or "").strip()

            if not value:
                return ""

            value = value.replace("https://www.instagram.com/", "")
            value = value.replace("https://instagram.com/", "")
            value = value.replace("http://www.instagram.com/", "")
            value = value.replace("http://instagram.com/", "")
            value = value.strip("/")

            if "/" in value:
                value = value.split("/")[0]

            value = value.split("?")[0].strip()
            value = value.replace("@", "").strip().lower()

            if not value:
                return ""

            if value in {"direct", "p", "reel", "stories", "explore"}:
                return ""

            return value

        except Exception:
            return ""

    def _extract_dm_other_username(self, messages: list[dict], contact_name: str = "") -> str:
        try:
            for msg in reversed(messages or []):
                if msg.get("sender") != "other":
                    continue

                profile_href = str(msg.get("profile_href") or "").strip()
                username = self._extract_instagram_username_from_url(profile_href)

                if username:
                    return username

            return self._normalize_username(contact_name)

        except Exception:
            return self._normalize_username(contact_name)

    def _resolve_related_prospect_from_dm(
        self,
        contact_name: str,
        messages: list[dict],
    ) -> Optional[dict]:
        try:
            campaign = self._get_active_campaign_for_dm()
            campaign_id = campaign.get("id")

            if not campaign_id:
                self.log.warning("No hay campaña activa para validar prospecto en DM.")
                return None

            dm_username = self._extract_dm_other_username(messages, contact_name)

            if dm_username:
                prospect = self._get_campaign_prospect_by_username(
                    campaign_id=campaign_id,
                    username=dm_username,
                )

                if prospect:
                    return prospect

            prospect = self._get_campaign_prospect_by_contact_name(
                campaign_id=campaign_id,
                contact_name=contact_name,
            )

            if prospect:
                return prospect

            self.log.info(
                "DM no relacionado con prospectos | campaign_id=%s | dm_username=%s | contact_name=%s",
                campaign_id,
                dm_username,
                contact_name,
            )

            return None

        except Exception as e:
            self.log.warning("Error resolviendo prospecto relacionado desde DM: %r", e)
            return None

    def _get_campaign_prospect_by_username(
        self,
        campaign_id: int,
        username: str,
    ) -> Optional[dict]:
        try:
            username_norm = self._normalize_username(username)

            if not username_norm:
                return None

            query_attempts = [
                {
                    "campaign_id": campaign_id,
                    "username": username_norm,
                },
                {
                    "campaign": campaign_id,
                    "username": username_norm,
                },
                {
                    "campaign_id": campaign_id,
                    "search": username_norm,
                },
                {
                    "campaign": campaign_id,
                    "search": username_norm,
                },
            ]

            for params in query_attempts:
                ok, payload = self.prospecting_api._get(
                    "prospecting/prospects/",
                    params=params,
                )[:2]

                if not ok:
                    continue

                prospects = self._normalize_api_list_payload(payload)

                for prospect in prospects:
                    prospect_username = self._normalize_username(
                        prospect.get("username")
                        or prospect.get("instagram_username")
                        or prospect.get("handle")
                        or ""
                    )

                    profile_url_username = self._extract_instagram_username_from_url(
                        prospect.get("profile_url")
                        or prospect.get("instagram_url")
                        or ""
                    )

                    if prospect_username == username_norm:
                        return prospect

                    if profile_url_username == username_norm:
                        return prospect

            return None

        except Exception as e:
            self.log.warning(
                "Error buscando prospecto por username | username=%s | error=%r",
                username,
                e,
            )
            return None

    def _get_campaign_prospect_by_contact_name(
        self,
        campaign_id: int,
        contact_name: str,
    ) -> Optional[dict]:
        try:
            contact_name_norm = self._normalize_text(contact_name)

            if not contact_name_norm:
                return None

            ok, payload = self.prospecting_api._get(
                "prospecting/prospects/",
                params={
                    "campaign_id": campaign_id,
                },
            )[:2]

            if not ok:
                return None

            prospects = self._normalize_api_list_payload(payload)

            for prospect in prospects:
                username = self._normalize_text(prospect.get("username") or "")
                display_name = self._normalize_text(prospect.get("display_name") or "")
                full_name = self._normalize_text(prospect.get("full_name") or "")
                name = self._normalize_text(prospect.get("name") or "")

                candidates = {
                    username,
                    display_name,
                    full_name,
                    name,
                }

                candidates = {x for x in candidates if x}

                if contact_name_norm in candidates:
                    return prospect

            return None

        except Exception as e:
            self.log.warning(
                "Error buscando prospecto por contact_name | contact_name=%s | error=%r",
                contact_name,
                e,
            )
            return None

    # =========================================================
    # CLASIFICACIÓN DE INTERÉS EN DM
    # =========================================================

    def _classify_dm_interest_with_ai(
        self,
        messages: list[dict],
        related_prospect: Optional[dict] = None,
    ) -> dict:
        try:
            last_incoming = self._get_last_incoming_message(messages)

            if not last_incoming:
                return {
                    "classification": "neutral",
                    "reason": "No incoming message found.",
                }

            last_message_text = str(last_incoming.get("text") or "").strip()
            conversation_context = self._build_conversation_context(messages, max_messages=20)

            if not self.ai_api:
                return self._classify_dm_interest_fallback(last_message_text)

            bot_personality_id = self._get_bot_personality_id()

            if not bot_personality_id:
                return self._classify_dm_interest_fallback(last_message_text)

            prospect_context = json.dumps(related_prospect or {}, ensure_ascii=False)[:1200]

            prompt = f"""
Classify this Instagram DM from a business prospect.

RELATED_PROSPECT:
{prospect_context}

VISIBLE_CONVERSATION_HISTORY:
{conversation_context}

LAST_PROSPECT_MESSAGE:
{last_message_text}

VALID classification values:
- interested
- question
- neutral
- negative
- irrelevant

RULES:
- Use "interested" if the person shows intent to buy, hire, schedule, contact, receive service, or says they are interested.
- Use "question" if the person asks for more information, price, quote, availability, service details, booking, appointment, or next steps.
- Use "neutral" for greetings, thanks, or low-intent messages.
- Use "negative" for rejection, complaints, stop signals, or not interested.
- Use "irrelevant" if unrelated to the business or service.

Return ONLY valid JSON:

{{
  "classification": "interested",
  "reason": "The person says they are interested in the services and asks for more information."
}}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                prompt,
            )

            if not ok_ai or not raw_response:
                return self._classify_dm_interest_fallback(last_message_text)

            parsed = self._parse_json_object(raw_response)

            if not parsed:
                return self._classify_dm_interest_fallback(last_message_text)

            classification = str(parsed.get("classification") or "neutral").strip().lower()
            reason = str(parsed.get("reason") or "").strip()

            if classification not in {"interested", "question", "neutral", "negative", "irrelevant"}:
                classification = "neutral"

            return {
                "classification": classification,
                "reason": reason,
            }

        except Exception as e:
            self.log.warning("Error clasificando interés de DM con IA: %r", e)
            return {
                "classification": "neutral",
                "reason": "Classification error.",
            }

    def _classify_dm_interest_fallback(self, text: str) -> dict:
        text_norm = self._normalize_text(text)

        negative_words = [
            "not interested",
            "no thanks",
            "stop",
            "don't contact",
            "do not contact",
            "no me interesa",
            "no gracias",
        ]

        interested_words = [
            "interested",
            "i'm interested",
            "im interested",
            "i am interested",
            "i would like",
            "i want",
            "need service",
            "need cleaning",
            "call me",
            "contact me",
            "me interesa",
            "estoy interesado",
            "estoy interesada",
            "quiero",
            "necesito",
        ]

        question_words = [
            "more information",
            "more info",
            "information",
            "info",
            "details",
            "price",
            "pricing",
            "cost",
            "how much",
            "quote",
            "estimate",
            "availability",
            "available",
            "appointment",
            "booking",
            "book",
            "schedule",
            "service",
            "services",
            "información",
            "precio",
            "cuánto",
            "cotización",
            "disponible",
            "cita",
            "servicio",
            "servicios",
        ]

        if any(x in text_norm for x in negative_words):
            return {
                "classification": "negative",
                "reason": "Negative or stop signal detected.",
            }

        if any(x in text_norm for x in interested_words):
            return {
                "classification": "interested",
                "reason": "The message shows clear interest in the services.",
            }

        if any(x in text_norm for x in question_words):
            return {
                "classification": "question",
                "reason": "The message asks for information or service details.",
            }

        return {
            "classification": "neutral",
            "reason": "No clear business intent detected.",
        }

    # =========================================================
    # EMAIL ALERT DM
    # =========================================================

    def _get_business_alert_email(self) -> str:
        try:
            social_media_account = self._get_social_media_account()
            campaign = self._get_active_campaign_for_dm()

            email_to = (
                self.data.get("email_to")
                or campaign.get("follow_up_email")
                or campaign.get("notification_email")
                or social_media_account.get("notification_email")
                or social_media_account.get("email")
                or os.getenv("FOLLOW_UP_ALERT_EMAIL")
                or os.getenv("SMTP_ALERT_TO")
                or ""
            )

            return str(email_to or "").strip()

        except Exception:
            return ""

    def _already_dm_email_alerted(
        self,
        related_prospect: Optional[dict],
        messages: list[dict],
        email_to: str,
    ) -> bool:
        try:
            related_prospect = related_prospect or {}
            prospect_id = related_prospect.get("id")

            if not prospect_id:
                return False

            last_incoming = self._get_last_incoming_message(messages)
            last_message_text = str(last_incoming.get("text") or "").strip() if last_incoming else ""

            if not last_message_text:
                return False

            target_text = self._normalize_text(last_message_text)
            email_to_norm = self._normalize_text(email_to)

            ok, payload = self.prospecting_api._get(
                "prospecting/prospect-interactions/",
                params={
                    "prospect_id": prospect_id,
                    "interaction_type": "dm_email_alerted",
                    "direction": "outbound",
                },
            )[:2]

            if not ok:
                return False

            interactions = self._normalize_api_list_payload(payload)

            for item in interactions:
                content = self._normalize_text(item.get("content_text") or "")

                if target_text and target_text in content and email_to_norm in content:
                    return True

            return False

        except Exception:
            return False

    def _send_dm_interest_email_alert_once(
        self,
        related_prospect: dict,
        contact_name: str,
        messages: list[dict],
        classification: str,
        reason: str = "",
        social_media_account_id: Optional[int] = None,
    ) -> bool:
        try:
            if not related_prospect:
                return False

            prospect_id = related_prospect.get("id")
            if not prospect_id:
                return False

            email_to = (
                self.data.get("email_to")
                or related_prospect.get("follow_up_email")
                or related_prospect.get("notification_email")
                or os.getenv("FOLLOW_UP_ALERT_EMAIL")
                or os.getenv("SMTP_ALERT_TO")
                or ""
            )

            email_to = str(email_to or "").strip()

            if not email_to:
                self.log.warning("No se envió alerta DM: falta email destino.")
                return False

            last_incoming = self._get_last_incoming_message(messages)
            last_text = str(last_incoming.get("text") if last_incoming else "").strip()

            subject = f"[Instagram DM] Prospecto interesado: {contact_name}"

            body = "\n".join([
                "Se detectó un prospecto con interés desde DM de Instagram.",
                "",
                "DATOS DEL PROSPECTO",
                f"Prospect ID: {prospect_id}",
                f"Username: {related_prospect.get('username', '')}",
                f"Display name: {related_prospect.get('display_name', '')}",
                f"Profile URL: {related_prospect.get('profile_url', '')}",
                "",
                "INTERACCIÓN DETECTADA",
                f"Contacto en chat: {contact_name}",
                f"Clasificación: {classification}",
                f"Razón IA: {reason}",
                f"Último mensaje recibido: {last_text}",
                "",
                "CUENTA",
                f"social_media_account_id: {social_media_account_id}",
            ])

            sent_ok = self.email_alert_service.send_email(
                to_email=email_to,
                subject=subject,
                body=body,
            )

            if not sent_ok:
                self.log.warning(
                    "Falló envío de alerta DM | prospect_id=%s | email_to=%s",
                    prospect_id,
                    email_to,
                )
                return False

            try:
                self.prospecting_api.create_follow_up_alert(
                    prospect_id=prospect_id,
                    prospect_post_id=None,
                    interaction_id=None,
                    alert_type="email",
                    status="pending",
                    email_to=email_to,
                    payload_json={
                        "reason": "Prospecto respondió por DM con interés o pregunta",
                        "reply_text": last_text,
                        "classification": classification,
                        "classification_reason": reason,
                        "delivery": "sent",
                        "source": "InteractWithInstagramUnreadMessagesTask",
                        "social_media_account_id": social_media_account_id,
                    },
                )
            except Exception as e:
                self.log.warning(
                    "Correo DM enviado pero no se pudo registrar follow_up_alert | error=%r",
                    e,
                )

            try:
                self.prospecting_api.create_prospect_interaction(
                    prospect_id=prospect_id,
                    prospect_post_id=None,
                    social_media_account_id=social_media_account_id,
                    interaction_type="email_alerted",
                    direction="outbound",
                    content_text=f"Email alert sent to {email_to}",
                    classification=self._map_classification_for_db(classification),
                    status="success",
                )
            except Exception as e:
                self.log.warning(
                    "No se pudo registrar interaction email_alerted desde DM | error=%r",
                    e,
                )

            self.log.info(
                "Email de alerta DM enviado | to=%s | prospect_id=%s | account_id=%s",
                email_to,
                prospect_id,
                social_media_account_id,
            )

            return True

        except Exception as e:
            self.log.exception("Error enviando alerta DM por email: %s", e)
            return False

    def _build_dm_interest_email_subject(
        self,
        prospect_username: str,
        classification: str,
    ) -> str:
        classification = str(classification or "").strip().lower()
        prospect_username = str(prospect_username or "unknown").strip()

        if classification == "question":
            return f"[Instagram DM] Prospecto pidió información: {prospect_username}"

        return f"[Instagram DM] Prospecto interesado en servicios: {prospect_username}"

    def _build_dm_interest_email_body(
        self,
        related_prospect: Optional[dict],
        contact_name: str,
        messages: list[dict],
        classification: str,
        reason: str,
    ) -> str:
        campaign = self._get_active_campaign_for_dm()
        conversation_context = self._build_conversation_context(messages, max_messages=20)
        last_incoming = self._get_last_incoming_message(messages)
        last_message_text = str(last_incoming.get("text") or "").strip() if last_incoming else ""

        related_prospect = related_prospect or {}

        username = (
            related_prospect.get("username")
            or related_prospect.get("instagram_username")
            or self._extract_dm_other_username(messages, contact_name)
            or contact_name
        )

        profile_url = (
            related_prospect.get("profile_url")
            or related_prospect.get("instagram_url")
            or ""
        )

        campaign_name = str(
            campaign.get("name")
            or campaign.get("campaign_name")
            or campaign.get("title")
            or ""
        ).strip()

        parts = [
            "Se detectó un prospecto interesado desde Instagram DM.",
            "",
            "CAMPAÑA",
            f"Campaña: {campaign_name}",
            "",
            "PROSPECTO",
            f"Username / contacto: {username}",
            f"Nombre visible: {contact_name}",
            f"Profile URL: {profile_url}",
            "",
            "MENSAJE DETECTADO",
            f"Clasificación: {classification}",
            f"Razón: {reason}",
            f"Mensaje del prospecto: {last_message_text}",
            "",
            "HISTORIAL VISIBLE",
            conversation_context,
        ]

        return "\n".join(parts)

    def _register_dm_email_alert_interaction_safe(
        self,
        related_prospect: Optional[dict],
        messages: list[dict],
        email_to: str,
        classification: str,
    ) -> None:
        try:
            related_prospect = related_prospect or {}
            prospect_id = related_prospect.get("id")

            if not prospect_id:
                return

            last_incoming = self._get_last_incoming_message(messages)
            last_message_text = str(last_incoming.get("text") or "").strip() if last_incoming else ""

            self.prospecting_api.create_prospect_interaction(
                prospect_id=prospect_id,
                prospect_post_id=None,
                interaction_type="dm_email_alerted",
                direction="outbound",
                content_text=f"Email alert sent to {email_to}. DM: {last_message_text}",
                classification=classification,
                status="success",
            )

        except Exception as e:
            self.log.warning("No se pudo registrar dm_email_alerted: %r", e)

    # =========================================================
    # REGISTROS / ESTADO PROSPECTO
    # =========================================================

    def _create_dm_inbound_interaction_safe(
        self,
        related_prospect: dict,
        messages: list[dict],
        classification: str = "neutral",
        social_media_account_id: Optional[int] = None,
    ) -> Optional[dict]:
        try:
            if not related_prospect:
                return None

            prospect_id = related_prospect.get("id")
            if not prospect_id:
                return None

            last_incoming = self._get_last_incoming_message(messages)
            if not last_incoming:
                return None

            content_text = str(last_incoming.get("text") or "").strip()
            if not content_text:
                return None

            result = self.prospecting_api.create_prospect_interaction(
                prospect_id=prospect_id,
                prospect_post_id=None,
                social_media_account_id=social_media_account_id,
                interaction_type="dm_received",
                direction="inbound",
                content_text=content_text,
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
                "No se pudo registrar DM inbound | prospect=%s | account_id=%s | error=%r",
                related_prospect,
                social_media_account_id,
                e,
            )
            return None

    def _create_dm_outbound_interaction_safe(
        self,
        related_prospect: dict,
        reply_text: str,
        classification: str = "neutral",
        social_media_account_id: Optional[int] = None,
    ) -> Optional[dict]:
        try:
            if not related_prospect:
                return None

            prospect_id = related_prospect.get("id")
            if not prospect_id:
                return None

            reply_text = str(reply_text or "").strip()
            if not reply_text:
                return None

            result = self.prospecting_api.create_prospect_interaction(
                prospect_id=prospect_id,
                prospect_post_id=None,
                social_media_account_id=social_media_account_id,
                interaction_type="dm_sent",
                direction="outbound",
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
                "No se pudo registrar DM outbound | prospect=%s | account_id=%s | error=%r",
                related_prospect,
                social_media_account_id,
                e,
            )
            return None

    def _mark_dm_prospect_interested_safe(
        self,
        related_prospect: Optional[dict],
    ) -> None:
        try:
            related_prospect = related_prospect or {}
            prospect_id = related_prospect.get("id")

            if not prospect_id:
                return

            self.prospecting_api.update_prospect(
                prospect_id,
                status="interested",
            )

        except Exception as e:
            self.log.warning("No se pudo actualizar prospecto a interested: %r", e)

    # =========================================================
    # IA / RESPUESTA DM
    # =========================================================

    def _extract_reply_json(self, raw_response) -> Optional[dict]:
        try:
            parsed = self._parse_json_object(raw_response)

            if not isinstance(parsed, dict):
                return None

            reply_text = str(parsed.get("reply_text") or "").strip()

            if not reply_text:
                return None

            parsed["reply_text"] = reply_text
            return parsed

        except Exception as e:
            self.log.warning("No se pudo parsear JSON del reply: %r", e)
            return None

    def _get_business_follow_up_phone(self, related_prospect: Optional[dict] = None) -> str:
        try:
            related_prospect = related_prospect or {}
            social_media_account = self._get_social_media_account()
            campaign = self._get_active_campaign_for_dm()

            phone = (
                self.data.get("follow_up_phone")
                or related_prospect.get("follow_up_phone")
                or campaign.get("follow_up_phone")
                or social_media_account.get("follow_up_phone")
                or social_media_account.get("phone")
                or social_media_account.get("business_phone")
                or os.getenv("BUSINESS_DM_PHONE")
                or os.getenv("FOLLOW_UP_PHONE")
                or ""
            )

            return str(phone or "").strip()

        except Exception:
            return ""

    def _get_first_name_from_contact(self, contact_name: str) -> str:
        try:
            contact_name = str(contact_name or "").strip()

            if not contact_name:
                return ""

            first_name = contact_name.split()[0].strip()
            first_name = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9._-]", "", first_name)

            return first_name

        except Exception:
            return ""

    def _generate_dm_reply_from_history(
        self,
        messages: list[dict],
        use_contact_name: bool = True,
        related_prospect: Optional[dict] = None,
        dm_classification: str = "neutral",
        dm_classification_reason: str = "",
    ) -> str:
        try:
            if not messages:
                return ""

            contact_name = str(messages[-1].get("contact_name") or "").strip()
            last_incoming = self._get_last_incoming_message(messages)

            if not last_incoming:
                return ""

            last_message_text = str(last_incoming.get("text") or "").strip()
            conversation_context = self._build_conversation_context(messages, max_messages=20)

            if self._is_business_account() or related_prospect:
                return self._generate_business_dm_reply_from_history(
                    messages=messages,
                    use_contact_name=use_contact_name,
                    related_prospect=related_prospect,
                    dm_classification=dm_classification,
                    dm_classification_reason=dm_classification_reason,
                )

            if not self.ai_api:
                return (
                    f"Hola {contact_name}, ¿cómo estás?"
                    if use_contact_name and contact_name
                    else "Hola, ¿cómo estás?"
                )

            bot_personality_id = self._get_bot_personality_id()

            if not bot_personality_id:
                return (
                    f"Hola {contact_name}, ¿cómo estás?"
                    if use_contact_name and contact_name
                    else "Hola, ¿cómo estás?"
                )

            name_instruction = (
                f"- You may naturally use the contact name '{contact_name}' once if it fits.\n"
                if use_contact_name and contact_name
                else "- Do not force the contact name if it sounds unnatural.\n"
            )

            user_prompt = f"""
You are a real person replying to an Instagram DM from your phone.

CONTACT_NAME:
{contact_name}

LAST_MESSAGE:
{last_message_text}

CONVERSATION_HISTORY:
{conversation_context}

GOAL:
Write one reply that looks exactly like a real person typed it fast on their phone.

RULES:
- Sound human and natural.
- If they asked something, answer it directly and short.
- If they greeted, respond casually.
- Do not over-explain.
- No hashtags.
- No links.
- No AI mention.
- Maximum 25 words.
{name_instruction}

Return ONLY valid JSON:

{{
  "reply_text": "..."
}}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                return (
                    f"Hola {contact_name}, ¿cómo estás?"
                    if use_contact_name and contact_name
                    else "Hola, ¿cómo estás?"
                )

            parsed = self._extract_reply_json(raw_response)

            if not parsed:
                return (
                    f"Hola {contact_name}, ¿cómo estás?"
                    if use_contact_name and contact_name
                    else "Hola, ¿cómo estás?"
                )

            return str(parsed.get("reply_text") or "").strip()

        except Exception as e:
            self.log.warning("Error generando reply DM desde historial: %r", e)
            return ""

    def _generate_business_dm_reply_from_history(
        self,
        messages: list[dict],
        use_contact_name: bool = True,
        related_prospect: Optional[dict] = None,
        dm_classification: str = "neutral",
        dm_classification_reason: str = "",
    ) -> str:
        try:
            if not messages:
                return ""

            contact_name = str(messages[-1].get("contact_name") or "").strip()
            first_name = self._get_first_name_from_contact(contact_name)

            last_incoming = self._get_last_incoming_message(messages)

            if not last_incoming:
                return ""

            last_message_text = str(last_incoming.get("text") or "").strip()
            conversation_context = self._build_conversation_context(messages, max_messages=20)
            follow_up_phone = self._get_business_follow_up_phone(related_prospect)

            if not self.ai_api:
                return self._build_business_dm_fallback(
                    contact_name=contact_name,
                    last_message_text=last_message_text,
                    follow_up_phone=follow_up_phone,
                    use_contact_name=use_contact_name,
                )

            bot_personality_id = self._get_bot_personality_id()

            if not bot_personality_id:
                return self._build_business_dm_fallback(
                    contact_name=contact_name,
                    last_message_text=last_message_text,
                    follow_up_phone=follow_up_phone,
                    use_contact_name=use_contact_name,
                )

            name_rule = (
                f"- You may greet using the first name '{first_name}' if it sounds natural.\n"
                if use_contact_name and first_name
                else "- Greet without using a name.\n"
            )

            phone_rule = (
                f"- If the person asks for information, price, service, availability, quote, booking, appointment or next steps, include this phone naturally: {follow_up_phone}\n"
                if follow_up_phone
                else "- Do not invent any phone number.\n"
            )

            prospect_context = json.dumps(related_prospect or {}, ensure_ascii=False)[:1500]

            user_prompt = f"""
You are replying from a BUSINESS Instagram account.

RELATED_PROSPECT_FROM_DATABASE:
{prospect_context}

CONTACT_NAME:
{contact_name}

LAST_PROSPECT_MESSAGE:
{last_message_text}

VISIBLE_CONVERSATION_HISTORY:
{conversation_context}

DM_CLASSIFICATION:
{dm_classification}

CLASSIFICATION_REASON:
{dm_classification_reason}

GOAL:
Write ONE short Instagram DM reply based on what the prospect said.

IMPORTANT:
This DM belongs to a prospect already registered in the prospecting system.
Reply as a business, not as a casual personal account.

RESPONSE RULES:
- Always start with a natural greeting.
- If the message is in Spanish, start with "Hola" or "Hola {first_name}" when the name fits.
- If the message is in English, start with "Hi" or "Hi {first_name}" when the name fits.
- After the greeting, thank them briefly or acknowledge their message.
- Do not start directly with a sales answer.
- Do not sound corporate or automated.
- Avoid phrases like "we have received your message", "our team will contact you soon", "dear customer", or "estimated prospect".
{name_rule}
- Analyze the prospect's last message and answer according to it.
- If they ask a question, answer it directly.
- If they ask for price, quote, appointment, availability, booking, service details or next steps, guide them to call.
{phone_rule}
- If they say they are interested, thank them and offer the next step.
- If they only greet, greet back and ask how you can help.
- If they complain, apologize briefly and offer help.
- If the message is unclear, ask one short clarification question.
- Keep it human, warm and professional.
- Do not sound robotic.
- Do not over-explain.
- Do not use hashtags.
- Do not use links.
- Do not mention AI.
- Maximum 40 words.
- Single message only.
- Language must match the prospect's message.

Return ONLY valid JSON:

{{
  "reply_text": "..."
}}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                return self._build_business_dm_fallback(
                    contact_name=contact_name,
                    last_message_text=last_message_text,
                    follow_up_phone=follow_up_phone,
                    use_contact_name=use_contact_name,
                )

            parsed = self._extract_reply_json(raw_response)

            if not parsed:
                return self._build_business_dm_fallback(
                    contact_name=contact_name,
                    last_message_text=last_message_text,
                    follow_up_phone=follow_up_phone,
                    use_contact_name=use_contact_name,
                )

            reply_text = str(parsed.get("reply_text") or "").strip()
            reply_text = self._sanitize_business_dm_reply(reply_text)

            if not reply_text:
                return self._build_business_dm_fallback(
                    contact_name=contact_name,
                    last_message_text=last_message_text,
                    follow_up_phone=follow_up_phone,
                    use_contact_name=use_contact_name,
                )

            return reply_text

        except Exception as e:
            self.log.warning("Error generando reply DM business: %r", e)
            return ""

    def _build_business_dm_fallback(
        self,
        contact_name: str,
        last_message_text: str,
        follow_up_phone: str = "",
        use_contact_name: bool = True,
    ) -> str:
        try:
            first_name = self._get_first_name_from_contact(contact_name)
            text = self._normalize_text(last_message_text)

            is_spanish = any(
                x in text
                for x in [
                    "hola",
                    "buenas",
                    "información",
                    "precio",
                    "servicio",
                    "cotización",
                    "cuánto",
                    "necesito",
                    "quiero",
                ]
            )

            greeting = (
                f"Hola {first_name}"
                if is_spanish and use_contact_name and first_name
                else "Hola"
                if is_spanish
                else f"Hi {first_name}"
                if use_contact_name and first_name
                else "Hi"
            )

            asks_info = any(
                word in text
                for word in [
                    "info",
                    "information",
                    "more information",
                    "details",
                    "price",
                    "cost",
                    "how much",
                    "service",
                    "services",
                    "quote",
                    "estimate",
                    "available",
                    "availability",
                    "appointment",
                    "booking",
                    "book",
                    "información",
                    "precio",
                    "cuánto",
                    "servicio",
                    "servicios",
                    "cotización",
                    "disponible",
                    "cita",
                ]
            )

            if is_spanish:
                if asks_info and follow_up_phone:
                    return (
                        f"{greeting}, gracias por escribirnos. "
                        f"Claro, podemos ayudarte con eso. "
                        f"Puedes llamarnos al {follow_up_phone} y te damos más detalles."
                    )

                if asks_info:
                    return (
                        f"{greeting}, gracias por escribirnos. "
                        "Claro, podemos ayudarte con eso. "
                        "Cuéntanos qué servicio necesitas y te damos más detalles."
                    )

                if follow_up_phone:
                    return (
                        f"{greeting}, gracias por tu mensaje. "
                        f"Pronto estaremos en contacto contigo. "
                        f"También puedes llamarnos al {follow_up_phone}."
                    )

                return f"{greeting}, gracias por tu mensaje. Pronto estaremos en contacto contigo."

            if asks_info and follow_up_phone:
                return (
                    f"{greeting}, thanks for reaching out. "
                    f"We can help with that. "
                    f"You can call us at {follow_up_phone} for more details."
                )

            if asks_info:
                return (
                    f"{greeting}, thanks for reaching out. "
                    "We can help with that. What service do you need more information about?"
                )

            if follow_up_phone:
                return (
                    f"{greeting}, thanks for your message. "
                    f"We’ll contact you soon. You can also call us at {follow_up_phone}."
                )

            return f"{greeting}, thanks for your message. We’ll contact you soon."

        except Exception:
            if follow_up_phone:
                return f"Hi, thanks for reaching out. You can call us at {follow_up_phone} for more information."
            return "Hi, thanks for reaching out. We’ll contact you soon."

    def _sanitize_business_dm_reply(self, reply_text: str) -> str:
        try:
            text = str(reply_text or "").strip()

            if not text:
                return ""

            text = " ".join(text.split())

            banned = [
                "http://",
                "https://",
                "www.",
                "#",
                "soy una ia",
                "soy un ai",
                "as an ai",
                "como inteligencia artificial",
            ]

            lower = text.lower()

            if any(item in lower for item in banned):
                return ""

            if len(text) > 280:
                text = text[:280].strip()

            return text

        except Exception:
            return ""

    # =========================================================
    # INPUT + ENVÍO
    # =========================================================

    def _get_dm_input_box(self):
        try:
            elems = self.browser.driver.find_elements(
                By.XPATH,
                InstagramDMLocators.DM_COMPOSER_INPUT,
            )

            for el in elems:
                try:
                    if el.is_displayed():
                        return el
                except Exception:
                    continue

            return None

        except Exception as e:
            self.log.warning("Error obteniendo input DM: %r", e)
            return None

    def _get_dm_send_button(self):
        try:
            elems = self.browser.driver.find_elements(
                By.XPATH,
                InstagramDMLocators.DM_SEND_BUTTON,
            )

            for el in elems:
                try:
                    if el.is_displayed():
                        return el
                except Exception:
                    continue

            return None

        except Exception as e:
            self.log.warning("Error obteniendo botón Enviar DM: %r", e)
            return None

    def _send_dm_message(self, message_text: str) -> bool:
        try:
            input_box = self._get_dm_input_box()

            if input_box is None:
                self.log.warning("No se encontró el input del DM.")
                return False

            wrote_ok = self._type_dm_message_like_human(input_box, message_text)

            if not wrote_ok:
                self.log.warning("No se pudo escribir el mensaje DM con teclado.")
                return False

            self.browser.time_sleep(1.2)

            send_btn = self._get_dm_send_button()

            if send_btn is None:
                self.log.warning("No se encontró el botón Enviar del DM.")
                return False

            try:
                send_btn.click()
                self.browser.time_sleep(random.randint(2, 4))
                self.log.info("Mensaje DM enviado con click directo.")
                return True
            except Exception:
                try:
                    ActionChains(self.browser.driver).move_to_element(send_btn).pause(
                        random.uniform(0.2, 0.5)
                    ).click().perform()
                    self.browser.time_sleep(random.randint(2, 4))
                    self.log.info("Mensaje DM enviado con ActionChains.")
                    return True
                except Exception:
                    try:
                        self.browser.driver.execute_script(
                            InstagramDMLocators.CLICK_ELEMENT_SCRIPT,
                            send_btn,
                        )
                        self.browser.time_sleep(random.randint(2, 4))
                        self.log.info("Mensaje DM enviado con JS click.")
                        return True
                    except Exception as e:
                        self.log.warning("Falló click en botón Enviar DM: %r", e)
                        return False

        except Exception as e:
            self.log.warning("Error enviando DM: %r", e)
            return False

    def _type_dm_message_like_human(self, input_box, message_text: str) -> bool:
        try:
            if input_box is None:
                self.log.warning("No se recibió input_box para escribir DM.")
                return False

            try:
                self.browser.driver.execute_script(
                    InstagramDMLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    input_box,
                )
            except Exception:
                pass

            self.browser.time_sleep(1)

            try:
                input_box.click()
            except Exception:
                pass

            self.browser.time_sleep(1)

            try:
                ActionChains(self.browser.driver).move_to_element(input_box).click().perform()
            except Exception:
                pass

            self.browser.time_sleep(0.5)

            try:
                input_box.send_keys(Keys.CONTROL, "a")
                self.browser.time_sleep(0.3)
                input_box.send_keys(Keys.BACKSPACE)
                self.browser.time_sleep(0.5)
            except Exception as e:
                self.log.warning("No se pudo limpiar el editor DM con teclado: %r", e)

            try:
                input_box.send_keys(message_text)
            except Exception as e:
                self.log.warning("Falló send_keys en editor DM: %r", e)
                return False

            self.browser.time_sleep(1.2)

            final_text = self.browser.driver.execute_script(
                InstagramDMLocators.READ_DM_INPUT_TEXT_SCRIPT,
                input_box,
            ) or ""

            final_text = str(final_text).strip()
            expected = str(message_text).strip()

            self.log.info(
                "Resultado escritura DM por teclado | esperado=%s | actual=%s",
                expected,
                final_text,
            )

            return final_text == expected

        except Exception as e:
            self.log.warning("Error escribiendo DM con teclado: %r", e)
            return False

    def _count_unread_chats(self) -> int:
        try:
            unread_chats = self._get_unread_chat_elements()
            return len(unread_chats)
        except Exception as e:
            self.log.warning("Error contando chats no leídos: %r", e)
            return 0

    # =========================================================
    # DB CLASSIFICATION MAPPING
    # =========================================================

    def _map_classification_for_db(self, classification: str) -> str:
        classification = str(classification or "").strip().lower()

        allowed = {
            "neutral",
            "interested",
            "question",
            "irrelevant",
            "negative",
        }

        if classification in allowed:
            return classification

        return "neutral"