from django.contrib import admin

from .models import Category, Dataset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "uploader", "region", "year", "download_count", "created_at")
    list_filter = ("category",)
    search_fields = ("title", "description", "region")
    readonly_fields = ("original_filename", "file_size", "download_count", "created_at")
