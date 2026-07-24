# Copilot Instructions for django-editable-pages

## Quick Start

This is a reusable Django package for admin-managed rich content pages with a
read-only API surface. Use `uv` for dependency management and `tox` as the
canonical local validation entry point. This repository currently targets
Python 3.13 only.

```bash
uv sync --extra dev
```

`uv.lock` is committed. Update it when dependency metadata changes, and keep CI
compatible with `uv sync --frozen --extra dev`.

## Build, Test, and Lint Commands

### Setup and Packaging
```bash
# Install the development toolchain
uv sync --extra dev

# Build wheel and sdist artifacts
uv run python -m build
```

### Tox Entry Points
```bash
# Run the default locally available tox environments
uv run tox

# Run one environment explicitly
uv run tox -e py313
uv run tox -e lint
uv run tox -e mypy
uv run tox -e security

# Run a single test file or test function through tox
uv run tox -e py313 -- tests/test_models.py
uv run tox -e py313 -- tests/test_api.py::test_pages_list_endpoint
```

### Direct Commands
```bash
# Run the full pytest suite
uv run pytest

# Run Ruff linting
uv run ruff check editable_pages tests

# Run mypy with the repository config
uv run mypy editable_pages tests

# Run security tooling directly
uv run bandit -q -r editable_pages -x editable_pages/migrations
uv run pip-audit
```

`tox` is the canonical entry point for local and CI checks. The configured
environments are `py313`, `lint`, `mypy`, and `security`, with optional `ruff`,
`bandit`, and `pip-audit` aliases for focused runs.

## High-Level Architecture

### Core Components

**Models and admin** (`editable_pages/models.py`, `editable_pages/admin.py`)
- `EditablePage` stores page hierarchy, visibility, featured/legal states, and
  rich HTML content
- Django admin integrates TinyMCE and history tracking for operator-managed
  content

**API surface** (`editable_pages/api.py`, `editable_pages/serializers.py`, `editable_pages/urls.py`)
- Read-only DRF endpoints serve page lists, detail views, featured pages, legal
  policies, and FAQs
- Host projects mount `editable_pages.urls` under their preferred API prefix

**Configuration and caching** (`editable_pages/conf.py`, `editable_pages/cache.py`)
- Settings drive page types, URL resolution, and cache TTL behavior
- Optional resolver hooks let host projects source cache and URL rules from
  application code instead of static settings

**TinyMCE defaults** (`editable_pages/tinymce_settings.py`)
- The package supplies a default `TINYMCE_DEFAULT_CONFIG`
- Host projects can layer overrides on top of the package defaults

**Management commands** (`editable_pages/management/`)
- `manage_editable_pages` imports and exports portable fixture or seed data for
  repo-managed content

## Key Conventions

### Code Style
- Use `from __future__ import annotations` when forward references are needed
- Ruff is the linting tool; line length is 99 characters
- Migration files are exempt from the normal line-length and import-order rules

### Django Patterns
- Keep API behavior read-only in the package; host-specific write flows belong
  outside the reusable app
- Treat stored HTML as trusted operator-managed content; do not assume it is
  safe for untrusted author input
- Preserve the optional resolver-hook pattern so consuming projects can connect
  this package to registry-backed configuration later

### Versioning and Release Flow
- `pyproject.toml` is the source of truth for the package version
- `editable_pages/__init__.py`, `uv.lock`'s editable `django-editable-pages`
  entry, and `django_editable_pages.egg-info/PKG-INFO` are committed mirrors
  that must stay aligned with `pyproject.toml`
- Use `uv run python scripts/release_version.py check-sync` to validate committed version metadata after packaging or release-flow changes
- Normal feature work should not bump the version manually
- Releases go through `.github/workflows/release.yml`, which creates a release
  bump PR, then creates the tag and GitHub Release after merge
- The release flow is GitHub-only for now; do not add PyPI publishing steps

## Git Workflow

### Using Worktrees
- Create branch worktrees under the shared `../../worktrees/` directory (full
  path: `/home/bjorn/workspace/web_projects/worktrees/`).
- Do not work directly on `main`; create a branch worktree first:
  ```bash
  git worktree add ../../worktrees/django-editable-pages-my-change -b my-change main
  cd ../../worktrees/django-editable-pages-my-change
  ```
- Commit and push from that worktree branch as usual.
- After the branch has been pushed and you no longer need the local checkout, or
  after the related PR/release has been published, remove the worktree and then
  delete the local branch:
  ```bash
  cd /home/bjorn/workspace/web_projects/pkgs/django-editable-pages
  git worktree remove ../../worktrees/django-editable-pages-my-change
  git branch -d my-change
  ```
- If the worktree has uncommitted local-only files, clean or intentionally
  discard them before removing the worktree. Use `git worktree remove --force`
  only when you mean to throw that local state away.

## Important Notes

- Tests use `tests.settings`
- `editable_pages/__init__.py`, `uv.lock`, and
  `django_editable_pages.egg-info/PKG-INFO` should stay in sync with packaging
  metadata changes
- Keep workflow path filters aligned with this repo's package path
