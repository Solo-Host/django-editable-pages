from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from editable_pages.models import EditablePage


def _make_fixture(pages: list[dict[str, object]], path: Path | None = None) -> Path:
    entries = [{"model": EditablePage._meta.label_lower, "fields": page} for page in pages]
    if path is None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp:
            path = Path(temp.name)
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def _minimal_page(**overrides: object) -> dict[str, object]:
    page = {
        "page_type": "faq",
        "title": "Test FAQ",
        "slug": "test-faq",
        "content": "<p>Test content</p>",
        "table_of_contents": "",
        "meta_description": "",
        "display_order": 0,
        "parent_page_slug": None,
        "is_active": True,
        "is_featured": False,
        "version_notes": "",
    }
    page.update(overrides)
    return page


@pytest.mark.django_db
def test_import_creates_fixture_managed_pages() -> None:
    fixture = _make_fixture(
        [_minimal_page(), _minimal_page(slug="docs", page_type="documentation")],
    )
    out = StringIO()

    call_command("manage_editable_pages", "import", "--source", str(fixture), stdout=out)

    assert EditablePage.objects.count() == 2
    assert EditablePage.objects.get(slug="test-faq").content_source == "fixture"
    assert "2 created" in out.getvalue()


@pytest.mark.django_db
def test_import_updates_existing_page_by_slug() -> None:
    fixture_v1 = _make_fixture([_minimal_page(content="<p>Old</p>")])
    call_command("manage_editable_pages", "import", "--source", str(fixture_v1), stdout=StringIO())

    fixture_v2 = _make_fixture([_minimal_page(content="<p>New</p>", page_type="documentation")])
    out = StringIO()
    call_command("manage_editable_pages", "import", "--source", str(fixture_v2), stdout=out)

    page = EditablePage.objects.get(slug="test-faq")
    assert page.content == "<p>New</p>"
    assert page.page_type == "documentation"
    assert "1 updated" in out.getvalue()


@pytest.mark.django_db
def test_import_supports_parent_page_slug() -> None:
    fixture = _make_fixture(
        [
            _minimal_page(slug="parent", page_type="documentation"),
            _minimal_page(
                slug="child",
                page_type="documentation",
                parent_page_slug="parent",
            ),
        ],
    )
    call_command("manage_editable_pages", "import", "--source", str(fixture), stdout=StringIO())

    child = EditablePage.objects.get(slug="child")
    assert child.parent_page is not None
    assert child.parent_page.slug == "parent"


@pytest.mark.django_db
def test_import_dry_run_does_not_write_changes() -> None:
    fixture = _make_fixture([_minimal_page()])
    out = StringIO()

    call_command(
        "manage_editable_pages",
        "import",
        "--source",
        str(fixture),
        "--dry-run",
        stdout=out,
    )

    assert EditablePage.objects.count() == 0
    assert "DRY RUN" in out.getvalue()


@pytest.mark.django_db
def test_import_rejects_missing_source_file() -> None:
    with pytest.raises(CommandError):
        call_command(
            "manage_editable_pages",
            "import",
            "--source",
            "/tmp/does-not-exist-editable-pages.json",
            stdout=StringIO(),
        )


@pytest.mark.django_db
def test_export_uses_package_model_label_and_parent_slug() -> None:
    parent = EditablePage.objects.create(
        page_type="documentation",
        title="Parent",
        slug="parent",
        content="<p>Parent</p>",
    )
    EditablePage.objects.create(
        page_type="documentation",
        title="Child",
        slug="child",
        content="<p>Child</p>",
        parent_page=parent,
    )

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp:
        output = Path(temp.name)
    call_command("manage_editable_pages", "export", "--output", str(output), stdout=StringIO())

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data[0]["model"] == "editable_pages.editablepage"
    child_entry = next(item for item in data if item["fields"]["slug"] == "child")
    assert child_entry["fields"]["parent_page_slug"] == "parent"


@pytest.mark.django_db
def test_export_dry_run_does_not_write_file() -> None:
    EditablePage.objects.create(
        page_type="faq",
        title="FAQ",
        slug="faq",
        content="<p>FAQ</p>",
    )
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp:
        output = Path(temp.name)
    output.unlink()

    call_command(
        "manage_editable_pages",
        "export",
        "--output",
        str(output),
        "--dry-run",
        stdout=StringIO(),
    )

    assert output.exists() is False
