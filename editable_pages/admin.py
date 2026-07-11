from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import EditablePage


@admin.register(EditablePage)
class EditablePageAdmin(SimpleHistoryAdmin):
    """Admin configuration for editable pages."""

    list_display = [
        "title",
        "page_type",
        "slug",
        "visibility",
        "is_active",
        "is_featured",
        "display_order",
        "last_modified_by",
        "updated_at",
    ]
    list_filter = [
        "page_type",
        "visibility",
        "is_active",
        "is_featured",
        "created_at",
        "updated_at",
        "last_modified_by",
    ]
    search_fields = ["title", "slug", "content", "meta_description"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["display_order", "page_type", "title"]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("page_type", "title", "slug", "meta_description")},
        ),
        (
            "Content",
            {"fields": ("table_of_contents", "content")},
        ),
        (
            "Organization",
            {"fields": ("parent_page", "display_order")},
        ),
        (
            "Visibility & Status",
            {"fields": ("visibility", "is_active", "is_featured")},
        ),
        (
            "Version Control",
            {"fields": ("version_notes", "last_modified_by")},
        ),
        (
            "Cache Management",
            {
                "fields": ("force_cache_refresh",),
                "description": "Use this to trigger any host-specific invalidation hook on save.",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("parent_page", "last_modified_by")

    def save_model(self, request, obj, form, change):
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)
