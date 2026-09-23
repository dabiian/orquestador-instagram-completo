<template>
  <div class="accounts-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">Configuración</p>
        <h1 class="page-title">Cuentas Sociales</h1>
        <p class="page-subtitle">
          Administra cuentas de Instagram, tipo de cuenta y campaña de prospección relacionada.
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
          label="Nueva cuenta"
          icon="pi pi-plus"
          @click="openCreate"
        />
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span>Total cuentas</span>
        <strong>{{ accounts.length }}</strong>
      </div>

      <div class="stat-card">
        <span>Personal</span>
        <strong>{{ countAccountKind('personal') }}</strong>
      </div>

      <div class="stat-card">
        <span>Business</span>
        <strong>{{ countAccountKind('business') }}</strong>
      </div>

      <div class="stat-card">
        <span>Con campaña</span>
        <strong>{{ accountsWithCampaign }}</strong>
      </div>

      <div class="stat-card">
        <span>Con proxy</span>
        <strong>{{ accountsWithProxy }}</strong>
      </div>

      <div class="stat-card">
        <span>Con cookies</span>
        <strong>{{ accountsWithCookies }}</strong>
      </div>
    </div>

    <Card class="section-card">
      <template #title>
        Listado de cuentas
      </template>

      <template #content>
        <DataTable
          :value="accounts"
          :loading="loading"
          dataKey="id"
          paginator
          :rows="12"
          responsiveLayout="scroll"
          stripedRows
          showGridlines
          emptyMessage="No hay cuentas sociales registradas."
        >
          <Column field="id" header="ID" style="width: 85px">
            <template #body="{ data }">
              <strong>#{{ data.id }}</strong>
            </template>
          </Column>

          <Column header="Cuenta">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ data.account_name || "Sin nombre" }}</strong>
                <small>{{ getAccountKindLabel(data.account_kind) }}</small>
              </div>
            </template>
          </Column>

          <Column header="Campaña">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ getAssignedCampaignName(data.id) }}</strong>
                <small v-if="getAssignedCampaignMeta(data.id)">
                  {{ getAssignedCampaignMeta(data.id) }}
                </small>
              </div>
            </template>
          </Column>

          <Column header="Plataforma">
            <template #body="{ data }">
              {{ getPlatformLabel(data) }}
            </template>
          </Column>

          <Column header="Proxy">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ getProxyLabel(data) }}</strong>
                <small v-if="getProxySecondary(data)">
                  {{ getProxySecondary(data) }}
                </small>
              </div>
            </template>
          </Column>

          <Column header="Personalidad">
            <template #body="{ data }">
              {{ getPersonalityLabel(data) }}
            </template>
          </Column>

          <Column header="Cookies" style="width: 110px">
            <template #body="{ data }">
              <Tag
                :value="hasCookies(data) ? 'Sí' : 'No'"
                :severity="hasCookies(data) ? 'success' : 'warning'"
              />
            </template>
          </Column>

          <Column header="Credenciales" style="width: 120px">
            <template #body="{ data }">
              <Button
                icon="pi pi-key"
                text
                rounded
                severity="secondary"
                @click="openJsonDialog('Credenciales', data.other_credentials)"
              />
            </template>
          </Column>

          <Column header="Acciones" style="width: 190px">
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
                  icon="pi pi-cookie"
                  text
                  rounded
                  severity="secondary"
                  @click="openCookieDialog(data)"
                />

                <Button
                  icon="pi pi-trash"
                  text
                  rounded
                  severity="danger"
                  @click="deleteAccount(data)"
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
      :header="isEditing ? 'Editar cuenta social' : 'Nueva cuenta social'"
      :style="{ width: '900px', maxWidth: '96vw' }"
    >
      <div class="form-grid">
        <div class="form-field">
          <label>Nombre de cuenta</label>
          <InputText
            v-model="form.account_name"
            placeholder="Ej: bot_instagram_01"
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Tipo de cuenta</label>
          <Dropdown
            v-model="form.account_kind"
            :options="accountKindOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Selecciona tipo"
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Plataforma</label>
          <Dropdown
            v-model="form.platform"
            :options="platforms"
            optionLabel="label"
            optionValue="id"
            placeholder="Selecciona plataforma"
            filter
            showClear
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Proxy</label>
          <Dropdown
            v-model="form.proxy"
            :options="proxies"
            optionLabel="label"
            optionValue="id"
            placeholder="Selecciona proxy"
            filter
            showClear
            class="w-full"
          />
        </div>

        <div class="form-field full">
          <label>Personalidad</label>
          <Dropdown
            v-model="form.bot_personality"
            :options="personalities"
            optionLabel="label"
            optionValue="id"
            placeholder="Selecciona personalidad"
            filter
            showClear
            class="w-full"
          />
        </div>

        <div class="form-field full">
          <label>Campaña de prospección</label>
          <Dropdown
            v-model="form.prospecting_campaign_id"
            :options="campaigns"
            optionLabel="label"
            optionValue="id"
            placeholder="Selecciona campaña"
            filter
            showClear
            class="w-full"
          />
          <small>
            Esta relación se guarda en prospecting_campaign_accounts.
          </small>
        </div>

        <div class="form-field">
          <label>Rol en campaña</label>
          <Dropdown
            v-model="form.campaign_role"
            :options="campaignRoleOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Estado en campaña</label>
          <Dropdown
            v-model="form.campaign_is_active"
            :options="activeOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Límite diario</label>
          <InputNumber
            v-model="form.daily_limit"
            :min="0"
            showButtons
            class="w-full"
          />
        </div>

        <div class="form-field">
          <label>Límite total</label>
          <InputNumber
            v-model="form.total_limit"
            :min="0"
            showButtons
            class="w-full"
          />
        </div>

        <div class="form-field full">
          <label>Credenciales / other_credentials</label>
          <Textarea
            v-model="form.other_credentials_raw"
            rows="9"
            autoResize
            class="json-input w-full"
          />

          <small>
            JSON válido. Ejemplo: {"User":"usuario","password":"clave","cookie":[]}
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
          :label="isEditing ? 'Guardar cambios' : 'Crear cuenta'"
          icon="pi pi-save"
          :loading="saving"
          @click="saveAccount"
        />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="cookieDialogVisible"
      modal
      header="Actualizar cookies"
      :style="{ width: '760px', maxWidth: '96vw' }"
    >
      <p class="dialog-help">
        Pega aquí el array de cookies exportado del navegador.
      </p>

      <Textarea
        v-model="cookieRaw"
        rows="12"
        autoResize
        class="json-input w-full"
        placeholder='[{"name":"sessionid","value":"...","domain":".instagram.com"}]'
      />

      <Message
        v-if="cookieError"
        severity="error"
        class="mt-4"
        :closable="false"
      >
        {{ cookieError }}
      </Message>

      <template #footer>
        <Button
          label="Cancelar"
          severity="secondary"
          outlined
          @click="cookieDialogVisible = false"
        />

        <Button
          label="Actualizar cookies"
          icon="pi pi-cookie"
          :loading="savingCookie"
          @click="saveCookie"
        />
      </template>
    </Dialog>

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
import { computed, onMounted, ref } from "vue";
import { useToast } from "primevue/usetoast";

