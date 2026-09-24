from django.test import TestCase
from rest_framework.test import APIClient


class InstagramAccountProvisioningTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_documented_six_step_flow_requires_assignment_for_active_lookup(self):
        personality = self.client.post(
            "/api/bot_personalities/",
            {"name": "Laura", "language": "ESPAÑOL"},
            format="json",
        )
        self.assertEqual(personality.status_code, 201)

        owner = self.client.post(
            "/api/account_owners/",
            {
                "owner_name": "Salon Test",
                "owner_email": "salon@example.com",
                "owner_phone": "+573001234567",
                "owner_urls": ["https://www.instagram.com/salon_test/"],
                "services": ["Coloracion"],
            },
            format="json",
        )
        self.assertEqual(owner.status_code, 201)

        account = self.client.post(
            "/api/social_media_accounts/",
            {
                "account_name": "salon_test",
                "group": ["grupo_1"],
                "owner": owner.data["id"],
                "bot_personality": personality.data["id"],
                "proxy": None,
                "account_kind": "business",
                "other_credentials": {
                    "user": "salon_test",
                    "password": "secret",
                    "cookie": [],
                },
            },
            format="json",
        )
        self.assertEqual(account.status_code, 201)

        campaign = self.client.post(
            "/api/prospecting/campaigns/",
            {
                "social_media_account": account.data["id"],
                "name": "Prospeccion Test",
                "platform": "instagram",
                "status": "active",
                "services_snapshot": ["Coloracion"],
                "strategy_snapshot": {"hashtags": ["#Bogota"]},
                "business_description": "Salon",
                "business_hours": "Lun-Sab",
                "follow_up_phone": "+573001234567",
                "follow_up_email": "salon@example.com",
                "owner_instagram_profile_url": "https://www.instagram.com/salon_test/",
            },
            format="json",
        )
        self.assertEqual(campaign.status_code, 201)

        active_url = (
            f"/api/prospecting/campaigns/active/"
            f"?social_media_account_id={account.data['id']}&platform=instagram"
        )
        self.assertEqual(self.client.get(active_url).status_code, 404)

        assignment = self.client.post(
            "/api/prospecting/campaign-accounts/",
            {
                "campaign": campaign.data["id"],
                "social_media_account": account.data["id"],
                "platform": "instagram",
                "role": "prospecting",
                "is_active": True,
                "daily_limit": 20,
                "total_limit": 500,
            },
            format="json",
        )
        self.assertEqual(assignment.status_code, 201)

        active = self.client.get(active_url)
        self.assertEqual(active.status_code, 200)
        self.assertTrue(active.data["ok"])
        self.assertEqual(active.data["campaign"]["id"], campaign.data["id"])
        self.assertEqual(active.data["assignment"]["id"], assignment.data["id"])

    def test_invalid_account_kind_is_rejected(self):
        personality = self.client.post("/api/bot_personalities/", {}, format="json")
        owner = self.client.post(
            "/api/account_owners/",
            {
                "owner_name": "Owner",
                "owner_email": "owner@example.com",
                "owner_phone": "123",
                "services": [],
            },
            format="json",
        )
        response = self.client.post(
            "/api/social_media_accounts/",
            {
                "account_name": "bad_kind",
                "group": [],
                "owner": owner.data["id"],
                "bot_personality": personality.data["id"],
                "account_kind": "instagram",
                "other_credentials": {"user": "bad_kind", "password": "secret", "cookie": []},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_campaign_assignment_is_rejected(self):
        personality = self.client.post("/api/bot_personalities/", {}, format="json").data
        owner = self.client.post(
            "/api/account_owners/",
            {
                "owner_name": "Owner",
                "owner_email": "owner@example.com",
                "owner_phone": "123",
                "services": [],
            },
            format="json",
        ).data
        account = self.client.post(
            "/api/social_media_accounts/",
            {
                "account_name": "duplicate_test",
                "group": [],
                "owner": owner["id"],
                "bot_personality": personality["id"],
                "account_kind": "business",
                "other_credentials": {"user": "duplicate_test", "password": "secret", "cookie": []},
            },
            format="json",
        ).data
        campaign = self.client.post(
            "/api/prospecting/campaigns/",
            {
                "social_media_account": account["id"],
                "name": "Campaign",
                "platform": "instagram",
                "status": "active",
            },
            format="json",
        ).data
        payload = {
            "campaign": campaign["id"],
            "social_media_account": account["id"],
            "platform": "instagram",
            "role": "prospecting",
            "is_active": True,
        }
        self.assertEqual(self.client.post("/api/prospecting/campaign-accounts/", payload, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/prospecting/campaign-accounts/", payload, format="json").status_code, 400)


    def test_campaign_rejects_put_and_defaults_to_draft(self):
        owner = self.client.post(
            "/api/account_owners/",
            {"owner_name": "Owner Draft", "owner_email": "draft@example.com", "owner_phone": "123", "services": []},
            format="json",
        ).data
        account = self.client.post(
            "/api/social_media_accounts/",
            {
                "account_name": "draft_account",
                "group": [],
                "owner": owner["id"],
                "account_kind": "business",
                "other_credentials": {"user": "draft_account", "password": "secret", "cookie": []},
            },
            format="json",
        ).data
        created = self.client.post(
            "/api/prospecting/campaigns/",
            {"social_media_account": account["id"], "name": "Draft Campaign", "platform": "instagram"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["status"], "draft")
        detail = f"/api/prospecting/campaigns/{created.data['id']}/"
        self.assertEqual(self.client.put(detail, created.data, format="json").status_code, 405)
        self.assertEqual(self.client.patch(detail, {"status": "active"}, format="json").status_code, 200)

    def test_proxy_can_only_be_assigned_to_one_account_and_cookie_can_be_empty(self):
        owner = self.client.post(
            "/api/account_owners/",
            {"owner_name": "Proxy Owner", "owner_email": "proxy@example.com", "owner_phone": "123", "services": []},
            format="json",
        ).data
        proxy = self.client.post(
            "/api/proxy/",
            {"ip_address": "192.168.10.25", "port": 8080, "username": None, "password": None},
            format="json",
        )
        self.assertEqual(proxy.status_code, 201)

        def create_account(name):
            return self.client.post(
                "/api/social_media_accounts/",
                {
                    "account_name": name,
                    "group": ["grupo_1"],
                    "owner": owner["id"],
                    "proxy": proxy.data["id"],
                    "account_kind": "business",
                    "other_credentials": {"user": name, "password": "secret", "cookie": []},
                },
                format="json",
            )

        first = create_account("proxy_first")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(create_account("proxy_second").status_code, 400)
        cookie_url = f"/api/social_media_accounts/{first.data['id']}/update_cookie/"
        self.assertEqual(self.client.patch(cookie_url, [], format="json").status_code, 200)

    def test_expanded_social_media_detail_exposes_relations(self):
        personality = self.client.post("/api/bot_personalities/", {"name": "Expanded"}, format="json").data
        owner = self.client.post(
            "/api/account_owners/",
            {"owner_name": "Expanded Owner", "owner_email": "expanded@example.com", "owner_phone": "123", "services": []},
            format="json",
        ).data
        account = self.client.post(
            "/api/social_media_accounts/",
            {
                "account_name": "expanded_account",
                "group": [],
                "owner": owner["id"],
                "bot_personality": personality["id"],
                "account_kind": "personal",
                "other_credentials": {"user": "expanded_account", "password": "secret", "cookie": []},
            },
            format="json",
        ).data
        response = self.client.get(f"/api/social_medias/{account['id']}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("owner", response.data)
        self.assertIn("bot_personality", response.data)
        self.assertIn("proxy", response.data)


    def test_proxy_port_must_be_strictly_positive(self):
        response = self.client.post(
            "/api/proxy/",
            {"ip_address": "192.168.10.26", "port": 0, "username": None, "password": None},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


    def test_assignment_limits_may_be_null_and_usage_remains_allowed(self):
        owner = self.client.post(
            "/api/account_owners/",
            {"owner_name": "Unlimited Owner", "owner_email": "unlimited@example.com", "owner_phone": "123", "services": []},
            format="json",
        ).data
        account = self.client.post(
            "/api/social_media_accounts/",
            {
                "account_name": "unlimited_account",
                "group": [],
                "owner": owner["id"],
                "account_kind": "business",
                "other_credentials": {"user": "unlimited_account", "password": "secret", "cookie": []},
            },
            format="json",
        ).data
        campaign = self.client.post(
            "/api/prospecting/campaigns/",
            {
                "social_media_account": account["id"],
                "name": "Unlimited Campaign",
                "platform": "instagram",
                "status": "active",
            },
            format="json",
        ).data
        assignment = self.client.post(
            "/api/prospecting/campaign-accounts/",
            {
                "campaign": campaign["id"],
                "social_media_account": account["id"],
                "platform": "instagram",
                "role": "prospecting",
                "is_active": True,
                "daily_limit": None,
                "total_limit": None,
            },
            format="json",
        )
        self.assertEqual(assignment.status_code, 201)
        self.assertIsNone(assignment.data["daily_limit"])
        self.assertIsNone(assignment.data["total_limit"])

        usage = self.client.get(f"/api/prospecting/campaign-accounts/{assignment.data['id']}/usage/")
        self.assertEqual(usage.status_code, 200)
        self.assertTrue(usage.data["allowed"])
        self.assertIsNone(usage.data["daily_remaining"])
        self.assertIsNone(usage.data["total_remaining"])
