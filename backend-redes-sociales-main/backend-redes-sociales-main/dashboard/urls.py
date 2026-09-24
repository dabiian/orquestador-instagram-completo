# dashboard/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BotExecutionArtifactViewSet, BotExecutionReportViewSet, BotPersonalitiesViewSet,
    CampaignInfoViewSet, SocialMediaPlatformsViewSet, AccountOwnersViewSet,
    SocialMediaAccountsViewSet, TaskTypeViewSet, TaskBotsViewSet,
    SocialMediaAccountsCompletedViewSet, ProxyViewSet, TaskPendings,
    AddTaskAllAccounts, TaskPendingBotViewSet, SocialMediaMessageViewSet,
    GroupsInfoViewSet, SocialMediaAccountGroupViewSet, AlertLogViewSet,
    BlacklistAccountViewSet, ProspectCommentViewSet, ProspectPostViewSet,
    ProspectReplyClassificationViewSet, ProspectViewSet, QuoteAnswerViewSet,
    UsedForRecommendationOrReviewViewSet, health_check, list_connected_machines,
    ProspectationGroupsViewSet,
)
from .views_v2 import AddTaskAllAccountsV2, PendingBotsV2ViewSet
from .orchestrator.catalog import instagram_catalog
from .orchestrator.claims import claim_instagram_task
from .instagram_prospecting_views import (
    InstagramProspectingCampaignViewSet,
    InstagramProspectViewSet,
    InstagramProspectPostViewSet,
    InstagramProspectInteractionViewSet,
    InstagramFollowUpAlertViewSet,
)

router = DefaultRouter()
router.register(r"bot_personalities", BotPersonalitiesViewSet)
router.register(r"social_media_platforms", SocialMediaPlatformsViewSet)
router.register(r"account_owners", AccountOwnersViewSet)
router.register(r"social_media_accounts", SocialMediaAccountsViewSet)
router.register(r"task_types", TaskTypeViewSet)
router.register(r"task_bots", TaskBotsViewSet, basename="task-bots")
router.register(r"bot-execution-reports", BotExecutionReportViewSet, basename="bot-execution-reports")
router.register(r"bot-execution-artifacts", BotExecutionArtifactViewSet, basename="bot-execution-artifacts")
router.register(r"social_medias", SocialMediaAccountsCompletedViewSet, basename="socialmedia_completed")
router.register(r"proxy", ProxyViewSet)
router.register(r"pending_bots", TaskPendings)
router.register(r"generate_tasks", AddTaskAllAccounts, basename="generate-tasks")
router.register(r"view_tasks", TaskPendingBotViewSet, basename="view-tasks")
router.register(r"account_messages", SocialMediaMessageViewSet, basename="account-messages")
router.register(r"groups_info", GroupsInfoViewSet, basename="groups-info")
router.register(r"account_groups", SocialMediaAccountGroupViewSet, basename="account-groups")
router.register(r"prospects", ProspectViewSet, basename="prospects")
router.register(r"prospect-posts", ProspectPostViewSet, basename="prospect-posts")
router.register(r"prospect-comments", ProspectCommentViewSet, basename="prospect-comments")
router.register(r"prospect-classifications", ProspectReplyClassificationViewSet, basename="prospect-classifications")
router.register(r"alerts", AlertLogViewSet, basename="alerts")
router.register(r"blacklist", BlacklistAccountViewSet, basename="blacklist")
router.register(r"quote-answers", QuoteAnswerViewSet, basename="quote-answers")
router.register(r"campaign-info", CampaignInfoViewSet, basename="campaign-info")
router.register(r"used-for-recommendation-or-review", UsedForRecommendationOrReviewViewSet, basename="used-for-recommendation-or-review")
router.register(r"prospectation-groups", ProspectationGroupsViewSet, basename="prospectation-groups")

prospecting_router = DefaultRouter()
prospecting_router.register(r"campaigns", InstagramProspectingCampaignViewSet, basename="instagram-prospecting-campaigns")
prospecting_router.register(r"prospects", InstagramProspectViewSet, basename="instagram-prospects")
prospecting_router.register(r"prospect-posts", InstagramProspectPostViewSet, basename="instagram-prospect-posts")
prospecting_router.register(r"prospect-interactions", InstagramProspectInteractionViewSet, basename="instagram-prospect-interactions")
prospecting_router.register(r"follow-up-alerts", InstagramFollowUpAlertViewSet, basename="instagram-follow-up-alerts")

router2 = DefaultRouter()
router2.register(r"generate_tasks", AddTaskAllAccountsV2, basename="generate-tasks-V2")
router2.register(r"pending_bots", PendingBotsV2ViewSet, basename="pending-bots-v2")

urlpatterns = [
    path("", include(router.urls)),
    path("prospecting/", include(prospecting_router.urls)),
    path("v2/", include(router2.urls)),
    path("health/", health_check, name="health_check"),
    path("connections/", list_connected_machines, name="list_connections"),
    path("orchestrator/instagram/catalog/", instagram_catalog, name="orchestrator-instagram-catalog"),
    path("orchestrator/instagram/tasks/claim/", claim_instagram_task, name="orchestrator-instagram-task-claim"),
]

