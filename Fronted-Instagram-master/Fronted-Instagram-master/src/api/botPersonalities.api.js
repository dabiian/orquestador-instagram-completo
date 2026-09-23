import http from "./http";

export const botPersonalitiesApi = {
  list(params = {}) {
    return http.get("/bot_personalities/", { params });
  },

  get(id) {
    return http.get(`/bot_personalities/${id}/`);
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