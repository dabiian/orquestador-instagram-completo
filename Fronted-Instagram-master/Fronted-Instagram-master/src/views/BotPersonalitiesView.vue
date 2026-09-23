<template>
  <div class="personalities-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">Configuración</p>
        <h1 class="page-title">Personalidades</h1>
        <p class="page-subtitle">
          Administra las personalidades que usarán las cuentas del bot de Instagram.
        </p>
      </div>

      <div class="header-actions">
        <Button
          label="Actualizar"
          icon="pi pi-refresh"
          severity="secondary"
          :loading="loading"
          @click="loadPersonalities"
        />

        <Button
          label="Nueva personalidad"
          icon="pi pi-plus"
          @click="openCreate"
        />
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span>Total de personalidades</span>
        <strong>{{ personalities.length }}</strong>
      </div>

      <div class="stat-card">
        <span>Campos editables</span>
        <strong>{{ editableFields.length }}</strong>
      </div>
    </div>

    <Card class="section-card">
      <template #title>
        Listado de personalidades
      </template>

      <template #content>
        <DataTable
          :value="personalities"
          :loading="loading"
          dataKey="id"
          paginator
          :rows="12"
          responsiveLayout="scroll"
          stripedRows
          showGridlines
          emptyMessage="No hay personalidades registradas."
        >
          <Column field="id" header="ID" style="width: 85px">
            <template #body="{ data }">
              <strong>#{{ data.id }}</strong>
            </template>
          </Column>

          <Column header="Nombre">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ getPersonalityName(data) }}</strong>
                <small>{{ getPersonalitySubtitle(data) }}</small>
              </div>
            </template>
          </Column>

          <Column header="Resumen">
            <template #body="{ data }">
              <span class="truncate-text">
                {{ getPersonalitySummary(data) }}
              </span>
            </template>
          </Column>

          <Column header="Idioma" style="width: 130px">
            <template #body="{ data }">
              {{ data.language || "Sin idioma" }}
            </template>
          </Column>

          <Column header="JSON" style="width: 110px">
            <template #body="{ data }">
              <Button
                icon="pi pi-code"
                text
                rounded
                severity="secondary"
                @click="openJsonDialog('Detalle de personalidad', data)"
              />
            </template>
          </Column>

          <Column header="Acciones" style="width: 150px">
            <template #body="{ data }">
              <div class="row-actions">
                <Button
                  icon="pi pi-pencil"
                  text
                  rounded
                  severity="info"
                  @click="openEdit(data)"
                />

                <Button
                  icon="pi pi-trash"
                  text
                  rounded
                  severity="danger"
                  @click="deletePersonality(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <Dialog
      v-model:visible="formDialogVisible"
      modal
      :header="isEditing ? 'Editar personalidad' : 'Nueva personalidad'"
      :style="{ width: '940px', maxWidth: '96vw' }"
    >
      <Message
        severity="info"
        :closable="false"
        class="mb-4"
      >
        Completa los campos de la personalidad. Los campos técnicos como ID no se envían al backend.
      </Message>

      <div v-if="editableFields.length" class="form-grid">
        <div
          v-for="field in editableFields"
          :key="field"
          class="form-field"
          :class="{ full: isLongField(field, form[field]) }"
        >
          <label>{{ formatFieldLabel(field) }}</label>

          <Textarea
            v-if="isLongField(field, form[field])"
            v-model="form[field]"
            rows="5"
            autoResize
            class="w-full"
            :placeholder="getFieldPlaceholder(field)"
          />

          <InputText
            v-else
            v-model="form[field]"
            class="w-full"
            :placeholder="getFieldPlaceholder(field)"
          />

          <small v-if="getFieldHelp(field)">
            {{ getFieldHelp(field) }}
          </small>
        </div>
      </div>

      <div v-else class="empty-fields">
        No se detectaron campos editables todavía. Puedes crear la personalidad usando el JSON manual.
      </div>

      <Divider />

      <div class="form-field full">
        <label>JSON extra / payload manual</label>

        <Textarea
          v-model="extraJsonRaw"
          rows="9"
          autoResize
          class="json-input w-full"
          placeholder='{"name":"Sofía","language":"español","communication_style":"Amable, natural y profesional"}'
        />

        <small>
          Este JSON se mezcla con el formulario. Si repites una clave, el JSON extra tiene prioridad.
        </small>
      </div>

      <Message
        v-if="errorMessage"
        severity="error"
        class="mt-4"
        :closable="false"
      >
        {{ errorMessage }}
      </Message>

      <template #footer>
        <Button
          label="Cancelar"
          severity="secondary"
          outlined
          @click="formDialogVisible = false"
        />

        <Button
          :label="isEditing ? 'Guardar cambios' : 'Crear personalidad'"
          icon="pi pi-save"
          :loading="saving"
          @click="savePersonality"
        />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="jsonDialogVisible"
      modal
      :header="jsonDialogTitle"
      :style="{ width: '760px', maxWidth: '95vw' }"
    >
      <pre class="json-box">{{ jsonDialogContent }}</pre>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useToast } from "primevue/usetoast";

