<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">Campañas</h2>
        <p class="page-subtitle">
          Crea campañas de prospección, define seguimiento y asigna una cuenta principal de referencia.
        </p>
      </div>

      <Button
        label="Nueva campaña"
        icon="pi pi-plus"
        @click="openCreate"
      />
    </div>

    <section class="section-card">
      <div class="campaign-toolbar">
        <div>
          <h3>Listado de campañas</h3>
          <p>Administra campañas activas, pausadas o en borrador.</p>
        </div>

        <IconField>
          <InputIcon class="pi pi-search" />
          <InputText
            v-model="search"
            placeholder="Buscar campaña..."
          />
        </IconField>
      </div>

      <DataTable
        :value="filteredItems"
        :loading="loading"
        dataKey="id"
        paginator
        :rows="10"
        stripedRows
        responsiveLayout="scroll"
      >
        <Column field="id" header="ID" style="width: 90px" sortable />

        <Column field="name" header="Nombre" sortable>
          <template #body="{ data }">
            <div class="campaign-name-cell">
              <strong>{{ data.name }}</strong>
              <small>{{ data.owner_instagram_profile_url || "Sin perfil owner configurado" }}</small>
            </div>
          </template>
        </Column>

        <Column field="platform" header="Plataforma" sortable>
          <template #body="{ data }">
            <Tag
              :value="formatPlatform(data.platform)"
              severity="info"
            />
          </template>
        </Column>

        <Column field="status" header="Estado">
          <template #body="{ data }">
            <Tag
              :value="formatStatus(data.status)"
              :severity="statusSeverity(data.status)"
            />
          </template>
        </Column>

        <Column field="follow_up_phone" header="Teléfono">
          <template #body="{ data }">
            {{ data.follow_up_phone || "-" }}
          </template>
        </Column>

        <Column field="follow_up_email" header="Email">
          <template #body="{ data }">
            {{ data.follow_up_email || "-" }}
          </template>
        </Column>

        <Column header="Acciones" style="width: 220px">
          <template #body="{ data }">
            <div class="table-actions">
              <Button
                icon="pi pi-eye"
                rounded
                outlined
                severity="success"
                v-tooltip.top="'Ver detalle'"
                @click="$router.push(`/campaigns/${data.id}`)"
              />

              <Button
                icon="pi pi-pencil"
                rounded
                outlined
                severity="info"
                v-tooltip.top="'Editar'"
                @click="openEdit(data)"
              />

              <Button
                icon="pi pi-trash"
                rounded
                outlined
                severity="danger"
                v-tooltip.top="'Eliminar'"
                @click="confirmRemove(data)"
              />
            </div>
          </template>
        </Column>

        <template #empty>
          <div class="empty-state">
            No hay campañas registradas.
          </div>
        </template>
      </DataTable>
    </section>

    <Dialog
      v-model:visible="showDialog"
      modal
      :header="form.id ? 'Editar campaña' : 'Nueva campaña'"
      style="width: 1040px; max-width: 96vw"
      contentStyle="padding: 0"
      :draggable="false"
    >
      <div class="campaign-modal">
        <div class="modal-intro">
          <div>
            <h3>{{ form.id ? "Actualizar campaña" : "Configurar nueva campaña" }}</h3>
            <p>
              La cuenta principal es requerida por el backend. Luego puedes asignar varias cuentas reales desde el detalle de la campaña.
            </p>
          </div>

          <Tag
            :value="formatStatus(form.status)"
            :severity="statusSeverity(form.status)"
          />
        </div>

        <div class="modal-section">
          <div class="modal-section-title">
            <i class="pi pi-info-circle"></i>
            <div>
              <h4>Información principal</h4>
              <p>Datos base de la campaña y estado operativo.</p>
            </div>
          </div>

          <div class="form-grid">
            <div class="form-field full">
              <label>Nombre de la campaña</label>
              <InputText
                v-model="form.name"
                placeholder="Ej: Prospección Amarres Chicago"
              />
            </div>

            <div class="form-field">
              <label>Plataforma</label>
              <Select
                v-model="form.platform"
                :options="platformOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Seleccionar plataforma"
              />
            </div>

            <div class="form-field">
              <label>Estado</label>
              <Select
                v-model="form.status"
                :options="statusOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Seleccionar estado"
              />
            </div>

            <div class="form-field full">
              <label>Cuenta principal de referencia</label>
              <Select
                v-model="form.social_media_account"
                :options="accounts"
                optionLabel="account_name"
                optionValue="id"
                placeholder="Seleccionar cuenta principal"
                filter
              />

              <small class="field-help">
                Esta cuenta mantiene compatibilidad con el backend. Las cuentas operativas se asignan después desde el detalle de campaña.
              </small>
            </div>
          </div>
        </div>

        <div class="modal-section">
          <div class="modal-section-title">
            <i class="pi pi-send"></i>
            <div>
              <h4>Seguimiento y contacto</h4>
              <p>Datos usados cuando el bot detecta interés o genera alerta.</p>
            </div>
          </div>

          <div class="form-grid">
            <div class="form-field">
              <label>Teléfono de seguimiento</label>
              <InputText
                v-model="form.follow_up_phone"
                placeholder="Ej: +1 773 000 0000"
              />
            </div>

            <div class="form-field">
              <label>Email de seguimiento</label>
              <InputText
                v-model="form.follow_up_email"
                placeholder="Ej: contacto@dominio.com"
              />
            </div>

            <div class="form-field full">
              <label>Perfil de Instagram del owner</label>
              <InputText
                v-model="form.owner_instagram_profile_url"
                placeholder="https://www.instagram.com/usuario/"
              />
            </div>
          </div>
        </div>

        <div class="modal-section">
          <div class="modal-section-title">
            <i class="pi pi-code"></i>
            <div>
              <h4>Configuración avanzada JSON</h4>
              <p>Define servicios y estrategia usados por el bot.</p>
            </div>
          </div>

          <div class="json-grid">
            <div class="json-card">
              <div class="json-card-header">
                <div>
                  <strong>Servicios</strong>
                  <small>Debe ser un array JSON</small>
                </div>

                <Button
                  label="Formatear"
                  size="small"
                  severity="secondary"
                  outlined
                  @click="formatServicesJson"
                />
              </div>

              <Textarea
                v-model="servicesRaw"
                rows="9"
                autoResize
                class="json-textarea"
                placeholder='[{"name": "Amarres de amor", "description": "Servicio principal"}]'
              />
            </div>

            <div class="json-card">
              <div class="json-card-header">
                <div>
                  <strong>Estrategia</strong>
                  <small>Debe ser un objeto JSON</small>
                </div>

                <Button
                  label="Formatear"
                  size="small"
                  severity="secondary"
                  outlined
                  @click="formatStrategyJson"
                />
              </div>

              <Textarea
                v-model="strategyRaw"
                rows="9"
                autoResize
                class="json-textarea"
                placeholder='{"target": "prospectos interesados", "tone": "natural"}'
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <Button
            label="Cancelar"
            severity="secondary"
            outlined
            @click="showDialog = false"
          />

          <Button
            label="Guardar campaña"
            icon="pi pi-save"
            :loading="saving"
            @click="save"
          />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useToast } from "primevue/usetoast";
