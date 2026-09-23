# Corrección de navegación de hashtags — 2026-09-18

## Problema corregido

La búsqueda de `#ChicagoGeneralContractor` podía recolectar cualquier enlace visible que contuviera `/explore/tags/` y después abrir `result_hrefs[0]`. Si el DOM contenía recomendaciones como `#Sacramento`, el bot podía navegar a Sacramento aunque el término solicitado fuera Chicago.

## Nueva barrera determinista

La navegación ahora:

1. Normaliza el término solicitado a un slug.
2. Extrae el slug real de cada `href` `/explore/tags/<slug>/`.
3. Acepta únicamente coincidencia exacta del slug solicitado.
4. Canonicaliza el `href` aceptado.
5. Si no existe coincidencia exacta, devuelve una lista vacía y no abre ningún hashtag ajeno.
6. Prospecting aplica además una segunda validación inmediatamente antes de abrir el destino.

Por tanto, un conjunto de resultados como `sacramento`, `yubacity`, `homeremodeling`, `kitchenremodel` y `bathroomremodel` no puede producir una navegación accidental desde `#ChicagoGeneralContractor`.

## Tests añadidos

`tests/test_hashtag_navigation_guard.py` cubre:

- `#ChicagoGeneralContractor` + `#Sacramento` => rechazado.
- resultado exacto aunque aparezca después de un enlace ajeno => aceptado.
- coincidencias parciales (`...company`, `...experts`) => rechazadas.
- mayúsculas, query string y slash final => normalizados.
- enlaces de posts => rechazados.
- entradas vacías/malformadas => fail-closed.

## Verificación local

- Tests específicos: **6 passed**.
- Suite seleccionada relacionada con configuración/prospecting + guard: **51 passed**.
- `compileall` de `app` y `tests`: correcto.
- La suite completa del ZIP no puede recopilarse en este entorno porque faltan dependencias de ejecución (`selenium`); los errores corresponden a esa dependencia, no a los tests del guard.
