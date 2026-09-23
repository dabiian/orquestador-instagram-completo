import { createRouter, createWebHistory } from "vue-router";

import DashboardLayout from "../layouts/DashboardLayout.vue";
import DashboardView from "../views/DashboardView.vue";
import BotPersonalitiesView from "../views/BotPersonalitiesView.vue";
import SocialAccountsView from "../views/SocialAccountsView.vue";
import CampaignsView from "../views/CampaignsView.vue";
import CampaignDetailView from "../views/CampaignDetailView.vue";
import TasksView from "../views/TasksView.vue";
import ProspectsView from "../views/ProspectsView.vue";
import ConnectionsView from "../views/ConnectionsView.vue";
import CreateTasksView from "../views/CreateTasksView.vue";
import MyTasksView from "../views/MyTasksView.vue";
import ProspectingCampaignsView from "../views/ProspectingCampaignsView.vue";
import ProxiesView from "../views/ProxiesView.vue";

const routes = [
  {
    path: "/",
    component: DashboardLayout,
    children: [
      {
        path: "",
        name: "dashboard",
        component: DashboardView,
      },
      {
        path: "personalities",
        name: "personalities",
        component: BotPersonalitiesView,
      },
      {
        path: "accounts",
        name: "accounts",
        component: SocialAccountsView,
      },
      {
        path: "campaigns",
        name: "campaigns",
        component: CampaignsView,
      },
      {
        path: "campaigns/:id",
        name: "campaign-detail",
        component: CampaignDetailView,
        props: true,
      },
      {
        path: "tasks/create",
        name: "create-tasks",
        component: CreateTasksView,
      },
      {
        path: "tasks/list",
        name: "my-tasks",
        component: MyTasksView,
      },
      {
        path: "prospects",
        name: "prospects",
        component: ProspectsView,
      },
      {
        path: "connections",
        name: "connections",
        component: ConnectionsView,
      },
      {
        path: "prospecting-campaigns",
        name: "prospecting-campaigns",
        component: ProspectingCampaignsView,
      },  
      {
        path: "proxies",
        name: "proxies",
        component: ProxiesView,
      },    
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;