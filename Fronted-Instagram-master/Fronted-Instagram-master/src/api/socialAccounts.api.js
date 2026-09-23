import http from "./http";

export const socialAccountsApi = {
  list(params = {}) {
    return http.get("/social_media_accounts/", { params });
  },

  listCompleted(params = {}) {
    return http.get("/social_medias/", { params });
  },

  get(id) {
    return http.get(`/social_media_accounts/${id}/`);
  },

  create(payload) {
    return http.post("/social_media_accounts/", payload);
  },

  update(id, payload) {
    return http.patch(`/social_media_accounts/${id}/`, payload);
  },

  remove(id) {
    return http.delete(`/social_media_accounts/${id}/`);
  },
};