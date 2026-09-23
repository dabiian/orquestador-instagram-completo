"""
app/config/locators/login_locators.py

XPaths relacionados con el flujo de login de Instagram.
Este módulo separa los selectores del servicio para mejorar la organización
y poder reutilizarlos o modificarlos sin tocar la lógica de negocio.
"""

from typing import List


class LoginLocators:
    # =========================
    # FORMULARIO DE LOGIN
    # =========================
    LOGIN_FORM = "//form[@id='ESTO_ES_UN_ERROR_DE_PRUEBA']"
    USER_INPUT = "//form[@id='login_form']//input[@name='email']"
    PASS_INPUT = "//form[@id='login_form']//input[@name='pass' and @type='password']"

    LOGIN_BUTTON = (
        "//form[@id='login_form']"
        "//*[self::button or @role='button']"
        "[.//span[normalize-space(.)='Iniciar sesión'] "
        "or .//span[normalize-space(.)='Log in'] "
        "or normalize-space(.)='Iniciar sesión' "
        "or normalize-space(.)='Log in']"
    )

    LOGIN_BUTTON_ENABLED = (
        "//form[@id='login_form']"
        "//*[self::button or @role='button']"
        "[(not(@aria-disabled) or @aria-disabled='false')]"
        "[.//span[normalize-space(.)='Iniciar sesión'] "
        "or .//span[normalize-space(.)='Log in'] "
        "or normalize-space(.)='Iniciar sesión' "
        "or normalize-space(.)='Log in']"
    )

    CONTINUE_BUTTON = (
        "//*[self::button or @role='button']"
        "[.//span[normalize-space(.)='Continuar'] "
        "or .//span[normalize-space(.)='Continue'] "
        "or normalize-space(.)='Continuar' "
        "or normalize-space(.)='Continue']"
    )

    # =========================
    # POPUP GUARDAR INFO LOGIN
    # =========================
    SAVE_INFO_TITLE_ES = "//h1[normalize-space(.)='¿Guardar tu información de inicio de sesión?']"
    SAVE_INFO_TITLE_EN = "//h1[normalize-space(.)='Save your login info?']"

    NOT_NOW_BUTTON_ES = "//*[self::button or @role='button'][normalize-space(.)='Ahora no']"
    NOT_NOW_BUTTON_EN = "//*[self::button or @role='button'][normalize-space(.)='Not Now']"

    SAVE_INFO_BUTTON_ES = "//*[self::button or @role='button'][normalize-space(.)='Guardar información']"
    SAVE_INFO_BUTTON_EN = "//*[self::button or @role='button'][normalize-space(.)='Save info']"

    # =========================
    # MENSAJES DE ERROR REALES
    # =========================
    LOGIN_ERRORS: List[str] = [
        "//span[contains(normalize-space(.), 'La contraseña no es correcta')]",
        "//span[contains(normalize-space(.), 'Tu contraseña es incorrecta')]",
        "//span[contains(normalize-space(.), 'incorrecta')]",
        "//span[contains(normalize-space(.), 'incorrecto')]",
        "//span[contains(normalize-space(.), 'Inténtalo de nuevo')]",
        "//span[contains(normalize-space(.), 'Try again later')]",
        "//span[contains(normalize-space(.), 'The password you entered is incorrect')]",
        "//span[contains(normalize-space(.), 'Sorry, your password was incorrect')]",
    ]

    # =========================
    # CHALLENGES REALES / MANUALES
    # =========================
    SECURITY_CHALLENGE: List[str] = [
        "//strong[contains(normalize-space(.), 'Aprobación de inicio de sesión necesaria')]",
        "//span[contains(normalize-space(.), 'Aprobación de inicio de sesión necesaria')]",
        "//span[contains(normalize-space(.), 'Confirma que fuiste tú')]",
        "//span[contains(normalize-space(.), 'Confirm it was you')]",
        "//input[contains(@name, 'verification')]",
        "//input[contains(@name, 'code')]",
        "//input[contains(@autocomplete, 'one-time-code')]",
    ]

    # =========================
    # MODAL INTERMEDIO: CONFIRMA QUE ERES UNA PERSONA
    # ESTO NO ES ERROR FATAL. SE DEBE RESOLVER CON CLICK EN CONTINUAR.
    # =========================
    HUMAN_CONFIRM_TITLE_ES = (
        "//span[@role='heading' and contains(normalize-space(.), 'Confirma que eres una persona para usar tu cuenta')]"
    )

    HUMAN_CONFIRM_TITLE_EN = (
        "//span[@role='heading' and contains(normalize-space(.), 'Confirm you are a person to use your account')]"
    )

    HUMAN_CONFIRM_CONTINUE_ES = (
        "//*[@role='button' and (@aria-label='Continuar' or .//span[normalize-space(.)='Continuar'])]"
    )

    HUMAN_CONFIRM_CONTINUE_EN = (
        "//*[@role='button' and (@aria-label='Continue' or .//span[normalize-space(.)='Continue'])]"
    )

    # =========================
    # INDICADORES DE LOGIN EXITOSO
    # =========================
    POST_LOGIN_SUCCESS: List[str] = [
        "//a[contains(@href, '/direct/inbox')]",
        "//a[contains(@href, '/explore')]",
        "//a[contains(@href, '/accounts/activity')]",
        "//a[contains(@href, '/accounts/edit/')]",
        "//a[contains(@href, '/reels')]",
        "//svg[@aria-label='Inicio']",
        "//svg[@aria-label='Home']",
        "//svg[@aria-label='Buscar']",
        "//svg[@aria-label='Search']",
        "//svg[@aria-label='Mensajes']",
        "//svg[@aria-label='Messages']",
        "//svg[@aria-label='Nuevo post']",
        "//svg[@aria-label='New post']",
        "//*[contains(@aria-label, 'Perfil')]",
        "//*[contains(@aria-label, 'Profile')]",
    ]