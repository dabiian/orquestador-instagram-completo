import json
from app.services.instagram_config_runtime_service import InstagramConfigRuntimeService
from typing import List, Optional, Tuple

from app.utils.logger import get_logger
from app.config.industry_prompt_rules import get_industry_prompt_rules, normalize_campaign_type
from app.services.instagram_campaign_policy_service import InstagramCampaignPolicyService


class InstagramCommentGenerationService:
    """
    Handles:
    - loading used comments by category
    - building AI prompts
    - parsing AI JSON output
    - saving generated comments

    Regla principal:
    - El idioma de salida SIEMPRE sale de:
      self.data["social_media_account"]["bot_personality"]["language"]
    - El idioma del post/caption SOLO sirve para entender contexto.
    """

    def __init__(self, data, account_api, ai_api, post_media_service, logger=None):
        self.data = data or {}
        self.account_api = account_api
        self.ai_api = ai_api
        self.post_media_service = post_media_service
        self.log = logger or get_logger(self.__class__.__name__)

    def _get_campaign_type(self, campaign_info=None, campaign_strategy=None) -> str:
        campaign_info = campaign_info if isinstance(campaign_info, dict) else {}
        campaign_strategy = campaign_strategy if isinstance(campaign_strategy, dict) else {}
        return normalize_campaign_type(
            campaign_info.get("campaign_type")
            or campaign_strategy.get("campaign_type")
            or self.data.get("campaign_type")
            or self.data.get("type")
        )

    def _get_industry_rules_prompt(self, campaign_info=None, campaign_strategy=None) -> str:
        campaign_type = self._get_campaign_type(campaign_info, campaign_strategy)
        rules = get_industry_prompt_rules(campaign_type)
        comment_policy = InstagramCampaignPolicyService.comment_prompt(campaign_type)
        if not rules and not comment_policy:
            return ""

        sections = [
            """
━━━━━━━━━━━━━━━━━━━━━━━━
FACEBOOK-COMPATIBLE INDUSTRY RULES
━━━━━━━━━━━━━━━━━━━━━━━━
These are the long-form campaign rules supplied for this industry.
Preserve their business logic on Instagram, but adapt references to
Facebook/groups to the actual Instagram post/profile/DM context.
Do not invent facts that are not present in the runtime inputs.

{rules}
""".format(rules=rules)
        ]

        if comment_policy:
            sections.append(
                """
━━━━━━━━━━━━━━━━━━━━━━━━
EXECUTABLE INTRO COMMENT POLICY
━━━━━━━━━━━━━━━━━━━━━━━━
Apply the migrated 04_intro_comment_policy.json as runtime constraints.
Templates are references, not permission to invent facts. Forbidden phrases,
banned patterns, sentence/emoji limits, CTA restrictions, duplication rules,
language/privacy rules, and category-specific guidance must be respected.

{policy}
""".format(policy=comment_policy)
            )

        return "\n\n".join(section.strip() for section in sections if section.strip())

    def _validate_campaign_comment_policy(
        self,
        parsed: dict,
        campaign_info=None,
        campaign_strategy=None,
        used_messages=None,
    ) -> bool:
        if not isinstance(parsed, dict):
            return False

        campaign_type = self._get_campaign_type(campaign_info, campaign_strategy)
        comment_text = str(parsed.get("comment_text") or "").strip()

        metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
        context = metadata.get("post_caption") or metadata.get("caption") or metadata.get("visual_description") or metadata.get("post_context") or {}
        ok, reasons = InstagramCampaignPolicyService.validate_comment(
            comment_text,
            campaign_type,
            used_messages or [],
            post_context=context,
            account_language=self.get_bot_personality_language(),
        )

        safety_reasons = InstagramConfigRuntimeService.forbidden_public_content(campaign_type, comment_text)
        if safety_reasons:
            self.log.warning("Generated comment rejected by config safety rules | campaign_type=%s | reasons=%s", campaign_type, safety_reasons)
            return False

        if not ok:
            self.log.warning(
                "Generated comment rejected by migrated 04_intro_comment_policy | "
                "campaign_type=%s | reasons=%s | comment=%s",
                campaign_type,
                reasons,
                comment_text,
            )
            return False

        metadata = parsed.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["campaign_policy_validated"] = True
        metadata["campaign_policy_source"] = "04_intro_comment_policy.json"
        parsed["metadata"] = metadata
        return True

    # =========================================================
    # ACCOUNT / PERSONALITY
    # =========================================================

    def get_account_id(self) -> Optional[int]:
        try:
            return self.data["social_media_account"]["id"]
        except Exception:
            return None

    def get_bot_personality_id(self) -> Optional[int]:
        try:
            return self.data["social_media_account"]["bot_personality"]["id"]
        except Exception:
            return None

    def get_bot_personality_language(self) -> str:
        """
        Devuelve el idioma definido directamente en BotPersonality.language.

        Backend esperado:
        self.data["social_media_account"]["bot_personality"]["language"]

        Ejemplos válidos:
        - ESPAÑOL / Español / ES / Spanish
        - ENGLISH / English / EN
        - PORTUGUÉS / Portuguese / PT
        """
        try:
            bot_personality = (
                self.data.get("social_media_account", {})
                .get("bot_personality", {})
            )

            if not isinstance(bot_personality, dict):
                return "Spanish"

            raw_language = str(bot_personality.get("language") or "").strip()

            if not raw_language:
                return "Spanish"

            normalized = raw_language.lower()

            if normalized in {"es", "esp", "español", "espanol", "spanish"}:
                return "Spanish"

            if normalized in {"en", "eng", "english", "inglés", "ingles"}:
                return "English"

            if normalized in {"pt", "por", "portuguese", "portugués", "portugues"}:
                return "Portuguese"

            if "español" in normalized or "espanol" in normalized or "spanish" in normalized:
                return "Spanish"

            if "english" in normalized or "inglés" in normalized or "ingles" in normalized:
                return "English"

            if "portuguese" in normalized or "portugués" in normalized or "portugues" in normalized:
                return "Portuguese"

            return "Spanish"

        except Exception:
            return "Spanish"

    def _build_language_prompt(self) -> str:
        output_language = self.get_bot_personality_language()

        return f"""
LANGUAGE RULES:
- OUTPUT_LANGUAGE = {output_language}
- The final value of "comment_text" must be written exclusively in OUTPUT_LANGUAGE.
- The language of POST_CAPTION is only for understanding context.
- Do NOT imitate the language of the post if it is different from OUTPUT_LANGUAGE.
- Do NOT answer in the detected post language unless it matches OUTPUT_LANGUAGE.
- Do NOT translate usernames, handles, brand names, campaign handles, URLs, or proper names.
- If examples in this prompt are written in another language, treat them only as structural examples.
- The final comment_text must still be written only in OUTPUT_LANGUAGE.
""".strip()

    # =========================================================
    # USED MESSAGES
    # =========================================================

    def get_used_messages_by_category(self, category: str) -> List[str]:
        try:
            account_id = self.get_account_id()
            if not account_id:
                return []

            response = self.account_api.get_comments(account_id, category)

            if not response:
                return []

            if hasattr(response, "status_code") and response.status_code != 200:
                self.log.warning(
                    "get_comments returned status %s for category %s",
                    response.status_code,
                    category,
                )
                return []

            try:
                payload = response.json()
            except Exception as e:
                self.log.warning(
                    "Could not decode get_comments response as JSON for category %s: %s",
                    category,
                    str(e),
                )
                return []

            items = []
            if isinstance(payload, list):
                items = payload
            elif isinstance(payload, dict):
                if isinstance(payload.get("results"), list):
                    items = payload["results"]
                elif isinstance(payload.get("data"), list):
                    items = payload["data"]
                elif isinstance(payload.get("items"), list):
                    items = payload["items"]
                else:
                    items = []

            messages = []

            for item in items:
                if not isinstance(item, dict):
                    continue

                text = str(
                    item.get("message_text")
                    or item.get("message")
                    or item.get("comment")
                    or item.get("text")
                    or ""
                ).strip()

                if text:
                    messages.append(text)

            return messages

        except Exception as e:
            self.log.warning(
                "Error getting used messages for category %s: %s",
                category,
                str(e),
            )
            return []

    def _build_used_messages_prompt(self, category: str, used_messages: List[str]) -> str:
        return f"""
Do not repeat any comment that has already been used before.

USED_MESSAGES = {json.dumps(used_messages, ensure_ascii=False)}

The USED_MESSAGES list contains comments already used by this account in the same category.
You must make sure the new "comment_text" is clearly different.
Do not reuse openings, closings, structure, or very similar wording.
CATEGORY = {category}
""".strip()

    @staticmethod
    def _clean_ai_json_text(raw_text: str) -> str:
        """Normalize common LLM JSON defects without changing valid JSON."""
        text = str(raw_text or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().lower().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Keep only the outer JSON object when the model adds prose.
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]

        # JSON disallows literal control characters inside strings. LLMs
        # occasionally emit them in fields such as profile_description.
        # Escape them only while inside a quoted JSON string.
        out = []
        in_string = False
        escaped = False
        for ch in text:
            if in_string:
                if escaped:
                    out.append(ch)
                    escaped = False
                elif ch == "\\":
                    out.append(ch)
                    escaped = True
                elif ch == '"':
                    out.append(ch)
                    in_string = False
                elif ord(ch) < 0x20:
                    out.append("\\n" if ch == "\n" else "\\r" if ch == "\r" else "\\t" if ch == "\t" else f"\\u{ord(ch):04x}")
                else:
                    out.append(ch)
            else:
                out.append(ch)
                if ch == '"':
                    in_string = True
        return "".join(out)

    @classmethod
    def _loads_ai_json(cls, raw_text: str):
        cleaned = cls._clean_ai_json_text(raw_text)
        return json.loads(cleaned)

    # =========================================================
    # PARSERS
    # =========================================================

    def parse_ai_comment_response(self, raw_response) -> Optional[dict]:
        try:
            data = raw_response

            if isinstance(data, dict):
                if "response" in data and isinstance(data["response"], str):
                    content = data["response"].strip()
                else:
                    content = data
            else:
                content = str(data).strip()

            if isinstance(content, dict):
                parsed = content
            else:
                text = content.strip()

                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

                parsed = self._loads_ai_json(text)

            if not isinstance(parsed, dict):
                return None

            comment_text = str(parsed.get("comment_text", "")).strip()
            metadata = parsed.get("metadata", {}) or {}

            if not comment_text:
                return None

            if not isinstance(metadata, dict):
                metadata = {}

            parsed["comment_text"] = comment_text
            parsed["metadata"] = metadata
            return parsed

        except Exception as e:
            self.log.warning("Error parsing AI comment response: %s", str(e))
            return None

    def parse_ai_prospecting_b2b_response(self, raw_response) -> Optional[dict]:
        """
        Parser para comentarios B2B de prospectación.
        Permite skip_post=true con comment_text vacío.
        """
        try:
            data = raw_response

            if isinstance(data, dict):
                if "response" in data and isinstance(data["response"], str):
                    content = data["response"].strip()
                else:
                    content = data
            else:
                content = str(data or "").strip()

            if isinstance(content, dict):
                parsed = content
            else:
                text = str(content or "").strip()

                if not text:
                    return None

                if text.startswith("```"):
                    text = (
                        text.replace("```json", "")
                        .replace("```JSON", "")
                        .replace("```", "")
                        .strip()
                    )

                try:
                    parsed = self._loads_ai_json(text)
                except Exception:
                    start = text.find("{")
                    end = text.rfind("}")

                    if start == -1 or end == -1 or end <= start:
                        return None

                    parsed = self._loads_ai_json(text[start : end + 1])

            if not isinstance(parsed, dict):
                return None

            skip_post = bool(parsed.get("skip_post", False))
            comment_text = str(parsed.get("comment_text") or "").strip()
            metadata = parsed.get("metadata") or {}

            if not isinstance(metadata, dict):
                metadata = {}

            if skip_post:
                parsed["skip_post"] = True
                parsed["comment_text"] = ""
                parsed["metadata"] = metadata
                return parsed

            if not comment_text:
                return None

            parsed["skip_post"] = False
            parsed["comment_text"] = comment_text
            parsed["metadata"] = metadata
            return parsed

        except Exception as e:
            self.log.warning("Error parsing AI B2B prospecting response: %s", str(e))
            return None

    def parse_ai_comment_text_only_response(
        self, raw_response, campaign_type=None, used_messages=None
    ) -> Optional[dict]:
        """
        Parser seguro para respuestas donde SOLO esperamos:
        {"comment_text": "..."}
        """
        try:
            data = raw_response

            if isinstance(data, dict):
                if "response" in data and isinstance(data["response"], str):
                    content = data["response"].strip()
                else:
                    content = data
            else:
                content = str(data or "").strip()

            if isinstance(content, dict):
                parsed = content
            else:
                text = str(content or "").strip()

                if not text:
                    return None

                if text.startswith("```"):
                    text = (
                        text.replace("```json", "")
                        .replace("```JSON", "")
                        .replace("```", "")
                        .strip()
                    )

                parsed = None

                try:
                    parsed = self._loads_ai_json(text)
                except Exception:
                    parsed = None

                if parsed is None:
                    try:
                        start = text.find("{")
                        end = text.rfind("}")

                        if start != -1 and end != -1 and end > start:
                            json_block = text[start : end + 1].strip()
                            parsed = json.loads(json_block)
                    except Exception:
                        parsed = None

                if parsed is None:
                    try:
                        key = '"comment_text"'
                        idx = text.find(key)

                        if idx != -1:
                            colon_idx = text.find(":", idx + len(key))
                            if colon_idx != -1:
                                first_quote = text.find('"', colon_idx + 1)

                                if first_quote != -1:
                                    value, _ = json.JSONDecoder().raw_decode(text[first_quote:])
                                    parsed = {"comment_text": value}
                    except Exception:
                        parsed = None

            if not isinstance(parsed, dict):
                return None

            resolved_campaign_type = self._get_campaign_type(
                {"campaign_type": campaign_type} if campaign_type else None
            )

            if not self._validate_campaign_comment_policy(
                parsed, {"campaign_type": resolved_campaign_type}, None, used_messages or []
            ):
                return False, None

            comment_text = str(parsed.get("comment_text") or "").strip()

            if not comment_text:
                return None

            parsed["comment_text"] = comment_text
            return parsed

        except Exception as e:
            self.log.warning("Error parsing AI text-only comment response: %s", str(e))
            return None

    # =========================================================
    # SAVE
    # =========================================================

    def _save_generated_comment(
        self,
        account_id: int,
        comment_text: str,
        category: str,
        metadata: dict,
    ) -> None:
        try:
            metadata = metadata or {}
            metadata.setdefault("output_language", self.get_bot_personality_language())

            response = self.account_api.save_new_comment(
                account_id,
                comment_text,
                category,
                metadata,
            )

            if hasattr(response, "status_code") and response.status_code not in (200, 201):
                self.log.warning(
                    "Generated comment could not be saved. Status: %s | Body: %s",
                    response.status_code,
                    getattr(response, "text", ""),
                )
            else:
                self.log.info("Generated comment saved successfully.")

        except Exception as e:
            self.log.warning("Could not save generated comment: %s", str(e))

    # =========================================================
    # IMAGE ONLY COMMENT
    # =========================================================

    def generate_comment_from_current_post_image(
        self,
        category: str = "comentario_publicacion_seguidor",
    ) -> Tuple[bool, Optional[str]]:
        try:
            account_id = self.get_account_id()
            bot_personality_id = self.get_bot_personality_id()

            if not account_id:
                self.log.warning("social_media_account.id was not found.")
                return False, None

            if not bot_personality_id:
                self.log.warning("bot_personality.id was not found.")
                return False, None

            ok_image_description, image_url, description = (
                self.post_media_service.analyze_current_post_image()
            )

            if not ok_image_description or not description:
                self.log.warning("Could not analyze current post image.")
                return False, None

            used_messages = self.get_used_messages_by_category(category)
            extra_prompt = self._build_used_messages_prompt(category, used_messages)
            language_prompt = self._build_language_prompt()
            campaign_type = self._get_campaign_type()
            comment_policy_prompt = InstagramCampaignPolicyService.comment_prompt(campaign_type)
            output_language = self.get_bot_personality_language()

            user_prompt = f"""
Generate ONE short Instagram comment based ONLY on this visual description.

{language_prompt}

IMAGE_DESCRIPTION = {description}

Rules:
- It must sound natural and human.
- It must fit the bot personality.
- It must not sound salesy.
- It must not sound robotic.
- Do not ask questions.
- Do not use hashtags.
- Maximum 8 words.
- Single line only.
- It may include 0 or 1 emoji if it fits naturally.

The response must be only one valid JSON object with this exact structure:

{{
  "comment_text": "comment here",
  "metadata": {{
    "source": "image_analysis",
    "category": "{category}",
    "image_url": "{image_url}",
    "visual_description": "{description}",
    "output_language": "{output_language}",
    "tone": "detected tone",
    "focus": "comment focus"
  }}
}}

{extra_prompt}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                self.log.warning("AI did not return any comment.")
                return False, None

            parsed = self.parse_ai_comment_response(raw_response)
            if not parsed:
                self.log.warning("Could not parse AI comment response.")
                return False, None

            if not self._validate_campaign_comment_policy(
                parsed, {"campaign_type": campaign_type}, None, used_messages
            ):
                return False, None

            comment_text = str(parsed.get("comment_text", "")).strip()
            metadata = parsed.get("metadata", {}) or {}

            if not comment_text:
                self.log.warning("Generated comment_text came back empty.")
                return False, None

            self._save_generated_comment(
                account_id=account_id,
                comment_text=comment_text,
                category=category,
                metadata=metadata,
            )

            return True, comment_text

        except Exception as e:
            self.log.warning("Error generating comment from post image: %s", str(e))
            return False, None

    # =========================================================
    # IMAGE + CAPTION COMMENT
    # =========================================================

    def generate_comment_from_current_post_context(
        self,
        category: str = "comentario_publicacion_seguidor",
    ) -> Tuple[bool, Optional[str]]:
        """
        Nuevo flujo:
        - usa imagen
        - usa caption del autor
        - usa username del autor
        - si no hay caption útil, cae en image-only
        """
        try:
            account_id = self.get_account_id()
            bot_personality_id = self.get_bot_personality_id()

            if not account_id:
                self.log.warning("social_media_account.id was not found.")
                return False, None

            if not bot_personality_id:
                self.log.warning("bot_personality.id was not found.")
                return False, None

            ok_image_description, image_url, description = (
                self.post_media_service.analyze_current_post_image()
            )

            if not ok_image_description or not description:
                self.log.warning("Could not analyze current post image.")
                return False, None

            post_context = self.post_media_service.get_current_post_context() or {}
            author_username = str(post_context.get("author_username") or "").strip()
            caption = str(post_context.get("caption") or "").strip()

            if caption:
                caption = " ".join(caption.split())

            if not caption:
                self.log.info(
                    "Current post has no useful caption. Falling back to image-only comment generation."
                )
                return self.generate_comment_from_current_post_image(category=category)

            used_messages = self.get_used_messages_by_category(category)
            extra_prompt = self._build_used_messages_prompt(category, used_messages)
            language_prompt = self._build_language_prompt()
            output_language = self.get_bot_personality_language()
            campaign_type = self._get_campaign_type()
            comment_policy_prompt = InstagramCampaignPolicyService.comment_prompt(campaign_type)

            user_prompt = f"""
