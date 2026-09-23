import random
import re
import unicodedata
import json
from typing import Optional


class InstagramFollowbackTextMixin:
    FOLLOWBACK_PATTERNS = [
        # Español
        r"\bsigueme y te sigo\b",
        r"\bsi?gueme y te sigo\b",
        r"\bya te segui\b",
        r"\bte sigo si me sigues\b",
        r"\bsi?gueme de vuelta\b",
        r"\bdevuelvo follow\b",
        r"\bte devuelvo follow\b",
        r"\bfollow x follow\b",
        r"\bf4f\b",

        # Inglés
        r"\bfollow me and i follow back\b",
        r"\bfollow for follow\b",
        r"\bfollow4follow\b",
        r"\bfollow for followback\b",
        r"\bfollow4followback\b",
        r"\bfollow back\b",
        r"\bi follow back\b",
        r"\bifb\b",
        r"\bf4f\b",
    ]

    NEGATIVE_PATTERNS = [
        r"\bbuy\b",
        r"\blink in bio\b",
        r"\bpromo\b",
        r"\bdiscount\b",
        r"\bshop\b",
        r"\bbooking\b",
        r"\bprecio\b",
        r"\bdescuento\b",
    ]

    def _get_social_media_account(self) -> dict:
        return self.data.get("social_media_account") or {}

    def _get_bot_personality(self) -> dict:
        social_media_account = self._get_social_media_account()
        return social_media_account.get("bot_personality") or {}

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""

        text = text.lower().strip()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"\s+", " ", text)
        return text

    def _is_followback_comment(self, text: str) -> bool:
        text = self._normalize_text(text)

        if not text:
            return False

        for pattern in self.NEGATIVE_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return False

        for pattern in self.FOLLOWBACK_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True

        return False

    def _get_bot_language(self) -> str:
        social_media_account = self._get_social_media_account()
        bot_personality = self._get_bot_personality()

        language = (
            bot_personality.get("language")
            or social_media_account.get("language")
            or "es"
        )

        language = str(language).strip().lower()

        if language in {"en", "english", "ingles", "inglés"}:
            return "en"

        return "es"

    def _get_search_term(self) -> str:
        language = self._get_bot_language()

        if language == "en":
            return "#followforfollowback"

        return "#siguemeytesigo"

    def _detect_followback_comment_language(self, text: str) -> str:
        text_norm = self._normalize_text(text)

        english_markers = [
            "follow me and i follow back",
            "follow for follow",
            "follow4follow",
            "follow for followback",
            "follow4followback",
            "follow back",
            "i follow back",
            "ifb",
            "like 4 like",
            "comment 4 comment",
        ]

        spanish_markers = [
            "sigueme y te sigo",
            "ya te segui",
            "te sigo si me sigues",
            "sigueme de vuelta",
            "devuelvo follow",
            "te devuelvo follow",
        ]

        if any(marker in text_norm for marker in english_markers):
            return "en"

        if any(marker in text_norm for marker in spanish_markers):
            return "es"

        return self._get_bot_language()

    def _get_followback_bot_personality_id(self) -> Optional[int]:
        try:
            return int(
                ((self.data.get("social_media_account") or {}).get("bot_personality") or {}).get("id")
            )
        except Exception:
            return None

    def _extract_followback_reply_json(self, raw_response) -> Optional[dict]:
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
                text = str(content).strip()
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()

                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    text = text[start:end + 1]

                parsed = json.loads(text)

            if not isinstance(parsed, dict):
                return None

            reply_text = str(parsed.get("reply_text", "")).strip()
            if not reply_text:
                return None

            parsed["reply_text"] = reply_text
            return parsed

        except Exception as e:
            self.log.warning("No se pudo parsear reply IA followback: %r", e)
            return None

    def _build_followback_reply_fallback(self, comment_text: str) -> str:
        lang = self._detect_followback_comment_language(comment_text)

        if lang == "en":
            options = [
                "I followed you, follow me back",
                "Done, I followed you",
                "Followed you already, follow me back",
            ]
            return random.choice(options)

        options = [
            "Ya te seguí, sígueme",
            "Listo, ya te seguí",
            "Ya te seguí, sígueme también",
        ]
        return random.choice(options)

    def _build_followback_reply(self, comment_text: str) -> str:
        cleaned_comment = str(comment_text or "").strip()
        lang = self._detect_followback_comment_language(cleaned_comment)
        bot_personality_id = self._get_followback_bot_personality_id()

        if not bot_personality_id:
            return self._build_followback_reply_fallback(cleaned_comment)

        user_prompt = f"""
You are generating ONE Instagram reply to a followback-style comment.

CONTEXT:
- This is a reply to a comment on a followback post.
- The bot already followed that person.
- ORIGINAL_COMMENT = {cleaned_comment}
- DETECTED_LANGUAGE = {lang}

GOAL:
Write a short natural reply that fits the original comment and the followback context.

STRICT RULES:
- Reply in the same language as the original comment when possible.
- Sound human and casual.
- Maximum 7 words.
- Single line only.
- No hashtags.
- No robotic tone.
- Do not always repeat the exact same structure.
- The reply must match the intention of the original comment.
- If the comment is about F4F, followback, teamwork, devuelvo, mutual support, align with that.
- Do not over-explain.
- The reply must explicitly encourage or invite the person to follow back.
- If the bot already followed them, the reply should naturally imply or say that they should follow back too.
- Avoid generic gratitude-only replies like "Thanks" or "Appreciate it" unless they also include a follow-back invitation.
- Preferred outcome: the reply should sound like a short followback exchange, not just a thank-you message.

Return ONLY one valid JSON object with this exact structure:
{{
  "reply_text": "your reply here"
}}
""".strip()

        ok_ai, raw_response = self.ai_api.get_bot_ia(
            bot_personality_id,
            user_prompt,
        )

        if not ok_ai or not raw_response:
            return self._build_followback_reply_fallback(cleaned_comment)

        parsed = self._extract_followback_reply_json(raw_response)
        if not parsed:
            return self._build_followback_reply_fallback(cleaned_comment)

        reply_text = str(parsed.get("reply_text", "")).strip()
        if not reply_text:
            return self._build_followback_reply_fallback(cleaned_comment)

        print(f"[followback] reply IA generado: {reply_text}")
        return reply_text

    def _validate_post_by_comments(
        self,
        comments_texts: list[str],
        min_matches: int = 2,
        min_comments_to_check: int = 10,
        max_comments_to_check: int = 12,
    ) -> bool:
        if not comments_texts:
            print("[followback] no hay textos de comentarios para validar")
            return False

        scan_limit = min(
            len(comments_texts),
            random.randint(min_comments_to_check, max_comments_to_check),
        )
        matches = 0

        for text in comments_texts[:scan_limit]:
            if self._is_followback_comment(text):
                matches += 1

        print(
            f"[followback] comentarios analizados: {scan_limit} | "
            f"compatibles encontrados: {matches}"
        )
        return matches >= min_matches