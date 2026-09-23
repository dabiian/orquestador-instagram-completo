# Entrega final — Instagram Bot

Esta versión integra y corrige el flujo de **Instagram Prospect Classification + Self-Healer** y añade la restricción geográfica de campañas.

## Cambios principales

### 1. `strategy_snapshot.locations`
- Si `locations` contiene una o más zonas, la ubicación pasa a ser un requisito obligatorio.
- El clasificador devuelve `location_match`, `location_confidence` y `location_evidence`.
- `location_match=true`: el candidato puede continuar.
- `location_match=false`: el candidato está fuera de la zona y se descarta.
- `location_match=null`: no se pudo verificar la ubicación; en una campaña restringida también se descarta.
- Si `locations=[]` o no existe, no hay restricción geográfica y el resultado se normaliza a `location_match=true`.
- Un hashtag de ciudad por sí solo no prueba que el negocio esté ubicado allí.

### 2. Corrección de `skip_post`
Antes, el servicio podía devolver `skip_post=true` y el task reconstruía la decisión usando solamente competencia/blacklist, convirtiendo accidentalmente el candidato en `valid=True`.

Ahora:
- `skip_post=true` es una decisión que se conserva.
- `mode=skip` fuerza descarte.
- Competidores, perfiles personales y negocios no relacionados fuerzan descarte.
- El task nunca convierte un candidato descartado en `qualified`.
- Un candidato descartado recibe score de engagement 0 y no entra en follow/comment.

### 3. Perfiles personales
El prompt pide distinguir una cuenta personal de empleado de una cuenta empresarial. Si la evidencia permite clasificarla como `COMMON_PERSON`, se descarta como prospecto empresarial.

## Archivos principales modificados

- `app/services/instagram_prospect_classification_service.py`
- `app/tasks/instagram_prospect_discovery_task.py`
- `test_classifier_contract.py`
- `.env.example`
- `INTEGRACION_CLASIFICADOR_SELF_HEALER.md`

## Configuración

El ZIP deliberadamente **no incluye `.env`** para no distribuir credenciales. Si ya tienes un `.env` funcional, consérvalo al reemplazar los archivos del proyecto.

Si necesitas crear uno nuevo:

```powershell
Copy-Item .env.example .env
```

Completa como mínimo la URL del backend y las claves que realmente utilices.

## Pruebas realizadas

- Reglas de competencia de las 7 industrias: PASS.
- Detección determinística de competencia: 10/10 PASS.
- Integración completa del classifier: 14/14 PASS.
- Contrato del classifier, incluyendo ubicación y preservación de `skip_post`: PASS.
- `test_instagram_classifier.py`: PASS.
- Compilación de todo el código Python de `app` y `self_healer`: PASS.

La ejecución real contra Instagram/backend depende de las credenciales, sesión, navegador y servicios externos de tu entorno.


=========================================================
CORRECCIONES FINALES - 2026-09-16
=========================================================

1. Se separa `industry_target` (objetivo de campaña) de `industry_detected` (industria real del prospecto).
2. Si el backend omite la industria explícita, el bot infiere el target de forma conservadora desde servicios/nombre de campaña.
3. `locations=[]` significa sin restricción geográfica; no se infiere una ciudad a partir de hashtags.
4. La validación geográfica ya no acepta un hashtag, username, cuenta etiquetada o mención aislada como prueba suficiente.
5. Se distinguen `true`, `false` y `null` para location_match: coincide, fuera de zona, o desconocido.
6. Se añadieron niveles de evidencia geográfica high/medium/low.
7. Se amplió la clasificación de perfiles: BUSINESS, PROFESSIONAL, EMPLOYEE, PERSONAL, CREATOR, ORGANIZATION.
8. Se añadió screening conservador temprano para cuentas personales vinculadas a un empleador.
9. `source_type/source_value` se mantienen como origen de discovery y no como prueba geográfica.
10. Se añade deduplicación de perfiles y publicaciones durante una ejecución y normalización de URLs/reels.
11. La puntuación queda separada de la validez semántica: `QUALIFIED`, `REVIEW`, `DISCARDED` y `engageable`.
12. La selección de servicio se valida contra `services_snapshot`.
13. Se añade persistencia best-effort de metadata extendida cuando el backend la soporta, con fallback al contrato legacy.
14. Se fuerza UTF-8 en stdout/stderr y los logs de aplicación usan archivos UTF-8 rotativos.
15. Se redujo el ruido de `is_visible`, sleeps y locators del Self-Healer a DEBUG cuando no son fallos reales.
16. El hover de followback es opcional y ya no trata un elemento incompatible con ActionChains como error bloqueante.

Nota de compatibilidad: si el backend aún no tiene columnas/campos para metadata extendida, el bot conserva el guardado legacy y deja trazabilidad en `qualification_reason`/logs. Para que el panel muestre cada nuevo campo como columna independiente, el serializer/modelo del backend debe aceptar esos campos.

## Contrato de puntuación del clasificador

- `commercial_intent_score`: puntuación principal del clasificador, de **0 a 100**.
- **60** es el umbral para considerar un candidato `QUALIFIED` y `engageable=true`.
- `REVIEW`: candidato no descartado con puntuación menor de 60.
- `DISCARDED`: candidato descartado por las reglas de clasificación.
- `qualification_score`: campo entero legado que la API de prospectación normaliza a **0-10** a partir de `commercial_intent_score`; no debe confundirse con la escala 0-100 del clasificador.