Generate ONE short Instagram comment for the CURRENT POST.

{language_prompt}

{comment_policy_prompt}

POST_CONTEXT:
- AUTHOR_USERNAME = {author_username}
- POST_CAPTION = {caption}
- IMAGE_DESCRIPTION = {description}

TASK:
Understand the REAL PURPOSE of the post first, then write one natural Instagram comment.

IMPORTANT:
You must infer the post type from the caption + image together.
Possible post types:
- followback_growth
- generic_social
- art_design
- service_offer
- promotional_post
- motivational_post
- community_engagement

PRIORITY ORDER:
1. Understand the post intent from POST_CAPTION.
2. Use IMAGE_DESCRIPTION only as supporting context.
3. Write a comment that matches the post purpose.
4. Do NOT focus on visual design unless the post is clearly about art/design.

STRICT RULES:
- The comment must feel like a real human Instagram comment.
- It must fit the bot personality.
- It must not sound salesy.
- It must not sound robotic.
- Do not ask questions.
- Do not use hashtags.
- Do not copy the caption literally.
- Do not repeat long fragments from the caption.
- Do not mention the author username unless it feels truly natural.
- Maximum 8 words.
- Single line only.
- 0 or 1 emoji max, only if natural.

FOLLOWBACK / GROWTH RULES:
If the post is about follow for follow, followback, mutual support, engagement, followers, likes, comments, or growth:
- the comment MUST align with that theme
- the comment should sound like support, participation, mutual growth, or real engagement
- the comment must NOT sound generic
- the comment must NOT focus on graphic design