import Button from "primevue/button";
import Card from "primevue/card";
import Column from "primevue/column";
import DataTable from "primevue/datatable";
import Dialog from "primevue/dialog";
import Dropdown from "primevue/dropdown";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Tag from "primevue/tag";
import Textarea from "primevue/textarea";

import { accountsApi } from "../api/accounts.api";
import { lookupsApi } from "../api/lookups.api";
import { prospectingApi } from "../api/prospecting.api";
import { normalizeList } from "../api/http";

const DEFAULT_OWNER_ID = 4;
const DEFAULT_GROUP_ID = 1;
const DEFAULT_ASSIGNMENT_PLATFORM = "instagram";

const toast = useToast();

const loading = ref(false);
const saving = ref(false);
const savingCookie = ref(false);

const accounts = ref([]);
const proxies = ref([]);
const platforms = ref([]);
const personalities = ref([]);
const campaigns = ref([]);
const campaignAssignments = ref([]);

const formDialogVisible = ref(false);
const cookieDialogVisible = ref(false);
const jsonDialogVisible = ref(false);

const jsonDialogTitle = ref("");
const jsonDialogContent = ref("{}");

const cookieRaw = ref("[]");
const cookieError = ref("");
const selectedAccount = ref(null);

const errorMessage = ref("");
const isEditing = ref(false);

