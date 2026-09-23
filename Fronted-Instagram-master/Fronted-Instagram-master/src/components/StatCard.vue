<template>
  <div class="stat-card">
    <div class="stat-icon" :class="tone">
      <i :class="icon"></i>
    </div>

    <div class="stat-content">
      <span>{{ label }}</span>
      <strong>{{ value }}</strong>
      <small>{{ hint }}</small>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number],
    default: 0,
  },
  hint: {
    type: String,
    default: "",
  },
  icon: {
    type: String,
    default: "pi pi-chart-bar",
  },
  tone: {
    type: String,
    default: "blue",
  },
});
</script>

<style scoped>
.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  padding: 18px;
  display: flex;
  gap: 14px;
  align-items: center;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 17px;
  display: grid;
  place-items: center;
  font-size: 21px;
}

.stat-icon.blue {
  background: #dbeafe;
  color: #2563eb;
}

.stat-icon.green {
  background: #dcfce7;
  color: #16a34a;
}

.stat-icon.orange {
  background: #ffedd5;
  color: #ea580c;
}

.stat-icon.purple {
  background: #ede9fe;
  color: #7c3aed;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-content span {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.stat-content strong {
  font-size: 28px;
  line-height: 1.1;
  letter-spacing: -0.04em;
  color: #0f172a;
}

.stat-content small {
  color: #94a3b8;
  margin-top: 2px;
}
</style>