# Corrección final del Bot Instagram — 2026-09-17

## Hallazgos del `bot_log.txt`

La ejecución real llegó correctamente hasta API, WebSocket, campaña, búsqueda de hashtag, apertura de publicaciones, extracción de perfil/posts, clasificación y persistencia. El problema funcional observado fue la clasificación de un negocio local:

- campaña: `Chicago Local Business Growth`
- servicio vendido: marketing
- perfil: `tastebuddiaries`
- evidencia: catering/baking/food y Chicago
- IA: `profile_classification=BUSINESS`
- IA: `industry_detected=food & beverage / catering & baking`
- IA: `competitor_relation=UNRELATED_BUSINESS`
- IA: `commercial_intent_score=18`
- resultado anterior: `qualification_score=0`, `DISCARDED`

En una campaña de **service prospecting**, `marketing` es el servicio que se vende; no debe exigirse que el negocio prospectado pertenezca a la industria `marketing`.

## Cambios aplicados

1. `UNRELATED_BUSINESS` ya no descarta automáticamente un negocio en campañas de service-prospecting de marketing. Solo se mantiene como exclusión determinística para campañas donde realmente representa una industria objetivo distinta.
2. Se agregó recuperación conservadora para un negocio local que la IA subpuntúa: requiere evidencia comercial, ubicación verificada y ausencia de competencia directa/perfil personal.
3. La recuperación nunca fabrica un score alto: usa `60` como piso mínimo de calificación cuando la evidencia permite recuperarlo.
4. Se agregó inferencia determinística de `business_vertical` cuando la IA devuelve `UNKNOWN`, sin sobrescribir un valor específico de la IA.
5. Si `industry_detected` queda vacío/unknown y la evidencia permite identificar el vertical, se completa con el vertical detectado (`food`, `beauty`, `retail`, etc.).
6. Se mantiene la validación de servicios: `selected_service` debe existir exactamente en `services_snapshot`.
7. Se mantienen las protecciones de URL, ubicación, competencia y deduplicación existentes.
8. Se agregó una prueba que reproduce el caso real del log.

## Resultado de pruebas

- `python -m compileall -q app self_healer main.py` → PASS
- Suite principal de lógica/contratos/reglas: **30 passed**
- Prueba específica del caso del `bot_log`: incluida y PASS
- La suite completa no puede ejecutarse en este entorno porque Selenium/Chrome y una sesión real de Instagram no están disponibles.
- La ejecución real del log sí demuestra que el navegador alcanzó el flujo de discovery; el primer error de XPath del Self-Healer fue recuperado y el input de búsqueda terminó funcionando.

## Ejemplo esperado para el caso del log

Ahora el caso equivalente queda conceptualmente como:

- `industry_target = marketing`
- `industry_detected = food`
- `business_vertical = FOOD`
- `competitor_relation = UNKNOWN`
- `is_competitor = false`
- `is_blacklisted = false`
- `skip_post = false`
- `selected_service = social media management`
- `qualification_score >= 6`
- `qualification_decision = QUALIFIED`
- `engageable = true`

Esto no significa que todos los perfiles encontrados por un hashtag deban ser aceptados: siguen siendo obligatorias la evidencia comercial, la ubicación y las exclusiones por competencia/perfil personal.
