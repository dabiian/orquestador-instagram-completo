import http from "./http";

export const campaignsApi = {
  list(params = {}) {
    return http.get("/prospecting/campaigns/", { params });
  },

  get(id) {
    return http.get(`/prospecting/campaigns/${id}/`);
  },

  create(payload) {
    return http.post("/prospecting/campaigns/", payload);
  },

  update(id, payload) {
    return http.patch(`/prospecting/campaigns/${id}/`, payload);
  },

  remove(id) {
    return http.delete(`/prospecting/campaigns/${id}/`);
  },
};