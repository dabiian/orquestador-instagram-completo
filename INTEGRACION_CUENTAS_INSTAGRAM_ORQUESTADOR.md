# Administración de cuentas Instagram desde el Orquestador

Implementación basada en `guia_creacion_cuenta_instagram_2026-09-24.md`.

## Arquitectura

El navegador solo habla con el Orquestador:

```
Dashboard /dashboard/
  -> /api/v1/instagram/admin/*
  -> Orquestador (BFF, autenticación del dashboard)
  -> Django /api/*
  -> PostgreSQL
```

La creación/edición de cuentas **no usa WebSocket**. El WebSocket del bot se mantiene exclusivamente para el ciclo de ejecución del Orquestador.

## Flujo de provisioning

El formulario **Administración de cuentas Instagram** ejecuta en orden:

1. `POST /api/bot_personalities/`
2. `POST /api/account_owners/`
3. `POST /api/proxy/` (opcional)
4. `POST /api/social_media_accounts/`
5. `POST /api/prospecting/campaigns/`
6. `POST /api/prospecting/campaign-accounts/`
7. Verificación: `GET /api/prospecting/campaigns/active/?social_media_account_id=<id>&platform=instagram`

La cuenta solo aparece en el catálogo operativo de Instagram cuando tiene una asignación activa de plataforma `instagram`. La plataforma no se deriva de `SocialMediaAccount.account_type`.

## Contrato de cuenta

El backend acepta el contrato nuevo:

- `account_name`
- `group` JSON no nulo
- `owner`
- `other_credentials` con `user`, `password`, `cookie`
- `bot_personality` opcional
- `proxy` opcional
- `account_kind`: `business` o `personal`

Se mantienen aliases legacy `owner_id`, `bot_personality_id`, `proxy_id` para no romper clientes existentes. `User` también se conserva dentro de `other_credentials` para compatibilidad con el bot existente.

## Campañas y asignaciones

La campaña tiene estado inicial `draft`; el bot solo resuelve campañas `active`.

`InstagramProspectingCampaignAccount` es la relación cuenta-campaña. Tiene:

- `platform`
- `role=prospecting`
- `is_active`
- `daily_limit`
- `total_limit`
- restricción única `campaign + social_media_account`

El endpoint `campaigns/active/` consulta esta relación y exige:

- assignment activo
- role `prospecting`
- platform solicitada
- campaña activa
- platform de campaña coincidente

## BFF del Orquestador

Recursos permitidos:

- `/api/v1/instagram/admin/personalities`
- `/api/v1/instagram/admin/owners`
- `/api/v1/instagram/admin/proxies`
- `/api/v1/instagram/admin/accounts`
- `/api/v1/instagram/admin/campaigns`
- `/api/v1/instagram/admin/assignments`

Cada recurso soporta GET/POST y detalle GET/PATCH/DELETE. El allowlist impide usar el BFF como proxy arbitrario.

Extras:

- `PATCH /api/v1/instagram/admin/accounts/{id}/cookie`
- `GET /api/v1/instagram/admin/accounts/{id}/verify`

## Migración

Aplicar:

```powershell
docker exec instagram-backend-local python manage.py migrate
```

La migración nueva es `0024_instagram_account_provisioning.py`.

## Pruebas recomendadas

Backend Django:

```powershell
docker exec instagram-backend-local python manage.py test dashboard.tests.test_instagram_account_provisioning dashboard.tests.test_orchestrator_instagram
```

Orquestador:

```powershell
docker exec rpa-orchestrator-api pytest -q tests/unit/test_instagram_admin.py tests/unit/test_dashboard.py tests/unit/test_standalone_instagram.py
```

Después:

1. Abrir `http://localhost:8005/dashboard/`.
2. Entrar a Instagram.
3. Crear una cuenta con el wizard.
4. Confirmar mensaje de verificación OK.
5. Confirmar que aparece en **Cuentas Instagram** de Nueva ejecución.
6. Ejecutar una tarea de prospección con esa cuenta.
7. Confirmar TaskBot y resultado terminal.

## Compatibilidad

El frontend Vue antiguo queda como referencia/legado. La administración operativa normal de Instagram queda en el Orquestador.
