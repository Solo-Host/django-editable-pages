from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from editable_pages.admin import EditablePageAdmin
from editable_pages.models import EditablePage

User = get_user_model()


@pytest.mark.django_db
def test_admin_save_model_updates_last_modified_by_on_each_save() -> None:
    site = AdminSite()
    admin = EditablePageAdmin(EditablePage, site)
    factory = RequestFactory()

    first_user = User.objects.create_user(username="first", password="secret")
    second_user = User.objects.create_user(username="second", password="secret")
    page = EditablePage.objects.create(
        page_type="documentation",
        title="Page",
        slug="page",
        content="<p>Content</p>",
    )

    first_request = factory.post("/admin/editable-pages/")
    first_request.user = first_user
    admin.save_model(first_request, page, form=None, change=True)
    page.refresh_from_db()
    assert page.last_modified_by == first_user

    second_request = factory.post("/admin/editable-pages/")
    second_request.user = second_user
    admin.save_model(second_request, page, form=None, change=True)
    page.refresh_from_db()
    assert page.last_modified_by == second_user
