import http from "./http";

export const personalitiesApi = {
  list(params = {}) {
    return http.get("/bot_personalities/", { params });
  },

  create(payload) {
    return http.post("/bot_personalities/", payload);
  },

  update(id, payload) {
    return http.patch(`/bot_personalities/${id}/`, payload);
  },

  remove(id) {
    return http.delete(`/bot_personalities/${id}/`);
  },
};