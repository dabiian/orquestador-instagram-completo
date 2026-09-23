# Corrección de búsqueda de hashtags — 2026-09-17

## Problema observado

El discovery abría correctamente el panel de búsqueda, pero el locator XPath del input era resuelto de forma inestable por el DOM dinámico de Instagram. El Self-Healer tampoco encontraba un candidato válido, por lo que `_type_search_term()` devolvía `False` antes de escribir el hashtag.

## Cambio realizado

`app/tasks/instagram_followback/instagram_followback_navigation.py` ahora:

- usa primero locators CSS directos y simples para el input;
- acepta variantes de `aria-label`, `placeholder` y `name`;
- filtra elementos visibles y habilitados;
- reintenta hasta 5 veces porque Instagram puede reconstruir el overlay;
- evita depender del Self-Healer para este locator conocido;
- hace click/focus antes de escribir;
- verifica el valor escrito y también permite confirmar por resultados visibles;
- conserva la lógica existente de recolección y apertura de resultados.

También se ampliaron los locators en `app/config/locators/instagram_followback_locators.py`.

## Validación local

- `python -m compileall -q app main.py` → OK
- Suite de regresión independiente de Selenium: `27 passed`
- La prueba real de navegador/Instagram debe ejecutarse en el Windows del bot porque este entorno no tiene Selenium ni una sesión de Instagram real.
