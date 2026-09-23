import http from "./http";

export const accountsApi = {
  list(params = {}) {
    return http.get("/social_medias/", { params });
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

  updateCookie(id, cookies) {
    return http.patch(`/social_media_accounts/${id}/update_cookie/`, cookies);
  },
};