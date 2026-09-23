# reny/View
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import JSONData, Acount, QuestionAndAnswer
from .serializers import (
    JSONDataSerializer,
    AcountSerializer,
    QuestionAndAnswerSerializer,
    CustomDataQuestionAndAnswerSerializer,
)
from rest_framework.permissions import AllowAny
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema


class JSONDataViewSet(ModelViewSet):
    queryset = JSONData.objects.all()
    serializer_class = JSONDataSerializer
    permission_classes = [AllowAny]


class AcountDataViewSet(ModelViewSet):
    queryset = Acount.objects.all()
    serializer_class = AcountSerializer
    permission_classes = [AllowAny]


class QuestionAndAnswerViewSet(ModelViewSet):
    queryset = QuestionAndAnswer.objects.all()
    serializer_class = QuestionAndAnswerSerializer
    permission_classes = [AllowAny]


class CombinedDataView(viewsets.ViewSet):
    @swagger_auto_schema(
        operation_description="Obtener datos combinados de JSON, Cuentas y Preguntas y Respuestas.",
        responses={200: CustomDataQuestionAndAnswerSerializer(many=True)},
    )
    def get(self, request):
        json_data = JSONData.objects.all()
        acount_data = Acount.objects.all()
        qa_data = QuestionAndAnswer.objects.all()

        json_serializer = CustomDataQuestionAndAnswerSerializer(json_data, many=True)
        acount_serializer = CustomDataQuestionAndAnswerSerializer(
            acount_data, many=True
        )
        qa_serializer = CustomDataQuestionAndAnswerSerializer(qa_data, many=True)

        combined_data = {
            "JSONData": json_serializer.data,
            "AcountData": acount_serializer.data,
            "QuestionAndAnswer": qa_serializer.data,
        }

        return Response(combined_data, status=status.HTTP_200_OK)
