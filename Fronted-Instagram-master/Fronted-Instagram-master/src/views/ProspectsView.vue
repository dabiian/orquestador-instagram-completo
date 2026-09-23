<template>
  <div>
    <div class="page-header">
      <div>
        <h2 class="page-title">Prospectos</h2>
        <p class="page-subtitle">Prospectos encontrados por campañas de prospección.</p>
      </div>

      <Button label="Recargar" icon="pi pi-refresh" severity="secondary" outlined @click="loadItems" />
    </div>

    <section class="section-card">
      <DataTable
        :value="items"
        :loading="loading"
        dataKey="id"
        paginator
        :rows="10"
        stripedRows
        responsiveLayout="scroll"
        v-model:filters="filters"
        filterDisplay="row"
      >
        <Column field="id" header="ID" style="width: 90px" sortable />
        <Column field="username" header="Usuario" sortable>
          <template #body="{ data }">
            <a v-if="data.profile_url" :href="data.profile_url" target="_blank" class="profile-link">
              {{ data.username }}
            </a>
            <span v-else>{{ data.username }}</span>
          </template>
        </Column>
        <Column field="platform" header="Plataforma" sortable />
        <Column field="status" header="Estado">
          <template #body="{ data }">
            <Tag :value="data.status" :severity="statusSeverity(data.status)" />
          </template>
        </Column>
        <Column field="industry_detected" header="Industria" />
        <Column field="qualification_score" header="Score" sortable />
        <Column field="source_type" header="Fuente" />
        <Column field="source_value" header="Valor fuente" />
        <Column header="Acciones" style="width: 120px">
          <template #body="{ data }">
            <Button icon="pi pi-eye" rounded outlined severity="info" @click="openDetail(data)" />
          </template>
        </Column>

        <template #empty>
          <div class="empty-state">No hay prospectos registrados.</div>
        </template>
      </DataTable>
    </section>

    <Dialog v-model:visible="showDetail" modal header="Detalle de prospecto" style="width: 960px; max-width: 95vw">
      <div v-if="selectedProspect" class="prospect-detail">
        <div class="detail-header">
          <div>
            <h3>{{ selectedProspect.username }}</h3>
            <p>{{ selectedProspect.display_name || "-" }}</p>
          </div>

          <Tag :value="selectedProspect.status" :severity="statusSeverity(selectedProspect.status)" />
        </div>

        <div class="detail-grid">
          <div>
            <span>Plataforma</span>
            <strong>{{ selectedProspect.platform }}</strong>
          </div>
          <div>
            <span>Industria</span>
            <strong>{{ selectedProspect.industry_detected || "-" }}</strong>
          </div>
          <div>
            <span>Score</span>
            <strong>{{ selectedProspect.qualification_score }}</strong>
          </div>
          <div>
            <span>Fuente</span>
            <strong>{{ selectedProspect.source_type }} / {{ selectedProspect.source_value || "-" }}</strong>
          </div>
        </div>

        <div class="bio-box">
          <strong>Bio</strong>
          <p>{{ selectedProspect.bio || "-" }}</p>
        </div>

        <div class="bio-box">
          <strong>Razón de calificación</strong>
          <p>{{ selectedProspect.qualification_reason || "-" }}</p>
        </div>

        <div class="detail-actions">
          <Button label="Calificado" severity="info" outlined @click="changeStatus('qualified')" />
          <Button label="Engaged" severity="success" outlined @click="changeStatus('engaged')" />
          <Button label="Interesado" severity="success" @click="changeStatus('interested')" />
          <Button label="Descartar" severity="danger" outlined @click="changeStatus('discarded')" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useToast } from "primevue/usetoast";
import { FilterMatchMode } from "@primevue/core/api";

import Button from "primevue/button";
import DataTable from "primevue/datatable";
import Column from "primevue/column";
import Dialog from "primevue/dialog";
import Tag from "primevue/tag";

import { prospectsApi } from "../api/prospects.api";
import { normalizeList } from "../api/http";

const toast = useToast();

const items = ref([]);
const loading = ref(false);
const showDetail = ref(false);
const selectedProspect = ref(null);

const filters = ref({
  username: { value: null, matchMode: FilterMatchMode.CONTAINS },
});

function statusSeverity(status) {
  if (status === "interested" || status === "qualified" || status === "engaged") return "success";
  if (status === "new") return "info";
  if (status === "discarded" || status === "closed") return "danger";
  return "secondary";
}

async function loadItems() {
  loading.value = true;

  try {
    const response = await prospectsApi.list();
    items.value = normalizeList(response.data);
  } catch {
    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudieron cargar los prospectos.",
      life: 3000,
    });
  } finally {
    loading.value = false;
  }
}

function openDetail(item) {
  selectedProspect.value = item;
  showDetail.value = true;
}

async function changeStatus(status) {
  if (!selectedProspect.value) return;

  try {
    await prospectsApi.update(selectedProspect.value.id, { status });

    toast.add({
      severity: "success",
      summary: "Actualizado",
      detail: `Prospecto marcado como ${status}.`,
      life: 2500,
    });

    showDetail.value = false;
    await loadItems();
  } catch {
    toast.add({
      severity: "error",
      summary: "Error",
      detail: "No se pudo actualizar el prospecto.",
      life: 3000,
    });
  }
}

onMounted(loadItems);
</script>

<style scoped>
.profile-link {
  color: #2563eb;
  font-weight: 800;
  text-decoration: none;
}

.profile-link:hover {
  text-decoration: underline;
}

.prospect-detail {
  display: grid;
  gap: 18px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.detail-header h3 {
  margin: 0;
  color: #0f172a;
}

.detail-header p {
  margin: 4px 0 0;
  color: #64748b;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.detail-grid div,
.bio-box {
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  border-radius: 16px;
  padding: 14px;
}

.detail-grid span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 6px;
}

.detail-grid strong {
  color: #0f172a;
}

.bio-box strong {
  display: block;
  margin-bottom: 8px;
}

.bio-box p {
  margin: 0;
  color: #334155;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>