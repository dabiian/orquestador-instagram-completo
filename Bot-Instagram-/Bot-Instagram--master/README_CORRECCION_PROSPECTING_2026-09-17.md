# Corrección de prospecting Instagram — 2026-09-17

## Cambios

1. **Campañas de marketing tratadas como campañas de servicio**
   - Cuando la campaña no declara `industry_target`/`industry` y sus servicios son de marketing, `marketing` se interpreta como el servicio vendido, no como la industria que deben tener los prospectos.
   - Un restaurante, salón, contratista, inmobiliaria, tienda u otro negocio local puede ser un prospecto válido.
   - Una agencia de marketing/social media/SEO/advertising que ofrece los mismos servicios sigue siendo competidor y se descarta.

2. **Competencia detectada también en la publicación**
   - La detección determinística de competidores ya no mira solamente username/display name/bio.
   - También revisa el texto del post y posts recientes. Esto corrige casos como una agencia cuya bio no contiene la señal pero cuyo post dice que es una agencia de marketing.

3. **URLs de navegador inválidas**
   - `chrome-error://`, `about:`, `javascript:` y `data:` ya no se convierten en URLs de Instagram.
   - También se rechazan hosts que no sean Instagram.
   - La extracción de contexto de posts rechaza URLs inválidas antes de guardar datos.

4. **Servicios de campaña respetados**
   - El prompt indica que `selected_service` debe pertenecer exactamente a `services_snapshot`.
   - Los servicios enumerados por reglas históricas de marketing no pueden sustituir los servicios realmente configurados en la campaña.

## Pruebas nuevas

Se agregó `tests/test_marketing_service_prospecting.py` con pruebas para:

- campaña de marketing como service-prospecting;
- restaurante como prospecto aunque `industry_detected != marketing`;
- agencia de marketing detectada desde el texto de una publicación;
- rechazo de URLs `chrome-error://`, JavaScript y hosts externos.

## Resultado de pruebas ejecutadas

- `19 passed` en las pruebas nuevas + contrato final + estabilidad.
- `22 passed` en el conjunto adicional de reglas/contratos.
- Los scripts de regresión de contrato y reglas de competencia ejecutados manualmente terminaron en PASS.
- `compileall` completó correctamente.

## Nota

Las pruebas que requieren Selenium/Chrome no pueden ejecutarse en este entorno de análisis porque el entorno disponible no tiene el paquete `selenium`. Por eso no se afirma que la navegación real de Instagram esté garantizada sin probarla en el Windows del usuario con su `.venv` y Chrome.


## Addendum — validación del bot_log 2026-09-17

Se corrigió el caso real en el que `UNRELATED_BUSINESS` + `commercial_intent_score=18` descartaba un negocio local porque la campaña vende marketing. En service-prospecting, esa relación no implica competencia. Se agregó recuperación determinística conservadora y normalización de `business_vertical`/`industry_detected` desde evidencia concreta. La prueba de regresión reproduce el caso `tastebuddiaries` y pasa.
