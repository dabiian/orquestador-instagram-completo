# Frontend del orquestador para el bot de Instagram

## 1. Objetivo

Esta guía describe cómo agregar al dashboard del orquestador una interfaz para:

- crear ejecuciones autónomas de maduración y prospección de Instagram;
- seguir sus estados y eventos;
- cancelar una ejecución activa;
- consultar y presentar el resultado final;
- mostrar resultados parciales cuando el bot falle.

La implementación debe integrarse en el frontend existente de `frontend/`, que
actualmente utiliza HTML, CSS y JavaScript sin framework.

## 2. Límite arquitectónico

El navegador **no debe conectarse** a `WS /api/v1/bots/ws`. Ese WebSocket es un
canal privado entre el adaptador Django y el orquestador:

```text
Navegador ──REST──> Orquestador ──WebSocket──> Adaptador Django ──> N Selenium
```

El frontend tampoco debe conocer ni almacenar `BOT_TOKENS`. Para el navegador,
el adaptador y las máquinas Selenium son detalles internos.

El flujo normal es:

```text
1. Usuario completa el formulario
2. Frontend crea una ejecución mediante POST
3. Orquestador responde 202 con execution_id
4. Frontend consulta estado y eventos
5. Adaptador procesa el trabajo por WebSocket
6. Frontend consulta el resultado cuando la ejecución termina
```

## 3. API disponible y dependencias pendientes

### Endpoints existentes

| Operación | Endpoint | Estado actual |
|---|---|---|
| Crear | `POST /api/v1/executions/standalone/instagram` | Implementado |
| Consultar estado | `GET /api/v1/executions/{execution_id}` | Implementado; requiere operador del dashboard |
| Consultar eventos | `GET /api/v1/executions/{execution_id}/events` | Implementado; requiere operador |
| Cancelar | `POST /api/v1/executions/{execution_id}/cancel` | Implementado; requiere operador |
| Leer input | `GET /api/v1/executions/{execution_id}/input` | Solo para el bot asignado; el frontend no debe usarlo |

### Endpoints que debe completar el desarrollador del API

#### Lectura del resultado

Debe agregarse:

```http
GET /api/v1/executions/{execution_id}/result
```

Requisitos:

- autenticación de operador del dashboard;
- comprobar que la ejecución existe;
- comprobar que `output_document_id` está informado;
- recuperar el documento desde `seo_flow_documents`;
- devolver su `payload`, no el documento interno completo de Mongo;
- responder `409` o `404` mientras el resultado todavía no exista;
- no permitir al navegador consultar MongoDB directamente.

Respuesta recomendada:

```json
{
  "execution_id": "uuid-ejecucion",
  "status": "succeeded",
  "payload": {
    "schema_version": "instagram.maduracion.result.v1",
    "ok": true,
    "stage": "instagram_maduracion",
    "totals": {"created": 12, "ok": 11, "error": 1},
    "tasks": []
  }
}
```

#### Historial

Para construir una pantalla de historial sin conocer UUID previamente se necesita
un endpoint paginado, por ejemplo:

```http
GET /api/v1/executions?bot_type=instagram&status=running&limit=50&cursor=...
```

El filtro no debe depender solamente del `bot_id`, porque las ejecuciones
`pending` todavía no tienen bot asignado. Debe identificar las capabilities
`instagram.maduracion` e `instagram.prospecting`.

#### Catálogos de cuentas y tareas

`targets.account_ids`, `targets.owner_id` y `task_types` contienen identificadores
del backend Django. El orquestador no dispone actualmente de un catálogo para
presentarlos al usuario.

La solución recomendada es exponer endpoints de consulta a través del
orquestador, o de un backend-for-frontend, por ejemplo:

```http
GET /api/v1/instagram/accounts?owner_id=123&search=...
GET /api/v1/instagram/owners?search=...
GET /api/v1/instagram/task-types
```

El navegador no debería conectarse directamente al backend Django si eso obliga a
duplicar autenticación, exponer secretos internos o habilitar CORS entre sistemas.
Mientras no exista el catálogo, la primera versión puede admitir IDs escritos o
pegados manualmente, dejando claro que son identificadores de Django.

## 4. Autenticación

Las consultas de estado, eventos y cancelación ya utilizan la identidad del
operador del dashboard. El frontend debe continuar usando solicitudes del mismo
origen y nunca incorporar credenciales en el bundle:

```js
fetch(url, {
  credentials: "same-origin",
  headers: { "Content-Type": "application/json" },
});
```