GOOD EXAMPLES for followback_growth are structural examples only:
- "Love the mutual support here"
- "Here for real growth 🙌"
- "Supporting genuine followback energy"
- "Mutual growth done right"

Return only ONE valid JSON object with this exact structure:

{{
  "comment_text": "comment here",
  "metadata": {{
    "source": "image_caption_context",
    "category": "{category}",
    "image_url": "{image_url}",
    "author_username": "{author_username}",
    "post_caption": "{caption}",
    "visual_description": "{description}",
    "output_language": "{output_language}",
    "tone": "detected tone",
    "focus": "caption+image"
  }}
}}

{extra_prompt}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                self.log.warning("AI did not return any contextual comment.")
                return False, None

            parsed = self.parse_ai_comment_response(raw_response)
            if not parsed:
                self.log.warning("Could not parse AI contextual comment response.")
                return False, None

            if not self._validate_campaign_comment_policy(
                parsed, {"campaign_type": campaign_type}, None, used_messages
            ):
                return False, None

            comment_text = str(parsed.get("comment_text", "")).strip()
            metadata = parsed.get("metadata", {}) or {}

            if not comment_text:
                self.log.warning("Generated contextual comment_text came back empty.")
                return False, None

            self._save_generated_comment(
                account_id=account_id,
                comment_text=comment_text,
                category=category,
                metadata=metadata,
            )

            return True, comment_text

        except Exception as e:
            self.log.warning("Error generating comment from post context: %s", str(e))
            return False, None

    # =========================================================
    # OWNER / FOLLOWER POST CONTEXT
    # =========================================================

    def generate_comment_from_current_post_image_caption_profile_description(
        self,
        profile_context: dict | None = None,
        category: str = "comentario_publicacion_owner",
    ) -> tuple[bool, str | None]:
        try:
            account_id = self.get_account_id()
            bot_personality_id = self.get_bot_personality_id()

            if not account_id:
                self.log.warning("social_media_account.id was not found.")
                return False, None

            if not bot_personality_id:
                self.log.warning("bot_personality.id was not found.")
                return False, None

            post_context = self.post_media_service.get_current_post_context_runtime_generic(
                max_attempts=8,
                sleep_seconds=1,
            ) or {}

            author_username = str(post_context.get("author_username") or "").strip()
            caption = str(post_context.get("caption") or "").strip()

            caption = self.post_media_service._clean_runtime_caption_text(
                caption=caption,
                author_username=author_username,
            )

            print("Mira el caption runtime generic limpio:", caption)

            if caption:
                caption = " ".join(caption.split())

            profile_context = profile_context or {}
            profile_category = str(profile_context.get("profile_category") or "").strip()
            profile_description = str(profile_context.get("profile_description") or "").strip()

            try:
                is_video_post = self.post_media_service.current_post_has_video()
            except Exception as e:
                self.log.warning("No se pudo detectar si el post es video: %s", str(e))
                is_video_post = False

            image_description = ""
            image_url = ""

            if not is_video_post:
                try:
                    ok_image_description, image_url, image_description = (
                        self.post_media_service.analyze_current_post_image()
                    )

                    if not ok_image_description or not image_description:
                        self.log.warning(
                            "No se pudo analizar la imagen del post. Se continuará con caption/perfil."
                        )
                        image_description = ""
                        image_url = ""

                except Exception as e:
                    self.log.warning(
                        "Error analizando imagen del post owner. Se continuará con caption/perfil: %s",
                        str(e),
                    )
                    image_description = ""
                    image_url = ""

            used_messages = self.get_used_messages_by_category(category)
            extra_prompt = self._build_used_messages_prompt(category, used_messages)
            language_prompt = self._build_language_prompt()
            output_language = self.get_bot_personality_language()
            campaign_info = self.data.get("campaign") if isinstance(self.data.get("campaign"), dict) else self.data.get("campaign_info", {})
            campaign_strategy = self.data.get("strategy_snapshot") if isinstance(self.data.get("strategy_snapshot"), dict) else {}
            industry_rules_prompt = self._get_industry_rules_prompt(campaign_info, campaign_strategy)

            caption_block = caption if caption else "not_available"

            if is_video_post:
                source_name = "video_or_caption_profile_description_context"
                media_block = """
POST_MEDIA_CONTEXT:
- POST_TYPE = video
- VISUAL_CONTEXT = not_available
""".strip()

                task_block = """
TASK:
Analyze the POST_CAPTION carefully to understand:
- What service, product, message, or campaign is being promoted
- The tone and emotional angle of the post
- Any specific benefit, urgency, value proposition, or intent mentioned

Then write ONE short Instagram comment that:
- Feels like a real person reacting naturally
- Matches the post objective
- Does NOT invent visual details
- Uses the caption and profile description as the main context
""".strip()

                strict_media_rule = "- This is a VIDEO: do not invent or describe visual elements."

            else:
                source_name = "image_caption_profile_description_context"
                media_block = f"""
POST_MEDIA_CONTEXT:
- POST_TYPE = image
- IMAGE_DESCRIPTION = {image_description if image_description else 'not_available'}
""".strip()

                task_block = """
TASK:
Analyze the available context in this order:
1. IMAGE_DESCRIPTION — what is visually happening
2. POST_CAPTION — what service/campaign/message is being communicated
3. PROFILE_DESCRIPTION — what kind of business or profile this is

Then write ONE short Instagram comment that:
- Feels like a real person reacting naturally
- Matches the post objective
- Uses the image and caption together when both are available
""".strip()

                strict_media_rule = "- Use IMAGE_DESCRIPTION and POST_CAPTION together when both exist."

            user_prompt = f"""
You are roleplaying as a real Instagram user leaving ONE short natural comment.

{language_prompt}

Your job is NOT to assume a fixed type of comment.
Your first job is to understand the TRUE OBJECTIVE of the post.
Then write the comment that best matches that objective.

---
POST_CONTEXT:
- AUTHOR_USERNAME = {author_username if author_username else 'not_available'}
- POST_CAPTION = {caption_block}

{media_block}

OWNER_PROFILE_CONTEXT:
- PROFILE_CATEGORY = {profile_category if profile_category else 'not_available'}
- PROFILE_DESCRIPTION = {profile_description if profile_description else 'not_available'}

---
{task_block}

---
STEP 1 — IDENTIFY THE MAIN OBJECTIVE OF THE POST

Choose the ONE primary objective that best fits the post:
- service_offer
- promotion_or_conversion
- testimonial_or_social_proof
- educational_or_tip
- emotional_reflection
- spiritual_or_faith_message
- motivational_quote
- brand_presence
- community_engagement
- announcement_or_update
- before_after_or_result
- entertainment_or_meme

Also detect:
- the emotional tone
- whether the post is trying to sell, inspire, comfort, educate, prove results, or simply stay present

---
STEP 2 — CHOOSE THE RIGHT COMMENT STYLE BASED ON THE OBJECTIVE

If objective = service_offer or promotion_or_conversion:
- the comment may sound like a satisfied user, interested customer, or supportive recommendation
- it can mention trust, usefulness, quality, urgency, or value
- keep it believable and natural

If objective = testimonial_or_social_proof or before_after_or_result:
- react to the result, credibility, or transformation
- sound impressed, supportive, or validating
- do not exaggerate beyond the post

If objective = educational_or_tip:
- react like someone who found it useful, smart, practical, or worth remembering
- do not sound like a fake testimonial unless the post clearly invites that

If objective = emotional_reflection, spiritual_or_faith_message, or motivational_quote:
- react emotionally, reflectively, spiritually, or with warmth
- do NOT sound like a customer testimonial unless the post is clearly about a service experience
- do NOT invent dramatic personal outcomes
- comment on the message, comfort, truth, hope, peace, faith, healing, or emotional resonance

If objective = brand_presence or community_engagement:
- leave a short supportive, human, warm comment
- it should feel socially natural, not promotional

If objective = announcement_or_update:
- react in a way that fits the update
- supportive, interested, warm, or validating depending on the tone

If objective = entertainment_or_meme:
- sound casual, spontaneous, and socially natural
- do not sound formal or salesy

---
STRICT RULES:
{strict_media_rule}
- The comment must feel like a real human Instagram comment
- It must match the actual objective of the post
- Do NOT force every post to sound like customer feedback
- Do NOT force every post to sound emotional or inspirational
- Do NOT sound like a marketer, brand account, or social media manager
- Do NOT ask questions
- Do NOT use hashtags or links
- Do NOT mention the author username
- Do NOT copy or closely paraphrase the caption
- Do NOT invent services not supported by POST_CAPTION or PROFILE_DESCRIPTION
- Do NOT invent testimonials unless the post clearly supports that kind of reaction
- Do NOT invent extreme personal outcomes
- Keep it believable, brief, and socially natural
- Maximum 9 words
- Single line only
- 0 or 1 emoji, only if completely natural

---
IMPORTANT DECISION RULE:
Before writing the comment, ask yourself:
"What is this post trying to do?"
Then write the comment that fits THAT purpose — not the account category alone.

---
Return ONLY one valid JSON object with this exact structure:

{{
  "comment_text": "comment here",
  "metadata": {{
    "source": "{source_name}",
    "category": "{category}",
    "image_url": "{image_url}",
    "author_username": "{author_username}",
    "post_caption": "{caption}",
    "image_description": "{image_description}",
    "profile_category": "{profile_category}",
    "profile_description": "{profile_description}",
    "post_type": "{'video' if is_video_post else 'image'}",
    "output_language": "{output_language}",
    "tone": "detected tone of the post",
    "focus": "main objective of the post"
  }}
}}

{extra_prompt}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                self.log.warning("AI did not return contextual comment.")
                return False, None

            parsed = self.parse_ai_comment_response(raw_response)
            if not parsed:
                self.log.warning("Could not parse contextual comment response.")
                return False, None

            if not self._validate_campaign_comment_policy(
                parsed, campaign_info, campaign_strategy, used_messages
            ):
                return False, None

            comment_text = str(parsed.get("comment_text", "")).strip()
            metadata = parsed.get("metadata", {}) or {}

            if not comment_text:
                self.log.warning("Generated contextual comment_text came back empty.")
                return False, None

            self._save_generated_comment(
                account_id=account_id,
                comment_text=comment_text,
                category=category,
                metadata=metadata,
            )

            return True, comment_text

        except Exception as e:
            self.log.warning(
                "Error generating comment from post context: %s",
                str(e),
            )
            return False, None

    # =========================================================
    # PROSPECTING CURRENT POST
    # =========================================================

    def generate_prospecting_comment_from_current_post(
        self,
        profile_context: dict | None = None,
        category: str = "comentario_publicacion_prospecto",
    ) -> tuple[bool, str | None]:
        """
        Genera un comentario específico para prospectación pública.

        Objetivo:
        - sonar natural
        - no vender
        - no mencionar servicios directos
        - no usar CTA agresivo
        - no romper los otros flujos del servicio
        """
        try:
            account_id = self.get_account_id()
            bot_personality_id = self.get_bot_personality_id()

            if not account_id:
                self.log.warning("social_media_account.id was not found.")
                return False, None

            if not bot_personality_id:
                self.log.warning("bot_personality.id was not found.")
                return False, None

            post_context = self.post_media_service.get_current_post_context_runtime_generic(
                max_attempts=8,
                sleep_seconds=1,
            ) or {}

            author_username = str(post_context.get("author_username") or "").strip()
            caption = str(post_context.get("caption") or "").strip()

            caption = self.post_media_service._clean_runtime_caption_text(
                caption=caption,
                author_username=author_username,
            )

            if caption:
                caption = " ".join(caption.split())

            profile_context = profile_context or {}
            profile_category = str(profile_context.get("profile_category") or "").strip()
            profile_description = str(profile_context.get("profile_description") or "").strip()
            profile_name = str(profile_context.get("profile_name") or "").strip()

            is_video_post = self.post_media_service.current_post_has_video()

            image_description = ""
            image_url = ""

            if not is_video_post:
                ok_image_description, image_url, image_description = (
                    self.post_media_service.analyze_current_post_image()
                )

                if not ok_image_description or not image_description:
                    self.log.warning(
                        "No se pudo analizar la imagen del post. Se continuará con caption/perfil."
                    )
                    image_description = ""
                    image_url = ""

            used_messages = self.get_used_messages_by_category(category)
            extra_prompt = self._build_used_messages_prompt(category, used_messages)
            language_prompt = self._build_language_prompt()
            output_language = self.get_bot_personality_language()

            caption_block = caption if caption else "not_available"

            if is_video_post:
                source_name = "prospecting_video_caption_profile_context"
                media_block = """
