import http from "./http";

export const tasksApi = {
  listTaskTypes(params = {}) {
    return http.get("/task_types/", { params });
  },

  listAccounts(params = {}) {
    return http.get("/social_medias/", { params });
  },

  createForAccounts(payload, socialMediaAccountId = null) {
    const params = {};

    if (socialMediaAccountId) {
      params.social_media_account_id = socialMediaAccountId;
    }

    return http.post(
      "/generate_tasks/create_tasks_for_all_accounts/",
      payload,
      { params }
    );
  },

  listTasks(params = {}) {
    return http.get("/view_tasks/", { params });
  },

  updateTask(id, payload) {
    return http.patch(`/task_bots/${id}/`, payload);
  },

  getTask(id) {
    return http.get(`/task_bots/${id}/`);
  },
};