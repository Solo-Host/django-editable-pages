from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .cache import get_cached_payload, set_cached_payload
from .conf import get_legal_page_types
from .models import EditablePage
from .serializers import EditablePageListSerializer, EditablePagePublicSerializer


class EditablePageViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only API for active editable pages."""

    queryset = EditablePage.objects.filter(is_active=True).select_related(
        "last_modified_by",
        "parent_page",
    )
    permission_classes = [permissions.AllowAny]
    serializer_class = EditablePagePublicSerializer
    lookup_field = "slug"

    def get_serializer_class(
        self,
    ) -> type[EditablePageListSerializer] | type[EditablePagePublicSerializer]:
        if self.action in {"list", "featured"}:
            return EditablePageListSerializer
        return EditablePagePublicSerializer

    def _payload_response(
        self,
        request: Request,
        *,
        scope: str,
        version_scope: str,
        timeout_scope: str,
        builder: Callable[[], Any],
    ) -> Response:
        request_path = request.get_full_path()
        cached = get_cached_payload(scope, request_path, version_scope=version_scope)
        if cached is not None:
            return Response(cached)

        payload = builder()
        set_cached_payload(
            scope,
            request_path,
            payload,
            version_scope=version_scope,
            timeout_scope=timeout_scope,
        )
        return Response(payload)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        def build_payload() -> Any:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data).data
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        return self._payload_response(
            request,
            scope="pages-list",
            version_scope="content_pages",
            timeout_scope="content_pages",
            builder=build_payload,
        )

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        def build_payload() -> Any:
            serializer = self.get_serializer(self.get_object())
            return serializer.data

        return self._payload_response(
            request,
            scope="pages-detail",
            version_scope="content_pages",
            timeout_scope="content_pages",
            builder=build_payload,
        )

    @action(detail=False, methods=["get"])
    def by_type(self, request: Request) -> Response:
        page_type = request.query_params.get("page_type")
        if not page_type:
            return Response(
                {"error": "page_type parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def build_payload() -> Any:
            queryset = self.get_queryset().filter(page_type=page_type)
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        return self._payload_response(
            request,
            scope="pages-by-type",
            version_scope="content_pages",
            timeout_scope="content_pages",
            builder=build_payload,
        )

    @action(detail=False, methods=["get"])
    def legal_policies(self, request: Request) -> Response:
        def build_payload() -> Any:
            queryset = self.get_queryset().filter(page_type__in=get_legal_page_types())
            serializer = self.get_serializer(
                queryset.order_by("display_order", "page_type"),
                many=True,
            )
            return serializer.data

        return self._payload_response(
            request,
            scope="pages-legal-policies",
            version_scope="content_pages",
            timeout_scope="content_pages",
            builder=build_payload,
        )

    @action(detail=False, methods=["get"])
    def featured(self, request: Request) -> Response:
        def build_payload() -> Any:
            queryset = self.get_queryset().filter(is_featured=True).order_by(
                "display_order",
                "title",
            )
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        return self._payload_response(
            request,
            scope="pages-featured",
            version_scope="content_pages",
            timeout_scope="content_pages",
            builder=build_payload,
        )

    @action(detail=False, methods=["get"])
    def faqs(self, request: Request) -> Response:
        def build_payload() -> Any:
            queryset = self.get_queryset().filter(page_type="faq").order_by(
                "display_order",
                "title",
            )
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        return self._payload_response(
            request,
            scope="pages-faqs",
            version_scope="faqs",
            timeout_scope="faqs",
            builder=build_payload,
        )
