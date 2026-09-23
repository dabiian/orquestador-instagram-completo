import logging
import os

from app.tasks.share_instagram_post_task import ShareInstagramPostTask


class ShareInstagramFollowbackPostTask(ShareInstagramPostTask):
    """
    Tarea especializada para publicar un post normal de followback:
    - Sígueme y te sigo
    - Nos seguimos
    - Follow me and I follow back

    No usa timing context.
    No usa fecha/hora.
    No usa campañas.
    No usa servicios.
    Reutiliza el flujo Selenium completo de ShareInstagramPostTask.
    """

    def __init__(self, browser, ai_api, account_api, data: dict):
        super().__init__(browser, ai_api, account_api, data)
        self.log = logging.getLogger(self.__class__.__name__)

    def execute(self) -> bool:
        if not self._can_publish_followback_for_account():
            self.log.info(
                "Followback post omitido: la cuenta no aplica para este tipo de contenido."
            )
            return True

        return super().execute()

    def _get_custom_task(self) -> dict:
        value = self.data.get("custom_task") or {}
        return value if isinstance(value, dict) else {}

    def _get_account_kind(self) -> str:
        social_media_account = self._get_social_media_account()
        return str(social_media_account.get("account_kind") or "business").strip()

    def _can_publish_followback_for_account(self) -> bool:
        """
        Por defecto:
        - personal / creator / support / fan / fanpage -> sí
        - business -> no, salvo allow_business_followback=true
        """
        custom_task = self._get_custom_task()
        account_kind = self._get_account_kind().lower()

        allow_business_followback = bool(
            custom_task.get("allow_business_followback")
            or self.data.get("allow_business_followback")
        )

        if account_kind in {"personal", "creator", "support", "fan", "fanpage"}:
            return True

        if account_kind == "business" and allow_business_followback:
            return True

        if account_kind == "business":
            self.log.info(
                "Cuenta business detectada. Followback post omitido porque "
                "allow_business_followback no está habilitado."
            )
            return False

        return True

    def _get_followback_extra_context_from_custom_task(self) -> str:
        custom_task = self._get_custom_task()

        parts = []

        custom_extra_context = str(custom_task.get("extra_context") or "").strip()
        if custom_extra_context:
            parts.append(custom_extra_context)

        followback_extra_context = str(
            custom_task.get("followback_extra_context") or ""
        ).strip()
        if followback_extra_context:
            parts.append(followback_extra_context)

        topic = str(
            custom_task.get("topic")
            or custom_task.get("post_topic")
            or ""
        ).strip()
        if topic:
            parts.append(f"Requested topic: {topic}")

        return "\n\n".join(parts).strip()

    def _build_post_extra_context(self) -> str:
        """
        IMPORTANTE:
        Este método NO usa timing.
        Solo fuerza el modo followback.
        """
        custom_task = self._get_custom_task()

        followback_language = str(
            custom_task.get("followback_language")
            or self.data.get("followback_language")
            or ""
        ).strip()

        tone = str(
            custom_task.get("tone")
            or custom_task.get("followback_tone")
            or "friendly, casual, natural"
        ).strip()

        extra_from_custom_task = self._get_followback_extra_context_from_custom_task()

        instruction = f"""
FOLLOWBACK_POST_MODE:
CONTENT_MODE: followback_post

TASK:
Generate a normal Instagram post for mutual follow / followback.

MANDATORY GOAL:
The post MUST clearly invite people to follow this account and receive a follow back.

STRICT CONTENT RULES:
- This is NOT a campaign post.
- This is NOT a service post.
- This is NOT a business promotion.
- This is NOT a location/lifestyle/reflection post.
- Do NOT create neighborhood, city, coffee, evening, motivational, business, service, or aesthetic-only content.
- The post must be clearly about "sígueme y te sigo" / mutual follow / followback.

IMAGE RULES:
- Generate exactly 1 image.
- Use overlay text.
- The image headline MUST be directly related to followback.
- Valid headline examples:
  - "Sígueme y te sigo"
  - "Nos seguimos?"
  - "Activos por aquí"
  - "Te sigo de vuelta"
  - "Follow me back"
  - "Let's connect"
  - "Follow me and I'll follow back"
- Do not leave headline empty.
- Do not use a generic lifestyle headline.

CAPTION RULES:
- Caption must be short.
- Caption must clearly support mutual follow / followback.
- Caption should sound casual and human.
- Do not sound scammy, robotic, aggressive, or spammy.

HASHTAG RULES:
- Hashtags must be directly related to followback, mutual follows, Instagram community, active users, or connection.
- Use valid JSON strings for every hashtag.
- Every hashtag must start with #.
- Do not create malformed hashtags.
- Do not create generic location-only hashtags unless they are secondary.

LANGUAGE:
- Use the account language naturally.
- If preferred followback language is provided, prioritize it.
- Preferred followback language: {followback_language or "not provided"}

TONE:
- {tone}

EXTRA USER CONTEXT:
{extra_from_custom_task or "none"}
""".strip()

        self.log.info(
            "Extra context para followback post construido SIN timing. length=%s",
            len(instruction),
        )

        return instruction

    def _generate_post_asset(self) -> dict:
        bot_personality_id = self._get_bot_personality_id()
        social_media_account = self._get_social_media_account()
        credentials = social_media_account.get("other_credentials") or {}

        username = (
            credentials.get("User")
            or credentials.get("user")
            or credentials.get("username")
            or ""
        ).strip()

        account_kind = self._get_account_kind()
        social_media_account_id = social_media_account.get("id")

        if not bot_personality_id:
            self.log.warning("No se encontró bot_personality_id en el payload")
            return {}

        if not username:
            self.log.warning("No se encontró username en other_credentials.User")
            return {}

        extra_context = self._build_post_extra_context()

        ok_post, post_data = self.ai_api.generate_instagram_post_asset(
            bot_personality_id=bot_personality_id,
            social_media_account_id=social_media_account_id,
            username=username,

            # Vacío a propósito:
            # Esta tarea NO debe ser de campaña, servicios ni ubicación.
            campaign_name="",
            business_name="",
            category="",
            location="",

            extra_context=extra_context,
            account_kind=account_kind,
            post_mode="single",
            max_images=1,
            image_text_mode="overlay",
            size_image="1024x1024",
            memory_asset_type="followback_post",
        )

        if not ok_post:
            self.log.warning("No se pudo generar el followback post asset: %s", post_data)
            return {}

        images = post_data.get("images") or []
        caption_with_hashtags = (post_data.get("caption_with_hashtags") or "").strip()
        headline = (post_data.get("headline") or "").strip()

        if not images:
            self.log.warning("El endpoint devolvió 0 imágenes")
            return {}

        valid_images = [img for img in images if img and os.path.exists(img)]

        if not valid_images:
            self.log.warning("Las imágenes generadas no existen en disco: %s", images)
            return {}

        if not caption_with_hashtags:
            self.log.warning("El caption del followback post vino vacío")
            return {}

        if not headline:
            self.log.warning("El headline del followback post vino vacío")
            return {}

        self.log.info(
            "Followback post asset generado. images=%s | caption_len=%s | headline=%s",
            len(valid_images[:1]),
            len(caption_with_hashtags),
            headline,
        )

        return {
            "images": valid_images[:1],
            "caption_with_hashtags": caption_with_hashtags,
            "headline": headline,
        }