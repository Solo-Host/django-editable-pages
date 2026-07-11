# django-editable-pages

Reusable Django app for admin-managed rich content pages with a public read-only API.

## Features

- `EditablePage` model with hierarchy, version notes, history tracking, and per-page visibility
- Django admin integration with TinyMCE-backed HTML fields
- Read-only DRF endpoints for page lists, detail, legal policies, featured pages, and FAQs
- Import/export management command for portable JSON fixtures and simpler repo-committed seed data
- Built-in cache versioning with optional host invalidation hooks
- Standalone configuration via Django settings, with optional resolver hooks for registry-backed setups

## Installation

```bash
uv add django-editable-pages
```

Add the package and its prerequisites to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "simple_history",
    "tinymce",
    "editable_pages",
]
```

`editable_pages` automatically applies a richer default `TINYMCE_DEFAULT_CONFIG`
for its `HTMLField` admin widgets when the app loads.

Run migrations:

```bash
python manage.py migrate editable_pages
```

## URL setup

Mount the package wherever you want the API to live:

```python
from django.urls import include, path

urlpatterns = [
    path(
        "api/v1/content/",
        include(("editable_pages.urls", "editable_pages"), namespace="editable_pages"),
    ),
]
```

## Model usage

```python
from editable_pages.models import EditablePage

EditablePage.objects.create(
    page_type="privacy_policy",
    title="Privacy Policy",
    slug="privacy-policy",
    content="<h1>Privacy Policy</h1><p>Your content here.</p>",
    visibility="public",
)
```

## Configuration

The package works in two modes:

1. **Standalone** via normal Django settings
2. **Optional registry-backed** via dotted-path resolver hooks

### Settings

| Setting | Purpose | Default |
| --- | --- | --- |
| `EDITABLE_PAGES_PAGE_TYPES` | Available `(value, label)` page types | Built-in defaults |
| `EDITABLE_PAGES_URLS` | Static `page_type -> frontend path` mapping | Docs/help/legal defaults |
| `EDITABLE_PAGES_DEFAULT_URL` | Fallback frontend path | `/` |
| `EDITABLE_PAGES_URL_RESOLVER` | Callable or dotted path resolving `page -> str` | unset |
| `EDITABLE_PAGES_LEGAL_PAGE_TYPES` | Page types returned by `legal_policies` | `("terms_of_service", "privacy_policy")` |
| `EDITABLE_PAGES_CACHE_TIMEOUTS` | Cache TTLs for `content_pages` and `faqs` | `900`, `604800` |
| `EDITABLE_PAGES_CACHE_TIMEOUT_RESOLVER` | Callable or dotted path resolving cache TTLs | unset |
| `EDITABLE_PAGES_CACHE_INVALIDATOR` | Optional host invalidation hook | unset |
| `EDITABLE_PAGES_CACHE_NAMESPACE` | Cache key namespace prefix | `editable_pages` |

### TinyMCE defaults

The package ships with a default `TINYMCE_DEFAULT_CONFIG` modeled after the
reference project configuration and applies it automatically during app loading.
If the consuming project defines `TINYMCE_DEFAULT_CONFIG`, those values are
merged on top of the package defaults so you only need to override the keys you
care about.

If you want to start from the package defaults explicitly in your project
settings, import and extend them:

```python
from editable_pages.tinymce_settings import (
    TINYMCE_DEFAULT_CONFIG as EDITABLE_PAGES_TINYMCE_DEFAULT_CONFIG,
)

TINYMCE_DEFAULT_CONFIG = {
    **EDITABLE_PAGES_TINYMCE_DEFAULT_CONFIG,
    "height": 600,
    "content_css": ["/static/css/editor.css"],
}
```

The package does not add any `django-filebrowser` settings. If the consuming
project installs filebrowser, `django-tinymce`'s native integration still
applies independently.

### Optional registry-backed integration

`django-editable-pages` does **not** depend on `django-system-resgistry`, but it is designed to work with a registry package if you install one later.

Example resolver:

```python
def editable_pages_cache_timeout(*, scope: str, page_type: str | None, default: int) -> int:
    del page_type
    from apps.core.models import SystemSetting

    mapping = {
        "content_pages": ("cache", "content_pages_timeout_seconds"),
        "faqs": ("cache", "faq_timeout_seconds"),
    }
    namespace, key = mapping.get(scope, ("cache", "unused"))
    return int(SystemSetting.get_value(namespace, key, default))


EDITABLE_PAGES_CACHE_TIMEOUT_RESOLVER = "config.editable_pages.editable_pages_cache_timeout"
```

Example URL resolver:

```python
def editable_pages_url(page) -> str:
    custom_urls = {
        "documentation": "/docs",
        "terms_of_service": "/terms-of-service",
        "privacy_policy": "/privacy-policy",
    }
    return custom_urls.get(page.page_type, f"/pages/{page.slug}")


EDITABLE_PAGES_URL_RESOLVER = "config.editable_pages.editable_pages_url"
```

## Management command

Use the package command to move portable fixture data in and out of the app:

```bash
python manage.py manage_editable_pages import --source fixtures/editable_pages.json
python manage.py manage_editable_pages import --source fixtures/help-pages.json --format seed --slug help
python manage.py manage_editable_pages export --output fixtures/editable_pages.json
python manage.py manage_editable_pages export --output fixtures/help-pages.json --format seed --page-type help_index --content-source fixture
```

The default exported fixture uses:

- the package model label (`editable_pages.editablepage`)
- `parent_page_slug` instead of parent primary keys for portability
- content-focused fields only, not environment-specific metadata

Use `--format seed` to export a simpler list of field dictionaries that is easier
to keep in a repository-controlled seed data file. Both fixture and seed imports
support filtering by `--slug`, `--page-type`, and `--visibility`; exports also
support `--content-source`.

## API endpoints

Assuming you mounted the URLs under `/api/v1/content/`:

| Endpoint | Purpose |
| --- | --- |
| `GET /pages/` | List active pages visible to the current caller |
| `GET /pages/{slug}/` | Retrieve a page by slug when visible to the current caller |
| `GET /pages/by_type/?page_type=faq` | Filter visible pages by type |
| `GET /pages/legal_policies/` | Return configured visible legal page types |
| `GET /pages/featured/` | Return visible featured pages |
| `GET /pages/faqs/` | Return visible FAQ pages |

## Frontend integration example

Keep framework-specific UI in the consuming app. A minimal TypeScript client is usually enough:

```ts
import axios from "axios";

export async function getPageBySlug(slug: string) {
  const response = await axios.get(`/api/v1/content/pages/${slug}/`);
  return response.data;
}
```

## HTML trust boundary

This package stores rich HTML and is intended for **trusted operator-managed content**. If your product allows untrusted authors to edit page content, add sanitization before save and/or before rendering on the frontend.

## Development

```bash
cd django-editable-pages
uv sync --extra dev
source .venv/bin/activate
pytest
ruff check editable_pages tests
mypy editable_pages tests
```