POST_MEDIA_CONTEXT:
- POST_TYPE = video
- VISUAL_CONTEXT = not_available
"""
                strict_media_rule = "- This is a VIDEO: do not invent visual details."
            else:
                source_name = "prospecting_image_caption_profile_context"
                media_block = f"""
POST_MEDIA_CONTEXT:
- POST_TYPE = image
- IMAGE_DESCRIPTION = {image_description if image_description else 'not_available'}
"""
                strict_media_rule = "- Use IMAGE_DESCRIPTION as supporting context when useful."

            user_prompt = f"""
You are roleplaying as a real Instagram user leaving ONE public comment on a prospect's post.

{language_prompt}

IMPORTANT:
- The bot personality already defines tone, style, and voice. Follow it naturally.
- This is PROSPECTING, but the comment must NOT look commercial.
- The comment must feel like a genuine human reaction.
- It must NOT sound like a business trying to sell.
- It must NOT mention cleaning services directly unless the bot personality/campaign context supports it.
- It must NOT offer help, prices, contact info, phone numbers, emails, links, or DMs.
- It must NOT sound like lead generation.
- It must NOT be generic like: "Nice", "Great post", "Awesome", "Love this".
- It must NOT ask questions.
- It must NOT use hashtags.
- It must NOT mention the author's username.
- Maximum 10 words.
- Single line only.
- 0 or 1 emoji only if truly natural.

