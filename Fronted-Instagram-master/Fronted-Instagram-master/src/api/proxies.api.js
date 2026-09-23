import http from "./http";

export const proxiesApi = {
  list(params = {}) {
    return http.get("/proxy/", { params });
  },

  create(payload) {
    return http.post("/proxy/", payload);
  },

  update(id, payload) {
    return http.patch(`/proxy/${id}/`, payload);
  },

  remove(id) {
    return http.delete(`/proxy/${id}/`);
  },
};