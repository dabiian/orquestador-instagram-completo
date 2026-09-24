from __future__ import annotations

import secrets

from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from dashboard.models import AccountOwner, SocialMediaAccount, TaskType
from dashboard.models.instagram_prospecting import InstagramProspectingCampaignAccount


def _authorized(request) -> bool:
    expected = getattr(settings, "INSTAGRAM_ORCHESTRATOR_TOKEN", "")
    supplied = request.headers.get("X-Orchestrator-Token", "")
    return bool(expected) and bool(supplied) and secrets.compare_digest(supplied, expected)


@api_view(["GET"])
@permission_classes([AllowAny])
def instagram_catalog(request):
    if not _authorized(request):
        return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

    instagram_tasks = Q(platform__platform_name__iexact="instagram")
    task_types = list(
        TaskType.objects.select_related("platform")
        .filter(instagram_tasks)
        .order_by("id")
        .values("id", "task_name", "descripcion", "operation", "platform__platform_name")
    )
    # Platform ownership is defined by the campaign-account assignment.
    # The account itself intentionally does not store the platform.
    instagram_account_ids = InstagramProspectingCampaignAccount.objects.filter(
        platform__iexact="instagram",
        is_active=True,
    ).values_list("social_media_account_id", flat=True)
    accounts = list(
        SocialMediaAccount.objects.select_related("owner")
        .filter(id__in=instagram_account_ids)
        .order_by("id")
        .values(
            "id",
            "account_name",
            "account_kind",
            "owner_id",
            "owner__owner_name",
        )
    )
    owners = list(AccountOwner.objects.order_by("id").values("id", "owner_name", "owner_email"))
    return Response(
        {
            "platform": "instagram",
            "accounts": accounts,
            "owners": owners,
            "task_types": task_types,
            "account_platform_note": "Instagram membership is derived from active campaign-account assignments.",
        }
    )
