<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">{{ campaign?.name || `Campaña #${id}` }}</h2>
        <p class="page-subtitle">Administra cuentas asignadas, límites y estado de ejecución.</p>
      </div>

      <Button label="Volver" icon="pi pi-arrow-left" severity="secondary" outlined @click="$router.push('/campaigns')" />
    </div>

    <div class="detail-grid">
      <div class="mini-card">
        <span>Estado</span>
        <Tag :value="campaign?.status || '-'" :severity="statusSeverity(campaign?.status)" />
      </div>

      <div class="mini-card">
        <span>Plataforma</span>
        <strong>{{ campaign?.platform || "-" }}</strong>
      </div>

      <div class="mini-card">
        <span>Teléfono</span>
        <strong>{{ campaign?.follow_up_phone || "-" }}</strong>
      </div>

      <div class="mini-card">
        <span>Email</span>
        <strong>{{ campaign?.follow_up_email || "-" }}</strong>
      </div>
    </div>

    <section class="section-card">
      <div class="section-card-header header-actions">
        <div>
          <h3>Cuentas asignadas</h3>
          <p>Cuentas que pueden ejecutar prospección dentro de esta campaña.</p>
        </div>

        <Button label="Asignar cuenta" icon="pi pi-plus" @click="openAssign" />
      </div>

      <DataTable :value="campaignAccounts" :loading="loadingAccounts" dataKey="id" stripedRows responsiveLayout="scroll">
        <Column field="id" header="ID" style="width: 90px" />
        <Column header="Cuenta">
          <template #body="{ data }">
            {{ data.social_media_account_name || getAccountName(data.social_media_account) }}
          </template>
        </Column>
        <Column field="platform" header="Plataforma" />
        <Column field="role" header="Rol" />
        <Column header="Activa">
          <template #body="{ data }">
            <Tag :value="data.is_active ? 'Activa' : 'Inactiva'" :severity="data.is_active ? 'success' : 'danger'" />
          </template>
        </Column>
        <Column field="daily_limit" header="Límite diario" />
        <Column field="total_limit" header="Límite total" />
        <Column header="Acciones" style="width: 180px">
          <template #body="{ data }">
            <div class="table-actions">
              <Button icon="pi pi-pencil" rounded outlined severity="info" @click="openEditAccount(data)" />
              <Button icon="pi pi-trash" rounded outlined severity="danger" @click="removeCampaignAccount(data)" />
            </div>
          </template>
        </Column>

        <template #empty>
          <div class="empty-state">No hay cuentas asignadas a esta campaña.</div>
        </template>
      </DataTable>
    </section>

    <Dialog v-model:visible="showAssignDialog" modal :header="assignForm.id ? 'Editar asignación' : 'Asignar cuenta'" style="width: 620px; max-width: 95vw">
      <div class="form-grid">
        <div class="form-field full">
          <label>Cuenta social</label>
          <Select
            v-model="assignForm.social_media_account"
            :options="accounts"
            optionLabel="account_name"
            optionValue="id"
            :disabled="Boolean(assignForm.id)"
          />
        </div>

        <div class="form-field">
          <label>Plataforma</label>
          <Select v-model="assignForm.platform" :options="platformOptions" optionLabel="label" optionValue="value" />
        </div>

        <div class="form-field">
          <label>Activa</label>
          <ToggleSwitch v-model="assignForm.is_active" />
        </div>

        <div class="form-field">
          <label>Límite diario</label>
          <InputNumber v-model="assignForm.daily_limit" :min="0" fluid />
        </div>

        <div class="form-field">
          <label>Límite total</label>
          <InputNumber v-model="assignForm.total_limit" :min="0" fluid />
        </div>
      </div>

      <template #footer>
        <Button label="Cancelar" severity="secondary" outlined @click="showAssignDialog = false" />
        <Button label="Guardar" icon="pi pi-save" :loading="savingAssign" @click="saveAssign" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useToast } from "primevue/usetoast";
import { useConfirm } from "primevue/useconfirm";

import Button from "primevue/button";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Dialog from "primevue/dialog";
import Select from "primevue/select";
import InputNumber from "primevue/inputnumber";
import ToggleSwitch from "primevue/toggleswitch";
import Tag from "primevue/tag";

import { campaignsApi } from "../api/campaigns.api";
import { campaignAccountsApi } from "../api/campaignAccounts.api";
import { socialAccountsApi } from "../api/socialAccounts.api";
import { normalizeList } from "../api/http";

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
});

