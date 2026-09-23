import asyncio
import json
import os
import queue
import websockets
from dotenv import load_dotenv

load_dotenv()


def _normalize_ws_base_url(value: str) -> str:
    """
    Normaliza la URL base del WebSocket.

    Local:
        ws://localhost:8000/ws/

    Docker:
        ws://backend:8000/ws/
    """
    value = (value or "").strip()

    if not value:
        value = "ws://localhost:8000/ws/"

    return value.rstrip("/") + "/"


class BotComunicador:
    def __init__(self, bot_id, running):
        self.bot_id = bot_id
        self.status_list = "Conectado"
        self.running = running
        self.last_sent_status = None
        self.last_sent_logs = None

        ws_base_url = _normalize_ws_base_url(
            os.getenv(
                "SOCKET",
                os.getenv("WS_BASE_URL", "ws://localhost:8000/ws/")
            )
        )

        self.url = f"{ws_base_url}{self.bot_id}/"

        print(f"[BotComunicador] WebSocket URL: {self.url}")

    async def communicate(self, pause_bot_queue, status_queue, logs_queue):
        async def send_updates(websocket):
            try:
                while True:
                    if not status_queue.empty():
                        status_data = {
                            "type": "update",
                            "status": status_queue.get_nowait(),
                            "running": self.running,
                        }
                        await websocket.send(json.dumps(status_data))

                    if not logs_queue.empty():
                        logs_data = {
                            "type": "update",
                            "logs": logs_queue.get_nowait(),
                            "running": self.running,
                        }
                        await websocket.send(json.dumps(logs_data))

                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print("Error enviando actualizaciones por WebSocket: " + str(e))

        async def receive_messages(websocket):
            try:
                while True:
                    response = await websocket.recv()

                    if isinstance(response, bytes):
                        response = response.decode("utf-8", errors="ignore")

                    response_text = str(response).strip().lower()

                    if response_text in ["true", "false"]:
                        is_running = response_text == "true"
                        pause_bot_queue.put(is_running)
                        self.running = is_running

            except websockets.exceptions.ConnectionClosed:
                print("Conexión WebSocket cerrada por el servidor.")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print("Error recibiendo mensajes por WebSocket: " + str(e))

        while True:
            try:
                async with websockets.connect(self.url) as websocket:
                    print("Conexión establecida socket.", self.url)

                    updated_data = {
                        "type": "create",
                        "running": self.running,
                        "status": self.status_list,
                        "logs": [],
                    }

                    await websocket.send(json.dumps(updated_data))

                    sender_task = asyncio.create_task(send_updates(websocket))
                    receiver_task = asyncio.create_task(receive_messages(websocket))

                    done, pending = await asyncio.wait(
                        [sender_task, receiver_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel()

                    for task in done:
                        exception = task.exception()
                        if exception is not None:
                            print(f"Error en tarea WebSocket: {exception}")

            except websockets.exceptions.ConnectionClosedError as e:
                print(f"Conexión cerrada, reconectando...: {e}")
                await asyncio.sleep(5)

            except ConnectionRefusedError as e:
                print(
                    f"Conexión rechazada por el servidor WebSocket, "
                    f"intentando en 10s...: {e}"
                )
                await asyncio.sleep(10)

            except OSError as e:
                print(
                    f"No se pudo conectar al WebSocket {self.url}, "
                    f"intentando en 10s...: {e}"
                )
                await asyncio.sleep(10)

            except Exception as e:
                print(f"Error en WebSocket: {e}")
                await asyncio.sleep(10)


# Ejemplo de uso local
# if __name__ == "__main__":
#     bot_id = "tu_bot_id"
#     running = True
#     bot_comunicador = BotComunicador(bot_id, running)
#
#     pause_bot_queue = queue.Queue()
#     status_queue = queue.Queue()
#     logs_queue = queue.Queue()
#
#     asyncio.run(bot_comunicador.communicate(pause_bot_queue, status_queue, logs_queue))