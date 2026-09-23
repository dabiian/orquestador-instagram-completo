from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("openai/", views.OpenAIView.as_view(), name="openai"),
    path("openai/custom/",views.SimpleOpenAIView.as_view(), name="openai_custom_text"),
    path("openai/image/", views.OpenAIImageView.as_view(), name="openai_image"),
    path("openai/text/", views.OpenTextGenerate.as_view(), name="openai_image"),
    path(
        "openai/image/anality/",
        views.OpenImageAnality.as_view(),
        name="openai_anality_image",
    ),
    path("openai/image/edit/", views.OpenAIImageEdit.as_view(),name="openai_edit_image"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
