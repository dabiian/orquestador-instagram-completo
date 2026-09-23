import json
import random
import signal
import contextlib

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from app.core.browser import Automate
from app.utils.proxy_validator import ProxyValidator
from app.core.interfaces import IBrowser, IAIAPI, IAccountAPI, ITaskAPI
from app.orchestrator.task_dispatcher import (
    parse_task_ids,
    build_default_flujos,
    build_selected_flujos,
)
from app.services.login_service import LoginService


@contextlib.contextmanager
def _ignore_sigint_temporarily():
    old = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        yield
    finally:
        try:
            signal.signal(signal.SIGINT, old)
        except Exception:
            pass


class InstagramController:
    HOME_URL = "https://www.instagram.com/"

    SHARE_STORY_TASK_ID = 4
    SHARE_POST_TASK_ID = 5
    FOLLOWBACK_POST_TASK_ID = 13
    CURATED_SHARE_TASK_ID = 14

    MOBILE_TASK_IDS = {
        SHARE_STORY_TASK_ID,
    }

    HARD_RESET_AFTER_TASK_IDS = {
        SHARE_STORY_TASK_ID,
        SHARE_POST_TASK_ID,
        FOLLOWBACK_POST_TASK_ID,
        CURATED_SHARE_TASK_ID,
    }

    MOBILE_PROFILE_BY_TASK_ID = {
        SHARE_STORY_TASK_ID: "story_large_android",
    }

    REST_MODE_MODAL = (
        "//div[@role='dialog' and .//h3[normalize-space()='Estás en modo descanso']]"
    )

    REST_MODE_ACCEPT_BUTTON = (
        "//div[@role='dialog' and .//h3[normalize-space()='Estás en modo descanso']]"
        "//*[@role='button' and normalize-space()='Aceptar']"
    )

    GENERIC_MODAL_CLOSE_XPATHS = (
        "//*[@role='button' and normalize-space()='Cancelar']",
        "//*[@role='button' and normalize-space()='Cancel']",
        "//*[@role='button' and normalize-space()='Descartar']",
        "//*[@role='button' and normalize-space()='Discard']",
        "//*[@role='button' and normalize-space()='Ahora no']",
        "//*[@role='button' and normalize-space()='Not now']",
        "//*[@role='button' and normalize-space()='Not Now']",

        "//div[@role='dialog']//*[@aria-label='Cerrar']",
        "//div[@role='dialog']//*[@aria-label='Close']",

        "//div[@role='dialog']//*[name()='svg' and (@aria-label='Cerrar' or @aria-label='Close')]/ancestor::*[@role='button' or self::button][1]",
    )

    def __init__(
        self,
        data: dict,
        task_api: ITaskAPI,
        ai_api: IAIAPI,
        account_api: IAccountAPI,
    ):
        self.data = data or {}

        social_media_account = self.data.get("social_media_account") or {}
        proxy_data = social_media_account.get("proxy") or {}

        validator = ProxyValidator()

        self.nave: IBrowser = Automate(
            proxy=str(proxy_data.get("ip_address") or ""),
            port=str(proxy_data.get("port") or ""),
            user=str(proxy_data.get("username") or ""),
            password=str(proxy_data.get("password") or ""),
            proxy_validator=validator,
        )

        self.task_api = task_api
        self.ai_api = ai_api
        self.account_api = account_api
        self.login_service = LoginService(self.nave, self.account_api, self.data)

    def _ensure_execution_context(self) -> None:
        """
        Agrega contexto universal de ejecución al payload.

        IMPORTANTE:
        - Usa UTC, no hora local del servidor.
        - No calcula timezone.
        - No quema ciudades.
        """
        try:
            if not isinstance(self.data, dict):
                self.data = {}

            root_execution_context = self.data.get("execution_context")
            custom_task = self.data.get("custom_task") or {}

            if not isinstance(root_execution_context, dict):
                root_execution_context = {}

            if isinstance(custom_task, dict):
                custom_execution_context = custom_task.get("execution_context")
                if isinstance(custom_execution_context, dict):
                    for key, value in custom_execution_context.items():
                        root_execution_context.setdefault(key, value)

            if not root_execution_context.get("current_datetime_utc"):
                root_execution_context["current_datetime_utc"] = datetime.now(
                    timezone.utc
                ).isoformat()

            root_execution_context.setdefault("source", "bot_controller")
            root_execution_context.setdefault("time_basis", "UTC")

            self.data["execution_context"] = root_execution_context

            print(
                "[execution_context] current_datetime_utc="
                f"{root_execution_context.get('current_datetime_utc')} | "
                f"source={root_execution_context.get('source')} | "
                f"time_basis={root_execution_context.get('time_basis')}"
            )

        except Exception as e:
            print(f"⚠️ No se pudo construir execution_context: {e}")

    def _task_requires_mobile(self, task_id: Any) -> bool:
        try:
            return int(task_id) in self.MOBILE_TASK_IDS
        except Exception:
            return False

    def _task_mobile_profile(self, task_id: Any) -> str:
        try:
            return self.MOBILE_PROFILE_BY_TASK_ID.get(int(task_id), "story_large_android")
        except Exception:
            return "story_large_android"

    def _task_requires_hard_reset_after(self, task_id: Any) -> bool:
        try:
            return int(task_id) in self.HARD_RESET_AFTER_TASK_IDS
        except Exception:
            return False

    def _get_cookie_session(self) -> list:
        try:
            social_media_account = self.data.get("social_media_account") or {}
            credentials = social_media_account.get("other_credentials") or {}
            cookie_session = credentials.get("cookie", [])
            return cookie_session if isinstance(cookie_session, list) else []
        except Exception:
            return []

    def _close_browser_safely(self):
        try:
            self.nave.close_browser()
        except Exception:
            pass

    def _safe_click_if_visible(
        self,
        xpath: str,
        sleep: int = 1,
        scroll: bool = False,
    ) -> bool:
        try:
            if not self.nave.is_visible(xpath):
                return False

            try:
                self.nave.click(xpath, scroll=scroll)
            except TypeError:
                self.nave.click(xpath)

            self.nave.time_sleep(sleep)
            return True

        except Exception:
            return False

    def _cerrar_modal_modo_descanso(self) -> bool:
        try:
            if self.nave.is_visible(self.REST_MODE_MODAL):
                print("⚠️ Apareció modal 'Estás en modo descanso'. Cerrándolo...")

                if self.nave.is_visible(self.REST_MODE_ACCEPT_BUTTON):
                    self.nave.click(self.REST_MODE_ACCEPT_BUTTON, scroll=True)
                    self.nave.time_sleep(2)
                    print("✅ Modal 'Estás en modo descanso' cerrado.")
                    return True

            return False

        except Exception as e:
            print(f"⚠️ No se pudo cerrar el modal 'modo descanso': {e}")
            return False

    def _soft_cleanup_instagram_ui(self) -> bool:
        cleaned = False

        if self._cerrar_modal_modo_descanso():
            cleaned = True

        for _ in range(2):
            closed_one = False

            for xpath in self.GENERIC_MODAL_CLOSE_XPATHS:
                if self._safe_click_if_visible(xpath, sleep=1, scroll=False):
                    cleaned = True
                    closed_one = True
                    break

            if not closed_one:
                break

        return cleaned

    def _wait_page_ready_limited(self, max_attempts: int = 20) -> bool:
        for _ in range(max_attempts):
            try:
                if self.nave.wait_for_page_load():
                    return True
            except Exception:
                pass

            try:
                self.nave.time_sleep(1)
            except Exception:
                pass

        return False

    def _open_and_prepare_instagram_session(self, *, mobile: bool, task_id: Any):
        cookie_session = self._get_cookie_session()
        mobile_profile = self._task_mobile_profile(task_id) if mobile else None

        print(
            f"[browser_debug] Abriendo Instagram | task_id={task_id} | "
            f"mobile={mobile} | mobile_profile={mobile_profile}"
        )

        rta = self.nave.open_browser(
            url=self.HOME_URL,
            cookies_add=cookie_session,
            mobile=mobile,
            mobile_profile=mobile_profile,
        )

        if not rta:
            return False, {"status": "Error en el proxy, depurar"}

        self._soft_cleanup_instagram_ui()

        session_ready = self.login_service.is_session_ready()

        print(f"[login_debug] is_session_ready inicial={session_ready}")
        print(f"[login_debug] current_url={self.nave.url_actual2()}")

        if not mobile:
            inbox_visible = self.nave.is_visible("//a[contains(@href, '/direct/inbox')]")
            print(f"[login_debug] inbox_visible={inbox_visible}")

            if session_ready and not inbox_visible:
                print("[login_debug] Falso positivo de sesión en desktop. Se forzará login.")
                session_ready = False
        else:
            print("[login_debug] mobile=True, se omite validación estricta de inbox desktop.")

        if session_ready:
            self.login_service.dismiss_post_login_dialogs()
            self._soft_cleanup_instagram_ui()
            self._wait_page_ready_limited()
            return True, ""

        social_media_account = self.data.get("social_media_account") or {}
        credentials = social_media_account.get("other_credentials") or {}

        username = (
            credentials.get("User")
            or credentials.get("user")
            or credentials.get("username")
        )
        password = credentials.get("password") or credentials.get("Password")

        if not username or not password:
            self._close_browser_safely()
            return False, "No hay credenciales User/password para iniciar sesión"

        print(f"[login_debug] Iniciando login con usuario={username}")

        login, texto = self.login_service.login(username, password)

        print(f"[login_debug] resultado login={login} | texto={texto}")

        if not login:
            self._close_browser_safely()
            return False, texto

        self.login_service.dismiss_post_login_dialogs()
        self._soft_cleanup_instagram_ui()
        self._wait_page_ready_limited()

        if not mobile:
            try:
                inbox_visible_after_login = self.nave.is_visible(
                    "//a[contains(@href, '/direct/inbox')]"
                )
                print(f"[login_debug] inbox_visible_after_login={inbox_visible_after_login}")

                if not inbox_visible_after_login:
                    print("[login_debug] Login marcado como OK, pero inbox no aparece.")
            except Exception as e:
                print(f"[login_debug] No se pudo validar inbox después del login: {e}")

        return True, ""

    def _append_task_result(
        self,
        *,
        resultados: List[Dict[str, Any]],
        task_id: Any,
        nombre_tarea: str,
        resultado: Any,
    ) -> bool:
        if isinstance(resultado, str):
            task_ok = not resultado.startswith("✗")

            resultados.append(
                {
                    "task_id": task_id,
                    "funcion": nombre_tarea,
                    "message": resultado,
                    "resultado": task_ok,
                }
            )

            return task_ok

        if isinstance(resultado, bool):
            resultados.append(
                {
                    "task_id": task_id,
                    "funcion": nombre_tarea,
                    "resultado": resultado,
                }
            )

            return resultado

        if resultado is None:
            resultados.append(
                {
                    "task_id": task_id,
                    "funcion": nombre_tarea,
                    "resultado": None,
                }
            )

            return False

        task_ok = bool(resultado)

        resultados.append(
            {
                "task_id": task_id,
                "funcion": nombre_tarea,
                "resultado": resultado,
            }
        )

        return task_ok

    def instagram_main(
        self,
        task: Optional[Union[List[Any], str]] = None,
        force_add_grups_last: bool = True,
    ):
        self._ensure_execution_context()

        if task is None:
            task = (
                self.data.get("task", None)
                or self.data.get("tasks", None)
                or self.data.get("task_ids", None)
            )

        task_ids = parse_task_ids(task)

        resultados: List[Dict[str, Any]] = []
        errores = 0

        if task_ids is None:
            flujos = build_default_flujos(
                self,
                browser=self.nave,
                ai_api=self.ai_api,
                account_api=self.account_api,
                data=self.data,
            )
            total_intentos = len(flujos)
        else:
            flujos, prev_results, prev_errors = build_selected_flujos(
                self,
                task_ids,
                browser=self.nave,
                ai_api=self.ai_api,
                account_api=self.account_api,
                data=self.data,
                force_add_grups_last=force_add_grups_last,
            )
            resultados.extend(prev_results)
            errores += prev_errors
            total_intentos = len(task_ids)

        if not flujos:
            self._close_browser_safely()

            resultado_final = {
                "porcentaje_exito": "0%",
                "detalle": (
                    resultados
                    if resultados
                    else [{"error_message": "No hay tareas válidas para ejecutar"}]
                ),
            }

            return False, json.dumps(resultado_final, ensure_ascii=False)

        browser_open = False
        current_mobile_mode: Optional[bool] = None

        for index, (funcion, arg, arg2, arg3) in enumerate(flujos):
            numero_aleatorio = random.randint(2, 5)
            self.nave.time_sleep(numero_aleatorio)

            nombre_tarea = arg2 or (
                arg.__class__.__name__ if arg is not None else funcion.__name__
            )

            task_id = arg3
            required_mobile_mode = self._task_requires_mobile(task_id)

            print(
                f"▶ Ejecutando tarea ID {task_id}: {nombre_tarea} | "
                f"mobile_required={required_mobile_mode}"
            )

            must_reopen_browser = (
                not browser_open
                or current_mobile_mode is None
                or current_mobile_mode != required_mobile_mode
            )

            if must_reopen_browser:
                if browser_open:
                    print(
                        "[browser_debug] Cambió el modo de navegador. "
                        "Cerrando sesión actual para reabrir correctamente..."
                    )
                    self._close_browser_safely()
                    browser_open = False
                    current_mobile_mode = None

                ok_session, session_message = self._open_and_prepare_instagram_session(
                    mobile=required_mobile_mode,
                    task_id=task_id,
                )

                if not ok_session:
                    errores += 1

                    resultados.append(
                        {
                            "task_id": task_id,
                            "funcion": nombre_tarea,
                            "resultado": False,
                            "error_message": session_message,
                        }
                    )

                    tareas_restantes = flujos[index + 1 :]
                    errores += len(tareas_restantes)

                    for _, _, next_name, next_task_id in tareas_restantes:
                        resultados.append(
                            {
                                "task_id": next_task_id,
                                "funcion": next_name,
                                "resultado": False,
                                "error_message": "No se ejecutó porque falló la sesión del navegador.",
                            }
                        )

                    break

                browser_open = True
                current_mobile_mode = required_mobile_mode

            try:
                self._soft_cleanup_instagram_ui()

                resultado = funcion(arg, arg2, arg3)

                task_ok = self._append_task_result(
                    resultados=resultados,
                    task_id=task_id,
                    nombre_tarea=nombre_tarea,
                    resultado=resultado,
                )

                if not task_ok:
                    errores += 1

                self._soft_cleanup_instagram_ui()

            except Exception as e:
                errores += 1

                try:
                    self._soft_cleanup_instagram_ui()
                except Exception:
                    pass

                resultados.append(
                    {
                        "task_id": task_id,
                        "funcion": nombre_tarea,
                        "resultado": False,
                        "error_message": str(e),
                        "error_doc": str(e.__doc__),
                    }
                )

                print(
                    f"[browser_debug] La tarea {task_id} falló. "
                    "Cerrando navegador para evitar estado sucio..."
                )
                self._close_browser_safely()
                browser_open = False
                current_mobile_mode = None
                continue

            has_next_task = index < len(flujos) - 1

            if has_next_task and self._task_requires_hard_reset_after(task_id):
                print(
                    f"[browser_debug] Hard reset después de tarea {task_id} "
                    "para evitar modales residuales."
                )
                self._close_browser_safely()
                browser_open = False
                current_mobile_mode = None

        self._close_browser_safely()

        if total_intentos <= 0:
            porcentaje_exito = 0
        else:
            porcentaje_errores = (errores / total_intentos) * 100
            porcentaje_exito = 100 - porcentaje_errores

        resultado_final = {
            "porcentaje_exito": f"{int(porcentaje_exito)}%",
            "detalle": resultados,
        }

        result_json = json.dumps(resultado_final, ensure_ascii=False)

        if porcentaje_exito < 60:
            return False, result_json

        return True, result_json

    def close(self):
        with _ignore_sigint_temporarily():
            try:
                self.nave.close_browser()
            except Exception:
                pass