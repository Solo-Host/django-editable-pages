from __future__ import annotations

from hashlib import md5
from typing import Any

from django.core.cache import cache

from .conf import get_cache_invalidator, get_cache_namespace, get_cache_timeout


def _version_key(scope: str) -> str:
    return f"{get_cache_namespace()}:version:{scope}"


def get_cache_version(scope: str) -> int:
    version = cache.get(_version_key(scope))
    if version is None:
        cache.set(_version_key(scope), 1, None)
        return 1
    return int(version)


def bump_cache_version(scope: str) -> int:
    key = _version_key(scope)
    current = cache.get(key)
    next_value = int(current) + 1 if current is not None else 2
    cache.set(key, next_value, None)
    return next_value


def response_cache_key(scope: str, request_path: str, *, version_scope: str, variant: str) -> str:
    digest = md5(request_path.encode("utf-8"), usedforsecurity=False).hexdigest()
    version = get_cache_version(version_scope)
    return f"{get_cache_namespace()}:response:{scope}:{variant}:v{version}:{digest}"


def get_cached_payload(scope: str, request_path: str, *, version_scope: str, variant: str) -> Any:
    return cache.get(
        response_cache_key(scope, request_path, version_scope=version_scope, variant=variant),
    )


def set_cached_payload(
    scope: str,
    request_path: str,
    payload: Any,
    *,
    version_scope: str,
    timeout_scope: str,
    variant: str,
) -> None:
    cache.set(
        response_cache_key(scope, request_path, version_scope=version_scope, variant=variant),
        payload,
        get_cache_timeout(timeout_scope),
    )


def invalidate_page_caches(*, page_type: str | None = None, force: bool = False) -> None:
    bump_cache_version("content_pages")
    bump_cache_version("faqs")

    invalidator = get_cache_invalidator()
    if invalidator is not None:
        invalidator(page_type=page_type, force=force)
