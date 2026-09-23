import json
import os
import random
from typing import Any, Optional

from app.utils.logger import get_logger
from app.api.prospecting_api import ProspectingAPI
from app.services.instagram_post_publisher_service import InstagramPostPublisherService
from app.services.instagram_story_publisher_service import InstagramStoryPublisherService

class InstagramCampaignServiceContentTask:
    """
    Tarea 15:
    Publica contenido relacionado con los servicios reales de la campaña
    asociada a la cuenta de Instagram.

    Características:
    - Usa campaña activa vinculada a la social_media_account.
    - Usa services_snapshot reales de la campaña.
    - Si custom_task trae service_name, usa ese servicio.
    - Si no trae service_name, elige un servicio aleatorio.
    - Si custom_task trae content_type, usa post/story.
    - Si no trae content_type, elige aleatorio.
    - Genera contenido más comercial, no genérico/lifestyle.
    - Obliga a mencionar el handle de campaña dentro del caption.
    - Para publicar post usa InstagramPostPublisherService directo.

    custom_task soportado:

    {
        "content_type": "post" | "story" | "random",
        "service_name": "Maid Service",
        "campaign_handle": "@expresscleanchicago",
        "post_mode": "single" | "carousel" | "auto",
        "max_images": 1,
        "image_text_mode": "clean" | "overlay" | "mixed",
        "size_image": "1024x1024",
        "story_style": "text_overlay" | "visual_clean" | "auto",
        "force_business_content": true,
        "promo_angle": "this week service availability",
        "extra_context": "texto adicional opcional"
    }
    """

    DEFAULT_POST_SIZE = "1024x1024"
    DEFAULT_STORY_SIZE = "1024x1536"

    VALID_IMAGE_SIZES = {
        "1024x1024",
        "1024x1536",
        "1536x1024",
        "auto",
    }

    def __init__(self, browser, ai_api, account_api, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data or {}
        self.log = get_logger(self.__class__.__name__)
        self.prospecting_api = ProspectingAPI()

        self.post_publisher = InstagramPostPublisherService(
            browser=self.browser,
            logger=self.log,
        )

        self.story_publisher = InstagramStoryPublisherService(
            browser=self.browser,
            logger=self.log,
        )

    # =========================================================
    # ENTRYPOINT
    # =========================================================
    def execute(self) -> bool:
        try:
            social_media_account = self._get_social_media_account()

            account_id = social_media_account.get("id")
            if not account_id:
                self.log.warning("[campaign-service-content] social_media_account.id no encontrado")
                return False

            bot_personality_id = self._get_bot_personality_id(social_media_account)
            if not bot_personality_id:
                self.log.warning("[campaign-service-content] bot_personality_id no encontrado")
                return False

            custom_task = self._get_custom_task()

            account_name = str(
                social_media_account.get("account_name")
                or social_media_account.get("username")
                or social_media_account.get("name")
                or f"account_{account_id}"
            ).strip()

            account_kind = str(
                custom_task.get("account_kind")
                or social_media_account.get("account_kind")
                or "business"
            ).strip().lower()

            force_business_content = bool(custom_task.get("force_business_content", True))
            if force_business_content:
                account_kind = "business"

            if account_kind not in {"business", "personal"}:
                account_kind = "business"

            ok_campaign, campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            self.log.info(
                "[campaign-service-content] campaign lookup | ok=%s | campaign=%s",
                ok_campaign,
                self._shorten(campaign),
            )

            if not ok_campaign or not isinstance(campaign, dict):
                self.log.warning(
                    "[campaign-service-content] No hay campaña activa para account_id=%s",
                    account_id,
                )
                return False

            services = self._extract_campaign_services(campaign)
            if not services:
                self.log.warning(
                    "[campaign-service-content] La campaña no tiene services_snapshot válido"
                )
                return False

            selected_service = self._select_service(
                services=services,
                custom_task=custom_task,
            )

            if not selected_service:
                self.log.warning("[campaign-service-content] No se pudo seleccionar servicio")
                return False

            content_type = self._resolve_content_type(custom_task)

            campaign_name = str(campaign.get("name") or "").strip()
            business_name = str(
                campaign.get("business_name")
                or campaign.get("name")
                or ""
            ).strip()

            campaign_handle = self._resolve_campaign_handle(
                campaign=campaign,
                custom_task=custom_task,
                fallback_name=campaign_name,
            )

            category = str(
                custom_task.get("category")
                or campaign.get("industry")
                or campaign.get("category")
                or selected_service
            ).strip()

            location = str(
                custom_task.get("location")
                or campaign.get("location")
                or ""
            ).strip()

            extra_context = self._build_extra_context(
                campaign=campaign,
                services=services,
                selected_service=selected_service,
                account_kind=account_kind,
                custom_task=custom_task,
                campaign_handle=campaign_handle,
                content_type=content_type,
            )

            self.log.info(
                "[campaign-service-content] listo | account_id=%s | kind=%s | content_type=%s | service=%s | campaign=%s | handle=%s",
                account_id,
                account_kind,
                content_type,
                selected_service,
                campaign_name,
                campaign_handle,
            )

            if content_type == "story":
                return self._generate_and_publish_story(
                    bot_personality_id=bot_personality_id,
                    account_name=account_name,
                    account_kind=account_kind,
                    campaign_name=campaign_name,
                    business_name=business_name,
                    category=category,
                    location=location,
                    selected_service=selected_service,
                    campaign_handle=campaign_handle,
                    extra_context=extra_context,
                    custom_task=custom_task,
                    social_media_account_id=account_id,
                )

            return self._generate_and_publish_post(
                bot_personality_id=bot_personality_id,
                account_name=account_name,
                account_kind=account_kind,
                campaign_name=campaign_name,
                business_name=business_name,
                category=category,
                location=location,
                selected_service=selected_service,
                campaign_handle=campaign_handle,
                extra_context=extra_context,
                custom_task=custom_task,
                social_media_account_id=account_id,
            )

        except Exception as e:
            self.log.exception("[campaign-service-content] Error ejecutando tarea: %s", e)
            return False

    # =========================================================
    # POST GENERATION + PUBLISH
    # =========================================================
    def _generate_and_publish_post(
        self,
        bot_personality_id: int,
        account_name: str,
        account_kind: str,
        campaign_name: str,
        business_name: str,
        category: str,
        location: str,
        selected_service: str,
        campaign_handle: str,
        extra_context: str,
        custom_task: dict,
        social_media_account_id: int,
    ) -> bool:
        try:
            post_mode = custom_task.get("post_mode")
            if post_mode == "auto":
                post_mode = None

            max_images = self._safe_int(custom_task.get("max_images"), default=1)
            max_images = max(1, min(max_images, 2))

            image_text_mode = str(
                custom_task.get("image_text_mode") or "overlay"
            ).strip().lower()

            if image_text_mode not in {"clean", "overlay", "mixed"}:
                image_text_mode = "overlay"

            size_image = self._normalize_size(
                custom_task.get("size_image"),
                default=self.DEFAULT_POST_SIZE,
            )

            ok_asset, asset = self.ai_api.generate_instagram_post_asset(
                bot_personality_id=bot_personality_id,
                social_media_account_id=social_media_account_id,
                username=account_name,
                campaign_name=campaign_name,
                business_name=business_name,
                category=category,
                location=location,
                extra_context=extra_context,
                post_mode=post_mode,
                max_images=max_images,
                image_text_mode=image_text_mode,
                size_image=size_image,
                account_kind=account_kind,
                memory_asset_type="post",
            )

            if not ok_asset or not isinstance(asset, dict):
                self.log.warning(
                    "[campaign-service-content] No se pudo generar post asset: %s",
                    asset,
                )
                return False

            image_paths = asset.get("images") or []
            raw_caption = str(asset.get("caption_with_hashtags") or "").strip()
            headline = str(asset.get("headline") or "").strip()

            if not image_paths:
                self.log.warning("[campaign-service-content] post asset sin imágenes")
                return False

            valid_images = [
                os.path.abspath(img)
                for img in image_paths
                if img and os.path.exists(img)
            ]

            if not valid_images:
                self.log.warning(
                    "[campaign-service-content] imágenes generadas no existen: %s",
                    image_paths,
                )
                return False

            if not raw_caption:
                self.log.warning("[campaign-service-content] post asset sin caption")
                return False

            caption = self._ensure_campaign_caption_rules(
                caption=raw_caption,
                campaign_handle=campaign_handle,
                selected_service=selected_service,
                custom_task=custom_task,
            )

            self.log.info(
                "[campaign-service-content] caption final=%s",
                caption,
            )

            ok_publish = self._publish_instagram_post(
                image_paths=valid_images,
                caption=caption,
            )

            if not ok_publish:
                self.log.warning("[campaign-service-content] Falló publicación de post")
                return False

            self._save_content_memory_safe(
                social_media_account_id=social_media_account_id,
                asset_type="post",
                caption_text=caption,
                overlay_phrase=headline,
            )

            self.log.info(
                "[campaign-service-content] post publicado OK | service=%s | images=%s",
                selected_service,
                valid_images,
            )
            return True

        except Exception as e:
            self.log.exception(
                "[campaign-service-content] Error generando/publicando post: %s",
                e,
            )
            return False

    def _publish_instagram_post(
        self,
        image_paths: list[str],
        caption: str,
    ) -> bool:
        try:
            return self.post_publisher.publish_post(
                media_paths=image_paths,
                caption=caption,
            )
        except Exception as e:
            self.log.exception(
                "[campaign-service-content] Error publicando post con InstagramPostPublisherService: %s",
                e,
            )
            return False

    # =========================================================
    # STORY GENERATION + PUBLISH
    # =========================================================
    def _generate_and_publish_story(
        self,
        bot_personality_id: int,
        account_name: str,
        account_kind: str,
        campaign_name: str,
        business_name: str,
        category: str,
        location: str,
        selected_service: str,
        campaign_handle: str,
        extra_context: str,
        custom_task: dict,
        social_media_account_id: int,
    ) -> bool:
        try:
            story_style = custom_task.get("story_style") or custom_task.get("forced_style")
            if story_style == "auto":
                story_style = None

            if story_style not in {None, "text_overlay", "visual_clean"}:
                story_style = None

            size_image = self._normalize_size(
                custom_task.get("size_image"),
                default=self.DEFAULT_STORY_SIZE,
            )

            ok_asset, asset = self.ai_api.generate_instagram_story_asset(
                bot_personality_id=bot_personality_id,
                username=account_name,
                campaign_name=campaign_name,
                business_name=business_name,
                category=category,
                location=location,
                extra_context=extra_context,
                forced_style=story_style,
                size_image=size_image,
                account_kind=account_kind,
            )

            if not ok_asset or not isinstance(asset, dict):
                self.log.warning(
                    "[campaign-service-content] No se pudo generar story asset: %s",
                    asset,
                )
                return False

            image_path = str(asset.get("image_path") or "").strip()
            headline = str(asset.get("headline") or "").strip()

            if not image_path or not os.path.exists(image_path):
                self.log.warning(
                    "[campaign-service-content] story asset inválido image_path=%s",
                    image_path,
                )
                return False

            ok_publish = self._publish_instagram_story(image_path=image_path)

            if not ok_publish:
                self.log.warning("[campaign-service-content] Falló publicación de story")
                return False

            self._save_content_memory_safe(
                social_media_account_id=social_media_account_id,
                asset_type="story",
                caption_text=f"{campaign_handle} - {selected_service}".strip(),
                overlay_phrase=headline,
            )

            self.log.info(
                "[campaign-service-content] story publicada OK | service=%s | image=%s",
                selected_service,
                image_path,
            )
            return True

        except Exception as e:
            self.log.exception(
                "[campaign-service-content] Error generando/publicando story: %s",
                e,
            )
            return False

    def _publish_instagram_story(self, image_path: str) -> bool:
        try:
            return self.story_publisher.publish_story(image_path=image_path)
        except Exception as e:
            self.log.exception(
                "[campaign-service-content] Error publicando story con InstagramStoryPublisherService: %s",
                e,
            )
            return False



    # =========================================================
    # CUSTOM TASK / CAMPAIGN HELPERS
    # =========================================================
    def _get_custom_task(self) -> dict:
        candidates = [
            self.data.get("custom_task"),
            (self.data.get("task") or {}).get("custom_task")
            if isinstance(self.data.get("task"), dict)
            else None,
            (self.data.get("task_bot") or {}).get("custom_task")
            if isinstance(self.data.get("task_bot"), dict)
            else None,
        ]

        for value in candidates:
            parsed = self._parse_jsonish(value)
            if isinstance(parsed, dict):
                return parsed

        return {}

    def _resolve_content_type(self, custom_task: dict) -> str:
        value = str(
            custom_task.get("content_type")
            or custom_task.get("asset_type")
            or custom_task.get("type")
            or "random"
        ).strip().lower()

        if value in {"post", "feed", "publication", "publicacion"}:
            return "post"

        if value in {"story", "historia", "stories", "history"}:
            return "story"

        return random.choice(["post", "story"])

    def _extract_campaign_services(self, campaign: dict) -> list[str]:
        raw_services = (
            campaign.get("services_snapshot")
            or campaign.get("services")
            or campaign.get("campaign_services")
            or []
        )

        if isinstance(raw_services, str):
            raw_services = [raw_services]

        services = []

        if isinstance(raw_services, list):
            for item in raw_services:
                if isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("service_name")
                        or item.get("primary_keyword")
                        or item.get("slug")
                        or ""
                    )
                else:
                    name = str(item or "")

                name = str(name or "").strip()
                if name:
                    services.append(name)

        unique = []
        seen = set()

        for service in services:
            key = service.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(service)

        return unique

    def _select_service(self, services: list[str], custom_task: dict) -> Optional[str]:
        if not services:
            return None

        requested = str(
            custom_task.get("service_name")
            or custom_task.get("service")
            or custom_task.get("selected_service")
            or ""
        ).strip()

        if requested:
            for service in services:
                if service.lower() == requested.lower():
                    return service

            for service in services:
                if requested.lower() in service.lower() or service.lower() in requested.lower():
                    return service

            self.log.warning(
                "[campaign-service-content] service_name solicitado no existe en campaña: %s | services=%s",
                requested,
                services,
            )

        return random.choice(services)

    def _resolve_campaign_handle(
        self,
        campaign: dict,
        custom_task: dict,
        fallback_name: str = "",
    ) -> str:
        value = str(
            custom_task.get("campaign_handle")
            or custom_task.get("campaign_username")
            or campaign.get("instagram_username")
            or campaign.get("instagram_handle")
            or campaign.get("handle")
            or campaign.get("username")
            or fallback_name
            or ""
        ).strip()

        value = value.strip()
        if not value:
            return ""

        value = value.lstrip("@").strip()
        value = value.replace(" ", "")

        if not value:
            return ""

        return f"@{value}"

    def _build_extra_context(
        self,
        campaign: dict,
        services: list[str],
        selected_service: str,
        account_kind: str,
        custom_task: dict,
        campaign_handle: str = "",
        content_type: str = "post",
    ) -> str:
        services_text = "\n".join(f"- {s}" for s in services)

        custom_extra = str(
            custom_task.get("extra_context")
            or custom_task.get("context")
            or ""
        ).strip()

        promo_angle = str(
            custom_task.get("promo_angle")
            or custom_task.get("offer_angle")
            or "this week service availability"
        ).strip()

        campaign_name = str(campaign.get("name") or "").strip()
        business_name = str(campaign.get("business_name") or campaign_name).strip()

        if not campaign_handle and campaign_name:
            campaign_handle = f"@{campaign_name.lstrip('@').replace(' ', '')}"

        return f"""
CAMPAIGN SERVICE CONTENT TASK

This is NOT a generic lifestyle post.
This is NOT a random inspirational post.
This is NOT just an aesthetic image.

The goal is to create a service-focused Instagram {content_type} for the campaign.

Campaign:
- Name: {campaign_name}
- Business name: {business_name}
- Campaign username/handle to mention in caption if this is a feed post: {campaign_handle}
- Platform: {campaign.get("platform", "instagram")}
- Industry: {campaign.get("industry", "")}

Selected service for this publication:
- {selected_service}

All valid campaign services:
{services_text}

PROMOTION ANGLE:
- {promo_angle}

CONTENT GOAL:
Create content that clearly offers or promotes the selected service.
The content must feel like a real business/service publication.

For feed post captions, the caption should sound like:
- "This week, {campaign_handle} is helping with {selected_service}..."
- "{campaign_handle} has availability for {selected_service}..."
- "Need help with {selected_service}? {campaign_handle} can help..."
- "Our team at {campaign_handle} is offering {selected_service}..."
- "Fresh, reliable {selected_service} for homes, apartments, offices, rentals, or businesses..."
depending on the selected service and campaign context.

STRICT FEED CAPTION RULES:
- If content_type is post, the caption MUST mention the campaign handle exactly once: {campaign_handle}
- Mention the handle naturally inside the sentence.
- Do NOT use the campaign handle only as a tag at the end.
- Do NOT put the handle alone.
- The selected service MUST be clearly mentioned in the caption.
- The caption must offer the service, not just describe a mood.
- Make it more commercial than lifestyle.
- It can mention availability this week if it sounds natural.
- Use a soft CTA.
- Allowed soft CTAs:
  - "Send a message to get started."
  - "Message us to check availability."
  - "Ask about this service today."
  - "Perfect for anyone who needs reliable help."

STRICT STORY RULES:
- If content_type is story, focus the image and overlay phrase on the selected service.
- The overlay phrase should be short, clear and service-related.
- Do not make a random motivational or city image.

GLOBAL RULES:
- Do NOT invent services outside the valid service list.
- Do NOT mention services that are not in the campaign.
- Do NOT include phone numbers.
- Do NOT include URLs.
- Do NOT include fake discounts.
- Do NOT say "free estimate" unless custom context says it.
- Do NOT create vague content like "peaceful spaces" without offering the service.

IMAGE RULES:
- The image should visually represent the selected service.
- Make the image look professional, attractive, and useful for an Instagram business publication.
- Avoid generic lifestyle imagery unrelated to the service.
- Avoid random city/night/nature photos unless directly connected to the service.
- If overlay text is used, make it service-related and promotional but not aggressive.
- Overlay text should be short and service-focused.

ACCOUNT BEHAVIOR:
This account is being used to promote the campaign services.
Even if the Instagram account type is personal/support, this task must create campaign-related service content.

CUSTOM EXTRA CONTEXT:
{custom_extra if custom_extra else "none"}
""".strip()

    def _ensure_campaign_caption_rules(
        self,
        caption: str,
        campaign_handle: str,
        selected_service: str,
        custom_task: dict,
    ) -> str:
        caption = str(caption or "").strip()
        campaign_handle = str(campaign_handle or "").strip()
        selected_service = str(selected_service or "").strip()

        if not caption or not campaign_handle:
            return caption

        caption_main, hashtags_block = self._split_caption_hashtags(caption)

        lower_main = caption_main.lower()
        handle_present = campaign_handle.lower() in lower_main
        service_present = selected_service.lower() in lower_main if selected_service else True

        promo_sentence = (
            f"This week, {campaign_handle} is helping with {selected_service}. "
            "Message us to check availability."
        )

        if not handle_present and not service_present:
            caption_main = f"{promo_sentence}\n\n{caption_main}".strip()

        elif not handle_present:
            caption_main = f"{campaign_handle} {caption_main}".strip()

        elif not service_present and selected_service:
            caption_main = (
                f"{caption_main}\n\nThis week we’re offering {selected_service}."
            ).strip()

        lines = [line.strip() for line in caption_main.splitlines() if line.strip()]
        if lines and lines[-1].strip().lower() == campaign_handle.lower():
            lines = lines[:-1]
            lines.insert(0, f"This week, {campaign_handle} is offering {selected_service}.")
            caption_main = "\n".join(lines).strip()

        caption_main = self._limit_handle_occurrences(
            caption_main,
            campaign_handle,
            max_occurrences=1,
        )

        final_caption = caption_main.strip()

        if hashtags_block:
            final_caption = f"{final_caption}\n\n{hashtags_block}".strip()

        return final_caption.strip()

    def _split_caption_hashtags(self, caption: str) -> tuple[str, str]:
        lines = [line.rstrip() for line in str(caption or "").splitlines()]
        main_lines = []
        hashtag_lines = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                main_lines.append(line)
                continue

            words = stripped.split()
            hashtag_word_count = sum(1 for w in words if w.startswith("#"))

            if words and hashtag_word_count >= max(1, len(words) // 2):
                hashtag_lines.append(stripped)
            else:
                main_lines.append(line)

        main = "\n".join(main_lines).strip()
        hashtags = "\n".join(hashtag_lines).strip()

        return main, hashtags

    def _limit_handle_occurrences(
        self,
        text: str,
        handle: str,
        max_occurrences: int = 1,
    ) -> str:
        if not text or not handle:
            return text

        parts = text.split(handle)

        if len(parts) <= max_occurrences + 1:
            return text

        rebuilt = parts[0]
        used = 0

        for part in parts[1:]:
            if used < max_occurrences:
                rebuilt += handle + part
                used += 1
            else:
                rebuilt += part

        return rebuilt

    # =========================================================
    # ACCOUNT HELPERS
    # =========================================================
    def _get_social_media_account(self) -> dict:
        value = self.data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def _get_bot_personality_id(self, social_media_account: dict) -> Optional[int]:
        try:
            bot_personality = social_media_account.get("bot_personality")
            if isinstance(bot_personality, dict) and bot_personality.get("id"):
                return int(bot_personality["id"])

            if social_media_account.get("bot_personality_id"):
                return int(social_media_account["bot_personality_id"])

            return None
        except Exception:
            return None

    def _save_content_memory_safe(
        self,
        social_media_account_id: int,
        asset_type: str,
        caption_text: str = "",
        overlay_phrase: str = "",
    ) -> None:
        try:
            if hasattr(self.ai_api, "save_content_memory"):
                self.ai_api.save_content_memory(
                    social_media_account_id=social_media_account_id,
                    asset_type=asset_type,
                    caption_text=caption_text,
                    overlay_phrase=overlay_phrase,
                )
        except Exception as e:
            self.log.warning("[campaign-service-content] No se pudo guardar memoria: %s", e)



    # =========================================================
    # GENERIC HELPERS
    # =========================================================
    def _parse_jsonish(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, (dict, list)):
            return value

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None

            try:
                return json.loads(text)
            except Exception:
                return None

        return None

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _normalize_size(self, value: Any, default: str) -> str:
        size = str(value or default or "").strip()

        if size not in self.VALID_IMAGE_SIZES:
            self.log.warning(
                "[campaign-service-content] size_image inválido=%s. Usando default=%s",
                size,
                default,
            )
            return default

        return size

    def _shorten(self, value: Any, max_len: int = 1200) -> str:
        try:
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False, default=str)

            value = value.replace("\n", " ").strip()

            if len(value) > max_len:
                return value[:max_len] + "...[truncated]"

            return value
        except Exception:
            return str(value)