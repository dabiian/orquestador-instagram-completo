import random
from typing import Optional

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.keys import Keys

from app.utils.logger import get_logger
from app.config.locators.instagram_post_interaction_locators import (
    InstagramPostInteractionLocators,
)


class InstagramPostInteractionService:
    """
    Servicio centralizado para interactuar con un post abierto:
    - detectar like
    - dar like
    - comentar
    - responder
    - compartir/repost

    No debe depender de locators de followers.
    No debe tener scripts JS quemados dentro del servicio.
    """

    def __init__(self, browser, logger=None):
        self.browser = browser
        self.log = logger or get_logger(self.__class__.__name__)

    # =========================================================
    # BROWSER WRAPPERS
    # =========================================================
    def _execute_script_safe(self, script: str, *args):
        if hasattr(self.browser, "execute_script_safe"):
            return self.browser.execute_script_safe(script, *args)

        if hasattr(self.browser, "execute_script"):
            return self.browser.execute_script(script, *args)

        if hasattr(self.browser, "driver"):
            return self.browser.driver.execute_script(script, *args)

        raise AttributeError(
            f"Browser wrapper ({self.browser.__class__.__name__}) "
            f"does not expose execute_script_safe, execute_script, or driver"
        )

    def _get_elements_safe(self, locator, time_x: int = 8):
        if hasattr(self.browser, "get_elements_safe"):
            return self.browser.get_elements_safe(locator, time_x=time_x)

        if hasattr(self.browser, "obtener_elementos"):
            return self.browser.obtener_elementos(locator, time_x=time_x)

        if hasattr(self.browser, "_get"):
            return self.browser._get(locator, time_x=time_x)

        raise AttributeError(
            f"Browser wrapper ({self.browser.__class__.__name__}) "
            f"does not expose get_elements_safe, obtener_elementos, or _get"
        )

    # =========================================================
    # LIKE
    # =========================================================
    def get_post_like_state_js(self) -> str:
        """
        Returns:
        - liked
        - not_liked
        - unknown
        """
        try:
            state = self._execute_script_safe(
                InstagramPostInteractionLocators.GET_POST_LIKE_STATE_SCRIPT
            )

            state = (state or "unknown").strip().lower()

            self.log.info("Detected like state via JS: %s", state)

            if state in ("liked", "not_liked"):
                return state

            return "unknown"

        except Exception as e:
            self.log.warning("Error getting like state via JS: %r", e)
            return "unknown"

    def has_post_like(self) -> Optional[bool]:
        """
        Returns:
        - True  -> already liked
        - False -> not liked yet
        - None  -> could not determine
        """
        try:
            state = self.get_post_like_state_js()

            if state == "liked":
                return True

            if state == "not_liked":
                return False

            return None

        except Exception as e:
            self.log.warning("Error validating post like state: %r", e)
            return None

    def like_current_post(self) -> bool:
        """
        Click en el botón principal de like del post abierto.
        """
        try:
            state = self.get_post_like_state_js()

            if state == "liked":
                self.log.info("Post already had a like.")
                return True

            if state != "not_liked":
                self.log.warning("Could not determine current like state.")
                return False

            clicked = self._execute_script_safe(
                InstagramPostInteractionLocators.CLICK_POST_LIKE_SCRIPT
            )

            if not clicked:
                self.log.warning("Could not click the main like button.")
                return False

            self.browser.time_sleep(2)

            final_state = self.get_post_like_state_js()

            if final_state == "liked":
                self.log.info("Like was applied successfully.")
                return True

            self.log.warning("Like was attempted but final state is not liked.")
            return False

        except Exception as e:
            self.log.warning("Error while liking current post: %r", e)
            return False

    # =========================================================
    # COMMENT - JS INSERTION
    # =========================================================
    def write_comment_with_emojis_js(self, comment_text: str) -> bool:
        """
        Inserta texto en caja de comentario usando JS.
        Soporta emojis y dispara eventos para que Instagram active el botón publicar.
        """
        try:
            comment_text = str(comment_text or "").strip()

            if not comment_text:
                self.log.warning("Comment text vacío.")
                return False

            comment_box = self._get_first_comment_box()

            if comment_box is None:
                self.log.warning("Comment textarea was not found.")
                return False

            final_value = self._execute_script_safe(
                InstagramPostInteractionLocators.WRITE_TEXT_TO_COMMENT_BOX_SCRIPT,
                comment_box,
                comment_text,
            )

            if final_value is None:
                self.log.warning("Comment insertion script did not return any value.")
                return False

            final_value = str(final_value).strip()
            expected_value = str(comment_text).strip()

            if final_value != expected_value:
                self.log.warning(
                    "Textarea value mismatch. Expected=%s | Actual=%s",
                    expected_value,
                    final_value,
                )
                return False

            self.log.info("Comment text inserted successfully via JS.")
            return True

        except Exception as e:
            self.log.warning("Error while writing comment with JS: %r", e)
            return False

    def _confirm_comment_visible(self, comment_text: str, attempts: int = 4) -> bool:
        """Confirm a published comment even when Instagram requires comment-area scrolling.

        Instagram frequently renders the newest comment outside the currently visible
        viewport.  A viewport-only DOM query can therefore produce a false negative
        after a successful publish.  Each verification pass searches the current DOM
        and progressively scrolls the likely comment containers (dialog/article
        scrollboxes plus the document) before checking again.  Scrolling is only a
        verification aid; it never clicks Publish again.
        """
        expected = " ".join(str(comment_text or "").split()).strip().lower()
        if not expected:
            return False

        script = r"""
        return (() => {
            const expected = String(arguments[0] || '').replace(/\s+/g, ' ').trim().toLowerCase();
            if (!expected) return false;

            const normalize = (value) => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
            const matches = () => {
                const roots = [];
                const article = document.querySelector('article');
                if (article) roots.push(article);
                const dialogs = [...document.querySelectorAll('[role="dialog"]')];
                roots.push(...dialogs);
                roots.push(document);

                for (const root of roots) {
                    const nodes = root.querySelectorAll
                        ? root.querySelectorAll('li, span[dir="auto"], div[dir="auto"]')
                        : [];
                    for (const node of nodes) {
                        const text = normalize(node.textContent);
                        if (text === expected || text.includes(expected)) return true;
                    }
                }
                return false;
            };

            if (matches()) return true;

            // Prefer containers that actually scroll.  Instagram may place the
            // comment list in a dialog/div with overflow:auto while the page itself
            // remains stationary.
            const roots = [];
            const article = document.querySelector('article');
            if (article) roots.push(article);
            const visibleDialogs = [...document.querySelectorAll('[role="dialog"]')].filter(el => {
                const r = el.getBoundingClientRect();
                const st = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && st.display !== 'none' && st.visibility !== 'hidden';
            });
            roots.push(...visibleDialogs);

            const scrollables = [];
            for (const root of roots) {
                const elements = [root, ...(root.querySelectorAll ? root.querySelectorAll('div, section, ul, ol') : [])];
                for (const el of elements) {
                    const st = getComputedStyle(el);
                    const canScrollY = el.scrollHeight > el.clientHeight + 8;
                    const overflowY = st.overflowY === 'auto' || st.overflowY === 'scroll';
                    if (canScrollY && (overflowY || el.clientHeight > 0)) scrollables.push(el);
                }
            }

            // Scroll the deepest/smallest scrollboxes first: these are more
            // likely to be Instagram's comment list than the whole page.
            scrollables.sort((a, b) => a.clientHeight - b.clientHeight);
            for (const el of scrollables.slice(0, 6)) {
                const step = Math.max(240, Math.floor(el.clientHeight * 0.8));
                el.scrollTop = Math.min(el.scrollTop + step, el.scrollHeight);
            }

            window.scrollBy(0, Math.max(240, Math.floor(window.innerHeight * 0.75)));
            return matches();
        })();
        """

        for attempt in range(1, attempts + 1):
            try:
                if self._execute_script_safe(script, expected):
                    self.log.info(
                        "Comment publish confirmed in rendered post (including scroll) | attempt=%s",
                        attempt,
                    )
                    return True
            except Exception:
                pass
            if attempt < attempts:
                self.browser.time_sleep(1.2)

        self.log.warning(
            "Comment publish click occurred but rendered comment was not confirmed after DOM search/scroll."
        )
        return False

    def comment_current_post(self, comment_text: str) -> bool:
        """
        Publica un comentario de forma idempotente.

        Regla crítica: después de un click de Publicar no se vuelve a
        escribir/republicar automáticamente salvo que se compruebe que el
        mismo texto sigue presente en la caja. Esto evita duplicados cuando
        Instagram acepta el click pero tarda en renderizar el comentario.
        """
        comment_text = str(comment_text or "").strip()
        if not comment_text:
            self.log.warning("Comment text vacío.")
            return False

        for attempt in range(1, 4):
            try:
                # Nunca reutilizar un WebElement después de un re-render.
                comment_box = self._get_first_comment_box()
                if comment_box is None:
                    self.log.warning("Comment textarea could not be obtained | attempt=%s", attempt)
                    return False

                self._focus_element_safe(comment_box)
                self.browser.time_sleep(0.8)

                # Antes de escribir, comprobar si el comentario ya quedó
                # renderizado. Esto hace la operación idempotente.
                if self._confirm_comment_visible(comment_text, attempts=2):
                    self.log.info("Comment already rendered before publish | no duplicate click.")
                    return True

                wrote_comment = self.write_comment_with_emojis_js(comment_text)
                if not wrote_comment:
                    self.log.warning("Could not insert comment text with JS | attempt=%s", attempt)
                    continue

                self.browser.time_sleep(1.5)

                # Volver a obtener la caja: el DOM de Instagram puede haber
                # cambiado al activar el estado de publicación.
                fresh_box = self._get_first_comment_box()
                if fresh_box is None:
                    self.log.warning("Comment box disappeared before publish | attempt=%s", attempt)
                    return False

                clicked_publish = self._click_publish_button_near_comment_box(fresh_box)
                if not clicked_publish:
                    self.log.warning("No se pudo hacer click real en Publicar/Post asociado al comment box.")
                    # Solo reintentamos si la caja sigue conteniendo el texto.
                    if self._comment_box_contains_text(comment_text):
                        continue
                    return False

                self.log.info("[comment-publish] click enviado | attempt=%s", attempt)

                # Tras el click, jamás repetir de inmediato. Esperar primero
                # a que aparezca el comentario o que la caja sea vaciada.
                confirmed = self._confirm_comment_visible(comment_text, attempts=6)
                if confirmed:
                    self.log.info("[comment-publish] comentario confirmado | attempt=%s", attempt)
                    return True

                if self._confirm_comment_box_empty():
                    # Instagram can accept the publish action and clear the
                    # editor before the new comment becomes visible in the
                    # rendered DOM. The click + cleared editor is our
                    # deterministic acceptance signal. Never publish again:
                    # a second click here can create a duplicate comment.
                    self.log.info(
                        "[comment-publish] submit aceptado y editor vacío; "
                        "se marca como publicado sin retry para evitar duplicados."
                    )
                    return True

                # Si el texto sigue inequívocamente en la caja, el click no
                # produjo submit. En ese único caso se permite un reintento.
                if self._comment_box_contains_text(comment_text):
                    self.log.warning(
                        "[comment-publish] el texto sigue en la caja; se permite retry | attempt=%s",
                        attempt,
                    )
                    continue

                self.log.warning(
                    "[comment-publish] estado indeterminado después de publicar; "
                    "NO se reintenta para evitar duplicados."
                )
                return False

            except StaleElementReferenceException:
                self.log.warning(
                    "DOM re-rendered while commenting | attempt=%s. Se reobtendrán elementos.",
                    attempt,
                )
                self.browser.time_sleep(0.8)
                # Si el comentario ya se publicó, no hacer otro click.
                if self._confirm_comment_visible(comment_text, attempts=2):
                    return True
                continue
            except Exception as e:
                self.log.warning("Error while commenting current post | attempt=%s | error=%r", attempt, e)
                return False

        self.log.warning("Could not publish comment after safe retries (sin duplicar).")
        return False

    def _comment_box_contains_text(self, comment_text: str) -> bool:
        expected = " ".join(str(comment_text or "").split()).strip().lower()
        if not expected:
            return False
        try:
            box = self._get_first_comment_box()
            if box is None:
                return False
            actual = self._read_comment_box_text(box)
            return expected in " ".join(str(actual or "").split()).strip().lower()
        except Exception:
            return False

    def _confirm_comment_box_empty(self) -> bool:
        try:
            box = self._get_first_comment_box()
            if box is None:
                return False
            return not self._read_comment_box_text(box).strip()
        except Exception:
            return False

    # =========================================================
    # COMMENT - VISIBLE FLOW
    # =========================================================
    def comment_current_post_visible(self, comment_text: str) -> bool:
        """
        Comenta usando flujo visible.
        Mantiene compatibilidad con tareas que no quieren JS fallback completo.
        """
        try:
            comment_text = str(comment_text or "").strip()

            if not comment_text:
                self.log.warning("Comment text vacío.")
                return False

            for attempt in range(3):
                try:
                    comment_box = self._get_first_comment_box()

                    if comment_box is None:
                        self.log.warning("Comment textarea could not be obtained.")
                        return False

                    self._focus_element_safe(comment_box)
                    self.browser.time_sleep(1)

                    typed_ok = self._type_into_comment_box_visible(
                        comment_box,
                        comment_text,
                    )

                    if not typed_ok:
                        self.log.warning("No se pudo escribir visible el comentario.")
                        continue

                    self.browser.time_sleep(2)

                    clicked_publish = self._click_publish_button_near_comment_box(comment_box)

                    if not clicked_publish:
                        self.log.warning(
                            "No se pudo hacer click real en Publicar/Post asociado al comment box."
                        )
                        continue

                    self.browser.time_sleep(random.randint(2, 4))
                    self.log.info("Comment publish click executed successfully (visible typing).")
                    return True

                except StaleElementReferenceException:
                    self.log.warning(
                        "DOM re-rendered while visible commenting. Retrying attempt=%s",
                        attempt + 1,
                    )
                    self.browser.time_sleep(1)
                    continue

            self.log.warning("Could not publish visible comment after multiple attempts.")
            return False

        except Exception as e:
            self.log.warning("Error en comment_current_post_visible: %r", e)
            return False

    def _type_into_comment_box_visible(self, element, comment_text: str) -> bool:
        try:
            comment_text = str(comment_text or "").strip()

            if not comment_text:
                return False

            try:
                self._execute_script_safe(
                    InstagramPostInteractionLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    element,
                )
                self.browser.time_sleep(random.uniform(0.3, 0.6))
            except Exception:
                pass

            self._focus_element_safe(element)

            self.browser.time_sleep(random.uniform(0.5, 1.0))

            final_value = self._execute_script_safe(
                InstagramPostInteractionLocators.TYPE_INTO_COMMENT_BOX_VISIBLE_SCRIPT,
                element,
                comment_text,
            )

            final_value = str(final_value or "").strip()

            if not final_value:
                self.log.warning("No quedó texto visible en la caja de comentario.")
                return False

            if comment_text not in final_value:
                self.log.warning(
                    "El texto del comentario no quedó visible. final_value=%r",
                    final_value,
                )
                return False

            self.log.info("Comment text inserted via JS (visible flow).")
            return True

        except Exception as e:
            self.log.warning("Error escribiendo visible en comment box: %r", e)
            return False

    # =========================================================
    # REPLY VISIBLE
    # =========================================================
    def reply_current_post_visible(self, reply_text: str) -> bool:
        """
        Responde un comentario/reply sin borrar el prefijo que Instagram deja.
        Ejemplo:
        '@usuario '
        """
        try:
            reply_text = str(reply_text or "").strip()

            if not reply_text:
                self.log.warning("Reply text vacío.")
                return False

            for attempt in range(3):
                try:
                    comment_box = self._get_first_comment_box()

                    if comment_box is None:
                        self.log.warning("Reply textarea could not be obtained.")
                        return False

                    self._focus_element_safe(comment_box)
                    self.browser.time_sleep(1)

                    typed_ok = self._type_into_reply_box_preserving_prefix(
                        comment_box,
                        reply_text,
                    )

                    if not typed_ok:
                        self.log.warning("No se pudo escribir visible el reply.")
                        continue

                    self.browser.time_sleep(2)

                    clicked_publish = self._click_publish_button_near_comment_box(comment_box)

                    if not clicked_publish:
                        self.log.warning(
                            "No se pudo hacer click real en Publicar/Post asociado al reply box."
                        )
                        continue

                    self.browser.time_sleep(random.randint(2, 4))
                    self.log.info("Reply publish click executed successfully.")
                    return True

                except StaleElementReferenceException:
                    self.log.warning(
                        "DOM re-rendered while visible replying. Retrying attempt=%s",
                        attempt + 1,
                    )
                    self.browser.time_sleep(1)
                    continue

            self.log.warning("Could not publish visible reply after multiple attempts.")
            return False

        except Exception as e:
            self.log.warning("Error en reply_current_post_visible: %r", e)
            return False

    def _type_into_reply_box_preserving_prefix(self, element, reply_text: str) -> bool:
        """
        Conserva el prefijo que Instagram deja al responder.
        Ejemplo:
        '@usuario '
        y escribe el reply a continuación.
        """
        try:
            reply_text = str(reply_text or "").strip()

            if not reply_text:
                return False

            self._focus_element_safe(element)

            self.browser.time_sleep(random.uniform(0.4, 0.8))

            current_value = self._read_comment_box_text(element)
            current_value = str(current_value or "")

            self.log.info(
                "Reply box current_value antes de escribir: %r",
                current_value,
            )

            if reply_text and reply_text in current_value:
                self.log.info("El reply ya parece estar escrito en la caja.")
                return True

            try:
                element.send_keys(Keys.END)
                self.browser.time_sleep(0.2)
            except Exception:
                pass

            if current_value and not current_value.endswith((" ", "\n")):
                try:
                    element.send_keys(" ")
                    self.browser.time_sleep(random.uniform(0.05, 0.12))
                except Exception:
                    pass

            for ch in reply_text:
                element.send_keys(ch)
                self.browser.time_sleep(random.uniform(0.02, 0.06))

            final_value = self._read_comment_box_text(element)
            final_value = str(final_value or "")

            self.log.info(
                "Reply box final_value después de escribir: %r",
                final_value,
            )

            if reply_text not in final_value:
                self.log.warning(
                    "El texto del reply no quedó visible en la caja. final_value=%r",
                    final_value,
                )
                return False

            self.log.info("Reply text inserted visibly preserving existing prefix.")
            return True

        except Exception as e:
            self.log.warning(
                "Error escribiendo visible en reply box preservando prefijo: %r",
                e,
            )
            return False

    # =========================================================
    # SHARE / REPOST
    # =========================================================
    def share_current_post(self) -> bool:
        """
        Hace click en el botón principal de Republicar/Repost usando JS.
        """
        try:
            clicked = self._execute_script_safe(
                InstagramPostInteractionLocators.SHARE_CURRENT_POST_SCRIPT
            )

            if not clicked:
                self.log.warning("Could not click the main repost button.")
                return False

            self.browser.time_sleep(2)

            self.log.info("Repost was attempted successfully.")
            return True

        except Exception as e:
            self.log.warning("Error while reposting current post: %r", e)
            return False

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================
    def _get_first_comment_box(self):
        try:
            comment_boxes = self._get_elements_safe(
                InstagramPostInteractionLocators.POST_COMMENT_BOX,
                time_x=8,
            )

            if not comment_boxes:
                return None

            for box in comment_boxes:
                try:
                    if box.is_displayed() and box.is_enabled():
                        return box
                except Exception:
                    continue

            return comment_boxes[0]

        except Exception:
            return None

    def _get_first_publish_button(self):
        try:
            publish_buttons = self._get_elements_safe(
                InstagramPostInteractionLocators.POST_COMMENT_PUBLISH_ENABLED,
                time_x=4,
            )

            if not publish_buttons:
                publish_buttons = self._get_elements_safe(
                    InstagramPostInteractionLocators.POST_COMMENT_PUBLISH,
                    time_x=4,
                )

            if not publish_buttons:
                return None

            for button in publish_buttons:
                try:
                    if button.is_displayed() and button.is_enabled():
                        return button
                except Exception:
                    continue

            return publish_buttons[0]

        except Exception:
            return None

    def _focus_element_safe(self, element) -> bool:
        try:
            try:
                self._execute_script_safe(
                    InstagramPostInteractionLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    element,
                )
            except Exception:
                pass

            try:
                element.click()
                return True
            except Exception:
                pass

            try:
                self._execute_script_safe(
                    InstagramPostInteractionLocators.CLICK_ELEMENT_SCRIPT,
                    element,
                )
                return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    def _click_element_safe(self, element) -> bool:
        try:
            try:
                element.click()
                return True
            except Exception:
                pass

            try:
                self._execute_script_safe(
                    InstagramPostInteractionLocators.CLICK_ELEMENT_SCRIPT,
                    element,
                )
                return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    def _read_comment_box_text(self, element) -> str:
        try:
            text = self._execute_script_safe(
                InstagramPostInteractionLocators.READ_INPUT_TEXT_SCRIPT,
                element,
            )

            return str(text or "").strip()

        except Exception:
            return ""
        

    def _click_publish_button_near_comment_box(self, comment_box) -> bool:
        """
        Click real sobre el botón Publicar/Post asociado a la caja de comentario.
        No usa el primer botón global que aparezca.
        """
        try:
            if comment_box is None:
                self.log.warning("No hay comment_box para buscar botón publicar cercano.")
                return False

            result = self._execute_script_safe(
                InstagramPostInteractionLocators.CLICK_PUBLISH_BUTTON_NEAR_COMMENT_BOX_SCRIPT,
                comment_box,
            )

            self.log.info("Publish near comment box result: %s", result)

            if not result or not result.get("ok"):
                self.log.warning("No se pudo clickear botón publicar cercano: %s", result)
                return False

            return True

        except Exception as e:
            self.log.warning("Error clickeando botón publicar cercano: %r", e)
            return False