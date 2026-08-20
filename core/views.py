from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import ContactForm
from .models import DataCustodian


def home(request):
    return render(request, "core/home.html")


def about(request):
    return render(request, "core/about.html")


def services(request):
    return render(request, "core/services.html")


def guidelines(request):
    return render(request, "core/guidelines.html")


def data_custodians(request):
    custodians = DataCustodian.objects.all()
    return render(request, "core/data_custodians.html", {"custodians": custodians})


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thanks! Your message has been sent.")
            return redirect(reverse("core:contact"))
    else:
        form = ContactForm()
    return render(request, "core/contact.html", {"form": form})
