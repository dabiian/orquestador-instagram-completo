import http from "./http";

export const prospectsApi = {
  list(params = {}) {
    return http.get("/prospecting/prospects/", { params });
  },

  get(id) {
    return http.get(`/prospecting/prospects/${id}/`);
  },

  update(id, payload) {
    return http.patch(`/prospecting/prospects/${id}/`, payload);
  },

  posts(params = {}) {
    return http.get("/prospecting/prospect-posts/", { params });
  },

  interactions(params = {}) {
    return http.get("/prospecting/prospect-interactions/", { params });
  },
};