const toast = useToast();
const confirm = useConfirm();

const campaign = ref(null);
const accounts = ref([]);
const campaignAccounts = ref([]);
const loadingAccounts = ref(false);
const savingAssign = ref(false);
const showAssignDialog = ref(false);

const platformOptions = [
  { label: "Instagram", value: "instagram" },
  { label: "Facebook", value: "facebook" },
];

const emptyAssignForm = {
  id: null,
  campaign: Number(props.id),
  social_media_account: null,
  platform: "instagram",
  role: "prospecting",
  is_active: true,
  daily_limit: null,
  total_limit: null,
};

const assignForm = reactive({ ...emptyAssignForm });

function resetAssignForm() {
  Object.assign(assignForm, { ...emptyAssignForm, campaign: Number(props.id) });
}

function statusSeverity(status) {
  if (status === "active") return "success";
  if (status === "paused") return "warn";
  if (status === "completed") return "info";
  if (status === "cancelled") return "danger";
  return "secondary";
}

function getAccountName(id) {
  if (!id) return "-";
  if (typeof id === "object") return id.account_name || id.id;
  const found = accounts.value.find((x) => x.id === id);
  return found?.account_name || id;
}

async function loadCampaign() {
  const response = await campaignsApi.get(props.id);
  campaign.value = response.data;
}

async function loadAccounts() {
  const response = await socialAccountsApi.list();
  accounts.value = normalizeList(response.data);
}

async function loadCampaignAccounts() {
  loadingAccounts.value = true;

  try {
    const response = await campaignAccountsApi.list({
      campaign: props.id,
    });

    campaignAccounts.value = normalizeList(response.data);
  } catch {
    campaignAccounts.value = [];
    toast.add({
      severity: "warn",
      summary: "Endpoint pendiente",
      detail: "No se pudo cargar campaign-accounts. Verifica que el backend tenga esa ruta.",
      life: 5000,
    });
  } finally {
    loadingAccounts.value = false;
  }
}

function openAssign() {
  resetAssignForm();
  assignForm.platform = campaign.value?.platform || "instagram";
  showAssignDialog.value = true;
}

function openEditAccount(item) {
  resetAssignForm();
  Object.assign(assignForm, {
    id: item.id,
    campaign: typeof item.campaign === "object" ? item.campaign.id : item.campaign,
    social_media_account:
      typeof item.social_media_account === "object"
        ? item.social_media_account.id
        : item.social_media_account,
    platform: item.platform || "instagram",
    role: item.role || "prospecting",
    is_active: Boolean(item.is_active),
    daily_limit: item.daily_limit,
    total_limit: item.total_limit,
  });
  showAssignDialog.value = true;
}

async function saveAssign() {
  if (!assignForm.social_media_account) {
    toast.add({
      severity: "warn",
      summary: "Validación",
      detail: "Selecciona una cuenta.",
      life: 3000,
    });
    return;
  }

  savingAssign.value = true;

  try {
    const payload = { ...assignForm };
    delete payload.id;

    if (assignForm.id) {
      await campaignAccountsApi.update(assignForm.id, payload);
    } else {
      await campaignAccountsApi.create(payload);
    }

    toast.add({
      severity: "success",
      summary: "Guardado",
      detail: "Cuenta asignada correctamente.",
      life: 2500,
    });

    showAssignDialog.value = false;
    await loadCampaignAccounts();
  } catch {
    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudo guardar. Puede que la cuenta ya esté asignada.",
      life: 4000,
    });
  } finally {
    savingAssign.value = false;
  }
}

function removeCampaignAccount(item) {
  confirm.require({
    message: "¿Quitar esta cuenta de la campaña?",
    header: "Confirmar",
    icon: "pi pi-exclamation-triangle",
    acceptLabel: "Quitar",
    rejectLabel: "Cancelar",
    acceptClass: "p-button-danger",
    accept: async () => {
      await campaignAccountsApi.remove(item.id);
      await loadCampaignAccounts();
    },
  });
}

onMounted(async () => {
  await Promise.all([loadCampaign(), loadAccounts()]);
  await loadCampaignAccounts();
});
</script>

<style scoped>
.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.mini-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 16px;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
}

.mini-card span {
  display: block;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 7px;
}

.mini-card strong {
  font-size: 16px;
  color: #0f172a;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

@media (max-width: 1100px) {
  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 650px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>