import Button from "primevue/button";
import Card from "primevue/card";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import Dialog from "primevue/dialog";
import Divider from "primevue/divider";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Textarea from "primevue/textarea";

import { personalitiesApi } from "../api/personalities.api";
import { normalizeList } from "../api/http";

const toast = useToast();

const loading = ref(false);
const saving = ref(false);

const personalities = ref([]);
const formDialogVisible = ref(false);
const jsonDialogVisible = ref(false);

const jsonDialogTitle = ref("");
const jsonDialogContent = ref("{}");

const selectedPersonality = ref(null);
const isEditing = ref(false);
const errorMessage = ref("");

const form = ref({});
const extraJsonRaw = ref("{}");

const readOnlyFields = [
  "id",
  "pk",
  "created_at",
  "updated_at",
  "create_date",
  "update_date",
  "deleted_at",
];

const fieldLabels = {
  name: "Nombre",
  bio: "Biografía",
  location: "Ubicación",
  language: "Idioma",
  communication_style: "Estilo de comunicación",
  values: "Valores",
  preferences: "Preferencias",
  dislikes: "Cosas que debe evitar",
  example_responses: "Respuestas de ejemplo",
  special_knowledge: "Conocimiento especial",
  cultural_references: "Referencias culturales",
  phraseology: "Fraseología",
  past_interactions: "Interacciones pasadas",
  emotional_reactions: "Reacciones emocionales",
  objectives: "Objetivos",
  behavioral_tendencies: "Tendencias de comportamiento",
};

const fieldPlaceholders = {
  name: "Ej: Sofía, Camila ventas, Asistente profesional",
  bio: "Describe brevemente quién es esta personalidad y cómo debe comportarse.",
  location: "Ej: Chicago, Bogotá, Estados Unidos, Colombia",
  language: "Ej: español, inglés, español neutro",
  communication_style: "Ej: amable, natural, profesional, cercana, persuasiva sin presión",
  values: "Ej: respeto, claridad, empatía, privacidad, profesionalismo",
  preferences: "Ej: responder de forma breve, usar tono humano, evitar tecnicismos",
  dislikes: "Ej: no sonar robótico, no prometer resultados, no insistir demasiado",
  example_responses: "Agrega ejemplos de respuestas que esta personalidad podría usar.",
  special_knowledge: "Agrega información específica del negocio, servicio o campaña.",
  cultural_references: "Ej: referencias locales, estilo latino, contexto de Chicago, etc.",
  phraseology: "Frases típicas, muletillas o formas de hablar que debe usar.",
  past_interactions: "Notas sobre interacciones anteriores o contexto conversacional.",
  emotional_reactions: "Cómo debe reaccionar ante dudas, objeciones, interés o rechazo.",
  objectives: "Qué busca lograr esta personalidad: agendar, informar, convertir, responder, etc.",
  behavioral_tendencies: "Patrones de comportamiento: paciente, directa, consultiva, empática, etc.",
};

