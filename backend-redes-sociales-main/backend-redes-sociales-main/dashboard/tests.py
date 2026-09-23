from datetime import datetime, timezone
import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from dashboard.models.account_owner import AccountOwner
from dashboard.models.campaign_info import CampaignInfo
from dashboard.models.social_media_account import SocialMediaAccount
from dashboard.models.task_bot import TaskBot
from dashboard.pagination import PendingBotPagination
from dashboard.serializers import (
    PendingBotQuerySerializer,
    PendingBotSerializer,
    TaskBotsSerializer2,
)
from dashboard.views_v2 import PendingBotsV2ViewSet
from dashboard.views import TaskPendings
from dashboard.orchestrator.adapter import CAPABILITIES, InstagramOrchestratorAdapter
from dashboard.orchestrator.catalog import _authorized


class PendingBotEndpointTests(SimpleTestCase):
    def test_pagination_returns_the_oldest_pending_tasks_first(self):
        self.assertEqual(PendingBotPagination.page_size, 10)
        self.assertEqual(PendingBotPagination.max_page_size, 100)
        self.assertEqual(PendingBotPagination.ordering, ("start_date", "id"))

    def test_pagination_preserves_the_legacy_list_response(self):
        paginator = PendingBotPagination()
        paginator.has_next = False
        paginator.has_previous = False
        response = paginator.get_paginated_response([{"id": 1}])
        self.assertEqual(response.data, [{"id": 1}])
        self.assertEqual(response["X-Result-Count"], "1")

    def test_query_parameters_are_validated(self):
        valid = PendingBotQuerySerializer(data={"bot_name": "Bot_Facebook_DESKTOP-CJ16S4J", "status_process": "EP", "account_id": "12"})
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.validated_data["account_id"], 12)
        missing_bot_name = PendingBotQuerySerializer(data={"status_process": "EP"})
        self.assertFalse(missing_bot_name.is_valid())
        self.assertIn("bot_name", missing_bot_name.errors)
        invalid = PendingBotQuerySerializer(data={"account_id": "invalid"})
        self.assertFalse(invalid.is_valid())
        self.assertIn("bot_name", invalid.errors)
        self.assertIn("account_id", invalid.errors)

    def test_v1_keeps_its_original_serializer_and_no_pagination(self):
        view = TaskPendings()
        self.assertIs(view.get_serializer_class(), TaskBotsSerializer2)
        self.assertIsNone(view.pagination_class)
        self.assertEqual(view.get_queryset().query.order_by, ())

    def test_v2_uses_the_optimized_serializer_and_queryset(self):
        view = PendingBotsV2ViewSet()
        queryset = view.get_queryset()
        self.assertIs(view.get_serializer_class(), PendingBotSerializer)
        self.assertEqual(queryset.query.order_by, ("start_date", "id"))
        self.assertIn("social_media_account", queryset.query.select_related)

    def test_v2_filters_ep_and_eq_by_default(self):
        view = PendingBotsV2ViewSet()
        queryset = view.filter_bot_queryset(view.get_queryset(), bot_name="Bot_Facebook_DESKTOP-CJ16S4J")
        _, params = queryset.query.sql_with_params()
        self.assertIn("Bot_Facebook_DESKTOP-CJ16S4J", params)
        self.assertIn("EP", params)
        self.assertIn("EQ", params)

    def test_v2_explicit_status_replaces_the_default_statuses(self):
        view = PendingBotsV2ViewSet()
        queryset = view.filter_bot_queryset(view.get_queryset(), bot_name="Bot_Facebook_DESKTOP-CJ16S4J", status_process="ER")
        _, params = queryset.query.sql_with_params()
        self.assertIn("ER", params)
        self.assertNotIn("EP", params)
        self.assertNotIn("EQ", params)

    def test_v2_rejects_a_request_without_bot_name_before_querying(self):
        request = APIRequestFactory().get("/api/v2/pending_bots/")
        view = PendingBotsV2ViewSet.as_view({"get": "list"})
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("bot_name", response.data)

    def test_task_bot_has_an_index_for_bot_name_queries(self):
        index_names = {index.name for index in TaskBot._meta.indexes}
        self.assertIn("taskbot_executor_id_idx", index_names)

    def test_pending_serializer_omits_the_reverse_campaign_relation(self):
        owner = AccountOwner(id=1, owner_name="Owner", owner_email="owner@example.com", owner_phone="000")
        campaign = CampaignInfo(id=2, campaign_name="Campaign", campaign_info="Info", phone_number="000", alt_phone_number="000", webpage_url="https://example.com", fanpage_url="https://example.com/page")
        account = SocialMediaAccount(id=3, account_name="Account", owner=owner, campaign_info=campaign)
        task = TaskBot(id=4, task_type=[1], status_process="EP", social_media_account=account)
        data = PendingBotSerializer(task).data
        campaign_data = data["social_media_account"]["campaign_info_data"]
        self.assertEqual(campaign_data["id"], 2)
        self.assertNotIn("prospectation_groups", campaign_data)

    def test_pending_serializer_returns_start_date_in_bogota_time(self):
        task = TaskBot(id=4, task_type=[1], status_process="EP", start_date=datetime(2026, 6, 30, 12, 40, tzinfo=timezone.utc), end_date=datetime(2026, 6, 30, 13, 40, tzinfo=timezone.utc))
        data = PendingBotSerializer(task).data
        self.assertEqual(data["start_date"], "2026-06-30T07:40:00-05:00")
        self.assertEqual(data["end_date"], "2026-06-30T08:40:00-05:00")


