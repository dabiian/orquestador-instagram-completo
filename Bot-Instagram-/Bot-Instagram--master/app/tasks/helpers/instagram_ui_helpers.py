import random
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class InstagramUIHelpersMixin:
    def _get_visible_elements(self, xpath: str, root=None) -> list:
        try:
            scope = root or self.browser.driver
            elements = scope.find_elements(By.XPATH, xpath)

            visible_elements = []
            for element in elements:
                try:
                    if element.is_displayed():
                        visible_elements.append(element)
                except Exception:
                    continue

            return visible_elements
        except Exception:
            return []

    def _scroll_into_view(self, element) -> None:
        try:
            self.browser.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                element,
            )
        except Exception:
            pass

    def _safe_click(self, element, pause_before: float = 0.8, pause_after: float = 0.0) -> bool:
        try:
            self._scroll_into_view(element)
            self.browser.time_sleep(pause_before)

            try:
                ActionChains(self.browser.driver).move_to_element(element).pause(0.2).click().perform()
                if pause_after:
                    self.browser.time_sleep(pause_after)
                return True
            except Exception:
                pass

            try:
                element.click()
                if pause_after:
                    self.browser.time_sleep(pause_after)
                return True
            except Exception:
                pass

            try:
                self.browser.driver.execute_script("arguments[0].click();", element)
                if pause_after:
                    self.browser.time_sleep(pause_after)
                return True
            except Exception:
                pass

            try:
                element.send_keys(Keys.ENTER)
                if pause_after:
                    self.browser.time_sleep(pause_after)
                return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    def _find_active_dialog(self):
        try:
            dialogs = self.browser.driver.find_elements(
                By.XPATH,
                "//div[@role='dialog' and not(@aria-hidden='true')]"
            )

            visible_dialogs = []
            for dialog in dialogs:
                try:
                    if dialog.is_displayed():
                        visible_dialogs.append(dialog)
                except Exception:
                    continue

            if not visible_dialogs:
                return None

            return visible_dialogs[-1]
        except Exception:
            return None

    def _find_visible_caption_editor(self, caption_xpath: str):
        try:
            editors = self.browser.driver.find_elements(By.XPATH, caption_xpath)
            visible_editors = []

            for editor in editors:
                try:
                    if editor.is_displayed():
                        visible_editors.append(editor)
                except Exception:
                    continue

            if not visible_editors:
                return None

            return visible_editors[-1]
        except Exception:
            return None

    def _clear_input_like_human(self, element) -> None:
        try:
            element.send_keys(Keys.CONTROL, "a")
            time.sleep(random.uniform(0.2, 0.4))
            element.send_keys(Keys.BACKSPACE)
            time.sleep(random.uniform(0.3, 0.6))
        except Exception:
            pass

    def _type_text_like_human(
        self,
        element,
        text: str,
        multiline: bool = True,
        sanitize_non_bmp: bool = False,
    ) -> bool:
        try:
            text = (text or "").strip()
            if not text:
                return False

            safe_text = text
            if sanitize_non_bmp:
                safe_text = "".join(
                    ch for ch in text
                    if ch == "\n" or ord(ch) <= 0xFFFF
                ).strip()

            if not safe_text:
                return False

            for index, ch in enumerate(safe_text):
                try:
                    if ch == "\n" and multiline:
                        element.send_keys(Keys.SHIFT, Keys.ENTER)
                    else:
                        element.send_keys(ch)

                    time.sleep(random.uniform(0.03, 0.09))

                    if ch in {".", ",", "!", "?", ":", ";"}:
                        time.sleep(random.uniform(0.15, 0.35))
                    elif ch == " ":
                        time.sleep(random.uniform(0.02, 0.06))

                except Exception as exc:
                    if hasattr(self, "log"):
                        self.log.warning(
                            "Error escribiendo texto en índice=%s | char=%r | codepoint=U+%X | exc=%r",
                            index,
                            ch,
                            ord(ch),
                            exc,
                        )
                    return False

            return True

        except Exception:
            return False