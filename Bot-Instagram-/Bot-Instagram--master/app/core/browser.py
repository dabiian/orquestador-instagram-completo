"""
Automatización del navegador mediante Selenium.

Este módulo contiene la clase Automate, responsable de:

- Crear Chrome local o Selenium Remote.
- Configurar proxy.
- Configurar emulación móvil.
- Abrir/cerrar/recargar/navegar.
- Buscar elementos mediante Selenium.
- Integrarse opcionalmente con Self-Healer.
- Ejecutar acciones sobre elementos.
- Hacer scroll, hover, clicks y escritura.
- Trabajar con cookies y uploads.
- Resolver scopes de posts.
- Mantener compatibilidad con el código existente del bot.

Self-Healer:
    Si está habilitado, self.driver será un HealableWebDriver.
    Si está deshabilitado o no está disponible, se utilizará Selenium directamente.

La integración está diseñada para que el resto del bot pueda continuar
utilizando:

    self.driver.find_element(...)
    self.driver.find_elements(...)
    self.driver.execute_script(...)
    WebDriverWait(self.driver, ...)
    ActionChains(self.driver)

sin tener que modificar todo el proyecto.
"""

from __future__ import annotations

import os
import time
import re
import random
import traceback
from typing import Any, Optional

try:
    import pyautogui
except Exception as exc:
    pyautogui = None
    print(f"[browser] pyautogui no disponible en este entorno: {exc}")

import pyperclip
import requests

from dotenv import load_dotenv
from app.utils.logger import get_logger

log = get_logger(__name__)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    UnexpectedAlertPresentException,
    InvalidSelectorException,
    TimeoutException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    WebDriverException,
)

from app.core.interfaces import IProxyValidator

load_dotenv()

# The self-healer has historically kept its settings in its own .env.
# Load that file without overriding the bot's main environment so existing
# deployments keep their values while the healer can actually be enabled.
_SELF_HEALER_ENV = (
    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    + os.sep
    + "self_healer"
    + os.sep
    + ".env"
)
if os.path.exists(_SELF_HEALER_ENV):
    load_dotenv(_SELF_HEALER_ENV, override=False)


# ============================================================================
# SELF-HEALER
# ============================================================================

try:
    from self_healer.core.config import SelfHealerConfig
    from self_healer.core.sqlite_store import SelfHealerStore
    from self_healer.providers.openai_provider import OpenAILocatorGenerator
    from self_healer.selenium_adapter.driver import HealableWebDriver

    SELF_HEALER_AVAILABLE = True

except Exception as exc:
    SelfHealerConfig = None
    SelfHealerStore = None
    OpenAILocatorGenerator = None
    HealableWebDriver = None
    SELF_HEALER_AVAILABLE = False

    print(
        f"[browser] Self-Healer no disponible: "
        f"{type(exc).__name__}: {exc}"
    )


# ============================================================================
# AUTOMATE
# ============================================================================


