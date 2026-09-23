<template>
  <div class="campaigns-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">Prospección</p>
        <h1 class="page-title">Campañas</h1>
        <p class="page-subtitle">
          Crea y administra las campañas de prospección para Instagram.
        </p>
      </div>

      <div class="header-actions">
        <Button
          label="Actualizar"
          icon="pi pi-refresh"
          severity="secondary"
          :loading="loading"
          @click="loadAll"
        />

        <Button
          label="Nueva campaña"
          icon="pi pi-plus"
          @click="openCreate"
        />
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span>Total campañas</span>
        <strong>{{ campaigns.length }}</strong>
      </div>

      <div class="stat-card">
        <span>Activas</span>
        <strong>{{ countByStatus("active") }}</strong>
      </div>

      <div class="stat-card">
        <span>Pausadas</span>
        <strong>{{ countByStatus("paused") }}</strong>
      </div>

      <div class="stat-card">
        <span>Borrador</span>
        <strong>{{ countByStatus("draft") }}</strong>
      </div>

      <div class="stat-card">
        <span>Completadas</span>
        <strong>{{ countByStatus("completed") }}</strong>
      </div>

      <div class="stat-card">
        <span>Cuentas asignadas</span>
        <strong>{{ activeAssignments.length }}</strong>
      </div>
    </div>

    <Card class="section-card">
      <template #title>
        Listado de campañas
      </template>

      <template #content>
        <DataTable
          :value="campaigns"
          :loading="loading"
          dataKey="id"
          paginator
          :rows="12"
          responsiveLayout="scroll"
          stripedRows
          showGridlines
          emptyMessage="No hay campañas registradas."
        >
          <Column field="id" header="ID" style="width: 85px">
            <template #body="{ data }">
              <strong>#{{ data.id }}</strong>
            </template>
          </Column>

          <Column header="Campaña">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ data.name || "Sin nombre" }}</strong>
                <small>{{ data.platform || "instagram" }}</small>
              </div>
            </template>
          </Column>

          <Column header="Estado" style="width: 140px">
            <template #body="{ data }">
              <Tag
                :value="getStatusLabel(data.status)"
                :severity="getStatusSeverity(data.status)"
              />
            </template>
          </Column>

          <Column header="Cuenta principal">
            <template #body="{ data }">
              {{ getCampaignAccountName(data) }}
            </template>
          </Column>

          <Column header="Horario">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ data.business_hours || "Sin horario" }}</strong>
                <small>{{ getShortDescription(data.business_description) }}</small>
              </div>
            </template>
          </Column>

          <Column header="Asignadas" style="width: 120px">
            <template #body="{ data }">
              <Tag
                :value="countAssignmentsByCampaign(data.id)"
                severity="info"
              />
            </template>
          </Column>

          <Column header="Seguimiento">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ data.follow_up_phone || "Sin teléfono" }}</strong>
                <small>{{ data.follow_up_email || "Sin email" }}</small>
              </div>
            </template>
          </Column>

          <Column header="JSON" style="width: 110px">
            <template #body="{ data }">
              <Button
                icon="pi pi-code"
                text
                rounded
                severity="secondary"
                @click="openJsonDialog('Detalle de campaña', data)"
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
                  @click="deleteCampaign(data)"
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
      :header="isEditing ? 'Editar campaña' : 'Nueva campaña'"
      :style="{ width: '940px', maxWidth: '96vw' }"
    >
      <Message
        severity="info"
        :closable="false"
        class="mb-4"
      >
        La campaña se crea aquí. Luego puedes asignarla a una o varias cuentas desde el módulo de Cuentas Sociales.
      </Message>

      <div class="form-grid">
        <div class="form-field">
          <label>Nombre de campaña</label>
          <InputText
            v-model="form.name"
            class="w-full"
            placeholder="Ej: Prospección restaurantes Chicago"
          />
        </div>

        <div class="form-field">
          <label>Plataforma</label>
          <Dropdown
            v-model="form.platform"
            :options="platformOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Estado</label>
          <Dropdown
            v-model="form.status"
            :options="statusOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Cuenta principal</label>
          <Dropdown
            v-model="form.social_media_account"
            :options="accountOptions"
            optionLabel="label"
            optionValue="id"
            placeholder="Selecciona cuenta principal"
            filter
            showClear
            class="w-full"
          />
          <small>
            Este campo es requerido por el modelo actual. Las demás cuentas se asignan desde Cuentas Sociales.
          </small>
        </div>

        <div class="form-field full">
          <label>Descripción de la empresa</label>
          <Textarea
            v-model="form.business_description"
            rows="5"
            autoResize
            class="w-full"
            placeholder="Ej: Empresa de limpieza profesional en Chicago especializada en hogares, oficinas, restaurantes y espacios comerciales."
          />
          <small>
            Esta descripción se usará como contexto para generar contenido más real y comercial.
          </small>
        </div>

        <div class="form-field full">
          <label>Horario de atención</label>
          <InputText
            v-model="form.business_hours"
            class="w-full"
            placeholder="Ej: 24/7 o Lunes a sábado de 8:00 AM a 6:00 PM"
          />
          <small>
            Si trabaja 24/7, escribe 24/7 o Atención 24 horas, 7 días a la semana.
          </small>
        </div>

        <div class="form-field">
          <label>Teléfono de seguimiento</label>
          <InputText
            v-model="form.follow_up_phone"
            class="w-full"
            placeholder="Ej: +1 773 000 0000"
          />
        </div>

        <div class="form-field">
          <label>Email de seguimiento</label>
          <InputText
            v-model="form.follow_up_email"
            class="w-full"
            placeholder="Ej: ventas@empresa.com"
          />
        </div>

        <div class="form-field full">
          <label>Perfil de Instagram del owner / empresa</label>
          <InputText
            v-model="form.owner_instagram_profile_url"
            class="w-full"
            placeholder="Ej: @empresa o https://www.instagram.com/empresa/"
          />
          <small>
            Este campo lo usa el bot para encontrar el perfil principal de la empresa.
          </small>
        </div>

        <div class="form-field full">
          <label>Servicios / services_snapshot</label>
          <Textarea
            v-model="form.services_snapshot_raw"
            rows="8"
            autoResize
            class="json-input w-full"
            placeholder='[{"name":"Limpieza comercial","description":"Servicio para oficinas y negocios"}]'
          />
          <small>
            Debe ser un array JSON. Puedes dejarlo como [].
          </small>
        </div>

        <div class="form-field full">
          <label>Estrategia / strategy_snapshot</label>
          <Textarea
            v-model="form.strategy_snapshot_raw"
            rows="8"
            autoResize
            class="json-input w-full"
            placeholder='{"target":"Restaurantes en Chicago","tone":"Profesional y cercano"}'
          />
          <small>
            Debe ser un objeto JSON. Puedes dejarlo como {}.
          </small>
        </div>
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
          :label="isEditing ? 'Guardar cambios' : 'Crear campaña'"
          icon="pi pi-save"
          :loading="saving"
          @click="saveCampaign"
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
import Dropdown from "primevue/dropdown";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Tag from "primevue/tag";
import Textarea from "primevue/textarea";

