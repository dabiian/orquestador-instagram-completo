from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# Cambia este import por la ruta real donde tengas tu función
from .email_sender import send_email_alert


class GmailSendEmailView(APIView):
    @swagger_auto_schema(
        operation_description="Envía un correo usando Gmail API",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["to_emails", "subject", "text_body"],
            properties={
                "to_emails": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_STRING),
                    description="Lista de destinatarios",
                    example=["destino@gmail.com"],
                ),
                "subject": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Asunto del correo",
                    example="[BOT][CRITICAL] Proxy failure",
                ),
                "text_body": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Cuerpo del correo en texto plano",
                    example="Se detectaron 10 errores consecutivos en el proxy principal.",
                ),
                "html_body": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Cuerpo HTML opcional",
                    example="<h2>Alerta</h2><p>Se detectaron 10 errores consecutivos en el proxy principal.</p>",
                ),
            },
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
                    "message": openapi.Schema(type=openapi.TYPE_STRING, example="Correo enviado correctamente"),
                    "data": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        description="Respuesta de Gmail API",
                    ),
                },
            ),
            400: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING, example="to_emails es requerido"),
                },
            ),
            500: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING, example="Detalle del error"),
                },
            ),
        },
        tags=["Gmail"],
    )
    def post(self, request):
        to_emails = request.data.get("to_emails")
        subject = request.data.get("subject")
        text_body = request.data.get("text_body")
        html_body = request.data.get("html_body")

        if not to_emails:
            return Response({"error": "to_emails es requerido"}, status=status.HTTP_400_BAD_REQUEST)

        if isinstance(to_emails, str):
            to_emails = [to_emails]

        if not isinstance(to_emails, list):
            return Response(
                {"error": "to_emails debe ser un string o una lista de strings"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        to_emails = [email.strip() for email in to_emails if isinstance(email, str) and email.strip()]
        if not to_emails:
            return Response({"error": "No hay destinatarios válidos"}, status=status.HTTP_400_BAD_REQUEST)

        if not subject:
            return Response({"error": "subject es requerido"}, status=status.HTTP_400_BAD_REQUEST)

        if not text_body:
            return Response({"error": "text_body es requerido"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = send_email_alert(
                to_emails=to_emails,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                "success": True,
                "message": "Correo enviado correctamente",
                "data": result,
            },
            status=status.HTTP_200_OK,
        )