const form = ref(getEmptyForm());

const accountKindOptions = [
  { label: "Personal", value: "personal" },
  { label: "Business", value: "business" },
];

const campaignRoleOptions = [
  { label: "Prospecting", value: "prospecting" },
];

const activeOptions = [
  { label: "Activa", value: true },
  { label: "Inactiva", value: false },
];

const accountsWithProxy = computed(() => {
  return accounts.value.filter((item) => normalizeId(item.proxy)).length;
});

const accountsWithCookies = computed(() => {
  return accounts.value.filter((item) => hasCookies(item)).length;
});

const accountsWithCampaign = computed(() => {
  return accounts.value.filter((item) => getActiveAssignmentByAccountId(item.id)).length;
});

onMounted(() => {
  loadAll();
});

async function loadAll() {
  loading.value = true;

  await Promise.allSettled([
    loadAccounts(),
    loadLookups(),
    loadCampaignAssignments(),
  ]);

  loading.value = false;
}

async function loadAccounts() {
  const response = await accountsApi.list();
  accounts.value = normalizeList(response.data);
}

async function loadCampaignAssignments() {
  const response = await prospectingApi.listCampaignAccounts();
  campaignAssignments.value = normalizeList(response.data);
}

async function loadLookups() {
  const [
    proxiesResponse,
    platformsResponse,
    personalitiesResponse,
    campaignsResponse,
  ] = await Promise.allSettled([
    lookupsApi.proxies(),
    lookupsApi.platforms(),
    lookupsApi.botPersonalities(),
    lookupsApi.prospectingCampaigns({ platform: DEFAULT_ASSIGNMENT_PLATFORM }),
  ]);

  if (proxiesResponse.status === "fulfilled") {
    proxies.value = normalizeList(proxiesResponse.value.data).map((item) => ({
      ...item,
      label: buildProxyOptionLabel(item),
    }));
  }

  if (platformsResponse.status === "fulfilled") {
    platforms.value = normalizeList(platformsResponse.value.data).map((item) => ({
      ...item,
      label: buildLookupLabel(item, [
        "platform_name",
        "name",
        "social_media_name",
      ]),
    }));
  }

  if (personalitiesResponse.status === "fulfilled") {
    personalities.value = normalizeList(personalitiesResponse.value.data).map((item) => ({
      ...item,
      label: buildLookupLabel(item, [
        "name",
        "personality_name",
        "bot_name",
        "title",
      ]),
    }));
  }

  if (campaignsResponse.status === "fulfilled") {
    campaigns.value = normalizeList(campaignsResponse.value.data).map((item) => ({
      ...item,
      label: buildCampaignLabel(item),
    }));
  }
}

function openCreate() {
  isEditing.value = false;
  selectedAccount.value = null;
  errorMessage.value = "";
  form.value = getEmptyForm();
  formDialogVisible.value = true;
}

function openEdit(row) {
  isEditing.value = true;
  selectedAccount.value = row;
  errorMessage.value = "";

  const assignment = getActiveAssignmentByAccountId(row.id);

  form.value = {
    account_name: row.account_name || "",
    account_kind: normalizeAccountKind(row.account_kind),
    platform: normalizeId(row.platform),
    proxy: normalizeId(row.proxy),
    bot_personality: normalizeId(row.bot_personality),
    prospecting_campaign_id: assignment?.campaign || assignment?.campaign_id || null,
    campaign_assignment_id: assignment?.id || null,
    campaign_role: assignment?.role || "prospecting",
    campaign_is_active: assignment?.is_active ?? true,
    daily_limit: normalizeNumberOrNull(assignment?.daily_limit),
    total_limit: normalizeNumberOrNull(assignment?.total_limit),
    other_credentials_raw: prettyJson(
      normalizeCredentials(row.other_credentials)
    ),
  };

  formDialogVisible.value = true;
}