El endpoint de creación de Instagram debe recibir la misma protección de operador.
Actualmente la ruta no declara esa dependencia, por lo que el desarrollador del
API debe agregarla antes de considerar terminada la pantalla.

No reutilizar el Bearer token del bot para autenticar el frontend.

## 5. Contrato de creación

### Endpoint

```http
POST /api/v1/executions/standalone/instagram
Content-Type: application/json
```

### Maduración

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
  "schedule": {
    "start_date": "2026-09-18T14:00:00Z"
  },
  "options": {
    "bot_executor": null,
    "max_accounts": 50
  }
}
```

### Prospección

La capability `instagram.prospecting` ya está aceptada por el orquestador. Sin
embargo, el contrato exacto de `schema_version`, `stage` y los bloques específicos
de prospección debe confirmarse con el equipo del adaptador Django antes de
hardcodearlo en el frontend.

Si el equipo confirma el patrón simétrico, el mapeo sería:

```js
const INSTAGRAM_OPERATIONS = {
  maduracion: {
    capability: "instagram.maduracion",
    schemaVersion: "instagram.maduracion.input.v1",
    stage: "instagram_maduracion",
  },
  prospecting: {
    capability: "instagram.prospecting",
    schemaVersion: "instagram.prospecting.input.v1", // confirmar con Django
    stage: "instagram_prospecting",                  // confirmar con Django
  },
};
```

No permitir que el usuario combine manualmente una capability con el schema o
stage de otra operación. Los tres valores deben salir de una sola selección.

### Validaciones vigentes

| Campo | Regla del orquestador |
|---|---|
| `schema_version` | String obligatorio y no vacío |
| `stage` | String obligatorio y no vacío |
| `capability` | `instagram.maduracion` o `instagram.prospecting` |
| `task_types` | Lista obligatoria, no vacía, de enteros estrictos |
| `targets.mode` | `accounts`, `owner` o `all` |
| `targets.account_ids` | Obligatorio y no vacío para `accounts` |
| `targets.owner_id` | Obligatorio para `owner` |
| `custom_task` | Opcional |
| `schedule` | Opcional |
| `options` | Opcional |

El frontend debe replicar estas reglas por experiencia de usuario, pero el API
sigue siendo la fuente de verdad.

## 6. Respuesta de creación

El API responde `202 Accepted`:

```json
{
  "id": "uuid-ejecucion",
  "flow_id": "uuid-sintetico",
  "requested_capability": "instagram.maduracion",
  "status": "pending",
  "bot_id": null,
  "step_id": null,
  "input_document_id": "mongo-object-id",
  "output_document_id": null,
  "error_message": null,
  "internal_state": null,
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-09-18T14:00:00Z",
  "updated_at": "2026-09-18T14:00:00Z"
}
```

`pending` no es un error. Significa que no hay slots disponibles o que el
adaptador todavía no está conectado. Si había capacidad, la respuesta puede venir
directamente como `queued`.

`step_id` siempre debe ser `null` para estas ejecuciones autónomas.

## 7. Diseño de la pantalla

Agregar una pestaña principal al dashboard existente:

```html
<button class="workspace-tab" data-view="instagram">Instagram</button>
```

Y una vista hermana de `view-operations`, `view-admin-data` y
`view-post-monitor`:

```html
<div id="view-instagram" class="workspace-view">
  <!-- formulario, seguimiento e historial -->
