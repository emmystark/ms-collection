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
from decimal import Decimal



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
def convert_decimals_to_floats(obj):
    """Recursively convert Decimal objects and model instances to JSON-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals_to_floats(item) for item in obj]
    elif hasattr(obj, '__dict__'):  # Handle Django model instances
        return convert_decimals_to_floats(obj.__dict__)
    return obj

def convert_decimals_to_floats(obj):
    """Recursively convert Decimal objects and model instances to JSON-serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals_to_floats(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        # Convert model instance to dict, excluding non-serializable fields
        data = {k: v for k, v in obj.__dict__.items() if k != '_state'}
        return convert_decimals_to_floats(data)
    return obj

class CreateCheckoutView(View):
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents before conversion: {cart.cart}")

            # Convert all Decimal objects and model instances in cart.cart
            try:
                # Replace product objects with serializable dictionaries
                modified_cart = {}
                for key, item in cart.cart.items():
                    item_copy = item.copy()
                    if 'product' in item_copy:
                        product = item_copy['product']
                        # Convert product to dict with essential fields
                        item_copy['product'] = {
                            'id': product.id,
                            'name': product.name,
                            # Add other necessary fields, excluding Decimal or non-serializable
                        }
                    modified_cart[key] = convert_decimals_to_floats(item_copy)
                # Update session with converted cart
                request.session['cart'] = modified_cart
                request.session.modified = True  # Force session save
                cart.cart = modified_cart  # Update cart object
                logger.debug(f"Cart contents after conversion: {request.session['cart']}")
            except Exception as e:
                logger.error(f"Error serializing cart session data: {str(e)}")
                return JsonResponse({"error": f"Failed to serialize cart data: {str(e)}"}, status=500)

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                try:
                    product = item['product']  # Now a dict
                    quantity = str(item['quantity'])
                    price = int(float(item['new_price']) * 100)  # Convert to cents
                    size = item.get('size', '')
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Invalid cart item: {str(e)}")
                    return JsonResponse({"error": f"Invalid cart item: {str(e)}"}, status=400)

                line_item = {
                    "quantity": quantity,
                    "name": f"{product['name']} ({size})" if size else product['name'],
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"  # Match test_payment_link_alt.py
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation, ensure float
            try:
                total_price = cart.get_total_price()
                if isinstance(total_price, Decimal):
                    total_price = float(total_price)
                total_amount = int(total_price * 100)  # Convert to cents
                logger.debug(f"Cart total: {total_price}, Total amount (cents): {total_amount}")
                if total_amount <= 0:
                    logger.error("Cart total is zero")
                    return JsonResponse({"error": "Cart total is zero"}, status=400)
            except (TypeError, ValueError) as e:
                logger.error(f"Error calculating cart total: {str(e)}")
                return JsonResponse({"error": f"Invalid cart total: {str(e)}"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_data, indent=2)}")

            headers = {
                "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "Square-Version": "2023-10-18"
            }
            try:
                response = requests.post(
                    "https://connect.squareupsandbox.com/v2/orders",
                    headers=headers,
                    data=json.dumps(order_data),
                    timeout=10
                )
                if response.status_code == 200:
                    order_id = response.json()['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    error_message = response.json().get('errors', ['Unknown error'])
                    logger.error(f"Order creation failed: {error_message}")
                    return JsonResponse({"error": error_message}, status=response.status_code)
            except requests.RequestException as e:
                logger.error(f"Order creation HTTP request failed: {str(e)}")
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/",
                    "currency": "CAD",  # Match test_payment_link_alt.py
                    "ask_for_shipping_address": False
                },
                "order": {
                    "order_id": order_id,
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items  # Include line_items to match test_payment_link_alt.py
                }
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
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
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents before conversion: {cart.cart}")

            # Convert all Decimal objects in cart.cart to float
            try:
                # Deep copy to avoid modifying the original cart prematurely
                modified_cart = convert_decimals_to_floats(cart.cart)
                # Update session with converted cart
                request.session['cart'] = modified_cart
                request.session.modified = True  # Force session save
                logger.debug(f"Cart contents after conversion: {request.session['cart']}")
            except Exception as e:
                logger.error(f"Error serializing cart session data: {str(e)}")
                return JsonResponse({"error": f"Failed to serialize cart data: {str(e)}"}, status=500)

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                try:
                    product = item['product']
                    quantity = str(item['quantity'])
                    price = int(float(item['new_price']) * 100)  # Convert to cents
                    size = item.get('size', '')
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Invalid cart item: {str(e)}")
                    return JsonResponse({"error": f"Invalid cart item: {str(e)}"}, status=400)

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"  # Match test_payment_link_alt.py
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation, convert Decimal to float
            try:
                total_price = cart.get_total_price()
                if isinstance(total_price, Decimal):
                    total_price = float(total_price)
                total_amount = int(total_price * 100)  # Convert to cents
                logger.debug(f"Cart total: {total_price}, Total amount (cents): {total_amount}")
                if total_amount <= 0:
                    logger.error("Cart total is zero")
                    return JsonResponse({"error": "Cart total is zero"}, status=400)
            except (TypeError, ValueError) as e:
                logger.error(f"Error calculating cart total: {str(e)}")
                return JsonResponse({"error": f"Invalid cart total: {str(e)}"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_data, indent=2)}")

            headers = {
                "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "Square-Version": "2023-10-18"
            }
            try:
                response = requests.post(
                    "https://connect.squareupsandbox.com/v2/orders",
                    headers=headers,
                    data=json.dumps(order_data),
                    timeout=10
                )
                if response.status_code == 200:
                    order_id = response.json()['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    error_message = response.json().get('errors', ['Unknown error'])
                    logger.error(f"Order creation failed: {error_message}")
                    return JsonResponse({"error": error_message}, status=response.status_code)
            except requests.RequestException as e:
                logger.error(f"Order creation HTTP request failed: {str(e)}")
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/",
                    "currency": "CAD",  # Match test_payment_link_alt.py
                    "ask_for_shipping_address": False
                },
                "order": {
                    "order_id": order_id,
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items  # Include line_items to match test_payment_link_alt.py
                }
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
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
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
    def get(self, request):
        try:
            # Initialize cart
            cart = Cart(request)
            logger.debug(f"Cart contents before conversion: {cart.cart}")

            # Convert all Decimal objects in cart.cart to float
            try:
                cart.cart = convert_decimals_to_floats(cart.cart)
                cart.save()  # Save the modified cart to session early
                logger.debug(f"Cart contents after conversion: {cart.cart}")
            except Exception as e:
                logger.error(f"Error serializing cart session data: {str(e)}")
                return JsonResponse({"error": f"Failed to serialize cart data: {str(e)}"}, status=500)

            # Check for empty cart
            if not cart.cart:
                logger.error("Cart is empty")
                return JsonResponse({"error": "Cart is empty"}, status=400)

            # Prepare line items for Square order
            line_items = []
            for item in cart:
                try:
                    product = item['product']
                    quantity = str(item['quantity'])
                    price = int(float(item['new_price']) * 100)  # Convert to cents
                    size = item.get('size', '')
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Invalid cart item: {str(e)}")
                    return JsonResponse({"error": f"Invalid cart item: {str(e)}"}, status=400)

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"  # Match test_payment_link_alt.py
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation, convert Decimal to float
            try:
                total_price = cart.get_total_price()
                if isinstance(total_price, Decimal):
                    total_price = float(total_price)
                total_amount = int(total_price * 100)  # Convert to cents
                logger.debug(f"Cart total: {total_price}, Total amount (cents): {total_amount}")
                if total_amount <= 0:
                    logger.error("Cart total is zero")
                    return JsonResponse({"error": "Cart total is zero"}, status=400)
            except (TypeError, ValueError) as e:
                logger.error(f"Error calculating cart total: {str(e)}")
                return JsonResponse({"error": f"Invalid cart total: {str(e)}"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_data, indent=2)}")

            headers = {
                "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "Square-Version": "2023-10-18"
            }
            try:
                response = requests.post(
                    "https://connect.squareupsandbox.com/v2/orders",
                    headers=headers,
                    data=json.dumps(order_data),
                    timeout=10
                )
                if response.status_code == 200:
                    order_id = response.json()['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    error_message = response.json().get('errors', ['Unknown error'])
                    logger.error(f"Order creation failed: {error_message}")
                    return JsonResponse({"error": error_message}, status=response.status_code)
            except requests.RequestException as e:
                logger.error(f"Order creation HTTP request failed: {str(e)}")
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/",
                    "currency": "CAD",  # Match test_payment_link_alt.py
                    "ask_for_shipping_address": False
                },
                "order": {
                    "order_id": order_id,
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items  # Include line_items to match test_payment_link_alt.py
                }
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
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
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
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
                try:
                    product = item['product']
                    quantity = str(item['quantity'])
                    price = int(float(item['new_price']) * 100)  # Convert to cents
                    size = item.get('size', '')
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Invalid cart item: {str(e)}")
                    return JsonResponse({"error": f"Invalid cart item: {str(e)}"}, status=400)

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"  # Match test_payment_link_alt.py
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation, convert Decimal to float
            try:
                total_price = cart.get_total_price()
                if isinstance(total_price, Decimal):
                    total_price = float(total_price)
                total_amount = int(total_price * 100)  # Convert to cents
                logger.debug(f"Cart total: {total_price}, Total amount (cents): {total_amount}")
                if total_amount <= 0:
                    logger.error("Cart total is zero")
                    return JsonResponse({"error": "Cart total is zero"}, status=400)
            except (TypeError, ValueError) as e:
                logger.error(f"Error calculating cart total: {str(e)}")
                return JsonResponse({"error": f"Invalid cart total: {str(e)}"}, status=400)

            # Ensure cart session data is JSON-serializable
            try:
                # Convert any Decimal values in cart.cart to float
                for item in cart.cart.values():
                    if 'new_price' in item and isinstance(item['new_price'], Decimal):
                        item['new_price'] = float(item['new_price'])
                # Save the modified cart to session
                cart.save()
            except Exception as e:
                logger.error(f"Error serializing cart session data: {str(e)}")
                return JsonResponse({"error": f"Failed to serialize cart data: {str(e)}"}, status=500)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_data, indent=2)}")

            headers = {
                "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "Square-Version": "2023-10-18"
            }
            try:
                response = requests.post(
                    "https://connect.squareupsandbox.com/v2/orders",
                    headers=headers,
                    data=json.dumps(order_data),
                    timeout=10
                )
                if response.status_code == 200:
                    order_id = response.json()['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    error_message = response.json().get('errors', ['Unknown error'])
                    logger.error(f"Order creation failed: {error_message}")
                    return JsonResponse({"error": error_message}, status=response.status_code)
            except requests.RequestException as e:
                logger.error(f"Order creation HTTP request failed: {str(e)}")
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/",
                    "currency": "CAD",  # Match test_payment_link_alt.py
                    "ask_for_shipping_address": False
                },
                "order": {
                    "order_id": order_id,
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items  # Include line_items to match test_payment_link_alt.py
                }
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
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
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
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
                try:
                    product = item['product']
                    quantity = str(item['quantity'])
                    price = int(float(item['new_price']) * 100)  # Convert to cents
                    size = item.get('size', '')
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Invalid cart item: {str(e)}")
                    return JsonResponse({"error": f"Invalid cart item: {str(e)}"}, status=400)

                line_item = {
                    "quantity": quantity,
                    "name": f"{product.name} ({size})" if size else product.name,
                    "base_price_money": {
                        "amount": price,
                        "currency": "CAD"  # Match test_payment_link_alt.py
                    }
                }
                line_items.append(line_item)

            # Calculate total for validation
            try:
                total_amount = int(float(cart.get_total_price()) * 100)  # Convert to cents
                logger.debug(f"Cart total: {cart.get_total_price()}, Total amount (cents): {total_amount}")
                if total_amount <= 0:
                    logger.error("Cart total is zero")
                    return JsonResponse({"error": "Cart total is zero"}, status=400)
            except (TypeError, ValueError) as e:
                logger.error(f"Error calculating cart total: {str(e)}")
                return JsonResponse({"error": f"Invalid cart total: {str(e)}"}, status=400)

            # Verify Square credentials
            if not settings.SQUARE_ACCESS_TOKEN or not settings.SQUARE_LOCATION_ID:
                logger.error("Missing Square credentials: ACCESS_TOKEN or LOCATION_ID")
                return JsonResponse({"error": "Missing Square credentials"}, status=500)

            # Create Square order
            idempotency_key = str(uuid.uuid4())
            order_data = {
                "order": {
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items,
                    "state": "OPEN"
                },
                "idempotency_key": idempotency_key
            }
            logger.debug(f"Order request body: {json.dumps(order_data, indent=2)}")

            headers = {
                "Authorization": f"Bearer {settings.SQUARE_ACCESS_TOKEN}",
                "Content-Type": "application/json",
                "Square-Version": "2023-10-18"
            }
            try:
                response = requests.post(
                    "https://connect.squareupsandbox.com/v2/orders",
                    headers=headers,
                    data=json.dumps(order_data),
                    timeout=10
                )
                if response.status_code == 200:
                    order_id = response.json()['order']['id']
                    logger.debug(f"Order created: {order_id}")
                else:
                    error_message = response.json().get('errors', ['Unknown error'])
                    logger.error(f"Order creation failed: {error_message}")
                    return JsonResponse({"error": error_message}, status=response.status_code)
            except requests.RequestException as e:
                logger.error(f"Order creation HTTP request failed: {str(e)}")
                return JsonResponse({"error": f"Order creation failed: {str(e)}"}, status=500)

            # Create payment link
            payment_link_body = {
                "idempotency_key": str(uuid.uuid4()),
                "checkout_options": {
                    "redirect_url": "http://localhost:8000/cart/checkout/success/",
                    "currency": "CAD",  # Match test_payment_link_alt.py
                    "ask_for_shipping_address": False
                },
                "order": {
                    "order_id": order_id,
                    "location_id": settings.SQUARE_LOCATION_ID,
                    "line_items": line_items  # Include line_items to match test_payment_link_alt.py
                }
            }
            logger.debug(f"Payment link request body: {json.dumps(payment_link_body, indent=2)}")

            try:
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
            return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
        
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