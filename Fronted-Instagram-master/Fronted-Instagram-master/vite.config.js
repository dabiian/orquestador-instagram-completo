import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://10.0.0.90:8004",
        changeOrigin: true,
        secure: false,
      },
    },
  },
});