POST_CONTEXT:
- AUTHOR_USERNAME = {author_username if author_username else 'not_available'}
- POST_CAPTION = {caption_block}

{media_block}

PROFILE_CONTEXT:
- PROFILE_NAME = {profile_name if profile_name else 'not_available'}
- PROFILE_CATEGORY = {profile_category if profile_category else 'not_available'}
- PROFILE_DESCRIPTION = {profile_description if profile_description else 'not_available'}

TASK:
1. Understand the real purpose of the post.
2. Decide what a normal human would naturally say in public.
3. Write ONE short comment that fits the post naturally.

COMMENTING STYLE FOR PROSPECTING:
- If it is a property/listing post: comment on presentation, layout, natural light, curb appeal, finish, staging, or overall impression.
- If it is a service/result/business post: react to the quality, clarity, polish, or professionalism.
- If it is personal or reflective: react briefly and naturally, without sounding fake or dramatic.
- The comment should feel low-pressure and socially believable.

STRICT RULES:
{strict_media_rule}
- Do not force emotional language.
- Do not force testimonial tone.
- Do not force promotion.
- Do not sound like outreach.
- Keep it subtle, short, and believable.

Return ONLY one valid JSON object with this exact structure:

{{
  "comment_text": "comment here",
  "metadata": {{
    "source": "{source_name}",
    "category": "{category}",
    "image_url": "{image_url}",
    "author_username": "{author_username}",
    "post_caption": "{caption}",
    "image_description": "{image_description}",
    "profile_category": "{profile_category}",
    "profile_description": "{profile_description}",
    "post_type": "{'video' if is_video_post else 'image'}",
    "output_language": "{output_language}",
    "focus": "prospecting_public_comment"
  }}
}}

