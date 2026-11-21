"""Solo se publica el panel administrativo propio; no existe bypass de Django-admin."""
from django.urls import path, include
urlpatterns = [path('',include('core.urls'))]
