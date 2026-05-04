from __future__ import annotations

from typing import Any

HOOK_CALLS: list[tuple[str | None, bool]] = []


def reset_hook_calls() -> None:
    HOOK_CALLS.clear()


def custom_url_resolver(page: Any) -> str:
    return f"/pages/{page.slug}/"


def cache_timeout_resolver(*, scope: str, page_type: str | None = None, default: int = 0) -> int:
    del page_type
    if scope == "content_pages":
        return 123
    if scope == "faqs":
        return 456
    return default


def record_cache_invalidator(*, page_type: str | None, force: bool) -> None:
    HOOK_CALLS.append((page_type, force))
