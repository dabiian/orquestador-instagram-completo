from typing import Protocol, Any, Tuple, List, Optional, Dict
from selenium.webdriver.remote.webelement import WebElement


class IBrowser(Protocol):
    """
    Capacidad de interactuar con el navegador.
    Consume: todos los flows/tasks, facebook_controller, login_service.
    """

    driver: Any  # acceso al driver para casos especiales (contar_fondos)

    def open_browser(
        self,
        url: str,
        proxy: bool = False,
        cookies_add: Any = None,
        mobile: bool = False,
        mobile_profile: str = "instagram_android",
    ) -> bool: ...
    def close_browser(self) -> None: ...
    def go_to_url(self, url: str) -> None: ...
    def url_actual2(self) -> str: ...
    def recargar_navegador(self) -> None: ...
    def go_back_page(self) -> None: ...
    def scroll_init(self) -> None: ...
    def scroll_to_xpath(
        self, xpath: str, timeX: int = 10, error: bool = True
    ) -> None: ...
    def click(
        self,
        xpath: str,
        xpath_hover: str = "",
        timeX: int = 10,
        scroll: bool = True,
        error: bool = True,
        hover: bool = False,
    ) -> None: ...
    def write_text(
        self,
        xpath_or_element: Any,
        text: str,
        time_x: int = 10,
        rapido: bool = False,
        fast_t: float = 0.1,
        enter: bool = False,
    ) -> None: ...
    def upload_file(
        self, xpath_or_element: Any, file_path: str, time_x: int = 10
    ) -> None: ...
    def is_visible(self, xpath: str) -> bool: ...
    def get_text_and_urls(self, xpath: str) -> Tuple[Optional[str], Optional[list]]: ...
    def get_text_by_xpath(self, xpath: str) -> str: ...
    def get_cookies(self) -> list: ...
    def time_sleep(self, time_x: float = 1) -> None: ...
    def wait_for_page_load(self, timeout: int = 10) -> bool: ...
    def hover(self, xpath: str) -> None: ...
    def obtener_elementos(self, selector: str, time_x: int = 10) -> list: ...
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
    ) -> dict: ...
    def contar_fondos(self, timeout: int = 20) -> int: ...

    def get_elements_safe(
        self, xpath: str, time_x: int = 2, base: Any = None
    ) -> list: ...
    def execute_script_safe(self, script: str, *args: Any) -> Any: ...
    def set_mobile_orientation(self, orientation: str = "portrait") -> bool: ...

class ITaskAPI(Protocol):
    """
    CRUD de tareas del bot.
    Consume: bot_runner.py (EjecutaBot), facebook_controller.py
    """

    def get_pending_bots(self) -> Tuple[bool, Any]: ...
    def update_task(
        self,
        id: Any,
        bot_executor: str,
        status_process: str,
        comment: Any,
        end_date: Optional[str] = None,
    ) -> Tuple[bool, Any]: ...
    def save_img_url(self, id: Any, img_url: Any) -> Any: ...


class IAIAPI(Protocol):
    """
    Generación de contenido con IA (texto e imágenes).
    Consume: text_generator, image_generator, comment_and_like_task,
             perfil_friends_task, messages_task, publish_story_task
    """

    def get_bot_ia(
        self, bot_personality_id: Any, user_prompt: str
    ) -> Tuple[bool, Any]: ...
    def get_bot_ia_image(
        self, user_prompt: str, size_image: str = "1024x1024"
    ) -> Tuple[bool, Any]: ...
    def analize_image(self, url: str, prompt: str) -> Tuple[bool, Any]: ...
    def get_img_edited(
        self, img_path: str, user_prompt: str, username: str, size_image: str = "auto"
    ) -> str: ...
    def download_image_edited(
        self, image_b64: str, filename: str, account_name: str = "not_provided"
    ) -> str: ...


class IAccountAPI(Protocol):
    """
    Gestión de cuenta: cookies, mensajes guardados, descarga de imágenes.
    Consume: login_service, text_generator, image_generator, publish_story_task
    """

    def update_cookie(self, id_user: Any, cookies: Any) -> None: ...
    def get_comments(self, account_id: Any, category: Optional[str] = None) -> Any: ...
    def save_new_comment(
        self, account_id: Any, message_text: str, category: str, metadata: Any
    ) -> Any: ...
    def download_image(self, url: str, filename: str) -> str: ...


# ─── PROXY VALIDATOR ─────────────────────────────────────────────────────────


class IProxyValidator(Protocol):
    """
    Validación de proxies.
    Consume: browser.py (Automate.open_browser)
    """

    def validate(
        self, proxy_ip: str, proxy_port: str, proxy_user: str, proxy_password: str
    ) -> bool: ...


class ILoginService(Protocol):
    """
    Servicio de login que encapsula la lógica de autenticación.
    Consume: `IBrowser`, `IAccountAPI`.
    """

    def login(self, user: str, password: str) -> Tuple[bool, str]: ...



class ITask(Protocol):
    """
    Contrato que toda tarea RPA debe cumplir.
    Consume: task_dispatcher.py (al iterar y ejecutar tareas)
    """

    def execute(self) -> str: ...