class InstagramOrchestratorAdapterTests(SimpleTestCase):
    @patch.dict(
        os.environ,
        {
            "ORCHESTRATOR_URL": "http://orchestrator:8005",
            "ORCHESTRATOR_WS_URL": "ws://orchestrator:8005/api/v1/bots/ws",
            "ORCHESTRATOR_BOT_KEY": "instagram-backend-test",
            "ORCHESTRATOR_BOT_TOKEN": "bot-secret",
            "ORCHESTRATOR_MAX_CONCURRENCY": "4",
        },
        clear=False,
    )
    def test_adapter_reads_the_django_bot_credentials(self):
        adapter = InstagramOrchestratorAdapter()
        self.assertEqual(adapter.bot_key, "instagram-backend-test")
        self.assertEqual(adapter.token, "bot-secret")
        self.assertEqual(adapter.ws_url, "ws://orchestrator:8005/api/v1/bots/ws")
        self.assertEqual(adapter.max_concurrency, 4)

    def test_capabilities_are_exactly_instagram(self):
        self.assertEqual(CAPABILITIES, {"instagram.maduracion", "instagram.prospecting"})


class InstagramOrchestratorCatalogAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(INSTAGRAM_ORCHESTRATOR_TOKEN="catalog-secret")
    def test_catalog_accepts_matching_token(self):
        request = self.factory.get("/api/orchestrator/instagram/catalog/", HTTP_X_ORCHESTRATOR_TOKEN="catalog-secret")
        self.assertTrue(_authorized(request))

    @override_settings(INSTAGRAM_ORCHESTRATOR_TOKEN="catalog-secret")
    def test_catalog_rejects_missing_or_wrong_token(self):
        missing = self.factory.get("/api/orchestrator/instagram/catalog/")
        wrong = self.factory.get("/api/orchestrator/instagram/catalog/", HTTP_X_ORCHESTRATOR_TOKEN="wrong-secret")
        self.assertFalse(_authorized(missing))
        self.assertFalse(_authorized(wrong))

    @override_settings(INSTAGRAM_ORCHESTRATOR_TOKEN="catalog-secret", ORCHESTRATOR_API_TOKEN="legacy-secret")
    def test_catalog_contract_does_not_accidentally_accept_the_legacy_token(self):
        request = self.factory.get("/api/orchestrator/instagram/catalog/", HTTP_X_ORCHESTRATOR_TOKEN="legacy-secret")
        self.assertFalse(_authorized(request))