import { accountsApi } from "../api/accounts.api";
import { prospectingApi } from "../api/prospecting.api";
import { normalizeList } from "../api/http";

const toast = useToast();

const loading = ref(false);
const saving = ref(false);

const campaigns = ref([]);
const accounts = ref([]);
const campaignAssignments = ref([]);

const formDialogVisible = ref(false);
const jsonDialogVisible = ref(false);

const jsonDialogTitle = ref("");
const jsonDialogContent = ref("{}");

const selectedCampaign = ref(null);
const isEditing = ref(false);
const errorMessage = ref("");

const form = ref(getEmptyForm());

const platformOptions = [
  { label: "Instagram", value: "instagram" },
  { label: "Facebook", value: "facebook" },
];

const statusOptions = [
  { label: "Borrador", value: "draft" },
  { label: "Activa", value: "active" },
  { label: "Pausada", value: "paused" },
  { label: "Completada", value: "completed" },
  { label: "Cancelada", value: "cancelled" },
];

const accountOptions = computed(() => {
  return accounts.value.map((item) => ({
    ...item,
    label: `${item.account_name || `Cuenta #${item.id}`} · ${item.account_kind || "instagram"}`,
  }));
});

const activeAssignments = computed(() => {
  return campaignAssignments.value.filter((item) => item.is_active !== false);
});

