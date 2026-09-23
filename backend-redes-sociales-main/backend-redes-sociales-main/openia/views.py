import json
import time
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from openai import OpenAI
from dashboard.models.Bot_personality import (
    BotPersonality,
)
from django.core.exceptions import ObjectDoesNotExist
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import os
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
import base64
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from typing import Any, Dict, List, cast

api_key = os.getenv('OPENAI_API_KEY')
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class OpenAIView(APIView):
    @swagger_auto_schema(
        operation_description="Obtiene una respuesta de OpenAI basada en la personalidad del bot",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["bot_personality_id", "user_prompt"],
            properties={
                "bot_personality_id": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="ID de la personalidad del bot",
                ),
                "user_prompt": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Prompt del usuario para OpenAI",
                ),
                "response_format": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Formato de respuesta opcional. Si llega vacío, no se envía al modelo.",
                ),
            },
        ),
        responses={
            200: "Respuesta de OpenAI",
            400: "Personalidad no existe",
            500: "Error",
        },
    )
    def post(self, request):
        bot_personality_id = request.data.get("bot_personality_id")
        user_prompt = request.data.get("user_prompt")  # Obtiene el prompt del usuario
        response_format = request.data.get("response_format")

        if not isinstance(response_format, dict) or not response_format:
            response_format = None

        if not bot_personality_id or not user_prompt:
            return Response(
                {"error": "bot_personality_id y user_prompt son requeridos"},
                status=400,
            )

        try:
            bot_personality = BotPersonality.objects.get(id=bot_personality_id)
        except ObjectDoesNotExist:
            return Response(
                {"error": "La personalidad con el ID proporcionado no existe"},
                status=400,
            )

        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

        try:
            response = _chat_completion_with_model(
                client=client,
                model_name="deepseek-v4-flash",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"A partir de ahora adoptarás completamente la siguiente personalidad y todas tus respuestas deberán reflejarla de forma natural y coherente.\n\n"
                            f"Nombre: {bot_personality.name}.\n"
                            f"Eres creador(a) de contenido para redes sociales, especialmente Facebook.\n"
                            f"Biografía / esencia personal: {bot_personality.bio}.\n"
                            f"Eres de {bot_personality.location}.\n"
                            f"Tu estilo de comunicación es {bot_personality.communication_style}.\n"
                            f"Tus valores principales son: {bot_personality.values}."
                        ),
                    },
                    {
                        "role": "system",
                        "content": (
                            f"Tus preferencias incluyen: {bot_personality.preferences}.\n"
                            f"No te gusta: {bot_personality.dislikes}.\n"
                            f"Tu conocimiento principal se centra en: {bot_personality.special_knowledge}.\n"
                            f"Sueles hacer referencias a: {bot_personality.cultural_references}."
                        ),
                    },
                    {
                        "role": "system",
                        "content": (
                            f"Frases o expresiones típicas tuyas: {bot_personality.phraseology}.\n"
                            f"En experiencias anteriores: {bot_personality.past_interactions}.\n"
                            f"Reaccionas emocionalmente de la siguiente forma: {bot_personality.emotional_reactions}.\n"
                            f"Tu objetivo principal es: {bot_personality.objectives}.\n"
                            f"Tu comportamiento habitual es: {bot_personality.behavioral_tendencies}."
                        ),
                    },
                    {
                        "role": "system",
                        "content": (
                            f"Todas las respuestas deben estar en {bot_personality.language}.\n"
                            "Debes escribir de forma natural, humana y fluida, evitando sonar artificial o forzado.\n"
                            "No expliques tu razonamiento.\n"
                            "Responde únicamente lo solicitado.\n"
                            "Sé breve, claro y alineado totalmente con la personalidad definida."
                        ),
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                response_format=response_format,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=500)

        if response.choices:
            return Response(response.choices[0].message.content, status=200)
        else:
            return Response({"error": "No se recibió respuesta de OpenAI"}, status=500)

