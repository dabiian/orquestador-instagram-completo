# Auditoría multiindustria — Bot Instagram — 2026-09-20

## Resultado

La versión entregada está muy avanzada y la migración multiindustria está estructuralmente bien implementada, pero la revisión encontró dos problemas reales en la ruta de Task 10 que impedían considerar que toda la configuración de seguridad/temporización se aplicara también cuando Task 10 hacía el flujo inline `follow + comment + like`.

También se encontró una discrepancia real en el renderizado de placeholders de las alertas `07_alerts.json`.

Estos tres puntos fueron corregidos en esta versión auditada.

## Evidencia de configuración

- El archivo de configuración RAR contiene 41 JSON de configuración canónica.
- Los 41 paths están presentes en `app/config/business_config`.
- Los 41 SHA-256 coinciden exactamente con `tests/config_source_sha256.json`.
- Los duplicados de `app/utils/config/instagram_policies` y `app/utils/config/response_rules` que corresponden a la configuración canónica son byte-identical.
- Los JSON canónicos pasan parseo sin errores.
- Las 7 industrias principales (`abogados`, `botanica`, `cleaning`, `fences`, `marketing`, `spa`, `spa colombia`) cargan correctamente `02`, `03`, `04`, `05` y `06` mediante `InstagramConfigRuntimeService`.

Nota: el entorno de auditoría no tenía un extractor RAR funcional (`unrar`/`7z`), por lo que no fue posible hacer una comparación byte-a-byte directa contra el contenido comprimido del RAR. La validación de contenido se hizo contra el manifiesto SHA-256 incluido en el propio proyecto y contra los 41 archivos canónicos extraídos del bot.

## Task 10 — hallazgos corregidos

### 1. Safety gate bypass en inline engagement

Task 10 sí utilizaba `InstagramSafetyGate` para `follow`, pero el camino inline hacía directamente:

- `comment_current_post()`
- `like_current_post()`

sin consultar/consumir los límites configurados.

Eso podía saltarse:

- `new_intro_comments_max`
- límite vitalicio de comentario por cuenta
- `likes_loves_max`
- límite semanal de likes por cuenta

Ahora el flujo inline consulta y registra el `safety_gate` para comentario y like.

### 2. Delays configurados no se aplicaban completamente en Task 10

El helper `_sleep_between_follows_if_needed()` existía pero no se invocaba desde el flujo inline. Además, faltaban los delays específicos antes del comentario y del like.

Ahora Task 10 aplica:

- `between_follows`
- `post_detected_to_intro_comment`
- `between_likes`
- y conserva `between_intro_comments` en el ciclo de discovery.

### 3. Resolución de industria de Task 10

El `safety_gate` se inicializaba inicialmente desde `campaign_type` directo con fallback a `botanica`, antes de resolver `industry_target`/`industry`.

Ahora Task 10 normaliza primero la industria usando la misma resolución multiindustria y después construye el `safety_gate`.

## Alertas 07 — hallazgo corregido

El JSON de alertas usa varios nombres de placeholder distintos para el mismo dato:

- `[Time]` vs `TIMESTAMP`
- `[Q1]`..`[Q4]` vs `Q1 ANSWER`..`Q4 ANSWER`
- `[Direct link to Facebook post]` vs `FACEBOOK POST LINK`

El renderer no resolvía esos alias, por lo que podían quedar placeholders literales en las alertas WhatsApp/email.

Ahora se resuelven ambos vocabularios y se añadió una prueba específica para impedir regresiones.

## Cobertura por tareas

### Task 10 — Discovery

- Industria de campaña normalizada.
- Hashtags obtenidos desde estrategia y fallback a `03_discovery_hashtags.json`.
- Validación de hashtags contra política configurada.
- Filtro de competencia desde `02_competitor_filter.json` mediante el motor determinista + prompt completo.
- Reglas de clasificación multiindustria.
- Comentario generado usando `04_intro_comment_policy.json`.
- Safety gate de follow/comment/like.
- Delays de configuración.
- Modo `NO_RESPONSE -> like only` usando workflow configurado.

### Task 11 — Comment

- Industria resuelta desde campaña.
- Safety gate aplicado.
- Comentario generado con las reglas de industria y `04_intro_comment_policy.json`.
- Delay `post_detected_to_intro_comment` aplicado.
- Flujo de publicación protegido contra duplicados/reintentos incorrectos.
- Limpieza de superficie/modal verificada.

### Task 12 — Reply monitor

- Industria resuelta por campaña.
- Respuestas clasificadas.
- Flujo unificado de conversación usando `05`/`06`.
- Ventana de respuesta configurada.
- Mínimos de preguntas antes de alerta tomados del JSON.
- Prioridad de alerta tomada del JSON.
- `HUMAN_TAKEOVER` respetado.
- Delay `comment_to_auto_reply` tomado de configuración.
- Alertas enviadas por el servicio de configuración `07` cuando existe.

## Pruebas ejecutadas

- `PYTHONPATH=. pytest -q tests`
- Resultado final: **172 passed**.
- `python -m compileall -q app tests self_healer`
- Resultado: **PASS**.
- Parseo de todos los JSON canónicos: **PASS**.
- Carga runtime de las 7 industrias: **PASS**.
- Comparación SHA-256 de 41 archivos canónicos: **41/41 PASS**.
- Comparación de duplicados canónicos bajo `utils/config`: **35/35 PASS**.

## Limitaciones de la validación

No se ejecutó una sesión real contra Instagram/Chrome ni contra el servidor de tareas porque esta auditoría no dispone de una sesión autenticada de Instagram ni de un entorno real equivalente al servidor productivo. Por tanto, las pruebas realizadas validan lógica, configuración, wiring, estados, parsing, políticas y caminos deterministas; no certifican que Instagram mantenga exactamente el mismo DOM o comportamiento externo durante una ejecución real.

## Conclusión técnica

Después de las correcciones, la versión queda en un estado coherente para la migración multiindustria de las Tasks 10, 11 y 12 a nivel de código/configuración y pruebas automatizadas.

No se debe interpretar el resultado como una garantía de ejecución real en Instagram: esa última capa requiere una corrida controlada contra el servidor y una cuenta de prueba.
