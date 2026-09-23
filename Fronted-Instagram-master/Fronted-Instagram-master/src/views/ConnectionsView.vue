<template>
  <div class="connections-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">WebSocket</p>
        <h1 class="page-title">Máquinas Conectadas</h1>
        <p class="page-subtitle">
          Bots activos conectados en tiempo real al backend de Instagram.
        </p>
      </div>

      <div class="header-actions">
        <Button
          label="Actualizar"
          icon="pi pi-refresh"
          :loading="loading"
          @click="loadConnections"
        />
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-label">Conexiones</span>
        <strong>{{ connections.length }}</strong>
      </div>

      <div class="stat-card">
        <span class="stat-label">Online</span>
        <strong>{{ onlineCount }}</strong>
      </div>

      <div class="stat-card">
        <span class="stat-label">Offline / stale</span>
        <strong>{{ offlineCount }}</strong>
      </div>

      <div class="stat-card">
        <span class="stat-label">Backend</span>
        <strong :class="backendOk ? 'text-ok' : 'text-error'">
          {{ backendOk ? "OK" : "ERROR" }}
        </strong>
      </div>
    </div>

    <Card class="section-card">
      <template #title>
        <div class="card-title-row">
          <span>Bots conectados</span>
          <small>Auto-refresh cada 5 segundos</small>
        </div>
      </template>

      <template #content>
        <DataTable
          :value="connections"
          :loading="loading"
          dataKey="id"
          paginator
          :rows="10"
          responsiveLayout="scroll"
          stripedRows
          showGridlines
          emptyMessage="No hay bots conectados en este momento."
        >
          <Column field="room" header="Room / Bot">
            <template #body="{ data }">
              <div class="bot-cell">
                <strong>{{ data.room || "Sin room" }}</strong>
                <small>{{ data.channel_name }}</small>
              </div>
            </template>
          </Column>

          <Column field="ip" header="IP">
            <template #body="{ data }">
              <Tag
                :value="data.ip || 'Sin IP'"
                severity="info"
              />
            </template>
          </Column>

          <Column field="machine_name" header="Máquina">
            <template #body="{ data }">
              {{ data.machine_name || "No reportada" }}
            </template>
          </Column>

          <Column field="bot_name" header="Bot">
            <template #body="{ data }">
              {{ data.bot_name || "Instagram Bot" }}
            </template>
          </Column>

          <Column field="bot_type" header="Tipo">
            <template #body="{ data }">
              <Tag
                :value="data.bot_type || 'instagram'"
                severity="secondary"
              />
            </template>
          </Column>

          <Column field="is_online" header="Estado">
            <template #body="{ data }">
              <Tag
                :value="data.is_online ? 'Online' : 'Stale'"
                :severity="data.is_online ? 'success' : 'warning'"
              />
            </template>
          </Column>

          <Column field="seconds_since_seen" header="Último ping">
            <template #body="{ data }">
              {{ formatSeconds(data.seconds_since_seen) }}
            </template>
          </Column>

          <Column field="connected_at" header="Conectado">
            <template #body="{ data }">
              {{ formatDate(data.connected_at) }}
            </template>
          </Column>

          <Column header="Metadata">
            <template #body="{ data }">
              <Button
                icon="pi pi-eye"
                text
                rounded
                severity="secondary"
                @click="openMetadata(data)"
              />
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="metadataDialog"
      modal
      header="Metadata de conexión"
      :style="{ width: '650px', maxWidth: '95vw' }"
    >
      <pre class="metadata-box">{{ selectedMetadata }}</pre>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import Button from "primevue/button";
import Card from "primevue/card";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import Dialog from "primevue/dialog";
import Tag from "primevue/tag";

import { connectionsApi } from "../api/connections.api";
import { normalizeList } from "../api/http";

const loading = ref(false);
const backendOk = ref(false);
const connections = ref([]);

const metadataDialog = ref(false);
const selectedMetadata = ref("{}");

let intervalId = null;

const onlineCount = computed(() => {
  return connections.value.filter((item) => item.is_online).length;
});

const offlineCount = computed(() => {
  return connections.value.length - onlineCount.value;
});

async function loadHealth() {
  try {
    await connectionsApi.health();
    backendOk.value = true;
  } catch (error) {
    backendOk.value = false;
  }
}

async function loadConnections() {
  loading.value = true;

  try {
    const response = await connectionsApi.list();
    connections.value = normalizeList(response.data);
  } catch (error) {
    console.error("Error cargando conexiones:", error.response?.data || error);
    connections.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadAll() {
  await Promise.all([
    loadHealth(),
    loadConnections(),
  ]);
}

function formatDate(value) {
  if (!value) return "N/A";

  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatSeconds(value) {
  if (value === null || value === undefined) return "N/A";

  if (value < 5) return "Ahora";
  if (value < 60) return `${value}s`;
  if (value < 3600) return `${Math.floor(value / 60)} min`;

  return `${Math.floor(value / 3600)} h`;
}

function openMetadata(row) {
  selectedMetadata.value = JSON.stringify(row.metadata || {}, null, 2);
  metadataDialog.value = true;
}

onMounted(async () => {
  await loadAll();

  intervalId = setInterval(() => {
    loadConnections();
  }, 5000);
});

onBeforeUnmount(() => {
  if (intervalId) {
    clearInterval(intervalId);
  }
});
</script>

<style scoped>
.connections-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.page-kicker {
  margin: 0 0 0.35rem;
  color: #ec4899;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.page-title {
  margin: 0;
  font-size: 2rem;
  font-weight: 800;
  color: #111827;
}

.page-subtitle {
  margin: 0.35rem 0 0;
  color: #6b7280;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 1.15rem;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.stat-label {
  display: block;
  color: #6b7280;
  font-size: 0.85rem;
  margin-bottom: 0.45rem;
}

.stat-card strong {
  font-size: 1.65rem;
  color: #111827;
}

.text-ok {
  color: #16a34a !important;
}

.text-error {
  color: #dc2626 !important;
}

.section-card {
  border-radius: 20px;
  overflow: hidden;
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.card-title-row small {
  color: #6b7280;
  font-weight: 400;
}

.bot-cell {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.bot-cell small {
  color: #6b7280;
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metadata-box {
  background: #0f172a;
  color: #e5e7eb;
  padding: 1rem;
  border-radius: 14px;
  overflow: auto;
  max-height: 420px;
  font-size: 0.85rem;
}

@media (max-width: 1100px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .page-header {
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>