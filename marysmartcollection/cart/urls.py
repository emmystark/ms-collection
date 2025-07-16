from django.urls import path
from . import views

app_name = 'cart'

# project imports
from cart.views import (
  
    CreateCheckoutView, PaymentWebhookView, checkout, CreateCheckoutView, PaymentWebhookView, 
    debug_cart,
)
# app_name = "ecomflutterwave"

urlpatterns = [
    path('', views.cart_detail, name='cart_detail'),
    path('add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('remove/<int:product_id>/', views.cart_remove,
         name='cart_remove'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('cart/clear/', views.cart_clear, name='cart_clear'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('checkout/', views.checkout, name='checkout'),
    path('create-checkout/', views.CreateCheckoutView.as_view(), name='create_checkout'),
    path('webhook/', views.PaymentWebhookView.as_view(), name='webhook'),
    # path('checkout/success/', views.CheckoutSuccessView.as_view(), name='checkout_success'),
    path('debug-cart/', views.debug_cart, name='debug_cart'),
]
