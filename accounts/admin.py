from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("DataBridge profile", {"fields": ("institution",)}),
    )
    list_display = ("username", "email", "institution", "is_staff")