onMounted(() => {
  loadAll();
});

async function loadAll() {
  loading.value = true;

  await Promise.allSettled([
    loadCampaigns(),
    loadAccounts(),
    loadCampaignAssignments(),
  ]);

  loading.value = false;
}

async function loadCampaigns() {
  const response = await prospectingApi.listCampaigns();
  campaigns.value = normalizeList(response.data);
}

async function loadAccounts() {
  const response = await accountsApi.list();
  accounts.value = normalizeList(response.data);
}

async function loadCampaignAssignments() {
  const response = await prospectingApi.listCampaignAccounts();
  campaignAssignments.value = normalizeList(response.data);
}

function openCreate() {
  isEditing.value = false;
  selectedCampaign.value = null;
  errorMessage.value = "";
  form.value = getEmptyForm();
  formDialogVisible.value = true;
}

function openEdit(row) {
  isEditing.value = true;
  selectedCampaign.value = row;
  errorMessage.value = "";

  form.value = {
    name: row.name || "",
    platform: row.platform || "instagram",
    status: row.status || "draft",
    social_media_account:
      normalizeId(row.social_media_account) ||
      row.social_media_account_id ||
      null,
    business_description: row.business_description || "",
    business_hours: row.business_hours || "",
    follow_up_phone: row.follow_up_phone || "",
    follow_up_email: row.follow_up_email || "",
    owner_instagram_profile_url: row.owner_instagram_profile_url || "",
    services_snapshot_raw: prettyJson(
      Array.isArray(row.services_snapshot) ? row.services_snapshot : []
    ),
    strategy_snapshot_raw: prettyJson(
      isObjectLike(row.strategy_snapshot) ? row.strategy_snapshot : {}
    ),
  };

  formDialogVisible.value = true;
}

async function saveCampaign() {
  errorMessage.value = "";

  if (!form.value.name?.trim()) {
    errorMessage.value = "El nombre de la campaña es obligatorio.";
    return;
  }

  if (!form.value.social_media_account) {
    errorMessage.value = "La cuenta principal es obligatoria.";
    return;
  }

  let payload;

  try {
    payload = buildPayload();
  } catch (error) {
    errorMessage.value = error.message;
    return;
  }

  saving.value = true;

  try {
    if (isEditing.value && selectedCampaign.value?.id) {
      await prospectingApi.updateCampaign(selectedCampaign.value.id, payload);

      toast.add({
        severity: "success",
        summary: "Campaña actualizada",
        detail: "Los cambios fueron guardados correctamente.",
        life: 3500,
      });
    } else {
      await prospectingApi.createCampaign(payload);

      toast.add({
        severity: "success",
        summary: "Campaña creada",
        detail: "La campaña fue creada correctamente.",
        life: 3500,
      });
    }

    formDialogVisible.value = false;
    await loadCampaigns();
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error guardando campaña:", backendError || error);

    errorMessage.value = backendError
      ? JSON.stringify(backendError)
      : "No se pudo guardar la campaña.";
  } finally {
    saving.value = false;
  }
}

async function deleteCampaign(row) {
  const ok = window.confirm(`¿Eliminar la campaña "${row.name || row.id}"?`);

  if (!ok) return;

  try {
    await prospectingApi.removeCampaign(row.id);

    toast.add({
      severity: "success",
      summary: "Campaña eliminada",
      detail: "La campaña fue eliminada correctamente.",
      life: 3500,
    });

    await Promise.allSettled([
      loadCampaigns(),
      loadCampaignAssignments(),
    ]);
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error eliminando campaña:", backendError || error);

    toast.add({
      severity: "error",
      summary: "Error",
      detail: backendError ? JSON.stringify(backendError) : "No se pudo eliminar.",
      life: 5000,
    });
  }
}