import { useConfirm } from "primevue/useconfirm";

import Button from "primevue/button";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Dialog from "primevue/dialog";
import InputText from "primevue/inputtext";
import Textarea from "primevue/textarea";
import Select from "primevue/select";
import Tag from "primevue/tag";
import IconField from "primevue/iconfield";
import InputIcon from "primevue/inputicon";

import { campaignsApi } from "../api/campaigns.api";
import { socialAccountsApi } from "../api/socialAccounts.api";
import { normalizeList } from "../api/http";

const toast = useToast();
const confirm = useConfirm();

const items = ref([]);
const accounts = ref([]);
const loading = ref(false);
const saving = ref(false);
const showDialog = ref(false);
const search = ref("");

const servicesRaw = ref("[]");
const strategyRaw = ref("{}");

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

function getEmptyForm() {
  return {
    id: null,
    social_media_account: null,
    name: "",
    platform: "instagram",
    status: "draft",
    services_snapshot: [],
    strategy_snapshot: {},
    follow_up_phone: "",
    follow_up_email: "",
    owner_instagram_profile_url: "",
  };
}

const form = reactive(getEmptyForm());

const filteredItems = computed(() => {
  const term = search.value.trim().toLowerCase();

  if (!term) return items.value;

  return items.value.filter((item) => {
    const values = [
      item.id,
      item.name,
      item.platform,
      item.status,
      item.follow_up_phone,
      item.follow_up_email,
      item.owner_instagram_profile_url,
    ];

    return values.some((value) =>
      String(value || "").toLowerCase().includes(term)
    );
  });
});

