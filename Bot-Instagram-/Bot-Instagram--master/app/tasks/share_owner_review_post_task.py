import logging
import os
import random
import re
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from app.api.prospecting_api import ProspectingAPI
from app.config.locators.share_instagram_post_locators import ShareInstagramPostLocators
from app.tasks.helpers.instagram_ui_helpers import InstagramUIHelpersMixin
from app.utils.instagram_url import _normalize_instagram_href


class ShareOwnerReviewPostTask(InstagramUIHelpersMixin):
    def __init__(self, browser, ai_api, account_api, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data or {}
        self.log = logging.getLogger(self.__class__.__name__)

        self.prospecting_api = ProspectingAPI()
        self.current_campaign = None
        self.post_data = {}

    def execute(self) -> bool:
        try:
            owner_profile_url = self._get_owner_instagram_url()
            if not owner_profile_url:
                self.log.warning("No se encontró la URL del owner.")
                return False

            owner_username = self._extract_owner_username(owner_profile_url)
            if not owner_username:
                self.log.warning("No se pudo extraer el username del owner.")
                return False

            self.browser.go_to_url(owner_profile_url)
            self.browser.time_sleep(random.randint(3, 5))

            self.post_data = self._generate_owner_review_post_asset(owner_username)
            if not self.post_data:
                self.log.warning("No se pudo preparar el asset del post owner review.")
                return False

            if not self._open_post_composer():
                self.log.warning("No se pudo abrir el composer de publicación.")
                return False

            if not self._upload_post_media(self.post_data.get("images", [])):
                self.log.warning("No se pudieron subir las imágenes del post.")
                return False

            if not self._click_next_button("Siguiente 1"):
                self.log.warning("No se pudo avanzar con el primer Siguiente.")
                return False

            if not self._click_next_button("Siguiente 2"):
                self.log.warning("No se pudo avanzar con el segundo Siguiente.")
                return False

            tagged_ok = self._tag_owner_on_post(owner_username)
            if not tagged_ok:
                self.log.warning("No se pudo etiquetar al owner. Se continúa sin romper el flujo.")

            caption = self.post_data.get("caption_with_hashtags", "")
            if not self._write_caption(caption):
                self.log.warning("No se pudo escribir el caption.")
                return False

            if not self._click_share_button():
                self.log.warning("No se pudo dar click en Compartir.")
                return False

            self.browser.time_sleep(random.randint(10, 12))

            self._save_owner_review_memory()
            self.log.info("Publicación owner review completada correctamente.")
            return True

        except Exception as e:
            self.log.exception("Error in ShareOwnerReviewPostTask: %s", e)
            return False

    # =========================================================
    # OWNER / CAMPAIGN RESOLUTION
    # =========================================================

    def _get_owner_instagram_url(self) -> str:
        try:
            custom_task = self._get_custom_task()

            direct_url = str(
                custom_task.get("owner_instagram_profile_url")
                or custom_task.get("owner_instagram_url")
                or custom_task.get("instagram_profile_url")
                or custom_task.get("profile_url")
                or self.data.get("owner_instagram_profile_url")
                or self.data.get("owner_instagram_url")
                or ""
            ).strip()

            if direct_url:
                return self._normalize_instagram_url(
                    direct_url,
                    source="custom_task_or_data",
                )

            campaign = self._get_campaign_from_payload()
            url_from_payload = self._extract_owner_url_from_campaign(campaign)

            if url_from_payload:
                self.current_campaign = campaign
                return self._normalize_instagram_url(
                    url_from_payload,
                    source="payload_campaign",
                )

            active_campaign = self._get_active_campaign_from_api()
            url_from_api = self._extract_owner_url_from_campaign(active_campaign)

            if url_from_api:
                self.current_campaign = active_campaign
                return self._normalize_instagram_url(
                    url_from_api,
                    source="active_campaign",
                )

            owner = self._get_owner_data()
            owner_url = str(
                owner.get("owner_instagram_profile_url")
                or owner.get("owner_instagram_url")
                or owner.get("instagram_profile_url")
                or owner.get("owner_urls")
                or ""
            ).strip()

            if owner_url:
                return self._normalize_instagram_url(
                    owner_url,
                    source="social_media_account.owner",
                )

            return ""

        except Exception as e:
            self.log.warning("Error obteniendo owner Instagram URL: %r", e)
            return ""

    def _get_owner_services(self) -> list[str]:
        try:
            custom_task = self._get_custom_task()

            services = (
                custom_task.get("owner_services")
                or custom_task.get("services_snapshot")
                or custom_task.get("services")
                or self.data.get("owner_services")
                or self.data.get("services_snapshot")
                or self.data.get("services")
            )

            normalized = self._normalize_services_list(services)
            if normalized:
                return normalized

            campaign = self._get_campaign_from_payload()
            normalized = self._extract_services_from_campaign(campaign)
            if normalized:
                self.current_campaign = campaign
                return normalized

            active_campaign = self._get_active_campaign_from_api()
            normalized = self._extract_services_from_campaign(active_campaign)
            if normalized:
                self.current_campaign = active_campaign
                return normalized

            owner = self._get_owner_data()
            normalized = self._normalize_services_list(owner.get("services"))
            if normalized:
                return normalized

            return []

        except Exception as e:
            self.log.warning("Error obteniendo servicios para owner review: %r", e)
            return []

    def _get_active_campaign_from_api(self) -> dict:
        if isinstance(self.current_campaign, dict) and self.current_campaign:
            return self.current_campaign

        try:
            social_media_account = self._get_social_media_account()
            account_id = social_media_account.get("id")

            if not account_id:
                self.log.warning("[owner_review] no hay social_media_account.id para campaña activa.")
                return {}

            ok_campaign, active_campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            self.log.info(
                "[owner_review] active campaign lookup | ok=%s | campaign=%s",
                ok_campaign,
                self._shorten_for_log(active_campaign),
            )

            if ok_campaign and isinstance(active_campaign, dict):
                self.current_campaign = active_campaign
                return active_campaign

            return {}

        except Exception as e:
            self.log.warning("[owner_review] error buscando campaña activa: %r", e)
            return {}

    def _extract_owner_url_from_campaign(self, campaign: dict) -> str:
        if not isinstance(campaign, dict):
            return ""

        return str(
            campaign.get("owner_instagram_profile_url")
            or campaign.get("owner_instagram_url")
            or campaign.get("instagram_profile_url")
            or campaign.get("profile_instagram_url")
            or campaign.get("owner_profile_url")
            or ""
        ).strip()

    def _extract_services_from_campaign(self, campaign: dict) -> list[str]:
        if not isinstance(campaign, dict):
            return []

        return self._normalize_services_list(
            campaign.get("services_snapshot")
            or campaign.get("services")
            or campaign.get("owner_services")
        )

    def _normalize_services_list(self, value) -> list[str]:
        if not value:
            return []

        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]

        if not isinstance(value, list):
            return []

        services = []

        for item in value:
            if isinstance(item, dict):
                name = str(
                    item.get("name")
                    or item.get("service_name")
                    or item.get("title")
                    or item.get("primary_keyword")
                    or ""
                ).strip()
            else:
                name = str(item or "").strip()

            if name:
                services.append(name)

        seen = set()
        unique_services = []

        for service in services:
            key = service.lower()

            if key in seen:
                continue

            seen.add(key)
            unique_services.append(service)

        return unique_services

    def _normalize_instagram_url(self, value: str, source: str = "") -> str:
        try:
            value = str(value or "").strip()

            if not value:
                return ""

            if value.startswith("@"):
                value = f"https://www.instagram.com/{value.lstrip('@').strip()}/"

            elif "instagram.com" not in value:
                value = value.strip().strip("/")
                value = f"https://www.instagram.com/{value}/"

            if "instagram.com" not in value:
                self.log.warning("URL de Instagram inválida desde %s: %s", source, value)
                return ""

            normalized = _normalize_instagram_href(value)

            self.log.info(
                "[owner_review] owner Instagram URL detectada desde %s: %s",
                source,
                normalized,
            )

            return normalized

        except Exception as e:
            self.log.warning("Error normalizando Instagram URL desde %s: %r", source, e)
            return ""

    def _extract_owner_username(self, owner_profile_url: str) -> str:
        try:
            return owner_profile_url.rstrip("/").split("/")[-1].strip()
        except Exception:
            return ""

    # =========================================================
    # DATA HELPERS
    # =========================================================

    def _get_custom_task(self) -> dict:
        value = self.data.get("custom_task") or {}
        return value if isinstance(value, dict) else {}

    def _get_social_media_account(self) -> dict:
        value = self.data.get("social_media_account") or {}
        return value if isinstance(value, dict) else {}

    def _get_owner_data(self) -> dict:
        social_media_account = self._get_social_media_account()
        value = social_media_account.get("owner") or {}
        return value if isinstance(value, dict) else {}

    def _get_campaign_from_payload(self) -> dict:
        candidates = [
            self.data.get("prospecting_campaign"),
            self.data.get("campaign"),
            self.data.get("active_campaign"),
            self.data.get("campaign_data"),
            (self.data.get("task") or {}).get("campaign")
            if isinstance(self.data.get("task"), dict)
            else None,
            (self.data.get("social_media_account") or {}).get("prospecting_campaign")
            if isinstance(self.data.get("social_media_account"), dict)
            else None,
            (self.data.get("social_media_account") or {}).get("campaign")
            if isinstance(self.data.get("social_media_account"), dict)
            else None,
        ]

        for candidate in candidates:
            if isinstance(candidate, dict) and candidate:
                return candidate

        return {}

    def _get_business_name(self) -> str:
        owner = self._get_owner_data()
        campaign = self._get_campaign_from_payload() or self._get_active_campaign_from_api()

        return str(
            owner.get("name")
            or owner.get("business_name")
            or campaign.get("business_name")
            or campaign.get("name")
            or self.data.get("business_name")
            or self.data.get("campaign_name")
            or ""
        ).strip()

    def _get_category(self) -> str:
        owner = self._get_owner_data()
        campaign = self._get_campaign_from_payload() or self._get_active_campaign_from_api()

        return str(
            self.data.get("category")
            or owner.get("category")
            or campaign.get("category")
            or campaign.get("industry")
            or ""
        ).strip()

    def _get_location(self) -> str:
        owner = self._get_owner_data()
        campaign = self._get_campaign_from_payload() or self._get_active_campaign_from_api()

        return str(
            self.data.get("location")
            or owner.get("location")
            or campaign.get("location")
            or campaign.get("city")
            or ""
        ).strip()

    def _get_campaign_name(self) -> str:
        campaign = self._get_campaign_from_payload() or self._get_active_campaign_from_api()

        return str(
            self.data.get("campaign_name")
            or campaign.get("name")
            or ""
        ).strip()

    def _get_bot_personality_id(self):
        social_media_account = self._get_social_media_account()

        bot_personality = social_media_account.get("bot_personality") or {}

        return (
            bot_personality.get("id")
            or social_media_account.get("bot_personality_id")
        )

    # =========================================================
    # ASSET GENERATION
    # =========================================================

    def _build_owner_review_extra_context(
        self,
        service_name: str,
        business_name: str,
        owner_username: str,
    ) -> str:
        return (
            f"Create exactly 1 Instagram post asset about only this service: {service_name}. "
            f"The business is {business_name} and the Instagram account to mention is @{owner_username}. "
            f"The image must be highly realistic and look like a real photograph, not an illustration, not a cartoon, "
            f"not CGI, not a poster, not a flyer, not a stock mockup, and not an overly polished artificial render. "
            f"It must visually match the actual service '{service_name}' in a believable real-world way. "
            f"If the service is cleaning, the space must look genuinely clean, organized, fresh, polished, and professionally maintained, "
            f"with realistic details that match cleaning work. "
            f"If the service is another type of business, the image must still reflect that exact service clearly and realistically, "
            f"using natural objects, environment, tools, and context related to the service. "
            f"The result must feel professional but authentic, with natural lighting, realistic textures, believable proportions, "
            f"real-world composition, and a service outcome that looks correct and visually convincing. "
            f"No text inside the image. No headline. No typography. No captions inside the image. "
            f"No stickers. No labels. No callouts. No watermark. "
            f"No split-screen. No collage. No infographic style. "
            f"Only one clear realistic scene related to the service. "
            f"The caption must feel like a real positive first-person recommendation for @{owner_username}. "
            f"It must talk only about the service '{service_name}', not about the whole business in general. "
            f"It should sound natural, warm, trustworthy, and human, like someone genuinely recommending that service "
            f"after having a good experience. "
            f"Make the caption medium-length: not too short and not too long. "
            f"It should mention specific positive impressions, why the service stood out, and why the person would recommend it, "
            f"without sounding robotic, generic, or overly detailed. "
            f"The caption may include a few natural emojis, but do not overuse them. "
            f"Use around 2 to 5 relevant emojis max, integrated naturally. "
            f"Do not add hashtags."
        )

    def _generate_owner_review_post_asset(self, owner_username: str) -> dict:
        social_media_account = self._get_social_media_account()
        social_media_account_id = social_media_account.get("id")
        bot_personality_id = self._get_bot_personality_id()

        if not bot_personality_id:
            self.log.warning("No se encontró bot_personality_id")
            return {}

        business_name = self._get_business_name()
        category = self._get_category()
        location = self._get_location()
        campaign_name = self._get_campaign_name()

        service_name = self._get_random_owner_service()

        if not service_name:
            self.log.warning("No se encontró ningún servicio desde campaña/owner.")
            return {}

        payload = {
            "bot_personality_id": bot_personality_id,
            "social_media_account_id": social_media_account_id,
            "username": owner_username,
            "campaign_name": campaign_name,
            "business_name": business_name,
            "category": category,
            "location": location,
            "extra_context": self._build_owner_review_extra_context(
                service_name=service_name,
                business_name=business_name,
                owner_username=owner_username,
            ),
            "account_kind": "business",
            "post_mode": None,
            "max_images": 1,
            "image_text_mode": "clean",
            "size_image": "1024x1024",
            "memory_asset_type": "owner_review_post",
        }

        ok_post, post_data = self.ai_api.generate_instagram_post_asset(**payload)

        if not ok_post:
            self.log.warning("No se pudo generar el post asset owner review: %s", post_data)
            return {}

        images = post_data.get("images") or []
        raw_caption = (post_data.get("caption_with_hashtags") or "").strip()
        caption_clean = self._remove_hashtags(raw_caption)

        valid_images = [
            img
            for img in images
            if img and os.path.exists(img)
        ]

        if not valid_images:
            self.log.warning("Las imágenes generadas no existen en disco: %s", images)
            return {}

        valid_images = valid_images[:1]
        owner_mention = f"@{owner_username}"

        if owner_mention.lower() not in caption_clean.lower():
            caption_clean = f"{caption_clean}\n\n{owner_mention}".strip()

        if not caption_clean:
            self.log.warning("El caption quedó vacío después de limpiar hashtags.")
            return {}

        self.log.info(
            "Owner review asset generado. service=%s | images=%s | caption_len=%s",
            service_name,
            len(valid_images),
            len(caption_clean),
        )

        return {
            "images": valid_images,
            "caption_with_hashtags": caption_clean,
            "headline": "",
            "service_name": service_name,
        }

    def _get_random_owner_service(self) -> str:
        services = self._get_owner_services()
        valid_services = [
            str(service).strip()
            for service in services
            if str(service).strip()
        ]

        if not valid_services:
            return ""

        return random.choice(valid_services)

    # =========================================================
    # POST UPLOAD FLOW
    # =========================================================

    def _open_post_composer(self) -> bool:
        try:
            driver = self.browser.driver

            icons = driver.find_elements(
                By.CSS_SELECTOR,
                ShareInstagramPostLocators.NEW_POST_ICON_CSS,
            )

            self.log.info("[post] íconos encontrados por CSS: %s", len(icons))

            if not icons:
                self.log.warning("[post] no se encontró el ícono de nueva publicación")
                return False

            icon = icons[0]
            clickable = None

            for rel_xpath in ShareInstagramPostLocators.NEW_POST_CLICKABLE_ANCESTOR_XPATHS:
                try:
                    candidate = icon.find_element(By.XPATH, rel_xpath)

                    if candidate:
                        clickable = candidate
                        self.log.info("[post] clickable encontrado con locator: %s", rel_xpath)
                        break

                except Exception:
                    continue

            if clickable is None:
                self.log.warning("[post] no se encontró contenedor clickable")
                return False

            for attempt in range(1, 5):
                self.log.info("[post] intento abrir composer %s/4", attempt)

                try:
                    ActionChains(driver).move_to_element(clickable).pause(0.6).perform()
                    self.log.info("[post] hover ok")
                except Exception as e:
                    self.log.info("[post] hover falló: %r", e)

                self.browser.time_sleep(0.8)

                try:
                    clickable.click()
                    self.log.info("[post] click normal ok")
                except Exception as e:
                    self.log.info("[post] click normal falló: %r", e)

                self.browser.time_sleep(1.2)

                if self._create_menu_opened():
                    self.log.info("[post] abrió menú de crear, intentando click en Publicación/Post...")

                    if self._click_post_option_if_present() and self._real_post_composer_opened():
                        self.log.info("[post] composer real abierto luego de elegir Publicación/Post")
                        return True

                if self._real_post_composer_opened():
                    self.log.info("[post] composer real abierto directo con click normal")
                    return True

                try:
                    ActionChains(driver).move_to_element(clickable).pause(0.3).click().perform()
                    self.log.info("[post] ActionChains click ok")
                except Exception as e:
                    self.log.info("[post] ActionChains click falló: %r", e)

                self.browser.time_sleep(1.2)

                if self._create_menu_opened():
                    self.log.info("[post] abrió menú de crear tras ActionChains, intentando click en Publicación/Post...")

                    if self._click_post_option_if_present() and self._real_post_composer_opened():
                        self.log.info("[post] composer real abierto luego de ActionChains + Publicación/Post")
                        return True

                if self._real_post_composer_opened():
                    self.log.info("[post] composer real abierto con ActionChains")
                    return True

                try:
                    clickable.send_keys(Keys.ENTER)
                    self.log.info("[post] ENTER ok")
                except Exception as e:
                    self.log.info("[post] ENTER falló: %r", e)

                self.browser.time_sleep(1.2)

                if self._create_menu_opened():
                    self.log.info("[post] abrió menú de crear tras ENTER, intentando click en Publicación/Post...")

                    if self._click_post_option_if_present() and self._real_post_composer_opened():
                        self.log.info("[post] composer real abierto luego de ENTER + Publicación/Post")
                        return True

                if self._real_post_composer_opened():
                    self.log.info("[post] composer real abierto con ENTER")
                    return True

                try:
                    clickable.send_keys(Keys.SPACE)
                    self.log.info("[post] SPACE ok")
                except Exception as e:
                    self.log.info("[post] SPACE falló: %r", e)

                self.browser.time_sleep(1.2)

                if self._create_menu_opened():
                    self.log.info("[post] abrió menú de crear tras SPACE, intentando click en Publicación/Post...")

                    if self._click_post_option_if_present() and self._real_post_composer_opened():
                        self.log.info("[post] composer real abierto luego de SPACE + Publicación/Post")
                        return True

                if self._real_post_composer_opened():
                    self.log.info("[post] composer real abierto con SPACE")
                    return True

            self.log.warning("[post] no se pudo abrir el composer")
            return False

        except Exception as e:
            self.log.warning("[post] error abriendo composer: %r", e)
            return False

    def _create_menu_opened(self) -> bool:
        try:
            for xpath in ShareInstagramPostLocators.CREATE_MENU_OPENED_XPATHS:
                if self._get_visible_elements(xpath):
                    self.log.info("[post] menú de crear detectado con locator: %s", xpath)
                    return True

            return False

        except Exception:
            return False

    def _real_post_composer_opened(self) -> bool:
        try:
            for xpath in ShareInstagramPostLocators.POST_COMPOSER_READY_XPATHS:
                visibles = self._get_visible_elements(xpath)

                if visibles:
                    self.log.info(
                        "[post] composer real detectado con locator: %s | visibles=%s",
                        xpath,
                        len(visibles),
                    )
                    return True

            self.log.info("[post] composer real no detectado")
            return False

        except Exception:
            return False

    def _click_post_option_if_present(self) -> bool:
        try:
            driver = self.browser.driver

            for xpath in ShareInstagramPostLocators.POST_OPTION_XPATHS:
                elems = self._get_visible_elements(xpath)

                self.log.info(
                    "[post] candidatos Publicación/Post: %s | locator=%s",
                    len(elems),
                    xpath,
                )

                for el in elems:
                    try:
                        txt = (el.text or "").strip()
                        href = (el.get_attribute("href") or "").strip()

                        self.log.info(
                            "[post] opción publicación visible | texto='%s' | href='%s'",
                            txt,
                            href,
                        )

                        self._scroll_into_view(el)
                        self.browser.time_sleep(0.5)

                        try:
                            el.click()
                            self.log.info("[post] click normal en Publicación/Post ok")
                            self.browser.time_sleep(1.5)
                            return True
                        except Exception as e:
                            self.log.info("[post] click normal en Publicación/Post falló: %r", e)

                        try:
                            ActionChains(driver).move_to_element(el).pause(0.2).click().perform()
                            self.log.info("[post] ActionChains click en Publicación/Post ok")
                            self.browser.time_sleep(1.5)
                            return True
                        except Exception as e:
                            self.log.info("[post] ActionChains click en Publicación/Post falló: %r", e)

                        try:
                            driver.execute_script(
                                ShareInstagramPostLocators.CLICK_ELEMENT_SCRIPT,
                                el,
                            )
                            self.log.info("[post] JS click en Publicación/Post ok")
                            self.browser.time_sleep(1.5)
                            return True
                        except Exception as e:
                            self.log.info("[post] JS click en Publicación/Post falló: %r", e)

                    except Exception:
                        continue

            self.log.info("[post] no apareció opción explícita de Publicación/Post")
            return False

        except Exception as e:
            self.log.warning("[post] error clickeando opción Publicación/Post: %r", e)
            return False

    def _upload_post_media(self, media_paths: list[str]) -> bool:
        try:
            if not media_paths:
                self.log.warning("No se recibieron imágenes para owner review.")
                return False

            valid_paths = [
                os.path.abspath(path)
                for path in media_paths
                if path and os.path.exists(path)
            ]

            if not valid_paths:
                self.log.warning("Ninguna imagen existe en disco para owner review.")
                return False

            if not self.browser.is_visible(ShareInstagramPostLocators.POST_COMPOSER_READY):
                self.log.warning("El composer de subida no está visible en owner review.")
                return False

            self.browser.time_sleep(1)

            url_before = self.browser.driver.current_url
            self.log.info("[owner_review] URL antes de upload: %s", url_before)

            active_dialog = self._find_active_dialog()

            if active_dialog is None:
                self.log.warning("No se encontró ningún dialog visible.")
                return False

            has_expected_ui = active_dialog.find_elements(
                By.XPATH,
                ShareInstagramPostLocators.ACTIVE_DIALOG_EXPECTED_UPLOAD_UI_REL_XPATH,
            )

            if not has_expected_ui:
                self.log.warning("El dialog visible no parece ser el composer de subida.")
                return False

            dialog_inputs = active_dialog.find_elements(
                By.XPATH,
                ShareInstagramPostLocators.ACTIVE_DIALOG_FILE_INPUTS_REL_XPATH,
            )

            if not dialog_inputs:
                self.log.warning("No se encontró input[type='file'] dentro del dialog activo.")
                return False

            candidate_inputs = []

            for inp in dialog_inputs:
                try:
                    accept = (inp.get_attribute("accept") or "").lower()
                    multiple = inp.get_attribute("multiple")

                    if "image" in accept or "video" in accept or multiple is not None:
                        candidate_inputs.append(inp)

                except Exception:
                    continue

            file_input = (candidate_inputs or dialog_inputs)[-1]

            try:
                self.browser.driver.execute_script(
                    ShareInstagramPostLocators.MAKE_FILE_INPUT_VISIBLE_SCRIPT,
                    file_input,
                )
            except Exception:
                pass

            self.log.info(
                "[owner_review] Enviando %s archivo(s) al input del dialog activo.",
                len(valid_paths),
            )

            file_input.send_keys("\n".join(valid_paths))
            self.browser.time_sleep(4)

            url_after = self.browser.driver.current_url
            self.log.info("[owner_review] URL después de upload: %s", url_after)

            if url_after != url_before:
                self.log.warning(
                    "[owner_review] La URL cambió tras send_keys. "
                    "Eso indica que Instagram disparó otro flujo y no el composer correcto."
                )

            for _ in range(20):
                try:
                    next_buttons = active_dialog.find_elements(
                        By.XPATH,
                        ShareInstagramPostLocators.ACTIVE_DIALOG_NEXT_BUTTONS_REL_XPATH,
                    )

                    visible_next = [
                        btn
                        for btn in next_buttons
                        if btn.is_displayed() and btn.is_enabled()
                    ]

                    if visible_next:
                        self.log.info("Medio subido correctamente en owner review, apareció Next.")
                        return True

                except Exception:
                    pass

                self.browser.time_sleep(1)

            self.log.warning("Se enviaron los archivos pero no apareció Next dentro del dialog activo.")
            return False

        except Exception as e:
            self.log.warning("Error subiendo medios owner review: %r", e)
            return False

    def _click_next_button(self, label="Siguiente") -> bool:
        try:
            for _ in range(5):
                self.browser.time_sleep(1)

                if self.browser.is_visible(ShareInstagramPostLocators.NEXT_BUTTON):
                    self.browser.click(
                        ShareInstagramPostLocators.NEXT_BUTTON,
                        timeX=10,
                        scroll=False,
                        error=False,
                        hover=False,
                    )

                    self.browser.time_sleep(3)
                    self.log.info("Click en %s ejecutado.", label)
                    return True

            return False

        except Exception as e:
            self.log.warning("Error dando click en %s: %r", label, e)
            return False

    def _write_caption(self, caption: str) -> bool:
        try:
            caption = (caption or "").strip()

            if not caption:
                self.log.warning("El caption está vacío.")
                return False

            editor = self._find_visible_caption_editor(
                ShareInstagramPostLocators.CAPTION_INPUT
            )

            if editor is None:
                self.log.warning("No se encontró ningún editor visible para caption.")
                return False

            self._scroll_into_view(editor)
            self.browser.time_sleep(1)

            if not self._safe_click(editor, pause_before=0, pause_after=0):
                self.log.warning("No se pudo enfocar el editor del caption owner review.")
                return False

            self.browser.time_sleep(1)
            self._clear_input_like_human(editor)

            ok = self._type_text_like_human(
                element=editor,
                text=caption,
                multiline=True,
                sanitize_non_bmp=True,
            )

            if not ok:
                return False

            self.browser.time_sleep(1)
            self.log.info("Caption owner review escrito correctamente.")
            return True

        except Exception as e:
            self.log.warning("Error escribiendo caption owner review: %r", e)
            return False

    def _click_share_button(self) -> bool:
        try:
            for _ in range(5):
                self.browser.time_sleep(1)

                buttons = self.browser.driver.find_elements(
                    By.XPATH,
                    ShareInstagramPostLocators.SHARE_BUTTON_ALL,
                )

                visible_buttons = []

                for btn in buttons:
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            txt = (btn.text or "").strip()

                            if txt in {"Compartir", "Share", "Publicar", "Post"}:
                                visible_buttons.append(btn)

                    except Exception:
                        continue

                if not visible_buttons:
                    continue

                button = visible_buttons[-1]

                try:
                    ActionChains(self.browser.driver).move_to_element(button).pause(0.3).click().perform()
                    self.browser.time_sleep(4)
                    return True
                except Exception:
                    pass

                try:
                    button.click()
                    self.browser.time_sleep(4)
                    return True
                except Exception:
                    pass

                try:
                    button.send_keys(Keys.ENTER)
                    self.browser.time_sleep(4)
                    return True
                except Exception:
                    pass

            return False

        except Exception as e:
            self.log.warning("Error dando click en Compartir owner review: %r", e)
            return False

    def _tag_owner_on_post(self, owner_username: str) -> bool:
        try:
            owner_username = (owner_username or "").strip().lstrip("@")

            if not owner_username:
                self.log.warning("owner_username vacío para etiquetar.")
                return False

            click_surfaces = []

            for _ in range(10):
                click_surfaces = self._get_visible_elements(
                    ShareInstagramPostLocators.TAG_PEOPLE_CLICK_SURFACE
                )

                if click_surfaces:
                    break

                self.browser.time_sleep(1)

            if not click_surfaces:
                self.log.warning("No se encontró la superficie clickeable del modal para etiquetar.")
                return False

            surface = click_surfaces[-1]
            self._scroll_into_view(surface)
            self.browser.time_sleep(1)

            clicked = False

            try:
                self.browser.driver.execute_script(
                    ShareInstagramPostLocators.CLICK_TAG_SURFACE_SCRIPT,
                    surface,
                    0.40,
                    0.35,
                )
                clicked = True
            except Exception:
                pass

            if not clicked:
                try:
                    ActionChains(self.browser.driver).move_to_element_with_offset(surface, 40, 40).click().perform()
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                clicked = self._safe_click(surface, pause_before=0.8, pause_after=0)

            if not clicked:
                self.log.warning("No se pudo clickear la superficie del modal para etiquetar.")
                return False

            self.browser.time_sleep(2)

            search_inputs = []

            for _ in range(10):
                search_inputs = self._get_visible_elements(
                    ShareInstagramPostLocators.USER_SEARCH_INPUT
                )

                if search_inputs:
                    break

                self.browser.time_sleep(1)

            if not search_inputs:
                self.log.warning("No apareció el input de búsqueda para etiquetar.")
                return False

            search_input = search_inputs[-1]
            self._safe_click(search_input, pause_before=0, pause_after=0)
            self.browser.time_sleep(0.8)
            self._clear_input_like_human(search_input)

            for ch in owner_username:
                search_input.send_keys(ch)
                time.sleep(random.uniform(0.03, 0.08))

            self.browser.time_sleep(2)

            result_xpath = ShareInstagramPostLocators.TAG_SEARCH_RESULT_BY_USERNAME_TEMPLATE.format(
                username=owner_username
            )

            selected = False

            for _ in range(10):
                results = self._get_visible_elements(result_xpath)

                if results and self._safe_click(results[-1], pause_before=0.8, pause_after=0):
                    selected = True
                    break

                self.browser.time_sleep(1)

            if not selected:
                self.log.warning("No se encontró resultado para etiquetar a @%s", owner_username)
                return False

            self.browser.time_sleep(1.5)

            done_buttons = self._get_visible_elements(
                ShareInstagramPostLocators.TAG_PEOPLE_DONE_BUTTON
            )

            if done_buttons:
                self._safe_click(done_buttons[-1], pause_before=0.8, pause_after=1.5)

            self.log.info("Owner etiquetado correctamente: @%s", owner_username)
            return True

        except Exception as e:
            self.log.warning("Error etiquetando owner en el post: %r", e)
            return False

    def _generate_owner_review_post_asset_2(self, owner_username: str) -> dict:
        try:
            test_image_path = ShareInstagramPostLocators.OWNER_REVIEW_TEST_IMAGE_PATH

            test_caption = (
                f"Probando publicación de reseña para @{owner_username}. "
                f"Este caption es solo de prueba para validar que el flujo de subida, "
                f"caption, etiquetado y publicación funcione correctamente.\n\n"
                f"@{owner_username}"
            )

            if not os.path.exists(test_image_path):
                self.log.warning("La imagen de prueba no existe: %s", test_image_path)
                return {}

            self.log.info(
                "Usando asset de prueba local. image=%s | caption_len=%s",
                test_image_path,
                len(test_caption),
            )

            return {
                "images": [test_image_path],
                "caption_with_hashtags": test_caption,
                "headline": "",
                "service_name": "test",
            }

        except Exception as e:
            self.log.warning("Error preparando asset local de prueba: %r", e)
            return {}

    def _save_owner_review_memory(self) -> None:
        try:
            social_media_account_id = self._get_social_media_account().get("id")
            caption_text = self.post_data.get("caption_with_hashtags", "")
            overlay_phrase = self.post_data.get("headline", "")

            ok_memory, memory_response = self.ai_api.save_content_memory(
                social_media_account_id=social_media_account_id,
                asset_type="owner_review_post",
                caption_text=caption_text,
                overlay_phrase=overlay_phrase,
            )

            if not ok_memory:
                self.log.warning(
                    "No se pudo guardar content memory del owner review post: %s",
                    memory_response,
                )

        except Exception as e:
            self.log.warning("Error guardando memoria owner review: %r", e)

    def _remove_hashtags(self, text: str) -> str:
        try:
            text = (text or "").strip()

            if not text:
                return ""

            cleaned_lines = []

            for line in text.splitlines():
                stripped = line.strip()

                if stripped and all(token.startswith("#") for token in stripped.split()):
                    continue

                cleaned_lines.append(line)

            cleaned = "\n".join(cleaned_lines).strip()
            cleaned = re.sub(r"(?<!\w)#[\w_]+", "", cleaned)
            cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

            return cleaned.strip()

        except Exception:
            return (text or "").strip()

    def _shorten_for_log(self, value, max_len: int = 1200):
        try:
            import json

            text = value

            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False, default=str)

            text = text.replace("\\n", " ").replace("\n", " ").strip()

            if len(text) > max_len:
                return text[:max_len] + "...[truncated]"

            return text

        except Exception:
            return str(value)