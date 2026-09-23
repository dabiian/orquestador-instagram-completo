from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from dashboard.models import AccountOwner, SocialMediaAccount
from dashboard.orchestrator.catalog import instagram_catalog


@override_settings(INSTAGRAM_ORCHESTRATOR_TOKEN="catalog-secret")
class InstagramCatalogTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner = AccountOwner.objects.create(
            owner_name="Catalog owner",
            owner_email="catalog@example.com",
            owner_phone="123",
        )

    def _request(self, token="catalog-secret"):
        return self.factory.get(
            "/api/orchestrator/instagram/catalog/",
            HTTP_X_ORCHESTRATOR_TOKEN=token,
        )

    def test_catalog_exposes_only_explicit_instagram_accounts(self):
        instagram = SocialMediaAccount.objects.create(
            owner=self.owner,
            account_name="Instagram account",
            account_type="instagram",
        )
        SocialMediaAccount.objects.create(
            owner=self.owner,
            account_name="Legacy account",
        )

        response = instagram_catalog(self._request())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["platform"], "instagram")
        self.assertEqual([row["id"] for row in response.data["accounts"]], [instagram.id])
        self.assertEqual(response.data["accounts"][0]["account_type"], "instagram")

    def test_catalog_rejects_wrong_token(self):
        response = instagram_catalog(self._request("wrong"))
        self.assertEqual(response.status_code, 401)