function resetForm() {
  Object.assign(form, getEmptyForm());
  servicesRaw.value = "[]";
  strategyRaw.value = "{}";
}

function statusSeverity(status) {
  if (status === "active") return "success";
  if (status === "paused") return "warn";
  if (status === "completed") return "info";
  if (status === "cancelled") return "danger";
  return "secondary";
}

function formatStatus(status) {
  const map = {
    draft: "Borrador",
    active: "Activa",
    paused: "Pausada",
    completed: "Completada",
    cancelled: "Cancelada",
  };

  return map[status] || status || "-";
}

function formatPlatform(platform) {
  const map = {
    instagram: "Instagram",
    facebook: "Facebook",
  };

  return map[platform] || platform || "-";
}

function parseJsonOrThrow(rawValue, fallback, expectedType) {
  const value = JSON.parse(rawValue || JSON.stringify(fallback));

  if (expectedType === "array" && !Array.isArray(value)) {
    throw new Error("INVALID_ARRAY");
  }

  if (
    expectedType === "object" &&
    (Array.isArray(value) || value === null || typeof value !== "object")
  ) {
    throw new Error("INVALID_OBJECT");
  }

  return value;
}

function formatServicesJson() {
  try {
    const parsed = parseJsonOrThrow(servicesRaw.value, [], "array");
    servicesRaw.value = JSON.stringify(parsed, null, 2);
  } catch {
    toast.add({
      severity: "warn",
      summary: "JSON inválido",
      detail: "Servicios debe ser un array JSON válido.",
      life: 3500,
    });
  }
}

function formatStrategyJson() {
  try {
    const parsed = parseJsonOrThrow(strategyRaw.value, {}, "object");
    strategyRaw.value = JSON.stringify(parsed, null, 2);
  } catch {
    toast.add({
      severity: "warn",
      summary: "JSON inválido",
      detail: "Estrategia debe ser un objeto JSON válido.",
      life: 3500,
    });
  }
}

async function loadItems() {
  loading.value = true;

  try {
    const response = await campaignsApi.list();
    items.value = normalizeList(response.data);
  } catch {
    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudieron cargar las campañas.",
      life: 3000,
    });
  } finally {
    loading.value = false;
  }
}

async function loadAccounts() {
  try {
    const response = await socialAccountsApi.list();
    accounts.value = normalizeList(response.data);
  } catch {
    accounts.value = [];

    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudieron cargar las cuentas sociales.",
      life: 3000,
    });
  }
}

function openCreate() {
  resetForm();

  if (accounts.value.length === 1) {
    form.social_media_account = accounts.value[0].id;
  }

  showDialog.value = true;
}

function openEdit(item) {
  resetForm();

  Object.assign(form, {
    ...item,
    social_media_account:
      typeof item.social_media_account === "object"
        ? item.social_media_account?.id
        : item.social_media_account,
  });

  servicesRaw.value = JSON.stringify(item.services_snapshot || [], null, 2);
  strategyRaw.value = JSON.stringify(item.strategy_snapshot || {}, null, 2);
  showDialog.value = true;
}

