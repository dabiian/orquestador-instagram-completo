import json
import logging
import time

from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ActiveWebSocketConnection

logger = logging.getLogger(__name__)

class MyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room"]
        self.room_group_name = f"chat_{self.room_name}"
        self.client_ip = (self.scope.get("client") or [None])[0]
        self.connected_at = time.monotonic()

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        logger.info(
            "WebSocket conectado | channel=%s | room=%s | ip=%s",
            self.channel_name,
            self.room_name,
            self.client_ip,
        )

        # Esta tabla es solamente observabilidad. Un fallo de BD no debe cerrar
        # una conexión WebSocket que ya fue aceptada correctamente.
        try:
            await ActiveWebSocketConnection.objects.acreate(
                channel_name=self.channel_name,
                room=self.room_name,
                ip=self.client_ip,
            )
        except Exception:
            logger.exception(
                "No se pudo registrar la conexión WebSocket en BD | "
                "channel=%s | room=%s | ip=%s",
                self.channel_name,
                self.room_name,
                self.client_ip,
            )

    async def disconnect(self, close_code):
        duration = time.monotonic() - getattr(self, "connected_at", time.monotonic())
        logger.warning(
            "WebSocket desconectado | channel=%s | room=%s | ip=%s | "
            "close_code=%s | duration=%.1fs",
            self.channel_name,
            getattr(self, "room_name", None),
            getattr(self, "client_ip", None),
            close_code,
            duration,
        )

        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )
        except Exception:
            logger.exception(
                "No se pudo retirar el WebSocket del grupo | channel=%s | room=%s",
                self.channel_name,
                getattr(self, "room_name", None),
            )

        try:
            await ActiveWebSocketConnection.objects.filter(
                channel_name=self.channel_name
            ).adelete()
        except Exception:
            logger.exception(
                "No se pudo eliminar la conexión WebSocket de BD | channel=%s",
                self.channel_name,
            )

    async def receive(self, text_data=None, bytes_data=None):
        # manejar mensajes entrantes (aquí simplemente los reenvía al grupo)
        if text_data is not None:
            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                logger.warning(
                    "Mensaje WebSocket JSON inválido | channel=%s | room=%s",
                    self.channel_name,
                    self.room_name,
                )
                return

            try:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat.message",  # esto invoca a chat_message()
                        "message": data,
                    },
                )
            except Exception:
                # Redis/capa de canales tampoco debe derribar el socket sin
                # dejar un diagnóstico claro.
                logger.exception(
                    "Error enviando mensaje al grupo WebSocket | "
                    "channel=%s | room=%s",
                    self.channel_name,
                    self.room_name,
                )

    # cualquier evento enviado al grupo con "type": "chat.message" llega aquí
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))
