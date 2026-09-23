# reny/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    JSONDataViewSet,
    AcountDataViewSet,
    QuestionAndAnswerViewSet,
    CombinedDataView,
)


router = DefaultRouter()
router.register(r"training", JSONDataViewSet, basename="Reny")
router.register(r"accounts", AcountDataViewSet, basename="Reny 2")
router.register(r"questionandanswer", QuestionAndAnswerViewSet, basename="Reny 3")
router.register(r"combined", CombinedDataView, basename="combined data")


urlpatterns = [
    path("gmb/", include(router.urls)),
]
