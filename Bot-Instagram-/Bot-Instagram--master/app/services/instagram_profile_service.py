import os
import random
import time
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from app.config.locators.instagram_profile_locators import InstagramProfileLocators
from app.utils.instagram_url import _normalize_instagram_href, _extract_username_from_url


class InstagramRateLimitError(RuntimeError):
    """Instagram respondió con una página de rate limit (HTTP 429)."""



class InstagramProfileService:
    """
    Servicio centralizado para operaciones de perfil/post abierto.

    Evita que las tareas tengan:
    - XPaths de posts de perfil
    - JS para leer captions/textos
    - JS para detectar autor
    - scrolls directos para recolectar publicaciones

    No publica.
    No comenta.
    No da like.
    Solo lee/navega/recolecta contexto de perfil/post.
    """

    def __init__(self, browser, logger=None):
        self.browser = browser
        self.log = logger

    def _raw_driver(self):
        """Return the real Selenium driver, bypassing the optional self-healer."""
        driver = getattr(self.browser, "driver", None)
        return getattr(driver, "raw", driver)

    @staticmethod
    def _canonical_profile_username(value: str) -> str:
        return str(value or "").strip().lower().lstrip("@").rstrip("/")

    def _is_expected_profile_page(self, profile_url: str, expected_username: str = "") -> bool:
        """Fail closed if the browser is not actually on the requested profile."""
        try:
            current = _normalize_instagram_href(
                str(self._raw_driver().current_url or "").strip()
            )
            expected = _normalize_instagram_href(str(profile_url or "").strip())
            if not current or not expected:
                return False

            current_username = self._canonical_profile_username(
                _extract_username_from_url(current)
            )
            expected_username = self._canonical_profile_username(
                expected_username or _extract_username_from_url(expected)
            )
            # For profile pages, username is the stable identity. Browser URLs
            # can differ in harmless canonicalization details (trailing slash,
            # query/fragment, host form) even after normalization.
            # Never accept a post/explore URL merely because it contains the name.
            # Work from the parsed URL path. Splitting the full URL on
            # ``instagram.com`` counts both the leading and trailing slash
            # (``/username/`` -> 2), which caused valid profile pages to be
            # rejected even when expected/current URLs were identical.
            from urllib.parse import urlsplit
            current_path = urlsplit(current).path.strip("/")
            expected_path = urlsplit(expected).path.strip("/")
            current_is_profile = bool(
                current_path
                and "/" not in current_path
                and current_username == current_path.lower()
            )
            expected_is_profile = bool(
                expected_path
                and "/" not in expected_path
                and expected_username == expected_path.lower()
            )
            ok = bool(
                current_username
                and expected_username
                and current_username == expected_username
                and current_is_profile
                and expected_is_profile
            )
            if not ok:
                self._warning(
                    "[profile-integrity] profile URL mismatch | expected=%r | current=%r | expected_user=%r | current_user=%r",
                    expected, current, expected_username, current_username,
                )
            return ok
        except Exception:
            return False

    def recover_from_post_surface(self, expected_profile_url: str = "") -> bool:
        """Clear an unexpected post/modal state without coordinate or heuristic clicks."""
        try:
            driver = self._raw_driver()
            body = driver.find_element(By.TAG_NAME, "body")
            try:
                body.send_keys(Keys.ESCAPE)
                self.sleep(0.4)
            except Exception:
                pass

            # A recovery is considered successful only when the caller's next
            # navigation can start from a known state. We never click arbitrary
            # screen coordinates or ask the self-healer to invent a close target.
            if expected_profile_url:
                current = _normalize_instagram_href(
                    str(driver.current_url or "").strip()
                )
                if current and not self.is_post_url(current):
                    return self._is_expected_profile_page(expected_profile_url)
            return True
        except Exception as exc:
            self._warning("[profile-recovery] estado post no pudo limpiarse | error=%r", exc)
            return False

    def _is_valid_post_context_url(self, url: str) -> bool:
        normalized = _normalize_instagram_href(url)
        return bool(normalized and self.is_post_url(normalized) and "chrome-error" not in normalized.lower())

    # =========================================================
    # PROFILE POSTS
    # =========================================================
    def collect_profile_post_urls(self, profile_url: str, limit: int = 8) -> list[str]:
        try:
            profile_url = str(profile_url or "").strip()

            if not profile_url:
                self._warning("[profile] profile_url vacío.")
                return []

            self.open_url(profile_url)
            self.sleep(random.uniform(3.0, 5.0))

            urls = []
            seen = set()
            scrolls_without_growth = 0
            last_count = 0

            while scrolls_without_growth < 3 and len(urls) < limit:
                elements = self.browser.driver.find_elements(
                    By.XPATH,
                    InstagramProfileLocators.PROFILE_POST_LINKS,
                )

                for element in elements:
                    try:
                        href = (element.get_attribute("href") or "").strip()

                        if not href:
                            continue

                        href = _normalize_instagram_href(href)

                        if not self.is_post_url(href):
                            continue

                        if href in seen:
                            continue

                        seen.add(href)
                        urls.append(href)

                        if len(urls) >= limit:
                            break

                    except Exception:
                        continue

                if len(urls) == last_count:
                    scrolls_without_growth += 1
                else:
                    scrolls_without_growth = 0
                    last_count = len(urls)

                if len(urls) >= limit:
                    break

                self.scroll_profile_grid()
                self.sleep(random.uniform(1.5, 2.5))

            self._info(
                "[profile] posts recolectados | profile=%s | count=%s | urls=%s",
                profile_url,
                len(urls),
                urls,
            )

            return urls[:limit]

        except Exception as e:
            self._warning(
                "[profile] error recolectando posts | profile=%s | error=%r",
                profile_url,
                e,
            )
            return []
    def collect_profile_grid_post_targets(
        self,
        profile_url: str,
        profile_username: str = "",
        limit: int = 8,
    ) -> list[str]:
        """
        Recolecta URLs de publicaciones visibles en el grid del perfil.

        Retorna una lista de URLs normalizadas:
        - /p/
        - /reel/
        - /tv/
        """
        try:
            profile_url = str(profile_url or "").strip()

            if not profile_url:
                self._warning("[profile] profile_url vacío.")
                return []

            expected_username = self._canonical_profile_username(
                profile_username or _extract_username_from_url(profile_url)
            )

            # Preflight: if the browser is already sitting on a different
            # profile, fail closed instead of navigating away and accidentally
            # treating the new page as proof that the previous context was safe.
            current_before = _normalize_instagram_href(
                str(getattr(self._raw_driver(), "current_url", "") or "").strip()
            )
            current_before_username = self._canonical_profile_username(
                _extract_username_from_url(current_before)
            )
            if current_before_username and current_before_username != expected_username:
                self._warning(
                    "[profile-integrity] BLOQUEADO preflight de perfil | expected=%s | current=%s",
                    profile_url,
                    current_before,
                )
                return []

            self.open_url(profile_url)
            self.sleep(random.uniform(3.0, 5.0))

            if not self._is_expected_profile_page(profile_url, expected_username):
                self._warning(
                    "[profile-integrity] BLOQUEADO grid en perfil incorrecto | expected=%s | current=%s",
                    profile_url,
                    getattr(self._raw_driver(), "current_url", ""),
                )
                return []

            urls = []
            seen = set()
            scrolls_without_growth = 0
            last_count = 0

            while scrolls_without_growth < 3 and len(urls) < limit:
                try:
                    raw_targets = self._raw_driver().execute_script(
                        InstagramProfileLocators.PROFILE_GRID_POST_TARGETS_SCRIPT,
                        profile_username,
                    )
                except Exception:
                    raw_targets = []

                for raw_url in raw_targets or []:
                    try:
                        href = _normalize_instagram_href(
                            str(raw_url or "").strip()
                        )

                        if not href or not self.is_post_url(href):
                            continue

                        if href in seen:
                            continue

                        seen.add(href)
                        urls.append(href)

                        if len(urls) >= limit:
                            break

                    except Exception:
                        continue

                if len(urls) == last_count:
                    scrolls_without_growth += 1
                else:
                    scrolls_without_growth = 0
                    last_count = len(urls)

                if len(urls) >= limit:
                    break

                self.scroll_profile_grid()
                self.sleep(random.uniform(1.5, 2.5))

            self._info(
                "[profile] grid targets recolectados | profile=%s | username=%s | count=%s",
                profile_url,
                profile_username,
                len(urls),
            )

            return urls[:limit]

        except Exception as e:
            self._warning(
                "[profile] error recolectando grid targets | profile=%s | error=%r",
                profile_url,
                e,
            )
            return []

    def extract_shortcode_from_post_url(self, post_url: str) -> str:
        """
        Extrae el shortcode de una URL de Instagram.

        Ejemplos:
        /p/ABC123/      -> ABC123
        /reel/ABC123/   -> ABC123
        /tv/ABC123/     -> ABC123
        """
        try:
            post_url = str(post_url or "").strip()

            if not post_url:
                return ""

            normalized = _normalize_instagram_href(post_url)

            parts = [
                part.strip()
                for part in normalized.split("/")
                if part.strip()
            ]

            if len(parts) < 2:
                return ""

            post_types = {"p", "reel", "reels", "tv"}

            for index, part in enumerate(parts[:-1]):
                if part.lower() in post_types:
                    return parts[index + 1]

            return ""

        except Exception:
            return ""

    def open_recent_post_from_profile_grid(
        self,
        profile_url: str,
        target_url: str,
        expected_author_username: str = "",
    ) -> bool:
        """Open a profile-grid target and verify URL + author ownership."""
        try:
            profile_url = str(profile_url or "").strip()
            target_url = _normalize_instagram_href(str(target_url or "").strip())
            expected_author = self._canonical_profile_username(expected_author_username)

            if not target_url or not self.is_post_url(target_url):
                return False

            # The grid was collected from this profile; verify that invariant
            # immediately before navigation too.
            self.open_url(target_url)
            self.sleep(random.uniform(2.5, 4.0))

            current_url = _normalize_instagram_href(
                str(self._raw_driver().current_url or "").strip()
            )
            if current_url != target_url:
                self._warning(
                    "[profile-integrity] BLOQUEADO URL post distinta | target=%s | current=%s",
                    target_url, current_url,
                )
                self.recover_from_post_surface()
                return False

            # Retry author extraction briefly because Instagram may hydrate the
            # post header after navigation. Unknown author is a hard failure.
            for attempt in range(1, 4):
                author = self.get_opened_post_author_username()
                if author:
                    if expected_author and author != expected_author:
                        self._warning(
                            "[profile-integrity] BLOQUEADO autor incorrecto | expected=%s | actual=%s | post=%s",
                            expected_author, author, target_url,
                        )
                        self.recover_from_post_surface()
                        return False
                    return True
                self.sleep(0.7)

            self._warning(
                "[profile-integrity] BLOQUEADO no se pudo determinar autor | post=%s",
                target_url,
            )
            self.recover_from_post_surface()
            return False

        except Exception as e:
            self._warning(
                "[profile] error abriendo recent post | profile=%s | target=%s | error=%r",
                profile_url, target_url, e,
            )
            try:
                self.recover_from_post_surface()
            except Exception:
                pass
            return False

    def extract_recent_post_context(
        self,
        expected_url: str = "",
        expected_author_username: str = "",
    ) -> dict:
        """Extract context only when current URL and author match expectations."""
        try:
            driver = self._raw_driver()
            data = driver.execute_script(
                InstagramProfileLocators.RECENT_POST_CONTEXT_SCRIPT
            )
            if not isinstance(data, dict):
                return {}

            current_url = _normalize_instagram_href(
                str(driver.current_url or "").strip()
            )
            post_url = _normalize_instagram_href(
                str(data.get("post_url", "") or "").strip()
            ) or current_url

            expected = _normalize_instagram_href(str(expected_url or "").strip())
            if expected and (current_url != expected or post_url != expected):
                self._warning(
                    "[profile-integrity] BLOQUEADO contexto URL distinta | expected=%s | current=%s | extracted=%s",
                    expected, current_url, post_url,
                )
                return {}

            author = self._canonical_profile_username(
                data.get("author_username", "")
            )
            expected_author = self._canonical_profile_username(expected_author_username)
            if expected_author and author != expected_author:
                self._warning(
                    "[profile-integrity] BLOQUEADO contexto autor distinto | expected=%s | actual=%s | post=%s",
                    expected_author, author, post_url,
                )
                return {}
            if expected_author and not author:
                self._warning(
                    "[profile-integrity] BLOQUEADO contexto sin autor | expected=%s | post=%s",
                    expected_author, post_url,
                )
                return {}

            return {
                "post_url": post_url,
                "author_username": author,
                "author_profile_url": str(
                    data.get("author_profile_url", "") or ""
                ).strip(),
                "caption_text": str(data.get("caption_text", "") or "").strip(),
                "post_type": str(
                    data.get("post_type", "post") or "post"
                ).strip().lower(),
            }

        except Exception as e:
            self._warning(
                "[profile] no se pudo extraer contexto de recent post | url=%s | error=%r",
                expected_url, e,
            )
            return {}

    def scroll_profile_grid(self) -> None:
        try:
            self.browser.driver.execute_script(
                "window.scrollBy(0, Math.floor(window.innerHeight * 0.85));"
            )
        except Exception:
            pass

    # =========================================================
    # OPENED POST
    # =========================================================
    def open_post_url(self, post_url: str, sleep_seconds: float = 4.0) -> bool:
        try:
            post_url = str(post_url or "").strip()

            if not post_url:
                return False

            self.open_url(post_url)
            self.sleep(sleep_seconds)
            return True

        except Exception as e:
            self._warning(
                "[profile] no se pudo abrir post_url=%s | error=%r",
                post_url,
                e,
            )
            return False

    def looks_like_post_page(self) -> bool:
        try:
            current_url = (self.browser.driver.current_url or "").lower()
            return self.is_post_url(current_url)
        except Exception:
            return False

    def is_post_url(self, url: str) -> bool:
        try:
            url = str(url or "").strip().lower()
            return any(part in url for part in InstagramProfileLocators.POST_URL_PARTS)
        except Exception:
            return False

    def extract_opened_post_text_context(self) -> str:
        try:
            text = self._raw_driver().execute_script(
                InstagramProfileLocators.OPENED_POST_TEXT_CONTEXT_SCRIPT
            )
            return str(text or "").strip()

        except Exception as e:
            self._warning("[profile] no se pudo extraer texto del post: %r", e)
            return ""

    def get_opened_post_author_username(self) -> str:
        try:
            author = self._raw_driver().execute_script(
                InstagramProfileLocators.OPENED_POST_AUTHOR_USERNAME_SCRIPT
            )
            author = str(author or "").strip().lower().lstrip("@")
            if re.fullmatch(r"[a-z0-9._]{1,30}", author):
                return author
        except Exception as e:
            self._warning("[profile] no se pudo extraer autor del post por DOM: %r", e)

        # Instagram puede renderizar el header del post sin un anchor estable.
        # En esos casos el contexto textual ya contiene el patrón inequívoco
        # ``<autor> el <fecha>:``. Solo usamos ese segmento y validamos el
        # username, evitando tomar usernames posteriores de comentaristas.
        try:
            text_context = self.extract_opened_post_text_context()
            match = re.search(
                r"(?:^|[|\-])\s*@?([a-z0-9._]{1,30})\s+el\s+"
                r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+"
                r"\d{1,2},\s*\d{4}\b",
                text_context,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).lower()

            # Fallback para UI inglesa / variantes de locale.
            match = re.search(
                r"(?:^|[|\-])\s*@?([a-z0-9._]{1,30})\s+(?:on|el)\s+"
                r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+"
                r"\d{1,2},\s*\d{4}\b",
                text_context,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).lower()
        except Exception as e:
            self._warning("[profile] fallback textual de autor falló: %r", e)

        return ""
    def extract_current_post_context(self, opened_href: str) -> dict:
        """
        Extrae el contexto básico de la publicación actualmente abierta.

        Retorna:
        - post_url
        - author_username
        - text_context
        """
        try:
            post_url = _normalize_instagram_href(
                str(opened_href or "").strip()
            )

            if not post_url:
                return {}

            author_username = self.get_opened_post_author_username()
            text_context = self.extract_opened_post_text_context()

            return {
                "post_url": post_url,
                "author_username": author_username,
                "text_context": text_context,
            }

        except Exception as e:
            self._warning(
                "[profile] no se pudo extraer contexto del post | url=%s | error=%r",
                opened_href,
                e,
            )
            return {}
    def extract_author_profile_context(self, post_context: dict) -> dict:
        """
        Construye el contexto básico del perfil autor del post abierto.

        Retorna:
        - username
        - profile_url
        - display_name
        - bio
        """
        try:
            post_context = post_context or {}

            username = str(
                post_context.get("author_username", "")
            ).strip().lower().lstrip("@")

            if not username:
                self._warning(
                    "[profile] no se pudo determinar el username del autor."
                )
                return {}

            profile_url = f"https://www.instagram.com/{username}/"

            return {
                "username": username,
                "profile_url": profile_url,
                "display_name": "",
                "bio": "",
            }

        except Exception as e:
            self._warning(
                "[profile] no se pudo extraer contexto del perfil del autor | error=%r",
                e,
            )
            return {}
    def is_own_post_opened(self, own_username: str) -> bool:
        try:
            own_username = str(own_username or "").strip().lower().lstrip("@")

            if not own_username:
                return False

            author = self.get_opened_post_author_username()

            return bool(author and author == own_username)

        except Exception:
            return False

    # =========================================================
    # BROWSER HELPERS
    # =========================================================
    def _rate_limit_cooldown_seconds(self) -> float:
        try:
            return max(30.0, float(os.getenv("INSTAGRAM_429_COOLDOWN_SECONDS", "90")))
        except Exception:
            return 90.0

    def _navigation_gap_seconds(self) -> float:
        try:
            return max(0.8, float(os.getenv("INSTAGRAM_PROFILE_NAV_GAP_SECONDS", "2.5")))
        except Exception:
            return 2.5

    def _is_rate_limit_page(self) -> bool:
        """Detecta la página de limitación sin depender del status HTTP de Selenium."""
        try:
            driver = self.browser.driver
            title = str(getattr(driver, "title", "") or "").lower()
            current_url = str(getattr(driver, "current_url", "") or "").lower()
            try:
                body = str(driver.find_element(By.TAG_NAME, "body").text or "")[:12000].lower()
            except Exception:
                body = ""

            hay_indicador = any(
                marker in body or marker in title
                for marker in (
                    "429 too many requests",
                    "too many requests",
                    "please wait a few minutes before you try again",
                    "we limit how often you can do certain things on instagram",
                    "rate limit",
                )
            )
            # No marcamos cualquier URL /challenge como 429: los challenges
            # tienen tratamiento distinto y no deben provocar falsos positivos.
            return hay_indicador or "429" in title
        except Exception:
            return False

    def _mark_rate_limited(self) -> None:
        now = time.monotonic()
        cooldown = self._rate_limit_cooldown_seconds()
        try:
            setattr(self.browser, "_instagram_rate_limit_until", now + cooldown)
        except Exception:
            pass
        self._warning(
            "[instagram-rate-limit] 429 detectado; pausando navegación durante %.0fs",
            cooldown,
        )

    def is_rate_limited(self) -> bool:
        try:
            until = float(getattr(self.browser, "_instagram_rate_limit_until", 0.0) or 0.0)
            return time.monotonic() < until
        except Exception:
            return False

    def clear_rate_limit_if_elapsed(self) -> None:
        try:
            if not self.is_rate_limited():
                setattr(self.browser, "_instagram_rate_limit_until", 0.0)
        except Exception:
            pass

    def _wait_navigation_gap(self) -> None:
        """Evita ráfagas de driver.get() al saltar entre perfiles/posts."""
        try:
            now = time.monotonic()
            last = float(getattr(self.browser, "_instagram_last_navigation_at", 0.0) or 0.0)
            remaining = self._navigation_gap_seconds() - (now - last)
            if remaining > 0:
                self.sleep(remaining)
            setattr(self.browser, "_instagram_last_navigation_at", time.monotonic())
        except Exception:
            pass

    def open_url(self, url: str) -> None:
        url = str(url or "").strip()
        if not url:
            return

        if self.is_rate_limited():
            raise InstagramRateLimitError(
                "Instagram está en cooldown por un rate limit 429. No se realizará otra navegación."
            )

        self._wait_navigation_gap()

        try:
            if hasattr(self.browser, "go_to_url"):
                self.browser.go_to_url(url)
            else:
                self.browser.driver.get(url)
        except InstagramRateLimitError:
            raise
        except Exception as exc:
            # Selenium normalmente no expone el HTTP status de una navegación.
            # Si la respuesta se convirtió en una página 429, la detectamos abajo.
            self._warning("[profile] navegación falló | url=%s | error=%r", url, exc)
            raise

        self.sleep(random.uniform(0.6, 1.1))
        if self._is_rate_limit_page():
            self._mark_rate_limited()
            raise InstagramRateLimitError(f"Instagram rate-limited URL: {url}")

    def sleep(self, seconds: float) -> None:
        try:
            if hasattr(self.browser, "time_sleep"):
                self.browser.time_sleep(seconds)
            else:
                time.sleep(seconds)
        except Exception:
            try:
                time.sleep(seconds)
            except Exception:
                pass

    # =========================================================
    # LOG HELPERS
    # =========================================================
    def _info(self, msg: str, *args) -> None:
        try:
            if self.log:
                self.log.info(msg, *args)
        except Exception:
            pass

    def _warning(self, msg: str, *args) -> None:
        try:
            if self.log:
                self.log.warning(msg, *args)
        except Exception:
            pass


    def _ensure_follow_on_current_post(self, expected_username: str) -> str:
        """
        Follow the post author without navigating to the profile when the
        current surface is already a post from that exact author.

        This is critical for prospecting: navigating post -> profile with
        Selenium ``driver.get`` can block at the ChromeDriver level even when
        page-load timeouts are configured. The post header already exposes the
        Follow/Following control, so an extra profile navigation is unnecessary.
        """
        try:
            current = _normalize_instagram_href(
                str(getattr(self._raw_driver(), "current_url", "") or "").strip()
            )
            if not self.is_post_url(current):
                return "not_applicable"

            expected = self._canonical_profile_username(expected_username)
            if not expected:
                return "error"

            author = self._canonical_profile_username(self.get_opened_post_author_username())
            if not author or author != expected:
                self._warning(
                    "[profile] follow en post bloqueado por autor mismatch | expected=%s | author=%s | url=%s",
                    expected, author, current,
                )
                # Fail closed: once we know we are on a post belonging to a
                # different author, do NOT fall back to profile navigation.
                # The caller must skip this candidate instead.
                return "error"

            self._info(
                "[profile] follow sin navegar al perfil | username=%s | current_post=%s",
                expected, current,
            )

            following_xpath = self.visible_any(InstagramProfileLocators.PROFILE_FOLLOWING_STATE_BUTTONS)
            if following_xpath:
                return "already_following"

            follow_xpath = self.visible_any(InstagramProfileLocators.PROFILE_FOLLOW_BUTTONS)
            if not follow_xpath:
                self._warning(
                    "[profile] no se encontró Follow en post del autor | username=%s | url=%s",
                    expected, current,
                )
                return "error"

            click_result = self._click_follow_control_robust(follow_xpath, expected)
            if not click_result.get("ok"):
                self._warning(
                    "[profile] follow click no aceptado | username=%s | result=%s",
                    expected,
                    click_result,
                )
                return "error"

            # Never issue a second click after an accepted click. Verification
            # is bounded so a missing UI update cannot stall the task.
            verified = self._verify_follow_state_bounded(
                expected,
                timeout_seconds=float(
                    os.getenv("INSTAGRAM_FOLLOW_VERIFY_TIMEOUT_SECONDS", "6")
                ),
            )
            if verified == "followed":
                return "followed"
            if verified == "already_following":
                return "already_following"

            self._warning(
                "[profile] follow click aceptado pero estado no confirmado | username=%s | result=%s",
                expected,
                click_result,
            )
            return "error"
        except InstagramRateLimitError:
            raise
        except Exception as exc:
            self._warning("[profile] follow directo en post falló | error=%r", exc)
            return "error"

    def ensure_follow_profile(self, profile_url: str) -> str:
        """
        Retorna:
        - already_following
        - followed
        - error
        """
        try:
            profile_url = str(profile_url or "").strip()

            if not profile_url:
                return "error"

            self.open_url(profile_url)
            self.sleep(random.randint(3, 5))

            already_following_xpath = self.visible_any(
                InstagramProfileLocators.PROFILE_FOLLOWING_STATE_BUTTONS
            )

            if already_following_xpath:
                self._info(
                    "[profile] ya estaba seguido/solicitado | xpath=%s | url=%s",
                    already_following_xpath,
                    profile_url,
                )
                return "already_following"

            follow_xpath = self.visible_any(
                InstagramProfileLocators.PROFILE_FOLLOW_BUTTONS
            )

            if not follow_xpath:
                self._warning(
                    "[profile] no se encontró botón Follow/Seguir | url=%s",
                    profile_url,
                )
                return "error"

            clicked = self.click_xpath(follow_xpath)

            if not clicked:
                self._warning(
                    "[profile] no se pudo hacer click en Follow/Seguir | xpath=%s | url=%s",
                    follow_xpath,
                    profile_url,
                )
                return "error"

            self.sleep(random.randint(2, 4))

            confirmed_xpath = self.visible_any(
                InstagramProfileLocators.PROFILE_FOLLOWING_STATE_BUTTONS
            )

            if confirmed_xpath:
                self._info(
                    "[profile] follow confirmado | xpath=%s | url=%s",
                    confirmed_xpath,
                    profile_url,
                )
                return "followed"

            follow_still_visible = self.visible_any(
                InstagramProfileLocators.PROFILE_FOLLOW_BUTTONS
            )

            if not follow_still_visible:
                self._info(
                    "[profile] Follow desapareció tras click. Se asume followed | url=%s",
                    profile_url,
                )
                return "followed"

            self.sleep(random.randint(2, 3))

            confirmed_xpath = self.visible_any(
                InstagramProfileLocators.PROFILE_FOLLOWING_STATE_BUTTONS
            )

            if confirmed_xpath:
                self._info(
                    "[profile] follow confirmado en segundo intento | xpath=%s | url=%s",
                    confirmed_xpath,
                    profile_url,
                )
                return "followed"

            self._warning(
                "[profile] click en Follow sin confirmación visual. Se marca followed para no tumbar flujo | url=%s",
                profile_url,
            )
            return "followed"

        except Exception as e:
            self._warning("[profile] error asegurando follow | error=%r", e)
            return "error"

    def visible_any(self, xpaths: list[str]) -> str:
        for xpath in xpaths or []:
            try:
                if hasattr(self.browser, "is_visible"):
                    if self.browser.is_visible(xpath):
                        return xpath
                    continue

                elements = self.browser.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    try:
                        if el.is_displayed():
                            return xpath
                    except Exception:
                        continue

            except Exception:
                continue

        return ""

    def click_xpath(self, xpath: str) -> bool:
        try:
            if hasattr(self.browser, "click"):
                return bool(self.browser.click(xpath, scroll=True, error=False))

            elements = self.browser.driver.find_elements(By.XPATH, xpath)

            for el in elements:
                try:
                    if not el.is_displayed() or not el.is_enabled():
                        continue

                    try:
                        self.browser.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                            el,
                        )
                    except Exception:
                        pass

                    try:
                        el.click()
                        return True
                    except Exception:
                        self.browser.driver.execute_script("arguments[0].click();", el)
                        return True

                except Exception:
                    continue

            return False

        except Exception:
            return False
