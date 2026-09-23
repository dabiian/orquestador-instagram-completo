import random
import re
from typing import Any, Dict, List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from app.core.interfaces import IBrowser, ITask
from app.utils.logger import get_logger
from app.config.locators.instagram_notifications_locators import InstagramNotificationsLocators


class InstagramNotificationsTask(ITask):
    """
    Tarea para revisar notificaciones recientes de Instagram.

    Nueva lógica:
    - Ya no depende de la sección "Nuevo/New".
    - Abre el panel de notificaciones.
    - Entra a la pestaña "Todas/All" si existe.
    - Extrae notificaciones visibles recientes desde el DOM.
    - Abre algunas notificaciones.
    - Evita repetir el mismo post/perfil aunque cambie el tiempo: 7 min, 8 min, 9 min.
    """

    def __init__(self, browser: IBrowser):
        self.browser = browser
        self.log = get_logger(self.__class__.__name__)

    def execute(self) -> str:
        try:
            self.log.info("Starting review of visible Instagram notifications")

            if not self._open_notifications():
                return "✗ Could not open Instagram notifications"

            self._click_all_tab_safe()

            reviewed_count = 0
            processed_keys = set()
            processed_target_urls = set()

            # Más natural: no abrir demasiadas notificaciones seguidas.
            human_limit = random.randint(2, 3)

            while reviewed_count < human_limit:
                if not self._ensure_notifications_panel_open():
                    self.log.warning("Notifications panel could not be opened again.")
                    break

                self._click_all_tab_safe()

                notifications = self._extract_visible_notifications(max_items=15)

                total_items = len(notifications)
                self.log.info("Visible notifications detected: %s", total_items)

                if total_items == 0:
                    self.log.info("No visible notifications found.")
                    break

                next_notification = self._get_next_unprocessed_notification(
                    notifications=notifications,
                    processed_keys=processed_keys,
                    processed_target_urls=processed_target_urls,
                )

                if not next_notification:
                    self.log.info("No more safe unprocessed notifications found.")
                    break

                key = str(next_notification.get("key") or "").strip()
                text = str(next_notification.get("text") or "").strip()
                target_url = str(next_notification.get("target_url") or "").strip()

                self.log.info(
                    "Reviewing notification %s/%s | text=%s | target=%s",
                    reviewed_count + 1,
                    human_limit,
                    text,
                    target_url,
                )

                reviewed_ok = self._open_notification_target(next_notification)

                if reviewed_ok:
                    reviewed_count += 1

                    if key:
                        processed_keys.add(key)

                    if target_url:
                        processed_target_urls.add(target_url)

                self.browser.time_sleep(random.randint(2, 4))

            return f"se revisaron {reviewed_count} notificaciones recientes de instagram"

        except Exception as e:
            self.log.error("Error reviewing Instagram notifications: %s", str(e))
            return f"✗ Error: {str(e)}"

    # =========================================================
    # PANEL
    # =========================================================

    def _ensure_notifications_panel_open(self) -> bool:
        try:
            if self._is_notifications_panel_visible():
                return True

            return self._open_notifications()

        except Exception as e:
            self.log.warning("Error ensuring notifications panel open: %s", str(e))
            return False

    def _is_notifications_panel_visible(self) -> bool:
        try:
            return bool(
                self.browser.is_visible(
                    InstagramNotificationsLocators.NOTIFICATIONS_PANEL_ROOT
                )
            )
        except Exception:
            return False

    def _open_notifications(self) -> bool:
        xpath = InstagramNotificationsLocators.NOTIFICATIONS_BUTTON

        try:
            if self._is_notifications_panel_visible():
                return True

            if not self.browser.is_visible(xpath):
                self.log.warning("Notifications button was not found.")
                return False

            ok = self.browser.hover_and_click(xpath)

            if not ok:
                self.log.warning("hover_and_click failed. Trying safe fallback click.")
                ok = self._safe_click_xpath(xpath)

            self.browser.time_sleep(random.randint(2, 4))

            if self._is_notifications_panel_visible():
                return True

            self.browser.time_sleep(2)

            return self._is_notifications_panel_visible()

        except Exception as e:
            self.log.warning("Could not open notifications: %s", str(e))
            return False

    def _click_all_tab_safe(self) -> bool:
        try:
            xpath = InstagramNotificationsLocators.ALL_TAB

            if not self.browser.is_visible(xpath):
                self.log.info("All tab is not visible. Continuing with current notifications view.")
                return False

            ok = self._safe_click_xpath(xpath)

            if ok:
                self.browser.time_sleep(random.uniform(0.8, 1.5))

            return ok

        except Exception as e:
            self.log.warning("Could not click All tab: %s", str(e))
            return False

    def _safe_click_xpath(self, xpath: str) -> bool:
        try:
            elements = self.browser.driver.find_elements(By.XPATH, xpath)

            for element in elements:
                try:
                    if not element.is_displayed():
                        continue

                    try:
                        self.browser.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                            element,
                        )
                    except Exception:
                        pass

                    self.browser.time_sleep(random.uniform(0.3, 0.7))

                    try:
                        ActionChains(self.browser.driver).move_to_element(element).pause(
                            random.uniform(0.2, 0.5)
                        ).click().perform()
                        return True
                    except Exception:
                        pass

                    try:
                        element.click()
                        return True
                    except Exception:
                        pass

                    try:
                        self.browser.driver.execute_script("arguments[0].click();", element)
                        return True
                    except Exception:
                        pass

                except Exception:
                    continue

            return False

        except Exception as e:
            self.log.warning("safe click failed for xpath=%s | error=%s", xpath, str(e))
            return False

    # =========================================================
    # LECTURA DE NOTIFICACIONES
    # =========================================================

    def _extract_visible_notifications(self, max_items: int = 15) -> List[Dict[str, Any]]:
        """
        Extrae notificaciones visibles desde el DOM actual.

        Preferencia de target:
        1. URL del post/reel/tv.
        2. URL del perfil.

        No depende de "Nuevo/New".
        """
        try:
            script = r"""
            return (() => {
                const norm = (txt) => (txt || '').replace(/\s+/g, ' ').trim();

                const isPostUrl = (url) => {
                    return url.includes('/p/') || url.includes('/reel/') || url.includes('/tv/');
                };

                const isBadUrl = (url) => {
                    return (
                        !url ||
                        url.includes('/direct/') ||
                        url.includes('/explore/') ||
                        url.includes('/accounts/') ||
                        url.includes('/notifications/')
                    );
                };

                const makeAbs = (href) => {
                    try {
                        return new URL(href, location.origin).href;
                    } catch (e) {
                        return '';
                    }
                };

                const containers = [
                    ...document.querySelectorAll('div[data-pressable-container="true"]')
                ];

                const results = [];
                const seen = new Set();

                for (const container of containers) {
                    try {
                        const text = norm(container.innerText || container.textContent || '');

                        if (!text) continue;
                        if (text.length < 8) continue;

                        const lower = text.toLowerCase();

                        const ignoredTexts = [
                            'todas',
                            'all',
                            'comentarios',
                            'comments',
                            'siguiendo',
                            'following',
                            'seguir',
                            'follow'
                        ];

                        if (ignoredTexts.includes(lower)) {
                            continue;
                        }

                        const links = [...container.querySelectorAll('a[href]')]
                            .map(a => makeAbs(a.getAttribute('href')))
                            .filter(url => url && !isBadUrl(url));

                        const postUrl = links.find(url => isPostUrl(url)) || '';
                        const profileUrl = links.find(url => !isPostUrl(url)) || '';

                        const targetUrl = postUrl || profileUrl || '';

                        if (!targetUrl) continue;

                        const abbr = container.querySelector('abbr');

                        const timeText = norm(
                            (abbr && (abbr.getAttribute('aria-label') || abbr.innerText || abbr.textContent)) || ''
                        );

                        let type = 'generic';

                        if (
                            lower.includes('comentario') ||
                            lower.includes('comment') ||
                            lower.includes('ha escrito un comentario')
                        ) {
                            type = 'comment';
                        } else if (
                            lower.includes('gustado') ||
                            lower.includes('liked') ||
                            lower.includes('like')
                        ) {
                            type = 'like';
                        } else if (
                            lower.includes('ha comenzado a seguirte') ||
                            lower.includes('started following') ||
                            lower.includes('followed you')
                        ) {
                            type = 'follow';
                        } else if (
                            lower.includes('mencion') ||
                            lower.includes('mentioned') ||
                            lower.includes('tagged')
                        ) {
                            type = 'mention';
                        }

                        /*
                         IMPORTANTE:
                         No usamos el tiempo para deduplicar.
                         Instagram cambia "7 min", "8 min", "9 min" y eso generaba repetidos.
                        */
                        const key = `${type}|${targetUrl}`.toLowerCase();

                        if (seen.has(key)) continue;
                        seen.add(key);

                        results.push({
                            text,
                            time_text: timeText,
                            type,
                            target_url: targetUrl,
                            key
                        });
                    } catch (e) {}
                }

                return results;
            })();
            """

            raw_items = self.browser.driver.execute_script(script) or []

            if not isinstance(raw_items, list):
                return []

            cleaned = []
            seen_targets = set()

            for item in raw_items:
                if not isinstance(item, dict):
                    continue

                text = str(item.get("text") or "").strip()
                target_url = str(item.get("target_url") or "").strip()
                key = str(item.get("key") or "").strip()

                if not text or not target_url or not key:
                    continue

                if not self._is_safe_instagram_target(target_url):
                    continue

                target_norm = self._normalize_url(target_url)

                if target_norm in seen_targets:
                    continue

                seen_targets.add(target_norm)

                cleaned.append(
                    {
                        "text": text,
                        "time_text": str(item.get("time_text") or "").strip(),
                        "type": str(item.get("type") or "generic").strip(),
                        "target_url": target_url,
                        "target_norm": target_norm,
                        "key": self._normalize_key(key),
                    }
                )

                if len(cleaned) >= max_items:
                    break

            return cleaned

        except Exception as e:
            self.log.warning("Error extracting visible notifications: %s", str(e))
            return []

    def _get_next_unprocessed_notification(
        self,
        notifications: List[Dict[str, Any]],
        processed_keys: set,
        processed_target_urls: set,
    ) -> Optional[Dict[str, Any]]:
        try:
            if not notifications:
                return None

            for notification in notifications:
                key = str(notification.get("key") or "").strip()
                target_url = str(notification.get("target_url") or "").strip()
                target_norm = str(notification.get("target_norm") or "").strip()

                if not key or not target_url:
                    continue

                if not target_norm:
                    target_norm = self._normalize_url(target_url)

                if key in processed_keys:
                    continue

                if target_url in processed_target_urls or target_norm in processed_target_urls:
                    self.log.info(
                        "Notification skipped because target_url was already processed: %s",
                        target_url,
                    )
                    continue

                if not self._is_safe_instagram_target(target_url):
                    continue

                return notification

            return None

        except Exception as e:
            self.log.warning("Error selecting next notification: %s", str(e))
            return None

    def _is_safe_instagram_target(self, url: str) -> bool:
        try:
            url = str(url or "").strip().lower()

            if not url:
                return False

            if "instagram.com" not in url:
                return False

            blocked_parts = [
                "/direct/",
                "/accounts/",
                "/explore/",
                "/notifications/",
                "/oauth/",
            ]

            if any(part in url for part in blocked_parts):
                return False

            return True

        except Exception:
            return False

    # =========================================================
    # REVISIÓN
    # =========================================================

    def _open_notification_target(self, notification: Dict[str, Any]) -> bool:
        try:
            target_url = str(notification.get("target_url") or "").strip()
            text = str(notification.get("text") or "").strip()

            if not target_url:
                return False

            if not self._is_safe_instagram_target(target_url):
                self.log.warning("Unsafe notification target skipped: %s", target_url)
                return False

            self.log.info("Opening notification target: %s | text=%s", target_url, text)

            self.browser.go_to_url(target_url)
            self.browser.time_sleep(random.randint(4, 8))

            try:
                self.browser.go_back_page()
                self.browser.time_sleep(random.randint(2, 4))
            except Exception as e:
                self.log.warning("Could not go back after notification: %s", str(e))

            return True

        except Exception as e:
            self.log.warning("Error opening notification target: %s", str(e))
            return False

    # =========================================================
    # NORMALIZACIÓN
    # =========================================================

    def _normalize_key(self, text: str) -> str:
        text = str(text or "").lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _normalize_url(self, url: str) -> str:
        try:
            url = str(url or "").strip()

            if not url:
                return ""

            url = url.split("?")[0].strip()
            url = url.rstrip("/")

            return url.lower()

        except Exception:
            return ""