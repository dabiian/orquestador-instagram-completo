<template>
  <div class="proxies-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">Configuración</p>
        <h1 class="page-title">Proxies</h1>
        <p class="page-subtitle">
          Administra los proxies usados por las cuentas y bots de Instagram.
        </p>
      </div>

      <div class="header-actions">
        <Button
          label="Actualizar"
          icon="pi pi-refresh"
          severity="secondary"
          :loading="loading"
          @click="loadProxies"
        />

        <Button
          label="Nuevo proxy"
          icon="pi pi-plus"
          @click="openCreate"
        />
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <span>Total proxies</span>
        <strong>{{ proxies.length }}</strong>
      </div>

      <div class="stat-card">
        <span>Con usuario</span>
        <strong>{{ proxiesWithUsername }}</strong>
      </div>

      <div class="stat-card">
        <span>Con password</span>
        <strong>{{ proxiesWithPassword }}</strong>
      </div>

      <div class="stat-card">
        <span>Sin credenciales</span>
        <strong>{{ proxiesWithoutCredentials }}</strong>
      </div>
    </div>

    <Card class="section-card">
      <template #title>
        Listado de proxies
      </template>

      <template #content>
        <DataTable
          :value="proxies"
          :loading="loading"
          dataKey="id"
          paginator
          :rows="12"
          responsiveLayout="scroll"
          stripedRows
          showGridlines
          emptyMessage="No hay proxies registrados."
        >
          <Column field="id" header="ID" style="width: 85px">
            <template #body="{ data }">
              <strong>#{{ data.id }}</strong>
            </template>
          </Column>

          <Column header="Proxy">
            <template #body="{ data }">
              <div class="main-cell">
                <strong>{{ data.ip_address }}:{{ data.port }}</strong>
                <small>{{ getProxyTypeLabel(data) }}</small>
              </div>
            </template>
          </Column>

          <Column header="IP">
            <template #body="{ data }">
              {{ data.ip_address || "Sin IP" }}
            </template>
          </Column>

          <Column header="Puerto" style="width: 120px">
            <template #body="{ data }">
              <Tag
                :value="data.port || 'Sin puerto'"
                severity="info"
              />
            </template>
          </Column>

          <Column header="Usuario">
            <template #body="{ data }">
              {{ data.username || "Sin usuario" }}
            </template>
          </Column>

          <Column header="Password">
            <template #body="{ data }">
              <span v-if="data.password">
                {{ showPasswords ? data.password : maskPassword(data.password) }}
              </span>
              <span v-else>Sin password</span>
            </template>
          </Column>

          <Column header="Credenciales" style="width: 140px">
            <template #body="{ data }">
              <Tag
                :value="hasCredentials(data) ? 'Completo' : 'Sin auth'"
                :severity="hasCredentials(data) ? 'success' : 'secondary'"
              />
            </template>
          </Column>

          <Column header="JSON" style="width: 100px">
            <template #body="{ data }">
              <Button
                icon="pi pi-code"
                text
                rounded
                severity="secondary"
                @click="openJsonDialog('Detalle del proxy', data)"
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
                  @click="deleteProxy(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>

        <div class="table-footer-actions">
          <Button
            :label="showPasswords ? 'Ocultar passwords' : 'Mostrar passwords'"
            :icon="showPasswords ? 'pi pi-eye-slash' : 'pi pi-eye'"
            severity="secondary"
            outlined
            @click="showPasswords = !showPasswords"
          />
        </div>
      </template>
    </Card>

    <Dialog
      v-model:visible="formDialogVisible"
      modal
      :header="isEditing ? 'Editar proxy' : 'Nuevo proxy'"
      :style="{ width: '620px', maxWidth: '96vw' }"
    >
      <div class="form-grid">
        <div class="form-field full">
          <label>IP del proxy</label>
          <InputText
            v-model="form.ip_address"
            class="w-full"
            placeholder="Ej: 192.168.1.100"
          />
          <small>
            Debe ser una IP válida. Ejemplo: 172.16.0.10 o 45.80.120.33.
          </small>
        </div>

        <div class="form-field full">
          <label>Puerto</label>
          <InputNumber
            v-model="form.port"
            class="w-full"
            inputClass="w-full"
            :useGrouping="false"
            :min="1"
            :max="65535"
            placeholder="Ej: 8000"
          />
          <small>
            Puerto del proxy. Rango válido: 1 a 65535.
          </small>
        </div>

        <div class="form-field">
          <label>Usuario</label>
          <InputText
            v-model="form.username"
            class="w-full"
            placeholder="Opcional"
          />
        </div>

        <div class="form-field">
          <label>Password</label>
          <Password
            v-model="form.password"
            class="w-full"
            inputClass="w-full"
            placeholder="Opcional"
            toggleMask
            :feedback="false"
          />
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
          :label="isEditing ? 'Guardar cambios' : 'Crear proxy'"
          icon="pi pi-save"
          :loading="saving"
          @click="saveProxy"
        />
      </template>
    </Dialog>

    <Dialog
      v-model:visible="jsonDialogVisible"
      modal
      :header="jsonDialogTitle"
      :style="{ width: '720px', maxWidth: '95vw' }"
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
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import Message from "primevue/message";
import Password from "primevue/password";
import Tag from "primevue/tag";

import { proxiesApi } from "../api/proxies.api";
import { normalizeList } from "../api/http";

const toast = useToast();

const loading = ref(false);
const saving = ref(false);

const proxies = ref([]);

const formDialogVisible = ref(false);
const jsonDialogVisible = ref(false);

const jsonDialogTitle = ref("");
const jsonDialogContent = ref("{}");

const selectedProxy = ref(null);
const isEditing = ref(false);
const errorMessage = ref("");
const showPasswords = ref(false);

