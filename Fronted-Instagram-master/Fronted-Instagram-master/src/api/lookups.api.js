import http from "./http";

export const lookupsApi = {
  owners(params = {}) {
    return http.get("/account_owners/", { params });
  },

  proxies(params = {}) {
    return http.get("/proxy/", { params });
  },

  availableProxies(params = {}) {
    return http.get("/proxy/available/", { params });
  },

  platforms(params = {}) {
    return http.get("/social_media_platforms/", { params });
  },

  botPersonalities(params = {}) {
    return http.get("/bot_personalities/", { params });
  },

  prospectingCampaigns(params = {}) {
    return http.get("/prospecting/campaigns/", { params });
  },

  prospectingCampaignAccounts(params = {}) {
    return http.get("/prospecting/campaign-accounts/", { params });
  },
};
