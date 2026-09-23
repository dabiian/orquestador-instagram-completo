import test from "node:test";
import assert from "node:assert/strict";

import { orchestratorDashboardUrl } from "../src/config/orchestrator.js";

test("accepts a dashboard link without credentials", () => {
  assert.equal(orchestratorDashboardUrl("https://rpa.example.com/dashboard/"),
    "https://rpa.example.com/dashboard/");
});

test("rejects credentials, query tokens and unsafe schemes", () => {
  assert.equal(orchestratorDashboardUrl("https://user:secret@rpa.example.com/dashboard/"), null);
  assert.equal(orchestratorDashboardUrl("https://rpa.example.com/dashboard/?token=secret"), null);
  assert.equal(orchestratorDashboardUrl("javascript:alert(1)"), null);
});
