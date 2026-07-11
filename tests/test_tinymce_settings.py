from __future__ import annotations

import importlib

import tinymce.settings

from editable_pages.tinymce_settings import (
    TINYMCE_DEFAULT_CONFIG,
    apply_tinymce_default_config,
    build_tinymce_default_config,
)


def test_build_tinymce_default_config_returns_a_copy_with_overrides() -> None:
    config = build_tinymce_default_config({"height": 640})

    assert config["height"] == 640
    assert config["width"] == "100%"

    config["content_css"].append("/static/css/editor.css")
    assert "/static/css/editor.css" not in TINYMCE_DEFAULT_CONFIG["content_css"]


def test_apply_tinymce_default_config_merges_project_overrides(settings, monkeypatch) -> None:
    settings.TINYMCE_DEFAULT_CONFIG = {"height": 720, "toolbar": "bold italic"}
    monkeypatch.setattr(tinymce.settings, "DEFAULT_CONFIG", {"height": 500})

    apply_tinymce_default_config()

    assert settings.TINYMCE_DEFAULT_CONFIG["height"] == 720
    assert settings.TINYMCE_DEFAULT_CONFIG["width"] == "100%"
    assert settings.TINYMCE_DEFAULT_CONFIG["toolbar"] == "bold italic"
    assert tinymce.settings.DEFAULT_CONFIG["height"] == 720
    assert tinymce.settings.DEFAULT_CONFIG["width"] == "100%"


def test_editable_pages_app_import_applies_default_tinymce_config(settings, monkeypatch) -> None:
    from editable_pages import apps as editable_pages_apps

    settings.TINYMCE_DEFAULT_CONFIG = {"height": 615}
    monkeypatch.setattr(tinymce.settings, "DEFAULT_CONFIG", {"height": 500})

    importlib.reload(editable_pages_apps)

    assert settings.TINYMCE_DEFAULT_CONFIG["height"] == 615
    assert settings.TINYMCE_DEFAULT_CONFIG["width"] == "100%"
    assert tinymce.settings.DEFAULT_CONFIG["height"] == 615
    assert tinymce.settings.DEFAULT_CONFIG["width"] == "100%"
