# Integración final: clasificador multi-industria + Self-Healer

## Qué quedó conectado

### Clasificador Instagram
- `campaign_type` es la fuente de selección de industria.
- Se cargan los `02_competitor_filter.json` de las 7 industrias.
- La industria detectada se conserva desde la campaña y no puede ser reemplazada por `unknown` devuelto por la IA.
- Se normalizan relaciones específicas como `DIRECT_FENCE_COMPETITOR`, `DIRECT_BOTANICA_COMPETITOR` y `DIRECT_LEGAL_COMPETITOR` al contrato canónico del bot.
- Se incorporan las clasificaciones/verticales adicionales usadas por las reglas espirituales y estéticas.
- El prompt ahora combina detección de competencia por reglas de industria con la clasificación comercial ya probada en `tools/instagram_prompt_lab.py`: `mode`, `selected_service`, `b2b_target_type`, `b2b_angle`, `b2b_confidence`, `request_directness`, `service_match_reason` y `comment`.
- `selected_service` se valida contra `services_snapshot`; el bot nunca acepta una oferta inventada por la IA.

### Self-Healer
- `Automate` envuelve el Selenium WebDriver con `HealableWebDriver` cuando `SELF_HEALER_ENABLED=true`.
- Se reutilizan locators guardados en SQLite antes de llamar a la IA.
- Los candidatos generados por IA se validan contra el DOM real antes de aceptarlos.
- `execute_script`/`execute_async_script` desempaquetan `HealableWebElement` para conservar compatibilidad con Selenium.
- El proveedor admite OpenAI-compatible/DeepSeek y ahora prioriza variables de entorno del proceso, evitando depender de una clave escrita dentro de `self_healer/.env`.

## Configuración

1. Copiar `.env.example` a `.env`.
2. Configurar la URL real del backend.
3. Configurar `DEEPSEEK_API_KEY` si se desea healing con IA.
4. Mantener `SELF_HEALER_ENABLED=true` para activar el healing.
5. En Docker, completar `DEEPSEEK_API_KEY` en `.env.docker`.

## Pruebas ejecutadas

- `test_all_competitor_rules.py`: 7/7 industrias PASS.
- `test_industry_competitor_detection.py`: 10/10 PASS.
- `test_full_instagram_classifier.py`: 14/14 PASS después de corregir la propagación de `industry_detected`.
- `test_instagram_classifier.py`: PASS.
- `tools/instagram_prompt_lab.py`: 10/10 PASS en modo offline.
- Prueba adicional de normalización comercial: PASS.
- `py_compile` sobre el código Python del bot y Self-Healer: PASS.

## Nota sobre el documento de prompts

El documento de prompts contiene algunas variantes con texto cruzado (por ejemplo, la variante `spa` describe fences y la variante `marketing` describe spa/aesthetic). Por eso la implementación usa los `02_competitor_filter.json` correspondientes a cada industria como reglas operativas y conserva la lógica comercial del laboratorio, en vez de copiar literalmente esos bloques inconsistentes.

## Seguridad

No se debe distribuir ni subir al repositorio ningún `.env` que contenga una clave real. La versión limpia entregada debe usar `.env.example`/`self_healer/.env.example`.

### Restricción geográfica de campañas
- `strategy_snapshot.locations` define la zona objetivo de la campaña.
- También se acepta `campaign.locations` como fallback.
- Si `locations` contiene uno o más valores, un candidato solo puede continuar si el clasificador devuelve `location_match=true`.
- `location_match=false` significa que la evidencia coloca al negocio fuera de la zona y el candidato se descarta.
- `location_match=null` significa que no se pudo verificar la ubicación; para campañas restringidas también se descarta para evitar asumir que está dentro de la zona.
- Si `locations=[]` o no existe, la campaña no tiene restricción geográfica y `location_match` se normaliza a `true`.
- Un hashtag de ciudad por sí solo no se considera prueba de ubicación.

### Contrato de skip / calificación
- `skip_post=true` proveniente del clasificador se conserva en el task y no puede ser convertido de nuevo a `valid=True`.
- `mode=skip`, competidor, perfil personal (`COMMON_PERSON`), negocio no relacionado o ubicación no válida fuerzan `skip_post=true`.
- Un candidato descartado recibe `qualification_score=0` y nunca entra al flujo de follow/comment.
