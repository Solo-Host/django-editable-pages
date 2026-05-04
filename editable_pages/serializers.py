from rest_framework import serializers

from .models import EditablePage


class EditablePageSerializer(serializers.ModelSerializer):
    """Full serializer including admin-oriented metadata."""

    page_type_display = serializers.CharField(source="get_page_type_display", read_only=True)
    absolute_url = serializers.CharField(source="get_absolute_url", read_only=True)
    last_modified_by_username = serializers.CharField(
        source="last_modified_by.username",
        read_only=True,
    )

    class Meta:
        model = EditablePage
        fields = [
            "id",
            "page_type",
            "page_type_display",
            "title",
            "slug",
            "table_of_contents",
            "content",
            "meta_description",
            "display_order",
            "is_active",
            "is_featured",
            "last_modified_by_username",
            "version_notes",
            "created_at",
            "updated_at",
            "absolute_url",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "page_type_display",
            "absolute_url",
            "last_modified_by_username",
        ]


class EditablePageListSerializer(serializers.ModelSerializer):
    """List serializer for public page indexes."""

    page_type_display = serializers.CharField(source="get_page_type_display", read_only=True)
    absolute_url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = EditablePage
        fields = [
            "id",
            "page_type",
            "page_type_display",
            "title",
            "slug",
            "meta_description",
            "display_order",
            "is_active",
            "is_featured",
            "updated_at",
            "absolute_url",
        ]
        read_only_fields = ["id", "updated_at", "page_type_display", "absolute_url"]


class EditablePagePublicSerializer(serializers.ModelSerializer):
    """Public serializer for page detail endpoints."""

    page_type_display = serializers.CharField(source="get_page_type_display", read_only=True)
    absolute_url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = EditablePage
        fields = [
            "id",
            "page_type",
            "page_type_display",
            "title",
            "slug",
            "table_of_contents",
            "content",
            "meta_description",
            "updated_at",
            "absolute_url",
        ]
        read_only_fields = fields