async function saveAccount() {
  errorMessage.value = "";

  if (!form.value.account_name?.trim()) {
    errorMessage.value = "El nombre de la cuenta es obligatorio.";
    return;
  }

  let accountPayload;

  try {
    accountPayload = buildAccountPayload();
  } catch (error) {
    errorMessage.value = error.message;
    return;
  }

  saving.value = true;

  try {
    let accountId = selectedAccount.value?.id || null;

    if (isEditing.value && accountId) {
      await accountsApi.update(accountId, accountPayload);

      toast.add({
        severity: "success",
        summary: "Cuenta actualizada",
        detail: "Los datos de la cuenta fueron guardados.",
        life: 3500,
      });
    } else {
      const response = await accountsApi.create(accountPayload);
      accountId = response.data?.id;

      toast.add({
        severity: "success",
        summary: "Cuenta creada",
        detail: "La cuenta fue creada correctamente.",
        life: 3500,
      });
    }

    if (!accountId) {
      throw new Error("No se pudo obtener el ID de la cuenta guardada.");
    }

    await saveCampaignAssignment(accountId);

    formDialogVisible.value = false;

    await Promise.allSettled([
      loadAccounts(),
      loadCampaignAssignments(),
    ]);
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error guardando cuenta:", backendError || error);

    errorMessage.value = backendError
      ? JSON.stringify(backendError)
      : error.message || "No se pudo guardar la cuenta.";
  } finally {
    saving.value = false;
  }
}

async function saveCampaignAssignment(accountId) {
  const campaignId = form.value.prospecting_campaign_id;

  const currentAssignment =
    form.value.campaign_assignment_id
      ? campaignAssignments.value.find(
          (item) => Number(item.id) === Number(form.value.campaign_assignment_id)
        )
      : getActiveAssignmentByAccountId(accountId);

  if (!campaignId) {
    if (currentAssignment?.id) {
      await prospectingApi.updateCampaignAccount(currentAssignment.id, {
        is_active: false,
      });
    }

    return;
  }

  const payload = {
    campaign: Number(campaignId),
    social_media_account: Number(accountId),
    platform: DEFAULT_ASSIGNMENT_PLATFORM,
    role: form.value.campaign_role || "prospecting",
    is_active: Boolean(form.value.campaign_is_active),
    daily_limit: normalizeLimitForPayload(form.value.daily_limit),
    total_limit: normalizeLimitForPayload(form.value.total_limit),
  };

  if (currentAssignment?.id) {
    await prospectingApi.updateCampaignAccount(currentAssignment.id, payload);
    return;
  }

  await prospectingApi.createCampaignAccount(payload);
}

async function deleteAccount(row) {
  const ok = window.confirm(`¿Eliminar la cuenta "${row.account_name || row.id}"?`);

  if (!ok) return;

  try {
    await accountsApi.remove(row.id);

    toast.add({
      severity: "success",
      summary: "Cuenta eliminada",
      detail: "La cuenta fue eliminada correctamente.",
      life: 3500,
    });

    await Promise.allSettled([
      loadAccounts(),
      loadCampaignAssignments(),
    ]);
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error eliminando cuenta:", backendError || error);

    toast.add({
      severity: "error",
      summary: "Error",
      detail: backendError ? JSON.stringify(backendError) : "No se pudo eliminar.",
      life: 5000,
    });
  }
}

function openCookieDialog(row) {
  selectedAccount.value = row;
  cookieError.value = "";

  const credentials = normalizeCredentials(row.other_credentials);
  const currentCookie = credentials.cookie;

  cookieRaw.value = Array.isArray(currentCookie)
    ? prettyJson(currentCookie)
    : "[]";

  cookieDialogVisible.value = true;
}

