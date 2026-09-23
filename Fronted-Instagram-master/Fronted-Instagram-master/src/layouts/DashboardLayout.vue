<template>
  <div class="app-shell">
    <AppSidebar />

    <main class="app-main">
      <AppTopbar />

      <section class="app-page">
        <router-view />
      </section>
    </main>
  </div>
</template>

<script setup>
import AppSidebar from "../components/AppSidebar.vue";
import AppTopbar from "../components/AppTopbar.vue";
</script>