class Automate:
    """
    Wrapper principal del navegador.

    El atributo self.driver puede contener:

        - webdriver.Chrome
        - webdriver.Remote
        - HealableWebDriver

    HealableWebDriver delega los métodos Selenium que no necesita interceptar,
    por lo que el resto del bot puede continuar trabajando normalmente.
    """

    def __init__(
        self,
        proxy=None,
        port=None,
        user=None,
        password=None,
        proxy_validator: IProxyValidator = None,
        self_healer_enabled: Optional[bool] = None,
        self_healer_config: Optional[Any] = None,
        self_healer_provider: Optional[Any] = None,
        self_healer_store: Optional[Any] = None,
    ):
        self.driver = None

        self.proxy = proxy
        self.port = port
        self.user = user
        self.password = password
        self.proxy_validator = proxy_validator

        self.last_anchor_element = None
        self.last_anchor_xpath = ""

        self.last_clicked_element = None
        self.last_clicked_xpath = ""

        self.mobile_profile_name = None
        self.mobile_profile_config = None
        self.mobile_mode = False

        # ------------------------------------------------------------------
        # Self-Healer
        # ------------------------------------------------------------------

        env_healer = os.getenv(
            "SELF_HEALER_ENABLED",
            "false",
        ).strip().lower()

        if self_healer_enabled is None:
            self.self_healer_enabled = env_healer in {
                "1",
                "true",
                "yes",
                "on",
            }
        else:
            self.self_healer_enabled = bool(self_healer_enabled)

        self.self_healer_config = self_healer_config
        self.self_healer_provider = self_healer_provider
        self.self_healer_store = self_healer_store

        self._self_healer_initialized = False

    # ========================================================================
    # SELF-HEALER
    # ========================================================================

    def _build_self_healer(self):
        """
        Construye la configuración/provider/store del Self-Healer.

        Todo es opcional. Si Self-Healer no está instalado o configurado,
        el navegador continúa funcionando con Selenium normal.
        """

        if not self.self_healer_enabled:
            return None

        if not SELF_HEALER_AVAILABLE:
            print(
                "[browser] Self-Healer solicitado pero sus módulos "
                "no están disponibles. Continuando con Selenium."
            )
            return None

        try:
            config = self.self_healer_config

            if config is None:
                config = SelfHealerConfig(
                    project_name=os.getenv(
                        "SELF_HEALER_PROJECT",
                        "instagram_bot",
                    ),
                    db_path=os.getenv(
                        "SELF_HEALER_DB_PATH",
                        "self_healer.db",
                    ),
                    enabled=True,
                    heal_on_find=True,
                    heal_on_action=True,
                    allow_ai=os.getenv(
                        "SELF_HEALER_ALLOW_AI",
                        "true",
                    ).strip().lower()
                    in {"1", "true", "yes", "on"},
                    max_ai_candidates=int(
                        os.getenv(
                            "SELF_HEALER_MAX_AI_CANDIDATES",
                            "5",
                        )
                    ),
                    max_html_chars=int(
                        os.getenv(
                            "SELF_HEALER_MAX_HTML_CHARS",
                            "120000",
                        )
                    ),
                    chunk_size_kb=int(
                        os.getenv(
                            "SELF_HEALER_CHUNK_SIZE_KB",
                            "50",
                        )
                    ),
                    max_chunks_to_try=int(
                        os.getenv(
                            "SELF_HEALER_MAX_CHUNKS",
                            "5",
                        )
                    ),
                    prefer_saved_locator=True,
                    save_only_validated_locators=True,
                    strict_mode=False,
                )

            store = self.self_healer_store

            if store is None:
                store = SelfHealerStore(config.db_path)

            provider = self.self_healer_provider

            if provider is None and config.allow_ai:
                try:
                    provider = OpenAILocatorGenerator(
                        model=os.getenv(
                            "SELF_HEALER_MODEL",
                            "deepseek-chat",
                        ),
                        max_candidates=config.max_ai_candidates,
                        chunk_size_kb=config.chunk_size_kb,
                        max_chunks_to_try=config.max_chunks_to_try,
                    )
                except Exception as exc:
                    print(
                        "[browser] No se pudo inicializar "
                        f"Self-Healer provider: {exc}"
                    )
                    provider = None

            self.self_healer_config = config
            self.self_healer_store = store
            self.self_healer_provider = provider
            self._self_healer_initialized = True

            return {
                "config": config,
                "store": store,
                "provider": provider,
            }

        except Exception as exc:
            print(
                "[browser] Error inicializando Self-Healer: "
                f"{type(exc).__name__}: {exc}"
            )

            self._self_healer_initialized = False
            return None

    def _wrap_driver_with_self_healer(self, raw_driver):
        """
        Envuelve un WebDriver Selenium con HealableWebDriver.

        Si algo falla durante la integración, devuelve el driver original.
        """

        if not self.self_healer_enabled:
            return raw_driver

        if not SELF_HEALER_AVAILABLE:
            return raw_driver

        try:
            healer = self._build_self_healer()

            if not healer:
                return raw_driver

            wrapped = HealableWebDriver(
                driver=raw_driver,
                config=healer["config"],
                locator_generator=healer["provider"],
                store=healer["store"],
            )

            print("[browser] Self-Healer integrado correctamente.")

            return wrapped

        except TypeError:
            # Compatibilidad por si el constructor de HealableWebDriver
            # utiliza nombres ligeramente diferentes.
            try:
                healer = self._build_self_healer()

                if not healer:
                    return raw_driver

                wrapped = HealableWebDriver(
                    driver=raw_driver,
                    config=healer["config"],
                    locator_generator=healer["provider"],
                    store=healer["store"],
                )

                print("[browser] Self-Healer integrado correctamente.")

                return wrapped

            except Exception as exc:
                print(
                    "[browser] No se pudo envolver el driver "
                    f"con Self-Healer: {exc}"
                )
                return raw_driver

        except Exception as exc:
            print(
                "[browser] No se pudo envolver el driver "
                f"con Self-Healer: {exc}"
            )
            return raw_driver

    # ========================================================================
    # CHROME DRIVER
    # ========================================================================

    def _create_chrome_driver(self, chrome_options):
        """
        Crea Chrome local o Selenium Remote.

        Si SELENIUM_REMOTE_URL está definido:
            webdriver.Remote(...)

        De lo contrario:
            webdriver.Chrome(...)
        """

        selenium_remote_url = os.getenv(
            "SELENIUM_REMOTE_URL",
            "",
        ).strip()

        if selenium_remote_url:
            print(
                f"[browser] Usando Selenium remoto: "
                f"{selenium_remote_url}"
            )

            raw_driver = webdriver.Remote(
                command_executor=selenium_remote_url,
                options=chrome_options,
            )

            # Necesario para uploads cuando el bot y Chrome/Selenium
            # viven en contenedores diferentes.
            try:
                raw_driver.file_detector = LocalFileDetector()
            except Exception as exc:
                print(
                    "[browser] No se pudo configurar LocalFileDetector: "
                    f"{exc}"
                )

        else:
            print("[browser] Usando Chrome local")

            raw_driver = webdriver.Chrome(
                options=chrome_options
            )

        return self._wrap_driver_with_self_healer(raw_driver)

    # ========================================================================
    # MOBILE PROFILES
    # ========================================================================

    def _get_mobile_emulation_profile(
        self,
        profile: str = "instagram_android",
    ) -> dict:
        profile = (
            profile or "instagram_android"
        ).strip().lower()

        profiles = {
            "instagram_android": {
                "deviceMetrics": {
                    "width": 430,
                    "height": 932,
                    "pixelRatio": 3.0,
                },
                "userAgent": (
                    "Mozilla/5.0 (Linux; Android 13; SM-S918B) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Mobile Safari/537.36"
                ),
                "clientHints": {
                    "platform": "Android",
                    "mobile": True,
                },
            },
            "instagram_android_landscape": {
                "deviceMetrics": {
                    "width": 932,
                    "height": 430,
                    "pixelRatio": 3.0,
                },
                "userAgent": (
                    "Mozilla/5.0 (Linux; Android 13; SM-S918B) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Mobile Safari/537.36"
                ),
                "clientHints": {
                    "platform": "Android",
                    "mobile": True,
                },
            },
            "ipad_landscape": {
                "deviceMetrics": {
                    "width": 1180,
                    "height": 820,
                    "pixelRatio": 2.0,
                },
                "userAgent": (
                    "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/16.0 Mobile/15E148 Safari/604.1"
                ),
                "clientHints": {
                    "platform": "iOS",
                    "mobile": True,
                },
            },
        }

        return profiles.get(
            profile,
            profiles["instagram_android"],
        )

    # ========================================================================
    # OPEN BROWSER
    # ========================================================================

    def open_browser(
        self,
        url,
        proxy=None,
        cookies_add=None,
        mobile=False,
        mobile_profile="instagram_android",
    ):
        try:
            chrome_options = webdriver.ChromeOptions()

            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument(
                "--disable-save-password-bubble"
            )

            chrome_options.add_experimental_option(
                "excludeSwitches",
                ["enable-automation"],
            )

            chrome_options.add_experimental_option(
                "useAutomationExtension",
                False,
            )

            chrome_options.add_argument(
                "--disable-blink-features=AutomationControlled"
            )
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(
                "--disable-browser-side-navigation"
            )
            chrome_options.add_argument("--disable-gpu")

            self.mobile_mode = bool(mobile)

            self.mobile_profile_name = (
                mobile_profile if mobile else None
            )

            self.mobile_profile_config = None

            # ----------------------------------------------------------------
            # MOBILE EMULATION
            # ----------------------------------------------------------------

            if mobile:
                mobile_emulation = (
                    self._get_mobile_emulation_profile(
                        mobile_profile
                    )
                )

                self.mobile_profile_config = mobile_emulation

                chrome_options.add_experimental_option(
                    "mobileEmulation",
                    mobile_emulation,
                )

            # ----------------------------------------------------------------
            # PROXY
            # ----------------------------------------------------------------

            has_proxy_data = all(
                [
                    self.proxy,
                    self.port,
                    self.user,
                    self.password,
                ]
            )

            use_proxy = (
                has_proxy_data
                if proxy is None
                else bool(proxy)
            )

            print(
                f"[open_browser] "
                f"proxy_param={proxy} | "
                f"has_proxy_data={has_proxy_data} | "
                f"use_proxy={use_proxy} | "
                f"proxy_host={self.proxy} | "
                f"port={self.port}"
            )

            if use_proxy:
                print("[open_browser] Abriendo con proxy")

                if not has_proxy_data:
                    print(
                        "[open_browser] Proxy activado, "
                        "pero faltan datos: "
                        "proxy/port/user/password"
                    )
                    return False

                if self.proxy_validator is None:
                    print(
                        "[open_browser] "
                        "No hay proxy_validator configurado"
                    )
                    return False

                if self.proxy_validator.validate(
                    self.proxy,
                    self.port,
                    self.user,
                    self.password,
                ):
                    print(
                        "[open_browser] "
                        "Proxy validado y funcional"
                    )

                    proxy_str = (
                        f"http://{self.proxy}:{self.port}"
                    )

                    chrome_options.add_argument(
                        f"--proxy-server={proxy_str}"
                    )

                else:
                    print(
                        "[open_browser] "
                        "Proxy no validado o no funcional"
                    )
                    return False

            else:
                print("[open_browser] Abriendo sin proxy")

            # ----------------------------------------------------------------
            # CREATE DRIVER
            # ----------------------------------------------------------------

            self.driver = self._create_chrome_driver(
                chrome_options
            )

            # ----------------------------------------------------------------
            # MOBILE CDP
            # ----------------------------------------------------------------

            if mobile:
                profile_cfg = (
                    self.mobile_profile_config
                    or self._get_mobile_emulation_profile(
                        mobile_profile
                    )
                )

                metrics = profile_cfg.get(
                    "deviceMetrics",
                    {},
                )

                width = int(
                    metrics.get("width", 430)
                )

                height = int(
                    metrics.get("height", 932)
                )

                pixel_ratio = float(
                    metrics.get("pixelRatio", 3.0)
                )

                orientation = {
                    "type": (
                        "landscapePrimary"
                        if width > height
                        else "portraitPrimary"
                    ),
                    "angle": (
                        90
                        if width > height
                        else 0
                    ),
                }

                # ------------------------------------------------------------
                # Metrics
                # ------------------------------------------------------------

                try:
                    self.driver.execute_cdp_cmd(
                        "Emulation.setDeviceMetricsOverride",
                        {
                            "mobile": True,
                            "width": width,
                            "height": height,
                            "deviceScaleFactor": pixel_ratio,
                            "screenWidth": width,
                            "screenHeight": height,
                            "screenOrientation": orientation,
                        },
                    )

                except Exception as exc:
                    print(
                        "[browser] Error "
                        f"setDeviceMetricsOverride: {exc}"
                    )

                # ------------------------------------------------------------
                # Touch
                # ------------------------------------------------------------

                try:
                    self.driver.execute_cdp_cmd(
                        "Emulation.setTouchEmulationEnabled",
                        {
                            "enabled": True,
                            "maxTouchPoints": 5,
                        },
                    )

                except Exception as exc:
                    print(
                        "[browser] Error "
                        f"setTouchEmulationEnabled: {exc}"
                    )

                # ------------------------------------------------------------
                # Mouse -> touch
                # ------------------------------------------------------------

                try:
                    self.driver.execute_cdp_cmd(
                        "Emulation.setEmitTouchEventsForMouse",
                        {
                            "enabled": True,
                            "configuration": "mobile",
                        },
                    )

                except Exception as exc:
                    print(
                        "[browser] Error "
                        f"setEmitTouchEventsForMouse: {exc}"
                    )

                # ------------------------------------------------------------
                # Navigator / orientation
                # ------------------------------------------------------------

                try:
                    self.driver.execute_cdp_cmd(
                        "Page.addScriptToEvaluateOnNewDocument",
                        {
                            "source": f"""
                                Object.defineProperty(
                                    navigator,
                                    'maxTouchPoints',
                                    {{
                                        get: () => 5
                                    }}
                                );

                                Object.defineProperty(
                                    window,
                                    'orientation',
                                    {{
                                        get: () => {
                                            90
                                            if width > height
                                            else 0
                                        }
                                    }}
                                );

                                try {{
                                    Object.defineProperty(
                                        screen,
                                        'orientation',
                                        {{
                                            value: {{
                                                type:
                                                    '{orientation["type"]}',
                                                angle:
                                                    {orientation["angle"]},
                                                onchange:
                                                    null
                                            }},
                                            configurable: true
                                        }}
                                    );
                                }} catch (e) {{}}
                            """
                        },
                    )

                except Exception as exc:
                    print(
                        "[browser] Error "
                        f"addScriptToEvaluateOnNewDocument: {exc}"
                    )

            # ----------------------------------------------------------------
            # OPEN URL
            # ----------------------------------------------------------------

            self.driver.get(url)

            # ----------------------------------------------------------------
            # PROXY AUTH POPUP
            # ----------------------------------------------------------------

            if use_proxy:
                if pyautogui is None:
                    print(
                        "[browser] Proxy con autenticación "
                        "por popup requiere pyautogui."
                    )
                    return False

                time.sleep(5)

                pyautogui.write(str(self.user))
                pyautogui.press("tab")
                pyautogui.write(str(self.password))
                pyautogui.press("enter")

            # ----------------------------------------------------------------
            # COOKIES
            # ----------------------------------------------------------------

            if cookies_add:
                for cookie in cookies_add:
                    cookie_data = dict(cookie)

                    if "expiry" in cookie_data:
                        try:
                            cookie_data["expiry"] = int(
                                cookie_data["expiry"]
                            )
                        except Exception:
                            cookie_data.pop("expiry", None)

                    try:
                        self.driver.add_cookie(
                            cookie_data
                        )

                    except Exception as exc:
                        print(
                            "[browser] No se pudo agregar "
                            f"cookie {cookie_data.get('name')}: {exc}"
                        )

                self.recargar_navegador()

                time.sleep(
                    random.uniform(2, 4)
                )

            else:
                print("[browser] Cookie vacía")

            # ----------------------------------------------------------------
            # MAXIMIZE
            # ----------------------------------------------------------------

            if not mobile:
                try:
                    self.driver.maximize_window()
                except Exception as exc:
                    print(
                        "[browser] No se pudo maximizar: "
                        f"{exc}"
                    )

            return True

        except Exception as exc:
            print(
                "[browser] Error al abrir el navegador: "
                f"{type(exc).__name__}: {exc}"
            )

            traceback.print_exc()

            return False

    # ========================================================================
    # HEADLESS
    # ========================================================================

    def open_browser_headless(
        self,
        url,
        proxy=None,
    ):
        chrome_options = webdriver.ChromeOptions()

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--enable-automation")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-setuid-sandbox")

        # Mantengo tu comportamiento original:
        # NO activo --headless automáticamente.

        self.driver = self._create_chrome_driver(
            chrome_options
        )

        self.driver.get(url)

        return True

    # ========================================================================
    # SCRIPT
    # ========================================================================

    def execute_script(self, script, *args):
        if not self.driver:
            raise AttributeError(
                "Driver is not initialized"
            )

        return self.driver.execute_script(
            script,
            *args,
        )

    def execute_script_safe(self, script: str, *args):
        if not self.driver:
            raise AttributeError(
                "Driver is not initialized"
            )

        try:
            return self.driver.execute_script(
                script,
                *args,
            )

        except Exception as exc:
            raise Exception(
                f"Error executing JS script: {exc}"
            ) from exc

    # ========================================================================
    # HOVER
    # ========================================================================

    def hover(self, xpath):
        element = self.driver.find_element(
            By.XPATH,
            xpath,
        )

        ActionChains(
            self.driver
        ).move_to_element(
            element
        ).perform()

        return element

    # ========================================================================
    # SCROLL
    # ========================================================================

    def scroll_to_xpath(
        self,
        xpath,
        timeX=10,
        error=True,
    ):
        scrolled_successfully = False
        last_exc = None

        for _ in range(3):
            try:
                wait_driver = getattr(self.driver, "raw", self.driver)

                element = WebDriverWait(
                    wait_driver,
                    timeX,
                ).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            xpath,
                        )
                    )
                )

                self.human_like_scroll(
                    element
                )

                scrolled_successfully = True
                break

            except Exception as exc:
                last_exc = exc
                self.time_sleep(1)

                print(
                    "[scroll_to_xpath] "
                    f"Error hacia elemento: {xpath}"
                )

        if not scrolled_successfully:
            msg = (
                f"No se pudo realizar el scroll hacia "
                f"{xpath} después de 3 intentos."
            )

            if last_exc:
                msg += (
                    f" Último error: "
                    f"{type(last_exc).__name__}: "
                    f"{last_exc}"
                )

            if error:
                raise Exception(msg)

            print(msg)

        return scrolled_successfully

    # ========================================================================
    # HOVER + CLICK
    # ========================================================================

    def hover_and_click(
        self,
        xpath,
        time_x=10,
        error=True,
    ):
        for attempt in range(1, 4):
            try:
                print(
                    f"[hover_and_click] "
                    f"intento {attempt}/3 | xpath: {xpath}"
                )
                wait_driver = getattr(
                    self.driver,
                    "raw",
                    self.driver,
                )
                element = WebDriverWait(
                    wait_driver,
                    time_x,
                ).until(
                    EC.visibility_of_element_located(
                        (
                            By.XPATH,
                            xpath,
                        )
                    )
                )

                wait_driver.execute_script(
                    """
                    arguments[0].scrollIntoView({
                        block: 'center',
                        inline: 'center'
                    });
                    """,
                    element,
                )

                time.sleep(
                    random.uniform(0.5, 1.0)
                )

                ActionChains(
                    wait_driver
                ).move_to_element(
                    element
                ).pause(
                    random.uniform(0.4, 1.0)
                ).click(
                    element
                ).perform()

                print(
                    "[hover_and_click] "
                    f"OK: {xpath}"
                )

                return True

            except Exception as exc:
                print(
                    "[hover_and_click] "
                    f"error intento {attempt}/3 | "
                    f"xpath: {xpath}"
                )

                print(
                    f"[hover_and_click] "
                    f"tipo: {type(exc).__name__}"
                )

                print(
                    f"[hover_and_click] "
                    f"msg: {exc}"
                )

                time.sleep(1)

        # --------------------------------------------------------------------
        # Fallback
        # --------------------------------------------------------------------

        try:
            print(
                "[hover_and_click] "
                f"fallback JS click: {xpath}"
            )

            wait_driver = getattr(
                self.driver,
                "raw",
                self.driver,
            )

            element = WebDriverWait(
                wait_driver,
                time_x,
            ).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        xpath,
                    )
                )
            )

            wait_driver.execute_script(
                "arguments[0].click();",
                element,
            )

            print(
                "[hover_and_click] "
                f"JS click OK: {xpath}"
            )

            return True

        except Exception as exc:
            msg = (
                f"No se pudo hacer hover_and_click "
                f"en {xpath}. "
                f"Último error: "
                f"{type(exc).__name__}: {exc}"
            )

            if error:
                raise Exception(msg) from exc

            print(msg)
            return False

    # ========================================================================
    # CLICK
    # ========================================================================

    def click(
        self,
        xpath,
        xpath_hover="",
        timeX=10,
        scroll=True,
        error=True,
        hover=False,
    ):
        clicked_successfully = False
        last_exc = None

        for attempt in range(1, 4):
            try:
                print(
                    f"[click] intento {attempt}/3 | "
                    f"xpath: {xpath}"
                )

                wait_driver = getattr(
                    self.driver,
                    "raw",
                    self.driver,
                )

                element = WebDriverWait(
                    wait_driver,
                    timeX,
                ).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            xpath,
                        )
                    )
                )

                self.last_anchor_element = element
                self.last_anchor_xpath = xpath

                if scroll:
                    self.human_like_scroll(
                        element
                    )

                if hover:
                    if not xpath_hover:
                        raise ValueError(
                            "hover=True pero "
                            "xpath_hover está vacío"
                        )

                    print(
                        "[click] haciendo hover..."
                    )

                    self.hover(xpath)

                    time.sleep(1)

                    wait_driver = getattr(self.driver, "raw", self.driver)

                    el = WebDriverWait(
                        wait_driver,
                        timeX,
                    ).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, xpath_hover)
                        )
                    )

                    self.last_clicked_element = el
                    self.last_clicked_xpath = xpath_hover

                    time.sleep(0.2)

                    el.click()

                    print(
                        "[click] "
                        f"click después de hover: "
                        f"{xpath_hover}"
                    )

                else:

                    self.last_clicked_element = element
                    self.last_clicked_xpath = xpath

                    time.sleep(0.2)

                    try:
                        element.click()

                    except ElementClickInterceptedException:
                        print(
                            "[click] Click interceptado. "
                            "Reposicionando elemento..."
                        )

                        try:
                            wait_driver.execute_script(
                                """
                                arguments[0].scrollIntoView({
                                    block: 'center',
                                    inline: 'center'
                                });
                                """,
                                element,
                            )
                        except Exception:
                            pass

                        time.sleep(0.8)

                        element.click()

                    print(
                        f"[click] OK: {xpath}"
                    )

                clicked_successfully = True
                break

            except Exception as exc:
                last_exc = exc

                print(
                    f"[click] error intento "
                    f"{attempt}/3 | xpath: {xpath}"
                )

                print(
                    f"[click] tipo: "
                    f"{type(exc).__name__}"
                )

                print(
                    f"[click] msg: {exc}"
                )

                try:
                    print(
                        f"[click] url actual: "
                        f"{self.driver.current_url}"
                    )
                except Exception:
                    pass

                self.time_sleep(1)

        if not clicked_successfully:
            msg = (
                f"No se pudo clickear {xpath} "
                f"después de 3 intentos."
            )

            if last_exc:
                msg += (
                    f" Último error: "
                    f"{type(last_exc).__name__}: "
                    f"{last_exc}"
                )

            if error:
                raise Exception(msg) from last_exc

            print(msg)

            return False

        return True

    # ========================================================================
    # CLICK ELEMENT
    # ========================================================================

    def click_element(self, element):
        try:
            element.click()

            try:
                text = element.text
            except Exception:
                text = ""

            print(
                f"Se clickeó: {text}"
            )

            return True

        except StaleElementReferenceException:
            try:
                element.click()

                try:
                    text = element.text
                except Exception:
                    text = ""

                print(
                    f"Se clickeó (reintentado): {text}"
                )

                return True

            except Exception as exc:
                print(
                    f"Error reintentando click: {exc}"
                )
                return False

        except Exception as exc:
            print(
                f"Error haciendo click: {exc}"
            )
            return False

    # ========================================================================
    # TEXT + URLS
    # ========================================================================

    def get_text_and_urls(self, xpath):
        try:
            element = self.driver.find_element(
                By.XPATH,
                xpath,
            )

            text = " ".join(
                (element.text or "").split()
            )

            images = element.find_elements(
                By.TAG_NAME,
                "img",
            )

            urls = []

            for img in images:
                src = img.get_attribute(
                    "src"
                )

                if src and ".jpg" in src.lower():
                    urls.append(
                        src.strip()
                    )

            return text, urls

        except NoSuchElementException as exc:
            print(
                f"Elemento no encontrado: {exc}"
            )
            return None, None

    # ========================================================================
    # TEST INPUT
    # ========================================================================

    def test1(self, element, text):
        textbox = element.find_element(
            By.XPATH,
            "//div[@role='textbox' "
            "and @aria-label='Escribe algo…']",
        )

        textbox.click()
        textbox.clear()
        textbox.send_keys(text)

    # ========================================================================
    # CSS CLICK
    # ========================================================================

    def click_css(
        self,
        selector,
        time_x=10,
    ):
        WebDriverWait(
            self.driver,
            time_x,
        ).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    selector,
                )
            )
        )

        element = self.driver.find_element(
            By.CSS_SELECTOR,
            selector,
        )

        print(
            f"Se clickeó: {selector}"
        )

        element.click()

        return element

    # ========================================================================
    # WRITE TEXT
    # ========================================================================

    def write_text(
        self,
        xpath_or_element,
        text,
        time_x=10,
        rapido=False,
        fast_t=0.1,
        enter=False,
    ):
        if isinstance(
            xpath_or_element,
            str,
        ):
            element = WebDriverWait(
                self.driver,
                time_x,
            ).until(
                EC.visibility_of_element_located(
                    (
                        By.XPATH,
                        xpath_or_element,
                    )
                )
            )
        else:
            element = xpath_or_element

        print(
            f"Escribiendo en: "
            f"{xpath_or_element}"
        )

        element.clear()

        if rapido:
            element.send_keys(text)

        else:
            for char in text:
                if self.contains_non_bmp_chars(
                    char
                ):
                    pyperclip.copy(char)

                    element.send_keys(
                        Keys.CONTROL,
                        "v",
                    )

                else:
                    element.send_keys(char)

                delay = (
                    random.random()
                    * fast_t
                    + 0.0001
                )

                time.sleep(delay)

        if enter:
            element.send_keys(
                Keys.ENTER
            )

    # ========================================================================
    # UPLOAD
    # ========================================================================

    def upload_file(
        self,
        xpath_or_element,
        file_path,
        time_x=10,
    ):
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"El archivo {file_path} no existe."
            )

        if isinstance(
            xpath_or_element,
            str,
        ):
            element = WebDriverWait(
                self.driver,
                time_x,
            ).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        xpath_or_element,
                    )
                )
            )

        else:
            element = xpath_or_element

        element.send_keys(file_path)

    # ========================================================================
    # PADRE
    # ========================================================================

    def padre(
        self,
        xpath_father,
        xpath_hijo,
        texto,
    ):
        try:
            span_element = WebDriverWait(
                self.driver,
                10,
            ).until(
                EC.visibility_of_element_located(
                    (
                        By.XPATH,
                        xpath_father,
                    )
                )
            )

            textarea_element = (
                span_element.find_element(
                    By.XPATH,
                    xpath_hijo,
                )
            )

            textarea_element.send_keys(
                texto
            )

        except NoSuchElementException as exc:
            print(
                f"Error: {exc}"
            )

    # ========================================================================
    # HELPERS
    # ========================================================================

    def contains_non_bmp_chars(self, text):
        return bool(
            re.search(
                r"[^\x00-\xFFFF]",
                text,
            )
        )

    # ========================================================================
    # CLEAR INPUT
    # ========================================================================

    def clear_input(self, xpath):
        try:
            WebDriverWait(
                self.driver,
                10,
            ).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        xpath,
                    )
                )
            )

            element = self.driver.find_element(
                By.XPATH,
                xpath,
            )

            element.clear()

        except Exception as exc:
            print(
                f"Error al limpiar input: {exc}"
            )

    # ========================================================================
    # GET TEXT
    # ========================================================================

    def get_text(self, tag_name):
        try:
            element = self.driver.find_element(
                By.TAG_NAME,
                tag_name,
            )

            return element.text

        except Exception as exc:
            print(
                f"Error obteniendo texto "
                f"{tag_name}: {exc}"
            )

            return ""

    def get_text_by_xpath(self, xpath):
        try:
            element = self.driver.find_element(
                By.XPATH,
                xpath,
            )

            return element.text

        except Exception as exc:
            print(
                f"Error obteniendo texto "
                f"{xpath}: {exc}"
            )

            return ""

    # ========================================================================
    # WINDOW
    # ========================================================================

    def wait_for_new_window(
        self,
        old_window_count,
    ):
        try:
            WebDriverWait(
                self.driver,
                20,
            ).until(
                EC.number_of_windows_to_be(
                    old_window_count + 1
                )
            )

        except Exception as exc:
            print(
                f"Error esperando nueva ventana: "
                f"{exc}"
            )

    # ========================================================================
    # VISIBLE
    # ========================================================================

    def is_visible(self, xpath):
        try:
            # Usar el driver Selenium real para comprobaciones
            # opcionales. Así, si el elemento NO existe,
            # Self-Healer no intenta repararlo.
            wait_driver = getattr(
                self.driver,
                "raw",
                self.driver,
            )

            elements = wait_driver.find_elements(
                By.XPATH,
                xpath,
            )

            if elements:
                log.debug("Elemento visible: %s", xpath)
                return True

            log.debug("Elemento no visible: %s", xpath)

            return False

        except Exception as exc:
            print(
                f"Error verificando visibilidad "
                f"{xpath}: {exc}"
            )

            return False


    # ========================================================================
    # CLOSE
    # ========================================================================

    def close_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as exc:
                print(
                    f"Error cerrando navegador: "
                    f"{exc}"
                )

            finally:
                self.driver = None

    # ========================================================================
    # SLEEP
    # ========================================================================

    def time_sleep(
        self,
        time_x: float = 1,
    ) -> None:
        # Sleep messages are DEBUG-only to keep production logs useful.
        log.debug("Esperando %.3f segundos", time_x)
        time.sleep(time_x)
        log.debug("Espera terminada")

    # ========================================================================
    # URL
    # ========================================================================

    def url_actual2(self):
        if not self.driver:
            return ""

        return self.driver.current_url

    def _navigation_timeout_seconds(self) -> float:
        try:
            return max(10.0, float(os.getenv("INSTAGRAM_NAVIGATION_TIMEOUT_SECONDS", "45")))
        except Exception:
            return 45.0

    def go_to_url(self, url):
        timeout = self._navigation_timeout_seconds()
        try:
            # A navigation must never be allowed to block a scheduled task
            # indefinitely. Selenium applies this timeout to get/back/refresh.
            try:
                self.driver.set_page_load_timeout(timeout)
            except Exception:
                pass
            try:
                self.driver.set_script_timeout(timeout)
            except Exception:
                pass
            self.driver.get(url)

        except TimeoutException as exc:
            log.warning(
                "[browser-timeout] navegación excedió %.1fs | url=%s | error=%r",
                timeout, url, exc,
            )
            raise

        except UnexpectedAlertPresentException:
            try:
                alert = self.driver.switch_to.alert
                alert.accept()
            except Exception:
                pass

            self.driver.get(url)

    # ========================================================================
    # WRITE TEXT GENERIC SELECTOR
    # ========================================================================

    def write_text2(
        self,
        selector_type,
        selector,
        text,
    ):
        try:
            WebDriverWait(
                self.driver,
                10,
            ).until(
                EC.presence_of_element_located(
                    (
                        selector_type,
                        selector,
                    )
                )
            )

            element = self.driver.find_element(
                selector_type,
                selector,
            )

            element.send_keys(text)

        except Exception as exc:
            print(
                f"Error escribiendo en elemento: "
                f"{exc}"
            )

    # ========================================================================
    # FIND ELEMENTS XPATH
    # ========================================================================

    def obtener_elementos_xpath(
        self,
        xpath,
        time_x=10,
        base=None,
    ):
        try:
            if base is not None:
                return (
                    base.find_elements(
                        By.XPATH,
                        xpath,
                    )
                    or []
                )

            return WebDriverWait(
                self.driver,
                time_x,
            ).until(
                EC.presence_of_all_elements_located(
                    (
                        By.XPATH,
                        xpath,
                    )
                )
            )

        except Exception as exc:
            print(
                f"Error obteniendo elementos "
                f"xpath {xpath}: {exc}"
            )

            return []

    # ========================================================================
    # ELEMENT TEXT
    # ========================================================================

    def get_element_text(
        self,
        xpath_or_element,
        default="",
        normalize=False,
        max_len=None,
        time_x=10,
    ):
        try:
            if isinstance(
                xpath_or_element,
                str,
            ):
                element = WebDriverWait(
                    self.driver,
                    time_x,
                ).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            xpath_or_element,
                        )
                    )
                )

            else:
                element = xpath_or_element

            text = (
                element.text or ""
            ).strip()

            if normalize:
                text = re.sub(
                    r"\s+",
                    " ",
                    text,
                ).strip()

            if max_len is not None:
                text = text[:max_len]

            return (
                text
                if text
                else default
            )

        except Exception as exc:
            print(
                f"Error obteniendo texto: "
                f"{exc}"
            )

            return default

    # ========================================================================
    # OBTENER ELEMENTOS
    # ========================================================================

    def obtener_elementos(
        self,
        selector,
        time_x=10,
    ):
        return WebDriverWait(
            self.driver,
            time_x,
        ).until(
            EC.presence_of_all_elements_located(
                (
                    By.XPATH,
                    selector,
                )
            )
        )

    # ========================================================================
    # HUMAN LIKE SCROLL
    # ========================================================================

    def human_like_scroll(
        self,
        element_or_xpath,
    ):
        try:
            # ---------------------------------------------------------------
            # Elemento Selenium o HealableWebElement
            # ---------------------------------------------------------------

            if isinstance(
                element_or_xpath,
                WebElement,
            ):
                element = element_or_xpath

            elif hasattr(
                element_or_xpath,
                "is_displayed",
            ) and hasattr(
                element_or_xpath,
                "click",
            ):
                # Compatible con HealableWebElement.
                element = element_or_xpath

            elif isinstance(
                element_or_xpath,
                str,
            ):
                element = self.driver.find_element(
                    By.XPATH,
                    element_or_xpath,
                )

            else:
                raise TypeError(
                    "element_or_xpath debe ser "
                    "un WebElement, HealableWebElement "
                    "o XPath."
                )

            # ---------------------------------------------------------------
            # Visibility
            # ---------------------------------------------------------------

            if not element.is_displayed():
                print(
                    "Element not displayed."
                )
                return False

            # ---------------------------------------------------------------
            # Window
            # ---------------------------------------------------------------

            window_height = self.driver.execute_script(
                "return window.innerHeight"
            )

            element_position = self.driver.execute_script(
                """
                return arguments[0]
                    .getBoundingClientRect()
                    .top;
                """,
                element,
            )

            scroll_adjustment = (
                element_position
                - (window_height / 2)
            )

            # ---------------------------------------------------------------
            # No scrolling needed
            # ---------------------------------------------------------------

            if abs(scroll_adjustment) < 5:
                time.sleep(
                    random.uniform(
                        0.3,
                        0.8,
                    )
                )
                return True

            # ---------------------------------------------------------------
            # Steps
            # ---------------------------------------------------------------

            num_steps = max(
                1,
                int(
                    abs(
                        scroll_adjustment
                    ) / 50
                ),
            )

            step = (
                scroll_adjustment
                / num_steps
            )

            for _ in range(num_steps):
                self.driver.execute_script(
                    "window.scrollBy(0, arguments[0]);",
                    step,
                )

                time.sleep(
                    random.uniform(
                        0.05,
                        0.25,
                    )
                )

            time.sleep(
                random.uniform(
                    0.5,
                    1.5,
                )
            )

            return True

        except NoSuchElementException:
            print(
                "Element not found with provided XPath."
            )
            return False

        except Exception as exc:
            print(
                f"An error occurred during scroll: "
                f"{exc}"
            )
            return False

    # ========================================================================
    # PAGE LOAD
    # ========================================================================

    def wait_for_page_load(
        self,
        timeout=10,
    ):
        try:
            WebDriverWait(
                self.driver,
                timeout,
            ).until(
                lambda driver: driver.execute_script(
                    "return document.readyState"
                )
                == "complete"
            )

            return True

        except Exception:
            return False

    # ========================================================================
    # SCROLL INIT
    # ========================================================================

    def scroll_init(self):
        self.driver.execute_script(
            "window.scrollTo(0, 0)"
        )

    # ========================================================================
    # CLICK2
    # ========================================================================

    def click2(
        self,
        xpath,
        timeX=10,
        scroll=False,
    ):
        last_exc = None

        for _ in range(3):
            try:
                element = WebDriverWait(
                    self.driver,
                    timeX,
                ).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            xpath,
                        )
                    )
                )

                element.click()

                if scroll:
                    self.scroll_to_element(
                        element
                    )

                print(
                    f"Se clickeó: {xpath}"
                )

                self.time_sleep(1)

                return element

            except StaleElementReferenceException as exc:
                last_exc = exc
                self.time_sleep(1)

            except Exception as exc:
                last_exc = exc
                self.time_sleep(1)

        raise Exception(
            f"Failed to click {xpath} "
            f"after 3 attempts. "
            f"Last error: {last_exc}"
        )

    # ========================================================================
    # SCROLL TO ELEMENT
    # ========================================================================

    def scroll_to_element(
        self,
        element,
    ):
        return self.human_like_scroll(
            element
        )

    # ========================================================================
    # PROXY VALIDATION
    # ========================================================================

    @staticmethod
    def validar_proxy(
        url,
        proxy_ip,
        proxy_port,
        proxy_usuario,
        proxy_contraseña,
    ):
        """
        Verifica si un proxy autenticado funciona.
        """

        proxies = {
            "http": (
                f"http://{proxy_usuario}:"
                f"{proxy_contraseña}@"
                f"{proxy_ip}:{proxy_port}"
            ),
            "https": (
                f"http://{proxy_usuario}:"
                f"{proxy_contraseña}@"
                f"{proxy_ip}:{proxy_port}"
            ),
        }

        try:
            response = requests.get(
                url or "https://www.facebook.com/",
                proxies=proxies,
                timeout=5,
            )

            return response.status_code == 200

        except requests.exceptions.ProxyError:
            print("Error de Proxy")

        except requests.exceptions.ConnectTimeout:
            print(
                "Tiempo de conexión agotado"
            )

        except requests.exceptions.SSLError:
            print(
                "Error SSL, posible problema "
                "con el proxy HTTPS"
            )

        except requests.exceptions.RequestException as exc:
            print(
                f"Error realizando solicitud: "
                f"{exc}"
            )

        return False

    # ========================================================================
    # ELEMENT WITHOUT CLASSES / DATA
    # ========================================================================

    def obtener_elemento_sin_clases(
        self,
        xpath,
    ):
        def eliminar_clases_y_atributos_data(
            elemento,
        ):
            script = """
            (function eliminarClasesYAtributosDataRecursivamente(elemento) {
                elemento.removeAttribute('class');
                elemento.removeAttribute('id');

                for (
                    let i = 0;
                    i < elemento.attributes.length;
                    i++
                ) {
                    const attr = elemento.attributes[i];

                    if (
                        attr.name.startsWith('data-')
                    ) {
                        elemento.removeAttribute(
                            attr.name
                        );
                        i--;
                    }
                }

                Array.from(
                    elemento.children
                ).forEach(
                    el =>
                        eliminarClasesYAtributosDataRecursivamente(
                            el
                        )
                );
            })(arguments[0]);
            """

            self.driver.execute_script(
                script,
                elemento,
            )

        try:
            elemento = self.driver.find_element(
                By.XPATH,
                xpath,
            )

            eliminar_clases_y_atributos_data(
                elemento
            )

            return elemento.get_attribute(
                "outerHTML"
            )

        except Exception as exc:
            print(
                "Error obteniendo elemento "
                "sin clases/data: "
                f"{exc}"
            )

            return None

    # ========================================================================
    # BACK
    # ========================================================================

    def go_back_page(self):
        try:
            self.driver.back()

        except Exception as exc:
            print(
                f"Error retrocediendo página: "
                f"{exc}"
            )

    # ========================================================================
    # REFRESH
    # ========================================================================

    def recargar_navegador(self):
        try:
            self.driver.refresh()

        except Exception as exc:
            print(
                f"Error recargando navegador: "
                f"{exc}"
            )

    # ========================================================================
    # COOKIES
    # ========================================================================

    def get_cookies(self):
        return self.driver.get_cookies()

    # ========================================================================
    # POST SCOPE
    # ========================================================================

    def resolve_post_scope_from_anchor(
        self,
        anchor_el,
        container_rules,
        timeX=10,
    ):
        """
        container_rules:

            [
                (
                    rel_xpath_desde_anchor,
                    list_xpath_global,
                ),
                ...
            ]

        Ejemplo:

            [
                (
                    "./ancestor::div["
                    "contains(@data-pagelet,'FeedUnit')"
                    "][1]",
                    "//div["
                    "contains(@data-pagelet,'FeedUnit')"
                    "]",
                ),
                (
                    "./ancestor::div[@role='article'][1]",
                    "//div[@role='article']",
                ),
            ]
        """

        if anchor_el is None:
            raise Exception(
                "anchor_el es None."
            )

        post_el = None
        root_list_xpath = None

        for rel_xpath, list_xpath in container_rules:
            try:
                tmp = anchor_el.find_element(
                    By.XPATH,
                    rel_xpath,
                )

                if self.driver.find_elements(
                    By.XPATH,
                    list_xpath,
                ):
                    post_el = tmp
                    root_list_xpath = list_xpath
                    break

            except Exception:
                continue

        if (
            post_el is None
            or root_list_xpath is None
        ):
            raise Exception(
                "No pude resolver el contenedor "
                "del post desde el anchor_el."
            )

        containers = self.driver.find_elements(
            By.XPATH,
            root_list_xpath,
        )

        post_idx = None

        for j, container in enumerate(
            containers,
            start=1,
        ):
            try:
                same = self.driver.execute_script(
                    """
                    return arguments[0] === arguments[1];
                    """,
                    container,
                    post_el,
                )

                if same:
                    post_idx = j
                    break

            except Exception:
                continue

        if not post_idx:
            raise Exception(
                "No pude calcular post_idx "
                "del post contenedor."
            )

        post_root = (
            f"({root_list_xpath})"
            f"[{post_idx}]"
        )

        return {
            "root_list_xpath": root_list_xpath,
            "post_idx": post_idx,
            "post_root": post_root,
        }

    # ========================================================================
    # REACT + COMMENT
    # ========================================================================

    def react_and_comment_same_post(
        self,
        *,
        like_xpath: str,
        reaction_xpaths: list,
        container_rules: list,
        comment_btn_suffix_xpath: str,
        textbox_suffix_xpath: str,
        submit_suffix_xpath: str,
        message: str,
        timeX_click: int = 10,
        scroll: bool = True,
        fallback_textbox_global_xpath: str = "",
        fallback_submit_global_xpath: str = "",
        **kwargs,
    ) -> dict:

        if not reaction_xpaths:
            raise Exception(
                "reaction_xpaths está vacío."
            )

        reaction_xpath = random.choice(
            reaction_xpaths
        )

        self.click(
            like_xpath,
            xpath_hover=reaction_xpath,
            timeX=timeX_click,
            scroll=scroll,
            hover=True,
        )

        anchor_el = getattr(
            self,
            "last_anchor_element",
            None,
        )

        if anchor_el is None:
            raise Exception(
                "No existe "
                "self.last_anchor_element."
            )

        scope = (
            self.resolve_post_scope_from_anchor(
                anchor_el,
                container_rules,
                timeX=timeX_click,
            )
        )

        post_root = scope["post_root"]

        for name, value in (
            (
                "comment_btn_suffix_xpath",
                comment_btn_suffix_xpath,
            ),
            (
                "textbox_suffix_xpath",
                textbox_suffix_xpath,
            ),
            (
                "submit_suffix_xpath",
                submit_suffix_xpath,
            ),
        ):
            if not value.startswith("//"):
                raise Exception(
                    f"{name} debe empezar con '//'."
                )

        comment_btn_xpath = (
            post_root
            + comment_btn_suffix_xpath
        )

        textbox_xpath = (
            post_root
            + textbox_suffix_xpath
        )

        submit_xpath = (
            post_root
            + submit_suffix_xpath
        )

        self.click(
            comment_btn_xpath,
            timeX=timeX_click,
            scroll=True,
            hover=False,
        )

        self.time_sleep(1)

        try:
            self.click(
                textbox_xpath,
                timeX=timeX_click,
                scroll=True,
                hover=False,
            )

            self.time_sleep(4)

            self.write_text(
                textbox_xpath,
                message,
                fast_t=0.1,
            )

            self.time_sleep(1)

            self.click(
                submit_xpath,
                timeX=timeX_click,
                scroll=True,
                hover=False,
            )

        except Exception:
            if (
                fallback_textbox_global_xpath
                and fallback_submit_global_xpath
            ):
                self.write_text(
                    fallback_textbox_global_xpath,
                    message,
                    fast_t=0.1,
                )

                self.time_sleep(6)

                self.click(
                    fallback_submit_global_xpath,
                    timeX=timeX_click,
                    scroll=True,
                    hover=False,
                )

            else:
                raise

        return scope

    # ========================================================================
    # COUNT FUNDS
    # ========================================================================

    def contar_fondos(
        self,
        timeout: int = 20,
    ) -> int:
        contenedor_xpath = (
            "//div["
            "contains(@class,'x78zum5') "
            "and contains(@class,'x1a02dak') "
            "and contains(@class,'x1g0dm76')"
            "]"
        )

        contenedor = self.driver.find_element(
            By.XPATH,
            contenedor_xpath,
        )

        fondos = contenedor.find_elements(
            By.XPATH,
            ".//div[@role='button' and @aria-label]",
        )

        return len(fondos)

    # ========================================================================
    # SAFE ELEMENTS
    # ========================================================================

    def get_elements_safe(
        self,
        xpath: str,
        time_x: int = 2,
        base=None,
    ) -> list:
        try:
            if base is not None:
                return (
                    base.find_elements(
                        By.XPATH,
                        xpath,
                    )
                    or []
                )

            return WebDriverWait(
                self.driver,
                time_x,
            ).until(
                EC.presence_of_all_elements_located(
                    (
                        By.XPATH,
                        xpath,
                    )
                )
            )

        except Exception as exc:
            print(
                f"Safe lookup failed "
                f"xpath={xpath} | "
                f"error={exc!r}"
            )

            return []

    # ========================================================================
    # MOBILE ORIENTATION
    # ========================================================================

    def set_mobile_orientation(
        self,
        orientation: str = "portrait",
    ) -> bool:
        """
        Cambia la orientación del viewport móvil emulado.

        orientation:
            portrait
            landscape
        """

        if not self.driver:
            print(
                "Driver no inicializado"
            )
            return False

        if not self.mobile_mode:
            print(
                "El navegador no fue abierto "
                "en modo móvil"
            )
            return False

        try:
            profile = (
                self.mobile_profile_config
                or self._get_mobile_emulation_profile(
                    self.mobile_profile_name
                    or "instagram_android"
                )
            )

            metrics = profile.get(
                "deviceMetrics",
                {},
            )

            base_width = int(
                metrics.get("width", 430)
            )

            base_height = int(
                metrics.get("height", 932)
            )

            pixel_ratio = float(
                metrics.get("pixelRatio", 3.0)
            )

            orientation = (
                orientation
                or "portrait"
            ).strip().lower()

            if orientation == "landscape":
                width = max(
                    base_width,
                    base_height,
                )

                height = min(
                    base_width,
                    base_height,
                )

                screen_orientation = {
                    "type": "landscapePrimary",
                    "angle": 90,
                }

            else:
                orientation = "portrait"

                width = min(
                    base_width,
                    base_height,
                )

                height = max(
                    base_width,
                    base_height,
                )

                screen_orientation = {
                    "type": "portraitPrimary",
                    "angle": 0,
                }

            self.driver.execute_cdp_cmd(
                "Emulation.setDeviceMetricsOverride",
                {
                    "mobile": True,
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": pixel_ratio,
                    "screenWidth": width,
                    "screenHeight": height,
                    "screenOrientation": screen_orientation,
                },
            )

            self.driver.execute_script(
                """
                try {
                    window.dispatchEvent(
                        new Event('resize')
                    );

                    window.dispatchEvent(
                        new Event('orientationchange')
                    );

                    document.dispatchEvent(
                        new Event('resize')
                    );

                    document.dispatchEvent(
                        new Event('orientationchange')
                    );
                } catch (e) {}
                """
            )

            print(
                "[browser] Orientación móvil "
                f"cambiada a {orientation}: "
                f"{width}x{height} | "
                f"{screen_orientation}"
            )

            return True

        except Exception as exc:
            print(
                "[browser] Error cambiando "
                f"orientación móvil: {exc}"
            )

            return False
