<template>
  <div class="dashboard-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">Panel principal</p>
        <h1 class="page-title">Dashboard Instagram Bot</h1>
        <p class="page-subtitle">
          Resumen operativo de máquinas, cuentas y tareas del bot.
        </p>
      </div>

      <Button
        label="Actualizar"
        icon="pi pi-refresh"
        :loading="loading"
        @click="loadDashboard"
      />
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">
          <i class="pi pi-server"></i>
        </div>
        <div>
          <span>Máquinas online</span>
          <strong>{{ machinesOnline }}</strong>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">
          <i class="pi pi-users"></i>
        </div>
        <div>
          <span>Cuentas sociales</span>
          <strong>{{ accounts.length }}</strong>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon warning">
          <i class="pi pi-clock"></i>
        </div>
        <div>
          <span>Tareas pendientes</span>
          <strong>{{ countByStatus("SP") }}</strong>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon info">
          <i class="pi pi-spin pi-spinner"></i>
        </div>
        <div>
          <span>En proceso</span>
          <strong>{{ countByStatus("EP") }}</strong>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon success">
          <i class="pi pi-check-circle"></i>
        </div>
        <div>
          <span>Finalizadas</span>
          <strong>{{ countByStatus("FN") }}</strong>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon danger">
          <i class="pi pi-exclamation-triangle"></i>
        </div>
        <div>
          <span>Errores</span>
          <strong>{{ countByStatus("ER") }}</strong>
        </div>
      </div>
    </div>

    <div class="content-grid">
      <Card class="section-card">
        <template #title>
          Máquinas conectadas
        </template>

        <template #content>
          <DataTable
            :value="connections"
            :loading="loading"
            dataKey="id"
            responsiveLayout="scroll"
            stripedRows
            emptyMessage="No hay máquinas conectadas."
          >
            <Column header="Máquina">
              <template #body="{ data }">
                <div class="main-cell">
                  <strong>{{ data.machine_name || data.room || "Sin nombre" }}</strong>
                  <small>{{ data.bot_name || "Bot Instagram" }}</small>
                </div>
              </template>
            </Column>

            <Column field="ip" header="IP" />

            <Column header="Estado" style="width: 130px">
              <template #body="{ data }">
                <Tag
                  :value="data.is_online ? 'Online' : 'Offline'"
                  :severity="data.is_online ? 'success' : 'danger'"
                />
              </template>
            </Column>

            <Column header="Último ping">
              <template #body="{ data }">
                {{ formatDate(data.last_seen_at) }}
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>

      <Card class="section-card">
        <template #title>
          Estado de tareas
        </template>

        <template #content>
          <div class="status-list">
            <div class="status-row">
              <span>Pendientes</span>
              <Tag :value="countByStatus('SP')" severity="warning" />
            </div>

            <div class="status-row">
              <span>En proceso</span>
              <Tag :value="countByStatus('EP')" severity="info" />
            </div>

            <div class="status-row">
              <span>Finalizadas</span>
              <Tag :value="countByStatus('FN')" severity="success" />
            </div>

            <div class="status-row">
              <span>Con error</span>
              <Tag :value="countByStatus('ER')" severity="danger" />
            </div>

            <div class="status-row total">
              <span>Total tareas</span>
              <Tag :value="tasks.length" severity="secondary" />
            </div>
          </div>
        </template>
      </Card>
    </div>

    <Card class="section-card">
      <template #title>
        Últimas tareas
      </template>

      <template #content>
        <DataTable
          :value="recentTasks"
          :loading="loading"
          dataKey="id"
          paginator
          :rows="10"
          responsiveLayout="scroll"
          stripedRows
          showGridlines
          emptyMessage="No hay tareas recientes."
        >
          <Column field="id" header="ID" style="width: 90px">
            <template #body="{ data }">
              <strong>#{{ data.id }}</strong>
            </template>
          </Column>

          <Column header="Tarea">
            <template #body="{ data }">
              <div class="task-tags">
                <Tag
                  v-for="label in getTaskLabels(data)"
                  :key="label"
                  :value="label"
                  severity="info"
                />
              </div>
            </template>
          </Column>

          <Column header="Cuenta">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ data.account_name || "Sin cuenta" }}</strong>
                <small>ID: {{ data.account_id || "N/A" }}</small>
              </div>
            </template>
          </Column>

          <Column header="Estado" style="width: 140px">
            <template #body="{ data }">
              <Tag
                :value="getStatusLabel(data.status_process)"
                :severity="getStatusSeverity(data.status_process)"
              />
            </template>
          </Column>

          <Column field="bot_executor" header="Bot executor">
            <template #body="{ data }">
              {{ data.bot_executor || "NONE" }}
            </template>
          </Column>

          <Column header="Inicio">
            <template #body="{ data }">
              {{ formatDate(data.start_date) }}
            </template>
          </Column>

          <Column header="Fin">
            <template #body="{ data }">
              {{ formatDate(data.end_date) }}
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";

