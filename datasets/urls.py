from django.urls import path

from . import views

app_name = "datasets"

urlpatterns = [
    path("", views.CatalogListView.as_view(), name="catalog"),
    path("upload/", views.DatasetUploadView.as_view(), name="upload"),
    path("my-uploads/", views.MyUploadsListView.as_view(), name="my_uploads"),
    path("<slug:slug>/", views.DatasetDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.DatasetUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.DatasetDeleteView.as_view(), name="delete"),
    path("<slug:slug>/download/", views.download_dataset, name="download"),
]