class OpenAIImageEdit(APIView):
    """
    Image-to-image (GPT Image) con retorno de URL:
    - recibe multipart image (+ prompt)
    - sube image a Files API (file_id)
    - llama images.edit con model gpt-image-1.5
    - recibe b64_json
    - guarda en MEDIA y retorna URL absoluta
    """
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        operation_description="Image-to-image (GPT Image) y retorna URL descargable.",
        consumes=["multipart/form-data"],
        responses={200: "OK", 400: "Bad Request", 500: "Error"},
        manual_parameters=[
            openapi.Parameter("image", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True, description="Imagen base"),
            openapi.Parameter("mask", openapi.IN_FORM, type=openapi.TYPE_FILE, required=False, description="Mascara PNG alpha (opcional)"),
            openapi.Parameter("user_prompt", openapi.IN_FORM, type=openapi.TYPE_STRING, required=True, description="Instrucciones (prompt)"),
            openapi.Parameter("size_image", openapi.IN_FORM, type=openapi.TYPE_STRING, required=False, default="1024x1024"),
            openapi.Parameter(
                "quality_image",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                default="medium",
                description="GPT Image quality: low|medium|high|auto",
            ),
        ],
    )
    def post(self, request):
        try:
            ALLOWED_SIZES = {"1024x1024", "1024x1536", "1024x1536", "auto"}
            user_prompt = request.data.get("user_prompt") or request.data.get("user_promt")  # por si hay typo
            if not user_prompt:
                return Response({"error": "user_prompt is required"}, status=400)

            if "image" not in request.FILES:
                return Response({"error": "image is required (multipart file field)"}, status=400)
            
            size_image = request.data.get("size_image", "auto") 
            if size_image not in ALLOWED_SIZES:
                return Response(
                    {"error": "Invalid size_image", "allowed": sorted(ALLOWED_SIZES)},
                    status=400,
                )

            quality = request.data.get("quality", "medium")  # low|medium|high|auto (si aplica)
            input_fidelity = request.data.get("input_fidelity", "high")  # low|high

            client = OpenAI(api_key=api_key)

            up_image = request.FILES["image"]
            image_bytes = up_image.read()

            # Files: purpose vision
            f = client.files.create(
                file=(up_image.name, image_bytes, up_image.content_type or "application/octet-stream"),
                purpose="vision",
            )

            # Responses API: image_generation tool edit + size
            resp = client.responses.create(
                model="gpt-5",
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_prompt},
                            {"type": "input_image", "file_id": f.id},
                        ],
                    }
                ],
                tools=[
                    {
                        "type": "image_generation",
                        "action": "edit",
                        "size": size_image,
                        "quality": quality,              
                        "input_fidelity": input_fidelity 
                    }
                ],
            )

            # 3) Extraer base64 de la salida
            image_b64_list = [
                o.result for o in resp.output
                if getattr(o, "type", None) == "image_generation_call"
            ]
            if not image_b64_list:
                return Response({"error": "No image returned", "raw": resp.model_dump()}, status=500)

            image_b64 = image_b64_list[0]
            return Response(
                {
                    "message": "ok",
                    "image_b64": image_b64,
                    "mime_type": "image/png",  # normalmente es png
                },
                status=200,
            )


        except Exception as e:
            return Response({"error": "Error editing image", "message": str(e)}, status=500)
    
    
class OpenAIImageView(APIView):
    """
    API endpoint to generate images from input text.
    """

    @swagger_auto_schema(
        operation_description="Generate images from input text using gpt-image-1-mini in medium quality.",
        responses={
            200: "Respuesta de OpenAI con el link",
            400: "Bad Request",
            500: "Error",
        },
        manual_parameters=[
            openapi.Parameter(
                "size_image",
                openapi.IN_QUERY,
                description="Image size: 1024x1024, 1024x1792 o 1792x1024",
                type=openapi.TYPE_STRING,
                default="1024x1024",
            ),
            openapi.Parameter(
                "user_prompt",
                openapi.IN_QUERY,
                description="Input text to generate the image",
                type=openapi.TYPE_STRING,
            ),
        ],
    )
    def get(self, request):
        try:
            allowed_sizes = {"1024x1024", "1024x1792", "1792x1024"}
            size_image = request.GET.get("size_image", "1024x1024")
            user_prompt = request.GET.get("user_prompt")

            if not user_prompt:
                return Response({"error": "User prompt is required"}, status=400)

            if size_image not in allowed_sizes:
                return Response(
                    {
                        "error": "Invalid size_image",
                        "allowed": sorted(allowed_sizes),
                    },
                    status=400,
                )

            if not api_key:
                return Response({"error": "OPENAI_API_KEY is not configured"}, status=400)

            client = OpenAI(api_key=api_key)
            response = client.images.generate(
                model="gpt-image-1-mini",
                prompt=user_prompt,
                size=size_image,
                quality="medium",
                n=1,
            )

            image_url = response.data[0].b64_json
            return Response(
                {"message": "Image generated successfully", "image_b64": image_url},
                status=200,
            )

        except Exception as e:
            # Log the exception for debugging purposes
            return Response({"error": "Error generating image",
                            "message": str(e)},
                            status=500)


