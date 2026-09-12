from django.contrib import admin

from .models import ContactMessage, DataCustodian, Insight, Partner, Project, SiteStat


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "created_at")
    readonly_fields = ("name", "email", "message", "created_at")


@admin.register(DataCustodian)
class DataCustodianAdmin(admin.ModelAdmin):
    list_display = ("name", "url")


@admin.register(SiteStat)
class SiteStatAdmin(admin.ModelAdmin):
    list_display = ("label", "value", "order")
    list_editable = ("value", "order")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "date_range", "order")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "order")


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published_at")
    list_filter = ("category",)
