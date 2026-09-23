import logging
import os
import random

from app.services.instagram_content_timing_context_service import (
    InstagramContentTimingContextService,
)
from app.services.instagram_post_publisher_service import (
    InstagramPostPublisherService,
)


class ShareInstagramPostTask:
    def __init__(self, browser, ai_api, account_api, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data or {}
        self.log = logging.getLogger(self.__class__.__name__)
        self.timing_context_service = InstagramContentTimingContextService()
        self.post_publisher = InstagramPostPublisherService(
            browser=self.browser,
            logger=self.log,
        )
        self.last_error = ""

    def execute(self) -> bool:
        try:
            self.log.info("Starting ShareInstagramPostTask.")

            self.browser.time_sleep(2)

            self.post_data = self._generate_post_asset()
            if not self.post_data:
                error_message = self.last_error or "No se pudo preparar el asset del post."
                self.log.warning(error_message)
                return f"✗ {error_message}"

            images = self.post_data.get("images", [])
            caption = self.post_data.get("caption_with_hashtags", "")

            ok_publish = self.post_publisher.publish_post(
                media_paths=images,
                caption=caption,
            )

            if not ok_publish:
                error_message = self.post_publisher.last_error or "No se pudo publicar el post."
                self.log.warning(error_message)
                return f"✗ {error_message}"

            social_media_account = self.data.get("social_media_account") or {}
            social_media_account_id = social_media_account.get("id")

            caption_text = self.post_data.get("caption_with_hashtags", "")
            overlay_phrase = self.post_data.get("headline", "")

            ok_memory, memory_response = self.ai_api.save_content_memory(
                social_media_account_id=social_media_account_id,
                asset_type="post",
                caption_text=caption_text,
                overlay_phrase=overlay_phrase,
            )

            if not ok_memory:
                self.log.warning(
                    "No se pudo guardar content memory del post: %s",
                    memory_response,
                )

            self.log.info("Publicación completada correctamente.")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.log.exception("Error in ShareInstagramPostTask: %s", e)
            return f"✗ {self.last_error}"

    # =========================================================
    # DATA HELPERS
    # =========================================================
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

    def _get_effective_location(self) -> str:
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

        post_extra_context = str(custom_task.get("post_extra_context") or "").strip()
        if post_extra_context:
            parts.append(post_extra_context)

        return "\n\n".join(parts).strip()

    def _build_post_extra_context(self) -> str:
        base_extra_context = self._get_base_extra_context()

        extra_context = self.timing_context_service.build_combined_extra_context(
            data=self.data,
            asset_type="post",
            base_extra_context=base_extra_context,
        )

        self.log.info(
            "Extra context para post construido. length=%s",
            len(extra_context or ""),
        )

        return extra_context

    # =========================================================
    # ASSET GENERATION
    # =========================================================
    def _generate_post_asset(self) -> dict:
        bot_personality_id = self._get_bot_personality_id()
        social_media_account = self._get_social_media_account()

        username = (
            (social_media_account.get("other_credentials") or {}).get("User")
            or (social_media_account.get("other_credentials") or {}).get("user")
            or (social_media_account.get("other_credentials") or {}).get("username")
            or ""
        ).strip()

        account_kind = (social_media_account.get("account_kind") or "business").strip()
        social_media_account_id = social_media_account.get("id")

        if not bot_personality_id:
            self.last_error = "No se encontró bot_personality_id en el payload"
            self.log.warning(self.last_error)
            return {}

        if not username:
            self.last_error = "No se encontró username en other_credentials.User"
            self.log.warning(self.last_error)
            return {}

        extra_context = self._build_post_extra_context()
        effective_location = self._get_effective_location()

        ok_post, post_data = self.ai_api.generate_instagram_post_asset(
            bot_personality_id=bot_personality_id,
            social_media_account_id=social_media_account_id,
            username=username,
            campaign_name=self.data.get("campaign_name", ""),
            business_name=self.data.get("business_name", ""),
            category=self.data.get("category", ""),
            location=effective_location,
            extra_context=extra_context,
            account_kind=account_kind,
            post_mode=None,
            max_images=2,
            image_text_mode="mixed",
            size_image="1024x1024",
        )

        if not ok_post:
            self.last_error = f"No se pudo generar el post asset: {post_data}"
            self.log.warning(self.last_error)
            return {}

        images = post_data.get("images") or []
        caption_with_hashtags = (post_data.get("caption_with_hashtags") or "").strip()
        headline = (post_data.get("headline") or "").strip()

        if not images:
            self.last_error = "El endpoint devolvió 0 imágenes"
            self.log.warning(self.last_error)
            return {}

        valid_images = [img for img in images if img and os.path.exists(img)]

        if not valid_images:
            self.last_error = f"Las imágenes generadas no existen en disco: {images}"
            self.log.warning(self.last_error)
            return {}

        self.log.info(
            "Post asset generado desde API. images=%s | caption_len=%s | headline=%s",
            len(valid_images),
            len(caption_with_hashtags),
            headline,
        )

        return {
            "images": valid_images,
            "caption_with_hashtags": caption_with_hashtags,
            "headline": headline,
        }

    def _open_post_composer(self) -> bool:
        return self.post_publisher.open_post_composer()

    def _upload_post_media(self, media_paths: list[str]) -> bool:
        return self.post_publisher.upload_post_media(media_paths)

    def _click_next_button(self, label="Siguiente") -> bool:
        return self.post_publisher.click_next_button(label)

    def _write_caption(self, caption: str) -> bool:
        return self.post_publisher.write_caption(caption)

    def _click_share_button(self) -> bool:
        return self.post_publisher.click_share_button()