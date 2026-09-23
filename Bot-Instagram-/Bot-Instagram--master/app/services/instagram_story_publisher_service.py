import os
import time

from selenium.webdriver.common.by import By

from app.config.locators.instagram_story_locators import InstagramStoryLocators


class InstagramStoryPublisherService:
    """
    Servicio reusable para publicar stories.

    IMPORTANTE:
    Este servicio mantiene el flujo original.
    NO abre /stories/create/.
    NO navega a URL directa.
    Solo:
    - busca input file existente
    - sube imagen
    - busca botón final de añadir a historia
    - publica
    """

    def __init__(self, browser, logger=None):
        self.browser = browser
        self.log = logger
        self.last_error = ""

    def publish_story(self, image_path: str) -> bool:
        try:
            image_path = os.path.abspath(str(image_path or "").strip())

            if not image_path or not os.path.exists(image_path):
                self._warning("Ruta de imagen inválida: %s", image_path)
                return False

            if not self.upload_story_image(image_path):
                self._warning("No se pudo subir la imagen de la historia.")
                return False

            if not self.share_story():
                self._warning("No se pudo compartir la historia.")
                return False

            if self.instagram_publish_error_visible():
                self._warning("Instagram mostró error al publicar story.")
                return False

            self._info("Historia compartida correctamente.")
            return True

        except Exception as e:
            self._exception("Error publicando story: %s", e)
            return False

    def upload_story_image(self, image_path: str) -> bool:
        if not image_path or not os.path.exists(image_path):
            self._warning("Ruta de imagen inválida: %s", image_path)
            return False

        try:
            self._sleep(2)

            upload_xpath = self._find_upload_input_xpath()

            if not upload_xpath:
                self._warning("No se encontró ningún input file para historias.")
                return False

            if hasattr(self.browser, "upload_file"):
                self.browser.upload_file(upload_xpath, image_path, time_x=10)
            else:
                elements = self.browser.driver.find_elements(By.XPATH, upload_xpath)
                if not elements:
                    self._warning("Input file desapareció antes de subir archivo.")
                    return False
                elements[0].send_keys(image_path)

            self._sleep(6)

            self._info("Archivo enviado al input file de historia.")
            return True

        except Exception as e:
            self._warning("Error subiendo imagen de historia: %r", e)
            return False

    def _find_upload_input_xpath(self) -> str:
        for candidate in InstagramStoryLocators.UPLOAD_INPUT_CANDIDATES:
            if not candidate:
                continue

            try:
                elements = self.browser.driver.find_elements(By.XPATH, candidate)

                if elements:
                    self._info("Input file de story detectado con xpath: %s", candidate)
                    return candidate

            except Exception:
                continue

        return ""

    def share_story(self) -> bool:
        try:
            for attempt in range(12):
                self._sleep(2)

                button = self.find_add_to_story_button()

                if button is not None:
                    if self.click_publish_button(button):
                        self._sleep(6)
                        self._info("Click en botón final de story ejecutado.")
                        return True

                self.scroll_for_publish_button(attempt)

            self._warning("No se encontró el botón final para publicar la historia.")
            self._sleep(10)
            return False

        except Exception as e:
            self._warning("Error publicando historia: %r", e)
            return False

    def find_add_to_story_button(self):
        for xpath in InstagramStoryLocators.ADD_TO_STORY_BUTTON_CANDIDATES:
            try:
                elements = self.browser.driver.find_elements(By.XPATH, xpath)

                visible_elements = []

                for element in elements:
                    try:
                        if element.is_displayed():
                            visible_elements.append(element)
                    except Exception:
                        continue

                if visible_elements:
                    self._info("Botón final detectado con xpath: %s", xpath)
                    return visible_elements[0]

            except Exception:
                continue

        return None

    def click_publish_button(self, element) -> bool:
        try:
            try:
                self.browser.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                    element,
                )
            except Exception:
                pass

            time.sleep(1)

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

            return False

        except Exception as e:
            self._warning("Error haciendo click en botón final: %r", e)
            return False

    def scroll_for_publish_button(self, attempt: int) -> None:
        try:
            if attempt < 4:
                self.browser.driver.execute_script("window.scrollBy(0, 250);")
            elif attempt < 8:
                self.browser.driver.execute_script("window.scrollBy(0, 400);")
            else:
                self.browser.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
        except Exception:
            pass

    def instagram_publish_error_visible(self) -> bool:
        try:
            body_text = self.browser.driver.find_element(By.TAG_NAME, "body").text or ""
            body_lower = body_text.lower()

            return any(
                pattern.lower() in body_lower
                for pattern in InstagramStoryLocators.PUBLISH_ERROR_TEXTS
            )

        except Exception:
            return False

    def _sleep(self, seconds: float) -> None:
        try:
            if hasattr(self.browser, "time_sleep"):
                self.browser.time_sleep(seconds)
            else:
                time.sleep(seconds)
        except Exception:
            time.sleep(seconds)

    def _info(self, msg: str, *args) -> None:
        try:
            if self.log:
                self.log.info(msg, *args)
        except Exception:
            pass

    def _warning(self, msg: str, *args) -> None:
        try:
            if args:
                self.last_error = msg % args
            else:
                self.last_error = msg

            if self.log:
                self.log.warning(msg, *args)
        except Exception:
            pass

    def _exception(self, msg: str, *args) -> None:
        try:
            if args:
                self.last_error = msg % args
            else:
                self.last_error = msg

            if self.log:
                self.log.exception(msg, *args)
        except Exception:
            pass