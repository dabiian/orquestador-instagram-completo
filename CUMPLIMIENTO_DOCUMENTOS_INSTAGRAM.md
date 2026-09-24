# Matriz de cumplimiento — Integración Instagram

Base contractual revisada:

- `instagram-frontend-integration.md`
- `guia_creacion_cuenta_instagram_2026-09-24.md`

Esta matriz separa **implementación** de **validación runtime**. Un requisito puede estar implementado en código y seguir pendiente de la prueba E2E local.

## A. instagram-frontend-integration.md

| § | Requisito | Implementación |
|---|---|---|
| 1 | Crear maduración/prospección, seguimiento, cancelación, resultado/parcial | Implementado |
| 2 | Browser REST → Orquestador; WS privado adaptador; sin BOT_TOKENS | Implementado |
| 3 | POST standalone, estado, eventos, cancelación, resultado, historial, catálogos | Implementado |
| 4 | Protección de operador y same-origin | Implementado |
| 5 | Contrato capability/schema/stage, task_types y targets | Implementado y validado en API |
| 6 | 202, pending/queued, step_id null | Implementado |
| 7.1 | Operación, tareas, targets, custom_task, schedule, opciones | Implementado |
| 7.2 | UUID, capability, estado, bot, timestamps, elapsed, error, eventos, cancelar | Implementado |
| 7.3 | Totales + tabla segura de tareas | Implementado |
| 8 | IDs positivos/únicos, UTC, bloques opcionales | Implementado; API también normaliza targets/task_types |
| 9 | Estado aislado, UUID en URL, sin payloads en localStorage | Implementado |
| 10 | Cliente REST same-origin | Implementado |
| 11 | Polling recursivo 4s, retry 10s, AbortController, terminal stop | Implementado |
| 12 | Eventos incrementales after_sequence | Implementado |
| 13 | Semántica de estados UI | Implementado |
| 14 | Resultado tolerante + JSON fallback | Implementado |
| 15 | Cancelación confirmada; UI espera API | Implementado |
| 16 | Errores HTTP sin retry automático de POST | Implementado |
| 17 | Integración dashboard existente | Implementado como extensión `instagram.js` cargada por `app.js`, evitando alterar el core |
| 18 | labels, aria-describedby, aria-live, escape, sin secretos | Implementado |
| 19 | Pruebas mínimas | Cobertura contractual ampliada; validar suite completa en Docker |
| 20 | Criterios de aceptación | Implementados; validar E2E |
| 21.1 | Proteger POST standalone | Implementado |
| 21.2 | GET result | Implementado |
| 21.3 | Historial paginado Instagram | Implementado API + cursor UI |
| 21.4 | Catálogos | Implementado vía BFF |
| 21.5 | Contrato prospecting | Confirmado por adaptador: `instagram.prospecting.input.v1` / `instagram_prospecting` y resultado simétrico |
| 21.6 | custom_task por capability | El adaptador lo trata como objeto opcional transparente para ambas capabilities; no existe una diferencia adicional documentada por los dos documentos |
| 21.7 | límites máximos | Los documentos no especifican cifras. No se inventan límites. La UI evita congelarse limitando el render inicial de tareas; cualquier límite funcional adicional requiere contrato externo |

### Nota §17

El documento propone editar `index.html`, `app.js` y `styles.css`. La implementación conserva el mismo resultado funcional mediante una extensión aislada: `app.js` importa `instagram.js`, y este agrega la pestaña/vista y estilos reutilizando las clases visuales existentes. Esto evita modificar módulos SEO existentes y mantiene el límite arquitectónico.

## B. guia_creacion_cuenta_instagram_2026-09-24.md

| Sección | Requisito | Implementación |
|---|---|---|
| Resumen | 6 registros en orden, proxy opcional | Implementado en wizard |
| 1 | Personalidad; campos opcionales; ESPAÑOL | Implementado |
| 2 | Owner + owner_urls + services | Implementado |
| 3 | Proxy IP única, puerto positivo, credenciales nullable, un proxy por cuenta | Implementado + prueba |
| 4 | Cuenta: group, owner, credentials, personality/proxy opcionales, account_kind | Implementado |
| 4 | Plataforma no almacenada/derivada de account_type | Catálogo y adaptador usan assignment |
| 4 | PATCH update_cookie acepta array incluso vacío | Implementado + prueba |
| 5 | Campaña: cuenta, name<=150, platform, draft default, snapshots y datos negocio | Implementado |
| 5 | Modificación solo PATCH; PUT no aceptado | Implementado (405) + prueba |
| 6 | Assignment cuenta↔campaña; role prospecting; límites; unique pair | Implementado |
| Verificación | GET campaigns/active usa assignment activo y campaña active | Implementado |
| Errores | proxy reutilizado, required fields, choices, duplicate assignment | Implementado/validado |
| Detalle | GET /api/social_medias/{id}/ expandido | Implementado + prueba contractual |

## C. Antes de declarar runtime 100%

Ejecutar, sobre la rama actual:

1. Migraciones Django.
2. Tests Django de provisioning y catálogo/adaptador.
3. Tests pytest del Orquestador.
4. Cargar dashboard y probar accesibilidad/flujo en navegador.
5. Crear una cuenta real completa desde el Orquestador.
6. Verificar `/active/`.
7. Confirmar que aparece en catálogo.
8. Ejecutar maduración y prospección.
9. Verificar pending → queued → running → terminal, eventos, resultado y cancelación.
10. Confirmar que el bot Selenium consume los TaskBot y libera capacidad.

Hasta completar C, la afirmación correcta es: **contrato implementado en código; validación runtime pendiente**.
