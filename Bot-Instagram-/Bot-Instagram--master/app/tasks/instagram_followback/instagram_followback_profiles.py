import random

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from app.config.locators.instagram_followback_locators import (
    InstagramFollowbackLocators,
)


class InstagramFollowbackProfilesMixin:
    def _open_profile_follow_and_return(self, comment: dict, post_href: str) -> str:
        """
        Retorna:
        - 'followed'
        - 'already_following'
        - 'failed'

        Nota:
        - `post_href` se conserva en la firma para no romper compatibilidad
          con el flujo actual, aunque aquí no se use directamente.
        """
        try:
            profile_href = (comment.get("profile_href") or "").strip()

            if not profile_href:
                return "failed"

            print(f"[followback] abriendo perfil directo: {profile_href}")

            self.browser.driver.get(profile_href)
            self.browser.time_sleep(random.uniform(3.0, 4.8))

            if not self._is_profile_page_open(profile_href):
                print(f"[followback] no se confirmó apertura del perfil: {profile_href}")
                return "failed"

            self.browser.time_sleep(random.uniform(1.5, 2.8))

            if self._is_already_following_current_profile():
                print(f"[followback] ya se seguía el perfil: {profile_href}")
                return "already_following"

            if self._click_follow_current_profile():
                self.browser.time_sleep(random.uniform(1.8, 3.0))
                print(f"[followback] follow realizado correctamente: {profile_href}")
                return "followed"

            print(f"[followback] no se pudo seguir el perfil: {profile_href}")
            return "failed"

        except Exception as e:
            print(f"[followback] error en open_profile_follow_and_return: {e}")
            return "failed"

    def _click_follow_current_profile(self) -> bool:
        try:
            follow_buttons = self.browser.driver.find_elements(
                By.XPATH,
                InstagramFollowbackLocators.PROFILE_FOLLOW_BUTTON,
            )

            visible_buttons = []

            for btn in follow_buttons:
                try:
                    if btn.is_displayed() and btn.is_enabled():
                        visible_buttons.append(btn)
                except Exception:
                    continue

            print(f"[followback] botones Follow/Seguir encontrados: {len(visible_buttons)}")

            if not visible_buttons:
                return False

            follow_btn = visible_buttons[0]

            try:
                self.browser.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                    follow_btn,
                )
            except Exception:
                pass

            self.browser.time_sleep(random.uniform(0.6, 1.1))

            if self._click_follow_button(follow_btn):
                self.browser.time_sleep(random.uniform(2.5, 4.0))
                return self._is_already_following_current_profile()

            return False

        except Exception as e:
            print(f"[followback] error haciendo click en Follow/Seguir: {e}")
            return False

    def _click_follow_button(self, follow_btn) -> bool:
        """
        Click centralizado para el botón Follow/Seguir.
        Mantiene los mismos fallback clicks del flujo anterior:
        - click normal
        - ActionChains
        - JS click
        """
        try:
            try:
                follow_btn.click()
                return True
            except Exception:
                pass

            try:
                ActionChains(self.browser.driver).move_to_element(follow_btn).pause(
                    random.uniform(0.2, 0.5)
                ).click().perform()
                return True
            except Exception:
                pass

            try:
                self.browser.driver.execute_script("arguments[0].click();", follow_btn)
                return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    def _is_already_following_current_profile(self) -> bool:
        try:
            elems = self.browser.driver.find_elements(
                By.XPATH,
                InstagramFollowbackLocators.PROFILE_FOLLOWING_STATE_BUTTON,
            )

            visible = []

            for el in elems:
                try:
                    if el.is_displayed():
                        visible.append(el)
                except Exception:
                    continue

            print(f"[followback] botones de estado Following/Siguiendo encontrados: {len(visible)}")
            return bool(visible)

        except Exception:
            return False