# Integración del backend de Instagram

El backend Django se registra en `WS /api/v1/bots/ws` como un único adaptador:

```json
{
  "type": "bot.register",
  "bot_key": "instagram-backend-01",
  "name": "Instagram Backend",
  "bot_type": "instagram",
  "capabilities": ["instagram.maduracion", "instagram.prospecting"],
  "max_concurrency": 10,
  "available_slots": 10
}
```

El número de máquinas Selenium queda encapsulado detrás del adaptador. El
orquestador solo ve este bot y los slots que reporta. Se conserva sin cambios el
protocolo WebSocket documentado en `docs/bot-websocket-protocol.md`.

## Variables y dos relaciones de confianza

Hay dos tokens distintos y no deben intercambiarse:

1. `BOT_TOKENS` en el Orchestrator es un mapa `token -> bot_key`. El token usado
   por Django en `ORCHESTRATOR_BOT_TOKEN` debe ser exactamente el mismo valor
   asociado a `instagram-backend-01`.
2. `INSTAGRAM_BACKEND_TOKEN` autentica las llamadas que el Orchestrator hace al
   catálogo Django mediante `X-Orchestrator-Token`. Debe ser exactamente igual a
   `INSTAGRAM_ORCHESTRATOR_TOKEN` en Django.

La URL del catálogo es `INSTAGRAM_BACKEND_URL` y normalmente apunta al backend
Django, por ejemplo `http://10.0.0.90:8004`.

### Importante para Docker

El archivo `.env` del servidor no se copia automáticamente dentro de la imagen.
`docker-compose.yml` debe propagar explícitamente estas variables al servicio
`orchestrator` (y al worker para mantener la configuración consistente). La
versión actual del repositorio ya las propaga:

```env
BOT_TOKENS={"<worker-token>":"instagram-backend-01"}
INSTAGRAM_BACKEND_URL=http://10.0.0.90:8004
INSTAGRAM_BACKEND_TOKEN=<catalog-token>
```

No poner tokens reales en Git. El `.env` de despliegue debe existir solo en el
servidor/Jenkins como secreto. Si el servidor conserva una versión anterior del
Compose que no contiene `INSTAGRAM_BACKEND_URL` y `INSTAGRAM_BACKEND_TOKEN` bajo
`environment`, el contenedor seguirá usando el valor por defecto de la URL y un
token vacío aunque `.env` tenga el valor correcto.

## Verificación del despliegue

La copia del servidor debe incluir el frontend del mismo commit que la API.
Después del despliegue, abrir `/dashboard/app.js` con la sesión del operador
y verificar que importa `/dashboard/app.core.js` y `/dashboard/instagram.js`.
El endpoint `/api/v1/health` no comprueba la versión del frontend. Como
`Dockerfile` copia `frontend/` dentro de la imagen, reconstruir y recrear
`orchestrator` tras actualizar el repositorio; un simple reinicio conserva
los archivos de la imagen anterior.

El backend Django debe definir `INSTAGRAM_TASK_CLAIM_TOKEN` y cada máquina
Instagram debe definir `TASK_API_TOKEN` con ese mismo secreto. Si falta, el
endpoint de toma de tareas devuelve 503; si no coincide, devuelve 401.
El bot no intenta la ruta antigua `pending_bots/` ante esos errores. La
programación `schedule.start_date` se aplica en Django y las tareas futuras
solo se ofrecen después de esa fecha.

Después de actualizar el código en el servidor:

```bash
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d --build orchestrator
```

Verificar que la API publicada es la versión nueva:

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/openapi.json | grep -o '/api/v1/instagram/catalog'
```

Para verificar la configuración sin imprimir secretos completos:

```bash
docker compose --env-file .env exec -T orchestrator \
  python -c 'from orchestrator.core.config import get_settings; s=get_settings(); print("bot_keys=", sorted(set(s.bot_tokens.values()))); print("instagram_url=", s.instagram_backend_url); print("instagram_token_configured=", bool(s.instagram_backend_token)); print("instagram_token_length=", len(s.instagram_backend_token))'
```

Para verificar la conexión del catálogo desde dentro del contenedor sin exponer
el token:

```bash
docker compose --env-file .env exec -T orchestrator \
  python -c 'import httpx; from orchestrator.core.config import get_settings; s=get_settings(); r=httpx.get(s.instagram_backend_url.rstrip("/")+"/api/orchestrator/instagram/catalog/", headers={"X-Orchestrator-Token":s.instagram_backend_token}, timeout=s.bot_request_timeout_seconds); print("catalog_status=",r.status_code); print(r.text[:500])'
