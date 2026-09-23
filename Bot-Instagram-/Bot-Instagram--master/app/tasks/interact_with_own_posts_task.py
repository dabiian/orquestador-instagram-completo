import json
import random
import re
import unicodedata
from typing import List, Optional, TypedDict

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from app.core.interfaces import IBrowser, ITask
from app.utils.logger import get_logger
from app.utils.instagram_url import _normalize_instagram_href
from app.config.locators.instagram_profile_locators import InstagramProfileLocators
from app.services.instagram_profile_service import InstagramProfileService
from app.services.instagram_post_media_service import InstagramPostMediaService
from app.services.instagram_post_interaction_service import InstagramPostInteractionService


class OwnPostsInteractionResult(TypedDict):
    ok: bool
    message: str
    posts_detectados: int
    posts_objetivo: int
    posts_visitados: int
    posts_sin_comentarios: int
    comentarios_detectados: int
    comentarios_candidatos: int
    comentarios_procesados: int
    likes_comentarios_ok: int
    likes_comentarios_fail: int
    replies_ok: int
    replies_fail: int
    comentarios_omitidos: int


class InteractWithOwnPostsTask(ITask):
    PROFILE_SCROLL_NO_GROWTH = 4
    PROFILE_HARD_SCROLL_LIMIT = 60
    PROFILE_MIN_POSTS_TO_COLLECT = 12
    PROFILE_STOP_WHEN_REACHING = 20

    POSTS_MIN = 3
    POSTS_MAX = 5

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

    def execute(self) -> str:
        try:
            self.log.info("Starting InteractWithOwnPostsTask.")

            my_profile_url = self._get_my_profile_url()
            if not my_profile_url:
                return "✗ No se pudo detectar la URL de mi perfil de Instagram"

            self.profile_service.open_url(my_profile_url)
            self._sleep_profile()

            result = self._process_random_own_posts_live(my_profile_url)

            if not result["ok"]:
                return f"✗ {result['message']} | {my_profile_url}"

            return self._build_success_message(my_profile_url, result)

        except Exception as e:
            self.log.error("Error en InteractWithOwnPostsTask: %r", e)
            return f"✗ Error en InteractWithOwnPostsTask: {repr(e)}"

    def _build_success_message(
        self,
        my_profile_url: str,
        result: OwnPostsInteractionResult,
    ) -> str:
        return (
            f"✓ Publicaciones propias procesadas | {my_profile_url} | "
            f"posts_detectados={result['posts_detectados']} | "
            f"posts_objetivo={result['posts_objetivo']} | "
            f"posts_visitados={result['posts_visitados']} | "
            f"posts_sin_comentarios={result['posts_sin_comentarios']} | "
            f"comentarios_detectados={result['comentarios_detectados']} | "
            f"comentarios_candidatos={result['comentarios_candidatos']} | "
            f"comentarios_procesados={result['comentarios_procesados']} | "
            f"likes_comentarios_ok={result['likes_comentarios_ok']} | "
            f"likes_comentarios_fail={result['likes_comentarios_fail']} | "
            f"replies_ok={result['replies_ok']} | "
            f"replies_fail={result['replies_fail']} | "
            f"comentarios_omitidos={result['comentarios_omitidos']}"
        )

    def _sleep_profile(self) -> None:
        self.browser.time_sleep(random.randint(self.PROFILE_WAIT_MIN, self.PROFILE_WAIT_MAX))

    def _sleep_post(self) -> None:
        self.browser.time_sleep(random.randint(self.POST_WAIT_MIN, self.POST_WAIT_MAX))

    def _sleep_short(self) -> None:
        self.browser.time_sleep(random.randint(self.SHORT_WAIT_MIN, self.SHORT_WAIT_MAX))

    def _new_result(
        self,
        *,
        posts_detectados: int,
        posts_objetivo: int,
    ) -> OwnPostsInteractionResult:
        return {
            "ok": True,
            "message": "OK",
            "posts_detectados": posts_detectados,
            "posts_objetivo": posts_objetivo,
            "posts_visitados": 0,
            "posts_sin_comentarios": 0,
            "comentarios_detectados": 0,
            "comentarios_candidatos": 0,
            "comentarios_procesados": 0,
            "likes_comentarios_ok": 0,
            "likes_comentarios_fail": 0,
            "replies_ok": 0,
            "replies_fail": 0,
            "comentarios_omitidos": 0,
        }

    def _empty_result(self, message: str) -> OwnPostsInteractionResult:
        return {
            "ok": False,
            "message": message,
            "posts_detectados": 0,
            "posts_objetivo": 0,
            "posts_visitados": 0,
            "posts_sin_comentarios": 0,
            "comentarios_detectados": 0,
            "comentarios_candidatos": 0,
            "comentarios_procesados": 0,
            "likes_comentarios_ok": 0,
            "likes_comentarios_fail": 0,
            "replies_ok": 0,
            "replies_fail": 0,
            "comentarios_omitidos": 0,
        }

    # =========================================================
    # PROFILE
    # =========================================================

    def _get_my_profile_url(self) -> Optional[str]:
        try:
            self.profile_service.open_url(InstagramProfileLocators.HOME_PAGE)
            self.browser.time_sleep(random.randint(3, 5))

            if not self.browser.is_visible(InstagramProfileLocators.MY_PROFILE_LINK):
                self.log.warning("No se encontró el link de mi perfil en header/nav.")
                return None

            profile_elements = self.browser.obtener_elementos(
                InstagramProfileLocators.MY_PROFILE_LINK,
                time_x=10,
            )

            if not profile_elements:
                self.log.warning("No se pudo obtener el elemento de mi perfil.")
                return None

            profile_href = (profile_elements[0].get_attribute("href") or "").strip()
            if not profile_href:
                self.log.warning("Mi profile href vino vacío.")
                return None

            profile_url = _normalize_instagram_href(profile_href)
            self.log.info("Mi perfil detectado: %s", profile_url)
            return profile_url

        except Exception as e:
            self.log.warning("Error detectando mi perfil: %r", e)
            return None

    def _process_random_own_posts_live(self, my_profile_url: str) -> OwnPostsInteractionResult:
        post_urls = self._get_profile_post_urls(
            max_scrolls_without_growth=self.PROFILE_SCROLL_NO_GROWTH,
            hard_scroll_limit=self.PROFILE_HARD_SCROLL_LIMIT,
            min_posts_to_collect=self.PROFILE_MIN_POSTS_TO_COLLECT,
            stop_when_reaching=self.PROFILE_STOP_WHEN_REACHING,
        )

        if not post_urls:
            return self._empty_result("No se encontraron publicaciones válidas en mi perfil")

        random.shuffle(post_urls)
        sample_urls = post_urls[: self.PROFILE_STOP_WHEN_REACHING]

        posts_objetivo = min(
            len(sample_urls),
            random.randint(self.POSTS_MIN, self.POSTS_MAX),
        )

        result = self._new_result(
            posts_detectados=len(post_urls),
            posts_objetivo=posts_objetivo,
        )

        self.log.info(
            "Own posts live | detectados=%s | muestra=%s | objetivo=%s",
            len(post_urls),
            len(sample_urls),
            posts_objetivo,
        )

        selected_count = 0

        for index, post_url in enumerate(sample_urls, start=1):
            if selected_count >= posts_objetivo:
                break

            try:
                self.log.info(
                    "Revisando publicación propia %s/%s: %s",
                    index,
                    len(sample_urls),
                    post_url,
                )

                opened_ok = self._open_post_from_profile_grid(my_profile_url, post_url)
                if not opened_ok:
                    self.log.warning("No se pudo abrir el post desde el grid: %s", post_url)
                    continue

                self._ensure_post_surface_loaded()
                self.browser.time_sleep(1)

                selected_count += 1
                result["posts_visitados"] += 1

                post_context = self._safe_get_current_post_context()
                self.log.info("Contexto post actual: %s", self._safe_json_for_log(post_context))

                comments = self._expand_comments_for_interaction(
                    max_rounds=3,
                    min_comments_goal=12,
                )

                result["comentarios_detectados"] += len(comments)

                if not comments:
                    result["posts_sin_comentarios"] += 1
                    self.log.info("Post sin comentarios visibles: %s", post_url)
                    self._sleep_short()
                    continue

                candidate_comments = self._filter_comment_candidates(comments)
                result["comentarios_candidatos"] += len(candidate_comments)

                if not candidate_comments:
                    self.log.info("No hubo comentarios candidatos válidos en: %s", post_url)
                    self._sleep_short()
                    continue

                selected_comments = list(candidate_comments)

                self.log.info(
                    "Post procesable | comentarios_visibles=%s | candidatos=%s | procesar_todos=%s | url=%s",
                    len(comments),
                    len(candidate_comments),
                    len(selected_comments),
                    post_url,
                )

                for comment_index, comment in enumerate(selected_comments, start=1):
                    try:
                        action = self._decide_comment_action(comment)

                        self.log.info(
                            "Procesando comentario %s/%s | action=%s | username=%s | permalink=%s",
                            comment_index,
                            len(selected_comments),
                            action,
                            comment.get("username"),
                            comment.get("permalink"),
                        )

                        processed_ok = self._process_comment_action(
                            comment=comment,
                            action=action,
                            post_context=post_context,
                            result=result,
                        )

                        if processed_ok:
                            result["comentarios_procesados"] += 1
                        else:
                            result["comentarios_omitidos"] += 1

                        self._sleep_short()

                    except Exception as e:
                        result["comentarios_omitidos"] += 1
                        self.log.warning("Error procesando comentario individual: %r", e)
                        continue

            except Exception as e:
                self.log.warning("Error procesando publicación propia %s: %r", post_url, e)
                continue

        if result["posts_visitados"] == 0:
            return self._empty_result("No se pudieron abrir publicaciones propias")

        return result

    def _get_profile_post_urls(
        self,
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
                    InstagramProfileLocators.PROFILE_POST_LINKS,
                    time_x=8,
                )
            except Exception as e:
                self.log.warning("Timeout/error leyendo posts del perfil propio: %r", e)
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
                    self.log.warning("Error leyendo URL del post propio: %r", e)
                    continue

            current_count = len(urls)

            if current_count == last_count:
                scroll_attempts_without_growth += 1
            else:
                scroll_attempts_without_growth = 0
                last_count = current_count

            self.log.info(
                "Posts propios recolectados: %s | scroll=%s/%s | no_growth=%s",
                current_count,
                total_scrolls,
                hard_scroll_limit,
                scroll_attempts_without_growth,
            )

            if current_count >= stop_when_reaching:
                self.log.info(
                    "Se detiene scroll porque ya se alcanzó el objetivo: %s",
                    stop_when_reaching,
                )
                break

            if current_count > 0 and scroll_attempts_without_growth >= max_scrolls_without_growth:
                self.log.info(
                    "Se detiene scroll por no_growth=%s con current_count=%s",
                    scroll_attempts_without_growth,
                    current_count,
                )
                break

            if current_count == 0 and scroll_attempts_without_growth >= max_scrolls_without_growth:
                self.log.info("Se detiene scroll porque no se detectaron posts tras varios intentos.")
                break

            if not self._scroll_profile_once():
                self.log.warning("No se pudo aplicar scroll al perfil propio.")
                break

            self.browser.time_sleep(random.randint(2, 4))

        if len(urls) < min_posts_to_collect:
            self.log.info(
                "Posts recolectados por debajo del mínimo sugerido | encontrados=%s | minimo=%s",
                len(urls),
                min_posts_to_collect,
            )

        return urls

    def _scroll_profile_once(self) -> bool:
        try:
            self.browser.driver.execute_script(InstagramProfileLocators.SCROLL_PROFILE_GRID_SCRIPT)
            self.log.info("Scroll aplicado con window.scrollBy")
            return True
        except Exception as e:
            self.log.warning("Falló window.scrollBy: %r", e)

        try:
            self.browser.driver.execute_script(InstagramProfileLocators.SCROLL_TO_BOTTOM_SCRIPT)
            self.log.info("Scroll aplicado con window.scrollTo(bottom)")
            return True
        except Exception as e:
            self.log.warning("Falló window.scrollTo(bottom): %r", e)

        return False

    def _extract_post_path(self, post_url: str) -> str:
        try:
            m = re.search(r"(\/(?:p|reel|tv)\/[^\/?#]+\/)", str(post_url or "").strip())
            return m.group(1) if m else ""
        except Exception:
            return ""

    def _open_post_from_profile_grid(
        self,
        my_profile_url: str,
        post_url: str,
        max_scrolls: int = 8,
    ) -> bool:
        try:
            target_path = self._extract_post_path(post_url)
            if not target_path:
                self.log.warning("No se pudo extraer target_path del post: %s", post_url)
                return False

            self.profile_service.open_url(my_profile_url)
            self._sleep_profile()

            for scroll_idx in range(1, max_scrolls + 1):
                try:
                    elements = self.browser.obtener_elementos(
                        InstagramProfileLocators.PROFILE_POST_LINKS,
                        time_x=8,
                    )
                except Exception as e:
                    self.log.warning("No se pudieron obtener posts del grid: %r", e)
                    elements = []

                for element in elements:
                    try:
                        href = (element.get_attribute("href") or "").strip()
                        if not href:
                            continue

                        href = _normalize_instagram_href(href)

                        if target_path not in href:
                            continue

                        self.log.info(
                            "Post encontrado en grid | target_path=%s | href=%s",
                            target_path,
                            href,
                        )

                        try:
                            self.browser.driver.execute_script(
                                InstagramProfileLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                                element,
                            )
                        except Exception:
                            pass

                        self.browser.time_sleep(random.uniform(0.8, 1.5))

                        # =====================================================
                        # IMPORTANTE:
                        # Se restaura el orden viejo que sí funcionaba:
                        # 1. element.click()
                        # 2. ActionChains
                        # 3. JS click
                        # =====================================================

                        try:
                            element.click()
                            self._sleep_post()
                            return True
                        except Exception as e:
                            self.log.warning(
                                "[own-posts] element.click falló | target_path=%s | error=%r",
                                target_path,
                                e,
                            )

                        try:
                            ActionChains(self.browser.driver).move_to_element(element).pause(
                                random.uniform(0.2, 0.5)
                            ).click().perform()
                            self._sleep_post()
                            return True
                        except Exception as e:
                            self.log.warning(
                                "[own-posts] ActionChains click falló | target_path=%s | error=%r",
                                target_path,
                                e,
                            )

                        try:
                            self.browser.driver.execute_script(
                                InstagramProfileLocators.CLICK_ELEMENT_SCRIPT,
                                element,
                            )
                            self._sleep_post()
                            return True
                        except Exception as e:
                            self.log.warning(
                                "[own-posts] JS click falló | target_path=%s | error=%r",
                                target_path,
                                e,
                            )

                    except Exception:
                        continue

                self.log.info(
                    "No se encontró aún el post en el grid | scroll=%s/%s | target_path=%s",
                    scroll_idx,
                    max_scrolls,
                    target_path,
                )

                if not self._scroll_profile_once():
                    break

                self.browser.time_sleep(random.randint(2, 4))

            self.log.warning(
                "No se pudo abrir el post desde el grid del perfil: %s",
                post_url,
            )
            return False

        except Exception as e:
            self.log.warning("Error abriendo post desde grid del perfil: %r", e)
            return False

    # =========================================================
    # POST / COMMENTS
    # =========================================================

    def _ensure_post_surface_loaded(self, max_attempts: int = 6) -> bool:
        try:
            for attempt in range(1, max_attempts + 1):
                state = self.browser.driver.execute_script(
                    InstagramProfileLocators.POST_SURFACE_STATE_SCRIPT
                ) or {}

                self.log.info(
                    "[own-posts] surface-state intento=%s => %s",
                    attempt,
                    self._safe_json_for_log(state),
                )

                if state.get("hasImage") and (
                    state.get("hasCaption")
                    or state.get("hasCommentPermalinks")
                    or state.get("hasCommentBox")
                ):
                    return True

                self.browser.time_sleep(1)

            return False

        except Exception as e:
            self.log.warning("Error asegurando carga de la superficie del post: %r", e)
            return False

    def _safe_get_current_post_context(self):
        try:
            best = {}

            for attempt in range(1, 6):
                data = self.browser.driver.execute_script(
                    InstagramProfileLocators.OWN_CURRENT_POST_CONTEXT_SCRIPT
                ) or {}

                best = {
                    "author_username": str(data.get("author_username") or "").strip(),
                    "caption": str(data.get("caption") or "").strip(),
                    "media_alt": str(data.get("media_alt") or "").strip(),
                    "media_src": str(data.get("media_src") or "").strip(),
                    "post_url": str(data.get("url") or self.browser.driver.current_url or "").strip(),
                }

                self.log.info(
                    "[own-posts] current-post-context intento=%s => %s",
                    attempt,
                    self._safe_json_for_log(best),
                )

                if best["caption"] or (best["author_username"] and best["media_alt"]):
                    return best

                self.browser.time_sleep(1)

            return best

        except Exception as e:
            self.log.warning("No se pudo obtener contexto del post actual: %r", e)
            return {}

    def _expand_comments_for_interaction(
        self,
        max_rounds: int = 3,
        min_comments_goal: int = 12,
    ) -> List[dict]:
        try:
            best_comments = self._get_visible_comments() or []
            best_count = len(best_comments)

            self.log.info("Comentarios iniciales visibles para interacción: %s", best_count)

            if 0 < best_count < min_comments_goal:
                self.log.info("Hay comentarios visibles (%s) y no hace falta expandir.", best_count)
                return best_comments

            if best_count == 0:
                self.log.info("No hay comentarios visibles al abrir el post.")
                return []

            stagnation = 0

            for round_idx in range(1, max_rounds + 1):
                clicked = self._click_load_more_comments_button()
                scrolled = self._scroll_last_visible_comment()

                if not clicked and not scrolled:
                    self.log.info("No hay botón para expandir ni más scroll útil.")
                    break

                fresh_comments = self._get_visible_comments() or []
                fresh_count = len(fresh_comments)

                self.log.info(
                    "Expansión comentarios ronda %s/%s | antes=%s | ahora=%s | clicked=%s | scrolled=%s",
                    round_idx,
                    max_rounds,
                    best_count,
                    fresh_count,
                    clicked,
                    scrolled,
                )

                if fresh_count > best_count:
                    best_comments = fresh_comments
                    best_count = fresh_count
                    stagnation = 0
                else:
                    stagnation += 1

                if best_count >= min_comments_goal:
                    break

                if stagnation >= 1:
                    break

            self.log.info("Comentarios finales visibles para interacción: %s", best_count)
            return best_comments

        except Exception as e:
            self.log.warning("Error expandiendo comentarios para interacción: %r", e)
            return self._get_visible_comments() or []

    def _get_visible_comments(self) -> list[dict]:
        try:
            best_comments = []

            for attempt in range(1, 6):
                payload = self.browser.driver.execute_script(
                    InstagramProfileLocators.VISIBLE_COMMENTS_SCRIPT
                ) or {}

                raw_comments = payload.get("comments") or []

                self.log.info(
                    "[own-posts] comentarios visibles por JS intento=%s => %s",
                    attempt,
                    len(raw_comments),
                )

                if raw_comments:
                    comments = []

                    for idx, item in enumerate(raw_comments, start=1):
                        username = str(item.get("username") or "").strip()
                        text = str(item.get("text") or "").strip()
                        profile_href = str(item.get("profile_href") or "").strip()
                        permalink = str(item.get("permalink") or "").strip()
                        has_reply_button = bool(item.get("has_reply_button"))
                        has_like_button = bool(item.get("has_like_button"))

                        root_el = self._find_comment_root_element(
                            profile_href=profile_href,
                            permalink=permalink,
                            text=text,
                        )

                        comments.append({
                            "index": idx,
                            "username": username,
                            "text": text,
                            "profile_href": profile_href,
                            "permalink": permalink,
                            "time_text": "",
                            "has_reply_button": has_reply_button,
                            "has_options": False,
                            "has_like_button": has_like_button,
                            "username_element": None,
                            "element": root_el,
                        })

                    if comments:
                        return comments

                    best_comments = comments

                self.browser.time_sleep(1)

            return best_comments

        except Exception as e:
            self.log.warning("Error obteniendo comentarios visibles: %r", e)
            return []

    def _find_comment_root_element(
        self,
        *,
        profile_href: str = "",
        permalink: str = "",
        text: str = "",
    ):
        try:
            return self.browser.driver.execute_script(
                InstagramProfileLocators.FIND_COMMENT_ROOT_SCRIPT,
                profile_href,
                permalink,
                text,
            )
        except Exception:
            return None

    def _find_visible_comment_again(self, original_comment: dict) -> Optional[dict]:
        try:
            if not original_comment:
                return None

            target_profile = str(original_comment.get("profile_href") or "").strip().rstrip("/")
            target_permalink = str(original_comment.get("permalink") or "").strip().rstrip("/")
            target_text = self._normalize_text(original_comment.get("text") or "")

            comments = self._get_visible_comments()

            for comment in comments:
                profile_href = str(comment.get("profile_href") or "").strip().rstrip("/")
                permalink = str(comment.get("permalink") or "").strip().rstrip("/")
                text = self._normalize_text(comment.get("text") or "")

                if target_permalink and permalink == target_permalink:
                    return comment

                if target_profile and profile_href == target_profile and target_text and target_text in text:
                    return comment

                if target_text and target_text == text:
                    return comment

            return None

        except Exception:
            return None

    def _scroll_last_visible_comment(self) -> bool:
        try:
            comments = self._get_visible_comments()
            if not comments:
                return False

            last_comment_el = comments[-1].get("element")
            if last_comment_el is None:
                return False

            self.browser.driver.execute_script(
                InstagramProfileLocators.SCROLL_INTO_VIEW_END_SCRIPT,
                last_comment_el,
            )
            self.browser.time_sleep(random.uniform(1.0, 1.8))
            return True

        except Exception as e:
            self.log.warning("Error haciendo scroll al último comentario: %r", e)
            return False

    def _click_load_more_comments_button(self) -> bool:
        try:
            for xpath in InstagramProfileLocators.LOAD_MORE_COMMENTS_BUTTONS:
                elems = self.browser.driver.find_elements(By.XPATH, xpath)

                for btn in elems:
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            self.browser.driver.execute_script(
                                InstagramProfileLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                                btn,
                            )
                            btn.click()
                            self.browser.time_sleep(random.uniform(1.2, 2.0))
                            self.log.info("[own-posts] click cargar más comentarios: OK")
                            return True
                    except Exception:
                        continue

            return False

        except Exception as e:
            self.log.warning("Error en _click_load_more_comments_button: %r", e)
            return False

    # =========================================================
    # COMMENT ACTIONS
    # =========================================================

    def _filter_comment_candidates(self, comments: List[dict]) -> List[dict]:
        my_username = self._get_my_instagram_username()
        candidates: List[dict] = []
        seen_keys = set()

        for comment in comments or []:
            try:
                username = str(comment.get("username") or "").strip().lower().replace("@", "")
                text = str(comment.get("text") or "").strip()
                profile_href = str(comment.get("profile_href") or "").strip().replace(" ", "")
                permalink = str(comment.get("permalink") or "").strip()

                if not username and not text:
                    continue

                if not text:
                    continue

                if my_username and username == my_username:
                    continue

                if not profile_href:
                    continue

                dedupe_key = permalink or f"{profile_href}|{self._normalize_text(text)}"
                if dedupe_key in seen_keys:
                    continue

                seen_keys.add(dedupe_key)
                candidates.append(comment)

            except Exception as e:
                self.log.warning("Error filtrando comentario candidato: %r", e)
                continue

        return candidates

    def _decide_comment_action(self, comment: dict) -> str:
        has_reply_button = bool(comment.get("has_reply_button"))

        if not has_reply_button:
            return "like_only"

        roll = random.random()

        if roll < 0.80:
            return "like_reply"

        return "like_only"

    def _process_comment_action(
        self,
        *,
        comment: dict,
        action: str,
        post_context,
        result: OwnPostsInteractionResult,
    ) -> bool:
        fresh_comment = self._find_visible_comment_again(comment) or comment

        like_ok = self._click_like_on_comment(fresh_comment)
        if like_ok:
            result["likes_comentarios_ok"] += 1
        else:
            result["likes_comentarios_fail"] += 1

        if action == "like_only":
            return like_ok

        if action == "like_reply" and not fresh_comment.get("has_reply_button"):
            return like_ok

        if action == "like_reply":
            reply_ok = self._reply_to_comment_on_current_post(
                original_comment=fresh_comment,
                post_context=post_context,
            )

            if reply_ok:
                result["replies_ok"] += 1
                return True

            result["replies_fail"] += 1
            return like_ok

        return like_ok

    def _click_like_on_comment(self, comment: dict) -> bool:
        try:
            comment_el = comment.get("element")
            if comment_el is None:
                return False

            try:
                self.browser.driver.execute_script(
                    InstagramProfileLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    comment_el,
                )
            except Exception:
                pass

            result = self.browser.driver.execute_script(
                InstagramProfileLocators.CLICK_LIKE_ON_COMMENT_SCRIPT,
                comment_el,
            )

            self.log.info("[own-posts] resultado like comentario: %s", result)

            return bool(result and result.get("ok"))

        except Exception as e:
            self.log.warning("Error dando like al comentario: %r", e)
            return False

    def _reply_to_comment_on_current_post(
        self,
        *,
        original_comment: dict,
        post_context,
    ) -> bool:
        try:
            fresh_comment = self._find_visible_comment_again(original_comment) or original_comment

            if not fresh_comment.get("has_reply_button"):
                self.log.info("Comentario sin botón reply visible.")
                return False

            if not self._click_reply_on_comment(fresh_comment):
                self.log.warning("No se pudo pulsar reply sobre el comentario.")
                return False

            reply_text = self._build_contextual_reply_for_comment(
                comment_text=fresh_comment.get("text") or "",
                post_context=post_context,
            )

            if not reply_text:
                self.log.warning("No se pudo construir reply para comentario.")
                return False

            self.log.info("Reply generado: %s", reply_text)
            return self._submit_reply_text(reply_text)

        except Exception as e:
            self.log.warning("Error respondiendo comentario del post propio: %r", e)
            return False

    def _click_reply_on_comment(self, comment: dict) -> bool:
        try:
            comment_el = comment.get("element")
            if comment_el is None:
                return False

            try:
                self.browser.driver.execute_script(
                    InstagramProfileLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    comment_el,
                )
            except Exception:
                pass

            self.browser.time_sleep(random.uniform(0.8, 1.4))

            reply_buttons = comment_el.find_elements(
                By.XPATH,
                InstagramProfileLocators.REPLY_BUTTON_REL_XPATH,
            )

            visible_buttons = []
            for btn in reply_buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        visible_buttons.append(btn)
                except Exception:
                    continue

            self.log.info("[own-posts] botones reply visibles en comentario: %s", len(visible_buttons))

            if not visible_buttons:
                return False

            reply_btn = visible_buttons[0]

            try:
                reply_btn.click()
                self.browser.time_sleep(2)
                return True
            except Exception:
                pass

            try:
                ActionChains(self.browser.driver).move_to_element(reply_btn).pause(
                    random.uniform(0.2, 0.5)
                ).click().perform()
                self.browser.time_sleep(2)
                return True
            except Exception:
                pass

            try:
                self.browser.driver.execute_script(
                    InstagramProfileLocators.CLICK_ELEMENT_SCRIPT,
                    reply_btn,
                )
                self.browser.time_sleep(2)
                return True
            except Exception:
                pass

            return False

        except Exception as e:
            self.log.warning("Error haciendo click en reply: %r", e)
            return False

    def _get_reply_input_box(self):
        for xpath in InstagramProfileLocators.REPLY_INPUT_BOXES:
            try:
                elems = self.browser.driver.find_elements(By.XPATH, xpath)
                for el in elems:
                    try:
                        if el.is_displayed() and el.is_enabled():
                            return el
                    except Exception:
                        continue
            except Exception:
                continue

        return None

    def _submit_reply_text(self, reply_text: str) -> bool:
        try:
            input_box = self._get_reply_input_box()
            if input_box is None:
                self.log.warning("No se encontró input box para reply.")
                return False

            try:
                self.browser.driver.execute_script(
                    InstagramProfileLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    input_box,
                )
            except Exception:
                pass

            self.browser.time_sleep(1)

            try:
                input_box.click()
            except Exception:
                pass

            self.browser.time_sleep(1)

            wrote_ok = self._write_reply_with_emojis_js(input_box, reply_text)
            if not wrote_ok:
                self.log.warning("No se pudo insertar el texto del reply con JS.")
                return False

            self.browser.time_sleep(2)

            for attempt in range(1, 6):
                btn = self._get_reply_publish_button(input_box)

                if btn is None:
                    self.log.warning("No se encontró botón publicar del reply. intento=%s", attempt)
                    self.browser.time_sleep(1)
                    continue

                try:
                    aria_disabled = (btn.get_attribute("aria-disabled") or "").strip().lower()
                except Exception:
                    aria_disabled = ""

                try:
                    btn_text = (btn.text or "").strip()
                except Exception:
                    btn_text = ""

                self.log.info(
                    "[own-posts] reply publish button intento=%s | text=%s | aria-disabled=%s",
                    attempt,
                    btn_text,
                    aria_disabled,
                )

                if aria_disabled == "true":
                    try:
                        self.browser.driver.execute_script(
                            InstagramProfileLocators.REDISPATCH_REPLY_INPUT_EVENTS_SCRIPT,
                            input_box,
                        )
                    except Exception:
                        pass

                    self.browser.time_sleep(1)
                    continue

                if self.profile_service.click_element_safely(btn):
                    self.browser.time_sleep(random.randint(2, 4))
                    self.log.info("Reply published successfully.")
                    return True

                self.browser.time_sleep(1)

            self.log.warning("No se pudo publicar el reply después de varios intentos.")
            return False

        except Exception as e:
            self.log.warning("Error enviando reply: %r", e)
            return False

    def _write_reply_with_emojis_js(self, input_box, reply_text: str) -> bool:
        try:
            if input_box is None:
                self.log.warning("Reply textarea was not found.")
                return False

            final_value = self.browser.driver.execute_script(
                InstagramProfileLocators.WRITE_REPLY_WITH_EMOJIS_SCRIPT,
                input_box,
                reply_text,
            )

            if final_value is None:
                self.log.warning("Reply insertion script did not return any value.")
                return False

            final_value = str(final_value).strip()
            expected_value = str(reply_text).strip()

            if final_value != expected_value:
                self.log.warning(
                    "Reply textarea mismatch. Expected=%s | Actual=%s",
                    expected_value,
                    final_value,
                )
                return False

            self.log.info("Reply text inserted successfully via JS.")
            return True

        except Exception as e:
            self.log.warning("Error while writing reply with JS: %r", e)
            return False

    def _get_reply_publish_button(self, input_box):
        try:
            return self.browser.driver.execute_script(
                InstagramProfileLocators.GET_REPLY_PUBLISH_BUTTON_SCRIPT,
                input_box,
            )
        except Exception as e:
            self.log.warning("Error finding reply publish button: %r", e)
            return None

    # =========================================================
    # AI REPLY
    # =========================================================

    def _build_contextual_reply_for_comment(
        self,
        *,
        comment_text: str,
        post_context,
    ) -> str:
        cleaned_comment = str(comment_text or "").strip()
        if not cleaned_comment:
            return self._build_contextual_reply_fallback(cleaned_comment, post_context)

        bot_personality_id = self._get_bot_personality_id()
        detected_language = self._detect_comment_language(cleaned_comment)
        post_context_text = self._truncate_for_prompt(post_context, max_len=1800)

        if not bot_personality_id or not self.ai_api:
            return self._build_contextual_reply_fallback(cleaned_comment, post_context)

        user_prompt = f"""
You are replying to a comment on your OWN Instagram post.

CONTEXT:
- ORIGINAL_COMMENT = {cleaned_comment}
- DETECTED_LANGUAGE = {detected_language}
- POST_CONTEXT = {post_context_text}

GOAL:
Write ONE short natural reply to the user's comment.
The reply must fit the post context and the comment tone.

STRICT RULES:
- Reply in the same language as the original comment when possible.
- Sound human, warm, casual, and natural.
- Maximum 14 words.
- Single line only.
- No hashtags.
- No quotation marks.
- No robotic or overly salesy tone.
- Do not over-explain.
- If the comment is positive, acknowledge it naturally.
- If the comment sounds emotional or appreciative, answer warmly.
- Keep it realistic for Instagram.
- Avoid repeating the exact wording from the user's comment.
- Do not ask for a sale.
- Emojis are optional, use at most one, and only if natural.

Return ONLY one valid JSON object with this exact structure:
{{
  "reply_text": "your reply here"
}}
""".strip()

        try:
            ok_ai, raw_response = self.ai_api.get_bot_ia(
                bot_personality_id,
                user_prompt,
            )

            if not ok_ai or not raw_response:
                return self._build_contextual_reply_fallback(cleaned_comment, post_context)

            parsed = self._extract_reply_json(raw_response)
            if not parsed:
                return self._build_contextual_reply_fallback(cleaned_comment, post_context)

            reply_text = str(parsed.get("reply_text") or "").strip()
            if not reply_text:
                return self._build_contextual_reply_fallback(cleaned_comment, post_context)

            return reply_text

        except Exception as e:
            self.log.warning("Error construyendo reply con IA: %r", e)
            return self._build_contextual_reply_fallback(cleaned_comment, post_context)

    def _build_contextual_reply_fallback(
        self,
        comment_text: str,
        post_context,
    ) -> str:
        lang = self._detect_comment_language(comment_text)
        text_norm = self._normalize_text(comment_text)

        if lang == "en":
            if "thank" in text_norm:
                return random.choice([
                    "Thanks a lot 😊",
                    "Thanks, really appreciate it",
                    "Thank you so much",
                ])

            if "love" in text_norm or "great" in text_norm or "amazing" in text_norm:
                return random.choice([
                    "Thank you, glad you liked it",
                    "Really appreciate that",
                    "So glad you liked it",
                ])

            return random.choice([
                "Thanks for stopping by",
                "Really appreciate your comment",
                "Glad you enjoyed it",
            ])

        if "gracias" in text_norm:
            return random.choice([
                "Gracias a ti 😊",
                "Muchas gracias de verdad",
                "Gracias por pasarte",
            ])

        if "encanta" in text_norm or "bonito" in text_norm or "hermoso" in text_norm:
            return random.choice([
                "Gracias, qué bueno que te gustó",
                "Me alegra mucho que te gustara",
                "Gracias, me alegra leer eso",
            ])

        return random.choice([
            "Gracias por comentar 😊",
            "Muchas gracias por pasarte",
            "Qué bueno leerte por aquí",
        ])

    # =========================================================
    # TEXT / DATA HELPERS
    # =========================================================

    def _get_social_media_account(self) -> dict:
        return self.data.get("social_media_account") or {}

    def _get_bot_personality(self) -> dict:
        social_media_account = self._get_social_media_account()
        return social_media_account.get("bot_personality") or {}

    def _get_bot_personality_id(self) -> Optional[int]:
        try:
            bot_personality = self._get_bot_personality()
            value = bot_personality.get("id")
            return int(value) if value is not None else None
        except Exception:
            return None

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

    def _detect_comment_language(self, text: str) -> str:
        text_norm = self._normalize_text(text)

        english_markers = [
            "thanks",
            "love it",
            "looks great",
            "amazing",
            "beautiful",
            "nice",
            "so good",
            "great post",
            "awesome",
        ]

        spanish_markers = [
            "gracias",
            "me encanta",
            "qué lindo",
            "que lindo",
            "hermoso",
            "bonito",
            "se ve bien",
            "muy bueno",
            "buen post",
        ]

        if any(marker in text_norm for marker in english_markers):
            return "en"

        if any(marker in text_norm for marker in spanish_markers):
            return "es"

        return self._get_bot_language()

    def _extract_reply_json(self, raw_response) -> Optional[dict]:
        try:
            content = raw_response

            if isinstance(content, dict) and "response" in content:
                content = content["response"]

            if isinstance(content, dict):
                parsed = content
            else:
                text = str(content or "").strip()
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "").strip()

                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    text = text[start:end + 1]

                parsed = json.loads(text)

            if not isinstance(parsed, dict):
                return None

            reply_text = str(parsed.get("reply_text") or "").strip()
            if not reply_text:
                return None

            parsed["reply_text"] = reply_text
            return parsed

        except Exception as e:
            self.log.warning("No se pudo parsear JSON del reply: %r", e)
            return None

    def _get_my_instagram_username(self) -> str:
        try:
            social_media_account = self.data.get("social_media_account") or {}

            username = str(
                social_media_account.get("username") or ""
            ).strip().lower().replace("@", "")

            if username:
                return username

            username = str(
                (social_media_account.get("other_credentials") or {}).get("User") or ""
            ).strip().lower().replace("@", "")

            if username:
                return username

            return ""

        except Exception:
            return ""

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""

        text = text.lower().strip()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"\s+", " ", text)
        return text

    def _safe_json_for_log(self, value) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, default=str)[:1200]
        except Exception:
            return str(value)[:1200]

    def _truncate_for_prompt(self, value, max_len: int = 1800) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)

        text = text.strip()
        if len(text) <= max_len:
            return text

        return text[:max_len] + "..."