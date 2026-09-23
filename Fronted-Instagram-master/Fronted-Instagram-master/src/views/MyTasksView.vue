<template>
  <div class="tasks-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">Operación</p>
        <h1 class="page-title">Mis Tareas</h1>
        <p class="page-subtitle">
          Consulta tareas pendientes, en proceso, finalizadas o con error.
        </p>
      </div>

      <Button
        label="Actualizar"
        icon="pi pi-refresh"
        :loading="loading"
        @click="loadTasks"
      />
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span>Total</span>
        <strong>{{ tasks.length }}</strong>
      </div>

      <div class="stat-card">
        <span>Pendientes</span>
        <strong>{{ countByStatus("SP") }}</strong>
      </div>

      <div class="stat-card">
        <span>En proceso</span>
        <strong>{{ countByStatus("EP") }}</strong>
      </div>

      <div class="stat-card">
        <span>Finalizadas</span>
        <strong>{{ countByStatus("FN") }}</strong>
      </div>

      <div class="stat-card">
        <span>Error</span>
        <strong>{{ countByStatus("ER") }}</strong>
      </div>
    </div>

    <Card class="section-card">
      <template #title>
        Filtros
      </template>

      <template #content>
        <div class="filters-grid">
          <div class="form-field">
            <label>Estado</label>
            <Dropdown
              v-model="filters.status_process"
              :options="statusOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="Todos"
              showClear
              class="w-full"
            />
          </div>

          <div class="form-field">
            <label>Fecha inicio</label>
            <InputText
              v-model="filters.start_date"
              type="date"
              class="w-full"
            />
          </div>

          <div class="form-field">
            <label>Fecha fin</label>
            <InputText
              v-model="filters.start_date_end"
              type="date"
              class="w-full"
            />
          </div>

          <div class="filter-actions">
            <Button
              label="Filtrar"
              icon="pi pi-search"
              :loading="loading"
              @click="loadTasks"
            />

            <Button
              label="Limpiar"
              icon="pi pi-filter-slash"
              severity="secondary"
              outlined
              @click="clearFilters"
            />
          </div>
        </div>
      </template>
    </Card>

    <Card class="section-card">
      <template #title>
        Listado de tareas
      </template>

      <template #content>
        <DataTable
          :value="tasks"
          :loading="loading"
          dataKey="id"
          paginator
          :rows="12"
          responsiveLayout="scroll"
          stripedRows
          showGridlines
          emptyMessage="No hay tareas para mostrar."
        >
          <Column field="id" header="ID" style="width: 90px">
            <template #body="{ data }">
              <strong>#{{ data.id }}</strong>
            </template>
          </Column>

          <Column header="Tareas">
            <template #body="{ data }">
              <div class="task-list">
                <Tag
                  v-for="label in getTaskLabels(data)"
                  :key="label"
                  :value="label"
                  severity="info"
                />
              </div>
            </template>
          </Column>

          <Column field="account_name" header="Cuenta">
            <template #body="{ data }">
              <div class="account-cell">
                <strong>{{ data.account_name || "Sin cuenta" }}</strong>
                <small>ID: {{ data.account_id || "N/A" }}</small>
              </div>
            </template>
          </Column>

          <Column field="status_process" header="Estado" style="width: 140px">
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

          <Column field="start_date" header="Inicio">
            <template #body="{ data }">
              {{ formatDate(data.start_date) }}
            </template>
          </Column>

          <Column field="end_date" header="Fin">
            <template #body="{ data }">
              {{ formatDate(data.end_date) }}
            </template>
          </Column>

          <Column header="Custom task" style="width: 110px">
            <template #body="{ data }">
              <Button
                icon="pi pi-code"
                text
                rounded
                severity="secondary"
                @click="openJsonDialog('Custom task', data.custom_task)"
              />
            </template>
          </Column>

          <Column header="Comentario" style="width: 110px">
            <template #body="{ data }">
              <Button
                icon="pi pi-comment"
                text
                rounded
                severity="secondary"
                @click="openJsonDialog('Comentario', data.comment)"
              />
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="jsonDialogVisible"
      modal
      :header="jsonDialogTitle"
      :style="{ width: '680px', maxWidth: '95vw' }"
    >
      <pre class="json-box">{{ jsonDialogContent }}</pre>
    </Dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";

import Button from "primevue/button";
import Card from "primevue/card";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import Dialog from "primevue/dialog";
import Dropdown from "primevue/dropdown";
import InputText from "primevue/inputtext";
import Tag from "primevue/tag";

import { tasksApi } from "../api/tasks.api";
import { normalizeList } from "../api/http";

const loading = ref(false);
const tasks = ref([]);

const jsonDialogVisible = ref(false);
const jsonDialogTitle = ref("");
const jsonDialogContent = ref("{}");

const filters = ref({
  status_process: null,
  start_date: "",
  start_date_end: "",
});

const statusOptions = [
  { label: "Pendiente", value: "SP" },
  { label: "En proceso", value: "EP" },
  { label: "Finalizada", value: "FN" },
  { label: "Error", value: "ER" },
];

onMounted(() => {
  loadTasks();
});

async function loadTasks() {
  loading.value = true;

  try {
    const params = buildParams();
    const response = await tasksApi.listTasks(params);
    tasks.value = normalizeList(response.data);
  } catch (error) {
    console.error("Error cargando tareas:", error.response?.data || error);
    tasks.value = [];
  } finally {
    loading.value = false;
  }
}

function buildParams() {
  const params = {};

  if (filters.value.status_process) {
    params.status_process = filters.value.status_process;
  }

  if (filters.value.start_date) {
    params.start_date = filters.value.start_date;
  }

  if (filters.value.start_date_end) {
    params.start_date_end = filters.value.start_date_end;
  }

  return params;
}

function clearFilters() {
  filters.value = {
    status_process: null,
    start_date: "",
    start_date_end: "",
  };

  loadTasks();
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

function openJsonDialog(title, value) {
  jsonDialogTitle.value = title;

  try {
    jsonDialogContent.value = JSON.stringify(value || {}, null, 2);
  } catch {
    jsonDialogContent.value = String(value || "");
  }

  jsonDialogVisible.value = true;
}
</script>

<style scoped>
.tasks-page {
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
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 1rem;
}

.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 1rem;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.stat-card span {
  display: block;
  font-size: 0.85rem;
  color: #6b7280;
  margin-bottom: 0.4rem;
}

.stat-card strong {
  font-size: 1.6rem;
  color: #111827;
}

.section-card {
  border-radius: 20px;
  overflow: hidden;
}

.filters-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 1rem;
  align-items: end;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.form-field label {
  color: #374151;
  font-size: 0.87rem;
  font-weight: 800;
}

.filter-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.task-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  max-width: 440px;
}

.account-cell {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.account-cell small {
  color: #6b7280;
}

.json-box {
  margin: 0;
  background: #0f172a;
  color: #e5e7eb;
  padding: 1rem;
  border-radius: 14px;
  overflow: auto;
  max-height: 520px;
  font-size: 0.85rem;
}

.w-full {
  width: 100%;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filters-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
  }

  .stats-grid,
  .filters-grid {
    grid-template-columns: 1fr;
  }
}
</style>