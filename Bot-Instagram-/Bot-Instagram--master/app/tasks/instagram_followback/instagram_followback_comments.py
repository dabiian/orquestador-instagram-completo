import random
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from app.config.locators.instagram_followback_locators import (
    InstagramFollowbackLocators,
)


class InstagramFollowbackCommentsMixin:
    def _get_visible_comments(self) -> list[dict]:
        try:
            items = self.browser.driver.find_elements(
                By.XPATH,
                InstagramFollowbackLocators.COMMENT_ITEMS,
            )

            print(f"[followback] comentarios visibles encontrados: {len(items)}")

            if not items:
                self.log.warning("No se encontraron comentarios visibles.")
                return []

            comments = []

            for idx, item in enumerate(items, start=1):
                try:
                    username = ""
                    text = ""
                    permalink = ""
                    time_text = ""
                    profile_href = ""
                    has_reply_button = False
                    has_options = False
                    username_el = None

                    try:
                        username_el = item.find_element(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_USERNAME_REL,
                        )
                        username = (username_el.text or "").strip()
                        profile_href = (username_el.get_attribute("href") or "").strip()
                    except Exception:
                        username = ""
                        profile_href = ""

                    try:
                        text_el = item.find_element(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_TEXT_REL,
                        )
                        text = (text_el.text or "").strip()
                    except Exception:
                        text = ""

                    try:
                        permalink_el = item.find_element(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_PERMALINK_REL,
                        )
                        permalink = (permalink_el.get_attribute("href") or "").strip()
                    except Exception:
                        permalink = ""

                    try:
                        time_el = item.find_element(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_TIME_REL,
                        )
                        time_text = (time_el.text or "").strip()
                    except Exception:
                        time_text = ""

                    try:
                        reply_btns = item.find_elements(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_REPLY_BUTTON_REL,
                        )
                        has_reply_button = bool(reply_btns)
                    except Exception:
                        has_reply_button = False

                    try:
                        option_btns = item.find_elements(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_OPTIONS_REL,
                        )
                        has_options = bool(option_btns)
                    except Exception:
                        has_options = False

                    if not username and not text:
                        continue

                    try:
                        root_comment_el = item.find_element(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_ROOT_REL,
                        )
                    except Exception:
                        root_comment_el = item

                    comment_data = {
                        "index": idx,
                        "username": username,
                        "text": text,
                        "profile_href": profile_href,
                        "permalink": permalink,
                        "time_text": time_text,
                        "has_reply_button": has_reply_button,
                        "has_options": has_options,
                        "username_element": username_el,
                        "element": root_comment_el,
                    }

                    print(
                        f"[followback] comentario #{idx} | "
                        f"username={username} | text={text} | "
                        f"profile_href={profile_href} | reply={has_reply_button}"
                    )

                    comments.append(comment_data)

                except Exception as e:
                    print(f"[followback] error leyendo comentario #{idx}: {e}")
                    continue

            self.log.info("Comentarios visibles procesados: %s", len(comments))
            return comments

        except Exception as e:
            self.log.warning("Error obteniendo comentarios visibles: %r", e)
            return []

    def _find_visible_comment_again(self, original_comment: dict) -> Optional[dict]:
        try:
            target_permalink = (original_comment.get("permalink") or "").strip()
            target_profile_href = (original_comment.get("profile_href") or "").strip()
            target_text = self._normalize_text(original_comment.get("text") or "")

            fresh_comments = self._get_visible_comments()
            if not fresh_comments:
                return None

            for comment in fresh_comments:
                permalink = (comment.get("permalink") or "").strip()
                if target_permalink and permalink == target_permalink:
                    return comment

            for comment in fresh_comments:
                profile_href = (comment.get("profile_href") or "").strip()
                if target_profile_href and profile_href == target_profile_href:
                    return comment

            for comment in fresh_comments:
                text = self._normalize_text(comment.get("text") or "")
                if target_text and text == target_text:
                    return comment

            return None

        except Exception as e:
            print(f"[followback] error buscando nuevamente el comentario: {e}")
            return None

    def _click_reply_on_comment(self, comment: dict) -> bool:
        try:
            comment_el = comment.get("element")
            if comment_el is None:
                return False

            try:
                self.browser.driver.execute_script(
                    InstagramFollowbackLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    comment_el,
                )
            except Exception:
                pass

            self.browser.time_sleep(random.uniform(0.8, 1.4))

            reply_buttons = comment_el.find_elements(
                By.XPATH,
                InstagramFollowbackLocators.COMMENT_REPLY_BUTTON_REL,
            )

            visible_buttons = []

            for btn in reply_buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        visible_buttons.append(btn)
                except Exception:
                    continue

            print(f"[followback] botones reply visibles en comentario: {len(visible_buttons)}")

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
                    InstagramFollowbackLocators.CLICK_ELEMENT_SCRIPT,
                    reply_btn,
                )
                self.browser.time_sleep(2)
                return True
            except Exception:
                pass

            return False

        except Exception as e:
            print(f"[followback] error haciendo click en reply: {e}")
            return False

    def _find_reply_input_box(self):
        for xpath in InstagramFollowbackLocators.REPLY_INPUT_BOXES:
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
            input_box = self._find_reply_input_box()

            if input_box is None:
                print("[followback] no se encontró input para responder comentario")
                return False

            try:
                self.browser.driver.execute_script(
                    InstagramFollowbackLocators.SCROLL_INTO_VIEW_CENTER_SCRIPT,
                    input_box,
                )
            except Exception:
                pass

            self.browser.time_sleep(random.uniform(0.8, 1.2))

            try:
                input_box.click()
            except Exception:
                try:
                    ActionChains(self.browser.driver).move_to_element(input_box).pause(0.2).click().perform()
                except Exception:
                    return False

            self.browser.time_sleep(1)

            if not self._write_reply_text_preserving_mention_js(input_box, reply_text):
                print("[followback] no se pudo escribir reply preservando @usuario")
                return False

            self.browser.time_sleep(1.2)

            for xpath in InstagramFollowbackLocators.REPLY_SUBMIT_BUTTONS:
                try:
                    buttons = self.browser.driver.find_elements(By.XPATH, xpath)

                    for btn in buttons:
                        try:
                            if btn.is_displayed() and btn.is_enabled():
                                btn.click()
                                self.browser.time_sleep(2)
                                return True
                        except Exception:
                            continue

                except Exception:
                    continue

            return False

        except Exception as e:
            print(f"[followback] error enviando texto de reply: {e}")
            return False

    def _click_like_on_comment(self, comment: dict) -> bool:
        try:
            profile_href = (comment.get("profile_href") or "").strip()
            permalink = (comment.get("permalink") or "").strip()

            if not profile_href:
                print("[followback] no hay profile_href para buscar like")
                return False

            result = self.browser.driver.execute_script(
                InstagramFollowbackLocators.CLICK_LIKE_ON_COMMENT_SCRIPT,
                profile_href,
                permalink,
            )

            print(f"[followback] resultado like js: {result}")

            return bool(result and result.get("ok"))

        except Exception as e:
            print(f"[followback] error dando like al comentario: {e}")
            return False

    def _reply_to_followback_comment(self, original_comment: dict, post_href: str) -> bool:
        try:
            if not self._reopen_post_for_reply(post_href):
                print("[followback] no se pudo reabrir el post antes de responder")
                return False

            fresh_comment = self._prepare_comments_after_reopen_for_reply(
                original_comment=original_comment,
                max_rounds=6,
                min_comments_goal=35,
            )

            if not fresh_comment:
                print("[followback] no se encontró nuevamente el comentario para responder")
                return False

            like_ok = self._click_like_on_comment(fresh_comment)
            print(f"[followback] like al comentario: {like_ok}")

            if not self._click_reply_on_comment(fresh_comment):
                print("[followback] no se pudo pulsar reply en el comentario")
                return False

            reply_text = self._build_followback_reply(fresh_comment.get("text") or "")
            print(f"[followback] reply generado: {reply_text}")

            return self._submit_reply_text(reply_text)

        except Exception as e:
            print(f"[followback] error respondiendo comentario followback: {e}")
            return False

    def _get_visible_comments_texts(self, comments: list[dict]) -> list[str]:
        try:
            texts = []

            for comment in comments:
                text = (comment.get("text") or "").strip()

                if text:
                    texts.append(text)

            print(f"[followback] textos de comentarios obtenidos: {len(texts)}")
            return texts

        except Exception as e:
            self.log.warning("Error obteniendo textos de comentarios: %r", e)
            return []

    def _click_load_more_comments_button(self) -> bool:
        try:
            result = self.browser.driver.execute_script(
                InstagramFollowbackLocators.CLICK_LOAD_MORE_COMMENTS_SCRIPT
            )

            print(f"[followback] resultado click cargar más comentarios: {result}")

            if result and result.get("ok"):
                self.browser.time_sleep(random.uniform(1.2, 2.0))
                return True

            return False

        except Exception as e:
            print(f"[followback] error en _click_load_more_comments_button: {e}")
            return False

    def _scroll_last_visible_comment(self) -> bool:
        try:
            comments = self._get_visible_comments()

            if not comments:
                return False

            last_comment_el = comments[-1].get("element")

            if last_comment_el is None:
                return False

            self.browser.driver.execute_script(
                InstagramFollowbackLocators.SCROLL_INTO_VIEW_END_SCRIPT,
                last_comment_el,
            )

            self.browser.time_sleep(random.uniform(1.0, 1.8))
            return True

        except Exception as e:
            print(f"[followback] error haciendo scroll al último comentario: {e}")
            return False

    def _get_expanded_comments_for_candidates(
        self,
        max_rounds: int = 6,
        min_comments_goal: int = 35,
    ) -> list[dict]:
        try:
            best_comments = self._get_visible_comments()
            best_count = len(best_comments)

            print(f"[followback] comentarios iniciales para candidatos: {best_count}")

            stagnation = 0

            for round_idx in range(1, max_rounds + 1):
                clicked = self._click_load_more_comments_button()
                scrolled = self._scroll_last_visible_comment()

                fresh_comments = self._get_visible_comments()
                fresh_count = len(fresh_comments)

                print(
                    f"[followback] expansión comentarios ronda {round_idx}/{max_rounds} | "
                    f"antes={best_count} | ahora={fresh_count} | clicked={clicked} | scrolled={scrolled}"
                )

                if fresh_count > best_count:
                    best_comments = fresh_comments
                    best_count = fresh_count
                    stagnation = 0
                else:
                    stagnation += 1

                if best_count >= min_comments_goal:
                    break

                if stagnation >= 2 and not clicked:
                    break

            print(f"[followback] comentarios finales para candidatos: {best_count}")
            return best_comments

        except Exception as e:
            print(f"[followback] error ampliando comentarios para candidatos: {e}")
            return self._get_visible_comments()

    def _prepare_comments_after_reopen_for_reply(
        self,
        original_comment: dict,
        max_rounds: int = 6,
        min_comments_goal: int = 35,
    ) -> Optional[dict]:
        try:
            target_permalink = (original_comment.get("permalink") or "").strip()
            target_profile_href = (original_comment.get("profile_href") or "").strip()

            fresh_comment = self._find_visible_comment_again(original_comment)

            if fresh_comment:
                print("[followback] comentario encontrado inmediatamente tras reabrir")
                return fresh_comment

            best_comments = self._get_visible_comments()
            best_count = len(best_comments)

            print(
                f"[followback] preparando comentarios tras reabrir | "
                f"iniciales={best_count} | target_permalink={target_permalink} | "
                f"target_profile={target_profile_href}"
            )

            for round_idx in range(1, max_rounds + 1):
                clicked = self._click_load_more_comments_button()
                scrolled = self._scroll_last_visible_comment()

                fresh_comment = self._find_visible_comment_again(original_comment)

                if fresh_comment:
                    print(
                        f"[followback] comentario objetivo encontrado tras expansión "
                        f"ronda {round_idx}/{max_rounds}"
                    )
                    return fresh_comment

                fresh_comments = self._get_visible_comments()
                fresh_count = len(fresh_comments)

                if fresh_count > best_count:
                    best_count = fresh_count

                print(
                    f"[followback] expansión tras reabrir ronda {round_idx}/{max_rounds} | "
                    f"comentarios_visibles={fresh_count} | clicked={clicked} | scrolled={scrolled}"
                )

                if fresh_count >= min_comments_goal and not clicked:
                    break

                if not clicked and not scrolled:
                    break

            print("[followback] no reapareció el comentario original tras reabrir")
            return None

        except Exception as e:
            print(f"[followback] error preparando comentarios tras reabrir: {e}")
            return None

    def _find_comment_root_element(
        self,
        *,
        profile_href: str = "",
        permalink: str = "",
        text: str = "",
    ):
        try:
            candidates = self.browser.driver.find_elements(
                By.XPATH,
                InstagramFollowbackLocators.COMMENT_ROOT_FROM_PERMALINK,
            )

            target_text = self._normalize_text(text)

            for el in candidates:
                try:
                    el_text = self._normalize_text(el.text or "")
                    hrefs = [
                        (a.get_attribute("href") or "").strip()
                        for a in el.find_elements(
                            By.XPATH,
                            InstagramFollowbackLocators.COMMENT_ROOT_LINKS_REL,
                        )
                    ]

                    has_profile = bool(profile_href) and any(
                        h.rstrip("/") == profile_href.rstrip("/") for h in hrefs
                    )

                    has_permalink = bool(permalink) and any(
                        h.rstrip("/") == permalink.rstrip("/") for h in hrefs
                    )

                    if has_permalink:
                        return el

                    if has_profile and target_text and target_text in el_text:
                        return el

                    if target_text and target_text in el_text:
                        return el

                except Exception:
                    continue

            return None

        except Exception:
            return None

    def _get_visible_comments_v2(self) -> list[dict]:
        try:
            raw_comments = self.browser.driver.execute_script(
                InstagramFollowbackLocators.VISIBLE_COMMENTS_V2_SCRIPT
            ) or []

            print(f"[own-posts] comentarios visibles encontrados por JS: {len(raw_comments)}")

            if not raw_comments:
                self.log.warning("No se encontraron comentarios visibles.")
                return []

            comments = []

            for idx, item in enumerate(raw_comments, start=1):
                try:
                    username = str(item.get("username") or "").strip()
                    text = str(item.get("text") or "").strip()
                    profile_href = str(item.get("profile_href") or "").strip()
                    permalink = str(item.get("permalink") or "").strip()
                    time_text = str(item.get("time_text") or "").strip()
                    has_reply_button = bool(item.get("has_reply_button"))
                    has_options = bool(item.get("has_options"))

                    root_el = self._find_comment_root_element(
                        profile_href=profile_href,
                        permalink=permalink,
                        text=text,
                    )

                    comment_data = {
                        "index": idx,
                        "username": username,
                        "text": text,
                        "profile_href": profile_href,
                        "permalink": permalink,
                        "time_text": time_text,
                        "has_reply_button": has_reply_button,
                        "has_options": has_options,
                        "username_element": None,
                        "element": root_el,
                    }

                    print(
                        f"[own-posts] comentario #{idx} | "
                        f"username={username} | text={text} | "
                        f"profile_href={profile_href} | reply={has_reply_button}"
                    )

                    comments.append(comment_data)

                except Exception as e:
                    print(f"[own-posts] error leyendo comentario #{idx}: {e}")
                    continue

            self.log.info("Comentarios visibles procesados: %s", len(comments))
            return comments

        except Exception as e:
            self.log.warning("Error obteniendo comentarios visibles: %r", e)
            return []