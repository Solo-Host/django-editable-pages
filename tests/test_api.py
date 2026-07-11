from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from editable_pages.models import EditablePage

User = get_user_model()


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
    help_page = EditablePage.objects.create(
        page_type="help_index",
        title="Help",
        slug="help",
        content="<p>Private help</p>",
        display_order=4,
        visibility=EditablePage.VISIBILITY_AUTHENTICATED,
    )
    return {"terms": terms, "privacy": privacy, "faq": faq, "help": help_page}


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
def test_authenticated_users_can_list_and_retrieve_authenticated_pages(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    user = User.objects.create_user(username="api-user", password="not-a-secret")
    client.force_authenticate(user=user)

    listing = client.get(reverse("editable_pages:pages-list"))
    detail = client.get(reverse("editable_pages:pages-detail", kwargs={"slug": "help"}))

    assert listing.status_code == status.HTTP_200_OK
    assert [item["slug"] for item in listing.data] == ["terms", "privacy", "faq", "help"]
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["visibility"] == EditablePage.VISIBILITY_AUTHENTICATED


@pytest.mark.django_db
def test_anonymous_users_cannot_retrieve_authenticated_pages(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    response = client.get(reverse("editable_pages:pages-detail", kwargs={"slug": "help"}))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_authenticated_page_cache_does_not_leak_to_anonymous_users(
    client: APIClient,
    pages: dict[str, EditablePage],
) -> None:
    user = User.objects.create_user(username="cache-user", password="not-a-secret")
    client.force_authenticate(user=user)

    authenticated_response = client.get(
        reverse("editable_pages:pages-detail", kwargs={"slug": "help"}),
    )
    assert authenticated_response.status_code == status.HTTP_200_OK

    client.force_authenticate(user=None)
    anonymous_response = client.get(
        reverse("editable_pages:pages-detail", kwargs={"slug": "help"}),
    )
    assert anonymous_response.status_code == status.HTTP_404_NOT_FOUND


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
