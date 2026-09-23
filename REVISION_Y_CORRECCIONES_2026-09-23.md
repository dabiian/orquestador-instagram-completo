# Revisión y correcciones — integración Instagram / RPA Orchestrator

Fecha: 2026-09-23

## Corrección crítica aplicada

Se encontró una desincronización real entre el modelo Django `SocialMediaAccount` y el historial de migraciones: el modelo y los serializers usan `account_type`, y la integración del catálogo, adapter y claim endpoint lo necesitan para filtrar cuentas Instagram, pero ninguna migración 0001–0017 creaba físicamente la columna.

Se agregó una migración enfocada:

- `dashboard/migrations/0018_socialmediaaccount_account_type.py`

La migración añade únicamente `SocialMediaAccount.account_type` con el mismo contrato que el modelo (`CharField(max_length=255, default="personal_account")`). No mezcla los demás cambios históricos detectados por `makemigrations`, porque esos cambios son drift legado no relacionado con la integración y agruparlos automáticamente sería riesgoso.

Esto corrige el error observado en el catálogo:

`django.db.utils.ProgrammingError: column dashboard_socialmediaaccount.account_type does not exist`

## Prueba añadida

Se agregó:

- `dashboard/tests/test_instagram_catalog.py`

Valida que el catálogo:

- acepte el token configurado;
- exponga cuentas marcadas explícitamente como `instagram`;
- no exponga cuentas legacy/default;
- rechace un token incorrecto.

## Validaciones realizadas en el paquete

- Compilación Python de `dashboard`, migraciones y código del adapter: OK.
- Compilación Python del bot Instagram y sus tests: OK.
- `tests/test_orchestrator_claim_fallback.py` del bot: **2 passed**.
- Sintaxis de `frontend/instagram.js` del RPA Orchestrator validada con Node: OK.
- Compilación Python del código `src/` del RPA Orchestrator y tests Instagram: OK.
- La ejecución local de pytest del Orchestrator en este entorno no pudo completarse porque el sandbox no tiene todas las dependencias instaladas (`structlog`) y no tiene acceso de red para instalarlas. Esto no es un fallo encontrado en el proyecto; el contenedor Docker del usuario ya había iniciado correctamente con sus dependencias.

## Estado de la integración observado antes de empaquetar

Las pruebas realizadas en el entorno Docker del usuario ya confirmaron:

- Orchestrator API arriba en `:8005`.
- PostgreSQL, MongoDB y Redis del Orchestrator saludables.
- Django backend arriba en `:8000`.
- WebSocket Django → Orchestrator aceptado.
- Bot adapter registrado como `instagram-backend-01` con capacidades `instagram.maduracion` e `instagram.prospecting`.
- Basic Auth del dashboard funcionando.
- Proxy `GET /api/v1/instagram/catalog` alcanzando Django.
- El único bloqueo del catálogo era la columna `account_type`, corregida por la migración 0018.

## Importante sobre el drift histórico

`makemigrations --dry-run` detectó otros cambios antiguos sin migración (modelos/campos de grupos, campañas y websocket). No se generó una migración automática con todos ellos. Hacerlo habría mezclado cambios no relacionados y podría alterar tablas legacy ya existentes. La corrección entregada es deliberadamente mínima y reproducible.

## Seguridad

Antes de desplegar fuera del entorno local deben rotarse credenciales/tokens que hayan sido compartidos durante las pruebas y usarse secretos distintos para adapter, catálogo y claim endpoint.
