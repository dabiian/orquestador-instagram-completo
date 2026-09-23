from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from dashboard.models import AccountOwner, SocialMediaAccount, TaskBot
from dashboard.orchestrator.claims import claim_instagram_task


@override_settings(INSTAGRAM_TASK_CLAIM_TOKEN="worker-secret")
class InstagramTaskClaimTests(TestCase):
    def setUp(self):
        owner = AccountOwner.objects.create(owner_name="Test", owner_email="test@example.com", owner_phone="123")
        self.account = SocialMediaAccount.objects.create(owner=owner, account_name="Instagram test", account_type="instagram")

    def request(self, token="worker-secret"):
        return APIRequestFactory().post(
            "/api/orchestrator/instagram/tasks/claim/",
            {"bot_executor": "Bot_Instagram_TEST"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}" if token else "",
        )

    def test_claim_changes_sp_to_ep_and_assigns_executor(self):
        task = TaskBot.objects.create(
            task_type=[10],
            bot_executor="NONE",
            status_process="SP",
            comment={"status": "Pending..."},
            social_media_account=self.account,
        )
        response = claim_instagram_task(self.request())

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status_process, "EP")
        self.assertEqual(task.bot_executor, "Bot_Instagram_TEST")
        self.assertEqual(response.data["task"]["id"], task.id)

    def test_claim_does_not_return_ep_task(self):
        TaskBot.objects.create(
            task_type=[10],
            bot_executor="Bot_Instagram_OTHER",
            status_process="EP",
        )

        response = claim_instagram_task(self.request())

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["task"])

    def test_claim_rejects_missing_or_wrong_token_without_changing_task(self):
        task = TaskBot.objects.create(status_process="SP", bot_executor="NONE", social_media_account=self.account)
        self.assertEqual(claim_instagram_task(self.request("")).status_code, 401)
        self.assertEqual(claim_instagram_task(self.request("wrong")).status_code, 401)
        task.refresh_from_db()
        self.assertEqual(task.status_process, "SP")

    def test_claim_waits_for_scheduled_start(self):
        TaskBot.objects.create(status_process="SP", bot_executor="NONE", social_media_account=self.account,
                               start_date=timezone.now() + timedelta(hours=1))
        response = claim_instagram_task(self.request())
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["task"])
