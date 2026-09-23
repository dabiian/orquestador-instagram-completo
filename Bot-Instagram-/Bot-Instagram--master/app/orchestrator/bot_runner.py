# app/orchestrator/bot_runner.py
import queue
import threading
import time
import datetime
import asyncio
import os
import sys
import signal
import contextlib
import traceback

# from app.api.azteca import PendingBotsAPI
from .instagram_controller import InstagramController
from app.orchestrator.communicator import BotComunicador


@contextlib.contextmanager
def _ignore_sigint_temporarily():
    """
    Evita que Ctrl+C interrumpa el driver.quit()/service shutdown a mitad,
    que es lo que te genera el stacktrace de Service.__del__.
    """
    old = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        yield
    finally:
        try:
            signal.signal(signal.SIGINT, old)
        except Exception:
            pass

from app.core.interfaces import IAIAPI, IAccountAPI, ITaskAPI, IBrowser

class EjecutaBot:
    def __init__(self, name: str, task_api: ITaskAPI, ai_api:IAIAPI,account_api: IAccountAPI):  
        self.name_bot = name
        self.task_api = task_api
        self.ai_api = ai_api
        self.account_api = account_api
        self.running = True
        self.pause_bot_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.status_logs_queue = queue.Queue()
        self.comunicador = BotComunicador(name, self.running)
        self._shutdown_requested = False
        self._active_run = None

    def _safe_put_status(self, msg: str):
        try:
            self.status_queue.put(msg)
        except Exception:
            pass

    def shutdown(self, reason: str = "shutdown"):
        """
        Cierre limpio best-effort. No debe reventar jamás.
        """
        self._shutdown_requested = True
        try:
            self.running = False
        except Exception:
            pass

        print(f"\nParando ejecucion ({reason})...")
        self._safe_put_status(f"Parando ejecucion ({reason})...")

        run = self._active_run
        if run is not None:
            with _ignore_sigint_temporarily():
                
                for m in ("close", "shutdown", "stop", "quit"):
                    try:
                        fn = getattr(run, m, None)
                        if callable(fn):
                            fn()
                            break
                    except Exception:
                        pass

                
                for attr in ("driver", "browser"):
                    try:
                        drv = getattr(run, attr, None)
                        if drv is not None and hasattr(drv, "quit"):
                            drv.quit()
                            break
                        if drv is not None and hasattr(drv, "close"):
                            drv.close()
                            break
                    except Exception:
                        pass

   
        try:
            for m in ("shutdown", "stop", "close"):
                fn = getattr(self.comunicador, m, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass
        except Exception:
            pass

    
    def run_bot(self, task):
        """
        Método principal para ejecutar el bot.
        """
        
        comunicacion_thread = threading.Thread(
            target=lambda: asyncio.run(
                self.comunicador.communicate(
                    self.pause_bot_queue, self.status_queue, self.status_logs_queue
                )
            ),
            daemon=True,
        )
        comunicacion_thread.start()
        try:
            while True:
                if self._shutdown_requested:
                    break

                try:
                    self.running = self.pause_bot_queue.get_nowait()
                    if self.running:
                        print("Va a ejecutar")
                        self._safe_put_status("Listo para ejecutar")
                    else:
                        print("Se pauso el proceso")
                        self._safe_put_status("Se pauso el bot")
                except queue.Empty:
                    pass

                if self._shutdown_requested:
                    break

                if self.running:
                    print("--Consultando BD--")
                    self._safe_put_status("Consultando Base de datos")

                    try:
                        success, data = self.task_api.get_pending_bots()
                    except Exception as e:
                        print(f"Error inesperado al consultar bots pendientes: {e}")
                        self._safe_put_status(f"Error de conexión: {e}")
                        time.sleep(10)
                        continue

                    if success:
                        for bot in data:
                            if self._shutdown_requested:
                                break

                            if bot.get("status_process") == "EP":
                                try:
                                    self.ejecuta(bot)
                                    success, data = self.task_api.get_pending_bots()
                                except ValueError as e:
                                    print(f"Error al ejecutar el bot: {e}")

                        for bot in data:
                            if self._shutdown_requested:
                                break

                            if bot.get("status_process") == "SP":
                                try:
                                    ok, respose = self.task_api.update_task(
                                        bot["id"],
                                        self.name_bot,
                                        "EP",
                                        {"status": "Ejecutando..."},
                                    )
                                    print("Update DB: ", respose)
                                    break
                                except Exception as e:
                                    print(f"Error al ejecutar el bot: {e}")

                    time.sleep(10)
                else:
                    time.sleep(1)

        except KeyboardInterrupt:         
            self.shutdown("Ctrl+C")

        except Exception as e:
            print(f"Error fatal en run_bot: {e}")
            traceback.print_exc()
            self._safe_put_status(f"Error fatal: {e}")
            self.shutdown("Error fatal")

        finally:
            try:
                comunicacion_thread.join(timeout=2)
            except Exception:
                pass

            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass

            os._exit(0)

    def ejecuta(self, bot):
        start_time = time.time()

        print(bot["social_media_account"]["account_name"])
        self.status_queue.put(
            f'Ejecutando cuenta: {bot["social_media_account"]["account_name"]} a las {datetime.datetime.now().strftime("%H:%M:%S")}'
        )

        run = InstagramController(bot,self.task_api,self.ai_api,self.account_api)
        self._active_run = run  

        try:
            print("numero de tareas a ejecutar: ", len(bot["task_type"]))
            print("tareas disponibles: ", bot["task_type"])

            task_id = list(bot["task_type"])
            rta, messes = run.instagram_main(task_id)

            end_time = time.time()
            duration = end_time - start_time
            formatted_duration = "{:.2f} segundos".format(duration)

            if rta:
                ok, rta2 = self.task_api.update_task(
                    bot["id"],
                    self.name_bot,
                    "OK",
                    messes,
                    datetime.datetime.now().isoformat(),
                )
                self.status_queue.put(
                    f"Proceso ejecutado con {ok}, duración: {formatted_duration}"
                )
                print(f"Se actualizo en {ok}", rta2)
            else:
                self.task_api.update_task(
                    bot["id"],
                    self.name_bot,
                    "ER",
                    messes,
                    datetime.datetime.now().isoformat(),
                )
                self.status_queue.put(
                    f"Error en el proceso, duración: {formatted_duration}"
                )
                print("Se actualizo en ERR")

        finally:
            try:
                if self._active_run is not None:
                    
                    close_fn = getattr(self._active_run, "close", None)
                    if callable(close_fn):
                        close_fn()
                    else:
                        
                        nave = getattr(self._active_run, "nave", None)
                        if nave is not None:
                            cb = getattr(nave, "close_browser", None)
                            if callable(cb):
                                cb()
            except Exception as e:
                print(f"⚠️ Error cerrando InstagramController en finally: {e}")
            finally:
                self._active_run = None
                
    def pause(self):
        self.paused = True
        self.comunicador.pause()