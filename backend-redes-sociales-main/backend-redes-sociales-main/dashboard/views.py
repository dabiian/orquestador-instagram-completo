"""MODULO DE VISTAS"""
from datetime import timezone
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters
from rest_framework import filters as rest_filter
from rest_framework.response import Response
from django.db.models import Q
from django.db import IntegrityError
from .models.active_websocket_connection import ActiveWebSocketConnection

from dashboard.pagination import SocialMediaMessagePagination

from .models.bot_execution import BotExecutionArtifact, BotExecutionReport
from .models.social_media_platform import SocialMediaPlatform
from .models.account_owner import AccountOwner
from .models.social_media_account import SocialMediaAccount
from .models.task_type import TaskType
from .models.task_bot import TaskBot
from .models.proxy import Proxy
from .models.Bot_personality import BotPersonality
from.models.social_media_messages import SocialMediaMessage
from .models.groups_info import GroupsInfo
from .models.social_media_account_group import SocialMediaAccountGroup
from .models.campaign_info import CampaignInfo
from .models.prospect import (
    AlertLog,
    BlacklistAccount,
    Prospect,
    ProspectComment,
    ProspectPost,
    QuoteAnswer,
)
from .models.used_for_recommendation_or_review import UsedForRecommendationOrReview
from .models.prospectation_groups import ProspectationGroups

from .serializers import (
    BotExecutionArtifactSerializer,
    BotExecutionReportSerializer,
    BotExecutionStepSerializer,
    BotPersonalitiesSerializer,
    SocialMediaPlatformsSerializer,
    AccountOwnersSerializer,
    SocialMediaAccountsSerializer,
    SocialMediaAccountCreateSerializer,
    TaskTypeSerializer,
    TaskBotsSerializer,
    SocialMediaAccountsSerializer2,
    ProxySerializer,
    TaskBotsSerializer2,
    CreateTasksSerializer,
    TaskBotsPendingSerializer,
    SocialMediaMessageSerializer,
    GroupsInfoSerializer,
    SocialMediaAccountGroupSerializer,
    AlertLogSerializer,
    BlacklistAccountSerializer,
    ProspectCommentSerializer,
    ProspectDetailSerializer,
    ProspectPostSerializer,
    ProspectReplyClassificationSerializer,
    ProspectSerializer,
    QuoteAnswerSerializer,
    CampaignInfoSerializer,
    UsedForRecommendationOrReviewSerializer,
    ProspectGroupsSerializer,
    )


class BotPersonalitiesViewSet(viewsets.ModelViewSet):
    queryset = BotPersonality.objects.all()
    serializer_class = BotPersonalitiesSerializer
    permission_classes = [AllowAny]


class SocialMediaPlatformsViewSet(viewsets.ModelViewSet):
    queryset = SocialMediaPlatform.objects.all()
    serializer_class = SocialMediaPlatformsSerializer
    permission_classes = [AllowAny]


class AccountOwnersViewSet(viewsets.ModelViewSet):
    queryset = AccountOwner.objects.all()
    serializer_class = AccountOwnersSerializer
    permission_classes = [AllowAny]


class SocialMediaAccountsViewSet(viewsets.ModelViewSet):
    queryset = SocialMediaAccount.objects.all()
    serializer_class = SocialMediaAccountsSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = SocialMediaAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        response_serializer = SocialMediaAccountsSerializer(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        method="patch",
        operation_description="Actualiza la cookie de una cuenta de redes sociales específica.",
        request_body=openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "domain": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Dominio de la cookie"
                    ),
                    "httpOnly": openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        description="Indica si la cookie es HTTPOnly",
                    ),
                    "name": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Nombre de la cookie"
                    ),
                    "path": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Ruta de la cookie"
                    ),
                    "sameSite": openapi.Schema(
                        type=openapi.TYPE_STRING,
                        description="Atributo SameSite de la cookie",
                    ),
                    "secure": openapi.Schema(
                        type=openapi.TYPE_BOOLEAN,
                        description="Indica si la cookie es segura",
                    ),
                    "value": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Valor de la cookie"
                    ),
                    "expiry": openapi.Schema(
                        type=openapi.TYPE_INTEGER,
                        format="int64",
                        description="Tiempo de expiración de la cookie",
                        nullable=True,
                    ),
                },
            ),
            description="Array de objetos cookie con sus atributos específicos",
        ),
        responses={
            200: openapi.Response(description="Cookie actualizada correctamente."),
            400: openapi.Response(description="Datos de la cookie inválidos."),
            404: openapi.Response(description="Cuenta no encontrada."),
        },
    )
    @action(detail=True, methods=["patch"])
    def update_cookie(self, request, pk=None):
        social_media_account = self.get_object()

        # Suponiendo que request.data es una lista de cookies
        cookie_data = request.data

        if cookie_data and isinstance(cookie_data, list):
            # Aquí actualizas solo el campo cookie
            social_media_account.other_credentials["cookie"] = cookie_data
            social_media_account.save(update_fields=["other_credentials"])
            return Response({"status": "cookie updated"}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Invalid cookie data"}, status=status.HTTP_400_BAD_REQUEST
            )