```

Si el catálogo responde `200`, la comunicación Orchestrator -> Django está
funcionando. Si responde `401`/`403`, revisar únicamente la pareja
`INSTAGRAM_BACKEND_TOKEN` / `INSTAGRAM_ORCHESTRATOR_TOKEN`. Si hay timeout o
connection refused, revisar red/VPN/firewall y que Django escuche en `10.0.0.90:8004`.

## Verificación del WebSocket

El adaptador Django debe estar ejecutándose con:

```bash
python manage.py run_instagram_orchestrator_adapter
```

En sus variables:

```env
ORCHESTRATOR_URL=http://10.0.0.92:8005
ORCHESTRATOR_WS_URL=ws://10.0.0.92:8005/api/v1/bots/ws
ORCHESTRATOR_BOT_KEY=instagram-backend-01
ORCHESTRATOR_BOT_TOKEN=<mismo-token-que-aparece-en-BOT_TOKENS>
INSTAGRAM_ORCHESTRATOR_TOKEN=<mismo-token-que-INSTAGRAM_BACKEND_TOKEN>
```

El log esperado al conectar es similar a:

```text
[ORCHESTRATOR] registered bot_key=instagram-backend-01
```

El error WebSocket `4401 Invalid bot credentials` significa que el token
presentado en el handshake no coincide con el token que el Orchestrator tiene
mapeado para `instagram-backend-01`. No se soluciona cambiando el token del
catálogo.

## Crear una ejecución autónoma

```http
POST /api/v1/executions/standalone/instagram
Content-Type: application/json
```

Ejemplo para maduración:

```json
{
  "schema_version": "instagram.maduracion.input.v1",
  "stage": "instagram_maduracion",
  "capability": "instagram.maduracion",
  "task_types": [1, 4, 7],
  "targets": {
    "mode": "accounts",
    "account_ids": [12, 45, 78],
    "owner_id": null
  },
  "custom_task": {
    "type": "muro",
    "post": "texto del post",
    "links_image": ["https://example.com/image.jpg"]
  },
  "schedule": {"start_date": "2026-09-18T14:00:00Z"},
  "options": {"bot_executor": null, "max_accounts": 50}
}
```

`capability` acepta `instagram.maduracion` o `instagram.prospecting`.
`task_types` es una lista obligatoria y no vacía de enteros. `targets.mode`
acepta `accounts`, `owner` o `all`; `accounts` exige `account_ids` no vacío y
`owner` exige `owner_id`. `custom_task`, `schedule` y `options` son opcionales.

La respuesta HTTP es `202 Accepted` y contiene la ejecución. Esta usa un
`flow_id` UUID sintético y `step_id: null`; no crea un flow, un flow step ni un
checkpoint. El objeto enviado se guarda íntegro como input y es la respuesta de:

```http
GET /api/v1/executions/{execution_id}/input
```

Cuando hay capacidad, el adaptador recibe el mensaje `execution.run` habitual y
consulta su `input_url`. Si no hay un adaptador online con slots libres, la
ejecución permanece `pending`.

## Resultado

El adaptador termina mediante `execution.succeeded` o `execution.failed`. Un
resultado exitoso tiene esta forma:

```json
{
  "type": "execution.succeeded",
  "execution_id": "uuid-ejecucion",
  "payload": {
    "schema_version": "instagram.maduracion.result.v1",
    "ok": true,
    "stage": "instagram_maduracion",
    "totals": {"created": 12, "ok": 11, "error": 1},
    "tasks": [
      {
        "task_bot_id": 8821,
        "account_id": 45,
        "status": "OK",
        "bot_executor": "Bot_Instagram_DESKTOP-MG4482",
        "end_date": "2026-09-18T15:04:11Z",
        "comment": {}
      }
    ]
  }
}
```

El payload se persiste como un diccionario libre. No se valida contra los
esquemas de resultado SEO ni avanza un workflow, porque la ejecución no tiene
`step_id`.

## Decisión de concurrencia

El control de capacidad se aplica a todos los tipos de bot. Antes de asignar una
ejecución, el orquestador reserva atómicamente en Redis uno de los
`available_slots` reportados. Si no hay capacidad, no envía `execution.run` y
conserva la ejecución en estado `pending`. La reserva por `execution_id` hace
idempotentes los reintentos.

Al registrar el adaptador se intentan despachar pendientes hasta el límite de
slots informado. Cada heartbeat actualiza esa capacidad y, si vuelve a ser
positiva, dispara el mismo intento de despacho de pendientes. El adaptador debe
seguir reportando `current_jobs` y `available_slots` reales en cada heartbeat.
