from django.urls import path
from . import views

urlpatterns = [
    path('submit/', views.alteration_request, name='alteration_request'),
]

