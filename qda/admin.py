"""
Admin for TakwimuBridge QDA: see every researcher's projects, transcripts,
themes and coded references.

Project content is read-only here. It's written by the researchers'
browsers (qda/api.py), and editing single rows behind their backs would
break the project documents they sync. What admins can do:

  * Move to trash / Restore from trash. The change reaches the researcher's
    browsers the next time they open the tool.
  * Download backup (JSON): the same file as the app's "Full Project Backup",
    which anyone can restore in the tool with Projects → Restore from backup
    (e.g. to hand a trainee's project to their supervisor).
  * Delete for good (the normal delete action).

Deactivating a researcher is done on their user account (Active box).
"""

import io
import json
import re
import zipfile

from django.contrib import admin, messages
from django.db.models import Count, IntegerField, OuterRef, Subquery
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .models import Analysis, Coding, Project, Source, Theme
from .sync import project_document

DEMO_PROJECT_ID = "proj-demo-community-perceptions"


def _count(model, field="project"):
    return Subquery(
        model.objects.filter(**{field: OuterRef("pk")})
        .order_by()
        .values(field)
        .annotate(n=Count("pk"))
        .values("n"),
        output_field=IntegerField(),
    )


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "project").lower()).strip("-")[:60] or "project"


class ReadOnlyMixin:
    """Content rows: viewable, not editable."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DemoFilter(admin.SimpleListFilter):
    title = "demo project"
    parameter_name = "demo"

    def lookups(self, request, model_admin):
        return [("no", "Researchers' own projects"), ("yes", "Copies of the demo")]

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.exclude(client_id=DEMO_PROJECT_ID)
        if self.value() == "yes":
            return queryset.filter(client_id=DEMO_PROJECT_ID)
        return queryset


class AnalysisInline(ReadOnlyMixin, admin.TabularInline):
    model = Analysis
    fields = ("name", "question")
    readonly_fields = fields
    extra = 0


class SourceInline(ReadOnlyMixin, admin.TabularInline):
    model = Source
    fields = ("name", "source_type", "respondent_id", "word_count")
    readonly_fields = fields
    extra = 0
    show_change_link = True


class ThemeInline(ReadOnlyMixin, admin.TabularInline):
    model = Theme
    fields = ("name", "parent", "analysis", "color_swatch", "references")
    readonly_fields = fields
    extra = 0
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("parent", "analysis").annotate(_refs=Count("codings"))

    @admin.display(description="colour")
    def color_swatch(self, obj):
        return _swatch(obj.color)

    @admin.display(description="coded references (directly)")
    def references(self, obj):
        return obj._refs


def _swatch(color):
    if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", color or ""):
        return color or "—"
    return format_html(
        '<span style="display:inline-block;width:1em;height:1em;border-radius:3px;vertical-align:middle;background:{}"></span> {}',
        color,
        color,
    )


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_link", "sources_n", "codings_n", "themes_n", "updated_at", "status")
    list_filter = ("deleted", DemoFilter, "updated_at")
    search_fields = ("title", "researcher", "organization", "owner__username", "owner__email")
    list_select_related = ("owner",)
    actions = ["download_backup", "move_to_trash", "restore_from_trash"]
    inlines = [AnalysisInline, SourceInline, ThemeInline]
    fieldsets = (
        (None, {"fields": ("title", "owner_link", "researcher", "organization", "topic", "status", "coded_references")}),
        (
            "Sync details",
            {
                "classes": ("collapse",),
                "fields": ("client_id", "revision", "created_at", "updated_at", "deleted_at", "data"),
            },
        ),
    )
    readonly_fields = (
        "title", "owner_link", "researcher", "organization", "topic", "status", "coded_references",
        "client_id", "revision", "created_at", "updated_at", "deleted_at", "data",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_sources=_count(Source), _codings=_count(Coding), _themes=_count(Theme))
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Viewing only (the actions below are the ways to change a project).
        return False

    def get_deleted_objects(self, objs, request):
        # A project's analyses, sources, themes and coded references can't be
        # deleted one by one, but deleting the project removes them with it.
        deleted, counts, perms_needed, protected = super().get_deleted_objects(objs, request)
        content = {m._meta.verbose_name for m in (Analysis, Source, Theme, Coding)}
        return deleted, counts, perms_needed - content, protected

    @admin.display(description="researcher account", ordering="owner__username")
    def owner_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.owner_id])
        return format_html('<a href="{}">{}</a>', url, obj.owner.get_username())

    @admin.display(description="sources", ordering="_sources")
    def sources_n(self, obj):
        return obj._sources or 0

    @admin.display(description="coded refs", ordering="_codings")
    def codings_n(self, obj):
        return obj._codings or 0

    @admin.display(description="themes", ordering="_themes")
    def themes_n(self, obj):
        return obj._themes or 0

    @admin.display(description="status", ordering="deleted")
    def status(self, obj):
        return "In trash" if obj.deleted else "Active"

    @admin.display(description="coded references")
    def coded_references(self, obj):
        url = reverse("admin:qda_coding_changelist") + f"?project__id__exact={obj.pk}"
        return format_html('<a href="{}">See all {} coded references</a>', url, obj._codings or 0)

    @admin.action(description="Download backup (JSON) — restorable in the tool")
    def download_backup(self, request, queryset):
        projects = list(queryset.select_related("owner"))
        if len(projects) == 1:
            p = projects[0]
            response = HttpResponse(
                json.dumps(project_document(p), ensure_ascii=False, indent=2), content_type="application/json"
            )
            response["Content-Disposition"] = f'attachment; filename="{_slug(p.title)}-project-backup.json"'
            return response
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for p in projects:
                name = f"{_slug(p.owner.get_username())}/{_slug(p.title)}-{p.pk}-project-backup.json"
                archive.writestr(name, json.dumps(project_document(p), ensure_ascii=False, indent=2))
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        stamp = timezone.now().strftime("%Y-%m-%d")
        response["Content-Disposition"] = f'attachment; filename="takwimubridge-qda-backups-{stamp}.zip"'
        return response

    @admin.action(description="Move to trash (hidden from the researcher, kept here)")
    def move_to_trash(self, request, queryset):
        n = self._set_deleted(queryset.filter(deleted=False), True)
        self.message_user(request, f"Moved {n} project(s) to the trash.", messages.SUCCESS)

    @admin.action(description="Restore from trash")
    def restore_from_trash(self, request, queryset):
        n = self._set_deleted(queryset.filter(deleted=True), False)
        self.message_user(request, f"Restored {n} project(s). They reappear the next time the researcher opens the tool.", messages.SUCCESS)

    def _set_deleted(self, queryset, deleted):
        n = 0
        for project in queryset:
            project.deleted = deleted
            project.deleted_at = timezone.now() if deleted else None
            project.revision += 1
            project.last_writer = "admin"
            project.last_write_base = None
            project.save(update_fields=["deleted", "deleted_at", "revision", "last_writer", "last_write_base", "updated_at"])
            n += 1
        return n


@admin.register(Source)
class SourceAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("name", "source_type", "respondent_id", "word_count", "project", "owner")
    list_filter = ("source_type",)
    search_fields = ("name", "respondent_id", "text", "project__title", "project__owner__username", "project__owner__email")
    list_select_related = ("project__owner",)
    fields = ("name", "source_type", "respondent_id", "project", "word_count", "attributes", "text")
    readonly_fields = fields

    @admin.display(description="researcher", ordering="project__owner__username")
    def owner(self, obj):
        return obj.project.owner.get_username()

    @admin.display(description="details")
    def attributes(self, obj):
        attrs = obj.data.get("attributes") if isinstance(obj.data.get("attributes"), dict) else {}
        rows = [(k, ", ".join(map(str, v)) if isinstance(v, list) else json.dumps(v) if isinstance(v, dict) else v)
                for k, v in attrs.items() if v not in ("", None, [], {})]
        if not rows:
            return "—"
        return format_html_join("", "<div><strong>{}</strong>: {}</div>", rows)


@admin.register(Theme)
class ThemeAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("theme_path", "analysis_name", "colour", "references", "project", "owner")
    search_fields = ("name", "project__title", "project__owner__username", "project__owner__email")
    list_select_related = ("project__owner", "parent__parent", "analysis")
    fields = ("name", "theme_path", "analysis_name", "colour", "project", "references")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_refs=Count("codings"))

    @admin.display(description="theme")
    def theme_path(self, obj):
        return obj.path()

    @admin.display(description="analysis")
    def analysis_name(self, obj):
        top = obj.top_level()
        return top.analysis.name if top.analysis_id else "—"

    @admin.display(description="colour")
    def colour(self, obj):
        return _swatch(obj.color)

    @admin.display(description="coded references (directly)", ordering="_refs")
    def references(self, obj):
        url = reverse("admin:qda_coding_changelist") + f"?themes__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj._refs)

    @admin.display(description="researcher", ordering="project__owner__username")
    def owner(self, obj):
        return obj.project.owner.get_username()


@admin.register(Coding)
class CodingAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("excerpt", "theme_list", "weight", "source", "project", "owner")
    search_fields = ("quote", "source__name", "project__title", "project__owner__username", "project__owner__email")
    list_filter = ("weight",)
    list_select_related = ("source", "project__owner")
    fields = ("quote", "theme_list", "weight", "source", "speaker_id", "start", "end", "project")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("themes")

    @admin.display(description="coded passage")
    def excerpt(self, obj):
        return str(obj)

    @admin.display(description="themes")
    def theme_list(self, obj):
        return ", ".join(t.name for t in obj.themes.all()) or "—"

    @admin.display(description="researcher", ordering="project__owner__username")
    def owner(self, obj):
        return obj.project.owner.get_username()