class OpenTextGenerate(APIView):
    """
    API endpoint to generate text using AI.
    """

    @swagger_auto_schema(
        operation_description="Generate text using AI.",
        responses={
            200: openapi.Response("AI-generated text"),
            500: "Error",
        },
        manual_parameters=[
            openapi.Parameter(
                "prompt",
                in_=openapi.IN_QUERY,
                description="Prompt for text generation",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "language",
                in_=openapi.IN_QUERY,
                description="Language for text generation",
                type=openapi.TYPE_STRING,
                default="SPANISH",
            ),
        ],
    )
    def get(self, request):
        try:
            prompt = request.GET.get(
                "prompt", "Una persona apasionada por las aves y la naturaleza"
            )
            language = request.GET.get("language", "SPANISH")

            # formatted_prompt = f"Create an English JSON object with keys such as name, bio, language, communication_style, values, preferences, dislikes, sample_responses, special_knowledge, cultural_references, phraseology, past_interactions, emotional_reactions, objectives, and behavioral_tendencies. The keys of the JSON object are constants and should not be changed for any reason. The content of each field must be in {language}, according to this description: {prompt}"
            formatted_prompt = f"Create an English JSON object with keys such as name, biography, location, language, communication style, values, preferences, dislikes, example_answers, special_knowledge, cultural_references, phraseology, past_interactions, emotional_reactions, goals, and behavioral_tendencies. The keys The JSON object are constants and should not be changed for any reason. The content of each field must be in {language} and everything you generate must be in first person, according to this description add many details: {prompt}"
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-1106",
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant designed to output JSON.",
                    },
                    {
                        "role": "user",
                        "content": formatted_prompt,
                    },
                ],
            )

            generated_text = response.choices[0].message.content
            json_obj = json.loads(generated_text)

            return Response(json_obj, status=200)

        except Exception as e:
            return Response({"error": f"Error generating text: {e}"}, status=500)


class OpenImageAnality(APIView):
    @swagger_auto_schema(
        operation_description="Analiza imágenes utilizando IA.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "url": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="URL de la imagen para analizar",
                ),
                "image_base64": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Imagen codificada en base64 para analizar",
                ),
                "prompt": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Indicación para la generación de texto",
                ),
            },
            required=["prompt"],  # Aquí especificas qué campos son obligatorios
        ),
        responses={
            200: openapi.Response("Texto generado por IA a partir de una imagen"),
            400: "Datos de entrada no válidos",
            500: "Error al generar texto",
        },
    )
    def post(self, request):
        # Validación: Verificar si la URL o la imagen en base64 están presentes
        url = request.data.get("url")
        image_base64 = request.data.get("image_base64")
        if not url and not image_base64:
            return Response(
                {"error": "Se requiere una URL de imagen o una imagen en base64"},
                status=400,
            )

        # Validación: Verificar si el prompt está presente
        prompt = request.data.get("prompt")
        if not prompt:
            return Response({"error": "El prompt es requerido"}, status=400)

        # Inicialización del cliente OpenAI
        client = OpenAI(api_key=api_key)

        try:
            # Preparar contenido de la solicitud
            content = [{"type": "text", "text": prompt}]
            if url:
                content.append({
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "low"
                    }
                })
            elif image_base64:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"{image_base64}",
                        "detail": "low"
                    }
                })

            # Creación de la solicitud a OpenAI
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Responde únicamente JSON válido. "
                            "Debes devolver exactamente esta estructura: "
                            '{"status": true|false, "response": "texto"}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": content,
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=300,
            )

            # Verificar si se recibió una respuesta
            detalle = response.choices[0].message.content

            if not detalle:
                return Response(
                    {"error": "La respuesta llegó vacía"},
                    status=500
                )

            objeto_dict = json.loads(detalle)

            return Response(objeto_dict, status=200)

        except json.JSONDecodeError as e:
            return Response(
                {"error": f"La respuesta no fue JSON válido: {str(e)}"},
                status=500
            )

        except Exception as e:
            # Manejo de excepciones generales
            return Response(
                {"error": f"Error al procesar la solicitud: {str(e)}"}, status=500
            )
            
        
