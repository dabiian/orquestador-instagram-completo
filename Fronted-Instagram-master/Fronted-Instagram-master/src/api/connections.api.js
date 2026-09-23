import http from "./http";

export const connectionsApi = {
  list() {
    return http.get("/connections/");
  },

  health() {
    return http.get("/health/");
  },
};