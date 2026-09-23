# Vue 3 + Vite

## Panel de ejecuciones Instagram

Este CRM sigue gestionando campañas, cuentas y tareas directamente en Django.
El enlace **Ejecuciones orquestadas** abre el dashboard del orquestador,
responsable de crear, seguir y cancelar las ejecuciones autónomas. Configure
`VITE_ORCHESTRATOR_DASHBOARD_URL` con la dirección pública que pueda abrir el
navegador (por defecto `http://10.0.0.92:8005/dashboard/`). En Docker pase el
valor como `--build-arg VITE_ORCHESTRATOR_DASHBOARD_URL=...` y reconstruya la
imagen; Vite inserta esta URL en la compilación. El enlace no incluye tokens;
el orquestador solicita la autenticación de su operador.

No cree la misma ejecución desde **Crear tareas** y desde el orquestador: son
flujos distintos y generarían trabajos duplicados.

This template should help get you started developing with Vue 3 in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about IDE Support for Vue in the [Vue Docs Scaling up Guide](https://vuejs.org/guide/scaling-up/tooling.html#ide-support).
