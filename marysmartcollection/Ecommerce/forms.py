from django import forms 

class SearchForm(forms.Form):
    query = forms.CharField(max_length=100, required=False)

class CartAddProductForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1, label="Quantity")
    size = forms.ChoiceField(
        choices=[
            ('38', '38'), ('39', '39'), ('40', '40'), ('41', '41'),
            ('42', '42'), ('43', '43'), ('S', 'S'), ('M', 'M'),
            ('X', 'X'), ('XL', 'XL')
        ],
        label="Size",
        required=True
    )
    update = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput)