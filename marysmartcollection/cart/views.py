from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from Ecommerce.models import Category, Product
from .cart import Cart
from .forms import CartAddProductForm
from rest_framework.views import APIView
from django.views import View
from marysmartcollection import settings
from .square_client import client
from .models import Payment
import uuid
import hmac
import hashlib
import requests
import json
import logging
import base64
from django.utils.decorators import method_decorator

UserModel = get_user_model()

@require_POST
@login_required
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    print(f"POST data: {request.POST}")  # Debug: Log form data
    form = CartAddProductForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        print(f"Cleaned data: {cd}")  # Debug: Log cleaned data
        size = cd.get('size')  # Safely get size to avoid KeyError
        if not size:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'size': ['Please select a size.']}}, status=400)
            return render(request, 'single-product.html', {
                'product': product,
                'cart_product_form': form,
                'error': 'Please select a size.',
                'category': product.category,
                'categories': Category.objects.all()
            })
        cart.add(
            product=product,
            quantity=cd['quantity'],
            size=size,
            override_quantity=cd['update']
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Product added to cart',
                'total_quantity': cart.__len__()
            })
        return redirect('cart:cart_detail')
    print(f"Form errors: {form.errors}")  # Debug: Log form errors
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return render(request, 'single-product.html', {
        'product': product,
        'cart_product_form': form,
        'error': form.errors.as_text(),
        'category': product.category,
        'categories': Category.objects.all()
    })

@require_POST
@login_required
def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Product removed from cart'})
    return redirect('cart:cart_detail')

@require_POST
@login_required
def cart_update(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    print(f"POST data: {request.POST}")  # Debug
    form = CartAddProductForm(request.POST)
    if form.is_valid():
        cd = form.cleaned_data
        print(f"Cleaned data: {cd}")  # Debug
        size = cd.get('size')
        cart.add(
            product=product,
            quantity=cd['quantity'],
            size=size,
            override_quantity=True
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Cart updated',
                'total_quantity': cart.__len__()
            })
        return redirect('cart:cart_detail')
    print(f"Form errors: {form.errors}")  # Debug
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return render(request, 'single-product.html', {
        'product': product,
        'cart_product_form': form,
        'error': form.errors.as_text(),
        'category': product.category,
        'categories': Category.objects.all()
    })

@require_POST
@login_required
def cart_clear(request):
    cart = Cart(request)
    cart.clear()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Cart cleared'})
    return redirect('cart:cart_detail')

def cart_detail(request, category_slug=None):
    cart = Cart(request)
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    
    context = {
        'cart': cart,
        'category': category,
        'categories': categories,
        'products': products,
        'cart_form': CartAddProductForm()
    }
    return render(request, 'cart/cart.html', context)

def checkout(request):
    cart = Cart(request)
    return render(request, 'cart/checkout.html', {'cart': cart})

def debug_cart(request):
    cart = Cart(request)
    return JsonResponse({'cart': cart.cart})


