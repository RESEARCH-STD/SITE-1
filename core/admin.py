from django.contrib import admin

from .models import ContactMessage, DataCustodian


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "created_at")
    readonly_fields = ("name", "email", "message", "created_at")


@admin.register(DataCustodian)
class DataCustodianAdmin(admin.ModelAdmin):
    list_display = ("name", "url")
