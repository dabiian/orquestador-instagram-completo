from datetime import datetime, timezone
from typing import Any, Dict, Optional


class InstagramContentTimingContextService:
    """
    Construye contexto temporal para generación de contenido en Instagram.

    Objetivo:
    - No quemar mapas de ciudades/timezones en Python.
    - No usar hora local del servidor.
    - Usar UTC universal + location de BotPersonality.
    - Dejar que la IA infiera hora local, día, temporada y fechas especiales.
    - Evitar posts/historias incoherentes tipo "Good morning" en la noche.
    - NO obligar a que todo sea sobre campaña, servicios u owner.
    """

    DEFAULT_LANGUAGE = "ESPAÑOL"
    DEFAULT_LOCATION = ""

    def build_combined_extra_context(
        self,
        *,
        data: dict,
        asset_type: str,
        base_extra_context: Optional[str] = "",
    ) -> str:
        base_extra_context = str(base_extra_context or "").strip()

        timing_context = self.build_timing_extra_context(
            data=data,
            asset_type=asset_type,
        )

        parts = []

        if base_extra_context:
            parts.append(
                "EXISTING_EXTRA_CONTEXT:\n"
                f"{base_extra_context}"
            )

        if timing_context:
            parts.append(timing_context)

        return "\n\n".join(parts).strip()

    def build_timing_extra_context(self, *, data: dict, asset_type: str) -> str:
        data = data or {}

        account_location = self._get_account_location(data)
        account_language = self._get_account_language(data)
        current_datetime_utc = self._get_current_datetime_utc(data)

        campaign_context = self._build_campaign_context(data)
        account_context = self._build_account_context(data)
        content_mode_context = self._build_content_mode_context(data)

        asset_type_clean = self._normalize_asset_type(asset_type)

        return f"""
TIMING_CONTEXT_FOR_INSTAGRAM_CONTENT:
Asset type: {asset_type_clean}
Account location: {account_location or "not provided"}
Account language: {account_language or self.DEFAULT_LANGUAGE}
Current UTC datetime: {current_datetime_utc}

ACCOUNT_CONTEXT:
{account_context}

CAMPAIGN_CONTEXT_AVAILABLE_BUT_OPTIONAL:
{campaign_context}

CONTENT_MODE:
{content_mode_context}

CRITICAL TIMING INSTRUCTIONS:
- Infer the account's likely local date, local time, weekday, daypart, season, and special-date relevance using Account location + Current UTC datetime.
- Do NOT assume the server local time is the account local time.
- Do NOT create morning content unless it is actually morning in the inferred local time of the account.
- Do NOT mention "good morning", "buenos días", breakfast, desayuno, sunrise, amanecer, start your day, empieza tu día, morning coffee, café de la mañana, or early-day routine unless locally appropriate.
- Do NOT create evening/night content unless it is actually evening or night in the inferred local time of the account.
- Do NOT mention a weekday unless it matches the inferred local weekday.
- Do NOT use holiday, seasonal, or special-date themes unless they are relevant to the inferred local date and location.
- If the local time or date is uncertain, create evergreen content that works at any time of day.

NORMAL CONTENT RULES:
- Do NOT force the post/story to be about campaign services.
- Do NOT force the post/story to mention the business, service, owner, campaign, or location unless it naturally fits.
- Normal content is allowed.
- Inspirational phrases are allowed.
- Simple visual posts are allowed.
- Lifestyle-style content is allowed.
- Soft brand presence is allowed.
- General engagement content is allowed.
- A post/story can be just a clean image with a short phrase if that fits the account personality.
- Keep the content natural for Instagram, not robotic.
- Avoid sounding like an ad unless the requested content mode explicitly asks for promotion.

CAMPAIGN USAGE RULES:
- Campaign, business, category, service, owner, or location context is available only as background.
- Use campaign/service context only if:
  1. custom_task.content_mode asks for it,
  2. custom_task.force_campaign_context is true,
  3. custom_task.force_service_context is true,
  4. custom_task.topic explicitly mentions campaign, service, business, owner, promotion, CTA, offer, or commercial content,
  5. the content naturally benefits from a very soft brand/service reference.
- If none of the above applies, generate a normal post/story adapted to time, date, location, and account personality.

IMAGE/TEXT RULES:
- The generated image text/headline and caption must both follow the timing rules.
- The image text can be minimal.
- Do not overload the image with service text unless service/promotion mode is explicitly requested.
- Match the account language unless the campaign or account context clearly indicates another language.

SAFE FALLBACK RULE:
If there is any uncertainty about the account's exact local time, avoid time-specific greetings and create neutral content that works morning, afternoon, evening, or night.
""".strip()

    def _get_social_media_account(self, data: dict) -> Dict[str, Any]:
        value = data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def _get_bot_personality(self, data: dict) -> Dict[str, Any]:
        social_media_account = self._get_social_media_account(data)

        value = (
            social_media_account.get("bot_personality")
            or data.get("bot_personality")
            or {}
        )

        return value if isinstance(value, dict) else {}

    def _get_custom_task(self, data: dict) -> Dict[str, Any]:
        value = data.get("custom_task") or {}
        return value if isinstance(value, dict) else {}

    def _get_execution_context(self, data: dict) -> Dict[str, Any]:
        root_context = data.get("execution_context") or {}
        custom_task = self._get_custom_task(data)
        custom_context = custom_task.get("execution_context") or {}

        result = {}

        if isinstance(custom_context, dict):
            result.update(custom_context)

        if isinstance(root_context, dict):
            result.update(root_context)

        return result

    def _get_current_datetime_utc(self, data: dict) -> str:
        execution_context = self._get_execution_context(data)

        current_utc = (
            execution_context.get("current_datetime_utc")
            or data.get("current_datetime_utc")
            or ""
        )

        current_utc = str(current_utc or "").strip()

        if current_utc:
            return current_utc

        return datetime.now(timezone.utc).isoformat()

    def _get_account_location(self, data: dict) -> str:
        social_media_account = self._get_social_media_account(data)
        bot_personality = self._get_bot_personality(data)
        custom_task = self._get_custom_task(data)

        location = (
            data.get("location")
            or bot_personality.get("location")
            or social_media_account.get("location")
            or custom_task.get("location")
            or self.DEFAULT_LOCATION
        )

        return str(location or "").strip()

    def _get_account_language(self, data: dict) -> str:
        social_media_account = self._get_social_media_account(data)
        bot_personality = self._get_bot_personality(data)
        custom_task = self._get_custom_task(data)

        language = (
            data.get("language")
            or bot_personality.get("language")
            or social_media_account.get("language")
            or custom_task.get("language")
            or self.DEFAULT_LANGUAGE
        )

        return str(language or self.DEFAULT_LANGUAGE).strip()

    def _build_account_context(self, data: dict) -> str:
        social_media_account = self._get_social_media_account(data)
        bot_personality = self._get_bot_personality(data)

        account_name = (
            social_media_account.get("account_name")
            or social_media_account.get("name")
            or ""
        )

        account_kind = (
            social_media_account.get("account_kind")
            or social_media_account.get("kind")
            or ""
        )

        personality_name = bot_personality.get("name") or ""
        personality_location = bot_personality.get("location") or ""
        personality_language = bot_personality.get("language") or ""
        personality_style = bot_personality.get("communication_style") or ""
        personality_preferences = bot_personality.get("preferences") or ""
        personality_dislikes = bot_personality.get("dislikes") or ""

        owner = social_media_account.get("owner") or {}
        has_owner = isinstance(owner, dict) and bool(owner)

        owner_context = ""
        if has_owner:
            owner_context = (
                f"- Owner exists: yes\n"
                f"- Owner id: {owner.get('id', '')}\n"
                f"- Owner URL(s): {owner.get('owner_urls', '')}"
            )
        else:
            owner_context = "- Owner exists: no"

        return "\n".join([
            f"- Account name: {account_name}",
            f"- Account kind: {account_kind}",
            f"- Bot personality name: {personality_name}",
            f"- Bot personality location: {personality_location}",
            f"- Bot personality language: {personality_language}",
            f"- Bot personality communication style: {personality_style}",
            f"- Bot personality preferences: {personality_preferences}",
            f"- Bot personality dislikes: {personality_dislikes}",
            owner_context,
        ]).strip()

    def _build_campaign_context(self, data: dict) -> str:
        custom_task = self._get_custom_task(data)

        campaign_name = (
            data.get("campaign_name")
            or custom_task.get("campaign_name")
            or ""
        )

        business_name = (
            data.get("business_name")
            or custom_task.get("business_name")
            or ""
        )

        category = (
            data.get("category")
            or custom_task.get("category")
            or ""
        )

        location = (
            data.get("location")
            or custom_task.get("location")
            or ""
        )

        hashtag = (
            data.get("hashtag")
            or custom_task.get("hashtag")
            or ""
        )

        return "\n".join([
            f"- Campaign name: {campaign_name}",
            f"- Business name: {business_name}",
            f"- Category: {category}",
            f"- Provided campaign/location field: {location}",
            f"- Hashtag/extra campaign hint: {hashtag}",
            "- This campaign context is optional background, not a mandatory topic.",
        ]).strip()

    def _build_content_mode_context(self, data: dict) -> str:
        custom_task = self._get_custom_task(data)

        content_mode = str(
            custom_task.get("content_mode")
            or custom_task.get("post_mode")
            or custom_task.get("story_mode")
            or data.get("content_mode")
            or ""
        ).strip()

        topic = str(
            custom_task.get("topic")
            or custom_task.get("post_topic")
            or custom_task.get("story_topic")
            or data.get("topic")
            or ""
        ).strip()

        force_campaign_context = bool(
            custom_task.get("force_campaign_context")
            or data.get("force_campaign_context")
        )

        force_service_context = bool(
            custom_task.get("force_service_context")
            or data.get("force_service_context")
        )

        force_owner_context = bool(
            custom_task.get("force_owner_context")
            or data.get("force_owner_context")
        )

        if not content_mode:
            content_mode = "normal"

        return "\n".join([
            f"- Requested content mode: {content_mode}",
            f"- Requested topic: {topic}",
            f"- Force campaign context: {force_campaign_context}",
            f"- Force service context: {force_service_context}",
            f"- Force owner context: {force_owner_context}",
            "- If mode is normal, create normal content and do not force service/campaign promotion.",
            "- If mode is promotional, service, owner_services, campaign_related, or CTA, then use the campaign/service context more directly.",
        ]).strip()

    def _normalize_asset_type(self, asset_type: str) -> str:
        value = str(asset_type or "").strip().lower()

        if value in {"post", "posts", "instagram_post"}:
            return "post"

        if value in {"story", "stories", "history", "histories", "instagram_story"}:
            return "story"

        return value or "instagram_content"