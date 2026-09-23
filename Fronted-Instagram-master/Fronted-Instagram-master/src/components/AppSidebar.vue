<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-icon">
        <i class="pi pi-instagram"></i>
      </div>

      <div>
        <div class="brand-title">Instagram Bot</div>
        <div class="brand-subtitle">Prospecting CRM</div>
      </div>
    </div>

    <div class="menu-section">Operación</div>

      <nav class="menu">
        <router-link to="/">
          <i class="pi pi-chart-line"></i>
          <span>Dashboard</span>
        </router-link>

        <router-link to="/connections">
          <i class="pi pi-server"></i>
          <span>Máquinas</span>
        </router-link>

        <router-link to="/campaigns">
          <i class="pi pi-bullseye"></i>
          <span>Campañas</span>
        </router-link>

        <router-link to="/tasks/create">
          <i class="pi pi-plus-circle"></i>
          <span>Crear tareas</span>
        </router-link>

        <router-link to="/tasks/list">
          <i class="pi pi-list-check"></i>
          <span>Mis tareas</span>
        </router-link>

        <a v-if="orchestratorUrl" :href="orchestratorUrl" target="_blank" rel="noopener noreferrer">
          <i class="pi pi-play-circle"></i>
          <span>Ejecuciones orquestadas ↗</span>
        </a>

        <router-link to="/prospecting-campaigns">
          <i class="pi pi-bullseye"></i>
          <span>Campañas</span>
        </router-link>

        <router-link to="/prospects">
          <i class="pi pi-users"></i>
          <span>Prospectos</span>
        </router-link>
        
        <router-link to="/proxies">
          <i class="pi pi-shield"></i>
          <span>Proxies</span>
        </router-link>

      </nav>

    <div class="menu-section">Configuración</div>

    <nav class="menu">
      <router-link to="/personalities">
        <i class="pi pi-sparkles"></i>
        <span>Personalidades</span>
      </router-link>

      <router-link to="/accounts">
        <i class="pi pi-user"></i>
        <span>Cuentas sociales</span>
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <div class="status-dot"></div>
      <div>
        <strong>Backend Docker</strong>
        <span>Conectado vía /api</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { orchestratorDashboardUrl } from "../config/orchestrator";

const orchestratorUrl = orchestratorDashboardUrl();
</script>

<style scoped>
.sidebar {
  width: 286px;
  min-height: 100vh;
  padding: 22px 18px;
  background:
    linear-gradient(180deg, rgba(37, 99, 235, 0.16), transparent 40%),
    #0f172a;
  color: #fff;
  position: sticky;
  top: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 10px 8px 24px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  margin-bottom: 20px;
}

.brand-icon {
  width: 46px;
  height: 46px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  box-shadow: 0 14px 30px rgba(37, 99, 235, 0.35);
  font-size: 22px;
}

.brand-title {
  font-weight: 900;
  letter-spacing: -0.03em;
  font-size: 18px;
}

.brand-subtitle {
  color: #94a3b8;
  font-size: 12px;
  margin-top: 2px;
}

.menu-section {
  color: #64748b;
  font-size: 11px;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 18px 8px 10px;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.menu a {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #cbd5e1;
  text-decoration: none;
  padding: 12px 13px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 700;
  transition: 0.18s ease;
}

.menu a:hover,
.menu a.router-link-active {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.28);
}

.sidebar-footer {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 16px;
  padding: 12px;
}

.sidebar-footer strong {
  display: block;
  font-size: 13px;
}

.sidebar-footer span {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.status-dot {
  width: 10px;
  height: 10px;
  background: #22c55e;
  border-radius: 999px;
  box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.12);
}

@media (max-width: 900px) {
  .sidebar {
    width: 100%;
    min-height: auto;
    position: relative;
  }

  .sidebar-footer {
    position: static;
    margin-top: 18px;
  }
}
</style>
