<template>
  <div class="tasks-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">Operación</p>
        <h1 class="page-title">Crear Tareas</h1>
        <p class="page-subtitle">
          Crea tareas del bot de Instagram para una cuenta específica o para todas las cuentas.
        </p>
        <p v-if="orchestratorUrl" class="page-subtitle">
          Para ejecutar maduración o prospección desde el orquestador,
          <a :href="orchestratorUrl" target="_blank" rel="noopener noreferrer">abre el panel de ejecuciones ↗</a>.
          Las tareas creadas aquí siguen el flujo directo del backend.
        </p>
      </div>

      <Button
        label="Recargar cuentas"
        icon="pi pi-refresh"
        severity="secondary"
        :loading="loadingCatalogs"
        @click="loadCatalogs"
      />
    </div>

    <div class="grid-layout">
      <Card class="section-card">
        <template #title>
          Nueva tarea
        </template>

        <template #content>
          <div class="form-grid">
            <div class="form-field full">
              <label>Tareas del bot</label>

              <MultiSelect
                v-model="form.task_type_id"
                :options="taskTypes"
                optionLabel="label"
                optionValue="id"
                placeholder="Selecciona una o varias tareas"
                filter
                display="chip"
                class="w-full"
              />

              <small>
                Se enviará como array de IDs. Ejemplo: [10] o [10, 11, 12].
              </small>
            </div>

            <div class="form-field">
              <label>Asignación</label>

              <Dropdown
                v-model="form.target_mode"
                :options="targetModes"
                optionLabel="label"
                optionValue="value"
                class="w-full"
              />
            </div>

            <div v-if="form.target_mode === 'one'" class="form-field">
              <label>Cuenta social</label>

              <Dropdown
                v-model="form.social_media_account_id"
                :options="accounts"
                optionLabel="label"
                optionValue="id"
                placeholder="Selecciona una cuenta"
                filter
                showClear
                class="w-full"
              />
            </div>

            <div class="form-field full">
              <label>Mensaje / texto opcional</label>

              <Textarea
                v-model="form.post"
                rows="5"
                autoResize
                placeholder="Opcional. Úsalo solo si la tarea necesita texto, comentario, caption o instrucción."
                class="w-full"
              />
            </div>

            <div class="form-field">
              <label>¿Contiene imagen?</label>

              <div class="checkbox-row">
                <Checkbox
                  v-model="form.contains_image"
                  binary
                  inputId="containsImage"
                />
                <label for="containsImage">Sí, incluye imagen</label>
              </div>
            </div>

            <div class="form-field full">
              <label>Links de imágenes</label>

              <Textarea
                v-model="imageLinksRaw"
                rows="4"
                autoResize
                placeholder="Opcional. Un link por línea."
                class="w-full"
              />

              <small>
                Déjalo vacío si la tarea no necesita imágenes.
              </small>
            </div>

            <div class="form-field full">
              <label>JSON extra opcional</label>

              <Textarea
                v-model="extraJsonRaw"
                rows="6"
                autoResize
                class="json-input w-full"
                placeholder='Ejemplo: {"profile_url":"https://instagram.com/usuario","comment_text":"Hola"}'
              />

              <small>
                Aquí puedes mandar campos específicos para una tarea. Debe ser un objeto JSON válido.
              </small>
            </div>
          </div>

          <Divider />

          <div class="actions-row">
            <Button
              label="Crear tarea"
              icon="pi pi-send"
              :loading="saving"
              @click="submitTask"
            />

            <Button
              label="Limpiar"
              icon="pi pi-eraser"
              severity="secondary"
              outlined
              :disabled="saving"
              @click="resetForm"
            />
          </div>

          <Message
            v-if="lastResponse"
            severity="success"
            class="mt-4"
            :closable="false"
          >
            {{ lastResponse }}
          </Message>

          <Message
            v-if="errorMessage"
            severity="error"
            class="mt-4"
            :closable="false"
          >
            {{ errorMessage }}
          </Message>
        </template>
      </Card>

      <Card class="section-card">
        <template #title>
          Preview payload
        </template>

        <template #content>
          <pre class="preview-box">{{ previewPayload }}</pre>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { orchestratorDashboardUrl } from "../config/orchestrator";

const orchestratorUrl = orchestratorDashboardUrl();
import { computed, onMounted, ref } from "vue";
import { useToast } from "primevue/usetoast";

import Button from "primevue/button";
import Card from "primevue/card";
import Checkbox from "primevue/checkbox";
import Divider from "primevue/divider";
import Dropdown from "primevue/dropdown";
import Message from "primevue/message";
import MultiSelect from "primevue/multiselect";
import Textarea from "primevue/textarea";

import { tasksApi } from "../api/tasks.api";
import { normalizeList } from "../api/http";
import { INSTAGRAM_TASK_TYPES } from "../constants/instagramTaskTypes";

const toast = useToast();

const loadingCatalogs = ref(false);
const saving = ref(false);

const accounts = ref([]);
const taskTypes = ref(INSTAGRAM_TASK_TYPES);

const imageLinksRaw = ref("");
const extraJsonRaw = ref("{}");

const lastResponse = ref("");
const errorMessage = ref("");

const form = ref({
  task_type_id: [],
  target_mode: "all",
  social_media_account_id: null,
  contains_image: false,
  post: "",
});

