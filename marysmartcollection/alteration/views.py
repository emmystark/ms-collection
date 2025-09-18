from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from .models import AlterationRequest, AlterationImage
from .forms import AlterationRequestForm, AlterationImageFormSet
import json


def alteration_request_view(request):
    """
    Handle both GET and POST requests for alteration form
    """
    if request.method == 'POST':
        form = AlterationRequestForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Save the alteration request
                    alteration_request = form.save()
                    
                    # Handle individual image uploads from the main upload section
                    uploaded_files = request.FILES.getlist('garment_images')
                    issue_description = request.POST.get('issue_description', '')
                    
                    # Update issue description if provided
                    if issue_description:
                        alteration_request.issue_description = issue_description
                        alteration_request.save()
                    
                    # Save uploaded images
                    for uploaded_file in uploaded_files:
                        AlterationImage.objects.create(
                            alteration_request=alteration_request,
                            image=uploaded_file,
                            description=f"Garment image - {uploaded_file.name}"
                        )
                    
                    messages.success(
                        request, 
                        'Your alteration request has been submitted successfully! '
                        'We will contact you within 24 hours to confirm the details.'
                    )
                    
                    # Return JSON response for AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Request submitted successfully!'
                        })
                    
                    return redirect('alteration:success')
                    
            except Exception as e:
                print(f"Error saving form: {e}")  # Debug print
                messages.error(
                    request, 
                    'There was an error processing your request. Please try again.'
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Error processing request. Please try again.'
                    })
        else:
            print(f"Form errors: {form.errors}")  # Debug print
            # Form validation errors
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = error_list[0]  # Get first error for each field
                
                return JsonResponse({
                    'success': False,
                    'errors': errors
                })
    else:
        form = AlterationRequestForm()
    
    context = {
        'form': form,
        'page_title': 'Request Alteration - Perfect Fit Always'
    }
    
    return render(request, 'alteration/alteration_form.html', context)


def alteration_success_view(request):
    """
    Success page after form submission
    """
    return render(request, 'alteration/success.html', {
        'page_title': 'Request Submitted - Perfect Fit Always'
    })


def alteration_list_view(request):
    """
    Admin view to list all alteration requests (optional)
    """
    requests = AlterationRequest.objects.all().order_by('-created_at')
    
    # Add pagination
    paginator = Paginator(requests, 20)  # Show 20 requests per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'page_title': 'Alteration Requests'
    }
    
    return render(request, 'alteration/request_list.html', context)


def alteration_detail_view(request, pk):
    """
    View individual alteration request details
    """
    alteration_request = get_object_or_404(AlterationRequest, pk=pk)
    
    context = {
        'request_obj': alteration_request,
        'images': alteration_request.images.all(),
        'page_title': f'Request #{alteration_request.pk} - {alteration_request.name}'
    }
    
    return render(request, 'alteration/request_detail.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def upload_images_ajax(request):
    """
    Handle AJAX image uploads
    """
    if request.FILES.getlist('images'):
        uploaded_files = request.FILES.getlist('images')
        file_info = []
        
        for file in uploaded_files:
            # Validate file size (5MB limit)
            if file.size > 5 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'error': f'File {file.name} is too large. Maximum size is 5MB.'
                })
            
            # Validate file type
            if not file.content_type.startswith('image/'):
                return JsonResponse({
                    'success': False,
                    'error': f'File {file.name} is not a valid image.'
                })
            
            file_info.append({
                'name': file.name,
                'size': file.size,
                'type': file.content_type
            })
        
        return JsonResponse({
            'success': True,
            'files': file_info
        })
    
    return JsonResponse({
        'success': False,
        'error': 'No files uploaded.'
    })