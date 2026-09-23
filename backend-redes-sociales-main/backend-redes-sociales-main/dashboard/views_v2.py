"""MODULO DE VISTAS"""
import logging
import time

from datetime import timezone
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters import rest_framework as django_filters
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters

from .models.social_media_account import SocialMediaAccount
from .models.task_bot import TaskBot
from .pagination import PendingBotPagination

from .serializers import (
    CreateTasksSerializer,
    PendingBotQuerySerializer,
    PendingBotSerializer,
)

logger = logging.getLogger(__name__)


class PendingBotsV2ViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    default_status_processes = ("EP", "EQ")
    serializer_class = PendingBotSerializer
    pagination_class = PendingBotPagination

    def get_queryset(self):
        return TaskBot.objects.select_related(
            "social_media_account__bot_personality",
            "social_media_account__owner",
            "social_media_account__proxy",
            "social_media_account__campaign_info",
        ).order_by("start_date", "id")

    def filter_bot_queryset(
        self,
        queryset,
        *,
        bot_name,
        status_process=None,
        account_id=None,
    ):
        queryset = queryset.filter(bot_executor=bot_name)
        if status_process:
            queryset = queryset.filter(status_process=status_process)
        else:
            queryset = queryset.filter(
                status_process__in=self.default_status_processes
            )
        if account_id:
            queryset = queryset.filter(social_media_account_id=account_id)
        return queryset

    @swagger_auto_schema(
        tags=["Tasks - Version 2"],
        operation_description=(
            "Lista las tareas EP y EQ asignadas al bot indicado. "
            "bot_name es obligatorio; status_process solo es necesario "
            "para consultar explícitamente otro estado."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="bot_name",
                in_=openapi.IN_QUERY,
                description="Nombre exacto almacenado en TaskBot.bot_executor.",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                name="status_process",
                in_=openapi.IN_QUERY,
                description="Estado opcional; sin este parámetro se usan EP y EQ.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                name="account_id",
                in_=openapi.IN_QUERY,
                description="ID de cuenta opcional.",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name="page_size",
                in_=openapi.IN_QUERY,
                description="Resultados por página; máximo 100.",
                type=openapi.TYPE_INTEGER,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        started_at = time.monotonic()
        result_count = 0
        bot_name = None
        status_process = None
        account_id = None
        user_id = getattr(request.user, "pk", None)
        logger.info("pending_bots_v2 START user_id=%s", user_id)

        try:
            query_serializer = PendingBotQuerySerializer(data=request.query_params)
            query_serializer.is_valid(raise_exception=True)
            query_params = query_serializer.validated_data

            bot_name = query_params["bot_name"]
            status_process = query_params.get("status_process")
            account_id = query_params.get("account_id")

            queryset = self.filter_bot_queryset(
                self.get_queryset(),
                bot_name=bot_name,
                status_process=status_process,
                account_id=account_id,
            )
            queryset = self.filter_queryset(queryset)

            page = self.paginate_queryset(queryset)
            if page is not None:
                result_count = len(page)
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            result_count = len(serializer.data)
            return Response(serializer.data)
        except APIException:
            logger.warning(
                "pending_bots_v2 REJECTED user_id=%s bot_name=%s",
                user_id,
                bot_name,
            )
            raise
        except Exception:
            logger.exception(
                "pending_bots_v2 ERROR user_id=%s bot_name=%s",
                user_id,
                bot_name,
            )
            raise
        finally:
            elapsed = time.monotonic() - started_at
            logger.info(
                (
                    "pending_bots_v2 END elapsed=%.3fs results=%d user_id=%s "
                    "bot_name=%s status_filter=%s account_filter=%s"
                ),
                elapsed,
                result_count,
                user_id,
                bot_name,
                bool(status_process),
                account_id,
            )


class AddTaskAllAccountsV2(viewsets.ViewSet):
    """
    Una vista especializada para crear una tarea para cada cuenta de redes sociales.
    """

    @swagger_auto_schema(
        tags=["Tasks - Version 2"],
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

        affected_accounts = [
            TaskBot.objects.create(
                task_type=task_type,
                bot_executor="NONE",
                status_process="SP",
                comment={"status": "Pending..."},
                social_media_account=account,
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
