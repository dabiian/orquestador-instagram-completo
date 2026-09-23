# Config 100% — deterministic enforcement

Se reforzó la capa runtime para que las reglas declarativas de `04_intro_comment_policy.json` no dependan únicamente del prompt de IA.

## Cambios
- Validación determinista de idioma cuando `account_language` está disponible.
- Validación de primera oración con contexto del post.
- Validación del puente de segunda oración cuando introduce servicio/CTA.
- Detección de fuga/copia de fragmentos de templates sin soporte en el post.
- Enforcement determinista de `privacy_rule`.
- Enforcement determinista de `no_guarantees_rule`.
- El generador de comentarios pasa contexto del post y lenguaje de la cuenta al validador.
- Se preservó el árbol `app/config/business_config` y los JSON fuente sin modificaciones.

## Validación ejecutada
- `PYTHONPATH=. pytest -q --ignore=self_healer --ignore=test_self_healer_instagram.py --ignore=tests/test_instagram_rate_limit_navigation.py`
- Resultado: **110 passed, 0 failed**
- `python -m compileall -q app tests`: OK
- Manifest SHA-256: **41/41 JSON coinciden**

Las pruebas Selenium/Instagram real no forman parte de esta validación, conforme al alcance solicitado.
