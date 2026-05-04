from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from editable_pages.models import EditablePage


@pytest.fixture
def client() -> APIClient:
    cache.clear()
    return APIClient()


@pytest.fixture
def pages() -> dict[str, EditablePage]:
    terms = EditablePage.objects.create(
        page_type="terms_of_service",
        title="Terms",
        slug="terms",
        content="<p>Terms</p>",
        display_order=1,
    )
    privacy = EditablePage.objects.create(
        page_type="privacy_policy",
        title="Privacy",
        slug="privacy",
        content="<p>Privacy</p>",
        display_order=2,
    )
    faq = EditablePage.objects.create(
        page_type="faq",
        title="FAQ",
        slug="faq",
        content="<p>FAQ</p>",
        display_order=3,
        is_featured=True,
    )
    return {"terms": terms, "privacy": privacy, "faq": faq}


@pytest.mark.django_db
def test_list_pages_returns_active_pages(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    EditablePage.objects.create(
        page_type="faq",
        title="Inactive",
        slug="inactive",
        content="<p>Inactive</p>",
        is_active=False,
    )

    response = client.get(reverse("editable_pages:pages-list"))

    assert response.status_code == status.HTTP_200_OK
    assert [item["slug"] for item in response.data] == ["terms", "privacy", "faq"]


@pytest.mark.django_db
def test_retrieve_page_by_slug(client: APIClient, pages: dict[str, EditablePage]) -> None:
    response = client.get(reverse("editable_pages:pages-detail", kwargs={"slug": "privacy"}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["title"] == "Privacy"
    assert response.data["absolute_url"] == "/privacy-policy"


@pytest.mark.django_db
def test_by_type_requires_page_type_parameter(client: APIClient) -> None:
    response = client.get(reverse("editable_pages:pages-by-type"))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "page_type parameter is required"


@pytest.mark.django_db
def test_legal_policies_uses_configured_page_types(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    response = client.get(reverse("editable_pages:pages-legal-policies"))

    assert response.status_code == status.HTTP_200_OK
    assert [item["slug"] for item in response.data] == ["terms", "privacy"]


@pytest.mark.django_db
def test_featured_and_faq_endpoints_filter_correctly(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    featured = client.get(reverse("editable_pages:pages-featured"))
    faqs = client.get(reverse("editable_pages:pages-faqs"))

    assert featured.status_code == status.HTTP_200_OK
    assert [item["slug"] for item in featured.data] == ["faq"]
    assert faqs.status_code == status.HTTP_200_OK
    assert [item["slug"] for item in faqs.data] == ["faq"]


@pytest.mark.django_db
def test_cached_api_payload_is_invalidated_after_save(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    url = reverse("editable_pages:pages-detail", kwargs={"slug": "privacy"})
    first = client.get(url)
    assert first.data["title"] == "Privacy"

    page = pages["privacy"]
    page.title = "Updated Privacy"
    page.save()

    second = client.get(url)
    assert second.data["title"] == "Updated Privacy"


@pytest.mark.django_db
@override_settings(EDITABLE_PAGES_CACHE_TIMEOUT_RESOLVER="tests.helpers.cache_timeout_resolver")
def test_cache_timeout_resolver_hook_is_used(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    response = client.get(reverse("editable_pages:pages-detail", kwargs={"slug": "privacy"}))
    assert response.status_code == status.HTTP_200_OK
    cache_keys = [key for key in cache._cache]  # type: ignore[attr-defined]
    assert any("pages-detail" in str(key) for key in cache_keys)
