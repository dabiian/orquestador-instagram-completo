# Verificación de la integración Instagram

## Trazabilidad del contrato

| Paso | Implementación | Evidencia verificable |
| --- | --- | --- |
| Entrada desde CRM Vue | `Fronted-Instagram-master/.../AppSidebar.vue` y `CreateTasksView.vue` | El enlace abre el dashboard autenticado del orquestador sin incluir tokens ni crear una tarea directa duplicada. |
| Formulario y catálogo | `frontend/instagram.js` -> `GET /api/v1/instagram/catalog` | Cuentas y tareas reales cargan sin exponer el token de Django. |
| Crear ejecución | `POST /api/v1/executions/standalone/instagram` | Devuelve 202 y un ID; `capability`, `schema_version` y `stage` concuerdan. |
| Despacho | `DispatchExecution` -> `WS /api/v1/bots/ws` | La ejecución pasa de `pending` a `queued` cuando se conecta el adaptador. |
| Adaptador Django | `run_instagram_orchestrator_adapter` | Registra capabilities, recupera input con token de bot y crea TaskBot vinculadas al ID. |
| Máquina Instagram | `POST /api/orchestrator/instagram/tasks/claim/` | Bearer `TASK_API_TOKEN` coincide con `INSTAGRAM_TASK_CLAIM_TOKEN`; solo toma tareas Instagram con fecha vencida. |
| Seguimiento | `GET /executions/{id}` y `/events?after_sequence=` | Los estados y eventos se actualizan sin duplicados. |
| Finalización | `GET /executions/{id}/result` | Devuelve payload, totales y tareas, también si hubo resultado parcial. |

## Antes de probar en el servidor

Antes de solicitar otro despliegue, ejecutar en Windows desde la raíz del
repositorio `powershell -ExecutionPolicy Bypass -File .\verify-instagram-local.ps1`.
Comprueba los cuatro proyectos sin crear una ejecución. Requiere Python 3.12,
Node/npm y acceso a dependencias; no requiere Docker ni PostgreSQL. La prueba
real de creación de TaskBot sí necesita PostgreSQL.

Si `/api/v1/instagram/catalog` devuelve 404 y `/dashboard/app.js` sigue siendo
el antiguo archivo extenso, diagnosticar qué copia atiende el puerto 8005
antes de reconstruir de nuevo. En el host de Docker, desde la carpeta de Compose:

```bash
git rev-parse --short HEAD
docker compose --env-file .env ps
docker compose --env-file .env exec -T orchestrator sh -c 'head -n 5 /app/frontend/app.js; test -s /app/frontend/instagram.js && echo instagram-js-present'
docker compose --env-file .env exec -T orchestrator python -c 'from orchestrator.main import create_app; print("catalog_registered=", "/api/v1/instagram/catalog" in create_app().openapi()["paths"])'
```

Si el checkout es nuevo pero el contenedor muestra el archivo antiguo, revisar
la imagen que está usando. Si el contenedor registra la ruta pero el host da
404, revisar qué proceso o proxy publica 8005. No compartir valores de `.env`.

En la máquina del orquestador, desde el directorio que contiene `docker-compose.yml`:

```bash
git rev-parse --short HEAD
docker compose --env-file .env up -d --build orchestrator
docker compose --env-file .env exec -T orchestrator sh -c 'head -n 5 /app/frontend/app.js && test -s /app/frontend/instagram.js && echo instagram-js-present'
```

`/dashboard/app.js`, abierto en el navegador autenticado, debe importar
`app.core.js` e `instagram.js`. Un `200` de `/api/v1/health` por sí solo no
comprueba el frontend. Si el servidor aún entrega el antiguo `app.js` largo,
comprobar la ubicación real de `docker-compose.yml`, el directorio `build.context`
y la imagen del contenedor que publica el puerto 8005.

En Django configurar `INSTAGRAM_TASK_CLAIM_TOKEN` y en cada bot Windows
`TASK_API_TOKEN` con el mismo secreto. Mantener aparte los tokens del WebSocket
(`BOT_TOKENS`/`ORCHESTRATOR_BOT_TOKEN`) y del catálogo
(`INSTAGRAM_BACKEND_TOKEN`/`INSTAGRAM_ORCHESTRATOR_TOKEN`). No imprimir sus valores.
Ejecutar la migración `dashboard/0017_orchestrator_instagram` y el comando
`python manage.py run_instagram_orchestrator_adapter` como proceso persistente.

Reconstruir también la imagen del frontend Vue de Instagram. Si la URL del
orquestador visible desde el navegador difiere de `10.0.0.92:8005`, pasar
`--build-arg VITE_ORCHESTRATOR_DASHBOARD_URL=https://.../dashboard/` al construir.
Comprobar el enlace **Ejecuciones orquestadas** en el menú y en **Crear tareas**.
El CRM Vue continúa conectado solo a Django para el trabajo directo; la
pantalla de ejecuciones permanece en el dashboard del orquestador conforme al
alcance de `instagram-frontend-integration.md`.

## Prueba controlada

1. En el dashboard, comprobar que el catálogo muestra cuentas y tareas Instagram.
2. Elegir **una cuenta de prueba** y una tarea expresamente aprobada para esa cuenta. No seleccionar `all` ni un propietario completo.
3. Crear una ejecución y guardar el UUID. `pending` significa espera del adaptador; no repetir el POST.
4. Seguir el mismo UUID en historial, eventos y resultado; verificar `pending/queued/running` y estado terminal.
5. Comparar el `task_bot_id` del resultado con la tarea creada en Django. Comprobar que la máquina tomó esa misma tarea y que su estado final, cuenta y comentario aparecen en el resultado.
6. En otra ejecución controlada, comprobar cancelación y resultado parcial sin repetir un POST incierto.

Las pruebas Django que necesitan modelos con `ArrayField` requieren PostgreSQL.
Las pruebas locales de autenticación sin base de datos y las pruebas unitarias del
orquestador no sustituyen esta ejecución de extremo a extremo.

## Límites y trabajos pendientes

El backend Django conserva otros endpoints heredados de TaskBot con
`AllowAny`; el token nuevo protege únicamente el endpoint de toma de tareas.
Revisar autorización del resto antes de exponerlos fuera de la red confiable.
El repositorio también contiene archivos de credenciales de terceros ya
versionados: tratar sus secretos como expuestos y coordinar su rotación y retirada
del historial con sus responsables.
