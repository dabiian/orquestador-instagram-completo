from rest_framework import serializers
from drf_yasg import openapi
import hashlib
import json
from zoneinfo import ZoneInfo

from django.db import IntegrityError
from django.db.models import Q

from .models.bot_execution import (
    BotExecutionArtifact,
    BotExecutionReport,
    BotExecutionStep,
)
from .models.social_media_platform import SocialMediaPlatform
from .models.account_owner import AccountOwner
from .models.social_media_account import SocialMediaAccount
from .models.task_type import TaskType
from .models.task_bot import TaskBot
from .models.proxy import Proxy
from .models.Bot_personality import BotPersonality
from .models.social_media_messages import SocialMediaMessage
from .models.groups_info import GroupsInfo
from .models.social_media_account_group import SocialMediaAccountGroup
from .models.campaign_info import CampaignInfo
from .models.prospect import (
    AlertLog,
    BlacklistAccount,
    Prospect,
    ProspectComment,
    ProspectPost,
    ProspectReplyClassification,
    QuoteAnswer,
)
from .models.used_for_recommendation_or_review import UsedForRecommendationOrReview
from .models.prospectation_groups import CampaignProspectationGroup, ProspectationGroups


class MultipartJSONField(serializers.JSONField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            if not data.strip():
                return {}
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Debe ser un JSON válido.")

        return super().to_internal_value(data)


class BotExecutionStepSerializer(serializers.ModelSerializer):
    metadata = MultipartJSONField(required=False)

    class Meta:
        model = BotExecutionStep
        fields = [
            "id",
            "report",
            "name",
            "status",
            "order",
            "message",
            "metadata",
            "started_at",
            "finished_at",
            "duration_ms",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "report", "created_at", "updated_at"]


class BotExecutionArtifactSerializer(serializers.ModelSerializer):
    report_id = serializers.PrimaryKeyRelatedField(
        source="report",
        queryset=BotExecutionReport.objects.all(),
        required=False,
        write_only=True,
    )
    step_id = serializers.PrimaryKeyRelatedField(
        source="step",
        queryset=BotExecutionStep.objects.select_related("report").all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    file_url = serializers.SerializerMethodField(read_only=True)
    metadata = MultipartJSONField(required=False)

    class Meta:
        model = BotExecutionArtifact
        fields = [
            "id",
            "report",
            "report_id",
            "step",
            "step_id",
            "artifact_type",
            "file",
            "file_url",
            "original_filename",
            "content_type",
            "size_bytes",
            "metadata",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "report",
            "step",
            "file_url",
            "original_filename",
            "content_type",
            "size_bytes",
            "created_at",
        ]

    def get_file_url(self, obj):
        if not obj.file:
            return None

        url = obj.file.url
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)

        return url

    def validate(self, attrs):
        report = attrs.get("report")
        step = attrs.get("step")

        if not report and not step:
            raise serializers.ValidationError(
                {"report_id": "Debe enviar report_id o step_id."}
            )

        if step and report and step.report_id != report.id:
            raise serializers.ValidationError(
                {"step_id": "El step_id no pertenece al report_id enviado."}
            )

        if step and not report:
            attrs["report"] = step.report

        return attrs

    def create(self, validated_data):
        uploaded_file = validated_data.get("file")

        if uploaded_file:
            validated_data["original_filename"] = uploaded_file.name
            validated_data["content_type"] = getattr(uploaded_file, "content_type", None)
            validated_data["size_bytes"] = uploaded_file.size

        return super().create(validated_data)


class BotExecutionReportSerializer(serializers.ModelSerializer):
    task_bot_id = serializers.PrimaryKeyRelatedField(
        source="task_bot",
        queryset=TaskBot.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    steps = BotExecutionStepSerializer(many=True, read_only=True)
    artifacts = BotExecutionArtifactSerializer(many=True, read_only=True)
    metadata = MultipartJSONField(required=False)

    class Meta:
        model = BotExecutionReport
        fields = [
            "id",
            "task_bot",
            "task_bot_id",
            "bot_executor",
            "status",
            "summary",
            "error_message",
            "metadata",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
            "steps",
            "artifacts",
        ]
        read_only_fields = [
            "id",
            "task_bot",
            "created_at",
            "updated_at",
            "steps",
            "artifacts",
        ]


class CampaignInfoSerializer(serializers.ModelSerializer):
    prospectation_groups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = CampaignInfo
        fields = [
            "id",
            "campaign_name",
            "category",
            "language",
            "campaign_info",
            "phone_number",
            "alt_phone_number",
            "webpage_url",
            "fanpage_url",
            "status",
            "prospectation_groups",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

class BotPersonalitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotPersonality
        fields = "__all__"


class SocialMediaPlatformsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMediaPlatform
        fields = "__all__"


class AccountOwnersSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountOwner
        fields = "__all__"


class otherCredentialsField(serializers.JSONField):
    class Meta:
        swagger_schema_fields = {
            "type": openapi.TYPE_OBJECT,
            "title": "other_credentials",
            "properties": {
                "User": openapi.Schema(
                    title="usuario",
                    type=openapi.TYPE_STRING,
                ),
                "password": openapi.Schema(
                    title="contraseñas",
                    type=openapi.TYPE_STRING,
                ),
                "cookie": openapi.Schema(
                    title="Cookie",
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "domain": openapi.Schema(type=openapi.TYPE_STRING),
                            "httpOnly": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            "name": openapi.Schema(type=openapi.TYPE_STRING),
                            "path": openapi.Schema(type=openapi.TYPE_STRING),
                            "sameSite": openapi.Schema(type=openapi.TYPE_STRING),
                            "secure": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            "value": openapi.Schema(type=openapi.TYPE_STRING),
                            "expiry": openapi.Schema(
                                type=openapi.TYPE_INTEGER, format="int64", nullable=True
                            ),
                        },
                    ),
                    default=None,
                ),
            },
            "required": ["User", "password"],
        }


class SocialMediaAccountsSerializer(serializers.ModelSerializer):
    # el ArrayField no siempre aparece bien en la documentación automática,
    # lo listamos explícitamente para que salga en los serializers y swagger
    groups_to_search = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    campaign_info_data = CampaignInfoSerializer(source="campaign_info", read_only=True)

    class Meta:
        model = SocialMediaAccount
        fields = [
            "id",
            "bot_personality",
            "group",
            "account_kind",
            "groups_to_search",
            "professional_mode",
            "account_name",
            "access_token",
            "access_secret",
            "other_credentials",
            "owner",
            "proxy",
            "campaign_info",
            "campaign_info_data",
            "account_type",
        ]

    other_credentials = otherCredentialsField()


class SocialMediaAccountCreateSerializer(serializers.ModelSerializer):
    # Contract documented in guia_creacion_cuenta_instagram_2026-09-24.md.
    # Legacy *_id aliases remain accepted so existing clients do not break.
    bot_personality_id = serializers.PrimaryKeyRelatedField(
        source="bot_personality",
        queryset=BotPersonality.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner",
        queryset=AccountOwner.objects.all(),
        required=False,
        write_only=True,
    )
    proxy_id = serializers.PrimaryKeyRelatedField(
        source="proxy",
        queryset=Proxy.objects.filter(socialmediaaccount__isnull=True),
        required=False,
        allow_null=True,
        write_only=True,
    )
    campaign_info_id = serializers.PrimaryKeyRelatedField(
        source="campaign_info",
        queryset=CampaignInfo.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    group = serializers.JSONField(required=True, allow_null=False)
    account_kind = serializers.ChoiceField(
        choices=("business", "personal"),
        required=False,
        default="business",
    )
    other_credentials = serializers.JSONField(required=True, allow_null=False)

    class Meta:
        model = SocialMediaAccount
        fields = [
            "id",
            "account_name",
            "group",
            "owner",
            "bot_personality",
            "proxy",
            "account_kind",
            "other_credentials",
            "access_token",
            "access_secret",
            # Backwards-compatible fields.
            "bot_personality_id",
            "owner_id",
            "proxy_id",
            "campaign_info_id",
            "groups_to_search",
            "professional_mode",
            "account_type",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "owner": {"required": False},
            "bot_personality": {"required": False, "allow_null": True},
            "proxy": {"required": False, "allow_null": True},
            "groups_to_search": {"required": False},
            "professional_mode": {"required": False},
            "account_type": {"required": False},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        proxy_queryset = Proxy.objects.filter(socialmediaaccount__isnull=True)
        if getattr(self, "instance", None) is not None and getattr(self.instance, "proxy_id", None):
            proxy_queryset = Proxy.objects.filter(
                Q(socialmediaaccount__isnull=True) | Q(socialmediaaccount=self.instance)
            )
        for field_name in ("proxy", "proxy_id"):
            if field_name in self.fields:
                self.fields[field_name].queryset = proxy_queryset.distinct()

    def validate(self, attrs):
        if not attrs.get("owner") and not getattr(self.instance, "owner_id", None):
            raise serializers.ValidationError({"owner": "This field is required."})
        return attrs

    def validate_other_credentials(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("other_credentials debe ser un objeto JSON.")

        normalized = dict(value)
        user = normalized.get("user", normalized.get("User"))
        password = normalized.get("password")
        cookie = normalized.get("cookie", [])

        if not isinstance(user, str) or not user.strip():
            raise serializers.ValidationError({"user": "user debe ser una cadena no vacía."})
        if not isinstance(password, str) or not password.strip():
            raise serializers.ValidationError({"password": "password debe ser una cadena no vacía."})
        if not isinstance(cookie, list):
            raise serializers.ValidationError({"cookie": "cookie debe ser una lista."})

        normalized["user"] = user.strip()
        normalized["User"] = user.strip()  # compatibility with the existing bot
        normalized["password"] = password
        normalized["cookie"] = cookie
        return normalized


class TaskTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskType
        fields = "__all__"


class TaskBotsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskBot
        fields = "__all__"


class ProxySerializer(serializers.ModelSerializer):
    class Meta:
        model = Proxy
        fields = "__all__"


class SocialMediaAccountsSerializer2(serializers.ModelSerializer):
    bot_personality = BotPersonalitiesSerializer()
    owner = AccountOwnersSerializer()
    proxy = ProxySerializer()
    campaign_info = serializers.PrimaryKeyRelatedField(read_only=True)
    campaign_info_data = CampaignInfoSerializer(source="campaign_info", read_only=True)

    class Meta:
        model = SocialMediaAccount
        fields = [
            "id",
            "bot_personality",
            "groups_to_search",
            "professional_mode",
            "account_name",
            "access_token",
            "access_secret",
            "other_credentials",
            "owner",
            "proxy",
            "campaign_info",
            "campaign_info_data",
            "account_type",
            "created_at",
        ]


class PendingCampaignInfoSerializer(serializers.ModelSerializer):
    """Campaign data needed by bots, without the reverse M2M lookup."""

    class Meta:
        model = CampaignInfo
        fields = [
            "id",
            "campaign_name",
            "category",
            "language",
            "campaign_info",
            "phone_number",
            "alt_phone_number",
            "webpage_url",
            "fanpage_url",
            "status",
            "created_at",
        ]


class PendingSocialMediaAccountSerializer(serializers.ModelSerializer):
    bot_personality = BotPersonalitiesSerializer(read_only=True)
    owner = AccountOwnersSerializer(read_only=True)
    proxy = ProxySerializer(read_only=True)
    campaign_info = serializers.PrimaryKeyRelatedField(read_only=True)
    campaign_info_data = PendingCampaignInfoSerializer(
        source="campaign_info", read_only=True
    )

    class Meta:
        model = SocialMediaAccount
        fields = [
            "id",
            "bot_personality",
            "groups_to_search",
            "professional_mode",
            "account_name",
            "access_token",
            "access_secret",
            "other_credentials",
            "owner",
            "proxy",
            "campaign_info",
            "campaign_info_data",
            "account_type",
            "created_at",
        ]


class PendingBotSerializer(serializers.ModelSerializer):
    start_date = serializers.DateTimeField(
        default_timezone=ZoneInfo("America/Bogota"),
        read_only=True,
    )
    end_date = serializers.DateTimeField(
        default_timezone=ZoneInfo("America/Bogota"),
        read_only=True,
    )
    social_media_account = PendingSocialMediaAccountSerializer(read_only=True)

    class Meta:
        model = TaskBot
        fields = "__all__"


class PendingBotQuerySerializer(serializers.Serializer):
    bot_name = serializers.RegexField(
        r"^[\w.@:-]+$",
        required=True,
        max_length=255,
        trim_whitespace=True,
    )
    status_process = serializers.RegexField(
        r"^[A-Za-z0-9_-]+$", required=False, max_length=255
    )
    account_id = serializers.IntegerField(required=False, min_value=1)


class TaskBotsSerializer2(serializers.ModelSerializer):
    social_media_account = SocialMediaAccountsSerializer2()

    class Meta:
        model = TaskBot
        fields = "__all__"


class CustomTaskSerializer(serializers.Serializer):
    type = serializers.CharField(required=False, allow_blank=True)
    post = serializers.CharField(required=False, allow_blank=True)
    links_image = serializers.ListField(
        child=serializers.URLField(), required=False, allow_empty=True
    )


class CreateTasksSerializer(serializers.Serializer):
    task_type_id = serializers.PrimaryKeyRelatedField(queryset=TaskType.objects.all())
    custom_task = CustomTaskSerializer(required=False)

    def to_internal_value(self, data):
        task_type_id = self.fields["task_type_id"].to_internal_value(
            data.get("task_type_id")  # Usar .get() permite que sea opcional
        )
        custom_task = self.fields["custom_task"].to_internal_value(
            data.get("custom_task", {})
        )

        return {
            "task_type_id": task_type_id,
            "custom_task": custom_task,
        }


class TaskBotsPendingSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source="task_type.platform", read_only=True)
    task_name = serializers.CharField(source="task_type.task_name", read_only=True)
    task_description = serializers.CharField(
        source="task_type.descripcion", read_only=True
    )
    bot_executor = serializers.CharField()
    comment = serializers.JSONField()
    custom_task = serializers.JSONField()
    status_process = serializers.CharField()
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    account_id = serializers.IntegerField(
        source="social_media_account.id", read_only=True
    )
    account_name = serializers.CharField(
        source="social_media_account.account_name", read_only=True
    )
    account_name = serializers.CharField(
        source="social_media_account.account_name", read_only=True
    )

    class Meta:
        model = TaskBot
        fields = [
            "platform_name",
            "task_name",
            "task_description",
            "bot_executor",
            "comment",
            "status_process",
            "start_date",
            "end_date",
            "account_id",
            "account_name",
            "custom_task",
        ]

class SocialMediaMessageSerializer(serializers.ModelSerializer):
    account_id = serializers.IntegerField(write_only=True)
    account = serializers.IntegerField(source="account_id", read_only=True)

    class Meta:
        model = SocialMediaMessage
        fields = [
            "id",
            "account_id",   # input
            "account",      # output
            "message_text",
            "category",
            "status",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "account"]

    def validate_message_text(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("message_text no puede estar vacío.")
        return value

    def validate(self, attrs):
        """
        Evita duplicados por cuenta usando el mismo criterio del model.save():
        md5(message_text.strip()) + account_id
        """
        account_id = attrs.get("account_id") or getattr(self.instance, "account_id", None)
        message_text = attrs.get("message_text") or (self.instance.message_text if self.instance else None)

        if account_id is None or message_text is None:
            return attrs

        normalized = message_text.strip()
        msg_hash = hashlib.md5(normalized.encode("utf-8")).hexdigest()

        qs = SocialMediaMessage.objects.filter(account_id=account_id, message_hash=msg_hash)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)

        if qs.exists():
            raise serializers.ValidationError(
                {"message_text": "Ya existe un mensaje idéntico para esta cuenta."}
            )

        return attrs

    def create(self, validated_data):
        account_id = validated_data.pop("account_id")
        validated_data["account_id"] = account_id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Si llega account_id, actualiza FK también
        account_id = validated_data.pop("account_id", None)
        if account_id is not None:
            instance.account_id = account_id

        for k, v in validated_data.items():
            setattr(instance, k, v)

        instance.save()
        return instance
    
class GroupsInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupsInfo
        fields ="__all__"
        read_only_fields = ["id", "created_at"]
        
class SocialMediaAccountGroupSerializer(serializers.ModelSerializer):
    account_id = serializers.ReadOnlyField(source='account.id')
    group_id = serializers.ReadOnlyField(source='group.id')
    group = GroupsInfoSerializer(read_only=True)
    # nuevo campo agregado a la serialización
    growth = serializers.BooleanField()
    # nuevo campo para prospección
    is_prospection = serializers.BooleanField(required=False)

    class Meta:
        model = SocialMediaAccountGroup
        # incluimos los nuevos campos en la lista que retorna la API
        fields = ["id", "account_id", "group_id", "group", "growth", "is_prospection"]

    def create(self, validated_data):
        initial_data = getattr(self, "initial_data", {}) or {}
        account_id = initial_data.get('account_id')
        group_id = initial_data.get('group_id')
        growth = initial_data.get('growth')
        is_prospection = initial_data.get('is_prospection')
        if not account_id or not group_id:
            raise serializers.ValidationError("account_id y group_id son requeridos.")
        try:
            account = SocialMediaAccount.objects.get(id=account_id)
            group = GroupsInfo.objects.get(id=group_id)
            return SocialMediaAccountGroup.objects.create(
                account=account,
                group=group,
                growth=growth or False,
                is_prospection=bool(is_prospection) if is_prospection is not None else False,
            )
        except SocialMediaAccount.DoesNotExist:
            raise serializers.ValidationError({"account_id": "Cuenta no encontrada."})
        except GroupsInfo.DoesNotExist:
            raise serializers.ValidationError({"group_id": "Grupo no encontrado."})
        except IntegrityError:
            raise serializers.ValidationError("La relación entre esta cuenta y grupo ya existe.")

    def update(self, instance, validated_data):
        # Para update, si se pasan account_id o group_id en initial_data
        initial_data = getattr(self, "initial_data", {}) or {}
        account_id = initial_data.get('account_id')
        group_id = initial_data.get('group_id')
        growth = initial_data.get('growth')
        is_prospection = initial_data.get('is_prospection')
        if account_id is not None:
            try:
                instance.account = SocialMediaAccount.objects.get(id=account_id)
            except SocialMediaAccount.DoesNotExist:
                raise serializers.ValidationError({"account_id": "Cuenta no encontrada."})
        if group_id is not None:
            try:
                instance.group = GroupsInfo.objects.get(id=group_id)
            except GroupsInfo.DoesNotExist:
                raise serializers.ValidationError({"group_id": "Grupo no encontrado."})
        if growth is not None:
            # actualiza el campo growth si se proporciona
            instance.growth = bool(growth)
        if is_prospection is not None:
            # actualiza el campo is_prospection si se proporciona
            instance.is_prospection = bool(is_prospection)
        instance.save()
        return instance
    
class ProspectPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProspectPost
        fields = "__all__"


class ProspectCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProspectComment
        fields = "__all__"


class ProspectReplyClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProspectReplyClassification
        fields = "__all__"


class AlertLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertLog
        fields = "__all__"


class BlacklistAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlacklistAccount
        fields = "__all__"


class QuoteAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteAnswer
        fields = "__all__"


class ProspectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prospect
        fields = "__all__"

class ProspectGroupsSerializer(serializers.ModelSerializer):
    campaigns_id = serializers.PrimaryKeyRelatedField(
        source="campaigns",
        queryset=CampaignInfo.objects.all(),
        many=True,
        required=False,
    )
    campaign_ids = serializers.PrimaryKeyRelatedField(
        source="campaigns",
        queryset=CampaignInfo.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = ProspectationGroups
        fields = [
            "id",
            "group_name",
            "group_url",
            "service_category",
            "city",
            "campaigns_id",
            "campaign_ids",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        campaigns = validated_data.pop("campaigns", [])
        group = ProspectationGroups.objects.create(**validated_data)
        for campaign in campaigns:
            CampaignProspectationGroup.objects.get_or_create(
                campaign=campaign,
                prospectation_group=group,
            )
        return group

    def update(self, instance, validated_data):
        campaigns = validated_data.pop("campaigns", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if campaigns is not None:
            CampaignProspectationGroup.objects.filter(
                prospectation_group=instance,
            ).delete()
            for campaign in campaigns:
                CampaignProspectationGroup.objects.get_or_create(
                    campaign=campaign,
                    prospectation_group=instance,
                )

        return instance
    
class ProspectDetailSerializer(serializers.ModelSerializer):
    posts = ProspectPostSerializer(many=True, read_only=True)
    comments = ProspectCommentSerializer(many=True, read_only=True)
    classifications = ProspectReplyClassificationSerializer(many=True, read_only=True)
    alerts = AlertLogSerializer(many=True, read_only=True)
    quote_answer = QuoteAnswerSerializer(read_only=True)

    class Meta:
        model = Prospect
        fields = "__all__"


class UsedForRecommendationOrReviewSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        source="account",
        queryset=SocialMediaAccount.objects.all()
    )

    class Meta:
        model = UsedForRecommendationOrReview
        fields = [
            "id",
            "account_id",
            "review",
            "mention",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate(self, attrs):
        account = attrs.get("account")

        if not account:
            return attrs

        qs = UsedForRecommendationOrReview.objects.filter(account=account)

        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "account_id": "Ya existe un registro para esta cuenta."
            })

        return attrs
