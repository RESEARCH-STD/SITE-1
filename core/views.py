from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import ContactForm
from .models import DataCustodian, Insight, Partner, Project, SiteStat


def home(request):
    context = {
        "stats": SiteStat.objects.all(),
        "featured_projects": Project.objects.all()[:4],
        "insights": Insight.objects.all()[:6],
        "partners": Partner.objects.all(),
    }
    return render(request, "core/home.html", context)


def about(request):
    return render(request, "core/about.html")


def services(request):
    return render(request, "core/services.html")


def products(request):
    return render(request, "core/products.html")


def projects(request):
    return render(request, "core/projects.html", {"projects": Project.objects.all()})


def insights(request):
    category = request.GET.get("cat", "")
    items = Insight.objects.all()
    if category:
        items = items.filter(category=category)
    return render(
        request,
        "core/insights.html",
        {
            "insights": items,
            "categories": Insight.CATEGORY_CHOICES,
            "selected_category": category,
        },
    )


def partners(request):
    return render(request, "core/partners.html", {"partners": Partner.objects.all()})


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
