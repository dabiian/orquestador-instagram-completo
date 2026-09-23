# Corrección de `cell_reveal_policy` — Instagram

Fecha: 2026-09-17

## Cambio

Se incorporó el enforcement runtime de las reglas `rules.cell_reveal_policy` y `rules.office_phone_sms_allowed` del `05_response_data_request.json` dentro de `InstagramConversationFlowService`.

### Cleaning
- `reveal_cell_only_if_prospect_explicitly_requests_text_or_sms`
  - Un pedido genérico de información no revela el celular privado.
  - `DM me` / `Message me` tampoco desbloquean el celular.
  - Un pedido explícito de texto/SMS sí permite revelar el celular configurado en el template.
  - Se evita reemplazar números fijos del template por el teléfono de campaña.

### Spa
- `never_reveal_private_owner_cell_publicly_use_campaign_phone_or_dm_only`
  - Se eliminan líneas explícitamente asociadas a un celular privado.
  - El teléfono de campaña continúa disponible.

### Spa Colombia / Abogados
- `business_whatsapp_can_be_shared_publicly`
  - Los contactos empresariales declarados en los templates no se eliminan.

### Marketing
- `no_private_cell_available_reveal_business_phone_and_free_audit_link_when_prospect_requests_info`
  - Se conserva el teléfono empresarial y el CTA del audit.

### Fences
- La política condicional queda aplicada aunque el template actual no contiene celular privado.

### `office_phone_sms_allowed`
- Cuando es `false`, una futura plantilla no puede presentar el teléfono de campaña como destino de SMS mediante `call or text`.
- Una línea de celular separada queda gobernada por `cell_reveal_policy`.

## Tests

Se agregó `tests/test_contact_policy_enforcement.py` con cobertura de:
- Cleaning: ocultación/revelación condicional.
- Cleaning: flujo `handle()`.
- Cleaning: DM vs SMS.
- Spa: nunca revelar celular privado.
- Spa: DM usando teléfono de campaña.
- Spa Colombia y Abogados: WhatsApp empresarial permitido.
- Marketing.
- Fences.
- Detección explícita de SMS/texto.
- `office_phone_sms_allowed`.
- Carga de políticas desde runtime.
- Botanica sin `cell_reveal_policy`, preservando su comportamiento existente.

## Validación ejecutada

- Tests de contacto + enforcement de config: **23 passed**.
- Suite funcional no dependiente de Selenium: **102 passed**.
- `py_compile` del servicio corregido: **OK**.
- La suite completa del repositorio no puede recolectarse en este entorno porque faltan dependencias Selenium; esto no afecta los tests de lógica ejecutados.
