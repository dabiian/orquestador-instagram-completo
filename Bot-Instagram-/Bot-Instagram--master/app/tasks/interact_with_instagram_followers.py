import random

from app.core.interfaces import IBrowser, ITask
from app.utils.logger import get_logger
from app.config.locators.instagram_profile_locators import InstagramProfileLocators
from app.config.locators.interact_with_instagram_followers_locators import (
    InteractWithInstagramFollowersLocators,
)
from app.services.instagram_profile_service import InstagramProfileService
from app.services.instagram_post_media_service import InstagramPostMediaService
from app.services.instagram_post_interaction_service import InstagramPostInteractionService
from app.services.instagram_comment_generation_service import InstagramCommentGenerationService
from app.utils.instagram_url import (
    _normalize_instagram_href,
    _extract_username_from_url,
    _is_valid_profile,
)


class InteractWithInstagramFollowersTask(ITask):
    """
    Flow:
    1. Go to Instagram home
    2. Detect my profile from header/nav avatar
    3. Open my profile
    4. Open followers modal
    5. Read real visible followers only
    6. Pick X random followers
    7. Open each follower profile
    8. Read follower profile context
    9. Review posts from newest to oldest
    10. Interact with ONLY 1 valid post per follower
    11. Comment generated from image + caption + optional profile context
    12. Like the post after commenting
    """

    def __init__(self, browser: IBrowser, data: dict, account_api, ai_api):
        self.browser = browser
        self.data = data or {}
        self.account_api = account_api
        self.ai_api = ai_api
        self.log = get_logger(self.__class__.__name__)

        self.profile_service = InstagramProfileService(
            browser=self.browser,
            logger=self.log,
        )

        self.post_media_service = InstagramPostMediaService(
            browser=self.browser,
            ai_api=self.ai_api,
            logger=self.log,
        )

        self.post_interaction_service = InstagramPostInteractionService(
            browser=self.browser,
            logger=self.log,
        )

        self.comment_generation_service = InstagramCommentGenerationService(
            data=self.data,
            account_api=self.account_api,
            ai_api=self.ai_api,
            post_media_service=self.post_media_service,
            logger=self.log,
        )

    def execute(self) -> str:
        try:
            self.log.info("Starting Instagram followers flow")

            my_profile_url = self._get_my_profile_url()
            if not my_profile_url:
                return "✗ Could not detect my Instagram profile URL"

            opened_followers_modal = self._open_followers_modal(my_profile_url)
            if not opened_followers_modal:
                return "✗ Followers modal could not be opened"

            follower_candidates = self._get_visible_follower_candidates(my_profile_url)
            if not follower_candidates:
                return "✗ No valid followers were found in the modal"

            followers_limit = self._get_followers_limit()
            followers_limit = min(followers_limit, len(follower_candidates))

            selected_followers = random.sample(
                follower_candidates,
                k=followers_limit,
            )

            self.log.info(
                "Followers selected for interaction: %s/%s",
                len(selected_followers),
                len(follower_candidates),
            )

            successful_followers = 0
            failed_followers = 0
            processed_results = []

            for follower_index, selected_follower in enumerate(selected_followers, start=1):
                username = selected_follower.get("username")
                follower_url = selected_follower.get("url")

                try:
                    self.log.info(
                        "Processing follower %s/%s: %s | %s",
                        follower_index,
                        len(selected_followers),
                        username,
                        follower_url,
                    )

                    self.profile_service.open_url(follower_url)
                    self.browser.time_sleep(random.randint(3, 5))

                    profile_context = self._get_follower_profile_context()

                    result = self._process_follower_posts(
                        max_scrolls=5,
                        profile_context=profile_context,
                    )

                    if str(result).startswith("✗"):
                        failed_followers += 1
                        processed_results.append(
                            {
                                "username": username,
                                "url": follower_url,
                                "ok": False,
                                "result": result,
                            }
                        )

                        self.log.warning(
                            "Follower processed without full interaction: %s | %s | %s",
                            username,
                            follower_url,
                            result,
                        )
                        continue

                    successful_followers += 1
                    processed_results.append(
                        {
                            "username": username,
                            "url": follower_url,
                            "ok": True,
                            "result": result,
                        }
                    )

                    self.log.info(
                        "Follower processed successfully: %s | %s | %s",
                        username,
                        follower_url,
                        result,
                    )

                    self.browser.time_sleep(random.randint(3, 6))

                except Exception as e:
                    failed_followers += 1
                    processed_results.append(
                        {
                            "username": username,
                            "url": follower_url,
                            "ok": False,
                            "result": repr(e),
                        }
                    )

                    self.log.warning(
                        "Error processing follower %s | %s: %r",
                        username,
                        follower_url,
                        e,
                    )
                    continue

            if successful_followers <= 0:
                return (
                    f"✗ No followers were fully processed | "
                    f"selected={len(selected_followers)} | "
                    f"success={successful_followers} | "
                    f"failed={failed_followers} | "
                    f"details={processed_results}"
                )

            return (
                f"✓ Followers processed | "
                f"selected={len(selected_followers)} | "
                f"success={successful_followers} | "
                f"failed={failed_followers} | "
                f"details={processed_results}"
            )

        except Exception as e:
            self.log.error("Error in Instagram followers flow: %r", e)
            return f"✗ Error in Instagram followers flow: {repr(e)}"

    # =========================================================
    # CONFIG
    # =========================================================

    def _get_followers_limit(self) -> int:
        try:
            custom_task = self.data.get("custom_task") or {}

            raw_value = (
                self.data.get("followers_to_process")
                or self.data.get("max_followers")
                or self.data.get("followers_limit")
                or custom_task.get("followers_to_process")
                or custom_task.get("max_followers")
                or custom_task.get("followers_limit")
            )

            if raw_value is None or raw_value == "":
                return random.randint(2, 4)

            value = int(raw_value)

            if value <= 0:
                return 1

            return min(value, 10)

        except Exception:
            return random.randint(2, 4)

    # =========================================================
    # MY PROFILE
    # =========================================================

    def _get_my_profile_url(self):
        try:
            self.profile_service.open_url(InstagramProfileLocators.HOME_PAGE)
            self.browser.time_sleep(random.randint(3, 5))

            if not self.browser.is_visible(InstagramProfileLocators.MY_PROFILE_LINK):
                self.log.warning("My profile link was not found in header/nav.")
                return None

            profile_elements = self.browser.obtener_elementos(
                InstagramProfileLocators.MY_PROFILE_LINK,
                time_x=10,
            )

            if not profile_elements:
                self.log.warning("Could not obtain my profile link element.")
                return None

            profile_href = (profile_elements[0].get_attribute("href") or "").strip()

            if not profile_href:
                self.log.warning("My profile href came back empty.")
                return None

            profile_url = _normalize_instagram_href(profile_href)

            self.log.info("Detected my profile URL: %s", profile_url)
            return profile_url

        except Exception as e:
            self.log.warning("Error detecting my profile URL: %r", e)
            return None

    # =========================================================
    # FOLLOWERS MODAL
    # =========================================================

    def _open_followers_modal(self, my_profile_url: str) -> bool:
        try:
            self.profile_service.open_url(my_profile_url)
            self.browser.time_sleep(random.randint(3, 5))

            for xpath in getattr(
                InteractWithInstagramFollowersLocators,
                "FOLLOWERS_BUTTON_XPATHS",
                [InteractWithInstagramFollowersLocators.FOLLOWERS_BUTTON],
            ):
                try:
                    if not self.browser.is_visible(xpath):
                        continue

                    self.log.info(
                        "[followers] intentando abrir modal con xpath=%s",
                        xpath,
                    )

                    self.browser.click(
                        xpath,
                        scroll=True,
                        error=False,
                    )

                    self.browser.time_sleep(random.randint(2, 4))

                    if self.browser.is_visible(InteractWithInstagramFollowersLocators.FOLLOWERS_MODAL):
                        self.log.info(
                            "[followers] modal abierto correctamente con xpath=%s",
                            xpath,
                        )
                        return True

                except Exception as e:
                    self.log.warning(
                        "[followers] error intentando click followers xpath=%s | error=%r",
                        xpath,
                        e,
                    )
                    continue

            try:
                result = self.browser.driver.execute_script(
                    InteractWithInstagramFollowersLocators.CLICK_FOLLOWERS_BUTTON_SCRIPT
                )

                self.log.info(
                    "[followers] click followers por JS result=%s",
                    result,
                )

                self.browser.time_sleep(random.randint(2, 4))

                if self.browser.is_visible(InteractWithInstagramFollowersLocators.FOLLOWERS_MODAL):
                    self.log.info("[followers] modal abierto correctamente con fallback JS.")
                    return True

            except Exception as e:
                self.log.warning(
                    "[followers] error en fallback JS followers button: %r",
                    e,
                )

            self.log.warning("Followers modal did not appear after all click attempts.")
            return False

        except Exception as e:
            self.log.warning("Error opening followers modal: %r", e)
            return False

    def _get_visible_follower_candidates(self, my_profile_url: str):
        try:
            # =====================================================
            # REGLA CRÍTICA:
            # Si aparece "Suggested for you", NUNCA usar FOLLOWERS_USERS general,
            # porque puede mezclar sugeridos con seguidores reales.
            # =====================================================

            suggestions_visible = False

            try:
                suggestions_visible = self.browser.is_visible(
                    InteractWithInstagramFollowersLocators.FOLLOWERS_SUGGESTIONS_HEADER
                )
            except Exception:
                suggestions_visible = False

            # =====================================================
            # 1) EXTRACCIÓN ESTRICTA ANTES DE "SUGGESTED FOR YOU"
            # =====================================================
            if suggestions_visible:
                self.log.info(
                    "[followers] Suggested block detected. Using STRICT before-suggestions extractor only."
                )

                try:
                    elements = self.browser.obtener_elementos(
                        InteractWithInstagramFollowersLocators.FOLLOWERS_USERS_BEFORE_SUGGESTIONS,
                        time_x=10,
                    )

                    candidates = self._extract_candidates_from_elements(
                        elements=elements,
                        my_profile_url=my_profile_url,
                    )

                    self.log.info(
                        "[followers] candidatos reales antes de sugeridos=%s",
                        len(candidates),
                    )

                    if candidates:
                        return candidates

                    self.log.warning(
                        "[followers] Suggested block exists but before-suggestions returned 0. "
                        "Returning empty list to avoid interacting with suggested users."
                    )

                    return []

                except Exception as e:
                    self.log.warning(
                        "[followers] strict before-suggestions extraction failed: %r. "
                        "Returning empty list to avoid suggested users.",
                        e,
                    )
                    return []

            # =====================================================
            # 2) INTENTO JS SOLO SI NO HAY BLOQUE DE SUGERIDOS VISIBLE
            # =====================================================
            try:
                result = self.browser.driver.execute_script(
                    InteractWithInstagramFollowersLocators.EXTRACT_REAL_FOLLOWERS_FROM_MODAL_SCRIPT
                )

                self.log.info(
                    "[followers] extract real followers result=%s",
                    result,
                )

                raw_followers = []

                if result and result.get("ok"):
                    raw_followers = result.get("followers") or []

                candidates = []
                seen_urls = set()

                for item in raw_followers:
                    try:
                        if not isinstance(item, dict):
                            continue

                        href = str(item.get("url") or "").strip()
                        username = str(item.get("username") or "").strip()

                        if not href or not username:
                            continue

                        href = _normalize_instagram_href(href)

                        if not _is_valid_profile(href):
                            continue

                        username = _extract_username_from_url(href) or username

                        if not username:
                            continue

                        if href.rstrip("/") == my_profile_url.rstrip("/"):
                            continue

                        if href in seen_urls:
                            continue

                        seen_urls.add(href)

                        candidates.append(
                            {
                                "username": username,
                                "url": href,
                            }
                        )

                    except Exception as e:
                        self.log.warning("Error procesando follower real del modal: %r", e)
                        continue

                self.log.info(
                    "[followers] followers reales extraídos por JS=%s | raw_count=%s",
                    len(candidates),
                    len(raw_followers),
                )

                if candidates:
                    return candidates

                self.log.warning(
                    "[followers] extractor JS devolvió 0. Se intenta fallback legacy seguro."
                )

            except Exception as e:
                self.log.warning(
                    "[followers] extractor JS falló. Se intenta fallback legacy seguro. error=%r",
                    e,
                )

            # =====================================================
            # 3) FALLBACK LEGACY SEGURO
            # Solo permitido si NO hay bloque de sugeridos visible.
            # =====================================================
            try:
                elements = self.browser.obtener_elementos(
                    InteractWithInstagramFollowersLocators.FOLLOWERS_USERS,
                    time_x=10,
                )

                candidates = self._extract_candidates_from_elements(
                    elements=elements,
                    my_profile_url=my_profile_url,
                )

                self.log.info(
                    "[followers] candidatos extraídos por fallback legacy seguro=%s",
                    len(candidates),
                )

                return candidates

            except Exception as e:
                self.log.warning("Error getting follower candidates with safe legacy fallback: %r", e)
                return []

        except Exception as e:
            self.log.warning("Error getting follower candidates: %r", e)
            return []

    def _extract_candidates_from_elements(self, elements, my_profile_url: str):
        candidates = []
        seen_urls = set()

        for element in elements:
            try:
                href = (element.get_attribute("href") or "").strip()

                if not href:
                    continue

                href = _normalize_instagram_href(href)

                if not _is_valid_profile(href):
                    continue

                username = _extract_username_from_url(href)

                if not username:
                    continue

                if href.rstrip("/") == my_profile_url.rstrip("/"):
                    continue

                if href in seen_urls:
                    continue

                seen_urls.add(href)

                candidates.append(
                    {
                        "username": username,
                        "url": href,
                    }
                )

            except Exception as e:
                self.log.warning("Error processing visible follower: %r", e)
                continue

        return candidates

    # =========================================================
    # FOLLOWER PROFILE / POSTS
    # =========================================================

    def _get_follower_profile_context(self):
        try:
            profile_context = self.post_media_service.get_current_profile_description_context()

            if profile_context:
                self.log.info(
                    "Follower profile context obtained successfully: %s",
                    profile_context,
                )
            else:
                self.log.info("Follower profile context is empty or unavailable.")

            return profile_context

        except Exception as e:
            self.log.warning("Error obtaining follower profile context: %r", e)
            return None

    def _process_follower_posts(self, max_scrolls=5, profile_context=None):
        post_urls = self._get_profile_post_urls(max_scrolls=max_scrolls)

        if not post_urls:
            self.log.warning("No posts were found in the follower profile.")
            return "✗ No posts were found in the profile"

        self.log.info("Posts detected in follower profile: %s", len(post_urls))

        already_interacted_posts = 0
        skipped_posts_due_to_error = 0

        for index, post_url in enumerate(post_urls, start=1):
            try:
                self.log.info(
                    "Reviewing post %s/%s: %s",
                    index,
                    len(post_urls),
                    post_url,
                )

                self.profile_service.open_url(post_url)
                self.browser.time_sleep(random.randint(3, 5))

                like_state = self.post_interaction_service.has_post_like()

                if like_state is None:
                    skipped_posts_due_to_error += 1
                    self.log.warning(
                        "Could not determine like state for %s. Skipping safely.",
                        post_url,
                    )
                    continue

                if like_state is True:
                    already_interacted_posts += 1
                    self.log.info("Post already had a like. Assuming prior interaction.")
                    continue

                ok_comment_ai, comment_text = (
                    self.comment_generation_service.generate_comment_from_current_post_image_caption_profile_description(
                        profile_context=profile_context,
                        category="comentario_publicacion_follower",
                    )
                )

                if not ok_comment_ai or not comment_text:
                    skipped_posts_due_to_error += 1
                    self.log.warning(
                        "Could not generate AI comment from image + caption for %s",
                        post_url,
                    )
                    continue

                self.log.info("Generated comment for follower post: %s", comment_text)

                ok_comment = self.post_interaction_service.comment_current_post(comment_text)

                if not ok_comment:
                    skipped_posts_due_to_error += 1
                    self.log.warning("Comment failed on %s", post_url)
                    continue

                self.browser.time_sleep(random.randint(1, 2))

                ok_like = self.post_interaction_service.like_current_post()

                if ok_like:
                    return f"✓ Comment and like completed on one post: {post_url}"

                skipped_posts_due_to_error += 1

                self.log.warning(
                    "Comment succeeded but like failed on %s",
                    post_url,
                )

            except Exception as e:
                skipped_posts_due_to_error += 1
                self.log.warning("Error reviewing post %s: %r", post_url, e)
                continue

        if already_interacted_posts == len(post_urls):
            return "✗ All posts already had a like"

        if skipped_posts_due_to_error > 0:
            return "✗ No safe post was found where comment + like could be completed"

        return "✗ No valid post could be processed"

    def _get_profile_post_urls(self, max_scrolls=5):
        urls = []
        seen_urls = set()
        scroll_attempts_without_growth = 0
        last_count = -1

        while scroll_attempts_without_growth < max_scrolls:
            try:
                elements = self.browser.obtener_elementos(
                    InstagramProfileLocators.PROFILE_POST_LINKS,
                    time_x=8,
                )
            except Exception as e:
                self.log.warning("Error obtaining profile post links: %r", e)
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
                    self.log.warning("Error reading profile post URL: %r", e)
                    continue

            current_count = len(urls)

            if current_count == last_count:
                scroll_attempts_without_growth += 1
            else:
                scroll_attempts_without_growth = 0
                last_count = current_count

            self.log.info(
                "Collected posts so far: %s | no_growth=%s/%s",
                current_count,
                scroll_attempts_without_growth,
                max_scrolls,
            )

            try:
                elements = self.browser.obtener_elementos(
                    InstagramProfileLocators.PROFILE_POST_LINKS,
                    time_x=5,
                )
            except Exception:
                elements = []

            if not elements:
                break

            try:
                last_element = elements[-1]
                self.browser.scroll_to_element(last_element)
            except Exception:
                try:
                    self.browser.scroll_to_xpath_force_feed_load(
                        f"({InstagramProfileLocators.PROFILE_POST_LINKS})[last()]"
                    )
                except Exception:
                    try:
                        self.browser.driver.execute_script(
                            InstagramProfileLocators.SCROLL_PROFILE_GRID_SCRIPT
                        )
                    except Exception:
                        pass

            self.browser.time_sleep(random.randint(2, 4))

        return urls