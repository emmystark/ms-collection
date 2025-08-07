from django.shortcuts import render, redirect
from .forms import AlterationRequestForm

def alteration_request(request):
    if request.method == 'POST':
        form = AlterationRequestForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('success_page')  # update this with your actual success URL name
    else:
        form = AlterationRequestForm()
    
    return render(request, 'alteration/alteration_form.html', {'form': form})
