from django.shortcuts import render
from django.contrib.auth import logout
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from .serializers import (
    MyTokenObtainPairSerializer,
    RegisterSerializer,
    LogoutSerializer,
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics
from django.contrib.auth.models import User
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
import json
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer


@api_view(["GET"])
def getRoutes(request):
    routes = ["/token/", "/register/", "/token/refresh/", "/test/"]
    return Response(routes)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def testEndPoint(request):
    if request.method == "GET":
        data = f"Congratulation {request.user}, your API just responded to GET request"
        return Response({"response": data}, status=status.HTTP_200_OK)
    elif request.method == "POST":
        try:
            body = request.body.decode("utf-8")
            data = json.loads(body)
            if "text" not in data:
                return Response("Invalid JSON data", status.HTTP_400_BAD_REQUEST)
            text = data.get("text")
            data = f"Congratulation your API just responded to POST request with text: {text}"
            return Response({"response": data}, status=status.HTTP_200_OK)
        except json.JSONDecodeError:
            return Response("Invalid JSON data", status.HTTP_400_BAD_REQUEST)
    return Response("Invalid JSON data", status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method="post",
    request_body=LogoutSerializer,  # Especifica el serializador para el cuerpo de la solicitud
)
@api_view(["POST"])
def logout_view(request):
    """
    Log out the user by blacklisting the refresh token.
    """
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(status=status.HTTP_200_OK)
    except Exception as e:
        return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
