import random
import time
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from app.config.locators.instagram_followback_locators import (
    InstagramFollowbackLocators,
)
from app.utils.instagram_url import _normalize_instagram_href

from app.services.instagram_hashtag_navigation_guard import (
    canonical_hashtag_href,
    extract_hashtag_slug_from_href,
    hashtag_href_matches_slug,
    normalize_hashtag_slug,
)


class InstagramFollowbackNavigationMixin:
    def _raw_driver(self):
        """Use raw Selenium for known Instagram navigation locators.
        Self-healing must not invent a different element when a known selector
        is temporarily unavailable.
        """
        driver = getattr(self.browser, "driver", None)
        return getattr(driver, "raw", driver)

    def _element_is_pointer_interactable(self, element) -> bool:
        try:
            driver = self._raw_driver()
            return bool(driver.execute_script(
                """
                const el = arguments[0];
                if (!el || !el.isConnected) return false;
                const r = el.getBoundingClientRect();
                if (!r.width || !r.height) return false;
                const s = getComputedStyle(el);
                if (s.display === 'none' || s.visibility === 'hidden' ||
                    s.pointerEvents === 'none' || Number(s.opacity) === 0) return false;
                const x = Math.min(Math.max(r.left + r.width / 2, 1), window.innerWidth - 1);
                const y = Math.min(Math.max(r.top + r.height / 2, 1), window.innerHeight - 1);
                const top = document.elementFromPoint(x, y);
                return !!top && (top === el || el.contains(top));
                """,
                element,
            ))
        except Exception:
            return False

    def _dismiss_transient_overlays_for_search(self) -> bool:
        """Return the browser to a Search-safe state before resolving Search.

        Instagram can leave a post surface/modal on top of the navigation rail.
        In that state Search may exist in the DOM but is not pointer-interactable.
        We therefore close the post deterministically (ESC/accessible close button)
        and, if Instagram keeps us on a post URL, use the canonical home navigation
        as a last-resort state reset. No coordinate clicks are used.
        """
        driver = self._raw_driver()
        try:
            current_url = str(getattr(driver, "current_url", "") or "").lower().rstrip("/")
        except Exception:
            current_url = ""

        post_surface = any(part in current_url for part in ("/p/", "/reel/", "/reels/", "/tv/"))
        close_xpath = getattr(InstagramFollowbackLocators, "CLOSE_POST_BUTTON", "")

        # First close with ESC. This is the least invasive action for both
        # full-page posts and modal posts.
        for _ in range(2):
            try:
                dialogs = driver.find_elements(By.XPATH, "//*[@role='dialog']")
                has_dialog = any(
                    bool(d.is_displayed()) for d in dialogs
                    if self._safe_bool(lambda: d.is_displayed())
                )
            except Exception:
                has_dialog = False

            if post_surface or has_dialog:
                try:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    self.browser.time_sleep(0.6)
                except Exception:
                    pass

                try:
                    current_url = str(getattr(driver, "current_url", "") or "").lower().rstrip("/")
                except Exception:
                    current_url = ""
                post_surface = any(part in current_url for part in ("/p/", "/reel/", "/reels/", "/tv/"))
                if not post_surface and not has_dialog:
                    break

        # If the modal remains, use only the known accessible close control.
        if close_xpath:
            try:
                for btn in driver.find_elements(By.XPATH, close_xpath):
                    if not btn.is_displayed():
                        continue
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    self.browser.time_sleep(0.7)
                    break
            except Exception as exc:
                self.log.debug("[search-ui] cierre accesible de post falló: %r", exc)

        try:
            current_url = str(getattr(driver, "current_url", "") or "").lower().rstrip("/")
        except Exception:
            current_url = ""

        post_surface = any(part in current_url for part in ("/p/", "/reel/", "/reels/", "/tv/"))

        # A post can remain as the top-level URL even after ESC. Going home is a
        # deterministic recovery: it removes the post surface instead of trying
        # to click Search through an overlay.
        if post_surface:
            try:
                self.browser.go_to_url("https://www.instagram.com/")
                self.browser.time_sleep(1.5)
                current_url = str(getattr(driver, "current_url", "") or "").lower().rstrip("/")
                post_surface = any(part in current_url for part in ("/p/", "/reel/", "/reels/", "/tv/"))
                if not post_surface:
                    self.log.info("[search-ui] estado post reiniciado navegando a Instagram Home")
            except Exception as exc:
                self.log.warning("[search-ui] no se pudo reiniciar estado post -> Home: %r", exc)

        try:
            remaining_dialog = any(
                bool(d.is_displayed())
                for d in driver.find_elements(By.XPATH, "//*[@role='dialog']")
                if self._safe_bool(lambda d=d: d.is_displayed())
            )
        except Exception:
            remaining_dialog = False

        return not post_surface and not remaining_dialog

    @staticmethod
    def _safe_bool(fn):
        try:
            return bool(fn())
        except Exception:
            return False

    def _resolve_search_control(self):
        """Resolve the real search navigation control from the live DOM.

        We do not rely on one SVG selector and never ask the self-healer to
        invent a target. The JS resolver returns the actual accessible control
        (button/link/labelled element), after which Selenium verifies that it is
        topmost and pointer-interactable.
        """
        driver = self._raw_driver()
        try:
            element = driver.execute_script(
                InstagramFollowbackLocators.SEARCH_NAV_JS
            )
            if element is not None:
                return element
        except Exception as exc:
            self.log.debug("[search-ui] JS resolver falló: %r", exc)

        try:
            icons = driver.find_elements(
                By.CSS_SELECTOR,
                InstagramFollowbackLocators.SEARCH_ICON_CSS,
            )
        except Exception:
            icons = []

        for icon in icons:
            try:
                candidate = self._find_search_clickable_ancestor(icon)
                if candidate is not None:
                    return candidate
            except Exception:
                continue
        return None

    def _open_search_button(self) -> bool:
        """Open Search using a live, validated control; recover instead of cascading."""
        try:
            if self._dismiss_transient_overlays_for_search() is False:
                self.log.warning("[search-ui] no se pudo limpiar completamente el estado anterior antes de Search")
                return False

            # Instagram can take a few seconds to hydrate the sidebar after the
            # session becomes ready. Re-resolve on every attempt.
            for attempt in range(1, 9):
                clickable = self._resolve_search_control()
                print(
                    f"[followback] intento resolver búsqueda {attempt}/8 | "
                    f"encontrado={clickable is not None}"
                )

                if clickable is None:
                    self.browser.time_sleep(0.75)
                    continue

                if not self._element_is_pointer_interactable(clickable):
                    self.log.info(
                        "[search-ui] control de búsqueda encontrado pero cubierto/no interactuable | intento=%s/8",
                        attempt,
                    )
                    # The control can exist underneath a post surface. Re-run the
                    # state reset instead of waiting for an overlay to disappear
                    # by chance.
                    self._dismiss_transient_overlays_for_search()
                    self.browser.time_sleep(0.4)
                    continue

                try:
                    clickable.click()
                except Exception as exc:
                    self.log.info("[search-ui] click normal falló: %r", exc)
                    # Re-resolve before any alternative input activation.
                    clickable = self._resolve_search_control()
                    if clickable is None or not self._element_is_pointer_interactable(clickable):
                        self.browser.time_sleep(0.75)
                        continue
                    try:
                        clickable.send_keys(Keys.ENTER)
                    except Exception:
                        self.browser.time_sleep(0.75)
                        continue

                # Search panel/input must really exist before success.
                for _ in range(6):
                    if self._search_opened():
                        print("[followback] búsqueda abierta y input confirmado")
                        return True
                    self.browser.time_sleep(0.5)

            self.log.error("[search-ui] no se pudo abrir búsqueda tras resolver DOM + reintentos")
            return False

        except Exception as e:
            self.log.error("[search-ui] error abriendo búsqueda: %r", e)
            return False

    def _find_search_clickable_ancestor(self, icon):
        for rel_xpath in InstagramFollowbackLocators.SEARCH_CLICKABLE_ANCESTORS:
            try:
                candidate = icon.find_element(By.XPATH, rel_xpath)
                if candidate:
                    print(f"[followback] clickable encontrado con: {rel_xpath}")
                    return candidate
            except Exception:
                continue

        return None

    def _get_visible_search_inputs(self):
        """Obtiene el input real del buscador sin depender de un XPath frágil.

        Instagram puede reemplazar el input del overlay mientras se abre. Por eso
        primero usamos CSS directo y, si el DOM cambió, reintentamos varias veces.
        Esta ruta deliberadamente evita el Self-Healer para un locator conocido.
        """
        driver = self._raw_driver()
        loc = InstagramFollowbackLocators

        for css in loc.SEARCH_INPUT_FALLBACK_CSS:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, css)
            except Exception:
                elements = []
            visible = []
            for el in elements:
                try:
                    if el.is_displayed() and el.is_enabled():
                        visible.append(el)
                except Exception:
                    continue
            if visible:
                return visible
        return []

    def _search_opened(self) -> bool:
        try:
            found = self._get_visible_search_inputs()
            print(f"[followback] inputs búsqueda encontrados: {len(found)}")
            return bool(found)
        except Exception:
            return False

    def _type_search_term(self) -> bool:
        term = str(self._get_search_term() or "").strip()
        if not term:
            self.log.warning("Término de búsqueda vacío.")
            return False

        self.log.info("Escribiendo término de búsqueda: %s", term)
        last_error = None

        # El overlay de Instagram puede reconstruir el input varias veces.
        for attempt in range(1, 6):
            try:
                inputs = self._get_visible_search_inputs()
                print(f"[followback] intento escribir {attempt}/5 - inputs visibles: {len(inputs)}")

                if not inputs:
                    self.browser.time_sleep(0.7)
                    continue

                search_input = inputs[0]

                try:
                    self._raw_driver().execute_script(
                        "arguments[0].scrollIntoView({block:'center',inline:'center'}); arguments[0].focus();",
                        search_input,
                    )
                except Exception:
                    pass

                self.browser.time_sleep(0.3)

                if not self._element_is_pointer_interactable(search_input):
                    last_error = RuntimeError("search input visible pero cubierto/no interactuable")
                    self.log.warning(
                        "[search-ui] input visible pero no interactuable | intento=%s/5",
                        attempt,
                    )
                    self.browser.time_sleep(0.7)
                    continue

                try:
                    search_input.click()
                except Exception as exc:
                    last_error = exc
                    self.browser.time_sleep(0.5)
                    continue

                # Limpiar y escribir usando el WebElement ya resuelto.
                search_input.send_keys(Keys.CONTROL, "a")
                search_input.send_keys(Keys.BACKSPACE)
                for ch in term:
                    search_input.send_keys(ch)
                    time.sleep(random.uniform(0.025, 0.06))

                self.browser.time_sleep(1.2)

                # Verificación: el valor debe contener el término.
                value = (search_input.get_attribute("value") or "").strip()
                if value and term.lower() in value.lower():
                    self.log.info("Término de búsqueda escrito correctamente: %s", value)
                    return True

                # React/Instagram puede no exponer value de forma normal;
                # si el input sigue visible y el texto produjo resultados, también vale.
                if self._has_search_results_now():
                    self.log.info("Término escrito; Instagram ya mostró resultados.")
                    return True

                last_error = RuntimeError(
                    f"El input no confirmó el término (value={value!r})"
                )
            except Exception as e:
                last_error = e
                self.log.warning(
                    "Intento %s/5 para escribir búsqueda falló: %r", attempt, e
                )
                self.browser.time_sleep(0.7)

        self.log.warning("No se pudo escribir el término de búsqueda: %s | error=%r", term, last_error)
        return False

    def _has_search_results_now(self) -> bool:
        try:
            results = self._raw_driver().find_elements(
                By.XPATH, InstagramFollowbackLocators.HASHTAG_SEARCH_RESULTS
            )
            return any(
                (lambda e: bool(e.is_displayed()))(el)
                for el in results
            )
        except Exception:
            return False

    def _collect_hashtag_result_hrefs(self) -> list[str]:
        """Recolecta únicamente el hashtag solicitado; nunca acepta un hashtag ajeno.

        El DOM de Instagram puede contener enlaces de hashtags de recomendaciones,
        contenido previamente renderizado o elementos fuera del overlay de búsqueda.
        Por eso NO usamos el primer ``/explore/tags/`` encontrado como destino.
        El destino debe coincidir exactamente con el slug del término solicitado.
        """
        try:
            requested_term = str(self._get_search_term() or "").strip()
            requested_slug = self._normalize_hashtag_slug(requested_term)
            if not requested_slug:
                self.log.warning("[hashtag-validation] término solicitado vacío; no se navega.")
                return []

            result_xpath = InstagramFollowbackLocators.HASHTAG_SEARCH_RESULTS

            for attempt in range(1, 9):
                self.browser.time_sleep(1)
                results = self._raw_driver().find_elements(By.XPATH, result_xpath)
                print(
                    f"[followback] intento {attempt}/8 - resultados hashtag encontrados: "
                    f"{len(results)} | solicitado=#{requested_slug}"
                )

                exact_hrefs: list[str] = []
                seen = set()

                for el in results:
                    try:
                        href = (el.get_attribute("href") or "").strip()
                        if not href or not self._is_hashtag_result_href(href):
                            continue
                        if not el.is_displayed() or not el.is_enabled():
                            continue
                        if not self._hashtag_href_matches_slug(href, requested_slug):
                            continue

                        canonical = self._canonical_hashtag_href(href)
                        if canonical and canonical not in seen:
                            seen.add(canonical)
                            exact_hrefs.append(canonical)
                    except Exception:
                        continue

                if exact_hrefs:
                    print(f"[followback] hashtag exacto validado: {exact_hrefs}")
                    return exact_hrefs

            self.log.warning(
                "[hashtag-validation] NO se encontró coincidencia exacta para #%s; "
                "se descartan todos los enlaces ajenos.",
                requested_slug,
            )
            return []

        except Exception as e:
            self.log.warning("Error recolectando resultados del hashtag: %r", e)
            return []

    @staticmethod
    def _normalize_hashtag_slug(value: str) -> str:
        return normalize_hashtag_slug(value)

    @staticmethod
    def _extract_hashtag_slug_from_href(href: str) -> str:
        return extract_hashtag_slug_from_href(href)

    @classmethod
    def _hashtag_href_matches_slug(cls, href: str, requested_slug: str) -> bool:
        return hashtag_href_matches_slug(href, requested_slug)

    @classmethod
    def _canonical_hashtag_href(cls, href: str) -> str:
        return canonical_hashtag_href(href)

    def _is_hashtag_result_href(self, href: str) -> bool:
        try:
            return bool(self._extract_hashtag_slug_from_href(href))
        except Exception:
            return False

    def _open_hashtag_result_by_href(self, href: str) -> bool:
        try:
            if not href:
                return False

            self.browser.driver.get(href)
            self.browser.time_sleep(4)

            visible_posts = self._get_visible_hashtag_grid_posts()

            print(f"[followback] posts visibles al abrir resultado: {len(visible_posts)}")
            return bool(visible_posts)

        except Exception as e:
            self.log.warning("Error abriendo resultado por href: %r", e)
            return False

    def _get_visible_hashtag_grid_posts(self) -> list:
        try:
            posts = self.browser.driver.find_elements(
                By.XPATH,
                InstagramFollowbackLocators.HASHTAG_GRID_POSTS,
            )

            visible_posts = []

            for post in posts:
                try:
                    if post.is_displayed():
                        visible_posts.append(post)
                except Exception:
                    continue

            return visible_posts

        except Exception:
            return []

    def _open_next_post_from_hashtag_grid(self, excluded_hrefs=None) -> Optional[str]:
        try:
            excluded_hrefs = excluded_hrefs or set()
            post_xpath = InstagramFollowbackLocators.HASHTAG_GRID_POSTS

            candidate_posts = []

            for attempt in range(1, 9):
                self.browser.time_sleep(1)

                posts = self.browser.driver.find_elements(By.XPATH, post_xpath)
                print(f"[followback] intento {attempt}/8 - posts encontrados en grid: {len(posts)}")

                unique_by_href = {}

                for el in posts:
                    try:
                        href = (el.get_attribute("href") or "").strip()

                        if not href:
                            continue

                        if not self._is_valid_hashtag_grid_post_href(href):
                            continue

                        if href in excluded_hrefs:
                            continue

                        if not el.is_displayed() or not el.is_enabled():
                            continue

                        unique_by_href[href] = el

                    except Exception:
                        continue

                candidate_posts = list(unique_by_href.items())

                print(
                    f"[followback] intento {attempt}/8 - "
                    f"posts válidos únicos no repetidos: {len(candidate_posts)}"
                )

                if candidate_posts:
                    break

            if not candidate_posts:
                self.log.warning("No se encontraron publicaciones válidas en el grid.")
                return None

            for idx, (href, post) in enumerate(candidate_posts, start=1):
                try:
                    print(f"[followback] probando post #{idx}: {href}")

                    try:
                        self.browser.driver.execute_script(
                            InstagramFollowbackLocators.SCROLL_GRID_POST_CENTER_SCRIPT,
                            post,
                        )
                    except Exception:
                        pass

                    self.browser.time_sleep(1)

                    # Do not use WebElement.click() here. A stale/overlay-blocked
                    # Selenium click can leave ChromeDriver waiting indefinitely.
                    # We already have the canonical href, so navigate directly;
                    # Browser.go_to_url applies the global page-load/script timeout.
                    self.log.info(
                        "[followback] abriendo candidato por href directo | href=%s",
                        href,
                    )
                    try:
                        self.browser.go_to_url(href)
                    except Exception as nav_exc:
                        self.log.warning(
                            "[followback] navegación directa falló | href=%s | error=%r",
                            href, nav_exc,
                        )
                        continue

                    self.browser.time_sleep(3)
                    current = _normalize_instagram_href(
                        str(self.browser.driver.current_url or "").strip()
                    )
                    if current == href:
                        return href

                    self.log.warning(
                        "[followback] candidato no confirmó URL | expected=%s | current=%s",
                        href, current,
                    )

                except Exception:
                    continue

            return None

        except Exception as e:
            self.log.warning("Error abriendo siguiente publicación del grid: %r", e)
            return None

    def _is_valid_hashtag_grid_post_href(self, href: str) -> bool:
        """Accept only canonical Instagram post/reel URLs from the grid.

        Nested routes such as ``/liked_by/`` and ``/comments/`` are not posts
        and must never enter the direct-navigation loop.
        """
        try:
            raw = str(href or "").strip()
            if not raw:
                return False

            from urllib.parse import urlparse
            if raw.startswith("/"):
                raw = f"https://www.instagram.com{raw}"
            parsed_raw = urlparse(raw)
            raw_host = (parsed_raw.netloc or "www.instagram.com").lower()
            if raw_host not in {"instagram.com", "www.instagram.com"} and not raw_host.endswith(".instagram.com"):
                return False

            path = parsed_raw.path.rstrip("/")
            parts = [part for part in path.split("/") if part]

            return (
                len(parts) == 2
                and parts[0].lower() in {"p", "reel"}
                and bool(parts[1])
            )

        except Exception:
            return False

    def _click_grid_post(self, post) -> bool:
        try:
            try:
                post.click()
                return True
            except Exception:
                pass

            try:
                ActionChains(self.browser.driver).move_to_element(post).pause(0.3).click().perform()
                return True
            except Exception:
                pass

            try:
                post.send_keys(Keys.ENTER)
                return True
            except Exception:
                pass

            try:
                self.browser.driver.execute_script(
                    InstagramFollowbackLocators.CLICK_ELEMENT_SCRIPT,
                    post,
                )
                return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    def _reopen_post_for_reply(self, post_href: str, max_attempts: int = 3) -> bool:
        try:
            if not post_href:
                return False

            for attempt in range(1, max_attempts + 1):
                try:
                    print(
                        f"[followback] reabriendo publicación para reply "
                        f"{attempt}/{max_attempts}: {post_href}"
                    )

                    self.browser.driver.get(post_href)
                    self.browser.time_sleep(4)

                    comments = self._get_visible_comments()

                    if comments:
                        print(
                            "[followback] publicación reabierta correctamente "
                            f"con {len(comments)} comentarios visibles"
                        )
                        return True

                    self.browser.time_sleep(2)

                except Exception as e:
                    print(f"[followback] fallo reabriendo publicación: {e}")
                    self.browser.time_sleep(2)

            print("[followback] no se pudo reabrir la publicación con comentarios visibles")
            return False

        except Exception as e:
            print(f"[followback] error en _reopen_post_for_reply: {e}")
            return False

    def _return_to_result_grid(self, result_href: str) -> bool:
        try:
            if not result_href:
                return False

            self.browser.driver.get(result_href)
            self.browser.time_sleep(4)

            visible_posts = self._get_visible_hashtag_grid_posts()

            print(f"[followback] posts visibles al volver al resultado: {len(visible_posts)}")
            return bool(visible_posts)

        except Exception as e:
            self.log.warning("Error volviendo al resultado del hashtag: %r", e)
            return False

    def _is_profile_page_open(self, expected_href: str = "") -> bool:
        try:
            current_url = (self.browser.driver.current_url or "").strip().lower()

            if expected_href:
                expected_href = expected_href.strip().lower().rstrip("/")

                if current_url.rstrip("/").startswith(expected_href):
                    return True

            if self._is_blocking_profile_url(current_url):
                return False

            header_candidates = self.browser.driver.find_elements(
                By.XPATH,
                InstagramFollowbackLocators.PROFILE_HEADER,
            )

            return bool(header_candidates)

        except Exception:
            return False

    def _is_blocking_profile_url(self, current_url: str) -> bool:
        try:
            current_url = str(current_url or "").strip().lower()

            return any(
                part in current_url
                for part in InstagramFollowbackLocators.PROFILE_BLOCKING_URL_PARTS
            )

        except Exception:
            return False