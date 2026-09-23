# api/urls.py

from django.urls import path
from . import views

from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

urlpatterns = [
    path('token/', views.MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/register/', views.RegisterView.as_view(), name='auth_register'),
    path('token/logout/', views.logout_view, name='logout'),
    path('token/test', views.testEndPoint, name='logout'),
    
    #path('', views.getRoutes)
]