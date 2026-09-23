import time
from typing import Tuple, Iterable

from app.core.interfaces import IBrowser, IAccountAPI, ILoginService
from app.config.locators import LoginLocators


class LoginService(ILoginService):
    LOGIN_FORM_TIMEOUT = 40
    LOGIN_BUTTON_TIMEOUT = 15
    LOGIN_RESULT_TIMEOUT = 120

    INPUT_WRITE_WAIT = 1
    CONTINUE_BUTTON_WAIT = 2

    POST_CLICK_INITIAL_WAIT = 8
    LOGIN_RESULT_POLL = 2
    STABLE_SUCCESS_REQUIRED = 3
    POST_LOGIN_DIALOG_ATTEMPTS = 8
    DIALOG_CLICK_WAIT = 3

    FINAL_VALIDATION_TIMEOUT = 20
    HUMAN_CONFIRM_AFTER_CLICK_WAIT = 5

    def __init__(
        self,
        browser: IBrowser,
        account_api: IAccountAPI,
        data: dict,
        locators: type = LoginLocators,
    ):
        self.browser = browser
        self.account_api = account_api
        self.data = data
        self.locators = locators

    def login(self, user: str, password: str) -> Tuple[bool, str]:
        try:
            if not self._wait_visible(self.locators.LOGIN_FORM, timeout=self.LOGIN_FORM_TIMEOUT):
                return False, "No apareció el formulario de login de Instagram"

            if self._safe_is_visible(self.locators.CONTINUE_BUTTON):
                self.browser.click(self.locators.CONTINUE_BUTTON)
                time.sleep(self.CONTINUE_BUTTON_WAIT)

            self.browser.write_text(self.locators.USER_INPUT, user, 20)
            time.sleep(self.INPUT_WRITE_WAIT)

            self.browser.write_text(self.locators.PASS_INPUT, password, 20)
            time.sleep(self.INPUT_WRITE_WAIT)

            if self._wait_visible(self.locators.LOGIN_BUTTON_ENABLED, timeout=self.LOGIN_BUTTON_TIMEOUT):
                self.browser.click(self.locators.LOGIN_BUTTON_ENABLED)
            else:
                self.browser.click(self.locators.LOGIN_BUTTON)

            time.sleep(self.POST_CLICK_INITIAL_WAIT)

            login_ok, message = self._wait_login_result(timeout=self.LOGIN_RESULT_TIMEOUT)
            if not login_ok:
                return False, message

            self._dismiss_post_login_dialogs()

            if not self._final_login_validation():
                return False, "El login no quedó estable después del clic en iniciar sesión"

            try:
                account_id = self.data["social_media_account"]["id"]
                cookies = self.browser.get_cookies()
                if cookies:
                    self.account_api.update_cookie(account_id, cookies)
            except Exception:
                pass

            return True, f"Se logueó satisfactoriamente {user}"

        except Exception as e:
            return False, f"Error en login: {str(e)}"

    def _wait_login_result(self, timeout: int = 120) -> Tuple[bool, str]:
        """
        Espera el resultado real del login.
        Maneja:
        - modal 'Confirma que eres una persona'
        - popup guardar info
        - señales visuales de home
        - cookie de sesión aunque no haya xpath visible
        """
        start = time.time()
        stable_success_hits = 0

        while time.time() - start < timeout:
            # 1. Modal intermedio resolvible: NO es error fatal
            if self._handle_human_confirmation_modal():
                stable_success_hits = 0
                time.sleep(self.HUMAN_CONFIRM_AFTER_CLICK_WAIT)
                continue

            # 2. Challenge real/manual
            if self._is_any_visible(self.locators.SECURITY_CHALLENGE):
                return False, "Instagram pidió verificación manual o aprobación de inicio de sesión"

            # 3. Error real de credenciales/login
            if self._is_any_visible(self.locators.LOGIN_ERRORS):
                return False, "Credenciales inválidas o login rechazado por Instagram"

            # 4. Popup guardar info
            if self._is_save_info_popup_visible():
                stable_success_hits += 1
                if stable_success_hits >= self.STABLE_SUCCESS_REQUIRED:
                    return True, "Login exitoso con popup de guardar información"
                time.sleep(self.LOGIN_RESULT_POLL)
                continue

            # 5. Señales visuales reales de post-login
            if self._is_any_visible(self.locators.POST_LOGIN_SUCCESS):
                stable_success_hits += 1
                if stable_success_hits >= self.STABLE_SUCCESS_REQUIRED:
                    return True, "Login exitoso"
            else:
                # 6. Fallback fuerte: si ya no está el login form
                # y ya existe sessionid, cuenta como login correcto
                form_visible = self._safe_is_visible(self.locators.LOGIN_FORM)
                has_session_cookie = self._has_session_cookie()

                if not form_visible and has_session_cookie:
                    stable_success_hits += 1
                    if stable_success_hits >= self.STABLE_SUCCESS_REQUIRED:
                        return True, "Login exitoso por cookie de sesión"
                else:
                    stable_success_hits = 0

            time.sleep(self.LOGIN_RESULT_POLL)

        return False, "Timeout esperando que el login se completara realmente"

    def _final_login_validation(self) -> bool:
        """
        Validación final más flexible:
        - éxito visual
        - popup guardar info
        - o sessionid + formulario ya no visible
        """
        stable_hits = 0
        start = time.time()

        while time.time() - start < self.FINAL_VALIDATION_TIMEOUT:
            # Si aparece modal intermedio, resolverlo y seguir validando
            if self._handle_human_confirmation_modal():
                stable_hits = 0
                time.sleep(self.HUMAN_CONFIRM_AFTER_CLICK_WAIT)
                continue

            if self._is_any_visible(self.locators.SECURITY_CHALLENGE):
                return False

            if self._is_any_visible(self.locators.LOGIN_ERRORS):
                return False

            form_visible = self._safe_is_visible(self.locators.LOGIN_FORM)
            logged_signal = self._is_logged_in_signal()
            has_session_cookie = self._has_session_cookie()

            # Éxito fuerte por UI
            if not form_visible and logged_signal:
                stable_hits += 1
                if stable_hits >= self.STABLE_SUCCESS_REQUIRED:
                    return True
            # Éxito fuerte por sesión aunque no haya xpath visual
            elif not form_visible and has_session_cookie:
                stable_hits += 1
                if stable_hits >= self.STABLE_SUCCESS_REQUIRED:
                    return True
            else:
                stable_hits = 0

            time.sleep(2)

        return False

    def _is_logged_in_signal(self) -> bool:
        """
        Señales de que ya entró de verdad.
        """
        return (
            self._is_any_visible(self.locators.POST_LOGIN_SUCCESS)
            or self._is_save_info_popup_visible()
        )

    def _handle_human_confirmation_modal(self) -> bool:
        """
        Modal:
        'Confirma que eres una persona para usar tu cuenta'
        No es error fatal. Se resuelve con Continuar.
        """
        title_xpaths = [
            self.locators.HUMAN_CONFIRM_TITLE_ES,
            self.locators.HUMAN_CONFIRM_TITLE_EN,
        ]

        continue_xpaths = [
            self.locators.HUMAN_CONFIRM_CONTINUE_ES,
            self.locators.HUMAN_CONFIRM_CONTINUE_EN,
        ]

        if not self._is_any_visible(title_xpaths):
            return False

        for xpath in continue_xpaths:
            try:
                if self._safe_is_visible(xpath):
                    self.browser.click(xpath)
                    return True
            except Exception:
                pass

        return False

    def _has_session_cookie(self) -> bool:
        try:
            cookies = self.browser.get_cookies() or []
            for cookie in cookies:
                name = str(cookie.get("name", "")).lower()
                value = cookie.get("value")
                if name == "sessionid" and value:
                    return True
            return False
        except Exception:
            return False

    def _dismiss_post_login_dialogs(self) -> None:
        preferred_buttons = [
            self.locators.NOT_NOW_BUTTON_ES,
            self.locators.NOT_NOW_BUTTON_EN,
        ]

        fallback_buttons = [
            self.locators.SAVE_INFO_BUTTON_ES,
            self.locators.SAVE_INFO_BUTTON_EN,
        ]

        for _ in range(self.POST_LOGIN_DIALOG_ATTEMPTS):
            clicked = False

            for xpath in preferred_buttons:
                try:
                    if self._safe_is_visible(xpath):
                        self.browser.click(xpath)
                        time.sleep(self.DIALOG_CLICK_WAIT)
                        clicked = True
                        break
                except Exception:
                    pass

            if clicked:
                continue

            for xpath in fallback_buttons:
                try:
                    if self._safe_is_visible(xpath):
                        self.browser.click(xpath)
                        time.sleep(self.DIALOG_CLICK_WAIT)
                        clicked = True
                        break
                except Exception:
                    pass

            if not clicked:
                break

    def _is_save_info_popup_visible(self) -> bool:
        popup_xpaths = [
            self.locators.SAVE_INFO_TITLE_ES,
            self.locators.SAVE_INFO_TITLE_EN,
            self.locators.NOT_NOW_BUTTON_ES,
            self.locators.NOT_NOW_BUTTON_EN,
            self.locators.SAVE_INFO_BUTTON_ES,
            self.locators.SAVE_INFO_BUTTON_EN,
        ]
        return self._is_any_visible(popup_xpaths)

    def _wait_visible(self, xpath: str, timeout: int = 20, poll: float = 1.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self._safe_is_visible(xpath):
                return True
            time.sleep(poll)
        return False

    def _is_any_visible(self, xpaths: Iterable[str]) -> bool:
        for xpath in xpaths:
            if self._safe_is_visible(xpath):
                return True
        return False

    def _safe_is_visible(self, xpath: str) -> bool:
        try:
            return self.browser.is_visible(xpath)
        except Exception:
            return False
        

    def is_session_ready(self) -> bool:
        """
        Determina si la sesión ya está lista sin forzar login manual.
        Considera:
        - popup de guardar información
        - señales visuales post-login
        - sessionid presente aunque no haya señal visual fuerte
        """
        try:
            if self._is_logged_in_signal():
                return True

            form_visible = self._safe_is_visible(self.locators.LOGIN_FORM)
            has_session_cookie = self._has_session_cookie()

            if not form_visible and has_session_cookie:
                return True

            return False
        except Exception:
            return False
        
    def dismiss_post_login_dialogs(self) -> None:
        self._dismiss_post_login_dialogs()