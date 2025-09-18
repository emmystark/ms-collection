from django.urls import path
from . import views

urlpatterns = [
    path('alteration-request/', views.alteration_request_view, name='alteration_request'),
    path('alteration-success/', views.alteration_success_view, name='alteration_success'),
]
