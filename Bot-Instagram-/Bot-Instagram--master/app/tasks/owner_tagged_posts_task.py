import random
from typing import Dict, List, Optional, TypedDict

from app.core.interfaces import IBrowser, ITask
from app.utils.logger import get_logger
from app.utils.instagram_url import _normalize_instagram_href
from app.config.locators.instagram_profile_locators import InstagramProfileLocators
from app.config.locators.instagram_common_locator import InstagramCommonLocators
from app.services.instagram_profile_service import InstagramProfileService
from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.api.prospecting_api import ProspectingAPI
from app.tasks.share_owner_review_post_task import ShareOwnerReviewPostTask


class LiveProcessResult(TypedDict):
    ok: bool
    message: str
    posts_detectados: int
    posts_objetivo: int
    visited: int
    attempted: int
    liked: int
    already_liked: int
    failed: int
    skipped_no_like: int
    likes_planeados: int


class OwnerTaggedPostsTask(ITask):
    """
    Flujo:
    1. Resolver campaña/owner.
    2. Obtener owner_instagram_profile_url.
    3. Obtener servicios desde campaña activa o owner.services.
    4. Seguir owner si aplica.
    5. Procesar posts normales del owner.
    6. Procesar posts etiquetados.
    7. Ejecutar ShareOwnerReviewPostTask con el mismo owner + servicios resueltos.
    """

    PROFILE_SCROLL_NO_GROWTH = 4
    PROFILE_HARD_SCROLL_LIMIT = 120
    PROFILE_MIN_POSTS_TO_COLLECT = 30
    PROFILE_STOP_WHEN_REACHING = 20

    POSTS_MIN = 6
    POSTS_MAX = 8

    PROFILE_WAIT_MIN = 3
    PROFILE_WAIT_MAX = 5

    POST_WAIT_MIN = 3
    POST_WAIT_MAX = 5

    SHORT_WAIT_MIN = 1
    SHORT_WAIT_MAX = 2

    def __init__(self, browser: IBrowser, data: dict, account_api=None, ai_api=None):
        self.browser = browser
        self.data = data or {}
        self.account_api = account_api
        self.ai_api = ai_api
        self.log = get_logger(self.__class__.__name__)

        self.prospecting_api = ProspectingAPI()
        self.current_campaign: dict | None = None

        self.profile_service = InstagramProfileService(
            browser=self.browser,
            logger=self.log,
        )

        self.post_interaction_service = InstagramPostInteractionService(
            browser=self.browser,
            logger=self.log,
        )

    def execute(self) -> str:
        try:
            owner_profile_url = self._get_owner_instagram_url()
            if not owner_profile_url:
                return "✗ No se encontró la URL de Instagram del owner/campaña"

            owner_services = self._get_owner_services()
            self.log.info(
                "[owner-tagged] owner_url=%s | services=%s",
                owner_profile_url,
                owner_services,
            )

            follow_status = self.profile_service.ensure_follow_profile(owner_profile_url)

            if follow_status == "error":
                return f"✗ No se pudo validar/seguir el perfil owner | {owner_profile_url}"

            if follow_status == "already_following":
                self.log.info("Ya se seguía el perfil owner: %s", owner_profile_url)
            else:
                self.log.info("Perfil owner seguido correctamente: %s", owner_profile_url)

            # =====================================================
            # 1) POSTS NORMALES DEL OWNER
            # =====================================================
            self.profile_service.open_url(owner_profile_url)
            self._sleep_profile()

            profile_result = self._process_random_posts_live(mode="profile")

            if not profile_result["ok"]:
                self.log.warning(
                    "No se pudieron procesar publicaciones normales del owner: %s",
                    profile_result["message"],
                )
            else:
                self.log.info(
                    "Publicaciones normales del owner procesadas correctamente: %s",
                    profile_result,
                )

            # =====================================================
            # 2) POSTS ETIQUETADOS DEL OWNER
            # =====================================================
            self.profile_service.open_url(owner_profile_url)
            self._sleep_profile()

            tagged_ok = self._open_tagged_tab()

            if not tagged_ok:
                self.log.warning(
                    "No se pudo abrir la pestaña de etiquetadas | %s",
                    owner_profile_url,
                )
                tagged_result = self._empty_result("No se pudo abrir la pestaña de etiquetadas")
            else:
                tagged_result = self._process_random_posts_live(mode="tagged")

                if not tagged_result["ok"]:
                    self.log.warning(
                        "No se pudieron procesar publicaciones etiquetadas del owner: %s",
                        tagged_result["message"],
                    )
                else:
                    self.log.info(
                        "Publicaciones etiquetadas del owner procesadas correctamente: %s",
                        tagged_result,
                    )

            if not profile_result["ok"] and not tagged_result["ok"]:
                return (
                    f"✗ No se pudieron procesar publicaciones normales ni etiquetadas | "
                    f"{owner_profile_url} | "
                    f"profile={profile_result['message']} | "
                    f"tagged={tagged_result['message']}"
                )

            # =====================================================
            # 3) OWNER REVIEW POST
            # =====================================================
            owner_review_post_ok = self._execute_owner_review_post(
                owner_profile_url=owner_profile_url,
                owner_services=owner_services,
            )

            return self._build_integrated_success_message(
                owner_profile_url=owner_profile_url,
                profile_result=profile_result,
                tagged_result=tagged_result,
                owner_review_post_ok=owner_review_post_ok,
            )

        except Exception as e:
            self.log.error("Error en OwnerTaggedPostsTask: %r", e)
            return f"✗ Error en OwnerTaggedPostsTask: {repr(e)}"

    # =========================================================
    # OWNER REVIEW POST
    # =========================================================

    def _execute_owner_review_post(
        self,
        *,
        owner_profile_url: str,
        owner_services: list[str],
    ) -> bool:
        try:
            review_data = self._build_review_data_payload(
                owner_profile_url=owner_profile_url,
                owner_services=owner_services,
            )

            task = ShareOwnerReviewPostTask(
                browser=self.browser,
                ai_api=self.ai_api,
                account_api=self.account_api,
                data=review_data,
            )

            raw_result = task.execute()
            ok = bool(raw_result) and not str(raw_result).strip().startswith("✗")

            if ok:
                self.log.info("Post de reseña del owner publicado correctamente: %s", raw_result)
            else:
                self.log.warning("No se pudo publicar el post de reseña del owner: %s", raw_result)

            return ok

        except Exception as e:
            self.log.warning("Error ejecutando ShareOwnerReviewPostTask: %r", e)
            return False

    def _build_review_data_payload(
        self,
        *,
        owner_profile_url: str,
        owner_services: list[str],
    ) -> dict:
        payload = dict(self.data or {})

        social_media_account = dict(payload.get("social_media_account") or {})
        owner = dict(social_media_account.get("owner") or {})

        owner["owner_urls"] = owner_profile_url
        owner["owner_instagram_profile_url"] = owner_profile_url

        if owner_services:
            owner["services"] = owner_services

        social_media_account["owner"] = owner
        payload["social_media_account"] = social_media_account

        payload["owner_instagram_profile_url"] = owner_profile_url
        payload["owner_services"] = owner_services
        payload["services_snapshot"] = owner_services

        if self.current_campaign:
            payload["active_campaign"] = self.current_campaign
            payload["prospecting_campaign"] = self.current_campaign
            payload["campaign_name"] = self.current_campaign.get("name") or payload.get("campaign_name") or ""

        return payload

    def _build_integrated_success_message(
        self,
        owner_profile_url: str,
        profile_result: LiveProcessResult,
        tagged_result: LiveProcessResult,
        owner_review_post_ok: bool,
    ) -> str:
        return (
            f"✓ Owner procesado | {owner_profile_url} | "
            f"profile_ok={profile_result['ok']} | "
            f"profile_posts_detectados={profile_result['posts_detectados']} | "
            f"profile_posts_objetivo={profile_result['posts_objetivo']} | "
            f"profile_posts_visitados={profile_result['visited']} | "
            f"profile_likes_ok={profile_result['liked']} | "
            f"profile_likes_ya_existian={profile_result['already_liked']} | "
            f"profile_likes_fallidos={profile_result['failed']} | "
            f"tagged_ok={tagged_result['ok']} | "
            f"tagged_posts_detectados={tagged_result['posts_detectados']} | "
            f"tagged_posts_objetivo={tagged_result['posts_objetivo']} | "
            f"tagged_posts_visitados={tagged_result['visited']} | "
            f"tagged_likes_ok={tagged_result['liked']} | "
            f"tagged_likes_ya_existian={tagged_result['already_liked']} | "
            f"tagged_likes_fallidos={tagged_result['failed']} | "
            f"owner_review_post={'ok' if owner_review_post_ok else 'failed'}"
        )

    # =========================================================
    # SLEEPS
    # =========================================================

    def _sleep_profile(self) -> None:
        self.browser.time_sleep(random.randint(self.PROFILE_WAIT_MIN, self.PROFILE_WAIT_MAX))

    def _sleep_post(self) -> None:
        self.browser.time_sleep(random.randint(self.POST_WAIT_MIN, self.POST_WAIT_MAX))

    def _sleep_short(self) -> None:
        self.browser.time_sleep(random.randint(self.SHORT_WAIT_MIN, self.SHORT_WAIT_MAX))

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
                return self._normalize_instagram_url(direct_url, source="custom_task_or_data")

            campaign = self._get_campaign_from_payload()
            url_from_payload = self._extract_owner_url_from_campaign(campaign)

            if url_from_payload:
                self.current_campaign = campaign
                return self._normalize_instagram_url(url_from_payload, source="payload_campaign")

            active_campaign = self._get_active_campaign_from_api()
            url_from_api = self._extract_owner_url_from_campaign(active_campaign)

            if url_from_api:
                self.current_campaign = active_campaign
                return self._normalize_instagram_url(url_from_api, source="active_campaign")

            owner = self._get_owner_data()
            owner_url = str(
                owner.get("owner_instagram_profile_url")
                or owner.get("owner_instagram_url")
                or owner.get("instagram_profile_url")
                or owner.get("owner_urls")
                or ""
            ).strip()

            if owner_url:
                return self._normalize_instagram_url(owner_url, source="social_media_account.owner")

            self.log.warning("No se encontró URL de Instagram del owner en payload ni campaña activa.")
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
            self.log.warning("Error obteniendo servicios del owner/campaña: %r", e)
            return []

    def _get_active_campaign_from_api(self) -> dict:
        if isinstance(self.current_campaign, dict) and self.current_campaign:
            return self.current_campaign

        try:
            social_media_account = self._get_social_media_account()
            account_id = social_media_account.get("id")

            if not account_id:
                self.log.warning("[owner-tagged] no hay social_media_account.id para campaña activa.")
                return {}

            ok_campaign, active_campaign = self.prospecting_api.get_active_campaign(
                social_media_account_id=account_id,
                platform="instagram",
            )

            self.log.info(
                "[owner-tagged] active campaign lookup | ok=%s | campaign=%s",
                ok_campaign,
                active_campaign,
            )

            if ok_campaign and isinstance(active_campaign, dict):
                self.current_campaign = active_campaign
                return active_campaign

            return {}

        except Exception as e:
            self.log.warning("[owner-tagged] error buscando campaña activa: %r", e)
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

        services: list[str] = []

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
                "Owner Instagram URL detectada desde %s: %s",
                source,
                normalized,
            )

            return normalized

        except Exception as e:
            self.log.warning("Error normalizando Instagram URL desde %s: %r", source, e)
            return ""

    # =========================================================
    # PROCESS POSTS
    # =========================================================

    def _process_random_posts_live(self, mode: str = "profile") -> LiveProcessResult:
        if mode == "tagged":
            grid_xpath = InstagramCommonLocators.PROFILE_TAGGED_POST_LINKS
            source_label = "etiquetadas"
            min_posts_to_collect = 8
            stop_when_reaching = 12
            max_scrolls_without_growth = 4
        else:
            grid_xpath = getattr(
                InstagramProfileLocators,
                "PROFILE_POST_LINKS_VIDEOS",
                InstagramProfileLocators.PROFILE_POST_LINKS,
            )
            source_label = "perfil"
            min_posts_to_collect = self.PROFILE_MIN_POSTS_TO_COLLECT
            stop_when_reaching = max(
                self.PROFILE_MIN_POSTS_TO_COLLECT,
                self.PROFILE_STOP_WHEN_REACHING,
            )
            max_scrolls_without_growth = self.PROFILE_SCROLL_NO_GROWTH

        urls = self._get_grid_post_urls(
            grid_xpath=grid_xpath,
            source_label=source_label,
            max_scrolls_without_growth=max_scrolls_without_growth,
            hard_scroll_limit=self.PROFILE_HARD_SCROLL_LIMIT,
            min_posts_to_collect=min_posts_to_collect,
            stop_when_reaching=stop_when_reaching,
        )

        if not urls:
            return self._empty_result(f"No se encontraron publicaciones válidas en {source_label}")

        random.shuffle(urls)
        urls = urls[: self.PROFILE_STOP_WHEN_REACHING]

        posts_objetivo = min(len(urls), random.randint(self.POSTS_MIN, self.POSTS_MAX))
        likes_planeados = self._plan_like_count(posts_objetivo)

        self.log.info(
            "Modo live %s | urls_detectadas=%s | urls_muestra=%s | posts_objetivo=%s | likes_planeados=%s",
            source_label,
            len(urls),
            len(urls),
            posts_objetivo,
            likes_planeados,
        )

        result = self._new_live_result(
            posts_detectados=len(urls),
            posts_objetivo=posts_objetivo,
            likes_planeados=likes_planeados,
        )

        selected_count = 0
        likes_marcados = 0
        used_dates: set[str] = set()

        for index, post_url in enumerate(urls, start=1):
            if selected_count >= posts_objetivo:
                break

            try:
                self.log.info(
                    "Revisando post live %s %s/%s: %s",
                    source_label,
                    index,
                    len(urls),
                    post_url,
                )

                self.profile_service.open_url(post_url)
                self._sleep_post()

                date_info = self._get_current_post_date_info()
                date_key = date_info.get("date_key")
                date_label = date_info.get("date_label")

                if self._should_skip_repeated_date(
                    date_key=date_key,
                    used_dates=used_dates,
                    current_index=index,
                    total_urls=len(urls),
                    selected_count=selected_count,
                    posts_objetivo=posts_objetivo,
                ):
                    self.log.info(
                        "Saltando post %s por fecha repetida | date=%s | url=%s",
                        source_label,
                        date_label,
                        post_url,
                    )
                    continue

                if date_key:
                    used_dates.add(date_key)

                selected_count += 1
                result["visited"] += 1

                should_like = self._should_like_current_post(
                    selected_count=selected_count,
                    posts_objetivo=posts_objetivo,
                    likes_marcados=likes_marcados,
                    likes_planeados=likes_planeados,
                )

                if should_like:
                    likes_marcados += 1

                self.log.info(
                    "Post %s aceptado %s/%s | date=%s | should_like=%s | url=%s",
                    source_label,
                    selected_count,
                    posts_objetivo,
                    date_label,
                    should_like,
                    post_url,
                )

                if not should_like:
                    result["skipped_no_like"] += 1
                    self._sleep_short()
                    continue

                self._apply_like(post_url, result)

            except Exception as e:
                result["failed"] += 1
                self.log.warning("Error procesando post %s %s: %r", source_label, post_url, e)

        if result["visited"] == 0:
            return self._empty_result(f"No se pudieron procesar publicaciones en {source_label}")

        return result

    def _new_live_result(
        self,
        *,
        posts_detectados: int,
        posts_objetivo: int,
        likes_planeados: int,
    ) -> LiveProcessResult:
        return {
            "ok": True,
            "message": "OK",
            "posts_detectados": posts_detectados,
            "posts_objetivo": posts_objetivo,
            "visited": 0,
            "attempted": 0,
            "liked": 0,
            "already_liked": 0,
            "failed": 0,
            "skipped_no_like": 0,
            "likes_planeados": likes_planeados,
        }

    def _empty_result(self, message: str) -> LiveProcessResult:
        return {
            "ok": False,
            "message": message,
            "posts_detectados": 0,
            "posts_objetivo": 0,
            "visited": 0,
            "attempted": 0,
            "liked": 0,
            "already_liked": 0,
            "failed": 0,
            "skipped_no_like": 0,
            "likes_planeados": 0,
        }

    def _plan_like_count(self, posts_objetivo: int) -> int:
        if posts_objetivo <= 1:
            return 1

        min_likes = max(1, (posts_objetivo + 1) // 2)
        max_likes = max(1, posts_objetivo - 1)
        return random.randint(min_likes, max_likes)

    def _should_skip_repeated_date(
        self,
        *,
        date_key: Optional[str],
        used_dates: set[str],
        current_index: int,
        total_urls: int,
        selected_count: int,
        posts_objetivo: int,
    ) -> bool:
        remaining_urls = total_urls - current_index
        remaining_slots = posts_objetivo - selected_count

        return bool(
            date_key
            and date_key in used_dates
            and remaining_urls > remaining_slots
            and random.random() < 0.70
        )

    def _should_like_current_post(
        self,
        *,
        selected_count: int,
        posts_objetivo: int,
        likes_marcados: int,
        likes_planeados: int,
    ) -> bool:
        slots_restantes = posts_objetivo - selected_count
        likes_restantes = likes_planeados - likes_marcados

        if likes_restantes <= 0:
            return False

        if slots_restantes < likes_restantes:
            return True

        prob_like = likes_restantes / (slots_restantes + 1)
        prob_like = max(0.35, min(0.85, prob_like))
        return random.random() < prob_like

    def _apply_like(self, post_url: str, result: LiveProcessResult) -> None:
        result["attempted"] += 1

        like_state = self.post_interaction_service.has_post_like()

        if like_state is True:
            result["already_liked"] += 1
            self.log.info("El post ya tenía like: %s", post_url)
            return

        if like_state is False:
            ok_like = self.post_interaction_service.like_current_post()

            if ok_like:
                result["liked"] += 1
                self.log.info("Like OK en post owner: %s", post_url)
            else:
                fallback_ok = self._try_fallback_like_click(post_url)

                if fallback_ok:
                    result["liked"] += 1
                else:
                    result["failed"] += 1
                    self.log.warning("Like fallido en post owner: %s", post_url)

            self._sleep_short()
            return

        self.log.warning("No se pudo determinar el like state: %s", post_url)

        fallback_ok = self._try_fallback_like_click(post_url)

        if fallback_ok:
            result["liked"] += 1
        else:
            result["failed"] += 1
            self.log.warning("Fallback like también falló: %s", post_url)

        self._sleep_short()

    # =========================================================
    # GRID / SCROLL
    # =========================================================

    def _get_grid_post_urls(
        self,
        grid_xpath: str,
        source_label: str,
        max_scrolls_without_growth: int,
        hard_scroll_limit: int,
        min_posts_to_collect: int,
        stop_when_reaching: int,
    ) -> List[str]:
        urls: List[str] = []
        seen_urls = set()

        scroll_attempts_without_growth = 0
        last_count = -1
        total_scrolls = 0

        while total_scrolls < hard_scroll_limit:
            total_scrolls += 1

            try:
                elements = self.browser.obtener_elementos(
                    grid_xpath,
                    time_x=8,
                )
            except Exception as e:
                self.log.warning(
                    "Timeout/error leyendo posts de %s: %r",
                    source_label,
                    e,
                )
                elements = []

            for element in elements:
                try:
                    href = (element.get_attribute("href") or "").strip()

                    if not href:
                        continue

                    href = _normalize_instagram_href(href)

                    if not self.profile_service.is_post_url(href):
                        continue

                    if href in seen_urls:
                        continue

                    seen_urls.add(href)
                    urls.append(href)

                except Exception as e:
                    self.log.warning(
                        "Error leyendo URL del post de %s: %r",
                        source_label,
                        e,
                    )
                    continue

            current_count = len(urls)

            if current_count == last_count:
                scroll_attempts_without_growth += 1
            else:
                scroll_attempts_without_growth = 0
                last_count = current_count

            self.log.info(
                "Posts %s recolectados hasta ahora: %s | scroll=%s/%s | no_growth=%s",
                source_label,
                current_count,
                total_scrolls,
                hard_scroll_limit,
                scroll_attempts_without_growth,
            )

            if current_count >= stop_when_reaching:
                self.log.info(
                    "Se detiene scroll de %s porque ya se alcanzó el objetivo de recolección: %s",
                    source_label,
                    stop_when_reaching,
                )
                break

            if scroll_attempts_without_growth >= max_scrolls_without_growth and current_count > 0:
                self.log.info(
                    "Se detiene scroll de %s por no_growth=%s con current_count=%s",
                    source_label,
                    scroll_attempts_without_growth,
                    current_count,
                )
                break

            if current_count < min_posts_to_collect:
                self.log.info(
                    "Posts %s por debajo del mínimo sugerido | encontrados=%s | minimo=%s",
                    source_label,
                    current_count,
                    min_posts_to_collect,
                )

            if not self._scroll_profile_once():
                self.log.warning("No se pudo aplicar ningún método de scroll en %s.", source_label)
                break

            self.browser.time_sleep(random.randint(2, 4))

        return urls

    def _scroll_profile_once(self) -> bool:
        try:
            self.browser.driver.execute_script(
                InstagramProfileLocators.SCROLL_PROFILE_GRID_SCRIPT
            )
            self.log.info("Scroll aplicado con InstagramProfileLocators.SCROLL_PROFILE_GRID_SCRIPT")
            return True
        except Exception as e:
            self.log.warning("Falló SCROLL_PROFILE_GRID_SCRIPT: %r", e)

        try:
            self.browser.driver.execute_script(
                InstagramProfileLocators.SCROLL_TO_BOTTOM_SCRIPT
            )
            self.log.info("Scroll aplicado con InstagramProfileLocators.SCROLL_TO_BOTTOM_SCRIPT")
            return True
        except Exception as e:
            self.log.warning("Falló SCROLL_TO_BOTTOM_SCRIPT: %r", e)

        return False

    # =========================================================
    # POST HELPERS
    # =========================================================

    def _get_current_post_date_info(self) -> Dict[str, Optional[str]]:
        for xpath in InstagramCommonLocators.DATE_XPATHS:
            try:
                elements = self.browser.obtener_elementos(xpath, time_x=5)
            except Exception:
                elements = []

            for element in elements:
                try:
                    raw_dt = (element.get_attribute("datetime") or "").strip()

                    if raw_dt:
                        return {
                            "date_key": raw_dt[:10],
                            "date_label": raw_dt[:10],
                        }

                except Exception:
                    continue

        return {
            "date_key": None,
            "date_label": "unknown",
        }

    def _try_fallback_like_click(self, post_url: str) -> bool:
        for xpath in InstagramCommonLocators.LIKE_BUTTON_XPATHS:
            try:
                if self.browser.is_visible(xpath):
                    self.browser.click(xpath, scroll=True, error=False)
                    self.browser.time_sleep(random.randint(2, 3))

                    like_state_after = self.post_interaction_service.has_post_like()

                    if like_state_after is True:
                        self.log.info("Fallback like OK en post owner: %s", post_url)
                        return True

            except Exception:
                continue

        return False

    # =========================================================
    # TAGGED TAB
    # =========================================================

    def _open_tagged_tab(self) -> bool:
        try:
            if self.browser.is_visible(InstagramCommonLocators.PROFILE_TAGGED_TAB_SELECTED):
                self.log.info("La pestaña de etiquetadas ya estaba activa.")
                return True

            if not self.browser.is_visible(InstagramCommonLocators.PROFILE_TAGGED_TAB):
                self.log.warning("No se encontró la pestaña de etiquetadas.")
                return False

            self.browser.click(
                InstagramCommonLocators.PROFILE_TAGGED_TAB,
                scroll=True,
                error=False,
            )

            self.browser.time_sleep(random.randint(2, 4))

            if self.browser.is_visible(InstagramCommonLocators.PROFILE_TAGGED_TAB_SELECTED):
                self.log.info("Pestaña de etiquetadas abierta correctamente.")
                return True

            self.log.warning("No se pudo confirmar que la pestaña de etiquetadas quedó activa.")
            return False

        except Exception as e:
            self.log.warning("Error abriendo pestaña de etiquetadas: %r", e)
            return False

    # =========================================================
    # PAYLOAD HELPERS
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