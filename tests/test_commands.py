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


def _make_seed(pages: list[dict[str, object]], path: Path | None = None) -> Path:
    if path is None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp:
            path = Path(temp.name)
    path.write_text(json.dumps(pages), encoding="utf-8")
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
        "visibility": EditablePage.VISIBILITY_PUBLIC,
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


@pytest.mark.django_db
def test_export_seed_format_can_filter_fixture_managed_pages() -> None:
    EditablePage.objects.create(
        page_type="help_index",
        title="Help",
        slug="help",
        content="<p>Help</p>",
        visibility=EditablePage.VISIBILITY_AUTHENTICATED,
        content_source="fixture",
    )
    EditablePage.objects.create(
        page_type="documentation",
        title="Docs",
        slug="docs",
        content="<p>Docs</p>",
    )

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp:
        output = Path(temp.name)

    call_command(
        "manage_editable_pages",
        "export",
        "--output",
        str(output),
        "--format",
        "seed",
        "--page-type",
        "help_index",
        "--content-source",
        "fixture",
        stdout=StringIO(),
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data == [
        {
            "page_type": "help_index",
            "title": "Help",
            "slug": "help",
            "table_of_contents": "",
            "content": "<p>Help</p>",
            "meta_description": "",
            "display_order": 0,
            "parent_page_slug": None,
            "visibility": EditablePage.VISIBILITY_AUTHENTICATED,
            "is_active": True,
            "is_featured": False,
            "version_notes": "",
        },
    ]


@pytest.mark.django_db
def test_filtered_import_only_deactivates_matching_fixture_scope() -> None:
    EditablePage.objects.create(
        page_type="help_index",
        title="Old Help",
        slug="help",
        content="<p>Old help</p>",
        content_source="fixture",
    )
    terms = EditablePage.objects.create(
        page_type="terms_of_service",
        title="Terms",
        slug="terms",
        content="<p>Terms</p>",
        content_source="fixture",
    )
    fixture = _make_fixture(
        [_minimal_page(page_type="help_index", slug="help", content="<p>New help</p>")],
    )

    call_command(
        "manage_editable_pages",
        "import",
        "--source",
        str(fixture),
        "--page-type",
        "help_index",
        stdout=StringIO(),
    )

    help_page = EditablePage.objects.get(slug="help")
    terms.refresh_from_db()
    assert help_page.content == "<p>New help</p>"
    assert help_page.is_active is True
    assert terms.is_active is True


@pytest.mark.django_db
def test_import_can_filter_seed_entries_by_visibility() -> None:
    seed = _make_seed(
        [
            _minimal_page(slug="public-help", page_type="help_index"),
            _minimal_page(
                slug="private-help",
                page_type="help_index",
                visibility=EditablePage.VISIBILITY_AUTHENTICATED,
            ),
        ],
    )
    out = StringIO()

    call_command(
        "manage_editable_pages",
        "import",
        "--source",
        str(seed),
        "--format",
        "seed",
        "--visibility",
        "authenticated",
        stdout=out,
    )

    assert EditablePage.objects.filter(slug="private-help").exists()
    assert not EditablePage.objects.filter(slug="public-help").exists()
    assert "1 created" in out.getvalue()
