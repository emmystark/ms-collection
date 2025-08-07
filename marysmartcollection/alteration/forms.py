from django import forms
from .models import AlterationRequest

class AlterationRequestForm(forms.ModelForm):
    class Meta:
        model = AlterationRequest
        fields = ['name', 'email', 'phone', 'pickup_address', 'delivery_address', 'description']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your email address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'pickup_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Pickup address'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Delivery address'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'What needs to be altered?'}),
        }

    def __init__(self, *args, **kwargs):
        super(AlterationRequestForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

