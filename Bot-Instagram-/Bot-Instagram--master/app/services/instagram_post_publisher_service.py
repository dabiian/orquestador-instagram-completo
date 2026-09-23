import os
import random
import time
import pyperclip

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from app.config.locators.instagram_post_locators import InstagramPostLocators


class InstagramPostPublisherService:
    """
    Servicio reusable para publicar posts en Instagram.

    Centraliza:
    - abrir composer de nueva publicación
    - subir imágenes/videos
    - click en Siguiente
    - escribir caption
    - click en Compartir
    - detección básica de errores

    Lo usan:
    - ShareInstagramPostTask
    - ShareInstagramFollowbackPostTask
    - ShareOwnerReviewPostTask
    - InstagramCampaignServiceContentTask
    """

    def __init__(self, browser, logger=None):
        self.browser = browser
        self.log = logger
        self.last_error = ""

    # =========================================================
    # PUBLIC API
    # =========================================================
    def publish_post(self, media_paths: list[str], caption: str) -> bool:
        try:
            valid_paths = self._normalize_media_paths(media_paths)
            caption = str(caption or "").strip()

            if not valid_paths:
                self._warning("No hay medios válidos para publicar.")
                return False

            if not caption:
                self._warning("El caption está vacío.")
                return False

            self._open_url(InstagramPostLocators.HOME_URL)
            self._sleep(3)

            if not self.open_post_composer():
                self._warning("No se pudo abrir el composer de publicación.")
                return False

            if not self.upload_post_media(valid_paths):
                self._warning("No se pudieron subir los medios del post.")
                return False

            if not self.click_next_button("Siguiente 1"):
                self._warning("No se pudo avanzar con el primer Siguiente.")
                return False

            if not self.click_next_button("Siguiente 2"):
                self._warning("No se pudo avanzar con el segundo Siguiente.")
                return False

            if not self.write_caption(caption):
                self._warning("No se pudo escribir el caption.")
                return False

            if not self.click_share_button():
                self._warning("No se pudo dar click en Compartir.")
                return False

            self._sleep(8)

            if self.instagram_publish_error_visible():
                self._warning("Instagram mostró error al publicar.")
                return False

            self._info("Post enviado correctamente desde InstagramPostPublisherService.")
            return True

        except Exception as e:
            self._exception("Error publicando post: %s", e)
            return False

    # =========================================================
    # COMPOSER
    # =========================================================
    def open_post_composer(self) -> bool:
        try:
            driver = self.browser.driver

            icons = driver.find_elements(
                By.CSS_SELECTOR,
                InstagramPostLocators.NEW_POST_ICON_CSS,
            )

            print(f"[post] íconos encontrados por CSS: {len(icons)}")

            if not icons:
                print("[post] no se encontró el ícono de nueva publicación")
                return False

            icon = icons[0]
            clickable = self._find_clickable_ancestor(icon)

            if clickable is None:
                print("[post] no se encontró contenedor clickable")
                return False

            for attempt in range(1, 5):
                print(f"[post] intento abrir composer {attempt}/4")

                try:
                    ActionChains(driver).move_to_element(clickable).pause(0.6).perform()
                    print("[post] hover ok")
                except Exception as e:
                    print(f"[post] hover falló: {e}")

                self._sleep(0.8)

                if self._try_click_element(clickable, label="click normal"):
                    self._sleep(1.2)

                    if self._create_menu_opened():
                        print("[post] abrió menú de crear, intentando Publicación/Post...")
                        if self._click_post_option_if_present() and self.real_post_composer_opened():
                            print("[post] composer real abierto luego de elegir Publicación/Post")
                            return True

                    if self.real_post_composer_opened():
                        print("[post] composer real abierto directo con click normal")
                        return True

                try:
                    ActionChains(driver).move_to_element(clickable).pause(0.3).click().perform()
                    print("[post] ActionChains click ok")
                except Exception as e:
                    print(f"[post] ActionChains click falló: {e}")

                self._sleep(1.2)

                if self._create_menu_opened():
                    print("[post] abrió menú tras ActionChains, intentando Publicación/Post...")
                    if self._click_post_option_if_present() and self.real_post_composer_opened():
                        print("[post] composer real abierto luego de ActionChains + Publicación/Post")
                        return True

                if self.real_post_composer_opened():
                    print("[post] composer real abierto con ActionChains")
                    return True

                try:
                    clickable.send_keys(Keys.ENTER)
                    print("[post] ENTER ok")
                except Exception as e:
                    print(f"[post] ENTER falló: {e}")

                self._sleep(1.2)

                if self._create_menu_opened():
                    print("[post] abrió menú tras ENTER, intentando Publicación/Post...")
                    if self._click_post_option_if_present() and self.real_post_composer_opened():
                        print("[post] composer real abierto luego de ENTER + Publicación/Post")
                        return True

                if self.real_post_composer_opened():
                    print("[post] composer real abierto con ENTER")
                    return True

                try:
                    clickable.send_keys(Keys.SPACE)
                    print("[post] SPACE ok")
                except Exception as e:
                    print(f"[post] SPACE falló: {e}")

                self._sleep(1.2)

                if self._create_menu_opened():
                    print("[post] abrió menú tras SPACE, intentando Publicación/Post...")
                    if self._click_post_option_if_present() and self.real_post_composer_opened():
                        print("[post] composer real abierto luego de SPACE + Publicación/Post")
                        return True

                if self.real_post_composer_opened():
                    print("[post] composer real abierto con SPACE")
                    return True

            print("[post] no se pudo abrir el composer")
            return False

        except Exception as e:
            print(f"[post] error abriendo composer: {e}")
            return False

    def real_post_composer_opened(self) -> bool:
        try:
            visibles = self._get_visible_elements(InstagramPostLocators.POST_COMPOSER_READY)
            if visibles:
                print(
                    f"[post] composer real detectado con: "
                    f"{InstagramPostLocators.POST_COMPOSER_READY} | visibles={len(visibles)}"
                )
                return True

            print("[post] composer real no detectado")
            return False

        except Exception:
            return False

    def _find_clickable_ancestor(self, icon):
        for rel_xpath in InstagramPostLocators.NEW_POST_CLICKABLE_ANCESTORS:
            try:
                candidate = icon.find_element(By.XPATH, rel_xpath)
                if candidate:
                    print(f"[post] clickable encontrado con: {rel_xpath}")
                    return candidate
            except Exception:
                continue

        return None

    def _create_menu_opened(self) -> bool:
        for xp in InstagramPostLocators.CREATE_MENU_DETECTORS:
            visibles = self._get_visible_elements(xp)
            if visibles:
                print(f"[post] menú de crear detectado con: {xp}")
                return True

        return False

    def _click_post_option_if_present(self) -> bool:
        for xp in InstagramPostLocators.CREATE_MENU_POST_OPTIONS:
            elems = self._get_visible_elements(xp)
            print(f"[post] candidatos Publicación/Post: {len(elems)} | {xp}")

            for el in elems:
                try:
                    txt = (el.text or "").strip()
                    href = (el.get_attribute("href") or "").strip()

                    print(
                        f"[post] opción publicación visible | texto='{txt}' | href='{href}'"
                    )

                    self._scroll_into_view(el)
                    self._sleep(0.5)

                    if self._try_click_element(el, label="Publicación/Post"):
                        self._sleep(1.5)
                        return True

                except Exception:
                    continue

        print("[post] no apareció opción explícita de Publicación/Post")
        return False

    # =========================================================
    # UPLOAD
    # =========================================================
    def upload_post_media(self, media_paths: list[str]) -> bool:
        try:
            valid_paths = self._normalize_media_paths(media_paths)

            if not valid_paths:
                self._warning("No se recibieron imágenes válidas para el post.")
                return False

            if not self._is_visible(InstagramPostLocators.POST_COMPOSER_READY):
                self._warning("El composer de subida no está visible.")
                return False

            self._sleep(1)

            input_elements = self.browser.driver.find_elements(
                By.XPATH,
                InstagramPostLocators.FILE_INPUT,
            )

            if not input_elements:
                if self._is_visible(InstagramPostLocators.SELECT_FROM_COMPUTER_BUTTON):
                    self._click_xpath(
                        InstagramPostLocators.SELECT_FROM_COMPUTER_BUTTON,
                        time_x=10,
                        scroll=False,
                    )
                    self._sleep(2)

                input_elements = self.browser.driver.find_elements(
                    By.XPATH,
                    InstagramPostLocators.FILE_INPUT,
                )

            if not input_elements:
                self._warning("No se encontró input[type='file'] para subir medios.")
                return False

            file_input = input_elements[0]
            files_payload = "\n".join(valid_paths)

            file_input.send_keys(files_payload)
            self._sleep(4)

            for _ in range(8):
                if self._is_visible(InstagramPostLocators.NEXT_BUTTON):
                    self._info("Medios subidos correctamente, apareció Next.")
                    return True

                self._sleep(1)

            self._warning("Se enviaron los archivos pero no apareció el botón Next.")
            return False

        except Exception as e:
            self._warning("Error subiendo medios del post: %r", e)
            return False

    # =========================================================
    # NEXT / CAPTION / SHARE
    # =========================================================
    def click_next_button(self, label: str = "Siguiente") -> bool:
        try:
            for _ in range(5):
                self._sleep(1)

                if self._is_visible(InstagramPostLocators.NEXT_BUTTON):
                    self._click_xpath(
                        InstagramPostLocators.NEXT_BUTTON,
                        time_x=10,
                        scroll=False,
                    )
                    self._sleep(3)
                    self._info("Click en botón %s ejecutado.", label)
                    return True

            self._warning("No se encontró el botón %s.", label)
            return False

        except Exception as e:
            self._warning("Error dando click en %s: %r", label, e)
            return False

    def write_caption(self, caption: str) -> bool:
        try:
            caption = str(caption or "").strip()

            if not caption:
                self._warning("El caption está vacío.")
                return False

            editors = self.browser.driver.find_elements(
                By.XPATH,
                InstagramPostLocators.CAPTION_INPUT,
            )

            if not editors:
                self._warning("No se encontró el editor del caption.")
                return False

            editor = None

            for candidate in editors:
                try:
                    if candidate.is_displayed() and candidate.is_enabled():
                        editor = candidate
                        break
                except Exception:
                    continue

            if editor is None:
                self._warning("No se encontró editor visible/habilitado para caption.")
                return False

            self._scroll_into_view(editor)
            self._sleep(1)

            try:
                ActionChains(self.browser.driver).move_to_element(editor).pause(
                    random.uniform(0.2, 0.5)
                ).click().perform()
            except Exception:
                try:
                    editor.click()
                except Exception as e:
                    self._warning("No se pudo enfocar el editor del caption: %r", e)
                    return False

            self._sleep(1)

            try:
                editor.send_keys(Keys.CONTROL, "a")
                time.sleep(random.uniform(0.2, 0.4))
                editor.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.3, 0.6))
            except Exception:
                pass

            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                old_clipboard = ""

            try:
                pyperclip.copy(caption)
                self._sleep(0.5)

                ActionChains(self.browser.driver).key_down(Keys.CONTROL).send_keys(
                    "v"
                ).key_up(Keys.CONTROL).perform()

                self._sleep(1)

                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

                self._info("Caption pegado correctamente usando clipboard.")
                return True

            except Exception as e:
                self._warning("Falló pegado por clipboard, error: %r", e)

                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

                return False

        except Exception as e:
            self._warning("Error escribiendo caption: %r", e)
            return False

    def click_share_button(self) -> bool:
        try:
            for attempt in range(1, 6):
                self._sleep(1)

                buttons = self.browser.driver.find_elements(
                    By.XPATH,
                    InstagramPostLocators.SHARE_BUTTON_ALL,
                )

                if not buttons:
                    self._warning("No se encontraron botones Compartir.")
                    continue

                visible_buttons = []

                for btn in buttons:
                    try:
                        if not btn.is_displayed() or not btn.is_enabled():
                            continue

                        txt = (btn.text or "").strip()

                        if txt in {"Compartir", "Share", "Publicar", "Post"}:
                            visible_buttons.append(btn)

                    except Exception:
                        continue

                if not visible_buttons:
                    self._warning("No hubo botones Compartir visibles.")
                    continue

                button = visible_buttons[-1]
                self._scroll_into_view(button)
                self._sleep(1)

                if self._try_click_element(button, label="Compartir"):
                    self._sleep(4)
                    self._info("Click en Compartir ejecutado.")
                    return True

            self._warning("No se pudo dar click en Compartir después de varios intentos.")
            return False

        except Exception as e:
            self._warning("Error dando click en Compartir: %r", e)
            return False

    def instagram_publish_error_visible(self) -> bool:
        try:
            body_text = self.browser.driver.find_element(By.TAG_NAME, "body").text or ""
            body_lower = body_text.lower()

            return any(
                pattern.lower() in body_lower
                for pattern in InstagramPostLocators.PUBLISH_ERROR_TEXTS
            )

        except Exception:
            return False

    # =========================================================
    # LOW LEVEL HELPERS
    # =========================================================
    def _normalize_media_paths(self, media_paths: list[str]) -> list[str]:
        valid_paths = []

        for path in media_paths or []:
            if path and os.path.exists(path):
                valid_paths.append(os.path.abspath(path))

        return valid_paths

    def _get_visible_elements(self, xpath: str):
        try:
            elements = self.browser.driver.find_elements(By.XPATH, xpath)
            visible = []

            for el in elements:
                try:
                    if el.is_displayed():
                        visible.append(el)
                except Exception:
                    continue

            return visible

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

    def _try_click_element(self, element, label: str = "element") -> bool:
        try:
            try:
                element.click()
                print(f"[post] click normal en {label} ok")
                return True
            except Exception as e:
                print(f"[post] click normal en {label} falló: {e}")

            try:
                ActionChains(self.browser.driver).move_to_element(element).pause(
                    0.2
                ).click().perform()
                print(f"[post] ActionChains click en {label} ok")
                return True
            except Exception as e:
                print(f"[post] ActionChains click en {label} falló: {e}")

            try:
                self.browser.driver.execute_script("arguments[0].click();", element)
                print(f"[post] JS click en {label} ok")
                return True
            except Exception as e:
                print(f"[post] JS click en {label} falló: {e}")

            return False

        except Exception:
            return False

    def _open_url(self, url: str) -> None:
        try:
            if hasattr(self.browser, "go_to_url"):
                self.browser.go_to_url(url)
                return
        except Exception:
            pass

        self.browser.driver.get(url)

    def _sleep(self, seconds: float) -> None:
        try:
            if hasattr(self.browser, "time_sleep"):
                self.browser.time_sleep(seconds)
            else:
                time.sleep(seconds)
        except Exception:
            time.sleep(seconds)

    def _is_visible(self, xpath: str) -> bool:
        try:
            if hasattr(self.browser, "is_visible"):
                return bool(self.browser.is_visible(xpath))

            elements = self.browser.driver.find_elements(By.XPATH, xpath)
            return any(el.is_displayed() for el in elements)

        except Exception:
            return False

    def _click_xpath(self, xpath: str, time_x: int = 10, scroll: bool = False) -> bool:
        try:
            if hasattr(self.browser, "click"):
                return bool(
                    self.browser.click(
                        xpath,
                        timeX=time_x,
                        scroll=scroll,
                        error=False,
                        hover=False,
                    )
                )

            elements = self.browser.driver.find_elements(By.XPATH, xpath)
            for el in elements:
                try:
                    if not el.is_displayed():
                        continue

                    if scroll:
                        self._scroll_into_view(el)

                    return self._try_click_element(el, label=xpath)

                except Exception:
                    continue

            return False

        except Exception:
            return False

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