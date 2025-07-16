# test_payment_link.py
import requests
import json
import uuid

headers = {
    "Authorization": "Bearer EAAAl5B86DEy7i6oS5oCgfFaR_-N1d_TYOqIPN7rpf4o9X_YspEJODozLOZ8SnSh",
    "Content-Type": "application/json",
    "Square-Version": "2023-10-18"
}
payment_link_body = {
    "idempotency_key": str(uuid.uuid4()),
    "checkout_options": {
        "redirect_url": "http://localhost:8000/cart/checkout/success/",
        "currency": "CAD",
        "ask_for_shipping_address": False
    },
    "order": {
        "order_id": "YOUR_NEW_ORDER_ID",  # Replace with new order_id from test_create_order.py
        "location_id": "LY3CP5ZEYQGVR"
    }
}

try:
    response = requests.post(
        "https://connect.squareupsandbox.com/v2/online-checkout/payment-links",
        headers=headers,
        data=json.dumps(payment_link_body),
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    if response.status_code == 200:
        print(f"Payment link created: {response.json()['payment_link']['url']}")
    else:
        print(f"Payment link creation failed: {response.json().get('errors', ['Unknown error'])}")
except Exception as e:
    print(f"Error: {e}")