{extra_prompt}
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                self.log.warning("AI did not return prospecting comment.")
                return False, None

            parsed = self.parse_ai_comment_response(raw_response)
            if not parsed:
                self.log.warning("Could not parse prospecting comment response.")
                return False, None

            if not self._validate_campaign_comment_policy(
                parsed, campaign_info, campaign_strategy, used_messages
            ):
                return False, None

            comment_text = str(parsed.get("comment_text", "")).strip()
            metadata = parsed.get("metadata", {}) or {}

            comment_text = self._sanitize_prospecting_comment_text(comment_text)

            if not comment_text:
                self.log.warning("Generated prospecting comment_text came back empty.")
                return False, None

            self._save_generated_comment(
                account_id=account_id,
                comment_text=comment_text,
                category=category,
                metadata=metadata,
            )

            return True, comment_text

        except Exception as e:
            self.log.warning(
                "Error generating prospecting comment from current post: %s",
                str(e),
            )
            return False, None

    # =========================================================
    # SANITIZERS
    # =========================================================

    def _sanitize_prospecting_comment_text(self, comment_text: str) -> str:
        try:
            text = str(comment_text or "").strip()
            if not text:
                return ""

            text = " ".join(text.split())

            banned_fragments = [
                "dm me",
                "dm us",
                "send dm",
                "message me",
                "message us",
                "contact me",
                "contact us",
                "call me",
                "call us",
                "text me",
                "text us",
                "whatsapp",
                "email me",
                "email us",
                "link in bio",
                "book now",
                "schedule now",
                "get a quote",
                "free quote",
                "we offer",
                "we provide",
                "we can help",
                "our service",
                "our services",
                "my service",
                "my services",
                "hire us",
                "choose us",
                "work with us",
                "http://",
                "https://",
                "www.",
                "@gmail.com",
                ".com",
                ".net",
                ".org",
            ]

            lower = text.lower()
            if any(item in lower for item in banned_fragments):
                return ""

            if "#" in text:
                return ""

            if len(text) > 140:
                text = text[:140].strip()

            return text

        except Exception:
            return ""

    def _sanitize_b2b_referral_comment_text(self, comment_text: str) -> str:
        """
        Sanitizador para comentarios B2B referral.
        No bloquea frases como "we help" o "we provide",
        porque en B2B pueden ser válidas.
        """
        try:
            text = str(comment_text or "").strip()
            if not text:
                return ""

            text = " ".join(text.split())

            banned_fragments = [
                "dm me",
                "dm us",
                "send dm",
                "message me",
                "message us",
                "contact me",
                "contact us",
                "call me",
                "call us",
                "text me",
                "text us",
                "whatsapp",
                "email me",
                "email us",
                "link in bio",
                "book now",
                "schedule now",
                "schedule today",
                "get a quote",
                "free quote",
                "hire us",
                "choose us",
                "http://",
                "https://",
                "www.",
                "@gmail.com",
                ".net",
                ".org",
            ]

            lower = text.lower()

            if any(item in lower for item in banned_fragments):
                return ""

            if "#" in text:
                return ""

            if len(text) > 300:
                text = text[:300].strip()

            return text

        except Exception:
            return ""

    # =========================================================
    # PROSPECTING SAVED POST B2B
    # =========================================================

    def generate_prospecting_comment_from_saved_post(
        self,
        post: dict,
        profile_context: dict | None = None,
        category: str = "comentario_publicacion_prospecto",
    ) -> tuple[bool, str | None]:
        """
        Prospecting B2B multi-industria:
        - usa caption_text guardado en BD como fuente principal
        - usa image analysis solo como apoyo
        - genera comentario Instagram B2B referral
        - NO está quemado para limpieza
        - funciona con cualquier campaña usando CAMPAIGN_SERVICES
        """
        try:
            account_id = self.get_account_id()
            bot_personality_id = self.get_bot_personality_id()

            if not account_id:
                self.log.warning("social_media_account.id was not found.")
                return False, None

            if not bot_personality_id:
                self.log.warning("bot_personality.id was not found.")
                return False, None

            post = post or {}
            profile_context = profile_context or {}

            caption = str(post.get("caption_text") or "").strip()
            analysis_reason = str(post.get("analysis_reason") or "").strip()

            if caption:
                caption = " ".join(caption.split())

            print(f"[prospecting-comment] CAPTION_USADO_LEN={len(caption)}")
            print(f"[prospecting-comment] CAPTION_USADO={caption}")

            if not caption:
                self.log.warning(
                    "Prospecting comment skipped: no useful stored caption_text in post."
                )
                return False, None

            social_media_account = self.data.get("social_media_account") or {}

            author_username = str(
                profile_context.get("username")
                or profile_context.get("profile_name")
                or ""
            ).strip()

            profile_category = str(profile_context.get("profile_category") or "").strip()
            profile_description = str(profile_context.get("profile_description") or "").strip()

            campaign_services = profile_context.get("campaign_services") or []
            campaign_strategy = profile_context.get("campaign_strategy") or {}
            campaign_name = str(profile_context.get("campaign_name") or "").strip()

            campaign_info = (
                profile_context.get("campaign_info")
                or profile_context.get("campaign")
                or {}
            )

            qualification = profile_context.get("qualification") or {}
            if not isinstance(qualification, dict):
                qualification = {}

            if isinstance(campaign_services, str):
                campaign_services = [campaign_services]

            campaign_services = [
                str(service or "").strip()
                for service in campaign_services
                if str(service or "").strip()
            ]

            if not campaign_name:
                campaign_name = str(
                    campaign_info.get("name")
                    if isinstance(campaign_info, dict)
                    else ""
                ).strip()

            campaign_handle = f"@{campaign_name.strip().lstrip('@')}" if campaign_name else ""

            support_profile_name = str(
                social_media_account.get("account_name")
                or social_media_account.get("name")
                or ""
            ).strip()

            support_profile_role = str(
                social_media_account.get("account_kind")
                or profile_context.get("support_profile_role")
                or ""
            ).strip()

            if not support_profile_name:
                support_profile_name = "the team"

            is_video_post = False
            image_description = ""
            image_url = ""

            try:
                is_video_post = self.post_media_service.current_post_has_video()
            except Exception:
                is_video_post = False

            if not is_video_post:
                try:
                    ok_image_description, image_url, image_description = (
                        self.post_media_service.analyze_current_post_image()
                    )

                    if not ok_image_description or not image_description:
                        image_description = ""
                        image_url = ""
                except Exception:
                    image_description = ""
                    image_url = ""

            used_messages = self.get_used_messages_by_category(category)

            source_name = "prospecting_saved_post_b2b_referral"

            campaign_services_json = json.dumps(campaign_services or [], ensure_ascii=False)
            campaign_strategy_json = json.dumps(campaign_strategy or {}, ensure_ascii=False)
            campaign_info_json = (
                json.dumps(campaign_info or {}, ensure_ascii=False)
                if isinstance(campaign_info, dict)
                else json.dumps({"raw": str(campaign_info or "")}, ensure_ascii=False)
            )
            used_messages_json = json.dumps(used_messages[:25], ensure_ascii=False)
            recent_comments_json = json.dumps(used_messages[-20:], ensure_ascii=False)
            language_prompt = self._build_language_prompt()
            output_language = self.get_bot_personality_language()
            industry_rules_prompt = self._get_industry_rules_prompt(campaign_info, campaign_strategy)

            user_prompt = f"""
You are an expert Instagram commercial prospecting comment writer for a local business.

Generate ONE short, natural Instagram comment.

{language_prompt}

{industry_rules_prompt}

This prompt uses the campaign-specific rules above whenever a campaign type is supplied.
Do NOT assume the business is cleaning.
Do NOT assume the business is real estate.
Do NOT assume the business niche unless it is clearly supported by CAMPAIGN_INFO or CAMPAIGN_SERVICES.

This prompt supports BOTH normal prospecting and B2B referral prospecting.
Do NOT write generic compliments.
Do NOT write a polished ad.
Do NOT sound like the official business page.

The comment is posted from a support/personal profile connected to the campaign business.

━━━━━━━━━━━━━━━━━━━━━━━━
INPUT
━━━━━━━━━━━━━━━━━━━━━━━━

PROSPECT PROFILE:
USERNAME = "{author_username}"
PROFILE_CATEGORY = "{profile_category}"
PROFILE_DESCRIPTION = "{profile_description}"

POST:
CAPTION_TEXT = "{caption}"
ANALYSIS_REASON = "{analysis_reason}"
IMAGE_DESCRIPTION = "{image_description if image_description else 'not_available'}"
POST_TYPE = "{'video' if is_video_post else 'image'}"

CAMPAIGN:
CAMPAIGN_NAME = "{campaign_name}"
CAMPAIGN_HANDLE = "{campaign_handle}"
CAMPAIGN_INFO = {campaign_info_json}
CAMPAIGN_SERVICES = {campaign_services_json}
CAMPAIGN_STRATEGY = {campaign_strategy_json}

COMMERCIAL CLASSIFICATION FROM PROSPECTING:
{json.dumps(qualification, ensure_ascii=False)}

If COMMERCIAL CLASSIFICATION FROM PROSPECTING is populated, treat its
selected_service, mode, b2b_target_type, b2b_angle, b2b_confidence,
request_directness and service_match_reason as the already-tested
prospecting classification. Do not replace that classification with a
generic industry assumption. The comment must use the selected service
and angle when they are compatible with the campaign services.

SUPPORT PROFILE:
SUPPORT_PROFILE_NAME = "{support_profile_name}"
SUPPORT_PROFILE_ROLE = "{support_profile_role}"

USED_MESSAGES = {used_messages_json}
RECENT_COMMENTS = {recent_comments_json}

━━━━━━━━━━━━━━━━━━━━━━━━
CORE OBJECTIVE
━━━━━━━━━━━━━━━━━━━━━━━━

Write a warm Instagram commercial prospecting comment.
For b2b_referral, open the door to referrals, partnership, client support,
project support, mutual business support, or becoming a useful service/resource contact.
For normal_prospecting, softly connect the selected campaign service to the
business opportunity shown by the post.

━━━━━━━━━━━━━━━━━━━━━━━━
VALID B2B TARGETS
━━━━━━━━━━━━━━━━━━━━━━━━

Only comment if the post/profile clearly involves a business, professional,
creator, organization, operator, or service provider with a reasonable
commercial connection to CAMPAIGN_SERVICES. For b2b_referral, that connection
should support referral/partnership/client support. For normal_prospecting,
the business itself may be the potential customer.

Examples of valid B2B targets may include, depending on the campaign:
- realtor
- broker
- property manager
- landlord
- apartment manager
- Airbnb host
- short-term rental manager
- contractor
- construction company
- remodeling company
- moving company
- event planner
- venue
- photographer
- videographer
- beauty professional
- local business owner
- office/commercial operator
- restaurant or hospitality business
- automotive business
- home service business
- professional service provider
- community business page
- any business whose clients may reasonably need CAMPAIGN_SERVICES

IMPORTANT:
The target type must make sense for the actual campaign.
Do not force a B2B angle when mode is not b2b_referral.
Do not force any commercial angle if the campaign services and the
post/profile do not logically connect.

━━━━━━━━━━━━━━━━━━━━━━━━
SKIP RULE
━━━━━━━━━━━━━━━━━━━━━━━━

Return skip_post true if:
- the post is personal, vague, emotional-only, entertainment-only, meme-like, or unrelated
- there is no clear commercial opportunity
- the post/profile is a direct competitor advertising the same main services
- the only possible comment would be a generic compliment
- the only possible comment would be an unsupported direct sales pitch
- CAMPAIGN_SERVICES are empty or too unclear to choose one relevant offer
- the campaign service does not reasonably connect to the post/profile context

━━━━━━━━━━━━━━━━━━━━━━━━
GROUNDING RULE
━━━━━━━━━━━━━━━━━━━━━━━━

Use only facts clearly supported by:
1. CAPTION_TEXT
2. ANALYSIS_REASON
3. IMAGE_DESCRIPTION
4. PROFILE_CATEGORY
5. PROFILE_DESCRIPTION
6. CAMPAIGN_INFO and CAMPAIGN_SERVICES
7. CAMPAIGN_STRATEGY only as soft supporting context

Do NOT invent:
- client needs
- project needs
- event details
- property details
- business type
- service needs
- location details
- partnership opportunity
- specific service fit
unless clearly supported by the inputs.

Do NOT mention hashtags.
Do NOT mention exact cities/neighborhoods unless clearly supported by the post text.

━━━━━━━━━━━━━━━━━━━━━━━━
CAMPAIGN OFFER MATCHING
━━━━━━━━━━━━━━━━━━━━━━━━

Choose exactly ONE relevant campaign offer.
The offer must come from CAMPAIGN_SERVICES or be a very close natural wording of one CAMPAIGN_SERVICE.

Do NOT invent services.
Do NOT list many services.
Do NOT mention unrelated services.
Do NOT mention a service just because it sounds good.
The selected offer must clearly support the commercial angle. When mode is
b2b_referral it must fit the referral/partnership relationship; when mode is
normal_prospecting it must fit the direct business opportunity.

━━━━━━━━━━━━━━━━━━━━━━━━
COMMENT STYLE
━━━━━━━━━━━━━━━━━━━━━━━━

- Instagram-native.
- Short, human, direct.
- 1 to 2 sentences.
- Ideal length: 120 to 240 characters.
- Hard maximum: 280 characters.
- 0 or 1 emoji maximum.
- No hashtags.
- No links.
- No phone numbers.
- No "book now".
- No "DM us".
- No "message us".
- No "contact us".
- No "schedule today".
- No "reach out".
- No "let us know".
- No "we have availability".
- No "this week".
- No hard sales CTA.
- No corporate tone.
- No fake excitement.
- No generic filler.

━━━━━━━━━━━━━━━━━━━━━━━━
VOICE
━━━━━━━━━━━━━━━━━━━━━━━━

The comment must sound like a real support profile connected to the campaign business.

Allowed introduction styles are structural examples only:
- "I’m {support_profile_name} with {campaign_handle}"
- "I work with {campaign_handle}"
- "I’m connected with {campaign_handle}"
- "I help with {campaign_handle}"

Only say “I own” or “I run” if SUPPORT_PROFILE_ROLE clearly means owner/founder.
Otherwise, never pretend to be the owner.

━━━━━━━━━━━━━━━━━━━━━━━━
B2B CTA
━━━━━━━━━━━━━━━━━━━━━━━━

For b2b_referral, the CTA must be about referral, partnership, client support,
project support, resource support, or mutual business support.
For normal_prospecting, use a soft service-oriented connection without a hard CTA.

Good generic CTA styles are structural examples only:
- "Could be a good referral fit."
- "Open to connecting for future referrals."
- "Happy to support clients when it makes sense."
- "Could be a helpful contact for your clients."
- "Open to supporting each other with referrals."
- "Could be a useful resource for future client needs."
- "Happy to connect as a service partner."
- "Open to building a local referral connection."

For normal_prospecting, prefer soft service-oriented endings such as:
- "Could be useful for your next growth push."
- "That service could fit what you're building."
- "Could be a helpful resource as you grow."

Bad CTA styles:
- "DM us"
- "message us"
- "contact us"
- "reach out"
- "let me know"
- "book now"
- "schedule today"
- "if you need help"
- "we have availability"
- "send me details"

━━━━━━━━━━━━━━━━━━━━━━━━
ANTI-REPETITION
━━━━━━━━━━━━━━━━━━━━━━━━

Compare against RECENT_COMMENTS and USED_MESSAGES.

Do NOT reuse:
- the same opener
- the same CTA
- the same emoji
- the same structure
- the same "Hi! I noticed..." pattern
- the same "Would love to connect..." ending
- the same service wording if a natural alternative exists

Make the new comment structurally different from the last 5 comments.

━━━━━━━━━━━━━━━━━━━━━━━━
SELF-CHECK
━━━━━━━━━━━━━━━━━━━━━━━━

Before returning, verify:
1. The post/profile supports a real B2B referral opportunity.
2. The selected offer comes from CAMPAIGN_SERVICES.
3. The selected offer logically matches the post/profile context.
4. The comment sounds like a real person, not an official business page.
5. The comment includes CAMPAIGN_HANDLE.
6. The comment includes exactly ONE selected offer.
7. The comment includes a referral/partner/client-support/project-support/mutual-support angle.
8. The comment is not a direct consumer sales pitch.
9. The comment is not too long for Instagram.
10. The comment does not invent unsupported details.
11. The comment is not too similar to USED_MESSAGES.
12. If the commercial angle is weak, return skip_post true.
13. The final comment_text is written exclusively in OUTPUT_LANGUAGE.

━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━

Return only valid JSON.
No explanations.
No markdown.
No code fences.

If commenting, use exactly this structure:

{{
  "comment_text": "comment here",
  "skip_post": false,
  "has_b2b_referral_opportunity": true,
  "service_confidence": "high",
  "service_matched": "one campaign service/offer",
  "metadata": {{
    "source": "{source_name}",
    "category": "{category}",
    "image_url": "{image_url}",
    "author_username": "{author_username}",
    "post_caption": "{caption}",
    "analysis_reason": "{analysis_reason}",
    "image_description": "{image_description}",
    "profile_category": "{profile_category}",
    "profile_description": "{profile_description}",
    "campaign_services": {campaign_services_json},
    "post_type": "{'video' if is_video_post else 'image'}",
    "output_language": "{output_language}",
    "tone": "tone label",
    "focus": "commercial_prospecting",
    "voice": "support_profile",
    "theme": "main topic",
    "mood": "mood",
    "intent": "why this B2B referral comment works",
    "selected_service": "one campaign service/offer",
    "campaign_business_type": "inferred campaign business type from CAMPAIGN_INFO/CAMPAIGN_SERVICES",
    "b2b_target_type": "realtor/property_manager/contractor/moving_company/event_planner/local_business/etc or null",
    "b2b_angle": "referral/partnership/client_support/project_support/service_partner/mutual_support",
    "service_match_reason": "short reason why the selected offer fits",
    "b2b_confidence": "high, medium, or low"
  }}
}}

If skipping, use exactly this structure:

{{
  "comment_text": "",
  "skip_post": true,
  "has_b2b_referral_opportunity": false,
  "service_confidence": "low",
  "service_matched": "",
  "metadata": {{
    "source": "{source_name}",
    "category": "{category}",
    "tone": "none",
    "focus": "commercial_prospecting",
    "voice": "support_profile",
    "theme": "not applicable",
    "mood": "not applicable",
    "intent": "skipped because no clear B2B referral opportunity was supported",
    "selected_service": null,
    "campaign_business_type": "unknown",
    "b2b_target_type": null,
    "b2b_angle": null,
    "service_match_reason": "not applicable",
    "b2b_confidence": "low",
    "output_language": "{output_language}"
  }}
}}
""".strip()

            if hasattr(self.ai_api, "get_bot_ia_long_prompt"):
                ok_ai, raw_response = self.ai_api.get_bot_ia_long_prompt(
                    bot_personality_id,
                    user_prompt,
                )
            else:
                ok_ai, raw_response = self.ai_api.get_bot_ia(
                    bot_personality_id,
                    user_prompt,
                )

            print("=" * 60)
            print("[DEBUG] OUTPUT_LANGUAGE:", output_language)
            print("[DEBUG] CAMPAIGN_SERVICES:", campaign_services)
            print("[DEBUG] CAMPAIGN_STRATEGY:", campaign_strategy)
            print("[DEBUG] CAMPAIGN_NAME:", campaign_name)
            print("[DEBUG] CAMPAIGN_HANDLE:", campaign_handle)
            print("[DEBUG] SUPPORT_PROFILE_NAME:", support_profile_name)
            print("[DEBUG] CAPTION:", caption)
            print("[DEBUG] ANALYSIS_REASON:", analysis_reason)
            print("[DEBUG] IMAGE_DESCRIPTION:", image_description)
            print("[DEBUG] PROFILE_CATEGORY:", profile_category)
            print("[DEBUG] PROFILE_DESCRIPTION:", profile_description)
            print("[DEBUG] IS_VIDEO:", is_video_post)
            print("=" * 60)

            if not ok_ai or not raw_response:
                self.log.warning("AI did not return B2B prospecting comment.")
                return False, None

            parsed = self.parse_ai_prospecting_b2b_response(raw_response)

            if not parsed:
                self.log.warning("Could not parse B2B prospecting comment response.")
                self.log.warning("Raw B2B response was: %s", raw_response)
                return False, None

            if bool(parsed.get("skip_post", False)):
                self.log.info(
                    "B2B prospecting comment skipped by AI. metadata=%s",
                    parsed.get("metadata", {}),
                )
                return False, None

            if not self._validate_campaign_comment_policy(
                parsed, campaign_info, campaign_strategy, used_messages
            ):
                return False, None

            comment_text = str(parsed.get("comment_text", "")).strip()
            metadata = parsed.get("metadata", {}) or {}

            comment_text = self._sanitize_b2b_referral_comment_text(comment_text)

            if not comment_text:
                self.log.warning("Generated B2B comment_text came back empty after sanitize.")
                return False, None

            self._save_generated_comment(
                account_id=account_id,
                comment_text=comment_text,
                category=category,
                metadata=metadata,
            )

            return True, comment_text

        except Exception as e:
            self.log.warning(
                "Error generating B2B prospecting comment from saved post: %s",
                str(e),
            )
            return False, None

    # =========================================================
    # SAFE FOLLOWBACK COMMENT
    # =========================================================

    def generate_comment_from_current_post_context_safe(
        self,
        category: str = "comentario_publicacion_seguidor",
    ) -> Tuple[bool, Optional[str]]:
        """
        Versión segura para followback.

        Diferencia contra generate_comment_from_current_post_context():
        - La IA SOLO devuelve {"comment_text": "..."}
        - La metadata se arma en Python
        - Evita romper JSON cuando caption o descripción tienen comillas internas
        """
        try:
            account_id = self.get_account_id()
            bot_personality_id = self.get_bot_personality_id()

            if not account_id:
                self.log.warning("social_media_account.id was not found.")
                return False, None

            if not bot_personality_id:
                self.log.warning("bot_personality.id was not found.")
                return False, None

            ok_image_description, image_url, description = (
                self.post_media_service.analyze_current_post_image()
            )

            if not ok_image_description or not description:
                self.log.warning("Could not analyze current post image.")
                return False, None

            post_context = self.post_media_service.get_current_post_context() or {}

            author_username = str(post_context.get("author_username") or "").strip()
            caption = str(post_context.get("caption") or "").strip()

            if caption:
                caption = " ".join(caption.split())

            used_messages = self.get_used_messages_by_category(category)
            extra_prompt = self._build_used_messages_prompt(category, used_messages)
            language_prompt = self._build_language_prompt()
            output_language = self.get_bot_personality_language()

            caption_for_prompt = caption if caption else "not_available"
            author_for_prompt = author_username if author_username else "not_available"

            user_prompt = f"""
Generate ONE short Instagram comment for the CURRENT POST.

{language_prompt}

POST_CONTEXT:
- AUTHOR_USERNAME = {author_for_prompt}
- POST_CAPTION = {caption_for_prompt}
- IMAGE_DESCRIPTION = {description}

TASK:
Understand the real purpose of the post using POST_CAPTION and IMAGE_DESCRIPTION.
Then write ONE short natural Instagram comment.

IMPORTANT:
You must infer the post type from the caption + image together.

Possible post types:
- followback_growth
- generic_social
- art_design
- service_offer
- promotional_post
- motivational_post
- community_engagement

PRIORITY ORDER:
1. Understand the post intent from POST_CAPTION.
2. Use IMAGE_DESCRIPTION only as supporting context.
3. Write a comment that matches the post purpose.
4. Do NOT focus on visual design unless the post is clearly about art/design.

STRICT RULES:
- The comment must feel like a real human Instagram comment.
- It must fit the bot personality.
- It must not sound salesy.
- It must not sound robotic.
- Do not ask questions.
- Do not use hashtags.
- Do not copy the caption literally.
- Do not repeat long fragments from the caption.
- Do not mention the author username.
- Maximum 8 words.
- Single line only.
- 0 or 1 emoji max, only if natural.

FOLLOWBACK / GROWTH RULES:
If the post is about follow for follow, followback, mutual support, engagement, followers, likes, comments, or growth:
- the comment MUST align with that theme
- the comment should sound like support, participation, mutual growth, or real engagement
- the comment must NOT sound generic
- the comment must NOT focus on graphic design

GOOD EXAMPLES for followback_growth are structural examples only:
- "Here for real growth 🙌"
- "Supporting genuine followback energy"
- "Mutual support always matters"
- "Growing together feels better"
- "Real support goes far"

BAD EXAMPLES:
- "Beautiful design!"
- "Nice colors!"
- "Great post!"
- "Amazing content!"
- "Love this layout!"

{extra_prompt}

Return ONLY one valid JSON object with this exact structure:

{{
  "comment_text": "comment here"
}}

Do not include metadata.
Do not include explanations.
Do not wrap the JSON in markdown.
""".strip()

            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                self.log.warning("AI did not return any safe contextual comment.")
                return False, None

            parsed = self.parse_ai_comment_text_only_response(
                raw_response, campaign_type=self._get_campaign_type(), used_messages=used_messages
            )

            if not parsed:
                self.log.warning("Could not parse safe AI contextual comment response.")
                self.log.warning("Raw safe AI response was: %s", raw_response)
                return False, None

            comment_text = str(parsed.get("comment_text") or "").strip()

            if not comment_text:
                self.log.warning("Safe generated comment_text came back empty.")
                return False, None

            metadata = {
                "source": "image_caption_context_safe",
                "category": category,
                "image_url": image_url,
                "author_username": author_username,
                "post_caption": caption,
                "visual_description": description,
                "output_language": output_language,
                "tone": "detected tone",
                "focus": "caption+image",
            }

            self._save_generated_comment(
                account_id=account_id,
                comment_text=comment_text,
                category=category,
                metadata=metadata,
            )

            return True, comment_text

        except Exception as e:
            self.log.warning(
                "Error generating SAFE comment from post context: %s",
                str(e),
            )
            return False, None
