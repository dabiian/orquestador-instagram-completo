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
| 17 | Integración dashboard existente | Implementado: pestaña/vista en `index.html`, carga desde `app.js`, estilos en `styles.css` y lógica aislada en `instagram.js` |
| 18 | labels, aria-describedby, aria-live, escape, sin secretos | Implementado |
| 19 | Pruebas mínimas | Cobertura contractual ampliada; validar suite completa en Docker |
| 20 | Criterios de aceptación | Implementados; validar E2E |
| 21.1 | Proteger POST standalone | Implementado |
| 21.2 | GET result | Implementado |
| 21.3 | Historial paginado Instagram | Implementado API + cursor UI |
| 21.4 | Catálogos | Implementado vía BFF |
| 21.5 | Contrato prospecting | Confirmado por adaptador: `instagram.prospecting.input.v1` / `instagram_prospecting` y resultado simétrico |
| 21.6 | custom_task por capability | Confirmado por la implementación del adaptador: el mismo objeto `custom_task` se propaga a `TaskBot` para maduración y prospección; no hay variante por capability en el contrato actual |
| 21.7 | límites máximos | Confirmado con el equipo: pueden quedar vacíos. `daily_limit`/`total_limit` son opcionales (`null`) y, cuando se configuran, controlan prospectos identificados por cuenta/campaña mediante usage diario e histórico. `links_image` y `post` siguen opcionales y sin máximo finito cuando no se configura una guía. `options.max_accounts` se mantiene separado: limita cuentas procesadas por una ejecución, no prospectos históricos. |

### Nota §17

La integración ya está plasmada en los archivos indicados por la guía: `index.html` contiene la pestaña y la vista hermana; `styles.css` contiene los estilos Instagram reutilizando variables/clases del dashboard; `app.js` carga el módulo aislado `instagram.js`, donde vive el estado y la lógica para no mezclarla con el core SEO.

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

Hasta completar C, la afirmación correcta es: **100% del contrato definido por los dos documentos y las aclaraciones del equipo está plasmado en código; la validación runtime sigue pendiente. §21.7 queda cerrado con límites opcionales: vacío/null significa que no se configuró un máximo finito.**


## D. Aclaración funcional de límites (§21.7)

La aclaración del equipo se implementa así:

- `daily_limit`: máximo opcional de prospectos distintos identificados por una cuenta/campaña durante el día. Vacío → `null` → sin máximo diario configurado.
- `total_limit`: máximo histórico opcional de prospectos distintos identificados por una cuenta/campaña. Vacío → `null` → sin máximo histórico configurado.
- El backend expone el consumo de esos límites y el bot de discovery lo consulta antes y durante la identificación; al agotarse una cuota configurada detiene nuevas identificaciones.
- `options.max_accounts` conserva el significado del contrato del Orquestador: cantidad máxima de cuentas a procesar en una ejecución. No se reutiliza como límite histórico de prospectos.
- `custom_task.post` y `custom_task.links_image` son opcionales. Si el equipo no fija una guía de longitud/cantidad, no se inventa un máximo. Cuando se proporcionan imágenes, la UI valida URLs HTTPS.
- La generación personal de posts/stories conserva el contexto por cuenta (personalidad, ubicación y contexto de tarea/campaña), de modo que una guía futura de longitud/cantidad puede añadirse sin convertirla en un valor global obligatorio para todas las cuentas.
