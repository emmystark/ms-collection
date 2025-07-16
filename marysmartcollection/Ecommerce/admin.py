from django.contrib import admin

# Register your models here.
from django.contrib import admin
# Register your models here.
from django.contrib import admin
from .models import Category, Product, PaymentUser
# from .models import PaymentUser
from django.contrib.auth.admin import UserAdmin

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'image', 'slug']
    prepopulated_fields = {'slug' : ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'new_price',
                    'available', 'created', 'updated']
    list_filter = ['available', 'created', 'updated']
    list_editable = ['new_price', 'available']
    prepopulated_fields = {'slug' : ('name', )}



class PaymentUserAdmin(UserAdmin):
    model = PaymentUser
    list_display = ('username','address', 'is_staff', 'phone_number', 'city', 'state', 'zip_code',  )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    
    fieldsets = (
        (None, {'fields': ('username', )}),
        ('Personal Info', {'fields': ('city', 'address', 'state', 'zip_code', )}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'address' ),
        }),
    )
    search_fields = ('username', 'address')
    ordering = ('username',)

# Register the CustomUserAdmin with the admin site
admin.site.register(PaymentUser, PaymentUserAdmin)