const fieldHelp = {
  name: "Nombre interno para identificar la personalidad.",
  bio: "Este campo ayuda a definir el contexto general de la personalidad.",
  communication_style: "Define cómo debe hablar: formal, casual, cercana, directa, etc.",
  values: "Sirve para mantener consistencia ética y de marca.",
  preferences: "Preferencias de respuesta o comportamiento.",
  dislikes: "Cosas que el bot debe evitar al responder.",
  example_responses: "Puedes pegar varias respuestas modelo.",
  special_knowledge: "Información que el bot debe recordar sobre la marca o servicio.",
  objectives: "Define la intención principal de esta personalidad.",
};

const editableFields = computed(() => {
  const keys = new Set();

  for (const item of personalities.value) {
    Object.keys(item || {}).forEach((key) => {
      if (!readOnlyFields.includes(key)) {
        keys.add(key);
      }
    });
  }

  const orderedFields = [
    "name",
    "bio",
    "location",
    "language",
    "communication_style",
    "values",
    "preferences",
    "dislikes",
    "example_responses",
    "special_knowledge",
    "cultural_references",
    "phraseology",
    "past_interactions",
    "emotional_reactions",
    "objectives",
    "behavioral_tendencies",
  ];

  const detectedFields = Array.from(keys);

  return [
    ...orderedFields.filter((field) => detectedFields.includes(field)),
    ...detectedFields.filter((field) => !orderedFields.includes(field)),
  ];
});

onMounted(() => {
  loadPersonalities();
});

async function loadPersonalities() {
  loading.value = true;

  try {
    const response = await personalitiesApi.list();
    personalities.value = normalizeList(response.data);
  } catch (error) {
    console.error("Error cargando personalidades:", error.response?.data || error);
    personalities.value = [];

    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudieron cargar las personalidades.",
      life: 4500,
    });
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  isEditing.value = false;
  selectedPersonality.value = null;
  errorMessage.value = "";

  const emptyForm = {};

  for (const field of editableFields.value) {
    emptyForm[field] = "";
  }

  form.value = emptyForm;
  extraJsonRaw.value = "{}";
  formDialogVisible.value = true;
}

function openEdit(row) {
  isEditing.value = true;
  selectedPersonality.value = row;
  errorMessage.value = "";

  const nextForm = {};

  for (const field of editableFields.value) {
    const value = row?.[field];

    if (isObjectLike(value)) {
      nextForm[field] = JSON.stringify(value, null, 2);
    } else {
      nextForm[field] = value ?? "";
    }
  }

  form.value = nextForm;
  extraJsonRaw.value = "{}";
  formDialogVisible.value = true;
}

async function savePersonality() {
  errorMessage.value = "";

  let payload;

  try {
    payload = buildPayload();
  } catch (error) {
    errorMessage.value = error.message;
    return;
  }

  if (Object.keys(payload).length === 0) {
    errorMessage.value = "No hay datos para guardar.";
    return;
  }

  saving.value = true;

  try {
    if (isEditing.value && selectedPersonality.value?.id) {
      await personalitiesApi.update(selectedPersonality.value.id, payload);

      toast.add({
        severity: "success",
        summary: "Personalidad actualizada",
        detail: "Los cambios fueron guardados correctamente.",
        life: 3500,
      });
    } else {
      await personalitiesApi.create(payload);

      toast.add({
        severity: "success",
        summary: "Personalidad creada",
        detail: "La personalidad fue creada correctamente.",
        life: 3500,
      });
    }

    formDialogVisible.value = false;
    await loadPersonalities();
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error guardando personalidad:", backendError || error);

    errorMessage.value = backendError
      ? JSON.stringify(backendError)
      : "No se pudo guardar la personalidad.";
  } finally {
    saving.value = false;
  }
}

async function deletePersonality(row) {
  const ok = window.confirm(
    `¿Eliminar la personalidad "${getPersonalityName(row)}"?`
  );

  if (!ok) return;

  try {
    await personalitiesApi.remove(row.id);

    toast.add({
      severity: "success",
      summary: "Personalidad eliminada",
      detail: "La personalidad fue eliminada correctamente.",
      life: 3500,
    });

    await loadPersonalities();
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error eliminando personalidad:", backendError || error);

    toast.add({
      severity: "error",
      summary: "Error",
      detail: backendError ? JSON.stringify(backendError) : "No se pudo eliminar.",
      life: 5000,
    });
  }
}