const targetModes = [
  { label: "Todas las cuentas", value: "all" },
  { label: "Una cuenta específica", value: "one" },
];

const previewPayload = computed(() => {
  try {
    return JSON.stringify(buildPayload(), null, 2);
  } catch {
    return "JSON extra inválido";
  }
});

onMounted(() => {
  loadCatalogs();
});

async function loadCatalogs() {
  loadingCatalogs.value = true;

  try {
    const accountsResponse = await tasksApi.listAccounts();

    accounts.value = normalizeList(accountsResponse.data).map((item) => ({
      ...item,
      id: item.id,
      label: buildAccountLabel(item),
    }));
  } catch (error) {
    console.error("Error cargando cuentas:", error.response?.data || error);

    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudieron cargar las cuentas sociales.",
      life: 4500,
    });
  } finally {
    loadingCatalogs.value = false;
  }
}

async function submitTask() {
  errorMessage.value = "";
  lastResponse.value = "";

  if (
    !Array.isArray(form.value.task_type_id) ||
    form.value.task_type_id.length === 0
  ) {
    errorMessage.value = "Selecciona al menos una tarea.";
    return;
  }

  if (form.value.target_mode === "one" && !form.value.social_media_account_id) {
    errorMessage.value = "Selecciona una cuenta social.";
    return;
  }

  let payload;

  try {
    payload = buildPayload();
  } catch (error) {
    errorMessage.value = error.message;
    return;
  }

  const accountId =
    form.value.target_mode === "one"
      ? form.value.social_media_account_id
      : null;

  saving.value = true;

  try {
    const response = await tasksApi.createForAccounts(payload, accountId);

    const affectedCount = response.data?.affected_accounts_count ?? 0;
    const message = response.data?.message || "Tarea creada correctamente.";

    lastResponse.value = `${message} Cuentas afectadas: ${affectedCount}`;

    toast.add({
      severity: "success",
      summary: "Tarea creada",
      detail: lastResponse.value,
      life: 4500,
    });
  } catch (error) {
    const backendError = error.response?.data;

    console.error("Error creando tarea:", backendError || error);

    errorMessage.value = backendError
      ? JSON.stringify(backendError)
      : "No se pudo crear la tarea.";

    toast.add({
      severity: "error",
      summary: "Error",
      detail: errorMessage.value,
      life: 6500,
    });
  } finally {
    saving.value = false;
  }
}

function buildPayload() {
  const extraJson = parseExtraJson();

  const customTask = {
    ...extraJson,
  };

  const post = form.value.post?.trim();

  if (post) {
    customTask.post = post;
  }

  const linksImage = imageLinksRaw.value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

  if (linksImage.length > 0) {
    customTask.links_image = linksImage;
  }

  if (form.value.contains_image) {
    customTask.contains_image = true;
  }

  return {
    task_type_id: form.value.task_type_id.map((id) => Number(id)),
    custom_task: customTask,
  };
}

function parseExtraJson() {
  const raw = extraJsonRaw.value?.trim();

  if (!raw) return {};

  let parsed;

  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("El JSON extra no es válido.");
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("El JSON extra debe ser un objeto, no un array ni texto.");
  }

  return parsed;
}

function resetForm() {
  form.value = {
    task_type_id: [],
    target_mode: "all",
    social_media_account_id: null,
    contains_image: false,
    post: "",
  };

  imageLinksRaw.value = "";
  extraJsonRaw.value = "{}";
  lastResponse.value = "";
  errorMessage.value = "";
}

function buildAccountLabel(item) {
  const accountName =
    item.account_name ||
    item.username ||
    item.name ||
    `Cuenta #${item.id}`;

  const owner =
    item.owner?.name ||
    item.owner?.owner_name ||
    item.owner_name ||
    "";

  const proxy =
    item.proxy?.proxy ||
    item.proxy?.host ||
    item.proxy_ip ||
    "";

  const campaign =
    item.campaign_info?.campaign_name ||
    item.campaign_name ||
    "";

  const extra = [owner, campaign, proxy].filter(Boolean).join(" · ");

  return extra ? `${accountName} · ${extra}` : accountName;
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

.grid-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr);
  gap: 1.25rem;
  align-items: start;
}

.section-card {
  border-radius: 20px;
  overflow: hidden;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.form-field.full {
  grid-column: 1 / -1;
}

.form-field label {
  color: #374151;
  font-size: 0.87rem;
  font-weight: 800;
}

.form-field small {
  color: #6b7280;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-height: 42px;
}

.checkbox-row label {
  font-weight: 600;
  color: #4b5563;
}

.actions-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.preview-box,
.json-input {
  font-family:
    ui-monospace,
    SFMono-Regular,
    Menlo,
    Monaco,
    Consolas,
    "Liberation Mono",
    "Courier New",
    monospace;
}

.preview-box {
  margin: 0;
  background: #0f172a;
  color: #e5e7eb;
  padding: 1rem;
  border-radius: 14px;
  overflow: auto;
  min-height: 420px;
  max-height: 650px;
  font-size: 0.85rem;
}

.mt-4 {
  margin-top: 1rem;
}

.w-full {
  width: 100%;
}

@media (max-width: 1100px) {
  .grid-layout {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
