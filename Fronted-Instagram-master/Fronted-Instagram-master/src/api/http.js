import axios from "axios";

// Use Vite env var `VITE_API_URL` at build time if provided, otherwise
// fall back to the dev proxy path `/api` defined in `vite.config.js`.
// If a full absolute URL is provided (e.g. http://10.0.0.90:8004) we
// force the client to use the local proxy `/api` so nginx can handle
// the request and avoid CORS issues in the browser.
const _RAW_API_BASE = import.meta.env?.VITE_API_URL;
const API_BASE = _RAW_API_BASE && _RAW_API_BASE.startsWith("http") ? "/api" : (_RAW_API_BASE || "/api");

const http = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API ERROR:", error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export function normalizeList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.active_connections)) return data.active_connections;
  return [];
}

export default http;