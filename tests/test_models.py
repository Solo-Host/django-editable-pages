from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings

from editable_pages.models import EditablePage
from tests.helpers import HOOK_CALLS, reset_hook_calls

User = get_user_model()


@pytest.mark.django_db
def test_str_method_uses_page_type_display() -> None:
    page = EditablePage.objects.create(
        page_type="documentation",
        title="Test Page",
        slug="test-page",
        content="<p>Content</p>",
    )
    assert str(page) == "Documentation - Test Page"


@pytest.mark.django_db
def test_get_absolute_url_uses_default_mapping() -> None:
    page = EditablePage.objects.create(
        page_type="privacy_policy",
        title="Privacy Policy",
        slug="privacy-policy",
        content="<p>Content</p>",
    )
    assert page.get_absolute_url() == "/privacy-policy"


@pytest.mark.django_db
@override_settings(EDITABLE_PAGES_URL_RESOLVER="tests.helpers.custom_url_resolver")
def test_get_absolute_url_uses_optional_resolver_hook() -> None:
    page = EditablePage.objects.create(
        page_type="custom",
        title="Custom Page",
        slug="custom-page",
        content="<p>Content</p>",
    )
    assert page.get_absolute_url() == "/pages/custom-page/"


@pytest.mark.django_db
def test_force_cache_refresh_flag_resets_after_save() -> None:
    page = EditablePage.objects.create(
        page_type="documentation",
        title="Page",
        slug="page",
        content="<p>Content</p>",
    )
    page.force_cache_refresh = True
    page.save()
    page.refresh_from_db()
    assert page.force_cache_refresh is False


@pytest.mark.django_db
@override_settings(EDITABLE_PAGES_CACHE_INVALIDATOR="tests.helpers.record_cache_invalidator")
def test_optional_cache_invalidator_receives_force_flag() -> None:
    reset_hook_calls()
    page = EditablePage.objects.create(
        page_type="documentation",
        title="Page",
        slug="page",
        content="<p>Content</p>",
    )
    assert HOOK_CALLS[-1] == ("documentation", False)

    page.force_cache_refresh = True
    page.save()
    assert HOOK_CALLS[-1] == ("documentation", True)


@pytest.mark.django_db
def test_save_bumps_cache_versions() -> None:
    cache.clear()
    page = EditablePage.objects.create(
        page_type="faq",
        title="FAQ",
        slug="faq",
        content="<p>Content</p>",
    )
    content_version = cache.get("editable_pages:version:content_pages")
    faq_version = cache.get("editable_pages:version:faqs")
    assert content_version == 2
    assert faq_version == 2

    page.title = "Updated FAQ"
    page.save()
    assert cache.get("editable_pages:version:content_pages") == 3
    assert cache.get("editable_pages:version:faqs") == 3


@pytest.mark.django_db
def test_breadcrumb_trail_and_children_helpers() -> None:
    parent = EditablePage.objects.create(
        page_type="documentation",
        title="Parent",
        slug="parent",
        content="<p>Parent</p>",
    )
    child = EditablePage.objects.create(
        page_type="documentation",
        title="Child",
        slug="child",
        content="<p>Child</p>",
        parent_page=parent,
    )

    assert parent.has_children() is True
    assert list(parent.get_children()) == [child]
    assert child.get_breadcrumb_trail() == [parent, child]


@pytest.mark.django_db
def test_get_by_type_filters_to_active_pages_by_default() -> None:
    active = EditablePage.objects.create(
        page_type="faq",
        title="Active FAQ",
        slug="active-faq",
        content="<p>Active</p>",
        is_active=True,
    )
    EditablePage.objects.create(
        page_type="faq",
        title="Inactive FAQ",
        slug="inactive-faq",
        content="<p>Inactive</p>",
        is_active=False,
    )

    assert list(EditablePage.get_by_type("faq")) == [active]
