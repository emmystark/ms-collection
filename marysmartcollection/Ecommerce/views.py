from django.shortcuts import render



from . models import Category, Product 
from django.shortcuts import render

from cart.forms import CartAddProductForm

from django.shortcuts import render, get_object_or_404
from django.shortcuts import render, HttpResponse, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login, logout
from django.contrib.auth.decorators import login_required

from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from .models import PaymentUser
from django.urls import reverse

import re
from bs4 import BeautifulSoup
from django.db.models import Q
from cart.cart import Cart

def home(request,category_slug=None):
    category = None
    categories = Category.objects.all()

    products = Product.objects.filter(available=True)
    # new_price = Product.formatted_price
    if category_slug:
        category = get_object_or_404(Category,
                                     slug=category_slug)
        products = products.filter(category=category)
    
    context = {
        'category' : category,
        'categories': categories,
        'products': products,
        # 'new_price': new_price,
        }
    
    if request.resolver_match.url_name == 'home':
        template_name = 'index.html'
    else:
        template_name = 'collection-full.html'
    return render(request, template_name, context)




def product_detail(request, id, slug,category_slug=None):
    category = None
    categories = Category.objects.all()

    products = Product.objects.filter(available=True)
    if category_slug:
        category = get_object_or_404(Category,
                                     slug=category_slug)
        products = products.filter(category=category)
    product = get_object_or_404(Product,
                                id=id,
                                slug=slug,
                                available=True)
    cart_product_form = CartAddProductForm()

    products = Product.objects.filter(available=True)


    context = {
        'product' : product,
        'products': products,
        'cart_product_form': cart_product_form,
        'category' : category,
        'categories': categories,
        }
    
    

    return render(request, 'single-product.html', context)


def payment(request,category_slug=None):
    if request.method == 'POST':
        username = request.POST.get("username")
        address = request.POST.get("address")
        city = request.POST.get("city")
        state = request.POST.get("state")
        zip_code = request.POST.get("zip_code")
        phone_number = request.POST.get("phone_number")

    try:
        # Create the user
        user = PaymentUser.objects.create_user(
            username=username,
            address=address,
            phone_number=phone_number,
            city=city,
            zip_code=zip_code,
            state=state
        )
        user.save()
        # print(user)
        return redirect(reverse('Ecommerce:paymentname'))
    except Exception as e:
        # Handle the exception (e.g., log it, show an error message)
        print(f"Error creating user: {e}")

    category = None
    categories = Category.objects.all()

    products = Product.objects.filter(available=True)
    if category_slug:
        category = get_object_or_404(Category,
                                     slug=category_slug)
        products = products.filter(category=category)
    
    cart = Cart(request)
    context = {
        'cart': cart,
        'category' : category,
        'categories': categories,
        'products': products
        }

    
    return render(request, 'payments.html', context)



def search(request,category_slug=None):
    category = None
    categories = Category.objects.all()

    products = Product.objects.filter(available=True)
    if category_slug:
        category = get_object_or_404(Category,
                                     slug=category_slug)
        products = products.filter(category=category)
    
  
    if request.method == 'GET':
        query = request.GET.get('query')

        # Search the database for products matching the query
        result = Product.objects.filter(Q(name__icontains=query) | Q(new_price__icontains=query))
        print(result)
        context = {
        'category' : category,
        'categories': categories,
        'results': result,
        'query': query,
        }

    return render(request, 'result.html',context)


def success(resquest): 
    return render(resquest, 'successfulPage.html')



def cart_view(request):
    cart = Cart(request)
    cart_item_count = sum(item['quantity'] for item in cart)

    return render(request, 'base.html', {'cart_item_count': cart_item_count, 'cart': cart})

def paymentname(request):
    cart = Cart(request)
    context = {
        'cart': cart,
        }
    return render(request, 'paymentName.html', context)
    
    
def custom_404(request, exception):
    return render(request, '404.html', status=404)



def about(request):
    return render(request, 'about.html', )
def blog(request):
    return render(request, 'blog.html', )
def contact(request):
    return render(request, 'contact.html', )
def login(request):
    return render(request, 'login.html', )
def shoping_cart(request):
    return render(request, 'shoping-cart.html', )
def coming_soon(request):
    return render(request, 'coming-soon.html', )
def collection_full(request,category_slug=None):
    category = None
    categories = Category.objects.all()

    products = Product.objects.filter(available=True)
    # new_price = Product.formatted_price
    if category_slug:
        category = get_object_or_404(Category,
                                     slug=category_slug)
        products = products.filter(category=category)
    
    context = {
        'category' : category,
        'categories': categories,
        'products': products,
        # 'new_price': new_price,
        }
    

    return render(request, 'collection-full.html', context)
# def single_product(request):
#     return render(request, 'single-product.html', )


def single_product(request, product_id=None):
    product = get_object_or_404(Product, id=product_id) if product_id else None
    cart_product_form = CartAddProductForm()
    return render(request, 'single-product.html', {
        'product': product,
        'cart_product_form': cart_product_form
    })