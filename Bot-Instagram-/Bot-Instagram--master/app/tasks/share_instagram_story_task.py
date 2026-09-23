import logging
import os
import random

from app.services.instagram_content_timing_context_service import (
    InstagramContentTimingContextService,
)
from app.services.instagram_story_publisher_service import (
    InstagramStoryPublisherService,
)


class ShareInstagramStoryTask:
    def __init__(self, browser, ai_api, account_api, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data or {}
        self.log = logging.getLogger(self.__class__.__name__)
        self.timing_context_service = InstagramContentTimingContextService()

        self.story_publisher = InstagramStoryPublisherService(
            browser=self.browser,
            logger=self.log,
        )
        self.last_error = ""

    def execute(self) -> bool:
        try:
            self.log.info("Starting ShareInstagramStoryTask.")

            self.browser.time_sleep(2)

            image_path = self._generate_story_image()

            if not image_path:
                error_message = self.last_error or "No se pudo generar la imagen de la historia."
                self.log.warning(error_message)
                return f"✗ {error_message}"

            ok_publish = self.story_publisher.publish_story(image_path=image_path)

            if not ok_publish:
                error_message = self.story_publisher.last_error or "No se pudo publicar la historia."
                self.log.warning(error_message)
                return f"✗ {error_message}"

            self.log.info("Historia compartida correctamente.")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.log.exception("Error in ShareInstagramStoryTask: %s", e)
            return f"✗ {self.last_error}"

    def _get_social_media_account(self) -> dict:
        value = self.data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def _get_bot_personality(self) -> dict:
        social_media_account = self._get_social_media_account()

        value = (
            social_media_account.get("bot_personality")
            or self.data.get("bot_personality")
            or {}
        )

        return value if isinstance(value, dict) else {}

    def _get_bot_personality_id(self):
        social_media_account = self._get_social_media_account()

        nested_id = (social_media_account.get("bot_personality") or {}).get("id")
        if nested_id:
            return nested_id

        direct_id = social_media_account.get("bot_personality_id")
        if direct_id:
            return direct_id

        return None

    def _get_username(self) -> str:
        social_media_account = self._get_social_media_account()
        credentials = social_media_account.get("other_credentials") or {}

        username = (
            credentials.get("User")
            or credentials.get("user")
            or credentials.get("username")
            or ""
        )

        return str(username or "").strip()

    def _get_account_kind(self) -> str:
        social_media_account = self._get_social_media_account()
        return str(social_media_account.get("account_kind") or "business").strip()

    def _get_effective_location(self) -> str:
        """
        Prioridad:
        1. self.data["location"]
        2. social_media_account.bot_personality.location
        3. social_media_account.location
        4. custom_task.location
        """
        social_media_account = self._get_social_media_account()
        bot_personality = self._get_bot_personality()
        custom_task = self.data.get("custom_task") or {}

        if not isinstance(custom_task, dict):
            custom_task = {}

        location = (
            self.data.get("location")
            or bot_personality.get("location")
            or social_media_account.get("location")
            or custom_task.get("location")
            or ""
        )

        return str(location or "").strip()

    def _get_base_extra_context(self) -> str:
        """
        Conserva el contexto anterior que ya usabas, pero permite extenderlo
        desde custom_task sin romper compatibilidad.
        """
        custom_task = self.data.get("custom_task") or {}

        if not isinstance(custom_task, dict):
            custom_task = {}

        parts = []

        hashtag = str(self.data.get("hashtag") or "").strip()
        if hashtag:
            parts.append(hashtag)

        custom_extra_context = str(custom_task.get("extra_context") or "").strip()
        if custom_extra_context:
            parts.append(custom_extra_context)

        story_extra_context = str(custom_task.get("story_extra_context") or "").strip()
        if story_extra_context:
            parts.append(story_extra_context)

        return "\n\n".join(parts).strip()

    def _build_story_extra_context(self) -> str:
        """
        Construye el extra_context final para la IA.

        Incluye:
        - contexto viejo: hashtag / custom extra_context
        - timing context: UTC + location + language + reglas de fecha/hora
        """
        base_extra_context = self._get_base_extra_context()

        extra_context = self.timing_context_service.build_combined_extra_context(
            data=self.data,
            asset_type="story",
            base_extra_context=base_extra_context,
        )

        self.log.info(
            "Extra context para story construido. length=%s",
            len(extra_context or ""),
        )

        return extra_context

    def _generate_story_image(self) -> str:
        bot_personality_id = self._get_bot_personality_id()
        username = self._get_username()

        if not bot_personality_id:
            self.last_error = "No se encontró bot_personality_id en el payload"
            self.log.warning(self.last_error)
            return ""

        if not username:
            self.last_error = "No se encontró username en other_credentials.User"
            self.log.warning(self.last_error)
            return ""

        account_kind = self._get_account_kind()
        effective_location = self._get_effective_location()
        extra_context = self._build_story_extra_context()

        selected_style = random.choices(
            population=["text_overlay", "visual_clean"],
            weights=[40, 60],
            k=1,
        )[0]


        custom_task = self.data.get("custom_task") or {}
        if not isinstance(custom_task, dict):
            custom_task = {}

        size_image = str(custom_task.get("size_image") or "1024x1536").strip()

        if size_image not in {"1024x1024", "1024x1536", "1536x1024", "auto"}:
            size_image = "1024x1536"

        ok_story, story_data = self.ai_api.generate_instagram_story_asset(
            bot_personality_id=bot_personality_id,
            username=username,
            campaign_name=self.data.get("campaign_name", ""),
            business_name=self.data.get("business_name", ""),
            category=self.data.get("category", ""),
            location=effective_location,
            extra_context=extra_context,
            account_kind=account_kind,
            forced_style=selected_style,
            size_image=size_image,
        )

        if not ok_story:
            self.last_error = f"No se pudo generar la historia: {story_data}"
            self.log.warning(self.last_error)
            return ""

        image_path = (story_data.get("image_path") or "").strip()
        if not image_path:
            self.last_error = "La IA no devolvió image_path"
            self.log.warning(self.last_error)
            return ""

        if not os.path.exists(image_path):
            self.last_error = f"La imagen no existe en disco: {image_path}"
            self.log.warning(self.last_error)
            return ""

        self.log.info("Historia generada en: %s", image_path)
        return image_path