const form = ref(getEmptyForm());

const proxiesWithUsername = computed(() => {
  return proxies.value.filter((item) => Boolean(item.username)).length;
});

const proxiesWithPassword = computed(() => {
  return proxies.value.filter((item) => Boolean(item.password)).length;
});

const proxiesWithoutCredentials = computed(() => {
  return proxies.value.filter((item) => !item.username && !item.password).length;
});

onMounted(() => {
  loadProxies();
});

async function loadProxies() {
  loading.value = true;

  try {
    const response = await proxiesApi.list();
    proxies.value = normalizeList(response.data);
  } catch (error) {
    console.error("Error cargando proxies:", error.response?.data || error);

    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudieron cargar los proxies.",
      life: 5000,
    });
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  isEditing.value = false;
  selectedProxy.value = null;
  errorMessage.value = "";
  form.value = getEmptyForm();
  formDialogVisible.value = true;
}

function openEdit(row) {
  isEditing.value = true;
  selectedProxy.value = row;
  errorMessage.value = "";

  form.value = {
    ip_address: row.ip_address || "",
    port: row.port ? Number(row.port) : null,
    username: row.username || "",
    password: row.password || "",
  };

  formDialogVisible.value = true;
}

async function saveProxy() {
  errorMessage.value = "";

  let payload;

  try {
    payload = buildPayload();
  } catch (error) {
    errorMessage.value = error.message;
    return;
  }

  saving.value = true;

  try {
    if (isEditing.value && selectedProxy.value?.id) {
      await proxiesApi.update(selectedProxy.value.id, payload);

      toast.add({
        severity: "success",
        summary: "Proxy actualizado",
        detail: "Los cambios fueron guardados correctamente.",
        life: 3500,
      });
    } else {
      await proxiesApi.create(payload);

      toast.add({
        severity: "success",
        summary: "Proxy creado",
        detail: "El proxy fue creado correctamente.",
        life: 3500,
      });
    }

    formDialogVisible.value = false;
    await loadProxies();
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error guardando proxy:", backendError || error);

    errorMessage.value = extractBackendError(
      backendError,
      "No se pudo guardar el proxy."
    );
  } finally {
    saving.value = false;
  }
}

async function deleteProxy(row) {
  const ok = window.confirm(
    `¿Eliminar el proxy ${row.ip_address}:${row.port}?`
  );

  if (!ok) return;

  try {
    await proxiesApi.remove(row.id);

    toast.add({
      severity: "success",
      summary: "Proxy eliminado",
      detail: "El proxy fue eliminado correctamente.",
      life: 3500,
    });

    await loadProxies();
  } catch (error) {
    const backendError = error.response?.data;
    console.error("Error eliminando proxy:", backendError || error);

    toast.add({
      severity: "error",
      summary: "Error",
      detail: extractBackendError(backendError, "No se pudo eliminar el proxy."),
      life: 5000,
    });
  }
}

function buildPayload() {
  const ipAddress = String(form.value.ip_address || "").trim();
  const port = Number(form.value.port);

  if (!ipAddress) {
    throw new Error("La IP del proxy es obligatoria.");
  }

  if (!isValidIp(ipAddress)) {
    throw new Error("La IP del proxy no tiene un formato válido.");
  }

  if (!port || Number.isNaN(port)) {
    throw new Error("El puerto del proxy es obligatorio.");
  }

  if (port < 1 || port > 65535) {
    throw new Error("El puerto debe estar entre 1 y 65535.");
  }

  return {
    ip_address: ipAddress,
    port,
    username: form.value.username?.trim() || null,
    password: form.value.password?.trim() || null,
  };
}

function getEmptyForm() {
  return {
    ip_address: "",
    port: null,
    username: "",
    password: "",
  };
}

function hasCredentials(row) {
  return Boolean(row.username && row.password);
}

function getProxyTypeLabel(row) {
  if (row.username && row.password) {
    return "Proxy con autenticación";
  }

  return "Proxy sin autenticación";
}

function maskPassword(value) {
  const text = String(value || "");

  if (!text) return "";

  if (text.length <= 4) return "••••";

  return `${text.slice(0, 2)}${"•".repeat(Math.max(4, text.length - 4))}${text.slice(-2)}`;
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

function extractBackendError(backendError, fallback) {
  if (!backendError) return fallback;

  if (typeof backendError === "string") {
    return backendError.length > 300
      ? "El backend devolvió un error HTML. Revisa los logs del backend."
      : backendError;
  }

  if (backendError.detail) {
    return backendError.detail;
  }

  const firstKey = Object.keys(backendError)[0];

  if (firstKey && Array.isArray(backendError[firstKey])) {
    return `${firstKey}: ${backendError[firstKey].join(", ")}`;
  }

  return JSON.stringify(backendError);
}

function isValidIp(value) {
  const text = String(value || "").trim();

  const ipv4Regex =
    /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

  const ipv6Regex =
    /^(([0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}|::1|::)$/;

  return ipv4Regex.test(text) || ipv6Regex.test(text);
}
</script>

<style scoped>
.proxies-page {
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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

.table-footer-actions {
  margin-top: 1rem;
  display: flex;
  justify-content: flex-end;
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

.json-box {
  margin: 0;
  background: #0f172a;
  color: #e5e7eb;
  padding: 1rem;
  border-radius: 14px;
  overflow: auto;
  max-height: 560px;
  font-size: 0.85rem;
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

.mb-4 {
  margin-bottom: 1rem;
}

.mt-4 {
  margin-top: 1rem;
}

.w-full {
  width: 100%;
}

@media (max-width: 1100px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 800px) {
  .page-header {
    flex-direction: column;
  }

  .stats-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>