import Button from "primevue/button";
import Card from "primevue/card";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import Tag from "primevue/tag";

import { tasksApi } from "../api/tasks.api";
import { connectionsApi } from "../api/connections.api";
import { normalizeList } from "../api/http";

const loading = ref(false);
const tasks = ref([]);
const accounts = ref([]);
const connections = ref([]);

let refreshInterval = null;

const machinesOnline = computed(() => {
  return connections.value.filter((item) => item.is_online).length;
});

const recentTasks = computed(() => {
  return [...tasks.value]
    .sort((a, b) => {
      const dateA = new Date(a.start_date || 0).getTime();
      const dateB = new Date(b.start_date || 0).getTime();

      return dateB - dateA;
    })
    .slice(0, 25);
});

onMounted(() => {
  loadDashboard();

  refreshInterval = setInterval(() => {
    loadDashboard(false);
  }, 10000);
});

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
});

async function loadDashboard(showLoading = true) {
  if (showLoading) {
    loading.value = true;
  }

  try {
    const [tasksResponse, accountsResponse, connectionsResponse] =
      await Promise.allSettled([
        tasksApi.listTasks(),
        tasksApi.listAccounts(),
        connectionsApi.list(),
      ]);

    if (tasksResponse.status === "fulfilled") {
      tasks.value = normalizeList(tasksResponse.value.data);
    }

    if (accountsResponse.status === "fulfilled") {
      accounts.value = normalizeList(accountsResponse.value.data);
    }

    if (connectionsResponse.status === "fulfilled") {
      connections.value = normalizeList(connectionsResponse.value.data);
    }
  } catch (error) {
    console.error("Error cargando dashboard:", error.response?.data || error);
  } finally {
    loading.value = false;
  }
}

function countByStatus(status) {
  return tasks.value.filter((task) => task.status_process === status).length;
}

function getTaskLabels(row) {
  if (Array.isArray(row.task_labels) && row.task_labels.length > 0) {
    return row.task_labels;
  }

  if (Array.isArray(row.task_names) && row.task_names.length > 0) {
    return row.task_names;
  }

  if (Array.isArray(row.task_type) && row.task_type.length > 0) {
    return row.task_type.map((id) => `Tarea #${id}`);
  }

  return ["Sin tarea"];
}

function getStatusLabel(status) {
  const map = {
    SP: "Pendiente",
    EP: "En proceso",
    FN: "Finalizada",
    ER: "Error",
  };

  return map[status] || status || "N/A";
}

function getStatusSeverity(status) {
  const map = {
    SP: "warning",
    EP: "info",
    FN: "success",
    ER: "danger",
  };

  return map[status] || "secondary";
}

function formatDate(value) {
  if (!value) return "N/A";

  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.page-kicker {
  margin: 0 0 0.35rem;
  color: #ec4899;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.page-title {
  margin: 0;
  font-size: 2rem;
  font-weight: 900;
  color: #111827;
}

.page-subtitle {
  margin: 0.35rem 0 0;
  color: #6b7280;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 1rem;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #fdf2f8;
  color: #db2777;
  font-size: 1.2rem;
  flex: 0 0 auto;
}

.stat-icon.warning {
  background: #fffbeb;
  color: #d97706;
}

.stat-icon.info {
  background: #eff6ff;
  color: #2563eb;
}

.stat-icon.success {
  background: #ecfdf5;
  color: #059669;
}

.stat-icon.danger {
  background: #fef2f2;
  color: #dc2626;
}

.stat-card span {
  display: block;
  font-size: 0.82rem;
  color: #6b7280;
  margin-bottom: 0.15rem;
}

.stat-card strong {
  font-size: 1.55rem;
  color: #111827;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
  gap: 1.25rem;
  align-items: start;
}

.section-card {
  border-radius: 20px;
  overflow: hidden;
}

.status-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  border-bottom: 1px solid #f3f4f6;
  padding-bottom: 0.75rem;
}

.status-row span {
  color: #374151;
  font-weight: 700;
}

.status-row.total {
  border-bottom: none;
  padding-bottom: 0;
  padding-top: 0.3rem;
}

.main-cell {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.main-cell small {
  color: #6b7280;
}

.task-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  max-width: 520px;
}

@media (max-width: 1400px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1000px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

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