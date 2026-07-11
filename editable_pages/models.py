from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords
from tinymce.models import HTMLField

from .cache import invalidate_page_caches
from .conf import get_page_type_choices, resolve_page_url


class EditablePage(models.Model):
    """Admin-editable page content with optional hierarchy and API metadata."""

    CONTENT_SOURCES = [
        ("", "Manual (Admin)"),
        ("fixture", "Imported from fixture"),
    ]
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_AUTHENTICATED = "authenticated"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, "Public"),
        (VISIBILITY_AUTHENTICATED, "Authenticated users only"),
    ]

    page_type = models.CharField(
        max_length=50,
        choices=get_page_type_choices,
        help_text="Logical page type used for filtering and host-specific routing.",
    )
    title = models.CharField(max_length=200, help_text="Human-friendly page title.")
    slug = models.SlugField(max_length=200, unique=True, help_text="Stable public slug.")
    table_of_contents = HTMLField(blank=True, help_text="Optional HTML table of contents.")
    content = HTMLField(help_text="Trusted rich HTML content managed by operators.")
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text="Optional SEO summary.",
    )
    display_order = models.IntegerField(default=0, help_text="Lower numbers are displayed first.")
    parent_page = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="child_pages",
        help_text="Optional parent page for hierarchical navigation.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the page is publicly visible.",
    )
    is_featured = models.BooleanField(default=False, help_text="Whether to feature this page.")
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PUBLIC,
        help_text="Who can access this page through the read-only API.",
    )
    content_source = models.CharField(
        max_length=20,
        choices=CONTENT_SOURCES,
        default="",
        blank=True,
        help_text="How this page was created.",
    )
    force_cache_refresh = models.BooleanField(
        default=False,
        help_text="Trigger host-specific cache invalidation hooks on the next save.",
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who last modified this page.",
    )
    version_notes = models.TextField(blank=True, help_text="Optional notes about this revision.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["display_order", "page_type", "title"]
        verbose_name = "Editable Page"
        verbose_name_plural = "Editable Pages"
        indexes = [
            models.Index(fields=["page_type"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["display_order"]),
            models.Index(fields=["parent_page"]),
            models.Index(fields=["is_featured"]),
            models.Index(fields=["visibility"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_page_type_display()} - {self.title}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        force_refresh = self.force_cache_refresh
        update_fields = kwargs.get("update_fields")
        if force_refresh:
            self.force_cache_refresh = False
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"force_cache_refresh"}

        super().save(*args, **kwargs)
        invalidate_page_caches(page_type=self.page_type, force=force_refresh)

    def get_absolute_url(self) -> str:
        return resolve_page_url(self)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        page_type = self.page_type
        result = super().delete(*args, **kwargs)
        invalidate_page_caches(page_type=page_type, force=True)
        return result

    @classmethod
    def get_by_type(
        cls,
        page_type: str,
        active_only: bool = True,
    ) -> models.QuerySet[EditablePage]:
        queryset = cls.objects.filter(page_type=page_type)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by("display_order", "title")

    @classmethod
    def get_featured_pages(cls) -> models.QuerySet[EditablePage]:
        return cls.objects.filter(is_featured=True, is_active=True).order_by(
            "display_order",
            "title",
        )

    @classmethod
    def visible_to(cls, *, is_authenticated: bool) -> models.QuerySet[EditablePage]:
        queryset = cls.objects.filter(is_active=True)
        if not is_authenticated:
            queryset = queryset.filter(visibility=cls.VISIBILITY_PUBLIC)
        return queryset

    @classmethod
    def get_top_level_pages(cls) -> models.QuerySet[EditablePage]:
        return cls.objects.filter(parent_page__isnull=True, is_active=True).order_by(
            "display_order",
            "title",
        )

    def get_children(self) -> models.QuerySet[EditablePage]:
        return self.child_pages.filter(is_active=True).order_by("display_order", "title")

    def has_children(self) -> bool:
        return self.child_pages.filter(is_active=True).exists()

    def get_breadcrumb_trail(self) -> list[EditablePage]:
        trail: list[EditablePage] = []
        current: EditablePage | None = self
        while current is not None:
            trail.insert(0, current)
            current = current.parent_page
        return trail
