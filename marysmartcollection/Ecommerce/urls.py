from django.urls import path
from . import views

app_name = "Ecommerce"

urlpatterns = [
    path('', views.home, name='home'),  # Route for homepage
    path('single-product/<int:product_id>/', views.single_product, name='single_product'),
    path('about/', views.about, name='about'),
    path('search/', views.search, name='search'),
    path('blog/', views.blog, name='blog'),
    path('coming-soon/', views.coming_soon, name='coming-soon'),
    path('contact/', views.contact, name='contact'),
    path('login/', views.login, name='login'),
    path('shoping-cart/', views.shoping_cart, name='shoping-cart'),
    path('single-product/', views.single_product, name='single-product'),
    path('collection-full/', views.collection_full, name='collection-full'),
    path('<int:id>/<slug:slug>/', views.product_detail,
        name = 'product_detail'),
] 
