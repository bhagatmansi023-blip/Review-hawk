from django.urls import path
from . import views

urlpatterns = [
    path('webhook/', views.github_webhook, name='github_webhook'),
]
