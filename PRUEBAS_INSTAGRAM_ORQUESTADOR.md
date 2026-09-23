# Pruebas manuales — Instagram en el Orquestador

## Objetivo

Validar la pestaña Instagram del dashboard del RPA Orchestrator de extremo a extremo, sin depender del frontend antiguo de Instagram.

Flujo esperado:

Navegador -> REST Orquestador -> WebSocket privado -> Adaptador Django -> TaskBot -> Bot Instagram -> resultado -> Orquestador -> Dashboard

## Preparación

1. Levantar Orquestador, PostgreSQL, Mongo y Redis.
2. Levantar backend-redes-sociales con el adaptador Instagram habilitado.
3. Confirmar que el bot adapter aparece conectado en el Orquestador.
4. Aplicar migraciones Django, incluida `0021_tasktype_operation`.
5. Clasificar los TaskType reales de Instagram:
   - `maduracion`: publicar post, publicar historia, notificaciones y demás tareas de maduración.
   - `prospecting`: tareas de prospección.
6. Abrir `http://localhost:8005/dashboard/` con usuario operador.

## 1. Catálogo y filtrado por operación

### Prospección
- Abrir pestaña Instagram.
- Elegir Operación = Prospección.
- Verificar que solo se muestran TaskType con `operation=prospecting`.
- Verificar que los task types de maduración no aparecen.

### Maduración
- Elegir Operación = Maduración.
- Verificar que solo se muestran TaskType con `operation=maduracion`.
- Verificar que los task types de prospección no aparecen.

Los registros históricos con `operation=NULL` se muestran temporalmente en ambas operaciones por compatibilidad. Deben clasificarse antes de producción.

## 2. Validaciones del formulario

- Sin ningún task type: Crear ejecución debe bloquear y mostrar mensaje.
- Destino=accounts sin cuentas: debe bloquear.
- Destino=owner sin propietario: debe bloquear.
- Tarea personalizada con JSON inválido: debe bloquear.
- Destino=all: debe pedir confirmación.
- Verificar que Bot executor está dentro de Opciones avanzadas.

## 3. Crear Prospección

- Operación: Prospección.
- Seleccionar un task type de prospección.
- Destino: cuenta concreta.
- Crear ejecución.

Esperado:
- Respuesta 202.
- UUID visible en Seguimiento.
- URL incorpora `execution_id=<uuid>`.
- Estado pasa por pending/queued/running según capacidad.
- Historial incluye la ejecución.
- Eventos aparecen si el adapter los emite.
- Al terminar, Resultado carga automáticamente.

## 4. Crear Maduración

Repetir el caso anterior con un task type de maduración.

Esperado:
- capability `instagram.maduracion`
- schema `instagram.maduracion.input.v1`
- stage `instagram_maduracion`

## 5. Destino por propietario

- Seleccionar Destino=Propietario.
- Elegir un propietario.
- Crear.

Esperado:
- Se crean TaskBot únicamente para cuentas Instagram de ese propietario.

## 6. Destino todas las cuentas

- Seleccionar Destino=Todas las cuentas Instagram.
- Crear.
- Confirmar diálogo.

Esperado:
- Solo se consideran cuentas con `account_type=instagram`.

## 7. Programación

- Elegir una fecha futura en Inicio programado.
- Crear ejecución.

Esperado:
- TaskBot se crea con `start_date` futuro.
- El bot no lo reclama antes de esa hora.
- El frontend convierte la hora local a UTC.

## 8. Cancelación

- Crear una ejecución que permanezca queued o running.
- Pulsar Cancelar.
- Rechazar confirmación: no debe cancelarse.
- Pulsar de nuevo y confirmar.

Esperado:
- POST cancel devuelve 202.
- UI mantiene polling.
- No cambia a cancelled hasta confirmación del API.
- TaskBot pendientes pasan a CA.
- Resultado final incluye cancelled.

## 9. Resultado exitoso

Abrir una ejecución succeeded.

Esperado:
- Totales created/ok/error/cancelled.
- Tabla de tasks.
- comment se muestra como texto, no HTML.
- No se expone documento Mongo interno.

## 10. Resultado parcial con fallo

Abrir una ejecución failed que haya creado TaskBot.

Esperado:
- Se muestra error terminal.
- También se intenta GET /result.
- Si hay payload parcial, se muestran totales y tareas completadas/fallidas.

## 11. Historial

- Recargar historial.
- Verificar que mezcla prospecting y maduracion ordenadas por fecha.
- Probar API:
  `GET /api/v1/executions?bot_type=instagram&limit=2`
- Si devuelve `next_cursor`, repetir:
  `GET /api/v1/executions?bot_type=instagram&limit=2&cursor=<next_cursor>`

Esperado:
- No repetir elementos entre páginas.

## 12. Seguridad

Desde DevTools > Network:
- Ninguna petición del navegador debe ir a `/api/v1/bots/ws`.
- Ninguna petición debe contener BOT_TOKENS.
- El frontend no debe llamar a `/executions/{id}/input`.
- Las peticiones usan misma sesión/origen del dashboard.
- Un usuario sin autenticación no debe consultar catálogo, historial, resultado ni crear ejecuciones.

## 13. Pruebas automatizadas

### Orquestador

Desde `rpa_orchestrator-master/rpa_orchestrator-master`:

```powershell
pytest tests/unit/test_standalone_instagram.py tests/unit/test_get_execution_result.py tests/unit/test_instagram_local_smoke.py tests/unit/test_dashboard.py
```

### Backend Django

Desde `backend-redes-sociales-main/backend-redes-sociales-main`:

```powershell
python manage.py test dashboard.tests.test_orchestrator_instagram
```

## Criterio de cierre

La integración se considera lista cuando:
- Prospección y Maduración crean ejecuciones válidas.
- Los task types se filtran por operación.
- pending no se trata como error.
- polling llega a estado terminal.
- cancelación funciona.
- resultado exitoso/parcial se visualiza.
- historial y cursor funcionan.
- el navegador no accede a WebSocket privado, input interno ni tokens.
