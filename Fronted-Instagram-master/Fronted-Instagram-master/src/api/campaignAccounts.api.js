import http from "./http";

export const campaignAccountsApi = {
  list(params = {}) {
    return http.get("/prospecting/campaign-accounts/", { params });
  },

  create(payload) {
    return http.post("/prospecting/campaign-accounts/", payload);
  },

  update(id, payload) {
    return http.patch(`/prospecting/campaign-accounts/${id}/`, payload);
  },

  remove(id) {
    return http.delete(`/prospecting/campaign-accounts/${id}/`);
  },
};