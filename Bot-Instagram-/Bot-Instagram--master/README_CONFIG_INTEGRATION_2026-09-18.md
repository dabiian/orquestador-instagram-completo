# Integración completa del config — 2026-09-18

Se integró el paquete `config 1.zip` como fuente runtime en `app/config/business_config/`.

## Cobertura
- 41 JSON originales del config conservados byte a byte.
- `02_competitor_filter`, `03_discovery_hashtags`, `04_intro_comment_policy`, `05_response_data_request`, `06_response_quote_request` cargados por runtime.
- `00_app_config`, `01_workflow`, `07_alerts` y `08_database_schema` accesibles desde `InstagramConfigRuntimeService`.
- Registries específicos de Abogados y Spa Colombia cargados y usados para gates de seguridad pública.
- Alertas DATA/SERVICE/QUOTE ejecutadas por `InstagramConfigAlertService`, con canales independientes email + WhatsApp webhook/adapter.
- HUMAN_TAKEOVER persistente: cuando la configuración indica que el takeover detiene al bot, futuras respuestas automáticas quedan bloqueadas.
- Límites diarios y límite de un comentario por cuenta implementados por `InstagramSafetyGate`.
- Reglas de seguridad pública de la configuración se validan antes de publicar comentarios.
- `InstagramConfigSchemaValidator` expone el esquema 08 como contrato runtime.

## Pruebas
- Suite de lógica relevante: **55 passed**.
- `python -m compileall -q app tests self_healer`: **OK**.
- La suite total del repositorio no puede colectarse en este entorno porque Selenium no está instalado; el error es de dependencia de entorno (`ModuleNotFoundError: selenium`), no de estas correcciones.
