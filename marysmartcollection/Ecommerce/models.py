from django.db import models

# Create your models here.
from django.db import models
from django.urls import reverse
# Create your models here.

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _



from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile

from django.core.exceptions import ValidationError

from decimal import Decimal

from django.contrib.humanize.templatetags.humanize import intcomma

class CommaSeparatedIntegerField(models.DecimalField):
    def formated_price(self):
        return "{:,.2f}".format(self.new_price)

class Category(models.Model):

    name = models.CharField(max_length=200)

    image = models.ImageField(upload_to='category_image//%Y/%m/%d',
                              blank=True)

    slug = models.SlugField(max_length=200,
                            unique=True)
    
    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('category_detail', args=[self.slug])

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=["name"]),
        ]
        verbose_name = 'category'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('Ecommerce:product_list_by_category',
                       args=[self.slug])


class Product(models.Model):
    category = models.ForeignKey(Category,
                                 related_name='products',
                                 on_delete=models.CASCADE)
    name = models.CharField(max_length=10)
    slug = models.SlugField(max_length=10)
    image = models.ImageField(upload_to='category_image//%Y/%m/%d',
                              blank=True)


    image1 = models.ImageField(upload_to='category_image//%Y/%m/%d',
                              blank=True)


    image2 = models.ImageField(upload_to='category_image//%Y/%m/%d',
                              blank=True)

    sizes = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, max_length=250)
    old_price = CommaSeparatedIntegerField(max_digits=10, decimal_places=0, null=True)
    new_price = models.DecimalField(max_digits=10, decimal_places=0, null=True)
    def formatted_price(self):
        return intcomma(self.new_price)
    
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['id', 'slug']),
            models.Index(fields=['name']),
            models.Index(fields=['-created']),
        ]

    def __str__(self):
        return self.name
        
    def get_absolute_url(self):
        return reverse('Ecommerce:product_detail',
            args=[self.id, self.slug])


class PaymentUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        # username = self.normalize_full_name(username)
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(username, password, **extra_fields)

class PaymentUser(AbstractBaseUser, PermissionsMixin):
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15)
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    username = models.CharField(max_length=20, unique=True)
    zip_code = models.CharField(max_length=7)

    objects = PaymentUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['phone_number', 'address', 'city', 'state', 'zip_code']

    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='paymentuser_groups',  # Use a unique related_name
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='paymentuser_user_permissions',  # Use a unique related_name
    )
    
    def __str__(self):
        return self.username