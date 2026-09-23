from __future__ import annotations

import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from dashboard.models import TaskBot
from dashboard.serializers import TaskBotsSerializer2


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def claim_instagram_task(request):
    """Atomically claim the oldest SP Instagram task for one executor.

    A task assigned to the exact executor is preferred.  Tasks with executor
    NONE remain backwards-compatible and may be claimed by any Instagram bot.
    """
    expected = getattr(settings, "INSTAGRAM_TASK_CLAIM_TOKEN", "")
    if not expected:
        return Response({"detail": "Instagram task claim is not configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    authorization = request.headers.get("Authorization", "")
    supplied = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    if not supplied or not secrets.compare_digest(supplied, expected):
        return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

    bot_executor = str(request.data.get("bot_executor") or "").strip()
    if not bot_executor:
        return Response({"detail": "bot_executor is required"}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        task = (
            TaskBot.objects.select_for_update(of=("self",))
            .select_related(
                "social_media_account__bot_personality",
                "social_media_account__owner",
                "social_media_account__proxy",
                "social_media_account__campaign_info",
            )
            .filter(status_process="SP")
            .filter(social_media_account__account_type__iexact="instagram")
            .filter(start_date__lte=timezone.now())
            .filter(bot_executor__in=[bot_executor, "NONE", "", None])
            .order_by("start_date", "id")
            .first()
        )
        if task is None:
            return Response({"task": None}, status=status.HTTP_200_OK)

        task.bot_executor = bot_executor
        task.status_process = "EP"
        task.comment = {
            **(task.comment or {}),
            "status": "Ejecutando...",
            "claimed_by": bot_executor,
        }
        task.save(update_fields=["bot_executor", "status_process", "comment"])

    return Response({"task": TaskBotsSerializer2(task).data}, status=status.HTTP_200_OK)


