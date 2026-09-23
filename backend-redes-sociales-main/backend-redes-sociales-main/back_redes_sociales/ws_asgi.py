import os
import django

from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "back_redes_sociales.settings")

# Inicializar Django antes de importar modelos
django.setup()

import dashboard.routing

application = ProtocolTypeRouter({
    # en este proceso sólo queremos manejar websockets
    "websocket": URLRouter(dashboard.routing.websocket_urlpatterns),
})