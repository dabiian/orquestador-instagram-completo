# Corrección final de equivalencia de configuración

## Cambio realizado

Se corrigió `app/services/instagram_config_policy_engine.py` para ejecutar la regla de fuente:

`runtime_rules.layer_L3_block_if_mystic_identity_keyword_hits_gte`

La regla se evalúa de forma independiente del umbral genérico L3. Para la configuración de Botanica, una sola señal de identidad mística definida en `clean_exports.account_name_keywords` dentro de la bio/description produce `BLOCK` y al menos 60 puntos.

No se modificaron los JSON migrados: los 41 JSON del árbol `app/config/business_config` siguen siendo idénticos a los 41 JSON de la fuente entregada.

## Pruebas

- Suites de equivalencia/configuración/regresión: **78 passed**.
- Suite no dependiente de Selenium: **87 passed**.
- `python -m compileall -q app tests`: OK.
- Comparación SHA-256 de JSON fuente vs runtime: **41/41 idénticos**.
- Prueba específica nueva: `bio="Maestro espiritual"` => `BLOCK`, score >= 60.
- Prueba de no regresión: `bio="contenido espiritual"` => `REVIEW`, score 40.

La suite global del proyecto no pudo completarse en este entorno porque Selenium no está instalado y el entorno no tiene acceso de red para instalar `selenium==4.15.2`. Esto afecta únicamente la colección de pruebas que importan Selenium; no invalida las 87 pruebas de lógica que sí pudieron ejecutarse.
