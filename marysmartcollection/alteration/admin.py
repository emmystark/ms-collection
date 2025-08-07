from django.contrib import admin
from .models import AlterationRequest, AlterationImage


class AlterationImageInline(admin.TabularInline):
    model = AlterationImage
    extra = 1
    readonly_fields = ['uploaded_at']


@admin.register(AlterationRequest)
class AlterationRequestAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'email', 'garment_type', 'status', 
        'preferred_date', 'delivery_option', 'created_at'
    ]
    list_filter = [
        'status', 'garment_type', 'delivery_option', 
        'created_at', 'preferred_date'
    ]
    search_fields = ['name', 'email', 'phone', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [AlterationImageInline]
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'email', 'phone')
        }),
        ('Garment Details', {
            'fields': ('garment_type', 'alteration_type', 'measurements', 'issue_description')
        }),
        ('Scheduling & Delivery', {
            'fields': ('preferred_date', 'delivery_option', 'pickup_address', 'delivery_address')
        }),
        ('Additional Information', {
            'fields': ('description', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('images')


@admin.register(AlterationImage)
class AlterationImageAdmin(admin.ModelAdmin):
    list_display = ['alteration_request', 'description', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['alteration_request__name', 'description']
    readonly_fields = ['uploaded_at']