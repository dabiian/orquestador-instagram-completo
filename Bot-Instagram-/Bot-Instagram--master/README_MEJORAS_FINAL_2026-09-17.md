# Bot Instagram — mejoras de equivalencia funcional

Esta versión mantiene la arquitectura propia de Instagram y traslada la lógica de negocio suministrada para Facebook.

## Cambios principales

- Se incorporaron las reglas largas de clasificación por industria suministradas en `prompts_clasificacion_prospectos_por_industria.docx`.
- Se incorporaron los prompts largos de comentarios de las industrias que los suministra el documento de campañas.
- Se conservaron las reglas de competencia existentes de Instagram y se mantuvo la validación para que `selected_service` nunca invente un servicio fuera de `services_snapshot`.
- Se incorporaron exactamente los 14 archivos `05/06` de respuesta de las 7 industrias activas del RAR de configuración como fuente de reglas.
- Se creó `InstagramConversationFlowService`, que interpreta esos JSON desde la arquitectura de Instagram.
- Las solicitudes de cotización usan el `bot_question_flow` de la industria, respetan las preguntas condicionales y terminan según el mínimo de respuestas definido por la regla.
- Las solicitudes de información usan las plantillas D1/D2/D3 suministradas y sustituyen placeholders por datos de campaña cuando están disponibles.
- El estado de una cotización se conserva en `data/instagram_conversation_flows.json` para permitir conversaciones de varios mensajes.
- El flujo se integra tanto con el inbox DM como con el monitor de replies públicos.
- Se conserva el pipeline existente de alertas, likes, interacciones y persistencia.

## Validación ejecutada

- `python -m compileall -q app self_healer main.py` → OK.
- Suite de regresión disponible sin dependencias externas de Selenium → **27 passed**.
- Se validaron las 14 configuraciones 05/06 contra sus fuentes del RAR mediante SHA-256 → **14/14 idénticas**.
- Se validaron las 7 industrias para reglas de clasificación.
- Se validaron los flujos de data request y quote request, incluyendo mínimo de respuestas y preguntas condicionales.

## Nota sobre pruebas de navegador

La suite completa del proyecto no puede ejecutarse en este entorno de construcción porque el entorno Linux utilizado para la validación no tiene Selenium instalado y no dispone de acceso de red para instalarlo. El código fue compilado completamente y las pruebas de lógica que no requieren navegador pasaron.

La validación real de Selenium/Instagram debe ejecutarse en el entorno Windows del bot, con sus dependencias y navegador configurados.
