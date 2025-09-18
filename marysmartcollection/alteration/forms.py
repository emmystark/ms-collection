from django import forms
from .models import AlterationRequest, AlterationImage
from django.forms import modelformset_factory

class AlterationRequestForm(forms.ModelForm):
    class Meta:
        model = AlterationRequest
        fields = [
            'name',
            'email',
            'phone',
            'garment_type',
            'alteration_type',
            'measurements',
            'description',
            'delivery_option',
            'pickup_address',
            'delivery_address',
            'preferred_date',
            'issue_description',
        ]
        widgets = {
            'preferred_date': forms.DateInput(attrs={'type': 'date'}),
        }


class AlterationImageForm(forms.ModelForm):
    class Meta:
        model = AlterationImage
        fields = ['image', 'description']


AlterationImageFormSet = modelformset_factory(
    AlterationImage,
    form=AlterationImageForm,
    extra=3,  # allows up to 3 images by default
    can_delete=True
)
