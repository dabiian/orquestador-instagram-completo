// The orchestrator owns execution creation and monitoring. The Instagram CRM
// only links to its authenticated dashboard; no bot or operator token is bundled.
export function orchestratorDashboardUrl(configured = import.meta.env.VITE_ORCHESTRATOR_DASHBOARD_URL) {
  const value = configured || "http://10.0.0.92:8005/dashboard/";
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    if (!url.pathname.endsWith("/dashboard/")) return null;
    if (url.username || url.password || url.search || url.hash) return null;
    return url.href;
  } catch {
    return null;
  }
}