function buildPayload() {
  const servicesSnapshot = parseJsonArray(
    form.value.services_snapshot_raw,
    "services_snapshot debe ser un array JSON válido."
  );

  const strategySnapshot = parseJsonObject(
    form.value.strategy_snapshot_raw,
    "strategy_snapshot debe ser un objeto JSON válido."
  );

  return {
    name: form.value.name.trim(),
    platform: form.value.platform || "instagram",
    status: form.value.status || "draft",
    social_media_account: Number(form.value.social_media_account),

    business_description: form.value.business_description?.trim() || null,
    business_hours: form.value.business_hours?.trim() || null,

    services_snapshot: servicesSnapshot,
    strategy_snapshot: strategySnapshot,
    follow_up_phone: form.value.follow_up_phone?.trim() || null,
    follow_up_email: form.value.follow_up_email?.trim() || null,
    owner_instagram_profile_url:
      form.value.owner_instagram_profile_url?.trim() || null,
  };
}

function getEmptyForm() {
  return {
    name: "",
    platform: "instagram",
    status: "draft",
    social_media_account: null,
    business_description: "",
    business_hours: "",
    follow_up_phone: "",
    follow_up_email: "",
    owner_instagram_profile_url: "",
    services_snapshot_raw: "[]",
    strategy_snapshot_raw: "{}",
  };
}

function parseJsonArray(raw, message) {
  let parsed;

  try {
    parsed = JSON.parse(raw || "[]");
  } catch {
    throw new Error(message);
  }

  if (!Array.isArray(parsed)) {
    throw new Error(message);
  }

  return parsed;
}

function parseJsonObject(raw, message) {
  let parsed;

  try {
    parsed = JSON.parse(raw || "{}");
  } catch {
    throw new Error(message);
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(message);
  }

  return parsed;
}

function normalizeId(value) {
  if (!value) return null;

  if (typeof value === "object") {
    return value.id ?? null;
  }

  return value;
}

function prettyJson(value) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return "{}";
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

function isObjectLike(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function countByStatus(status) {
  return campaigns.value.filter((item) => item.status === status).length;
}

function getStatusLabel(status) {
  const map = {
    draft: "Borrador",
    active: "Activa",
    paused: "Pausada",
    completed: "Completada",
    cancelled: "Cancelada",
  };

  return map[status] || status || "Sin estado";
}

function getStatusSeverity(status) {
  const map = {
    draft: "secondary",
    active: "success",
    paused: "warning",
    completed: "info",
    cancelled: "danger",
  };

  return map[status] || "secondary";
}

function getCampaignAccountName(row) {
  const accountId =
    normalizeId(row.social_media_account) ||
    row.social_media_account_id ||
    null;

  return getAccountName(accountId);
}

function getAccountName(value) {
  const accountId = normalizeId(value);

  if (!accountId) return "Sin cuenta";

  const account = accounts.value.find(
    (item) => Number(item.id) === Number(accountId)
  );

  return account?.account_name || `Cuenta #${accountId}`;
}

function countAssignmentsByCampaign(campaignId) {
  return activeAssignments.value.filter((item) => {
    const itemCampaignId = normalizeId(item.campaign) || item.campaign_id;

    return Number(itemCampaignId) === Number(campaignId);
  }).length;
}

function getShortDescription(value) {
  const text = String(value || "").trim();

  if (!text) return "Sin descripción";

  if (text.length <= 70) return text;

  return `${text.slice(0, 70)}...`;
}
</script>

<style scoped>
.campaigns-page {
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
  grid-template-columns: repeat(6, minmax(0, 1fr));
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

@media (max-width: 1300px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
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