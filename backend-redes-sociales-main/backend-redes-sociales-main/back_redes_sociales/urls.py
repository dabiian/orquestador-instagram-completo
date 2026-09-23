# back_redes_sociales\urls.py
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.decorators.csrf import csrf_exempt

schema_view = get_schema_view(
    openapi.Info(
        title="Documentación API Redes Sociales - Versiones 1 y 2",
        default_version="v2",
        description="Documentación de las APIs de Redes Sociales para las versiones 1 y 2",
        contact=openapi.Contact(email="homero9726@gmail.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
urlpatterns = [
    path("admin/", admin.site.urls),
    # path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path(
        "docs/",
        csrf_exempt(schema_view.with_ui("swagger", cache_timeout=0)),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    # re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path("api/", include("dashboard.urls"), name="dashboard"),
    path("api/", include("login_app.urls"), name="token"),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("openia.urls"), name="IA"),
    path("api/", include("email_send.urls"), name="email_sender"),
    path("api/reny/", include("reny.urls"), name="reny apis"),
    # Version 2 de las url
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# # Configuración adicional para la nueva página de Swagger
# schema_view_v2 = get_schema_view(
#     openapi.Info(
#         title="Documentación API Redes Sociales - Versión 2",
#         default_version="v2",
#         description="Documentación específica para la Versión 2 de la API de Redes Sociales",
#         contact=openapi.Contact(email="homero9726@gmail.com"),
#         license=openapi.License(name="BSD License"),
#     ),
#     public=True,
#     permission_classes=(permissions.AllowAny,),
# )

# urlpatterns = [
#     # ... otras rutas ...
#     # Ruta para la documentación de Swagger de la versión 2
#     path(
#         "docs/v2/",
#         csrf_exempt(schema_view_v2.with_ui("swagger", cache_timeout=0)),
#         name="schema-swagger-ui-v2",
#     ),
# ]