async function saveCookie() {
  cookieError.value = "";

  let cookies;

  try {
    cookies = JSON.parse(cookieRaw.value || "[]");
  } catch {
    cookieError.value = "El JSON de cookies no es válido.";
    return;
  }

  if (!Array.isArray(cookies)) {
    cookieError.value = "Las cookies deben ser un array JSON.";
    return;
  }

  if (!selectedAccount.value?.id) {
    cookieError.value = "No hay cuenta seleccionada.";
    return;
  }

  savingCookie.value = true;

  try {
    await accountsApi.updateCookie(selectedAccount.value.id, cookies);

    toast.add({
      severity: "success",
      summary: "Cookies actualizadas",
      detail: "Las cookies fueron guardadas correctamente.",
      life: 3500,
    });

    cookieDialogVisible.value = false;
    await loadAccounts();
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error actualizando cookies:", backendError || error);

    cookieError.value = backendError
      ? JSON.stringify(backendError)
      : "No se pudieron actualizar las cookies.";
  } finally {
    savingCookie.value = false;
  }
}

function buildAccountPayload() {
  const otherCredentials = parseObjectJson(
    form.value.other_credentials_raw,
    "other_credentials debe ser un objeto JSON válido."
  );

  const payload = {
    account_name: form.value.account_name.trim(),
    account_kind: form.value.account_kind || "personal",
    owner: DEFAULT_OWNER_ID,
    group: DEFAULT_GROUP_ID,
    other_credentials: normalizeCredentials(otherCredentials),
  };

  addNullableId(payload, "platform", form.value.platform);
  addNullableId(payload, "proxy", form.value.proxy);
  addNullableId(payload, "bot_personality", form.value.bot_personality);

  return payload;
}

function addNullableId(payload, key, value) {
  if (value !== null && value !== undefined && value !== "") {
    payload[key] = Number(value);
  }
}

