from django.db import models
from django.core.validators import RegexValidator


class AlterationRequest(models.Model):
    GARMENT_CHOICES = [
        ('dress', 'Dress'),
        ('pants', 'Pants/Trousers'),
        ('skirt', 'Skirt'),
        ('blouse', 'Blouse/Shirt'),
        ('jacket', 'Jacket/Blazer'),
        ('jeans', 'Jeans'),
        ('formal', 'Formal Wear'),
        ('other', 'Other'),
    ]
    
    ALTERATION_CHOICES = [
        ('hemming', 'Hemming'),
        ('take_in', 'Take In'),
        ('let_out', 'Let Out'),
        ('shorten_sleeves', 'Shorten Sleeves'),
        ('lengthen_sleeves', 'Lengthen Sleeves'),
        ('zip_repair', 'Zip Repair'),
        ('button_replacement', 'Button Replacement'),
        ('waist_adjustment', 'Waist Adjustment'),
        ('other', 'Other'),
    ]
    
    DELIVERY_CHOICES = [
        ('pickup', 'Pickup from Location'),
        ('delivery', 'Home Delivery'),
    ]
    
    # Personal Information
    name = models.CharField(max_length=100, verbose_name="Full Name")
    email = models.EmailField(verbose_name="Email Address")
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        verbose_name="Phone Number"
    )
    
    # Garment Information
    garment_type = models.CharField(
        max_length=20, 
        choices=GARMENT_CHOICES,
        verbose_name="Garment Type"
    )
    alteration_type = models.CharField(
        max_length=200,
        verbose_name="Alteration Types",
        help_text="Comma-separated list of alteration types"
    )
    measurements = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Measurements",
        help_text="Optional measurements or sizing notes"
    )
    description = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Special Instructions",
        help_text="Any additional details or special requests"
    )
    
    # Delivery Information
    delivery_option = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default='pickup',
        verbose_name="Delivery Option"
    )
    pickup_address = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Pickup Address",
        help_text="Address for garment pickup (if applicable)"
    )
    delivery_address = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Delivery Address", 
        help_text="Address for garment delivery (if applicable)"
    )
    
    # Scheduling
    preferred_date = models.DateField(verbose_name="Preferred Date")
    
    # Issue Description
    issue_description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Issue Description",
        help_text="Brief description of what needs to be altered"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Alteration Request"
        verbose_name_plural = "Alteration Requests"
    
    def __str__(self):
        return f"{self.name} - {self.garment_type} ({self.status})"
    
    def get_alteration_types_list(self):
        """Return alteration types as a list"""
        if self.alteration_type:
            return [alt.strip() for alt in self.alteration_type.split(',')]
        return []


class AlterationImage(models.Model):
    """Model to store multiple images for each alteration request"""
    alteration_request = models.ForeignKey(
        AlterationRequest,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        upload_to='alteration_images/%Y/%m/%d/',
        verbose_name="Garment Image"
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Image Description"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = "Alteration Image"
        verbose_name_plural = "Alteration Images"
    
    def __str__(self):
        return f"Image for {self.alteration_request.name} - {self.alteration_request.garment_type}"