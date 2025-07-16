from django import forms
PRODUCT_QUANTITY_CHOICES = [(i, str(i)) for i in range(1, 21)]


class CartAddProductForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, initial=1, label="Quantity")
    size = forms.ChoiceField(label="Size", required=True)
    update = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        if product and product.sizes:
            self.fields['size'].choices = [(size, size) for size in product.sizes]
        else:
            self.fields['size'].choices = [
                 ('S', 'S'), ('M', 'M'),
                ('X', 'X'), ('XL', 'XL')
            ]