class TaskTypeFilter(django_filters.FilterSet):
    platform_id = django_filters.NumberFilter(field_name="platform__id")

    class Meta:
        model = TaskType
        fields = ["platform_id"]


class TaskTypeViewSet(viewsets.ModelViewSet):
    queryset = TaskType.objects.all().order_by("create_date")
    serializer_class = TaskTypeSerializer
    permission_classes = [AllowAny]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TaskTypeFilter

    @swagger_auto_schema(
        operation_description="Listar todos los tipos de tareas, o filtrar por ID de plataforma.",
        manual_parameters=[
            openapi.Parameter(
                name="platform_id",
                in_=openapi.IN_QUERY,
                description="ID de la plataforma para filtrar los tipos de tareas.",
                type=openapi.TYPE_INTEGER,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class TaskBotsViewSet(viewsets.ModelViewSet):
    queryset = TaskBot.objects.all()
    serializer_class = TaskBotsSerializer
    permission_classes = [AllowAny]


class BotExecutionReportViewSet(viewsets.ModelViewSet):
    serializer_class = BotExecutionReportSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = (
            BotExecutionReport.objects.select_related("task_bot")
            .prefetch_related("steps", "artifacts")
            .order_by("-created_at")
        )

        task_bot_id = self.request.query_params.get("task_bot_id")
        status_param = self.request.query_params.get("status")
        bot_executor = self.request.query_params.get("bot_executor")

        if task_bot_id:
            queryset = queryset.filter(task_bot_id=task_bot_id)

        if status_param:
            queryset = queryset.filter(status=status_param)

        if bot_executor:
            queryset = queryset.filter(bot_executor=bot_executor)

        return queryset

    @action(detail=True, methods=["post"], url_path="steps")
    def create_step(self, request, pk=None):
        report = self.get_object()
        serializer = BotExecutionStepSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(report=report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BotExecutionArtifactViewSet(viewsets.ModelViewSet):
    serializer_class = BotExecutionArtifactSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = (
            BotExecutionArtifact.objects.select_related("report", "step")
            .order_by("-created_at")
        )

        report_id = self.request.query_params.get("report_id")
        step_id = self.request.query_params.get("step_id")
        artifact_type = self.request.query_params.get("artifact_type")

        if report_id:
            queryset = queryset.filter(report_id=report_id)

        if step_id:
            queryset = queryset.filter(step_id=step_id)

        if artifact_type:
            queryset = queryset.filter(artifact_type=artifact_type)

        return queryset


class ProxyViewSet(viewsets.ModelViewSet):
    queryset = Proxy.objects.all()
    serializer_class = ProxySerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def available(self, request):
        available_proxies = self.get_queryset().filter(socialmediaaccount__isnull=True)
        serializer = self.get_serializer(available_proxies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SocialMediaAccountsCompletedViewSet(viewsets.ModelViewSet):
    queryset = SocialMediaAccount.objects.select_related(
        "bot_personality", "owner", "proxy", "campaign_info"
    ).all()
    serializer_class = SocialMediaAccountsSerializer2
    permission_classes = [AllowAny]

    def get_queryset(self):
        return self.queryset.prefetch_related("bot_personality")


class TaskPendings(viewsets.ModelViewSet):
    queryset = TaskBot.objects.all()
    serializer_class = TaskBotsSerializer2

    def get_queryset(self):
        # Realizar una "carga anticipada" (eager load) de los datos relacionados
        # para mejorar el rendimiento y reducir el número de consultas a la base de datos.
        return TaskBot.objects.select_related(
            "social_media_account__bot_personality",
            "social_media_account__owner",
            "social_media_account__proxy",
            "social_media_account__campaign_info"

        )


# necesito que por cada cuenta crees un registro http://127.0.0.1:8000/api/task_bots/
# para agragarle tareas a las cuents
class AddTaskAllAccounts(viewsets.ViewSet):
    """
    Una vista especializada para crear una tarea para cada cuenta de redes sociales.
    """

    @swagger_auto_schema(
        method="post",
        responses={
            201: "Tareas creadas exitosamente",
            400: "ID de tipo de tarea inválido",
        },
        operation_description="Crear una tarea para cada cuenta de redes sociales o para una cuenta específica por su ID.",
        request_body=CreateTasksSerializer,
        manual_parameters=[
            openapi.Parameter(
                name="social_media_account_id",
                in_=openapi.IN_QUERY,
                description="ID de la cuenta de redes sociales para la cual crear la tarea (opcional)",
                type=openapi.TYPE_INTEGER,
            ),
        ],
    )
    @action(detail=False, methods=["post"])
    def create_tasks_for_all_accounts(self, request):
        serializer = CreateTasksSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        task_type = serializer.validated_data["task_type_id"]
        custom_task_data = serializer.validated_data.get("custom_task")

        if custom_task_data is None:
            custom_task_data = {}

        social_media_account_id = request.query_params.get("social_media_account_id")

        accounts_to_process = (
            SocialMediaAccount.objects.filter(id=social_media_account_id)
            if social_media_account_id
            else SocialMediaAccount.objects.all()
        )

        if not accounts_to_process.exists() and social_media_account_id:
            return Response(
                {
                    "error": "La cuenta de redes sociales con ID {} no existe".format(
                        social_media_account_id
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Ejemplo del objeto
        # custom_task
        #     {
        #         "type": "page, muro, all",
        #         "post": "mensaje del post",
        #         "links_image": ["link", "link"],
        #     },

        affected_accounts = [
            TaskBot.objects.create(
                task_type=task_type,
                bot_executor="NONE",
                status_process="SP",
                comment={"status": "Pending..."},
                social_media_account=account,
                custom_task=custom_task_data,
            ).social_media_account.id
            for account in accounts_to_process
        ]

        message = (
            "Tarea creada correctamente para la cuenta con ID: {}".format(
                social_media_account_id
            )
            if social_media_account_id
            else "Tareas creadas correctamente"
        )

        return Response(
            {
                "message": message,
                "affected_accounts_count": len(affected_accounts),
                "affected_accounts": affected_accounts,
            },
            status=status.HTTP_201_CREATED,
        )


class TaskBotFilter(filters.FilterSet):
    start_date = filters.DateTimeFilter(field_name="start_date", lookup_expr="gte")
    end_date = filters.DateTimeFilter(field_name="end_date", lookup_expr="lte")
    status_process = filters.CharFilter(field_name="status_process")

    class Meta:
        model = TaskBot
        fields = ["start_date", "end_date", "status_process"]


class TaskPendingBotViewSet(viewsets.ModelViewSet):
    queryset = TaskBot.objects.all()
    serializer_class = TaskBotsPendingSerializer

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name="start_date",
                in_=openapi.IN_QUERY,
                description="Fecha de inicio para filtrar las tareas pendientes (formato: YYYY-MM-DDTHH:MM:SS)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                default=timezone.now().isoformat(),
            ),
            openapi.Parameter(
                name="start_date_end",
                in_=openapi.IN_QUERY,
                description="Fecha de fin para filtrar las tareas pendientes (formato: YYYY-MM-DDTHH:MM:SS)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                default=timezone.now().isoformat(),
            ),
            openapi.Parameter(
                name="status_process",
                in_=openapi.IN_QUERY,
                description="Estado del proceso para filtrar las tareas pendientes",
                type=openapi.TYPE_STRING,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        start_date = request.query_params.get("start_date")
        start_date_end = request.query_params.get("start_date_end")
        status_process = request.query_params.get("status_process")

        queryset = TaskBot.objects.all()

        if start_date:
            queryset = queryset.filter(start_date__date=start_date)

        if start_date_end:
            queryset = queryset.filter(start_date__date__lte=start_date_end)

        if status_process:
            queryset = queryset.filter(status_process=status_process)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
class SocialMediaMessageViewSet(viewsets.ModelViewSet):
    serializer_class = SocialMediaMessageSerializer
    pagination_class = SocialMediaMessagePagination

    # filtros
    filter_backends = [
        DjangoFilterBackend,
        rest_filter.SearchFilter,
        rest_filter.OrderingFilter,
    ]
    filterset_fields = ["account_id", "status", "category"]
    search_fields = ["message_text", "category"]
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = SocialMediaMessage.objects.all()

        try:
            qs = qs.select_related("account")
        except Exception:
            pass

        return qs

class GroupsInfoViewSet(viewsets.ModelViewSet):
    queryset = GroupsInfo.objects.all()
    serializer_class = GroupsInfoSerializer
    
    filter_backends = [
        DjangoFilterBackend,
        rest_filter.SearchFilter,
        rest_filter.OrderingFilter,
    ]
    
    filterset_fields = ["status", "group_url"]
    search_fields = ["group_name", "description", "rules", "group_url"]
    ordering_fields = ["created_at", "id"]

    @swagger_auto_schema(
        operation_description="Listar grupos de información y permitir filtrado por group_url.",
        manual_parameters=[
            openapi.Parameter(
                name="group_url",
                in_=openapi.IN_QUERY,
                description="Filtrar por la URL exacta del grupo.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                name="status",
                in_=openapi.IN_QUERY,
                description="Filtrar por estado del grupo.",
                type=openapi.TYPE_STRING,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        return qs
    
class SocialMediaAccountGroupFilter(django_filters.FilterSet):
    account_id = django_filters.NumberFilter(field_name="account__id")
    is_prospection = django_filters.BooleanFilter(field_name="is_prospection")

    class Meta:
        model = SocialMediaAccountGroup
        fields = ["account_id", "group_id", "is_prospection"]


class SocialMediaAccountGroupViewSet(viewsets.ModelViewSet):
    queryset = SocialMediaAccountGroup.objects.all()
    serializer_class = SocialMediaAccountGroupSerializer
    permission_classes = [AllowAny]
    
    filter_backends = [
        DjangoFilterBackend,
        rest_filter.SearchFilter,
        rest_filter.OrderingFilter,
    ]
    
    filterset_class = SocialMediaAccountGroupFilter
    search_fields = []
    ordering_fields = ["id"]
    
    @swagger_auto_schema(
        operation_description="Listar las relaciones entre cuentas de redes sociales y grupos.",
        manual_parameters=[
            openapi.Parameter(
                name="account_id",
                in_=openapi.IN_QUERY,
                description="ID de la cuenta de redes sociales para filtrar sus grupos asociados.",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name="group_id",
                in_=openapi.IN_QUERY,
                description="ID del grupo para filtrar sus cuentas asociadas.",
                type=openapi.TYPE_INTEGER,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    def get_queryset(self):
        qs = super().get_queryset()
        return qs
    
class ProspectViewSet(viewsets.ModelViewSet):
    queryset = (
        Prospect.objects.select_related("discovered_by_account")
        .prefetch_related("posts", "comments", "classifications", "alerts")
        .order_by("-created_at")
    )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProspectDetailSerializer
        return ProspectSerializer

    def get_queryset(self):
        queryset = (
            Prospect.objects.select_related("discovered_by_account")
            .prefetch_related("posts", "comments", "classifications", "alerts")
            .order_by("-created_at")
        )

        params = self.request.GET

        status_param = params.get("status")
        is_blacklisted = params.get("is_blacklisted")
        external_account_id = params.get("external_account_id")
        profile_url = params.get("profile_url")
        id = params.get("id")
        discovered_by_account = params.get("discovered_by_account")
        account_name = params.get("account_name")
        search = params.get("search")

        if status_param:
            queryset = queryset.filter(status=status_param)
        if id:
            queryset = queryset.filter(id = id)
        if is_blacklisted is not None:
            is_blacklisted_bool = str(is_blacklisted).lower() in ["1", "true", "yes"]
            queryset = queryset.filter(is_blacklisted=is_blacklisted_bool)

        if external_account_id:
            queryset = queryset.filter(external_account_id=external_account_id)

        if profile_url:
            queryset = queryset.filter(profile_url=profile_url)

        if discovered_by_account:
            queryset = queryset.filter(discovered_by_account_id=discovered_by_account)

        if account_name:
            queryset=queryset.filter(account_name=account_name)
        
        if search:
            queryset = queryset.filter(
                Q(account_name__icontains=search)
                | Q(external_account_id__icontains=search)
                | Q(profile_url__icontains=search)
            )

        return queryset
    @action(detail=True, methods=["post"])
    def set_status(self, request, pk=None):
        prospect = self.get_object()
        new_status = request.data.get("status")

        valid_statuses = dict(Prospect.STATUS_CHOICES).keys()
        if new_status not in valid_statuses:
            return Response(
                {"detail": "status inválido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prospect.status = new_status

        if new_status == "RESPONDED":
            prospect.last_response_at = timezone.now()

        if new_status == "ALERTED":
            prospect.last_alert_at = timezone.now()

        if new_status == "BLACKLISTED":
            prospect.is_blacklisted = True

        prospect.save()

        return Response(ProspectSerializer(prospect).data)

    @action(detail=True, methods=["post"])
    def blacklist(self, request, pk=None):
        prospect = self.get_object()

        reason = request.data.get("reason")
        source = request.data.get("source")
        score = request.data.get("score", prospect.competitor_score)
        matched_layers = request.data.get("matched_layers", [])
        evidence = request.data.get("evidence", {})

        blacklist_obj, _ = BlacklistAccount.objects.update_or_create(
            external_account_id=prospect.external_account_id,
            defaults={
                "platform": "facebook",
                "account_name": prospect.account_name,
                "profile_url": prospect.profile_url,
                "source": source,
                "score": score or 0,
                "matched_layers": matched_layers,
                "evidence": evidence,
                "reason": reason,
            },
        )

        prospect.is_blacklisted = True
        prospect.blacklist_reason = reason
        prospect.status = "BLACKLISTED"
        prospect.competitor_score = score or 0
        prospect.save()

        return Response(
            {
                "prospect": ProspectSerializer(prospect).data,
                "blacklist": BlacklistAccountSerializer(blacklist_obj).data,
            }
        )

    @action(detail=True, methods=["post"])
    def unblacklist(self, request, pk=None):
        prospect = self.get_object()

        BlacklistAccount.objects.filter(
            external_account_id=prospect.external_account_id
        ).delete()

        prospect.is_blacklisted = False
        prospect.blacklist_reason = None

        if prospect.status == "BLACKLISTED":
            prospect.status = "NEW"

        prospect.save()

        return Response(ProspectSerializer(prospect).data)

    @action(detail=True, methods=["post"])
    def upsert_quote_answer(self, request, pk=None):
        prospect = self.get_object()

        quote_answer, _ = QuoteAnswer.objects.update_or_create(
            prospect=prospect,
            defaults={
                "q1_type_of_cleaning": request.data.get("q1_type_of_cleaning"),
                "q2_space_size": request.data.get("q2_space_size"),
                "q3_needed_date": request.data.get("q3_needed_date"),
                "q4_condition": request.data.get("q4_condition"),
                "min_answers_ready_for_alert": request.data.get(
                    "min_answers_ready_for_alert",
                    False,
                ),
            },
        )

        return Response(QuoteAnswerSerializer(quote_answer).data)


class ProspectPostViewSet(viewsets.ModelViewSet):
    queryset = ProspectPost.objects.select_related("prospect").order_by("-created_at")
    serializer_class = ProspectPostSerializer

    def get_queryset(self):
        queryset = (
            ProspectPost.objects.select_related("prospect")
            .order_by("-created_at")
        )

        params = self.request.GET

        prospect_external_account_id = params.get("prospect_external_account_id")
        prospect_profile_url = params.get("prospect_profile_url")
        id = params.get('id')
        used_for_intro_comment = params.get("used_for_intro_comment")
        external_post_id = params.get("external_post_id")
        post_url = params.get("post_url")

        if prospect_external_account_id:
            queryset = queryset.filter(
                prospect__external_account_id=prospect_external_account_id
            )
        if id:
            queryset = queryset.filter(id=id)

        if prospect_profile_url:
            queryset = queryset.filter(
                prospect__profile_url=prospect_profile_url
            )

        if used_for_intro_comment is not None:
            used_bool = str(used_for_intro_comment).lower() in ["1", "true", "yes"]
            queryset = queryset.filter(used_for_intro_comment=used_bool)

        if external_post_id:
            queryset = queryset.filter(external_post_id=external_post_id)

        if post_url:
            queryset = queryset.filter(post_url=post_url)

        return queryset


class ProspectCommentViewSet(viewsets.ModelViewSet):

    serializer_class = ProspectCommentSerializer

    def get_queryset(self):
        queryset = (
            ProspectComment.objects.select_related(
                "prospect",
                "post",
                "bot_account",
                "related_message",
            ).order_by("-created_at")
        )

        params = self.request.GET

        prospect_external_account_id = params.get("prospect_external_account_id")
        prospect_profile_url = params.get("prospect_profile_url")
        post_url = params.get("post_url")
        actor_type = params.get("actor_type")
        comment_kind = params.get("comment_kind")
        related_message_id = params.get("related_message_id")

        if prospect_external_account_id:
            queryset = queryset.filter(
                prospect__external_account_id=prospect_external_account_id
            )

        if prospect_profile_url:
            queryset = queryset.filter(
                prospect__profile_url=prospect_profile_url
            )

        if post_url:
            queryset = queryset.filter(
                post__post_url=post_url
            )

        if actor_type:
            queryset = queryset.filter(actor_type=actor_type)

        if comment_kind:
            queryset = queryset.filter(comment_kind=comment_kind)

        if related_message_id:
            queryset = queryset.filter(related_message_id=related_message_id)

        return queryset


class ProspectReplyClassificationViewSet(viewsets.ModelViewSet):

    serializer_class = ProspectReplyClassificationSerializer

    def get_queryset(self):
        queryset = (
            ProspectComment.objects.select_related(
                "prospect",
                "post",
                "bot_account",
                "related_message",
            ).order_by("-created_at")
        )

        params = self.request.GET

        prospect_external_account_id = params.get("prospect_external_account_id")
        prospect_profile_url = params.get("prospect_profile_url")
        post_url = params.get("post_url")
        actor_type = params.get("actor_type")
        comment_kind = params.get("comment_kind")
        related_message_id = params.get("related_message_id")

        if prospect_external_account_id:
            queryset = queryset.filter(
                prospect__external_account_id=prospect_external_account_id
            )

        if prospect_profile_url:
            queryset = queryset.filter(
                prospect__profile_url=prospect_profile_url
            )

        if post_url:
            queryset = queryset.filter(
                post__post_url=post_url
            )

        if actor_type:
            queryset = queryset.filter(actor_type=actor_type)

        if comment_kind:
            queryset = queryset.filter(comment_kind=comment_kind)

        if related_message_id:
            queryset = queryset.filter(related_message_id=related_message_id)

        return queryset


class AlertLogViewSet(viewsets.ModelViewSet):
    queryset = AlertLog.objects.select_related("prospect", "bot_account").order_by("-created_at")
    serializer_class = AlertLogSerializer

    def get_queryset(self):
        queryset = AlertLog.objects.select_related("prospect", "bot_account").order_by("-created_at")

        prospect_id = self.request.query_params.get("prospect_id")
        event_code = self.request.query_params.get("event_code")
        priority = self.request.query_params.get("priority")
        email_sent = self.request.query_params.get("email_sent")
        whatsapp_sent = self.request.query_params.get("whatsapp_sent")

        if prospect_id:
            queryset = queryset.filter(prospect_id=prospect_id)

        if event_code:
            queryset = queryset.filter(event_code=event_code)

        if priority:
            queryset = queryset.filter(priority=priority)

        if email_sent is not None:
            email_sent_bool = str(email_sent).lower() in ["1", "true", "yes"]
            queryset = queryset.filter(email_sent=email_sent_bool)

        if whatsapp_sent is not None:
            whatsapp_sent_bool = str(whatsapp_sent).lower() in ["1", "true", "yes"]
            queryset = queryset.filter(whatsapp_sent=whatsapp_sent_bool)

        return queryset

    @action(detail=True, methods=["post"])
    def mark_sent(self, request, pk=None):
        alert = self.get_object()

        if "email_sent" in request.data:
            alert.email_sent = bool(request.data.get("email_sent"))

        if "whatsapp_sent" in request.data:
            alert.whatsapp_sent = bool(request.data.get("whatsapp_sent"))

        if "email_message_id" in request.data:
            alert.email_message_id = request.data.get("email_message_id")

        if "whatsapp_message_id" in request.data:
            alert.whatsapp_message_id = request.data.get("whatsapp_message_id")

        alert.sent_at = timezone.now()
        alert.save()

        if alert.prospect_id:
            alert.prospect.last_alert_at = alert.sent_at
            alert.prospect.status = "ALERTED"
            alert.prospect.save(update_fields=["last_alert_at", "status", "updated_at"])

        return Response(AlertLogSerializer(alert).data)


class BlacklistAccountViewSet(viewsets.ModelViewSet):
    queryset = BlacklistAccount.objects.order_by("-created_at")
    serializer_class = BlacklistAccountSerializer

    def get_queryset(self):
        queryset = BlacklistAccount.objects.order_by("-created_at")

        external_account_id = self.request.query_params.get("external_account_id")
        account_name = self.request.query_params.get("account_name")
        source = self.request.query_params.get("source")

        if external_account_id:
            queryset = queryset.filter(external_account_id=external_account_id)

        if account_name:
            queryset = queryset.filter(account_name__icontains=account_name)

        if source:
            queryset = queryset.filter(source=source)

        return queryset


class QuoteAnswerViewSet(viewsets.ModelViewSet):
    queryset = QuoteAnswer.objects.select_related("prospect").order_by("-created_at")
    serializer_class = QuoteAnswerSerializer

    def get_queryset(self):
        queryset = QuoteAnswer.objects.select_related("prospect").order_by("-created_at")

        params = self.request.GET

        prospect_external_account_id = params.get("prospect_external_account_id")
        prospect_profile_url = params.get("prospect_profile_url")
        min_answers_ready_for_alert = params.get("min_answers_ready_for_alert")

        if prospect_external_account_id:
            queryset = queryset.filter(
                prospect__external_account_id=prospect_external_account_id
            )

        if prospect_profile_url:
            queryset = queryset.filter(
                prospect__profile_url=prospect_profile_url
            )

        if min_answers_ready_for_alert is not None:
            ready_bool = str(min_answers_ready_for_alert).lower() in ["1", "true", "yes"]
            queryset = queryset.filter(min_answers_ready_for_alert=ready_bool)

        return queryset
    
class CampaignInfoViewSet(viewsets.ModelViewSet):
    queryset = CampaignInfo.objects.all().order_by("-created_at")
    serializer_class = CampaignInfoSerializer
    permission_classes = [AllowAny]

    filter_backends = [DjangoFilterBackend, rest_filter.SearchFilter, rest_filter.OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["campaign_name", "category", "language", "phone_number", "alt_phone_number", "webpage_url", "fanpage_url"]
    ordering_fields = ["id", "campaign_name", "category", "language", "status", "created_at"]
    ordering = ["-created_at"]

    @swagger_auto_schema(
        operation_summary="Listar campañas",
        operation_description="Obtiene el listado de campañas. Permite filtrar por status, buscar y ordenar.",
        manual_parameters=[
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filtrar por estado. Ejemplo: active",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Buscar por campaign_name, category, language, phone_number, alt_phone_number, webpage_url o fanpage_url",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "ordering",
                openapi.IN_QUERY,
                description="Ordenar por: id, campaign_name, category, language, status, created_at. Usa - para descendente. Ej: -created_at",
                type=openapi.TYPE_STRING
            ),
        ],
        responses={200: CampaignInfoSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Obtener campaña por ID",
        operation_description="Retorna el detalle de una campaña por su ID.",
        responses={200: CampaignInfoSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Crear campaña",
        operation_description="Crea un nuevo registro de campaña.",
        request_body=CampaignInfoSerializer,
        responses={201: CampaignInfoSerializer()}
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar campaña completa",
        operation_description="Actualiza todos los campos de una campaña.",
        request_body=CampaignInfoSerializer,
        responses={200: CampaignInfoSerializer()}
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar campaña parcial",
        operation_description="Actualiza parcialmente una campaña.",
        request_body=CampaignInfoSerializer,
        responses={200: CampaignInfoSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Eliminar campaña",
        operation_description="Elimina una campaña por ID.",
        responses={204: "Eliminado correctamente"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
class UsedForRecommendationOrReviewViewSet(viewsets.ModelViewSet):
    queryset = UsedForRecommendationOrReview.objects.select_related("account").all().order_by("-updated_at")
    serializer_class = UsedForRecommendationOrReviewSerializer

    lookup_field = "account_id"
    lookup_url_kwarg = "account_id"

    @swagger_auto_schema(
        operation_summary="Listar registros",
        operation_description="Obtiene todos los registros de uso para recommendation o review.",
        responses={200: UsedForRecommendationOrReviewSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Obtener registro por account_id",
        operation_description="Obtiene un registro específico usando el ID de la cuenta.",
        responses={200: UsedForRecommendationOrReviewSerializer()}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Crear registro",
        operation_description="Crea un nuevo registro asociado a una cuenta. Solo se permite uno por account_id.",
        request_body=UsedForRecommendationOrReviewSerializer,
        responses={
            201: UsedForRecommendationOrReviewSerializer(),
            400: "Solicitud inválida"
        }
    )
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {"detail": "Ya existe un registro para esta cuenta."},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_summary="Actualizar registro completo por account_id",
        operation_description="Actualiza completamente un registro existente usando el ID de la cuenta.",
        request_body=UsedForRecommendationOrReviewSerializer,
        responses={
            200: UsedForRecommendationOrReviewSerializer(),
            400: "Solicitud inválida"
        }
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        try:
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except IntegrityError:
            return Response(
                {"detail": "Ya existe un registro para esta cuenta."},
                status=status.HTTP_400_BAD_REQUEST
            )

    @swagger_auto_schema(
        operation_summary="Actualizar registro parcial por account_id",
        operation_description="Actualiza parcialmente un registro existente usando el ID de la cuenta.",
        request_body=UsedForRecommendationOrReviewSerializer,
        responses={
            200: UsedForRecommendationOrReviewSerializer(),
            400: "Solicitud inválida"
        }
    )
    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Eliminar registro por account_id",
        operation_description="Elimina un registro usando el ID de la cuenta.",
        responses={204: "Registro eliminado correctamente"}
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
def health_check(request):
    return JsonResponse({
        "status": "ok"
    })

def list_connected_machines(request):
    import logging
    logger = logging.getLogger(__name__)
    
    # Obtener todas las conexiones activas de la base de datos
    connections = ActiveWebSocketConnection.objects.all()
    connections_data = [
        {
            'room': conn.room,
            'connected_at': str(conn.connected_at.timestamp())
        } for conn in connections
    ]
    
    print(f"DEBUG VISTA: Conexiones activas en BD: {connections_data}")
    print(f"DEBUG VISTA: cantidad de conexiones: {len(connections_data)}")
    logger.info(f"Conexiones activas en este momento: {connections_data}")
    return JsonResponse({'active_connections': connections_data})

class ProspectationGroupsViewSet(viewsets.ModelViewSet):
    queryset = ProspectationGroups.objects.prefetch_related("campaigns").all().distinct().order_by("-id")
    serializer_class = ProspectGroupsSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        # Accept common aliases for campaign filter in query params.
        campaign_id = (
            params.get("campaigns_id")
            or params.get("campaign_ids")
            or params.get("campaigns__id")
        )
        group_url = params.get("group_url")

        if campaign_id:
            queryset = queryset.filter(campaigns__id=campaign_id)

        if group_url:
            queryset = queryset.filter(group_url=group_url)

        return queryset

    filter_backends = [DjangoFilterBackend, rest_filter.SearchFilter, rest_filter.OrderingFilter]
    filterset_fields = ["service_category", "city", "group_url", "campaigns__id"]
    search_fields = ["group_name", "group_url", "service_category", "city", "campaigns__campaign_name"]
    ordering_fields = ["id", "group_name", "service_category", "city", "campaigns__campaign_name"]
    ordering = ["-id"]

    @swagger_auto_schema(
        operation_summary="Listar grupos de prospectación",
        operation_description="Obtiene el listado de grupos de prospectación. Permite filtrar por categoría de servicio, ciudad, ID de campaña, buscar por nombre, URL, categoría, ciudad o nombre de campaña, y ordenar por diferentes campos.",
        manual_parameters=[
            openapi.Parameter(
                "service_category",
                openapi.IN_QUERY,
                description="Filtrar por categoría de servicio. Ejemplo: limpieza",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "city",
                openapi.IN_QUERY,
                description="Filtrar por ciudad. Ejemplo: Bogotá",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "campaigns_id",
                openapi.IN_QUERY,
                description="Filtrar por ID de campaña asociada (alias soportados: campaign_ids, campaigns__id).",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                "group_url",
                openapi.IN_QUERY,
                description="Filtrar por URL exacta del grupo.",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Buscar por group_name, group_url, service_category, city o campaigns__campaign_name",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "ordering",
                openapi.IN_QUERY,
                description="Ordenar por: id, group_name, service_category, city, campaigns__campaign_name. Usa - para descendente. Ej: -id",
                type=openapi.TYPE_STRING
            ),
        ],
        responses={200: ProspectGroupsSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