async function save() {
  if (!form.name || !String(form.name).trim()) {
    toast.add({
      severity: "warn",
      summary: "Validación",
      detail: "El nombre de la campaña es obligatorio.",
      life: 3000,
    });
    return;
  }

  if (!form.social_media_account) {
    toast.add({
      severity: "warn",
      summary: "Validación",
      detail: "La cuenta principal de referencia es obligatoria.",
      life: 3000,
    });
    return;
  }

  saving.value = true;

  try {
    const servicesSnapshot = parseJsonOrThrow(servicesRaw.value, [], "array");
    const strategySnapshot = parseJsonOrThrow(strategyRaw.value, {}, "object");

    /*
      Payload limpio:
      No mandamos created_at, updated_at ni campos extra que vengan del backend.
    */
    const payload = {
      social_media_account: Number(form.social_media_account),
      name: String(form.name).trim(),
      platform: form.platform,
      status: form.status,
      services_snapshot: servicesSnapshot,
      strategy_snapshot: strategySnapshot,
      follow_up_phone: form.follow_up_phone || null,
      follow_up_email: form.follow_up_email || null,
      owner_instagram_profile_url: form.owner_instagram_profile_url || null,
    };

    console.log("PAYLOAD CAMPAIGN:", payload);

    if (form.id) {
      await campaignsApi.update(form.id, payload);
    } else {
      await campaignsApi.create(payload);
    }

    toast.add({
      severity: "success",
      summary: "Guardado",
      detail: "Campaña guardada correctamente.",
      life: 2500,
    });

    showDialog.value = false;
    await loadItems();
  } catch (error) {
    console.error("ERROR GUARDANDO CAMPAÑA:", error.response?.data || error);

    let detail = "No se pudo guardar la campaña. Revisa los campos.";

    if (error.message === "INVALID_ARRAY") {
      detail = "Servicios debe ser un array JSON válido.";
    } else if (error.message === "INVALID_OBJECT") {
      detail = "Estrategia debe ser un objeto JSON válido.";
    } else if (error.response?.data) {
      detail = JSON.stringify(error.response.data);
    }

    toast.add({
      severity: "error",
      summary: "Error",
      detail,
      life: 7000,
    });
  } finally {
    saving.value = false;
  }
}

function confirmRemove(item) {
  confirm.require({
    message: `¿Eliminar la campaña "${item.name}"?`,
    header: "Confirmar eliminación",
    icon: "pi pi-exclamation-triangle",
    acceptLabel: "Eliminar",
    rejectLabel: "Cancelar",
    acceptClass: "p-button-danger",
    accept: async () => {
      try {
        await campaignsApi.remove(item.id);

        toast.add({
          severity: "success",
          summary: "Eliminada",
          detail: "Campaña eliminada correctamente.",
          life: 2500,
        });

        await loadItems();
      } catch {
        toast.add({
          severity: "error",
          summary: "Error",
          detail: "No se pudo eliminar la campaña.",
          life: 3000,
        });
      }
    },
  });
}

onMounted(async () => {
  await Promise.all([loadAccounts(), loadItems()]);
});
</script>

<style scoped>
.campaign-toolbar {
  padding: 18px 20px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
}

.campaign-toolbar h3 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.campaign-toolbar p {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 13px;
}

.campaign-name-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.campaign-name-cell strong {
  color: #0f172a;
}

.campaign-name-cell small {
  color: #64748b;
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.campaign-modal {
  background: #f8fafc;
  padding: 22px;
  display: grid;
  gap: 18px;
}

.modal-intro {
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 35%),
    #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 18px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.modal-intro h3 {
  margin: 0;
  font-size: 20px;
  letter-spacing: -0.03em;
  color: #0f172a;
}

.modal-intro p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.5;
}

.modal-section {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
}

.modal-section-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
}

.modal-section-title i {
  width: 38px;
  height: 38px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #dbeafe;
  color: #2563eb;
  font-size: 17px;
  flex-shrink: 0;
}

.modal-section-title h4 {
  margin: 0;
  color: #0f172a;
  font-size: 16px;
}

.modal-section-title p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.field-help {
  display: block;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

.json-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.json-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  overflow: hidden;
  background: #f8fafc;
}

.json-card-header {
  padding: 13px 14px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.json-card-header strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
}

.json-card-header small {
  color: #64748b;
  font-size: 12px;
}

.json-textarea {
  width: 100%;
  border: 0;
  border-radius: 0;
  font-family: Consolas, Monaco, "Courier New", monospace;
  font-size: 13px;
  background: #0f172a;
  color: #e5e7eb;
}

.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.table-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

:deep(.p-dialog-footer) {
  border-top: 1px solid #e5e7eb;
  padding: 16px 22px;
}

:deep(.p-dialog-header) {
  border-bottom: 1px solid #e5e7eb;
}

:deep(.p-inputtext),
:deep(.p-select) {
  width: 100%;
}

@media (max-width: 900px) {
  .campaign-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .json-grid {
    grid-template-columns: 1fr;
  }

  .modal-intro {
    flex-direction: column;
  }
}
</style>