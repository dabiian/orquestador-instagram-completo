from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from dashboard.orchestrator.adapter import CAPABILITIES, InstagramOrchestratorAdapter, _scheduled_start_date
from dashboard.orchestrator.catalog import _authorized
from dashboard.orchestrator.claims import claim_instagram_task


class InstagramOrchestratorAdapterTests(SimpleTestCase):
    @patch.dict(
        "os.environ",
        {
            "ORCHESTRATOR_URL": "http://orchestrator:8005",
            "ORCHESTRATOR_WS_URL": "ws://orchestrator:8005/api/v1/bots/ws",
            "ORCHESTRATOR_BOT_KEY": "instagram-backend-test",
            "ORCHESTRATOR_BOT_TOKEN": "secret",
            "ORCHESTRATOR_MAX_CONCURRENCY": "4",
        },
        clear=False,
    )
    def test_adapter_registration_contract(self):
        adapter = InstagramOrchestratorAdapter()
        self.assertEqual(adapter.bot_key, "instagram-backend-test")
        self.assertEqual(adapter.max_concurrency, 4)
        self.assertEqual(adapter.ws_url, "ws://orchestrator:8005/api/v1/bots/ws")

    def test_capabilities_are_exactly_instagram(self):
        self.assertEqual(CAPABILITIES, {"instagram.maduracion", "instagram.prospecting"})

    @patch("dashboard.orchestrator.adapter.OrchestratorInstagramExecution.objects.filter")
    def test_capacity_counts_executions_not_account_tasks(self, filtered):
        filtered.return_value.count.return_value = 1
        with patch.dict("os.environ", {"ORCHESTRATOR_MAX_CONCURRENCY": "3"}):
            self.assertEqual(InstagramOrchestratorAdapter()._available_slots(), 2)
        filtered.assert_called_once_with(status__in=["running", "cancelling"])


class InstagramOrchestratorCatalogAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(INSTAGRAM_ORCHESTRATOR_TOKEN="catalog-secret")
    def test_catalog_accepts_matching_token(self):
        request = self.factory.get(
            "/api/orchestrator/instagram/catalog/",
            HTTP_X_ORCHESTRATOR_TOKEN="catalog-secret",
        )
        self.assertTrue(_authorized(request))

    @override_settings(INSTAGRAM_ORCHESTRATOR_TOKEN="catalog-secret")
    def test_catalog_rejects_missing_or_wrong_token(self):
        missing = self.factory.get("/api/orchestrator/instagram/catalog/")
        wrong = self.factory.get(
            "/api/orchestrator/instagram/catalog/",
            HTTP_X_ORCHESTRATOR_TOKEN="wrong-secret",
        )
        self.assertFalse(_authorized(missing))
        self.assertFalse(_authorized(wrong))


class InstagramClaimAuthenticationTests(SimpleTestCase):
    @override_settings(INSTAGRAM_TASK_CLAIM_TOKEN="worker-secret")
    def test_claim_rejects_requests_without_matching_bearer_token(self):
        factory = APIRequestFactory()
        for headers in ({}, {"HTTP_AUTHORIZATION": "Bearer wrong"}):
            request = factory.post("/api/orchestrator/instagram/tasks/claim/", {"bot_executor": "bot"},
                                   format="json", **headers)
            self.assertEqual(claim_instagram_task(request).status_code, 401)

    @override_settings(INSTAGRAM_TASK_CLAIM_TOKEN="")
    def test_claim_fails_closed_when_secret_is_not_configured(self):
        request = APIRequestFactory().post("/api/orchestrator/instagram/tasks/claim/", {}, format="json")
        self.assertEqual(claim_instagram_task(request).status_code, 503)


class InstagramScheduleTests(SimpleTestCase):
    def test_utc_start_date_is_preserved(self):
        self.assertEqual(_scheduled_start_date({"start_date": "2026-09-23T14:00:00Z"}).isoformat(),
                         "2026-09-23T14:00:00+00:00")

    def test_naive_start_date_is_rejected(self):
        with self.assertRaises(ValueError):
            _scheduled_start_date({"start_date": "2026-09-23T14:00:00"})
