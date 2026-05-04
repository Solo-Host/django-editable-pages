from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from editable_pages.cache import invalidate_page_caches
from editable_pages.models import EditablePage

DEFAULT_FIXTURE = "fixtures/editable_pages.json"
SYNC_FIELDS = [
    "page_type",
    "title",
    "content",
    "table_of_contents",
    "meta_description",
    "display_order",
    "is_active",
    "is_featured",
    "version_notes",
]
EXPORT_FIELDS = [
    "page_type",
    "title",
    "slug",
    "table_of_contents",
    "content",
    "meta_description",
    "display_order",
    "parent_page_slug",
    "is_active",
    "is_featured",
    "version_notes",
]


class Command(BaseCommand):
    help = "Import or export editable pages."

    def add_arguments(self, parser) -> None:
        subparsers = parser.add_subparsers(dest="action", help="Action to perform.")

        import_parser = subparsers.add_parser("import", help="Import pages from a fixture.")
        import_parser.add_argument(
            "--source",
            default=DEFAULT_FIXTURE,
            help=f"Path to the JSON fixture file (default: {DEFAULT_FIXTURE})",
        )
        import_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )
        import_parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all fixture-managed pages before importing.",
        )

        export_parser = subparsers.add_parser("export", help="Export pages to a fixture.")
        export_parser.add_argument(
            "--output",
            default=DEFAULT_FIXTURE,
            help=f"Output file path (default: {DEFAULT_FIXTURE})",
        )
        export_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview export without writing the file.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        action = options.get("action")
        if action == "import":
            self._handle_import(options)
            return
        if action == "export":
            self._handle_export(options)
            return
        raise CommandError("Please specify an action: import or export")

    def _handle_import(self, options: dict[str, Any]) -> None:
        source_path = self._resolve_path(options["source"])
        dry_run = bool(options["dry_run"])
        clear = bool(options["clear"])

        if not source_path.exists():
            raise CommandError(f"Fixture file not found: {source_path}")

        entries = self._load_fixture(source_path)
        if dry_run:
            self.stdout.write(self.style.NOTICE("=== DRY RUN — no changes will be made ==="))

        stats = {"created": 0, "updated": 0, "unchanged": 0, "deactivated": 0, "cleared": 0}
        parent_links: list[tuple[str, str | None]] = []
        seen_slugs: set[str] = set()

        with transaction.atomic():
            if clear:
                stats["cleared"] = self._clear_managed_pages(dry_run)

            for entry in entries:
                fields = self._normalize_entry(entry)
                slug = str(fields.get("slug", "")).strip()
                if not slug:
                    self.stdout.write(
                        self.style.WARNING(f"  Skipping entry missing slug: {entry}"),
                    )
                    continue

                seen_slugs.add(slug)
                parent_links.append((slug, self._optional_str(fields.get("parent_page_slug"))))
                result = self._sync_page(fields, dry_run)
                stats[result] += 1

            self._apply_parent_links(parent_links, dry_run)
            stats["deactivated"] = self._deactivate_removed_pages(seen_slugs, dry_run)

            if dry_run:
                transaction.set_rollback(True)
            else:
                invalidate_page_caches(force=True)

        self._print_import_summary(stats, dry_run)

    def _handle_export(self, options: dict[str, Any]) -> None:
        output_path = self._resolve_path(options["output"])
        dry_run = bool(options["dry_run"])
        pages = EditablePage.objects.all().select_related("parent_page").order_by("slug")
        if not pages.exists():
            self.stdout.write(self.style.WARNING("No editable pages to export."))
            return

        fixture_data = [self._page_to_fixture_entry(page) for page in pages]
        if dry_run:
            self.stdout.write(self.style.NOTICE("=== DRY RUN — file will not be written ==="))
            self.stdout.write(f"  Would export {len(fixture_data)} page(s) to {output_path}")
            for entry in fixture_data:
                fields = entry["fields"]
                self.stdout.write(f"  - {fields['page_type']}/{fields['slug']}")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(fixture_data, handle, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f"Exported {len(fixture_data)} page(s) to {output_path}"),
        )

    def _load_fixture(self, path: Path) -> list[dict[str, Any]]:
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError) as exc:
            raise CommandError(f"Failed to read fixture file: {exc}") from exc

        if not isinstance(data, list):
            raise CommandError("Fixture file must contain a JSON array.")
        return data

    def _normalize_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(entry, dict):
            raise CommandError(f"Fixture entries must be objects, got {type(entry)!r}")
        fields = entry.get("fields", entry)
        if not isinstance(fields, dict):
            raise CommandError("Fixture entry fields must be an object.")
        return fields

    def _sync_page(self, fields: dict[str, Any], dry_run: bool) -> str:
        slug = str(fields["slug"])
        defaults = {key: fields[key] for key in SYNC_FIELDS if key in fields}
        defaults["content_source"] = "fixture"

        try:
            existing = EditablePage.objects.get(slug=slug)
        except EditablePage.DoesNotExist:
            existing = None

        if existing is None:
            if dry_run:
                self.stdout.write(f"  Would create: {defaults.get('page_type', 'unknown')}/{slug}")
            else:
                EditablePage.objects.create(slug=slug, **defaults)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created: {defaults.get('page_type', 'unknown')}/{slug}",
                    ),
                )
            return "created"

        changed_fields = [
            key for key, new_value in defaults.items() if getattr(existing, key, None) != new_value
        ]
        if not changed_fields:
            return "unchanged"

        if dry_run:
            self.stdout.write(
                f"  Would update: {existing.page_type}/{slug} "
                f"({', '.join(changed_fields)})",
            )
        else:
            for key, value in defaults.items():
                setattr(existing, key, value)
            existing.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Updated: {existing.page_type}/{slug} ({', '.join(changed_fields)})",
                ),
            )
        return "updated"

    def _apply_parent_links(
        self,
        parent_links: list[tuple[str, str | None]],
        dry_run: bool,
    ) -> None:
        for slug, parent_slug in parent_links:
            child = EditablePage.objects.filter(slug=slug).first()
            if child is None:
                continue

            parent = EditablePage.objects.filter(slug=parent_slug).first() if parent_slug else None
            if child.parent_page_id == (parent.id if parent else None):
                continue

            if dry_run:
                if parent_slug:
                    self.stdout.write(f"  Would set parent: {slug} -> {parent_slug}")
                continue

            child.parent_page = parent
            child.save(update_fields={"parent_page", "updated_at"})

    def _deactivate_removed_pages(self, seen_slugs: set[str], dry_run: bool) -> int:
        managed_pages = EditablePage.objects.filter(content_source="fixture", is_active=True)
        count = 0
        for page in managed_pages:
            if page.slug in seen_slugs:
                continue
            if dry_run:
                self.stdout.write(f"  Would deactivate: {page.page_type}/{page.slug}")
            else:
                page.is_active = False
                page.save(update_fields={"is_active", "updated_at"})
                self.stdout.write(
                    self.style.WARNING(f"  Deactivated: {page.page_type}/{page.slug}"),
                )
            count += 1
        return count

    def _clear_managed_pages(self, dry_run: bool) -> int:
        queryset = EditablePage.objects.filter(content_source="fixture")
        count = queryset.count()
        if count == 0:
            return 0
        if dry_run:
            self.stdout.write(f"  Would delete {count} fixture-managed page(s)")
            return count
        queryset.delete()
        self.stdout.write(self.style.WARNING(f"  Deleted {count} fixture-managed page(s)"))
        return count

    def _print_import_summary(self, stats: dict[str, int], dry_run: bool) -> None:
        prefix = "DRY RUN " if dry_run else ""
        parts = []
        if stats["cleared"]:
            parts.append(f"{stats['cleared']} cleared")
        parts.extend(
            [
                f"{stats['created']} created",
                f"{stats['updated']} updated",
                f"{stats['unchanged']} unchanged",
            ],
        )
        if stats["deactivated"]:
            parts.append(f"{stats['deactivated']} deactivated")
        self.stdout.write(self.style.SUCCESS(f"{prefix}Import complete: {', '.join(parts)}"))

    def _page_to_fixture_entry(self, page: EditablePage) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "page_type": page.page_type,
            "title": page.title,
            "slug": page.slug,
            "table_of_contents": page.table_of_contents,
            "content": page.content,
            "meta_description": page.meta_description,
            "display_order": page.display_order,
            "parent_page_slug": page.parent_page.slug if page.parent_page else None,
            "is_active": page.is_active,
            "is_featured": page.is_featured,
            "version_notes": page.version_notes,
        }
        return {
            "model": page._meta.label_lower,
            "fields": {name: fields[name] for name in EXPORT_FIELDS},
        }

    def _resolve_path(self, path_str: str) -> Path:
        path = Path(path_str)
        if path.is_absolute():
            return path
        base_dir = getattr(settings, "BASE_DIR", Path.cwd())
        return Path(base_dir) / path

    def _optional_str(self, value: Any) -> str | None:
        if value in {None, ""}:
            return None
        return str(value)