function parseObjectJson(raw, message) {
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

function getEmptyForm() {
  return {
    account_name: "",
    account_kind: "personal",
    platform: null,
    proxy: null,
    bot_personality: null,
    prospecting_campaign_id: null,
    campaign_assignment_id: null,
    campaign_role: "prospecting",
    campaign_is_active: true,
    daily_limit: null,
    total_limit: null,
    other_credentials_raw: prettyJson(getDefaultCredentials()),
  };
}

function getDefaultCredentials() {
  return {
    User: "",
    password: "",
    cookie: [],
  };
}

function normalizeCredentials(value) {
  let credentials = value || {};

  if (typeof credentials === "string") {
    try {
      credentials = JSON.parse(credentials);
    } catch {
      credentials = {};
    }
  }

  if (!credentials || Array.isArray(credentials) || typeof credentials !== "object") {
    credentials = {};
  }

  return {
    User: credentials.User || credentials.user || "",
    password: credentials.password || "",
    cookie: Array.isArray(credentials.cookie) ? credentials.cookie : [],
    ...credentials,
  };
}

function normalizeId(value) {
  if (!value) return null;

  if (typeof value === "object") {
    return value.id ?? null;
  }

  return value;
}

function normalizeNumberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeLimitForPayload(value) {
  const normalized = normalizeNumberOrNull(value);

  if (normalized === null) return null;

  return Math.max(0, normalized);
}

function prettyJson(value) {
  try {
    return JSON.stringify(value || {}, null, 2);
  } catch {
    return "{}";
  }
}

function openJsonDialog(title, value) {
  jsonDialogTitle.value = title;
  jsonDialogContent.value = prettyJson(normalizeCredentials(value));
  jsonDialogVisible.value = true;
}

function buildLookupLabel(item, keys) {
  for (const key of keys) {
    if (item?.[key]) return item[key];
  }

  return `Registro #${item.id}`;
}

function buildCampaignLabel(item) {
  const name = item.name || item.campaign_name || `Campaña #${item.id}`;
  const status = item.status ? ` · ${item.status}` : "";
  const platform = item.platform ? ` · ${item.platform}` : "";

  return `${name}${platform}${status}`;
}

function buildProxyOptionLabel(item) {
  const host =
    item.proxy ||
    item.host ||
    item.ip ||
    item.server ||
    `Proxy #${item.id}`;

  const port = item.port ? `:${item.port}` : "";
  const username = item.username || item.user || "";

  return username ? `${host}${port} · ${username}` : `${host}${port}`;
}

function getPlatformLabel(row) {
  if (!row.platform) return "Sin plataforma";

  if (typeof row.platform === "object") {
    return (
      row.platform.platform_name ||
      row.platform.name ||
      row.platform.social_media_name ||
      `Plataforma #${row.platform.id}`
    );
  }

  return `Plataforma #${row.platform}`;
}

function getProxyLabel(row) {
  if (!row.proxy) return "Sin proxy";

  if (typeof row.proxy === "object") {
    return (
      row.proxy.proxy ||
      row.proxy.host ||
      row.proxy.ip ||
      `Proxy #${row.proxy.id}`
    );
  }

  return `Proxy #${row.proxy}`;
}

function getProxySecondary(row) {
  if (!row.proxy || typeof row.proxy !== "object") return "";

  const parts = [
    row.proxy.port ? `Puerto ${row.proxy.port}` : "",
    row.proxy.username || row.proxy.user || "",
  ].filter(Boolean);

  return parts.join(" · ");
}

function getPersonalityLabel(row) {
  if (!row.bot_personality) return "Sin personalidad";

  if (typeof row.bot_personality === "object") {
    return (
      row.bot_personality.name ||
      row.bot_personality.personality_name ||
      row.bot_personality.bot_name ||
      row.bot_personality.title ||
      `Personalidad #${row.bot_personality.id}`
    );
  }

  return `Personalidad #${row.bot_personality}`;
}

function hasCookies(row) {
  const credentials = normalizeCredentials(row.other_credentials);
  return Array.isArray(credentials.cookie) && credentials.cookie.length > 0;
}

function normalizeAccountKind(value) {
  if (!value) return "personal";

  const normalized = String(value).toLowerCase();

  if (normalized.includes("business") || normalized.includes("bussines")) {
    return "business";
  }

  return "personal";
}

function getAccountKindLabel(value) {
  const normalized = normalizeAccountKind(value);

  return normalized === "business" ? "Business" : "Personal";
}

function countAccountKind(kind) {
  return accounts.value.filter(
    (item) => normalizeAccountKind(item.account_kind) === kind
  ).length;
}

function getActiveAssignmentByAccountId(accountId) {
  return campaignAssignments.value.find((item) => {
    const itemAccountId =
      normalizeId(item.social_media_account) ||
      item.social_media_account_id;

    return (
      Number(itemAccountId) === Number(accountId) &&
      item.is_active !== false
    );
  });
}

function getAssignedCampaignName(accountId) {
  const assignment = getActiveAssignmentByAccountId(accountId);

  if (!assignment) return "Sin campaña";

  if (assignment.campaign_name) return assignment.campaign_name;

  const campaignId = normalizeId(assignment.campaign) || assignment.campaign_id;
  const campaign = campaigns.value.find(
    (item) => Number(item.id) === Number(campaignId)
  );

  return campaign?.name || campaign?.campaign_name || `Campaña #${campaignId}`;
}

function getAssignedCampaignMeta(accountId) {
  const assignment = getActiveAssignmentByAccountId(accountId);

  if (!assignment) return "";

  const parts = [
    assignment.role || "",
    assignment.daily_limit ? `Diario: ${assignment.daily_limit}` : "",
    assignment.total_limit ? `Total: ${assignment.total_limit}` : "",
  ].filter(Boolean);

  return parts.join(" · ");
}
</script>

<style scoped>
.accounts-page {
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

.form-field small,
.dialog-help {
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
  max-height: 520px;
  font-size: 0.85rem;
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

@media (max-width: 1000px) {
  .stats-grid,
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .page-header {
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .stats-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>