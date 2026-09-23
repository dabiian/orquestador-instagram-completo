import http from "./http";

export const prospectingApi = {
  listCampaigns(params = {}) {
    return http.get("/prospecting/campaigns/", { params });
  },

  createCampaign(payload) {
    return http.post("/prospecting/campaigns/", payload);
  },

  updateCampaign(id, payload) {
    return http.patch(`/prospecting/campaigns/${id}/`, payload);
  },

  removeCampaign(id) {
    return http.delete(`/prospecting/campaigns/${id}/`);
  },

  listCampaignAccounts(params = {}) {
    return http.get("/prospecting/campaign-accounts/", { params });
  },

  createCampaignAccount(payload) {
    return http.post("/prospecting/campaign-accounts/", payload);
  },

  updateCampaignAccount(id, payload) {
    return http.patch(`/prospecting/campaign-accounts/${id}/`, payload);
  },

  removeCampaignAccount(id) {
    return http.delete(`/prospecting/campaign-accounts/${id}/`);
  },
};