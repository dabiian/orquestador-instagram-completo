from rest_framework import serializers
from .models import JSONData, Acount, QuestionAndAnswer


class JSONDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = JSONData
        fields = "__all__"


class AcountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Acount
        fields = "__all__"


class QuestionAndAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAndAnswer
        fields = "__all__"


class CustomDataSerializer(serializers.Serializer):
    data = serializers.JSONField()
    credenciales = serializers.JSONField()


class CustomDataJSONDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = JSONData
        fields = ("data",)


class CustomDataAcountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Acount
        fields = ("credenciales",)


class CustomDataQuestionAndAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAndAnswer
        fields = ("data",)
