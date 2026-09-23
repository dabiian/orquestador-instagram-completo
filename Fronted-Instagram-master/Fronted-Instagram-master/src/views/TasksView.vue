<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">Tareas</h2>
        <p class="page-subtitle">Crea tareas para una cuenta o para todas las cuentas.</p>
      </div>

      <Button label="Nueva tarea" icon="pi pi-plus" @click="openCreate" />
    </div>

    <section class="section-card">
      <DataTable :value="items" :loading="loading" dataKey="id" paginator :rows="10" stripedRows responsiveLayout="scroll">
        <Column field="id" header="ID" style="width: 90px" sortable />
        <Column field="task_type" header="Task Type" />
        <Column header="Cuenta">
          <template #body="{ data }">
            {{ getAccountName(data.social_media_account) }}
          </template>
        </Column>
        <Column field="status_process" header="Estado">
          <template #body="{ data }">
            <Tag :value="data.status_process || '-'" :severity="taskSeverity(data.status_process)" />
          </template>
        </Column>
        <Column field="bot_executor" header="Executor" />
        <Column field="start_date" header="Inicio" />
        <Column field="end_date" header="Fin" />

        <template #empty>
          <div class="empty-state">No hay tareas registradas.</div>
        </template>
      </DataTable>
    </section>

    <Dialog v-model:visible="showDialog" modal header="Nueva tarea" style="width: 720px; max-width: 95vw">
      <div class="form-grid">
        <div class="form-field full">
          <label>Modo</label>
          <Select v-model="mode" :options="modeOptions" optionLabel="label" optionValue="value" />
        </div>

        <div v-if="mode === 'account'" class="form-field full">
          <label>Cuenta</label>
          <Select v-model="selectedAccountId" :options="accounts" optionLabel="account_name" optionValue="id" />
        </div>

        <div class="form-field full">
          <label>Task type IDs</label>
          <InputText v-model="taskTypeRaw" placeholder="Ejemplo: 1,2,3" />
        </div>

        <div class="form-field full">
          <label>Custom task JSON</label>
          <Textarea v-model="customTaskRaw" rows="8" autoResize />
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" severity="secondary" outlined @click="showDialog = false" />
        <Button label="Crear tarea" icon="pi pi-send" :loading="saving" @click="saveTask" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useToast } from "primevue/usetoast";

import Button from "primevue/button";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Dialog from "primevue/dialog";
import Select from "primevue/select";
import InputText from "primevue/inputtext";
import Textarea from "primevue/textarea";
import Tag from "primevue/tag";

import { tasksApi } from "../api/tasks.api";
import { socialAccountsApi } from "../api/socialAccounts.api";
import { normalizeList } from "../api/http";

const toast = useToast();

const items = ref([]);
const accounts = ref([]);
const loading = ref(false);
const saving = ref(false);
const showDialog = ref(false);

const mode = ref("account");
const selectedAccountId = ref(null);
const taskTypeRaw = ref("");
const customTaskRaw = ref("{}");

const modeOptions = [
  { label: "Crear para una cuenta", value: "account" },
  { label: "Crear para todas las cuentas", value: "all" },
];

function getAccountName(value) {
  if (!value) return "-";
  if (typeof value === "object") return value.account_name || value.id;
  const found = accounts.value.find((x) => x.id === value);
  return found?.account_name || value;
}

function taskSeverity(status) {
  if (status === "FN" || status === "success") return "success";
  if (status === "SP" || status === "pending") return "warn";
  if (status === "EP" || status === "running") return "info";
  if (status === "ER" || status === "failed") return "danger";
  return "secondary";
}

async function loadItems() {
  loading.value = true;

  try {
    const response = await tasksApi.list();
    items.value = normalizeList(response.data);
  } catch {
    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudieron cargar las tareas.",
      life: 3000,
    });
  } finally {
    loading.value = false;
  }
}

async function loadAccounts() {
  const response = await socialAccountsApi.list();
  accounts.value = normalizeList(response.data);
}

function openCreate() {
  mode.value = "account";
  selectedAccountId.value = null;
  taskTypeRaw.value = "";
  customTaskRaw.value = "{}";
  showDialog.value = true;
}

function parseTaskTypes() {
  return taskTypeRaw.value
    .split(",")
    .map((x) => Number(String(x).trim()))
    .filter((x) => Number.isInteger(x) && x > 0);
}

async function saveTask() {
  const taskTypeIds = parseTaskTypes();

  if (!taskTypeIds.length) {
    toast.add({
      severity: "warn",
      summary: "Validación",
      detail: "Debes poner al menos un task type ID.",
      life: 3000,
    });
    return;
  }

  if (mode.value === "account" && !selectedAccountId.value) {
    toast.add({
      severity: "warn",
      summary: "Validación",
      detail: "Selecciona una cuenta.",
      life: 3000,
    });
    return;
  }

  saving.value = true;

  try {
    const payload = {
      task_type_id: taskTypeIds,
      custom_task: JSON.parse(customTaskRaw.value || "{}"),
    };

    if (mode.value === "account") {
      await tasksApi.generateForAccount(selectedAccountId.value, payload);
    } else {
      await tasksApi.generateForAll(payload);
    }

    toast.add({
      severity: "success",
      summary: "Creada",
      detail: "Tarea creada correctamente.",
      life: 2500,
    });

    showDialog.value = false;
    await loadItems();
  } catch {
    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudo crear la tarea. Revisa JSON y task type IDs.",
      life: 4000,
    });
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadAccounts(), loadItems()]);
});
</script>