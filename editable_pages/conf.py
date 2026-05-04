from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from django.conf import settings
from django.utils.module_loading import import_string

DEFAULT_PAGE_TYPES: list[tuple[str, str]] = [
    ("documentation", "Documentation"),
    ("help_index", "Help Index"),
    ("terms_of_service", "Terms of Service"),
    ("privacy_policy", "Privacy Policy"),
    ("faq", "FAQ"),
    ("user_guide", "User Guide"),
    ("tutorial", "Tutorial"),
    ("api_docs", "API Documentation"),
    ("changelog", "Changelog"),
    ("custom", "Custom Page"),
]
DEFAULT_URLS: dict[str, str] = {
    "documentation": "/docs",
    "help_index": "/help",
    "terms_of_service": "/terms-of-service",
    "privacy_policy": "/privacy-policy",
}
DEFAULT_CACHE_TIMEOUTS: dict[str, int] = {
    "content_pages": 900,
    "faqs": 604800,
}
DEFAULT_LEGAL_PAGE_TYPES: tuple[str, ...] = ("terms_of_service", "privacy_policy")


def _setting(name: str, default: Any) -> Any:
    return getattr(settings, f"EDITABLE_PAGES_{name}", default)


def _resolve_callable(value: Any) -> Callable[..., Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return cast(Callable[..., Any], import_string(value))
    if callable(value):
        return cast(Callable[..., Any], value)
    msg = f"Expected a dotted path or callable, got {type(value)!r}"
    raise TypeError(msg)


def get_page_type_choices() -> list[tuple[str, str]]:
    configured = _setting("PAGE_TYPES", DEFAULT_PAGE_TYPES)
    choices: list[tuple[str, str]] = []
    for value, label in configured:
        choices.append((str(value), str(label)))
    return choices


def get_legal_page_types() -> tuple[str, ...]:
    configured = _setting("LEGAL_PAGE_TYPES", DEFAULT_LEGAL_PAGE_TYPES)
    return tuple(str(page_type) for page_type in configured)


def get_default_url_mapping() -> dict[str, str]:
    configured = _setting("URLS", {})
    mapping = dict(DEFAULT_URLS)
    mapping.update({str(key): str(value) for key, value in dict(configured).items()})
    return mapping


def get_default_page_url() -> str:
    return str(_setting("DEFAULT_URL", "/"))


def resolve_page_url(page: Any) -> str:
    resolver = _resolve_callable(_setting("URL_RESOLVER", None))
    if resolver is not None:
        return str(resolver(page))
    return get_default_url_mapping().get(str(page.page_type), get_default_page_url())


def get_cache_timeouts() -> dict[str, int]:
    configured = _setting("CACHE_TIMEOUTS", {})
    timeouts = dict(DEFAULT_CACHE_TIMEOUTS)
    timeouts.update({str(key): int(value) for key, value in dict(configured).items()})
    return timeouts


def get_cache_timeout(scope: str, *, page_type: str | None = None) -> int:
    timeouts = get_cache_timeouts()
    default = int(timeouts.get(scope, 0))
    resolver = _resolve_callable(_setting("CACHE_TIMEOUT_RESOLVER", None))
    if resolver is None:
        return default
    return int(resolver(scope=scope, page_type=page_type, default=default))


def get_cache_namespace() -> str:
    return str(_setting("CACHE_NAMESPACE", "editable_pages"))


def get_cache_invalidator() -> Callable[..., Any] | None:
    return _resolve_callable(_setting("CACHE_INVALIDATOR", None))
