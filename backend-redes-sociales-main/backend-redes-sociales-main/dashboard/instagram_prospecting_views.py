from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models.instagram_prospecting import (
    InstagramProspectingCampaign,
    InstagramProspect,
    InstagramProspectPost,
    InstagramProspectInteraction,
    InstagramFollowUpAlert,
)
from .instagram_prospecting_serializers import (
    InstagramProspectingCampaignSerializer,
    InstagramProspectSerializer,
    InstagramProspectPostSerializer,
    InstagramProspectInteractionSerializer,
    InstagramFollowUpAlertSerializer,
)


class InstagramProspectingCampaignViewSet(viewsets.ModelViewSet):
    queryset = InstagramProspectingCampaign.objects.select_related(
        "social_media_account"
    ).order_by("-created_at")
    serializer_class = InstagramProspectingCampaignSerializer

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        account_id = request.query_params.get("social_media_account_id")
        platform = request.query_params.get("platform", "instagram")

        if not account_id:
            return Response(
                {"ok": False, "error": "social_media_account_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign = (
            self.get_queryset()
            .filter(
                social_media_account_id=account_id,
                platform=platform,
                status="active",
            )
            .first()
        )

        if campaign is None:
            return Response(
                {"ok": False, "error": "No active campaign found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = self.get_serializer(campaign).data

        return Response(
            {
                "ok": True,
                "campaign": data,
                "assignment": {
                    "social_media_account_id": campaign.social_media_account_id,
                    "campaign_id": campaign.id,
                },
            }
        )


class InstagramProspectViewSet(viewsets.ModelViewSet):
    pagination_class = None
    queryset = InstagramProspect.objects.select_related("campaign").order_by(
        "-created_at"
    )
    serializer_class = InstagramProspectSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        campaign_id = self.request.query_params.get("campaign_id")
        platform = self.request.query_params.get("platform")
        username = self.request.query_params.get("username")
        status_value = self.request.query_params.get("status")

        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        if platform:
            queryset = queryset.filter(platform=platform)
        if username:
            queryset = queryset.filter(username=username)
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset


class InstagramProspectPostViewSet(viewsets.ModelViewSet):
    pagination_class = None
    queryset = InstagramProspectPost.objects.select_related("prospect").order_by(
        "-created_at"
    )
    serializer_class = InstagramProspectPostSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        prospect_id = self.request.query_params.get("prospect_id")
        status_value = self.request.query_params.get("status")

        if prospect_id:
            queryset = queryset.filter(prospect_id=prospect_id)
        if status_value:
            queryset = queryset.filter(status=status_value)

        return queryset


class InstagramProspectInteractionViewSet(viewsets.ModelViewSet):
    queryset = InstagramProspectInteraction.objects.select_related(
        "prospect",
        "prospect_post",
        "social_media_account",
    ).order_by("-created_at")
    serializer_class = InstagramProspectInteractionSerializer


class InstagramFollowUpAlertViewSet(viewsets.ModelViewSet):
    queryset = InstagramFollowUpAlert.objects.select_related(
        "prospect",
        "prospect_post",
        "interaction",
    ).order_by("-created_at")
    serializer_class = InstagramFollowUpAlertSerializer

    @action(detail=False, methods=["get"], url_path="pending")
    def pending(self, request):
        queryset = self.get_queryset().filter(status="pending")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)