</div>
```

La vista debería tener tres áreas.

### 7.1 Nueva ejecución

Campos recomendados:

1. Operación: maduración o prospección.
2. Tipos de tarea: selección múltiple basada en el catálogo.
3. Modo de objetivos:
   - cuentas concretas;
   - todas las cuentas de un propietario;
   - todas las cuentas autorizadas.
4. Cuentas o propietario, según el modo.
5. Tarea personalizada, opcional.
6. Programación, opcional.
7. Opciones avanzadas.

El campo `bot_executor` debe estar oculto dentro de “Opciones avanzadas”. En la
operación normal, el adaptador Django decide qué máquina Selenium utiliza.

### 7.2 Seguimiento

Mostrar:

- UUID de ejecución;
- capability;
- estado;
- bot asignado;
- hora de creación, inicio y finalización;
- tiempo transcurrido;
- error terminal;
- eventos recientes, si existen;
- botón de cancelación para `queued` o `running`.

### 7.3 Resultado

Mostrar primero el resumen:

- tareas creadas;
- tareas correctas;
- tareas con error;
- duración, si está presente.

Después, una tabla paginable o virtualizada con:

- `task_bot_id`;
- `account_id`;
- estado;
- ejecutor;
- fecha de finalización;
- comentario o detalle.

No renderizar `comment` mediante `innerHTML`. Debe convertirse a texto seguro o a
una tabla de clave/valor utilizando la función de escape existente.

## 8. Construcción del payload

### Objetivos

```js
function buildInstagramTargets(mode, accountIds, ownerId) {
  if (mode === "accounts") {
    return {
      mode,
      account_ids: [...new Set(accountIds.map(Number))],
      owner_id: null,
    };
  }
  if (mode === "owner") {
    return {
      mode,
      account_ids: null,
      owner_id: Number(ownerId),
    };
  }
  return { mode: "all", account_ids: null, owner_id: null };
}
```

Antes de enviar, eliminar valores `NaN`, IDs no positivos y duplicados. Para modo
`accounts`, bloquear el envío si la lista final queda vacía.

### Fecha programada

`datetime-local` no incluye zona horaria. Convertir el valor local a UTC:

```js
function toUtcIso(localDateTime) {
  return localDateTime ? new Date(localDateTime).toISOString() : null;
}
```

No concatenar una `Z` manualmente: eso cambiaría la hora real del usuario.

### Imágenes

Si la interfaz recibe una URL por línea:

```js
function parseImageLinks(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}
```

Validar cada elemento con `new URL(...)` y admitir solamente protocolos aprobados,
normalmente `https:`.

### Omisión de bloques opcionales

Si `custom_task`, `schedule` u `options` no contienen datos, es preferible omitir
el bloque completo en vez de enviar objetos vacíos. Esto conserva la diferencia
entre “no configurado” y “configurado sin valores”.

## 9. Estado JavaScript recomendado

Extender el objeto `state` de `frontend/app.js`:

```js
const state = {
  // estado existente...
  instagram: {
    loaded: false,
    executions: [],
    currentExecution: null,
    currentResult: null,
    events: [],
    afterSequence: 0,
    pollTimer: null,
    pollController: null,
  },
};
```

No guardar payloads completos ni resultados sensibles en `localStorage`. Si se
quiere conservar la ejecución seleccionada al recargar, colocar únicamente el UUID
en la URL:

```text
/dashboard/?view=instagram&execution_id=<uuid>
```

## 10. Cliente REST

Puede reutilizarse la función `api()` existente. Debe asegurarse de enviar
credenciales del mismo origen:

```js
async function api(path, options = {}) {
  const { headers = {}, ...requestOptions } = options;
  const response = await fetch(`${API}${path}`, {
    credentials: "same-origin",
    ...requestOptions,
    headers: { "Content-Type": "application/json", ...headers },
  });
  // conservar el manejo de errores existente
}
```

Funciones específicas:

```js
async function createInstagramExecution(payload) {
  return api("/executions/standalone/instagram", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function getInstagramExecution(executionId) {
  return api(`/executions/${encodeURIComponent(executionId)}`);
}

async function getInstagramEvents(executionId, afterSequence = 0) {
  const query = new URLSearchParams({
    after_sequence: String(afterSequence),
    limit: "200",
  });
  return api(`/executions/${encodeURIComponent(executionId)}/events?${query}`);
}

async function cancelInstagramExecution(executionId) {
  return api(`/executions/${encodeURIComponent(executionId)}/cancel`, {
    method: "POST",
  });
}

async function getInstagramResult(executionId) {
  return api(`/executions/${encodeURIComponent(executionId)}/result`);
}
```

La última función depende del endpoint de resultado pendiente descrito en §3.

## 11. Polling de estado y eventos

Estados terminales:

```js
const TERMINAL_EXECUTION_STATES = new Set([
  "succeeded",
  "failed",
  "cancelled",
]);
```

Utilizar `setTimeout` recursivo y no `setInterval`, para evitar solicitudes
solapadas:

```js
async function pollInstagramExecution(executionId) {
  clearTimeout(state.instagram.pollTimer);
  state.instagram.pollController?.abort();
  const controller = new AbortController();
  state.instagram.pollController = controller;

  try {
    const execution = await api(
      `/executions/${encodeURIComponent(executionId)}`,
      { signal: controller.signal },
    );
    state.instagram.currentExecution = execution;
    renderInstagramExecution(execution);

    await loadNewInstagramEvents(executionId);

    if (TERMINAL_EXECUTION_STATES.has(execution.status)) {
      state.instagram.currentResult = await getInstagramResult(executionId);
      renderInstagramResult(state.instagram.currentResult);
      return;
    }

    state.instagram.pollTimer = setTimeout(
      () => pollInstagramExecution(executionId),
      4000,
    );
  } catch (error) {
    if (error.name === "AbortError") return;
    renderInstagramPollingError(error);
    state.instagram.pollTimer = setTimeout(
      () => pollInstagramExecution(executionId),
      10000,
    );
  }
}
```

Al cambiar de vista o seleccionar otra ejecución:

```js
clearTimeout(state.instagram.pollTimer);
state.instagram.pollController?.abort();
```

Intervalos recomendados:

- 4 segundos para `pending`, `queued` y `running`;
- 10–15 segundos después de un error transitorio;
- detener en estado terminal;
- no imponer un timeout artificial desde el navegador.

## 12. Eventos de progreso

El endpoint `/events` ya existe, pero la interfaz no debe asumir que el adaptador
de Instagram emite `execution.progress`. El estado de la ejecución funciona sin
eventos.

Si el adaptador empieza a enviarlos, consumirlos incrementalmente mediante
`after_sequence`:

```js
async function loadNewInstagramEvents(executionId) {
  const events = await getInstagramEvents(
    executionId,
    state.instagram.afterSequence,
  );
  if (!events.length) return;
  state.instagram.events.push(...events);
  state.instagram.afterSequence = Math.max(
    ...events.map((event) => event.sequence),
  );
  renderInstagramEvents(state.instagram.events);
}
```

Tratar `summary` y `payload` como datos informativos. Un evento de tipo `error` no
convierte por sí solo la ejecución en fallida; el estado final sigue viniendo de
`GET /executions/{id}`.

## 13. Máquina de estados para la interfaz

| Estado | Texto sugerido | Comportamiento |
|---|---|---|
| `pending` | Esperando capacidad del bot | Seguir consultando; no mostrar error |
| `queued` | Trabajo enviado al adaptador | Habilitar cancelación |
| `running` | Procesando cuentas de Instagram | Mostrar tiempo y eventos |
| `succeeded` | Ejecución finalizada | Cargar resultado |
| `failed` | Ejecución fallida | Mostrar error y resultado parcial si existe |
| `cancelled` | Ejecución cancelada | Mostrar motivo y detener polling |

Aunque una ejecución falle, debe intentarse leer su documento de resultado. El bot
puede haber completado varias cuentas antes del error terminal.

## 14. Contrato del resultado

Ejemplo exitoso:

```json
{
  "schema_version": "instagram.maduracion.result.v1",
  "ok": true,
  "stage": "instagram_maduracion",
  "totals": {
    "created": 12,
    "ok": 11,
    "error": 1
  },
  "tasks": [
    {
      "task_bot_id": 8821,
      "account_id": 45,
      "status": "OK",
      "bot_executor": "Bot_Instagram_DESKTOP-MG4482N",
      "end_date": "2026-09-18T15:04:11Z",
      "comment": {}
    }
  ]
}
```

El frontend debe ser tolerante a campos adicionales. La versión del schema permite
elegir el renderizador adecuado:

```js
function renderInstagramResultEnvelope(result) {
  const payload = result.payload || result;
  switch (payload.schema_version) {
    case "instagram.maduracion.result.v1":
      return renderMaturationResult(payload);
    case "instagram.prospecting.result.v1":
      return renderProspectingResult(payload);
    default:
      return renderDynamicJson(payload);
  }
}
```

El schema de resultado de prospección debe confirmarse con el adaptador antes de
crear un renderizador especializado. El fallback JSON evita dejar la pantalla
vacía cuando aparece una versión desconocida.

## 15. Cancelación

Mostrar el botón solo para `queued` y `running`. Antes de cancelar, pedir
confirmación explícita:

```text
La cancelación puede tardar mientras el bot termina una operación atómica.
¿Deseas continuar?
```

Después de recibir `202`, mantener el polling. No cambiar localmente el estado a
`cancelled` hasta que el API lo confirme.

Deshabilitar el botón durante la petición para evitar dobles clics.

## 16. Errores HTTP

| Código | Tratamiento |
|---|---|
| `202` | Ejecución creada o cancelación aceptada |
| `401` | Solicitar autenticación del operador |
| `403` | Mostrar falta de permisos |
| `404` | Ejecución o resultado inexistente |
| `409` | Resultado todavía no disponible o transición incompatible |
| `422` | Mostrar errores del formulario por campo |
| `503` | Cancelación o despacho temporalmente no disponible |
| `5xx` | Error recuperable; conservar el formulario |

El frontend **no debe repetir automáticamente un POST de creación** cuando la
respuesta sea incierta. El contrato actual no incluye una clave de idempotencia y
un reintento podría crear dos ejecuciones. Mantener el botón deshabilitado mientras
la primera solicitud esté pendiente y pedir confirmación antes de reintentar.

## 17. Integración con los archivos existentes

### `frontend/index.html`

- agregar la pestaña `Instagram`;
- agregar `view-instagram`;
- incluir el formulario;
- agregar tarjetas de estado;
- agregar tabla de eventos y tabla de tareas;
- agregar un diálogo de confirmación para cancelar.

### `frontend/app.js`

- extender `state.instagram`;
- declarar el mapeo de operaciones;
- construir y validar el payload;
- implementar cliente REST;
- implementar polling cancelable;
- renderizar estado, eventos y resultado;
- limpiar timers al cambiar de vista;
- actualizar la URL con el UUID seleccionado.

### `frontend/styles.css`

Reutilizar `workspace-tabs`, `workspace-view`, `card`, `panel`, `field`, `pill`,
`table-wrap` y los colores semánticos existentes. Añadir únicamente estilos para:

- selector múltiple de cuentas y tareas;
- línea temporal de eventos;
- resumen de totales;
- detalle expandible de comentarios;
- diseño responsive de la tabla de tareas.

No crear un segundo sistema visual exclusivo para Instagram.

## 18. Accesibilidad y seguridad de presentación

- Todos los campos deben tener `label` asociado.
- Los errores deben estar conectados mediante `aria-describedby`.
- El cambio de estado debe anunciarse con una región `aria-live="polite"`.
- No depender únicamente del color para diferenciar éxito y fallo.
- Escapar cualquier texto procedente del bot antes de insertarlo en el DOM.
- No usar `innerHTML` con `post`, `comment`, errores ni eventos sin sanitización.
- No mostrar tokens, documentos Mongo internos ni trazas sensibles.
- Confirmar las operaciones destructivas o de alcance `all`.

## 19. Pruebas mínimas del frontend

### Formulario

- `accounts` sin IDs bloquea el envío.
- `owner` sin `owner_id` bloquea el envío.
- `all` no envía IDs residuales de selecciones anteriores.
- `task_types` vacío bloquea el envío.
- los IDs se convierten a enteros y se eliminan duplicados;
- la fecha local se convierte correctamente a UTC;
- los bloques opcionales vacíos se omiten;
- maduración genera exactamente capability, schema y stage acordados.

### Seguimiento

- `pending` no se presenta como error;
- el polling sigue `pending → queued → running → succeeded`;
- el polling se detiene en estados terminales;
- cambiar de ejecución cancela las solicitudes anteriores;
- un error transitorio aumenta el intervalo sin crear otra ejecución;
- recargar la URL recupera el UUID existente.

### Resultado

- éxito muestra totales y tareas;
- fallo muestra `error_message` y el payload parcial;
- un schema desconocido usa el visor JSON;
- comentarios y errores se muestran escapados;
- listas grandes no bloquean el navegador.

### Cancelación y seguridad

- solo `queued` y `running` muestran cancelar;
- el botón queda deshabilitado durante la petición;
- ningún request del navegador contiene `BOT_TOKENS`;
- el frontend no llama a `/input`;
- un usuario sin sesión no consulta ejecuciones ni resultados.

## 20. Criterios de aceptación

- El usuario puede crear una ejecución válida de maduración.
- La ejecución puede permanecer `pending` sin que la UI la declare fallida.
- La vista sigue la ejecución hasta un estado terminal.
- Los eventos son opcionales y no condicionan el seguimiento.
- El resultado exitoso y el parcial de fallo pueden visualizarse.
- La cancelación espera la confirmación real del API.
- El navegador no accede al WebSocket de bots ni utiliza credenciales del adaptador.
- El formulario no permite combinaciones inconsistentes de schema, stage y
  capability.
- La interfaz sigue el diseño y las utilidades del dashboard existente.
- Las dependencias pendientes del API están implementadas antes de publicar la
  pantalla en producción.

## 21. Anotaciones para el desarrollador backend

Antes de dar por terminada la integración frontend:

1. Proteger `POST /standalone/instagram` con la identidad del operador.
2. Implementar `GET /executions/{id}/result`.
3. Implementar un listado paginado de ejecuciones Instagram.
4. Definir cómo obtiene el frontend los catálogos de cuentas, propietarios y
   tipos de tarea.
5. Confirmar con Django los contratos exactos de entrada y resultado de
   `instagram.prospecting`.
6. Documentar si `custom_task` cambia según la capability seleccionada.
7. Confirmar los límites máximos de cuentas, imágenes y tamaño del texto.

Estas anotaciones son requisitos del API y del contrato funcional. No implican que
el navegador deba conocer la topología Selenium ni el protocolo WebSocket.
