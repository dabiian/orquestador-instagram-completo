# Guía del Backend - Redes Sociales

## Descripción General

Este es un backend Django + Django Channels para gestionar bots de redes sociales (Facebook, Instagram, Twitter, etc.). Proporciona:

- **API REST** para gestionar cuentas, tareas y bots
- **WebSocket** para comunicación en tiempo real entre el backend y los clientes/bots
- **Enrutamiento dinámico** de tareas a diferentes plataformas sociales
- **Sistema de autenticación** basado en tokens (DRF)

---

## Estructura del Proyecto
backend-redes-sociales/
├── back_redes_sociales/ # Configuración general del proyecto
│ ├── settings.py # Configuración de Django
│ ├── urls.py # Enrutador HTTP principal
│ ├── asgi.py # Configuración ASGI (HTTP + WebSocket)
│ ├── ws_asgi.py # ASGI solo para WebSocket (puerto 8001)
│ └── wsgi.py # Configuración WSGI (solo HTTP)
│
├── dashboard/ # Aplicación principal
│ ├── models.py # Modelos de BD (Bot, Cuenta, Tarea, etc.)
│ ├── views.py # Vistas REST API
│ ├── views_v2.py # Vistas REST API v2
│ ├── urls.py # Rutas HTTP
│ ├── routing.py # Rutas WebSocket
│ ├── consumers.py # Lógica de WebSocket
│ └── serializers.py # Serializadores DRF
│
└── venv/ # Entorno virtual Python

---

## Funciones Esenciales

### 1. **Modelos de Base de Datos**

#### `BotPersonalities`
- Define tipos de bots (personalidades): bot agresivo, pasivo, neutral, etc.
- Se asignan a cada bot para dar un "carácter" a las respuestas.

#### `SocialMediaPlatforms`
- Plataformas soportadas: Facebook, Instagram, Twitter, TikTok, etc.

#### `AccountOwners`
- Dueños de cuentas sociales (usuarios del sistema).

#### `SocialMediaAccounts`
- Cuentas reales de redes sociales vinculadas a un dueño.
- Ejemplo: cuenta de Facebook `mi_negocio_123` del usuario `jorge`.

#### `TaskTypes`
- Tipo de tarea: "responder comentario", "enviar mensaje privado", "publicar estado", etc.

#### `TaskBots`
- Asignación de bots a tareas específicas.
- Ejemplo: El bot "Agresivo" responde comentarios en Facebook.

#### `TaskPending`
- Tareas pendientes por ejecutar.
- Contiene: qué tarea, en qué cuenta, para qué bot, estado (pendiente/en progreso/completada).

---

## Flujo de Funcionamiento

### Flujo HTTP (API REST)
Cliente Request (GET/POST/PUT/DELETE)
↓
urls.py (enrutador)
↓
views.py (ViewSets REST)
↓
serializers.py (validación)
↓
models.py (BD)
↓
Response JSON

**Endpoints principales:**

GET /api/bot_personalities → Listar personalidades
GET /api/social_media_platforms → Listar plataformas
GET /api/account_owners → Listar dueños
GET /api/social_media_accounts → Listar cuentas
POST /api/generate_tasks → Crear tareas
GET /api/view_tasks → Ver tareas pendientes
GET /api/pending_bots → Ver tareas por bot
POST /api/v2/generate_tasks → Crear tareas (versión 2)

### Flujo WebSocket (Comunicación en Tiempo Real)

