from rest_framework import serializers

from .models.instagram_prospecting import (
    InstagramProspectingCampaign,
    InstagramProspect,
    InstagramProspectPost,
    InstagramProspectInteraction,
    InstagramFollowUpAlert,
)


class InstagramProspectingCampaignSerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source="name", read_only=True)

    class Meta:
        model = InstagramProspectingCampaign
        fields = "__all__"


class InstagramProspectSerializer(serializers.ModelSerializer):
    industry_target = serializers.CharField(required=False, allow_blank=True, write_only=True)
    location_match = serializers.BooleanField(required=False, allow_null=True, write_only=True)
    location_confidence = serializers.CharField(required=False, allow_blank=True, write_only=True)
    location_evidence = serializers.JSONField(required=False, write_only=True)
    profile_classification = serializers.CharField(required=False, allow_blank=True, write_only=True)
    business_role = serializers.CharField(required=False, allow_blank=True, write_only=True)
    business_vertical = serializers.CharField(required=False, allow_blank=True, write_only=True)
    competitor_relation = serializers.CharField(required=False, allow_blank=True, write_only=True)
    commercial_intent_score = serializers.FloatField(required=False, allow_null=True, write_only=True)
    classification_confidence = serializers.FloatField(required=False, allow_null=True, write_only=True)
    qualification_decision = serializers.CharField(required=False, allow_blank=True, write_only=True)
    engageable = serializers.BooleanField(required=False, allow_null=True, write_only=True)

    EXTENDED_METADATA_FIELDS = (
        "industry_target",
        "location_match",
        "location_confidence",
        "location_evidence",
        "profile_classification",
        "business_role",
        "business_vertical",
        "competitor_relation",
        "commercial_intent_score",
        "classification_confidence",
        "qualification_decision",
        "engageable",
    )

    class Meta:
        model = InstagramProspect
        fields = "__all__"

    def _merge_extended_metadata(self, validated_data, instance=None):
        metadata = dict(getattr(instance, "metadata_json", None) or {})
        metadata.update(validated_data.get("metadata_json") or {})

        for field_name in self.EXTENDED_METADATA_FIELDS:
            if field_name in validated_data:
                metadata[field_name] = validated_data.pop(field_name)

        validated_data["metadata_json"] = metadata
        return validated_data

    def create(self, validated_data):
        validated_data = self._merge_extended_metadata(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._merge_extended_metadata(validated_data, instance)
        return super().update(instance, validated_data)


class InstagramProspectPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramProspectPost
        fields = "__all__"


class InstagramProspectInteractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramProspectInteraction
        fields = "__all__"


class InstagramFollowUpAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramFollowUpAlert
        fields = "__all__"

