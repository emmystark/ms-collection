// Main JavaScript for Alteration Request Page
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all functionality
    initImageUpload();
    initFormValidation();
    initDeliveryOptions();
    initSmoothScrolling();
});

// Image Upload Functionality
function initImageUpload() {
    const uploadZone = document.getElementById('uploadZone');
    const imageUpload = document.getElementById('imageUpload');
    const imagePreviews = document.getElementById('imagePreviews');
    let uploadedFiles = [];

    if (!uploadZone || !imageUpload || !imagePreviews) return;

    // Drag and drop functionality
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    uploadZone.addEventListener('click', () => {
        imageUpload.click();
    });

    imageUpload.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    function handleFiles(files) {
        const fileArray = Array.from(files);
        const validFiles = fileArray.filter(file => 
            file.type.startsWith('image/') && file.size <= 5 * 1024 * 1024
        );

        if (validFiles.length + uploadedFiles.length > 5) {
            alert('Maximum 5 images allowed');
            return;
        }

        validFiles.forEach(file => {
            uploadedFiles.push(file);
            const reader = new FileReader();
            reader.onload = (e) => {
                createImagePreview(e.target.result, uploadedFiles.length - 1);
            };
            reader.readAsDataURL(file);
        });

        // Update the file input with new files
        updateFileInput();
    }

    function createImagePreview(src, index) {
        const previewDiv = document.createElement('div');
        previewDiv.className = 'image-preview';
        previewDiv.innerHTML = `
            <img src="${src}" alt="Preview ${index + 1}">
            <button type="button" class="remove-image" onclick="removeImage(${index})">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;
        imagePreviews.appendChild(previewDiv);
    }

    function updateFileInput() {
        // Create a new DataTransfer object to update the file input
        const dt = new DataTransfer();
        uploadedFiles.forEach(file => dt.items.add(file));
        imageUpload.files = dt.files;
    }

    // Global function for removing images
    window.removeImage = function(index) {
        uploadedFiles.splice(index, 1);
        imagePreviews.innerHTML = '';
        uploadedFiles.forEach((file, i) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                createImagePreview(e.target.result, i);
            };
            reader.readAsDataURL(file);
        });
        updateFileInput();
    };
}

// Form Validation
function initFormValidation() {
    const form = document.getElementById('alterationForm');
    const submitButton = document.getElementById('submitButton');
    const successMessage = document.getElementById('successMessage');

    if (!form) return;

    // Set minimum date to tomorrow
    const preferredDateInput = form.querySelector('input[type="date"]');
    if (preferredDateInput) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        preferredDateInput.min = tomorrow.toISOString().split('T')[0];
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (!validateForm()) {
            return;
        }

        // Show loading state
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="loading"></span> Submitting Request...';
        }

        try {
            const formData = new FormData(form);
            
            // Add alteration types from checkboxes
            const alterationTypes = [];
            const checkedBoxes = form.querySelectorAll('input[name="alteration_types"]:checked');
            checkedBoxes.forEach(checkbox => {
                alterationTypes.push(checkbox.value);
            });
            
            // Remove existing alteration_types entries and add the collected ones
            formData.delete('alteration_types');
            alterationTypes.forEach(type => {
                formData.append('alteration_types', type);
            });
            
            // Add uploaded images to form data
            const imageUpload = document.getElementById('imageUpload');
            if (imageUpload && imageUpload.files) {
                for (let i = 0; i < imageUpload.files.length; i++) {
                    formData.append('garment_images', imageUpload.files[i]);
                }
            }

            // Add issue description
            const issueDescription = document.getElementById('issueDescription');
            if (issueDescription) {
                formData.append('issue_description', issueDescription.value);
            }

            // Debug: Log form data
            console.log('Form data being sent:');
            for (let [key, value] of formData.entries()) {
                console.log(key, value);
            }
            const response = await fetch(form.action || window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });

            const result = await response.json();

            if (result.success) {
                // Show success message
                if (successMessage) {
                    successMessage.classList.add('show');
                }
                
                // Reset form
                form.reset();
                document.getElementById('imagePreviews').innerHTML = '';
                if (issueDescription) issueDescription.value = '';
                
                // Hide success message after 5 seconds
                setTimeout(() => {
                    if (successMessage) {
                        successMessage.classList.remove('show');
                    }
                }, 5000);
                
                // Scroll to top of form
                document.getElementById('form-section').scrollIntoView({ behavior: 'smooth' });
            } else {
                console.log('Form submission failed:', result);
                // Handle validation errors
                if (result.errors) {
                    displayFormErrors(result.errors);
                } else {
                    alert(result.message || 'There was an error submitting your request. Please try again.');
                }
            }
            
        } catch (error) {
            console.error('Error submitting form:', error);
            alert('There was an error submitting your request. Please try again.');
        } finally {
            // Reset button state
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.innerHTML = 'Submit Alteration Request';
            }
        }
    });

    function validateForm() {
        let isValid = true;
        
        // Clear previous errors
        document.querySelectorAll('.form-group').forEach(group => {
            group.classList.remove('error');
        });
        document.querySelectorAll('.error-message').forEach(error => {
            error.textContent = '';
        });

        // Validate required fields
        const requiredFields = [
            { name: 'name', message: 'Name is required' },
            { name: 'email', message: 'Email is required' },
            { name: 'phone', message: 'Phone number is required' },
            { name: 'garment_type', message: 'Please select a garment type' },
            { name: 'preferred_date', message: 'Please select a preferred date' }
        ];

        requiredFields.forEach(field => {
            const element = form.querySelector(`[name="${field.name}"]`);
            if (element) {
                const value = element.value.trim();
                
                if (!value) {
                    showError(element, field.message);
                    isValid = false;
                }
            }
        });

        // Validate email format
        const emailField = form.querySelector('[name="email"]');
        if (emailField) {
            const email = emailField.value.trim();
            if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showError(emailField, 'Please enter a valid email address');
                isValid = false;
            }
        }

        // Validate alteration type (at least one checkbox must be checked)
        const alterationTypes = form.querySelectorAll('input[name="alteration_types"]:checked');
        if (alterationTypes.length === 0) {
            const alterationGroup = form.querySelector('.checkbox-group').closest('.form-group');
            if (alterationGroup) {
                alterationGroup.classList.add('error');
                const errorElement = alterationGroup.querySelector('.error-message');
                if (errorElement) {
                    errorElement.textContent = 'Please select at least one alteration type';
                }
            }
            isValid = false;
        }

        return isValid;
    }

    function showError(field, message) {
        const formGroup = field.closest('.form-group');
        if (formGroup) {
            formGroup.classList.add('error');
            const errorElement = formGroup.querySelector('.error-message');
            if (errorElement) {
                errorElement.textContent = message;
            }
        }
    }

    function displayFormErrors(errors) {
        Object.keys(errors).forEach(fieldName => {
            const field = form.querySelector(`[name="${fieldName}"]`);
            if (field) {
                showError(field, errors[fieldName]);
            }
        });
    }

    // Real-time validation
    form.querySelectorAll('input, select, textarea').forEach(element => {
        element.addEventListener('blur', () => {
            const formGroup = element.closest('.form-group');
            if (formGroup && formGroup.classList.contains('error')) {
                const value = element.value.trim();
                if (value) {
                    formGroup.classList.remove('error');
                    const errorElement = formGroup.querySelector('.error-message');
                    if (errorElement) {
                        errorElement.textContent = '';
                    }
                }
            }
        });
    });
}

// Delivery Options
function initDeliveryOptions() {
    const deliveryRadios = document.querySelectorAll('input[name="delivery_option"]');
    const pickupAddress = document.querySelector('.pickup-address');
    const deliveryAddress = document.querySelector('.delivery-address');

    if (!deliveryRadios.length) return;

    deliveryRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (pickupAddress) {
                pickupAddress.style.display = this.value === 'pickup' ? 'block' : 'none';
            }
            if (deliveryAddress) {
                deliveryAddress.style.display = this.value === 'delivery' ? 'block' : 'none';
            }
        });
    });

    // Initialize on page load
    const checkedRadio = document.querySelector('input[name="delivery_option"]:checked');
    if (checkedRadio) {
        checkedRadio.dispatchEvent(new Event('change'));
    }
}

// Smooth Scrolling
function initSmoothScrolling() {
    const ctaButton = document.querySelector('.cta-button');
    if (ctaButton) {
        ctaButton.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(ctaButton.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ 
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    }
}

// Utility function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}