Cliente WS (ws://127.0.0.1:8001/ws/Bot_Facebook_DESKTOP-CJ16S4J/)
↓
routing.py (enrutador WS)
↓
consumers.py (lógica WS)
↓
Channel Layer (gestión de mensajes)
↓
Retorno de datos en tiempo real

**Proceso WebSocket:**

1. Cliente conecta a `ws://127.0.0.1:8001/ws/{room_name}/`
2. `routing.py` enruta a `MyConsumer`
3. `connect()` acepta la conexión y agrega el canal a un grupo
4. `receive()` recibe mensajes del cliente
5. `group_send()` reenvía mensajes a todos los clientes del grupo
6. `disconnect()` desconecta y limpia recursos

---

## Puertos y Servidores

### Puerto 8000 - HTTP (API REST)

```powershell
# Inicia el servidor Django normal
python manage.py runserver 127.0.0.1:8000

# O con uvicorn
uvicorn back_redes_sociales.asgi:application --host 127.0.0.1 --port 8000

Uso:

Crear/leer/actualizar/eliminar bots, cuentas y tareas
Autenticación por token

Puerto 8001 - WebSocket (Comunicación Real-Time)

# Inicia solo el servidor WebSocket
uvicorn back_redes_sociales.ws_asgi:application --host 127.0.0.1 --port 8001 --reload

Uso:

Los bots se conectan aquí para recibir tareas en tiempo real
El backend envía notificaciones de nuevas tareas, actualizaciones de estado, etc.
Channel Layer: Redis vs InMemory
¿Qué es Channel Layer?
Es el sistema que gestiona la comunicación entre consumers (conexiones WebSocket).
Cuando un bot envía un mensaje, el channel layer se encarga de distribuirlo a otros
bots en el mismo grupo.

InMemoryChannelLayer (Desarrollo Local)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

Características:

✅ Sin dependencias externas
✅ Fácil de configurar
✅ Ideal para desarrollo local
❌ No persiste datos entre reinicios
❌ No funciona con múltiples procesos/servidores
❌ Solo guarda mensajes en RAM del proceso actual
Cuándo usarlo:

Desarrollo local en una sola máquina
Testing rápido
Prototipado
Ejemplo de uso:

uvicorn back_redes_sociales.ws_asgi:application --host 127.0.0.1 --port 8001
# Funciona inmediatamente, sin necesidad de Redis

RedisChannelLayer (Producción)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

Características:

✅ Persiste datos entre reinicios
✅ Funciona con múltiples procesos/servidores
✅ Mayor rendimiento en producción
❌ Requiere instalar y mantener Redis
❌ Dependencia externa

Cuándo usarlo:

Ambiente de producción
Múltiples instancias de uvicorn corriendo
Necesidad de persistencia de mensajes
Requisitos:

# en Windows (WSL2):
# Descargar e instalar Redis desde https://redis.io/download

# Luego en otra terminal:
redis-server
# Verás: "Ready to accept connections"

Flujo Completo: Crear una Tarea
1. Usuario crea tarea vía API REST

POST http://127.0.0.1:8000/api/generate_tasks/
{
    "task_type_id": 1,
    "bot_personality_id": 2,
    "account_ids": [5, 10]
}

2. Backend crea registros en BD

TaskPending creados para cada cuenta:
- task_type_id: 1 (responder comentario)
- bot_personality_id: 2 (bot pasivo)
- account_id: 5
- status: "pendiente"

2. Backend crea registros en BD

Bot conectado a ws://127.0.0.1:8001/ws/Bot_Facebook_DESKTOP-CJ16S4J/

Channel Layer envía:
{
    "type": "task.new",
    "task_id": 123,
    "account_id": 5,
    "task_type": "responder_comentario"
}

4. Bot procesa tarea

Bot descarga detalles:
GET /api/social_media_accounts/5/
GET /api/view_tasks/?bot_id=123

5. Bot ejecuta y reporta resultado

POST /api/view_tasks/123/
{
    "status": "completada",
    "result": "Tarea ejecutada exitosamente"
}

Instalación y Configuración Inicial
1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate

2. Instalar dependencias

pip install -r requirements.txt

3. Configurar base de datos

python manage.py migrate

4. Crear superusuario

python manage.py createsuperuser

5. Levantar servidores

Terminal 1 - HTTP:

python manage.py runserver 127.0.0.1:8000

Terminal 2 - WebSocket:

uvicorn back_redes_sociales.ws_asgi:application --host 127.0.0.1 --port 8001 --reload

Terminal 3 - Redis (si usas RedisChannelLayer):

redis-server


Autenticación y Permisos
API REST: Token-based (DRF TokenAuthentication)
WebSocket: Puede usar el mismo token o custom authentication
Obtener token:

POST http://127.0.0.1:8000/api-token-auth/
{
    "username": "tu_usuario",
    "password": "tu_contraseña"
}

Usar token en API:

GET http://127.0.0.1:8000/api/bot_personalities/
Authorization: Token abc123def456...

## Pending bots v2

El endpoint optimizado consulta unicamente las tareas asignadas a un bot:

```text
GET /api/v2/pending_bots/?bot_name=Bot_Facebook_DESKTOP-CJ16S4J
```

`bot_name` es obligatorio y debe coincidir exactamente con
`TaskBot.bot_executor`. Sin enviar otro estado, el backend devuelve solamente
tareas `EP` y `EQ`. Tambien admite los filtros opcionales `status_process` y
`account_id`; `status_process` reemplaza el filtro predeterminado.

La respuesta conserva el formato de lista, devuelve 10 elementos por defecto
y acepta `page_size` hasta 100. Las tareas se entregan de la mas antigua a la
mas reciente segun `start_date`; si dos tareas tienen la misma fecha y hora,
se desempatan por `id`. Si existen mas resultados, el header HTTP `Link`
contiene la URL de la siguiente pagina.

`start_date` y `end_date` se devuelven en la zona horaria de Bogota con el
offset explicito `-05:00`; por ejemplo, `2026-06-30T07:40:00-05:00`.

El endpoint anterior `/api/pending_bots/` permanece disponible sin cambios
para compatibilidad con clientes existentes.

Troubleshooting
Error: "No route found for path 'ws/...'"
→ Revisar que routing.py tenga el patrón correcto

Error: "settings are not configured"
→ Asegurar que DJANGO_SETTINGS_MODULE está en settings.py antes de imports

Error: "ConnectionRefusedError" en Redis
→ Iniciar Redis: redis-server o cambiar a InMemoryChannelLayer

Error: "Unsupported upgrade request"
→ Instalar: pip install "uvicorn[standard]"