function buildPayload() {
  const payload = {};

  for (const field of editableFields.value) {
    const rawValue = form.value[field];

    if (rawValue === "" || rawValue === null || rawValue === undefined) {
      continue;
    }

    payload[field] = parseFieldValue(rawValue);
  }

  const extra = parseExtraJson(extraJsonRaw.value);

  return {
    ...payload,
    ...extra,
  };
}

function parseFieldValue(value) {
  if (typeof value !== "string") {
    return value;
  }

  const trimmed = value.trim();

  if (!trimmed) return "";

  if (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  ) {
    try {
      return JSON.parse(trimmed);
    } catch {
      return value;
    }
  }

  if (trimmed === "true") return true;
  if (trimmed === "false") return false;

  return value;
}

function parseExtraJson(raw) {
  const clean = raw?.trim();

  if (!clean) return {};

  let parsed;

  try {
    parsed = JSON.parse(clean);
  } catch {
    throw new Error("El JSON extra no es válido.");
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("El JSON extra debe ser un objeto JSON.");
  }

  return parsed;
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

function getPersonalityName(row) {
  return (
    row?.name ||
    row?.personality_name ||
    row?.bot_name ||
    row?.title ||
    row?.nombre ||
    `Personalidad #${row?.id}`
  );
}

function getPersonalitySubtitle(row) {
  return (
    row?.communication_style ||
    row?.language ||
    row?.location ||
    "Sin subtítulo"
  );
}

function getPersonalitySummary(row) {
  const candidates = [
    row?.bio,
    row?.communication_style,
    row?.special_knowledge,
    row?.objectives,
    row?.preferences,
    row?.values,
  ];

  const found = candidates.find((item) => item);

  if (!found) return "Sin resumen disponible.";

  if (typeof found === "object") {
    return JSON.stringify(found).slice(0, 180);
  }

  return String(found).slice(0, 180);
}

function isObjectLike(value) {
  return value && typeof value === "object";
}

function isLongField(field, value) {
  const lower = String(field).toLowerCase();

  return (
    lower.includes("bio") ||
    lower.includes("style") ||
    lower.includes("communication") ||
    lower.includes("values") ||
    lower.includes("preferences") ||
    lower.includes("dislikes") ||
    lower.includes("responses") ||
    lower.includes("knowledge") ||
    lower.includes("references") ||
    lower.includes("phraseology") ||
    lower.includes("interactions") ||
    lower.includes("reactions") ||
    lower.includes("objectives") ||
    lower.includes("tendencies") ||
    lower.includes("prompt") ||
    lower.includes("description") ||
    lower.includes("rules") ||
    lower.includes("context") ||
    String(value || "").length > 90
  );
}

function formatFieldLabel(field) {
  if (fieldLabels[field]) {
    return fieldLabels[field];
  }

  return String(field)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getFieldPlaceholder(field) {
  return fieldPlaceholders[field] || "";
}

function getFieldHelp(field) {
  return fieldHelp[field] || "";
}
</script>

<style scoped>
.personalities-page {
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

.header-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
  color: #6b7280;
  font-size: 0.85rem;
  margin-bottom: 0.35rem;
}

.stat-card strong {
  font-size: 1.6rem;
  color: #111827;
}

.section-card {
  border-radius: 20px;
  overflow: hidden;
}

.main-cell {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.main-cell small {
  color: #6b7280;
}

.truncate-text {
  display: inline-block;
  max-width: 620px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-actions {
  display: flex;
  gap: 0.25rem;
  align-items: center;
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

.empty-fields {
  border: 1px dashed #d1d5db;
  color: #6b7280;
  border-radius: 14px;
  padding: 1rem;
  background: #f9fafb;
}

.json-input,
.json-box {
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

.json-box {
  margin: 0;
  background: #0f172a;
  color: #e5e7eb;
  padding: 1rem;
  border-radius: 14px;
  overflow: auto;
  max-height: 560px;
  font-size: 0.85rem;
}

.mb-4 {
  margin-bottom: 1rem;
}

.mt-4 {
  margin-top: 1rem;
}

.w-full {
  width: 100%;
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
  }

  .stats-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>