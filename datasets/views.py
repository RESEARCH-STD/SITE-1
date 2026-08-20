from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import DatasetForm
from .models import Category, Dataset


class CatalogListView(ListView):
    model = Dataset
    template_name = "datasets/catalog.html"
    context_object_name = "datasets"
    paginate_by = 12

    def get_queryset(self):
        qs = Dataset.objects.select_related("category", "uploader")
        query = self.request.GET.get("q", "").strip()
        category_slug = self.request.GET.get("category", "").strip()
        sort = self.request.GET.get("sort", "newest")

        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(region__icontains=query)
            )
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        if sort == "downloads":
            qs = qs.order_by("-download_count")
        elif sort == "title":
            qs = qs.order_by("title")
        else:
            qs = qs.order_by("-created_at")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        context["query"] = self.request.GET.get("q", "")
        context["selected_category"] = self.request.GET.get("category", "")
        context["sort"] = self.request.GET.get("sort", "newest")
        return context


class DatasetDetailView(DetailView):
    model = Dataset
    template_name = "datasets/dataset_detail.html"
    context_object_name = "dataset"
    slug_url_kwarg = "slug"


class DatasetUploadView(LoginRequiredMixin, CreateView):
    model = Dataset
    form_class = DatasetForm
    template_name = "datasets/dataset_form.html"

    def form_valid(self, form):
        form.instance.uploader = self.request.user
        return super().form_valid(form)


class OwnerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        dataset = self.get_object()
        return dataset.uploader_id == self.request.user.id


class DatasetUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = Dataset
    form_class = DatasetForm
    template_name = "datasets/dataset_form.html"


class DatasetDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = Dataset
    template_name = "datasets/dataset_confirm_delete.html"
    success_url = reverse_lazy("datasets:my_uploads")


class MyUploadsListView(LoginRequiredMixin, ListView):
    template_name = "datasets/my_uploads.html"
    context_object_name = "datasets"

    def get_queryset(self):
        return Dataset.objects.filter(uploader=self.request.user).select_related("category")


@login_required
def download_dataset(request, slug):
    dataset = get_object_or_404(Dataset, slug=slug)
    if not dataset.file:
        raise Http404("File not available.")
    Dataset.objects.filter(pk=dataset.pk).update(download_count=dataset.download_count + 1)
    return FileResponse(
        dataset.file.open("rb"),
        as_attachment=True,
        filename=dataset.original_filename or dataset.file.name.split("/")[-1],
    )
