from django.conf import settings
from Ecommerce.models import Product

class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart

    def add(self, product, quantity=1, size=None, override_quantity=False):
        product_id = str(product.id)
        if not hasattr(product, 'id') or not hasattr(product, 'name') or not hasattr(product, 'new_price'):
            raise ValueError(f"Invalid product: {product}")
        if product_id not in self.cart:
            self.cart[product_id] = {
                'quantity': 0,
                'size': size or 'N/A',
                'new_price': float(product.new_price),  # Ensure float
                'product': {'id': product.id, 'name': product.name}  # Store minimal product data
            }
        if override_quantity:
            self.cart[product_id]['quantity'] = quantity
        else:
            self.cart[product_id]['quantity'] += quantity
        self.cart[product_id]['size'] = size or 'N/A'
        self.save()
        total_quantity = sum(item['quantity'] for item in self.cart.values())
        return total_quantity

    def edit(self, product, quantity=None, size=None):
        """
        Edit quantity and/or size of an existing cart item.
        Args:
            product: Product instance or product_id (str or int)
            quantity: New quantity (int, optional)
            size: New size (str, optional)
        Raises:
            ValueError: If product_id is invalid or not in cart
        Returns:
            Updated total quantity of items in cart
        """
        product_id = str(product.id) if hasattr(product, 'id') else str(product)
        if product_id not in self.cart:
            raise ValueError(f"Product {product_id} not in cart")
        
        if quantity is not None:
            if not isinstance(quantity, int) or quantity < 0:
                raise ValueError("Quantity must be a non-negative integer")
            self.cart[product_id]['quantity'] = quantity
        
        if size is not None:
            self.cart[product_id]['size'] = size or 'N/A'
        
        self.save()
        total_quantity = sum(item['quantity'] for item in self.cart.values())
        return total_quantity

    def save(self):
        self.session[settings.CART_SESSION_ID] = self.cart
        self.session.modified = True

    def remove(self, product):
        product_id = str(product.id) if hasattr(product, 'id') else str(product)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def __iter__(self):
        for item in self.cart.values():
            item_copy = item.copy()
            if 'product' not in item_copy:
                item_copy['product'] = {'id': '', 'name': 'Unknown Product'}  # Fallback
            item_copy['new_price'] = float(item_copy['new_price'])  # Ensure float
            item_copy['total_price'] = item_copy['new_price'] * item_copy['quantity']
            item_copy['size'] = item_copy.get('size', 'N/A')
            yield item_copy

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        return float(sum(float(item['new_price']) * item['quantity'] for item in self.cart.values()))

    def clear(self):
        del self.session[settings.CART_SESSION_ID]
        self.save()