# from square.http.api_response import ApiResponse  

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class CreateCheckoutView(View):
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "location_id": settings.SQUARE_LOCATION_ID,
                "line_items": line_items,
                "state": "OPEN"
            }
            logger.debug(f"Order data: {json.dumps(order_data, indent=2)}")

            try:
                order_response = client.orders.create(
                    order=order_data,
                    idempotency_key=idempotency_key
                )
                if not order_response.errors and order_response.order:
                    order_id = order_response.order.id
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors or "Unknown error"}, status=400)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                body = {
                    "order": order_data,
                    "idempotency_key": idempotency_key
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)

            # Create payment link using HTTP request
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/",
                    "currency": "CAD",
                    "ask_for_shipping_address": False
                },
                "order": {
                    "order_id": order_id,
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items  # Reuse line_items from order creation
                }
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                response = requests.post(
                    "https://connect.squareupsandbox.com/v2/online-checkout/payment-links",
                    headers=headers,
                    data=json.dumps(payment_link_body),
                    timeout=10
                )
                if response.status_code == 200:
                    checkout_url = response.json()['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    error_message = response.json().get('errors', ['Unknown error'])
                    logger.error(f"Payment link creation failed: {error_message}")
                    return JsonResponse({"error": error_message}, status=response.status_code)
            except requests.RequestException as e:
                logger.error(f"Payment link creation error: {str(e)}")
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "location_id": settings.SQUARE_LOCATION_ID,
                "line_items": line_items,
                "state": "OPEN"
            }
            logger.debug(f"Order data: {json.dumps(order_data, indent=2)}")

            try:
                order_response = client.orders.create(
                    order=order_data,
                    idempotency_key=idempotency_key
                )
                if not order_response.errors and order_response.order:
                    order_id = order_response.order.id
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors or "Unknown error"}, status=400)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                body = {
                    "order": order_data,
                    "idempotency_key": idempotency_key
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(
                    idempotency_key=payment_link_body["idempotency_key"],
                    checkout_options=payment_link_body["checkout_options"],
                    order_id=payment_link_body["order_id"]
                )
                if not payment_link_response.errors and payment_link_response.payment_link:
                    checkout_url = payment_link_response.payment_link.url
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors or "Unknown error"}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "location_id": settings.SQUARE_LOCATION_ID,
                "line_items": line_items,
                "state": "OPEN"
            }
            logger.debug(f"Order data: {json.dumps(order_data, indent=2)}")

            try:
                order_response = client.orders.create(
                    order=order_data,
                    idempotency_key=idempotency_key
                )
                if not order_response.errors and order_response.order:
                    order_id = order_response.order.id
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors or "Unknown error"}, status=400)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                body = {
                    "order": order_data,
                    "idempotency_key": idempotency_key
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(
                    idempotency_key=payment_link_body["idempotency_key"],
                    checkout_options=payment_link_body["checkout_options"],
                    order_id=payment_link_body["order_id"]
                )
                if not payment_link_response.errors and payment_link_response.payment_link:
                    checkout_url = payment_link_response.payment_link.url
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors or "Unknown error"}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"  # Confirmed as CAD
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "location_id": settings.SQUARE_LOCATION_ID,
                "line_items": line_items,
                "state": "OPEN"
            }
            logger.debug(f"Order data: {json.dumps(order_data, indent=2)}")

            try:
                order_response = client.orders.create(
                    order=order_data,
                    idempotency_key=idempotency_key
                )
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                body = {
                    "order": order_data,
                    "idempotency_key": idempotency_key
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"  # Changed to CAD
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "location_id": settings.SQUARE_LOCATION_ID,
                "line_items": line_items,
                "state": "OPEN"
            }
            logger.debug(f"Order data: {json.dumps(order_data, indent=2)}")

            try:
                order_response = client.orders.create(
                    order=order_data,
                    idempotency_key=idempotency_key
                )
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                body = {
                    "order": order_data,
                    "idempotency_key": idempotency_key
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
        
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "USD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "location_id": settings.SQUARE_LOCATION_ID,
                "line_items": line_items,
                "state": "OPEN"
            }
            logger.debug(f"Order data: {json.dumps(order_data, indent=2)}")

            try:
                order_response = client.orders.create(
                    order=order_data,
                    idempotency_key=idempotency_key
                )
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                body = {
                    "order": order_data,
                    "idempotency_key": idempotency_key
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "USD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "location_id": settings.SQUARE_LOCATION_ID,
                "line_items": line_items,
                "state": "OPEN"
            }
            logger.debug(f"Order data: {json.dumps(order_data, indent=2)}")

            try:
                order_response = client.orders.create(
                    order=order_data,
                    idempotency_key=idempotency_key
                )  # Pass order and idempotency_key directly
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except AttributeError as e:
                logger.error(f"SDK AttributeError: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                body = {
                    "order": order_data,
                    "idempotency_key": idempotency_key
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "USD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_body = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_body, indent=2)}")

            try:
                order_response = client.orders.create(body=order_body)  # Use 'create' instead of 'create_order'
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except AttributeError as e:
                logger.error(f"SDK AttributeError: {str(e)}. Falling back to HTTP request.")
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2023-10-18"
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(order_body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']  # Product object from cart
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents
                size = item.get('size', '')  # Get size, default to empty string

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "USD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)  # Convert to cents
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Create Square order using SDK
            idempotency_key = str(uuid.uuid4())
            order_body = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_body, indent=2)}")

            try:
                order_response = client.orders.create(body=order_body)
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except AttributeError as e:
                logger.error(f"SDK AttributeError: {str(e)}. Falling back to HTTP request.")
                # Fallback to HTTP request
                headers = {
                    "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Square-Version": "2025-05-21"
                }
                try:
                    response = requests.post(
                        "https://connect.squareupsandbox.com/v2/orders",
                        headers=headers,
                        data=json.dumps(order_body),
                        timeout=10
                    )
                    if response.status_code == 200:
                        order_id = response.json()['order']['id']
                        logger.debug(f"Order created via HTTP: {order_id}")
                    else:
                        error_message = response.json().get('errors', ['Unknown error'])
                        logger.error(f"HTTP Order creation failed: {error_message}")
                        return JsonResponse({"error": error_message}, status=response.status_code)
                except requests.RequestException as e:
                    logger.error(f"HTTP request failed: {str(e)}")
                    return JsonResponse({"error": f"HTTP request failed: {str(e)}"}, status=500)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link for the order
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"  # Update for production
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.checkout.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']  # Product object from cart
                quantity = str(item['quantity'])
                price = int(float(item['new_price']) * 100)  # Convert to cents, ensure float conversion
                size = item.get('size', '')  # Get size, default to empty string

                # Create line item with size as part of name
                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "USD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(float(cart.get_total_price()) * 100)  # Convert to cents
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_body = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_body, indent=2)}")

            try:
                # Use the correct Orders API endpoint
                order_response = client.orders.create(body=order_body)
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except AttributeError as e:
                logger.error(f"SDK AttributeError: {str(e)}")
                return JsonResponse({"error": f"SDK error: {str(e)}. Please ensure the Square SDK is up to date."}, status=500)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link for the order
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"  # Update for production
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                # Use the correct Payment Links API endpoint
                payment_link_response = client.checkout.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    # Save order_id in session for webhook processing
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}", exc_info=True)
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")
            
            # Calculate total
            try:
                total_amount = int(cart.get_total_price() * 100)  # Use get_total_price
                logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            except (TypeError, ValueError) as e:
                logger.error(f"Error calculating cart total: {str(e)}")
                return JsonResponse({"error": "Invalid cart total"}, status=400)
            
            # Check for empty cart
            if total_amount <= 0:
                logger.error("Cart is empty or total is zero")
                return JsonResponse({"error": "Cart is empty or total is zero"}, status=400)
            
            # Verify credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)
            logger.debug(f"Access Token: {settings.SQUARE_ACCESS_TOKEN[:10]}...")
            logger.debug(f"Location ID: {settings.SQUARE_LOCATION_ID}")
            
            # Generate idempotency key
            idempotency_key = str(uuid.uuid4())
            logger.debug(f"Idempotency key: {idempotency_key}")

            # Prepare API request
            headers = {
                "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "Square-Version": "2023-10-18"
            }

            body = {
                "idempotency_key": idempotency_key,
                "quick_pay": {
                    "name": "Cart Total",
                    "price_money": {
                        "amount": total_amount,
                        "currency": "USD"
                    },
                    "location_id": settings.SQUARE_LOCATION_ID
                }
            }

            logger.debug(f"Request headers: {headers}")
            logger.debug(f"Request body: {json.dumps(body, indent=2)}")
            
            # Make API request
            try:
                response = requests.post(
                    "https://connect.squareupsandbox.com/v2/online-checkout/payment-links",
                    headers=headers,
                    data=json.dumps(body),
                    timeout=10
                )
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed: {str(e)}")
                return JsonResponse({"error": f"API request failed: {str(e)}"}, status=500)

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response content: {response.content}")

            # Parse response
            try:
                data = response.json()
                if response.status_code == 200:
                    checkout_url = data["payment_link"]["url"]
                    logger.debug(f"Checkout URL: {checkout_url}")
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    error_message = data.get("errors", ["Unknown error"])
                    logger.error(f"API error: {error_message}")
                    return JsonResponse({"error": error_message}, status=response.status_code)
            except ValueError as e:
                logger.error(f"Failed to parse response: {str(e)}, Content: {response.content}")
                return JsonResponse({"error": "Failed to parse response from Square"}, status=500)
            except KeyError as e:
                logger.error(f"Missing key in response: {str(e)}, Content: {response.content}")
                return JsonResponse({"error": f"Missing key in response: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents: {cart.cart}")

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                product = item['product']  # Product object from cart
                quantity = str(item['quantity'])
                price = int(item['new_price'] * 100)  # Convert to cents
                size = item.get('size', '')  # Get size, default to empty string if not present

                # Create line item with size as a modifier or note
                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "USD"
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            total_amount = int(cart.get_total_price() * 100)  # Convert to cents
            logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
            if total_amount <= 0:
                logger.error("Cart total is zero")
                return JsonResponse({"error": "Cart total is zero"}, status=400)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_body = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_body, indent=2)}")

            try:
                order_response = client.orders.create(body=order_body)
                if order_response.is_success():
                    order_id = order_response.body['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    logger.error(f"Order creation failed: {order_response.errors}")
                    return JsonResponse({"error": order_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Order creation error: {str(e)}")
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link for the order
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/"  # Update for production
                },
                "order_id": order_id
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
                payment_link_response = client.payment_links.create_payment_link(body=payment_link_body)
                if payment_link_response.is_success():
                    checkout_url = payment_link_response.body['payment_link']['url']
                    logger.debug(f"Checkout URL: {checkout_url}")
                    # Save order_id in session for later use (e.g., webhook processing)
                    request.session['square_order_id'] = order_id
                    return JsonResponse({"checkout_url": checkout_url})
                else:
                    logger.error(f"Payment link creation failed: {payment_link_response.errors}")
                    return JsonResponse({"error": payment_link_response.errors}, status=400)
            except Exception as e:
                logger.error(f"Payment link creation error: {str(e)}")
                return JsonResponse({"error": f"Payment link creation failed: {str(e)}"}, status=500)

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
        
        
@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(APIView):
    authentication_classes = []

    def post(self, request):
        signature_header = request.headers.get('x-square-hmacsha256-signature')
        notification_url = "http://localhost:8000/cart/webhook/"  # Update for production
        payload = notification_url + request.body.decode('utf-8')

        try:
            computed_signature = hmac.new(
                settings.SQUARE_WEBHOOK_SIGNATURE_KEY.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).digest()
            computed_signature = base64.b64encode(computed_signature).decode('utf-8')
            is_valid = hmac.compare_digest(computed_signature.encode('utf-8'), signature_header.encode('utf-8'))
        except Exception as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse({"error": f"Webhook verification failed: {str(e)}"}, status=400)

        if not is_valid:
            logger.error("Invalid webhook signature")
            return JsonResponse({"error": "Invalid signature"}, status=400)

        event = request.data
        logger.debug(f"Webhook event: {json.dumps(event, indent=2)}")

        if event.get("type") == "payment.created":
            data = event.get("data", {}).get("object", {}).get("payment", {})
            transaction_id = data.get("id")
            amount = data.get("amount_money", {}).get("amount", 0) / 100
            status = data.get("status", "PENDING").lower()
            order_id = data.get("order_id")

            try:
                Payment.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    transaction_id=transaction_id,
                    amount=amount,
                    status=status,
                    order_id=order_id
                )
                if status == "completed":
                    cart = Cart(request)
                    cart.clear()
                    logger.debug(f"Cart cleared for payment: {transaction_id}")
                logger.debug(f"Payment recorded: {transaction_id}, Order ID: {order_id}")
                return JsonResponse({"status": "success"}, status=200)
            except Exception as e:
                logger.error(f"Payment recording failed: {str(e)}")
                return JsonResponse({"error": f"Payment recording failed: {str(e)}"}, status=500)

        return JsonResponse({"status": "ignored"}, status=200)
    authentication_classes = []

    def post(self, request):
        signature_header = request.headers.get('x-square-hmacsha256-signature')
        notification_url = "http://localhost:8000/cart/webhook/"  # Update for production
        payload = notification_url + request.body.decode('utf-8')

        try:
            computed_signature = hmac.new(
                settings.SQUARE_WEBHOOK_SIGNATURE_KEY.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).digest()
            computed_signature = base64.b64encode(computed_signature).decode('utf-8')
            is_valid = hmac.compare_digest(computed_signature.encode('utf-8'), signature_header.encode('utf-8'))
        except Exception as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse({"error": f"Webhook verification failed: {str(e)}"}, status=400)

        if not is_valid:
            logger.error("Invalid webhook signature")
            return JsonResponse({"error": "Invalid signature"}, status=400)

        event = request.data
        logger.debug(f"Webhook event: {json.dumps(event, indent=2)}")

        if event.get("type") == "payment.created":
            data = event.get("data", {}).get("object", {}).get("payment", {})
            transaction_id = data.get("id")
            amount = data.get("amount_money", {}).get("amount", 0) / 100
            status = data.get("status", "PENDING").lower()
            order_id = data.get("order_id")

            try:
                Payment.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    transaction_id=transaction_id,
                    amount=amount,
                    status=status,
                    order_id=order_id
                )
                if status == "completed":
                    cart = Cart(request)
                    cart.clear()
                    logger.debug(f"Cart cleared for payment: {transaction_id}")
                logger.debug(f"Payment recorded: {transaction_id}, Order ID: {order_id}")
                return JsonResponse({"status": "success"}, status=200)
            except Exception as e:
                logger.error(f"Payment recording failed: {str(e)}")
                return JsonResponse({"error": f"Payment recording failed: {str(e)}"}, status=500)

        return JsonResponse({"status": "ignored"}, status=200)
    authentication_classes = []

    @csrf_exempt
    def post(self, request):
        signature_header = request.headers.get('x-square-hmacsha256-signature')
        notification_url = "http://localhost:8000/cart/webhook/"  # Update for production
        payload = notification_url + request.body.decode('utf-8')

        try:
            computed_signature = hmac.new(
                settings.SQUARE_WEBHOOK_SIGNATURE_KEY.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).digest()
            computed_signature = base64.b64encode(computed_signature).decode('utf-8')
            is_valid = hmac.compare_digest(computed_signature.encode('utf-8'), signature_header.encode('utf-8'))
        except Exception as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse({"error": f"Webhook verification failed: {str(e)}"}, status=400)

        if not is_valid:
            logger.error("Invalid webhook signature")
            return JsonResponse({"error": "Invalid signature"}, status=400)

        event = request.data
        logger.debug(f"Webhook event: {json.dumps(event, indent=2)}")

        if event.get("type") == "payment.created":
            data = event.get("data", {}).get("object", {}).get("payment", {})
            transaction_id = data.get("id")
            amount = data.get("amount_money", {}).get("amount", 0) / 100
            status = data.get("status", "PENDING").lower()
            order_id = data.get("order_id")

            try:
                Payment.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    transaction_id=transaction_id,
                    amount=amount,
                    status=status,
                    order_id=order_id
                )
                if status == "completed":
                    cart = Cart(request)
                    cart.clear()
                    logger.debug(f"Cart cleared for payment: {transaction_id}")
                logger.debug(f"Payment recorded: {transaction_id}, Order ID: {order_id}")
                return JsonResponse({"status": "success"}, status=200)
            except Exception as e:
                logger.error(f"Payment recording failed: {str(e)}")
                return JsonResponse({"error": f"Payment recording failed: {str(e)}"}, status=500)

        return JsonResponse({"status": "ignored"}, status=200)
    authentication_classes = []

    @csrf_exempt
    def post(self, request):
        signature_header = request.headers.get('x-square-hmacsha256-signature')
        notification_url = "http://localhost:8000/cart/webhook/"  # Update for production
        payload = notification_url + request.body.decode('utf-8')

        try:
            computed_signature = hmac.new(
                settings.SQUARE_WEBHOOK_SIGNATURE_KEY.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).digest()
            computed_signature = base64.b64encode(computed_signature).decode('utf-8')
            is_valid = hmac.compare_digest(computed_signature.encode('utf-8'), signature_header.encode('utf-8'))
        except Exception as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse({"error": f"Webhook verification failed: {str(e)}"}, status=400)

        if not is_valid:
            logger.error("Invalid webhook signature")
            return JsonResponse({"error": "Invalid signature"}, status=400)

        event = request.data
        logger.debug(f"Webhook event: {json.dumps(event, indent=2)}")

        if event.get("type") == "payment.created":
            data = event.get("data", {}).get("object", {}).get("payment", {})
            transaction_id = data.get("id")
            amount = data.get("amount_money", {}).get("amount", 0) / 100
            status = data.get("status", "PENDING").lower()
            order_id = data.get("order_id")

            try:
                Payment.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    transaction_id=transaction_id,
                    amount=amount,
                    status=status,
                    order_id=order_id
                )
                if status == "completed":
                    cart = Cart(request)
                    cart.clear()
                    logger.debug(f"Cart cleared for payment: {transaction_id}")
                logger.debug(f"Payment recorded: {transaction_id}, Order ID: {order_id}")
                return JsonResponse({"status": "success"}, status=200)
            except Exception as e:
                logger.error(f"Payment recording failed: {str(e)}")
                return JsonResponse({"error": f"Payment recording failed: {str(e)}"}, status=500)

        return JsonResponse({"status": "ignored"}, status=200)
    authentication_classes = []

    @csrf_exempt
    def post(self, request):
        signature_header = request.headers.get('x-square-hmacsha256-signature')
        notification_url = "http://localhost:8000/cart/webhook/"  # Update for production
        payload = notification_url + request.body.decode('utf-8')

        try:
            computed_signature = hmac.new(
                settings.SQUARE_WEBHOOK_SIGNATURE_KEY.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).digest()
            computed_signature = base64.b64encode(computed_signature).decode('utf-8')
            is_valid = hmac.compare_digest(computed_signature.encode('utf-8'), signature_header.encode('utf-8'))
        except Exception as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse({"error": f"Webhook verification failed: {str(e)}"}, status=400)

        if not is_valid:
            logger.error("Invalid webhook signature")
            return JsonResponse({"error": "Invalid signature"}, status=400)

        event = request.data
        logger.debug(f"Webhook event: {json.dumps(event, indent=2)}")

        if event.get("type") == "payment.created":
            data = event.get("data", {}).get("object", {}).get("payment", {})
            transaction_id = data.get("id")
            amount = data.get("amount_money", {}).get("amount", 0) / 100
            status = data.get("status", "PENDING").lower()
            order_id = data.get("order_id")

            try:
                Payment.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    transaction_id=transaction_id,
                    amount=amount,
                    status=status,
                    order_id=order_id
                )
                if status == "completed":
                    cart = Cart(request)
                    cart.clear()
                    logger.debug(f"Cart cleared for payment: {transaction_id}")
                logger.debug(f"Payment recorded: {transaction_id}, Order ID: {order_id}")
                return JsonResponse({"status": "success"}, status=200)
            except Exception as e:
                logger.error(f"Payment recording failed: {str(e)}")
                return JsonResponse({"error": f"Payment recording failed: {str(e)}"}, status=500)

        return JsonResponse({"status": "ignored"}, status=200)
    authentication_classes = []

    @csrf_exempt
    def post(self, request):
        signature_header = request.headers.get('x-square-hmacsha256-signature')
        notification_url = "http://localhost:8000/cart/webhook/"  # Update for production
        payload = notification_url + request.body.decode('utf-8')

        try:
            computed_signature = hmac.new(
                settings.SQUARE_WEBHOOK_SIGNATURE_KEY.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).digest()
            computed_signature = base64.b64encode(computed_signature).decode('utf-8')
            is_valid = hmac.compare_digest(computed_signature, signature_header)
        except Exception as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse({"error": f"Webhook verification failed: {str(e)}"}, status=400)

        if not is_valid:
            logger.error("Invalid webhook signature")
            return JsonResponse({"error": "Invalid signature"}, status=400)

        event = request.data
        logger.debug(f"Webhook event: {json.dumps(event, indent=2)}")

        if event.get("type") == "payment.created":
            data = event.get("data", {}).get("object", {}).get("payment", {})
            transaction_id = data.get("id")
            amount = data.get("amount_money", {}).get("amount", 0) / 100
            status = data.get("status", "PENDING").lower()
            order_id = data.get("order_id")  # Link to order

            try:
                Payment.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    transaction_id=transaction_id,
                    amount=amount,
                    status=status,
                    order_id=order_id  # Store order_id if your Payment model supports it
                )
                logger.debug(f"Payment recorded: {transaction_id}, Order ID: {order_id}")
                # Clear cart after successful payment
                if status == "completed":
                    cart = Cart(request)
                    cart.clear()
                return JsonResponse({"status": "success"}, status=200)
            except Exception as e:
                logger.error(f"Payment recording failed: {str(e)}")
                return JsonResponse({"error": f"Payment recording failed: {str(e)}"}, status=500)

        return JsonResponse({"status": "ignored"}, status=200)