def _is_deepseek_model(model_name: str) -> bool:
    return (model_name or "").lower().startswith("deepseek")


def _build_deepseek_chat_kwargs(model_name: str) -> Dict[str, Any]:
    if not _is_deepseek_model(model_name):
        return {}

    return {
        "reasoning_effort": "high",
        "extra_body": {"thinking": {"type": "enabled"}},
    }


def _chat_completion_with_model(
    client: OpenAI,
    model_name: str,
    messages: List[Dict[str, Any]],
    response_format: Dict[str, Any] | None = None,
):
    kwargs = _build_deepseek_chat_kwargs(model_name)
    if response_format:
        kwargs["response_format"] = response_format

    return client.chat.completions.create(
        model=model_name,
        messages=messages,
        **kwargs,
    )


def _build_client_and_model(requested_model: str):
    model_name = (requested_model or "deepseek-v4-flash").strip()

    if _is_deepseek_model(model_name):
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY no está configurada")
        return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL), model_name, "deepseek"

    if not api_key:
        raise ValueError("OPENAI_API_KEY no está configurada")
    return OpenAI(api_key=api_key), model_name, "openai"

class SimpleOpenAIView(APIView):
    @swagger_auto_schema(
        operation_description="Obtiene una respuesta simple de OpenAI usando DeepSeek sin personalidad del bot",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["user_prompt"],
            properties={
                "user_prompt": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Prompt del usuario para OpenAI",
                ),
                "system_prompt": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Prompt del sistema para OpenAI (opcional)",
                ),
                "model": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Modelo a usar. Por defecto deepseek-v4-flash. Si envías un modelo distinto a deepseek*, se usa OpenAI.",
                    default="deepseek-v4-flash",
                ),
                "response_format": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Formato de respuesta opcional. Si llega vacío, no se envía al modelo.",
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Respuesta de OpenAI",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "response": openapi.Schema(type=openapi.TYPE_STRING),
                        "model": openapi.Schema(type=openapi.TYPE_STRING),
                        "provider": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
            400: "Prompt requerido",
            500: "Error",
        },
    )
    def post(self, request):
        user_prompt = request.data.get("user_prompt")
        system_prompt = request.data.get("system_prompt")
        requested_model = request.data.get("model", "deepseek-v4-flash")
        response_format = request.data.get("response_format")

        if not isinstance(response_format, dict) or not response_format:
            response_format = None

        if not user_prompt:
            return Response(
                {"error": "user_prompt es requerido"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Recorte defensivo para evitar prompts monstruosos
        user_prompt = (user_prompt or "")
        system_prompt = (system_prompt or "").strip()[:10000]

        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        messages.append({
            "role": "user",
            "content": user_prompt,
        })

        try:
            client, model_name, provider = _build_client_and_model(requested_model)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        started_at = time.perf_counter()

        try:
            ai_response = _chat_completion_with_model(
                client=client,
                model_name=model_name,
                messages=messages,
                response_format=response_format,
            )
        except Exception as e:
            elapsed = time.perf_counter() - started_at
            print(f"[SimpleOpenAIView] error tras {elapsed:.2f}s -> {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        elapsed = time.perf_counter() - started_at
        print(f"[SimpleOpenAIView] tiempo={elapsed:.2f}s")

        if ai_response.choices and ai_response.choices[0].message:
            content = ai_response.choices[0].message.content or ""
            return Response(
                {
                    "response": content,
                    "model": model_name,
                    "provider": provider,
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {"error": "No se recibió respuesta de OpenAI"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )