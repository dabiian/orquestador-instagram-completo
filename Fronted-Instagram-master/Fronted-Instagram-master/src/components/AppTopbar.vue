<template>
  <header class="topbar">
    <div>
      <div class="eyebrow">Panel operativo</div>
      <h1>Gestión de prospección automatizada</h1>
    </div>

    <div class="topbar-actions">
      <Button
        icon="pi pi-refresh"
        label="Recargar"
        severity="secondary"
        outlined
        @click="reloadPage"
      />

      <Button
        icon="pi pi-plus"
        label="Nueva tarea"
        @click="$router.push('/tasks')"
      />
    </div>
  </header>
</template>

<script setup>
import Button from "primevue/button";

function reloadPage() {
  window.location.reload();
}
</script>

<style scoped>
.topbar {
  min-height: 88px;
  padding: 18px 22px;
  margin-bottom: 22px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 18px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
}

.eyebrow {
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #2563eb;
  margin-bottom: 4px;
}

h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.04em;
  color: #0f172a;
}

.topbar-actions {
  display: flex;
  gap: 10px;
}

@media (max-width: 900px) {
  .topbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .topbar-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>